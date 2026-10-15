"""Compact store for synthetic clips: few large shards instead of tens of thousands of WAV files.

  <project>/generated/tts/corpus.json        index: voice, phrases, shards (name, count, seconds)
  <project>/generated/tts/shard-000000.npz   audio (int16, all clips concatenated), offsets (n+1),
                                              speaker, phrase (index into phrases), scales (n x 3)

All clips are 16 kHz mono. Shards and the index are written atomically, so readers never see partial data.
"""

from __future__ import annotations

import io
import json
import os
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000


def corpus_dir(project: Path) -> Path:
    return project / "generated" / "tts"


def load_index(path: Path) -> dict:
    index = path / "corpus.json"
    if index.is_file():
        return json.loads(index.read_text(encoding="utf-8"))
    return {"voice": None, "phrases": [], "shards": [], "total": 0, "seconds": 0.0}


def write_index(path: Path, index: dict) -> None:
    index["total"] = sum(s["count"] for s in index["shards"])
    index["seconds"] = round(sum(s["seconds"] for s in index["shards"]), 1)
    tmp = path / "corpus.json.tmp"
    tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path / "corpus.json")


def append_shard(path: Path, index: dict, clips: list[np.ndarray], speaker: list[int], phrase: list[int], scales: list) -> None:
    """Write one shard of float32 clips in [-1, 1] and register it in the index."""
    path.mkdir(parents=True, exist_ok=True)
    name = f"shard-{len(index['shards']):06d}.npz"
    offsets = np.zeros(len(clips) + 1, dtype=np.int64)
    offsets[1:] = np.cumsum([len(c) for c in clips])
    audio = (np.concatenate(clips) * 32767).astype(np.int16)
    tmp = path / f"{name}.tmp"
    with open(tmp, "wb") as f:
        np.savez(f, audio=audio, offsets=offsets, speaker=np.asarray(speaker, np.int32),
                 phrase=np.asarray(phrase, np.int16), scales=np.asarray(scales, np.float32))
    os.replace(tmp, path / name)
    index["shards"].append({"name": name, "count": len(clips), "seconds": round(len(audio) / SAMPLE_RATE, 2)})
    write_index(path, index)


def shard_path(path: Path, index: dict, shard: int) -> Path:
    if not 0 <= shard < len(index["shards"]):
        raise FileNotFoundError(f"shard not found: {shard}")
    return path / index["shards"][shard]["name"]


def read_clip(path: Path, shard: int, clip: int) -> tuple[np.ndarray, dict]:
    index = load_index(path)
    with np.load(shard_path(path, index, shard)) as data:
        offsets = data["offsets"]
        if not 0 <= clip < len(offsets) - 1:
            raise FileNotFoundError(f"clip not found: {shard}/{clip}")
        audio = data["audio"][offsets[clip]:offsets[clip + 1]]
        phrase = int(data["phrase"][clip])
        meta = {
            "shard": shard,
            "clip": clip,
            "speaker": int(data["speaker"][clip]),
            "phrase": index["phrases"][phrase] if phrase < len(index["phrases"]) else None,
            "scales": [round(float(x), 2) for x in data["scales"][clip]],
            "seconds": round(len(audio) / SAMPLE_RATE, 2),
        }
    return audio, meta


def wav_bytes(audio: np.ndarray) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def random_clips(path: Path, n: int, rng: np.random.Generator) -> list[dict]:
    index = load_index(path)
    total = index.get("total", 0)
    if not total:
        return []
    counts = np.array([s["count"] for s in index["shards"]])
    picks = np.sort(rng.choice(total, size=min(n, total), replace=False))
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
    result = []
    for g in picks:
        shard = int(np.searchsorted(starts, g, side="right") - 1)
        result.append(read_clip(path, shard, int(g - starts[shard]))[1])
    return result


def reset(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
