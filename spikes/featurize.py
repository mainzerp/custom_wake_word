"""Spike C (part 1): parallel augmentation + spectrogram featurization into RaggedMmap.

Mirrors the old trainer's augmenter settings, but fans the CPU work out over a process pool.

  py-train spikes/featurize.py --input data/spikes/piper --output data/spikes/features/piper
"""

import argparse
import os
import random
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import soundfile as sf

DATASETS = Path(os.environ.get("CWW_DATA", "data")) / "datasets"
SPLITS = {"training": ("train", 2, 10), "validation": ("validation", 1, 10), "testing": ("test", 1, 1)}

_augmenter = None


def _init_worker(seed: int) -> None:
    global _augmenter
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    from microwakeword.audio.augmentation import Augmentation

    np.random.seed(seed + os.getpid())
    random.seed(seed + os.getpid())
    _augmenter = Augmentation(
        augmentation_duration_s=3.2,
        augmentation_probabilities={
            "SevenBandParametricEQ": 0.1,
            "TanhDistortion": 0.05,
            "PitchShift": 0.15,
            "BandStopFilter": 0.1,
            "AddColorNoise": 0.1,
            "AddBackgroundNoise": 0.7,
            "Gain": 0.8,
            "RIR": 0.7,
        },
        impulse_paths=[str(DATASETS / "mit_rirs_16k")],
        background_paths=[str(DATASETS / d) for d in ("chime_16k", "fma_16k", "audioset_16k")
                          if (DATASETS / d).exists()],
        background_min_snr_db=5,
        background_max_snr_db=10,
        min_jitter_s=0.2,
        max_jitter_s=0.3,
    )


def _featurize(job: tuple[str, int, int]) -> list[np.ndarray]:
    from microwakeword.audio.audio_utils import generate_features_for_clip, remove_silence_webrtc

    path, repeat, slide_frames = job
    audio, sr = sf.read(path, dtype="float32")
    assert sr == 16000, f"{path}: expected 16 kHz, got {sr}"
    audio = remove_silence_webrtc(audio)
    out = []
    for _ in range(repeat):
        spec = generate_features_for_clip(_augmenter.augment_clip(audio), step_ms=10)
        length = spec.shape[0] - slide_frames + 1
        out.extend(spec[i : i + length] for i in range(slide_frames))
    return out


def main() -> None:
    from mmap_ninja.ragged import RaggedMmap

    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--seed", type=int, default=10)
    args = ap.parse_args()

    files = sorted(str(p) for p in args.input.glob("*.wav"))
    random.Random(args.seed).shuffle(files)
    n_val = n_test = max(1, len(files) // 10)
    parts = {"train": files[n_val + n_test :], "validation": files[:n_val], "test": files[n_val : n_val + n_test]}

    t0 = time.perf_counter()
    with Pool(args.workers, initializer=_init_worker, initargs=(args.seed,)) as pool:
        for split_dir, (name, repeat, slide) in SPLITS.items():
            t = time.perf_counter()
            jobs = [(f, repeat, slide) for f in parts[name]]
            gen = (spec for specs in pool.imap(_featurize, jobs, chunksize=16) for spec in specs)
            out = args.output / split_dir / "wakeword_mmap"
            out.parent.mkdir(parents=True, exist_ok=True)
            RaggedMmap.from_generator(out_dir=str(out), sample_generator=gen, batch_size=1000, verbose=False)
            print(f"{split_dir}: {len(jobs)} clips -> {len(RaggedMmap(str(out)))} spectrograms "
                  f"in {time.perf_counter() - t:.1f}s")
    print(f"total {time.perf_counter() - t0:.1f}s with {args.workers} workers")


if __name__ == "__main__":
    main()
