"""Spike B shared helpers (numpy + soundfile only, importable from every model venv via PYTHONPATH=/app).

Each runner writes data/spikes/listen/<model>/<ref>_<text>.wav and data/spikes/ttsb/results/<model>.json.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path("data/spikes/ttsb")
REFS = ROOT / "refs"
RESULTS = ROOT / "results"
LISTEN = Path("data/spikes/listen")

# Round 1: 5 male + 5 female reference voices.
REF_IDS = ["ref00", "ref01", "ref02", "ref03", "ref04", "ref08", "ref09", "ref10", "ref11", "ref12"]
TEXTS = {
    "dscharwis": "Dscharwis.",
    "jarvis": "Jarvis.",
    "satz": "Jarvis, mach bitte das Licht an.",
}
# Voice design prompts for models that support it (no reference audio).
DESIGNS = [
    "a young German woman, bright and friendly voice",
    "an elderly German man, deep and slightly hoarse voice",
    "a German teenage boy, fast and casual",
    "a middle-aged German woman, calm and low voice",
    "a German man in his thirties, energetic and loud",
    "a German girl, high pitched and cheerful",
]
THROUGHPUT_N = 64


def refs() -> list[dict]:
    meta = {r["id"]: r for r in json.loads((ROOT / "refs.json").read_text(encoding="utf-8"))}
    return [{**meta[i], "path": str(REFS / f"{i}.wav")} for i in REF_IDS]


def out_dir(model: str) -> Path:
    d = LISTEN / model
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.wav"):
        f.unlink()
    return d


def save(d: Path, name: str, audio, rate: int) -> float:
    audio = np.asarray(audio, dtype=np.float32).squeeze()
    peak = float(np.abs(audio).max()) if audio.size else 0.0
    if peak > 0:
        audio = audio / peak * 0.9
    sf.write(d / f"{name}.wav", audio, rate, subtype="PCM_16")
    return round(len(audio) / rate, 2)


class Timer:
    def __enter__(self):
        self.t = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.s = time.perf_counter() - self.t


def write_result(model: str, data: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{model}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tp = data.get("throughput", {})
    print(f"{model}: load {data.get('load_s')}s, {len(data.get('clips', []))} clips, "
          f"throughput {tp.get('clips_per_s')} clips/s (batch {tp.get('batch')}), vram {data.get('vram_gb')} GB")
