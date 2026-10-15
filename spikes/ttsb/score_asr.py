"""Spike B: transcribe every clip below data/spikes/listen/<model>/ with Whisper (German) and score wake word hits.

  docker exec -e PYTHONPATH=/app -e HF_HOME=/app/data/cache/huggingface cww-trainer \
    /opt/spike/asr/bin/python spikes/ttsb/score_asr.py [model ...]

A clip counts as a hit when the transcript contains a spelling that sounds like "Jarvis" (Dscharwis, Tscharwis,
Jarwis, Charvis, ...). Writes data/spikes/ttsb/results/asr.json and prints a table.
"""

import json
import re
import sys
from pathlib import Path

import librosa
import torch
from transformers import pipeline

from spikes.ttsb.common import LISTEN, RESULTS

WAKE = re.compile(r"(dsch|dch|tsch|sch|j|ch|g|dj|dz)[aä]h?r*[wvf]+[iíeyü]+e?h?[sßz]+")


def normalize(text: str) -> str:
    return re.sub(r"[^a-zäöüß]", "", text.lower())


def koelner(text: str) -> str:
    """Kölner Phonetik code of the whole transcript (words concatenated)."""
    s = normalize(text).replace("ä", "a").replace("ö", "o").replace("ü", "u").replace("ß", "s")
    codes = []
    for i, c in enumerate(s):
        prev, nxt = (s[i - 1] if i else ""), (s[i + 1] if i + 1 < len(s) else "")
        if c in "aeijouy":
            code = "0"
        elif c == "h":
            code = ""
        elif c == "b" or (c == "p" and nxt != "h"):
            code = "1"
        elif c in "dt":
            code = "8" if nxt in "csz" else "2"
        elif c in "fvw" or (c == "p" and nxt == "h"):
            code = "3"
        elif c in "gkq":
            code = "4"
        elif c == "c":
            if i == 0:
                code = "4" if nxt in "ahkloqrux" else "8"
            else:
                code = "8" if prev in "sz" or nxt not in "ahkoqux" else "4"
        elif c == "x":
            code = "8" if prev in "ckq" else "48"
        elif c == "l":
            code = "5"
        elif c in "mn":
            code = "6"
        elif c == "r":
            code = "7"
        elif c in "sz":
            code = "8"
        else:
            code = ""
        codes.append(code)
    out = []
    for code in "".join(codes):
        if not out or out[-1] != code:
            out.append(code)
    return out[0] + "".join(c for c in out[1:] if c != "0") if out else ""


def lenient_hit(text: str) -> bool:
    """Jarvis = 0738, Dscharwis = 8738; accept a vocalized r and b/w confusion (Whisper splits unknown names)."""
    return bool(re.search(r"[08]7?[13]8", koelner(text)))


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available")
    asr = pipeline("automatic-speech-recognition", model="openai/whisper-large-v3-turbo", torch_dtype=torch.float16,
                   device="cuda:0")
    models = sys.argv[1:] or sorted(p.name for p in LISTEN.iterdir() if p.is_dir())
    out_path = RESULTS / "asr.json"
    results = json.loads(out_path.read_text(encoding="utf-8")) if out_path.is_file() else {}
    for model in models:
        files = sorted((LISTEN / model).glob("*.wav"))
        audio = [librosa.load(f, sr=16000)[0] for f in files]
        texts = asr([{"raw": a, "sampling_rate": 16000} for a in audio], batch_size=16,
                    generate_kwargs={"language": "german", "task": "transcribe"})
        rows = [{"file": f.name, "text": t["text"].strip(), "hit": bool(WAKE.search(normalize(t["text"]))),
                 "lenient": lenient_hit(t["text"])} for f, t in zip(files, texts)]
        results[model] = rows
        report(model, rows)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


def report(model: str, rows: list[dict]) -> None:
    by_kind: dict[str, list[dict]] = {}
    for r in rows:
        by_kind.setdefault(r["file"].rsplit("_", 1)[1].removesuffix(".wav"), []).append(r)
    ok = lambda r: r["hit"] or r["lenient"]  # noqa: E731
    summary = "  ".join(f"{k} {sum(ok(x) for x in v)}/{len(v)}" for k, v in sorted(by_kind.items()))
    print(f"{model:18s} strict {sum(r['hit'] for r in rows):3d}/{len(rows):<3d} combined "
          f"{sum(ok(r) for r in rows):3d}/{len(rows):<3d}  [{summary}]", flush=True)


def rescore() -> None:
    results = json.loads((RESULTS / "asr.json").read_text(encoding="utf-8"))
    for model, rows in sorted(results.items()):
        for r in rows:
            r["hit"], r["lenient"] = bool(WAKE.search(normalize(r["text"]))), lenient_hit(r["text"])
        report(model, rows)
    (RESULTS / "asr.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    rescore() if sys.argv[1:] == ["--rescore"] else main()
