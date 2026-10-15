"""Spike A: batched Piper generation on GPU, measure throughput.

Run inside the container:
  /opt/venv-tts/bin/python spikes/piper_throughput.py --phrase Dscharwis --count 2000
"""

import argparse
import random
import time
import urllib.request
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import soundfile as sf
from piper import PiperVoice
from piper.patch_voice_with_alignment import add_alignment_output
from scipy.signal import resample_poly

VOICE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/mls/medium/{name}"
TARGET_SR = 16000


def ensure_voice(models_dir: Path, name: str) -> Path:
    models_dir.mkdir(parents=True, exist_ok=True)
    for fname in (f"{name}.onnx", f"{name}.onnx.json"):
        dest = models_dir / fname
        if not dest.exists():
            print(f"downloading {fname}")
            urllib.request.urlretrieve(VOICE_URL.format(name=fname), dest)
    return models_dir / f"{name}.onnx"


def batched_session(model: Path, cpu: bool) -> ort.InferenceSession:
    """Piper exports `sid` with a fixed batch dim of 1; relax it so each row gets its own speaker.
    Also expose per-phoneme durations so padded rows can be cropped to their true length."""
    patched = model.with_suffix(".batch.onnx")
    if not patched.exists():
        m = onnx.load(str(model))
        for inp in m.graph.input:
            if inp.name == "sid":
                inp.type.tensor_type.shape.dim[0].dim_param = "batch_size"
        add_alignment_output(m)
        onnx.save(m, str(patched))
    providers = ["CPUExecutionProvider"] if cpu else [
        ("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC"}), "CPUExecutionProvider"
    ]
    session = ort.InferenceSession(str(patched), providers=providers)
    if not cpu and "CUDAExecutionProvider" not in session.get_providers():
        raise RuntimeError("CUDAExecutionProvider failed to load; refusing to fall back to CPU")
    return session


def trim(audio: np.ndarray, rel_threshold: float = 0.05, pad: int = 1600) -> np.ndarray:
    idx = np.flatnonzero(np.abs(audio) > rel_threshold * np.abs(audio).max())
    if idx.size == 0:
        return audio[:0]
    return audio[max(idx[0] - pad, 0) : idx[-1] + pad]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phrase", nargs="+", default=["Dscharwis"])
    ap.add_argument("--count", type=int, default=2000)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--voice", default="de_DE-mls-medium")
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--cpu", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    model = ensure_voice(args.data / "models" / "piper", args.voice)
    out_dir = args.data / "spikes" / "piper"
    out_dir.mkdir(parents=True, exist_ok=True)

    voice = PiperVoice.load(model)
    session = batched_session(model, args.cpu)
    print("providers:", session.get_providers(), "ort device:", ort.get_device())
    sr = voice.config.sample_rate
    hop = voice.config.hop_length
    speakers = list(range(voice.config.num_speakers))
    phrase_ids = [
        [i for sentence in voice.phonemize(p) for i in voice.phonemes_to_ids(sentence)]
        for p in args.phrase
    ]
    for p, ids in zip(args.phrase, phrase_ids):
        print(f"{p!r}: {len(ids)} phoneme ids")

    t0 = time.perf_counter()
    written = rejected = 0
    rejected_durs: list[float] = []
    total_audio = 0.0
    while written < args.count:
        n = min(args.batch, args.count - written)
        ids = rng.choice(phrase_ids)
        inputs = {
            "input": np.tile(np.array(ids, dtype=np.int64), (n, 1)),
            "input_lengths": np.full(n, len(ids), dtype=np.int64),
            "scales": np.array(
                [rng.uniform(0.3, 0.8), rng.uniform(0.55, 1.0), rng.uniform(0.2, 0.5)],
                dtype=np.float32,
            ),
            "sid": np.array([rng.choice(speakers) for _ in range(n)], dtype=np.int64),
        }
        audio, widths = session.run(None, inputs)
        lengths = widths.reshape(n, -1).sum(axis=1).astype(np.int64) * hop
        for row, length in zip(audio.reshape(n, -1), lengths):
            clip = trim(resample_poly(row[:length], TARGET_SR, sr).astype(np.float32))
            dur = clip.size / TARGET_SR
            if not 0.3 <= dur <= 2.0:
                rejected += 1
                rejected_durs.append(dur)
                continue
            peak = np.abs(clip).max()
            sf.write(out_dir / f"{written:06d}.wav", clip / peak * 0.9, TARGET_SR, subtype="PCM_16")
            total_audio += dur
            written += 1
            if written >= args.count:
                break
        elapsed = time.perf_counter() - t0
        print(f"\r{written}/{args.count}  {written / elapsed:.1f} samples/s  rejected={rejected}", end="")

    elapsed = time.perf_counter() - t0
    print(
        f"\ndone: {written} samples in {elapsed:.1f}s = {written / elapsed:.1f} samples/s "
        f"({written / elapsed * 60:.0f}/min), avg {total_audio / max(written, 1):.2f}s, "
        f"rejected {rejected}, est. 50k: {50000 / (written / elapsed) / 60:.1f} min"
    )
    if rejected_durs:
        print("rejected durations min/median/max:", np.percentile(rejected_durs, [0, 50, 100]).round(2))


if __name__ == "__main__":
    main()
