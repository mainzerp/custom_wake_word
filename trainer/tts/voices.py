"""Reference voice bank for voice-cloning TTS (runs in the OmniVoice venv).

  py-omni -m trainer.tts.voices build --language de --max 300

Source: Kartoffelphon Arrow shards in data/downloads/kartoffelphon/ (German podcasts + LibriVox, CC-BY 4.0).
One crop per (show, speaker), 2.5-5 s at 24 kHz, cut at speech pauses and transcribed with Whisper (the crop
cuts sentences, so the original transcript does not match). Output: data/voices/<language>/<id>.wav + voices.json.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import random
from pathlib import Path

import numpy as np
import pyarrow.ipc as ipc
import soundfile as sf
from scipy.signal import resample_poly

from trainer.paths import DATA, VOICES

RATE = 24000
MIN_CROP_S, MAX_CROP_S = 2.5, 5.0
ENGLISH = {"the", "and", "was", "of", "that", "to", "i", "it", "my", "when", "if", "you", "is"}
SOURCES = {"de": DATA / "downloads" / "kartoffelphon"}


def voice_dir(language: str) -> Path:
    return VOICES / language


def load_bank(language: str) -> list[dict]:
    path = voice_dir(language) / "voices.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def median_f0(y: np.ndarray, sr: int) -> float:
    """Rough median pitch from frame autocorrelation; only used to balance male/female voices."""
    frame, hop = int(0.04 * sr), int(0.01 * sr)
    lo, hi = sr // 400, sr // 60
    rms = np.array([np.sqrt(np.mean(y[i:i + frame] ** 2)) for i in range(0, len(y) - frame, hop)])
    f0 = []
    for k, i in enumerate(range(0, len(y) - frame, hop)):
        if rms[k] < np.percentile(rms, 60):
            continue
        x = y[i:i + frame] - y[i:i + frame].mean()
        ac = np.correlate(x, x, "full")[frame - 1:]
        if ac[0] <= 0:
            continue
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] / ac[0] > 0.4:
            f0.append(sr / lag)
    return float(np.median(f0)) if f0 else float("nan")


def crop_at_pauses(y: np.ndarray, sr: int) -> np.ndarray | None:
    """Cut from speech onset to the quietest point 2.5-5 s later, so the crop holds whole words only.

    A crop ending mid-word makes voice cloning continue the cut-off word in front of the wake word."""
    hop = int(0.01 * sr)
    rms = np.sqrt(np.convolve(y ** 2, np.ones(5 * hop) / (5 * hop), mode="same"))[::hop]
    loud = rms > 0.1 * rms.max()
    if not loud.any():
        return None
    start = max(0, int(np.argmax(loud)) - 10)
    lo, hi = start + int(MIN_CROP_S * 100), min(len(rms), start + int(MAX_CROP_S * 100))
    if hi - lo < 10:
        return None
    end = lo + int(np.argmin(rms[lo:hi]))
    if rms[end] > 0.05 * rms.max():
        return None
    return y[start * hop:end * hop + 5 * hop]


def candidates(language: str, rng: random.Random) -> list[dict]:
    shards = sorted(SOURCES[language].glob("*.arrow"))
    if not shards:
        raise FileNotFoundError(f"no Arrow shards in {SOURCES[language]}")
    seen, out = set(), []
    for shard in shards:
        table = ipc.open_stream(shard).read_all()
        meta = table.select(["text", "start", "end", "speaker", "dnsmos", "podcast_name", "episode_name"]).to_pylist()
        order = list(range(len(meta)))
        rng.shuffle(order)
        for i in order:
            r = meta[i]
            show = r["episode_name"].split("_")[0] if r["podcast_name"] == "librivox" else r["podcast_name"]
            words = set(r["text"].lower().replace(",", " ").replace(".", " ").split())
            if (show, r["speaker"]) in seen or not 4.0 <= r["end"] - r["start"] <= 15.0 or r["dnsmos"] < 3.1 \
                    or len(words & ENGLISH) >= 2:
                continue
            seen.add((show, r["speaker"]))
            out.append({"shard": shard, "row": i, "source": r["podcast_name"], "show": show, "speaker": r["speaker"],
                        "dnsmos": round(r["dnsmos"], 2)})
    return out


def build(language: str, max_voices: int, seed: int) -> None:
    import torch
    from transformers import pipeline

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available")
    rng = random.Random(seed)
    cands = candidates(language, rng)
    print(f"{len(cands)} candidate speakers", flush=True)
    tables: dict[Path, object] = {}
    crops = []
    for c in cands:
        table = tables.setdefault(c["shard"], ipc.open_stream(c["shard"]).read_all())
        raw = table.column("audio")[c["row"]].as_py()["bytes"]
        y, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=True)
        g = np.gcd(sr, RATE)
        y = resample_poly(y.mean(1), RATE // g, sr // g).astype(np.float32)
        crop = crop_at_pauses(y, RATE)
        if crop is None or np.abs(crop).max() < 1e-3:
            continue
        crops.append((c, crop / np.abs(crop).max() * 0.9, median_f0(crop, RATE)))

    male = [x for x in crops if x[2] < 160]
    female = [x for x in crops if x[2] >= 160]
    half = max_voices // 2
    chosen = male[:half] + female[:max_voices - min(half, len(male))]
    chosen = (chosen + [x for x in crops if x not in chosen])[:max_voices]

    asr = pipeline("automatic-speech-recognition", model="openai/whisper-large-v3-turbo", dtype=torch.float16,
                   device="cuda:0")
    audio16 = [resample_poly(x[1], 2, 3).astype(np.float32) for x in chosen]
    texts = asr([{"raw": a, "sampling_rate": 16000} for a in audio16], batch_size=16,
                generate_kwargs={"language": "german" if language == "de" else language, "task": "transcribe"})

    out = voice_dir(language)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.wav"):
        f.unlink()
    bank = []
    for n, ((c, crop, f0), t) in enumerate(zip(chosen, texts)):
        text = t["text"].strip()
        if len(text.split()) < 3:
            continue
        vid = f"{language}{n:04d}"
        sf.write(out / f"{vid}.wav", crop, RATE, subtype="PCM_16")
        bank.append({"id": vid, "text": text, "f0": None if np.isnan(f0) else round(f0, 1),
                     "gender": "m" if f0 < 160 else "f" if f0 >= 160 else None, "source": c["source"],
                     "show": c["show"], "dnsmos": c["dnsmos"]})
    tmp = out / "voices.json.tmp"
    tmp.write_text(json.dumps(bank, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, out / "voices.json")
    g = [b["gender"] for b in bank]
    print(f"wrote {len(bank)} voices ({g.count('m')} m, {g.count('f')} f) to {out}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--language", default="de", choices=sorted(SOURCES))
    b.add_argument("--max", type=int, default=300)
    b.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    build(args.language, args.max, args.seed)


if __name__ == "__main__":
    main()
