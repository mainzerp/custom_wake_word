"""Augment clips and turn them into microfrontend spectrograms, cached per item (runs in the TF venv, CPU pool).

  <cache>/<key>/training/features_mmap     2 augmented copies x 10 one-frame slides per clip, last CROP frames
  <cache>/<key>/validation/features_mmap   1 copy x 10 slides, last CROP frames
  <cache>/<key>/testing/features_mmap      1 copy, full 3.2 s (streaming calibration needs the lead-in)
  <cache>/<key>/done                       written last; an item without it is rebuilt

Spectrograms are stored as the raw uint16 microfrontend values (microWakeWord scales them by 0.0390625 on load):
half the size of float32 and lossless. Training only ever reads the last spectrogram_length frames of a slide
(truncate_start), so storing more is waste; CROP equals spectrogram_length of the model in trainer/train/run.py.

  py-train -m trainer.train.featurize --project data/projects/dscharwis
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import signal
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf

from trainer.paths import DATASETS
from trainer.train.sources import Item, split_of

CROP = 178
SCALE = 0.0390625
SPLITS = {"training": (2, 10, True), "validation": (1, 10, True), "testing": (1, 1, False)}  # repeat, slides, crop

_augmenter = None


def _init_worker(seed: int) -> None:
    global _augmenter
    # The job's stop signal reaches the whole process group; only the parent handles it, a dead worker would hang imap.
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
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
        background_paths=[str(DATASETS / d) for d in ("chime_16k", "fma_16k", "audioset_16k") if (DATASETS / d).exists()],
        background_min_snr_db=5,
        background_max_snr_db=10,
        min_jitter_s=0.2,
        max_jitter_s=0.3,
    )


def _featurize(job: tuple[np.ndarray, int, int, bool]) -> list[np.ndarray]:
    from microwakeword.audio.audio_utils import generate_features_for_clip, remove_silence_webrtc

    audio, repeat, slides, crop = job
    audio = remove_silence_webrtc(audio)
    out = []
    for _ in range(repeat):
        spec = generate_features_for_clip(_augmenter.augment_clip(audio), step_ms=10)
        spec = np.round(spec / SCALE).astype(np.uint16)
        length = spec.shape[0] - slides + 1
        for i in range(slides):
            s = spec[i:i + length]
            out.append(s[-CROP:] if crop else s)
    return out


def item_clips(item: Item) -> list[tuple[str, np.ndarray]]:
    if item.kind == "shard":
        name = Path(item.path).name
        with np.load(item.path) as d:
            audio, offsets = d["audio"], d["offsets"]
            return [(f"{name}:{i}", audio[offsets[i]:offsets[i + 1]].astype(np.float32) / 32767)
                    for i in range(len(offsets) - 1)]
    out = []
    for f in sorted(Path(item.path).glob("*.wav")):
        audio, sr = sf.read(f, dtype="float32", always_2d=False)
        if sr != 16000:
            raise ValueError(f"{f}: expected 16 kHz, got {sr}")
        out.append((f.name, audio if audio.ndim == 1 else audio.mean(axis=1)))
    return out


class Stopped(Exception):
    pass


def build_item(pool: Pool, item: Item, on_clips: Callable[[int], None], stop: Callable[[], bool] = lambda: False) -> dict:
    """Featurize one item into its cache dir (atomic: built in a temp dir, renamed when complete)."""
    from mmap_ninja.ragged import RaggedMmap

    final = item.cache
    tmp = final.with_name(f"{final.name}.tmp{os.getpid()}")
    shutil.rmtree(tmp, ignore_errors=True)
    clips = item_clips(item)
    counts = {}
    for split, (repeat, slides, crop) in SPLITS.items():
        chosen = [a for name, a in clips if split_of(name) == split and len(a) > 1600]
        counts[split] = len(chosen)
        if not chosen:
            continue

        def gen():
            for specs in pool.imap(_featurize, [(a, repeat, slides, crop) for a in chosen], chunksize=8):
                if stop():
                    raise Stopped
                on_clips(1)
                yield from specs

        out = tmp / split / "features_mmap"
        out.parent.mkdir(parents=True, exist_ok=True)
        RaggedMmap.from_generator(out_dir=str(out), sample_generator=gen(), batch_size=2048, verbose=False)
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "done").write_text(json.dumps({"kind": item.kind, "path": item.path, "clips": counts}), encoding="utf-8")
    if final.exists():
        shutil.rmtree(final)
    os.replace(tmp, final)
    return counts


def featurize(items: list[Item], workers: int, progress: Callable[[dict], None], stop: Callable[[], bool]) -> None:
    todo = [i for i in items if not (i.cache / "done").is_file()]
    total = sum(i.clips for i in todo)
    state = {"done": 0, "total": total, "items": len(todo), "item": 0, "t0": time.perf_counter()}

    def on_clips(n: int) -> None:
        state["done"] += n
        if state["done"] % 50 == 0 or state["done"] == total:
            progress(state)

    if not todo:
        progress(state)
        return
    with Pool(workers, initializer=_init_worker, initargs=(10,)) as pool:
        for k, item in enumerate(todo, 1):
            state["item"] = k
            try:
                build_item(pool, item, on_clips, stop)
            except Stopped:
                shutil.rmtree(item.cache.with_name(f"{item.cache.name}.tmp{os.getpid()}"), ignore_errors=True)
                return
            progress(state)


def split_counts(item: Item) -> dict:
    """Clips per split of a built item (from its done marker)."""
    try:
        return json.loads((item.cache / "done").read_text(encoding="utf-8"))["clips"]
    except (OSError, ValueError, KeyError):
        return {}


def default_workers() -> int:
    return max(1, min(12, (os.cpu_count() or 2) - 2))


def main() -> None:
    from trainer import projects
    from trainer.train.sources import project_sources

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=default_workers())
    args = ap.parse_args()
    projects.load(args.project)
    items = [i for s in project_sources(args.project) for i in s.items]
    t0 = time.perf_counter()

    def show(s: dict) -> None:
        rate = s["done"] / max(1e-6, time.perf_counter() - s["t0"])
        print(f"item {s['item']}/{s['items']}: {s['done']}/{s['total']} clips, {rate:.1f} clips/s", flush=True)

    featurize(items, args.workers, show, lambda: False)
    print(f"done in {time.perf_counter() - t0:.0f}s")


if __name__ == "__main__":
    main()
