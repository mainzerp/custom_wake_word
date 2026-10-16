"""Pick the on-device operating point (probability cutoff + sliding window) of a streaming model.

Streams the quantized TFLite model over held-out data, like ESPHome does on the device:

  positives   the testing split of every positive source (synthetic, own recordings): recall
  ambient     datasets/negative_datasets/dinner_party_eval/testing_ambient (hours of real rooms): false accepts/hour
  word sets   the testing split of word-like negatives (sound-alikes, own negatives, borrowed): trigger rate

Selection (as in the old trainer's calibrate_detector.py): the strictest false-accept tier that has candidates
(target, then 2x, then 4x), within it the candidates within `recall_margin` of the best recall, and of those the one
with the fewest false accepts.

  py-train -m trainer.train.calibrate --model run/model.tflite --project data/projects/dscharwis
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Callable

import numpy as np

from trainer.paths import DATASETS
from trainer.train.sources import Source

WINDOWS = [3, 4, 5, 6, 7, 8]
# The int8 model's output has 1/256 steps, so above 0.99 only a few distinct cutoffs exist; scan those finer.
CUTOFFS = np.round(np.r_[np.arange(0.50, 0.99, 0.01), np.arange(0.990, 0.9985, 0.002)], 3)
COOLDOWN = 25  # slices after an accept (stride 2 x 10 ms = 0.5 s)
POSITIVE_SKIP = 25  # streaming state warm-up at the start of a positive clip
STEP_S = 0.01
AMBIENT = DATASETS / "negative_datasets" / "dinner_party_eval" / "testing_ambient"
PREFERRED_WINDOW = 5


def moving_average(x: np.ndarray, w: int) -> np.ndarray:
    if x.size < w:
        return np.asarray([x.mean()]) if x.size else x
    c = np.cumsum(np.insert(x.astype(np.float64), 0, 0.0))
    return (c[w:] - c[:-w]) / w


def false_accepts(track: np.ndarray, cutoffs: np.ndarray) -> np.ndarray:
    """Accepts per cutoff with a cooldown after each accept (vectorized over cutoffs)."""
    count = np.zeros(len(cutoffs))
    cooldown = np.zeros(len(cutoffs), dtype=np.int32)
    above = track[:, None] > cutoffs[None, :]
    for row in above:
        cooldown = np.maximum(cooldown - 1, 0)
        hit = row & (cooldown == 0)
        count += hit
        cooldown[hit] = COOLDOWN
    return count


def load_split(dirs: list[Path], split: str) -> list[np.ndarray]:
    from mmap_ninja.ragged import RaggedMmap

    out = []
    for d in dirs:
        for m in sorted((d / split).glob("*_mmap")):
            out.extend(np.asarray(x) for x in RaggedMmap(str(m)))
    return out


def select(candidates: list[dict], target: float, margin: float) -> dict:
    limits = [target, max(target * 2, target + 0.5), max(target * 4, 2.0)]

    def tier(c: dict) -> int:
        return next((i for i, lim in enumerate(limits) if c["faph"] <= lim + 1e-9), len(limits))

    best_tier = min(tier(c) for c in candidates)
    pool = [c for c in candidates if tier(c) == best_tier]
    floor = max(c["recall"] for c in pool) - margin
    pool = [c for c in pool if c["recall"] >= floor - 1e-12]
    return min(pool, key=lambda c: (c["faph"], -c["recall"], abs(c["window"] - PREFERRED_WINDOW), -c["cutoff"]))


def calibrate(model_path: Path, sources: list[Source], target_faph: float = 0.25, margin: float = 0.005,
              stride: int = 2, log: Callable[[str], None] = print) -> dict:
    from microwakeword.inference import Model

    model = Model(str(model_path), stride=stride)
    t0 = time.perf_counter()

    def predict(tracks: list[np.ndarray]) -> list[np.ndarray]:
        return [np.asarray(model.predict_spectrogram(t), dtype=np.float32) for t in tracks]

    groups = []  # (source, predictions)
    for s in sources:
        if s.id.startswith("shared:") or not s.items:
            continue
        tracks = load_split([i.cache for i in s.items], "testing")
        if tracks:
            groups.append((s, predict(tracks)))
    ambient = predict(load_split([AMBIENT.parent], AMBIENT.name))
    hours = sum(len(p) for p in ambient) * stride * STEP_S / 3600
    log(f"calibration: {sum(len(p) for _, p in groups)} clips, {hours:.1f} h ambient, "
        f"inference {time.perf_counter() - t0:.0f}s")

    def maxima(preds: list[np.ndarray], w: int, skip: int) -> np.ndarray:
        return np.asarray([moving_average(p[skip:] if p.size > skip else p, w).max(initial=0.0) for p in preds])

    candidates, curves, per_source = [], {}, {}
    for w in WINDOWS:
        fa = sum(false_accepts(moving_average(p, w), CUTOFFS) for p in ambient)
        faph = fa / hours if hours else np.full(len(CUTOFFS), np.inf)
        pos = np.concatenate([maxima(p, w, POSITIVE_SKIP) for s, p in groups if s.truth] or [np.zeros(0)])
        recall = (pos[None, :] > CUTOFFS[:, None]).mean(axis=1) if pos.size else np.zeros(len(CUTOFFS))
        per_source[w] = {s.id: (maxima(p, w, POSITIVE_SKIP if s.truth else 0)[None, :] > CUTOFFS[:, None]).mean(axis=1)
                         for s, p in groups}
        curves[w] = [{"cutoff": float(c), "recall": round(float(r), 4), "faph": round(float(f), 3)}
                     for c, r, f in zip(CUTOFFS, recall, faph)]
        candidates += [{"cutoff": float(c), "window": w, "recall": float(r), "faph": float(f)}
                       for c, r, f in zip(CUTOFFS, recall, faph)]
    best = select(candidates, target_faph, margin)
    i = int(np.argmin(np.abs(CUTOFFS - best["cutoff"])))
    w = best["window"]
    result = {
        "probability_cutoff": best["cutoff"],
        "sliding_window_size": w,
        "recall": round(best["recall"], 4),
        "false_accepts_per_hour": round(best["faph"], 3),
        "target_false_accepts_per_hour": target_faph,
        "met_target": best["faph"] <= target_faph + 1e-9,
        "ambient_hours": round(hours, 2),
        "sources": [{"id": s.id, "label": s.label, "truth": s.truth, "clips": len(p),
                     ("recall" if s.truth else "trigger_rate"): round(float(per_source[w][s.id][i]), 4)}
                    for s, p in groups],
        "curve": curves[w],
        "seconds": round(time.perf_counter() - t0, 1),
    }
    log(f"selected cutoff {result['probability_cutoff']:.3f}, window {w}: recall {result['recall']:.1%}, "
        f"{result['false_accepts_per_hour']:.2f} false accepts/h")
    return result


def main() -> None:
    from trainer.train.sources import project_sources

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--target-faph", type=float, default=0.25)
    args = ap.parse_args()
    result = calibrate(args.model, project_sources(args.project), args.target_faph)
    result.pop("curve")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
