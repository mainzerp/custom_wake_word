"""Spike B: pick German reference voices for voice-cloning TTS from a Kartoffelphon shard.

  docker exec -e PYTHONPATH=/app cww-trainer py-train spikes/ttsb/refs.py --count 16

One clip per (podcast, episode, speaker), 5-10 s, high DNSMOS, balanced by median F0 (rough gender proxy).
Writes data/spikes/ttsb/refs/<id>.wav (24 kHz mono) and refs.json.
"""

import argparse
import io
import json
from pathlib import Path

import librosa
import numpy as np
import pyarrow.ipc as ipc
import soundfile as sf

SHARD = Path("data/downloads/kartoffelphon/test-00000.arrow")
OUT = Path("data/spikes/ttsb/refs")
RATE = 24000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=16)
    args = ap.parse_args()

    table = ipc.open_stream(SHARD).read_all()
    rows = table.select(["text", "start", "end", "speaker", "dnsmos", "podcast_name", "episode_name"]).to_pylist()
    seen, picks = set(), []
    order = sorted(range(len(rows)), key=lambda i: -rows[i]["dnsmos"])
    for i in order:
        r = rows[i]
        dur = r["end"] - r["start"]
        show = r["podcast_name"] if r["podcast_name"] != "librivox" else r["episode_name"].split("_")[0]
        key = (show, r["speaker"])
        words = set(r["text"].lower().replace(",", " ").replace(".", " ").split())
        english = len(words & {"the", "and", "was", "of", "that", "to", "i", "it", "my", "when", "if"}) >= 2
        if english or not 5.0 <= dur <= 10.0 or r["dnsmos"] < 3.3 or len(words) < 8 or key in seen or show in {k[0] for k in seen}:
            continue
        seen.add(key)
        picks.append(i)
        if len(picks) >= args.count * 4:
            break

    audio_col = table.column("audio")
    cands = []
    for i in picks:
        raw = audio_col[i].as_py()["bytes"]
        y, sr = librosa.load(io.BytesIO(raw), sr=RATE, mono=True)
        f0, voiced, _ = librosa.pyin(y, fmin=60, fmax=400, sr=RATE, frame_length=2048)
        med = float(np.nanmedian(f0[voiced])) if voiced.any() else float("nan")
        cands.append((i, y, med))

    male = [c for c in cands if c[2] < 160]
    female = [c for c in cands if c[2] >= 160]
    half = args.count // 2
    chosen = male[:half] + female[: args.count - min(half, len(male))]
    chosen = chosen[: args.count]

    OUT.mkdir(parents=True, exist_ok=True)
    meta = []
    for n, (i, y, med) in enumerate(chosen):
        r = rows[i]
        rid = f"ref{n:02d}"
        y = y / max(1e-6, np.abs(y).max()) * 0.9
        sf.write(OUT / f"{rid}.wav", y, RATE, subtype="PCM_16")
        meta.append({"id": rid, "text": r["text"].strip(), "seconds": round(len(y) / RATE, 2), "f0": round(med, 1),
                     "gender": "m" if med < 160 else "f", "source": r["podcast_name"], "episode": r["episode_name"],
                     "dnsmos": round(r["dnsmos"], 2)})
    (OUT.parent / "refs.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    for m in meta:
        print(m["id"], m["gender"], m["f0"], m["seconds"], m["source"][:40], "|", m["text"][:70])


if __name__ == "__main__":
    main()
