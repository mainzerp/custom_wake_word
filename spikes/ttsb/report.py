"""Spike B: build data/spikes/listen/index.html (players + Whisper transcripts + speed table). Stdlib only.

  python spikes/ttsb/report.py
"""

import html
import json
from pathlib import Path

LISTEN = Path("data/spikes/listen")
RESULTS = Path("data/spikes/ttsb/results")
ORDER = ["qwen-17b", "qwen-06b", "omnivoice", "audio8", "voxcpm2", "omnivoice-design", "qwen-17b-design",
         "piper-thorsten", "tater", "piper-mls"]


def main() -> None:
    asr = json.loads((RESULTS / "asr.json").read_text(encoding="utf-8"))
    models = [m for m in ORDER if (LISTEN / m).is_dir()] + sorted(
        p.name for p in LISTEN.iterdir() if p.is_dir() and p.name not in ORDER)
    rows, sections = [], []
    for m in models:
        res_path = RESULTS / f"{m}.json"
        res = json.loads(res_path.read_text(encoding="utf-8")) if res_path.is_file() else {}
        tr = {r["file"]: r for r in asr.get(m, [])}
        ok = sum(r["hit"] or r["lenient"] for r in tr.values())
        tp = res.get("throughput", {})
        rows.append(f"<tr><td><a href='#{m}'>{m}</a></td><td>{ok}/{len(tr)}</td><td>{tp.get('clips_per_s', '–')}</td>"
                    f"<td>{tp.get('batch', '–')}</td><td>{res.get('vram_gb', '–')}</td><td>{res.get('sample_rate', '–')}</td></tr>")
        groups: dict[str, list[str]] = {}
        for f in sorted((LISTEN / m).glob("*.wav")):
            kind = f.stem.rsplit("_", 1)[1] if "_" in f.stem else "clips"
            r = tr.get(f.name, {})
            mark = "hit" if r.get("hit") or r.get("lenient") else "miss"
            groups.setdefault(kind, []).append(
                f"<div class='clip {mark}'><span>{html.escape(f.stem)}</span>"
                f"<audio controls preload='none' src='{m}/{f.name}'></audio>"
                f"<em>{html.escape(r.get('text', ''))}</em></div>")
        body = "".join(f"<h3>{html.escape(k)}</h3><div class='grid'>{''.join(v)}</div>" for k, v in groups.items())
        sections.append(f"<section id='{m}'><h2>{m}</h2>{body}</section>")
    page = f"""<!doctype html><meta charset="utf-8"><title>Spike B: German TTS</title>
<style>
body{{font-family:system-ui;background:#0a0820;color:#ece9ff;margin:24px}} a{{color:#29f0ff}}
table{{border-collapse:collapse;margin-bottom:24px}} td,th{{border:1px solid #333;padding:6px 10px;text-align:left}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px}}
.clip{{background:#14112e;border:1px solid #2a2550;border-radius:8px;padding:8px;display:flex;flex-direction:column;gap:4px}}
.clip.miss{{border-color:#ff3df2}} .clip span{{font-family:monospace;font-size:12px;color:#9d97c7}}
.clip em{{font-size:12px;color:#9d97c7}} audio{{width:100%}} section{{margin-top:32px}}
</style>
<h1>Spike B: German TTS for "Dscharwis"</h1>
<p>Whisper hit = transcript sounds like Jarvis/Dscharwis (pink border = miss). Voices ref00-04 male, ref08-12 female,
d* = voice design from a text description.</p>
<table><tr><th>model</th><th>Whisper hits</th><th>clips/s</th><th>batch</th><th>VRAM GB</th><th>Hz</th></tr>{''.join(rows)}</table>
{''.join(sections)}"""
    (LISTEN / "index.html").write_text(page, encoding="utf-8")
    print(LISTEN / "index.html")


if __name__ == "__main__":
    main()
