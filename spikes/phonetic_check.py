"""Calibrate the IPA phone check: distance of recognized phones to the espeak-ng target of the spellings.

  docker exec -e PYTHONPATH=/app -e HF_HOME=/app/data/cache/huggingface cww-trainer py-omni spikes/phonetic_check.py

Sets: own recordings (real positives), OmniVoice corpus, Tater corpus, Piper MLS gibberish, random 1 s speech crops
from Kartoffelphon (other speech).
"""

import io
import random
from pathlib import Path

import numpy as np
import pyarrow.ipc as ipc
import soundfile as sf
from scipy.signal import resample_poly

from trainer.tts import corpus
from trainer.tts.phonetic import PhoneChecker

PHRASES = ["Jarvis", "Dscharwis"]
N = 150


def load(path: Path) -> np.ndarray:
    y, sr = sf.read(path, dtype="float32", always_2d=True)
    y = y.mean(1)
    return resample_poly(y, 16000 // np.gcd(sr, 16000), sr // np.gcd(sr, 16000)).astype(np.float32) if sr != 16000 else y


def main() -> None:
    rng = random.Random(0)
    sets: dict[str, list[np.ndarray]] = {}
    own = sorted(Path("data/projects/dscharwis/samples/positive").glob("*.wav"))
    sets["own recordings"] = [load(p) for p in own]
    d = corpus.corpus_dir(Path("data/projects/dscharwis"))
    sets["omnivoice corpus"] = [corpus.read_clip(d, 0, i)[0].astype(np.float32) / 32767 for i in range(N)]
    tater = sorted(Path("data/datasets/tater_corpus/dscharwis_de_50k").glob("*.wav"))
    sets["tater"] = [load(p) for p in rng.sample(tater, N)]
    sets["piper mls"] = [load(p) for p in sorted(Path("data/spikes/listen/piper-mls").glob("A_*.wav"))
                         + sorted(Path("data/spikes/listen/piper-mls").glob("B_*.wav"))
                         + sorted(Path("data/spikes/listen/piper-mls").glob("C_*.wav"))]
    table = ipc.open_stream("data/downloads/kartoffelphon/test-00000.arrow").read_all()
    other = []
    for i in rng.sample(range(table.num_rows), N):
        y, sr = sf.read(io.BytesIO(table.column("audio")[i].as_py()["bytes"]), dtype="float32", always_2d=True)
        y = y.mean(1)
        if len(y) > sr * 2:
            s = rng.randrange(0, len(y) - sr)
            other.append(y[s:s + int(sr * rng.uniform(0.6, 1.3))])
    sets["other speech"] = other

    checker = PhoneChecker("de", PHRASES)
    print("targets:", checker.targets)
    for name, clips in sets.items():
        res = checker.score(clips)
        dist = np.array([r.distance for r in res])
        bands = {b: sum(r.band == b for r in res) for b in ("positive", "gray", "negative")}
        print(f"{name:18s} n={len(dist):3d}  median {np.median(dist):.2f}  p10 {np.percentile(dist, 10):.2f}  "
              f"p90 {np.percentile(dist, 90):.2f}  bands {bands}")
        for r in sorted(res, key=lambda r: r.distance)[:: max(1, len(res) // 6)]:
            print(f"    {r.distance:.2f} {r.band:8s} {' '.join(r.phones)}")


if __name__ == "__main__":
    main()
