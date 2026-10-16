"""What to do next in a project: one recommendation plus per-step notes, derived from the files alone.

The workflow is a loop, not a line: generate -> train -> mine (scan, check, review) -> train again -> mine again ...
The guide tells which part of the loop is due. Most important: a model is "stale" when the training data changed
since it was trained (new mined clips, recordings, synthetic samples), compared per source with the clip counts the
latest finished run recorded in its run.json.

Pure Python (no TF, no torch): the server calls it on every poll of the project page.
"""

from __future__ import annotations

import json
from pathlib import Path

from trainer import jobs, setup
from trainer.mining import store as mining
from trainer.train.sources import project_sources

KIND_STEP = {"generate": "generate", "confusables": "generate", "train": "train", "mining": "mining", "triage": "mining"}
KIND_LABEL = {"generate": "Synthetic samples are being generated", "confusables": "Sound-alikes are being generated",
              "train": "A model is being trained", "mining": "Real speech is being scanned for false triggers",
              "triage": "The triggers are being checked"}


def latest_run(project: Path) -> dict | None:
    root = project / "runs"
    for d in sorted(root.iterdir(), reverse=True) if root.is_dir() else []:
        try:
            run = json.loads((d / "run.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if run.get("state") == "done" and run.get("calibration") and any(d.glob("*.tflite")):
            return run
    return None


def changes(sources: list, run: dict) -> list[dict]:
    """Project sources whose clip count differs from what the run trained on (shared datasets never change)."""
    before = {s["id"]: s.get("clips", 0) for s in run.get("sources", [])}
    out = []
    for s in sources:
        if s.id.startswith("shared:"):
            continue
        was = before.get(s.id, 0)
        if s.clips != was:
            out.append({"id": s.id, "label": s.label, "before": was, "now": s.clips, "truth": s.truth})
    gone = {s.id for s in sources}
    out += [{"id": sid, "label": sid, "before": n, "now": 0, "truth": False} for sid, n in before.items()
            if sid not in gone and not sid.startswith("shared:") and n]
    return out


def describe(diff: list[dict]) -> str:
    parts = [f"{d['now'] - d['before']:+,} {d['label'].lower()}" for d in diff]
    return ", ".join(parts)


def guide(project: Path) -> dict:
    data = json.loads((project / "project.json").read_text(encoding="utf-8"))
    sources = [s for s in project_sources(project, keys=False) if not s.id.startswith("shared:")]
    positives = sum(s.clips for s in sources if s.truth)
    run = latest_run(project)
    diff = changes(sources, run) if run else []
    scans = [mining.summary(d) for d in mining.mine_dirs(project)]
    open_reviews = sum(s["counts"]["open"] for s in scans if s.get("state") != "running")
    scanned = bool(run and any(s.get("run") == run["id"] and s.get("state") == "done" for s in scans))
    active = jobs.active()
    mine = active if active and active["project"] == project.name else None
    steps: dict[str, dict] = {}

    def note(text: str, **params) -> dict:
        return {"attention": True, "note": fill(text, params), "tpl": text, "params": params}

    if run and diff:
        steps["train"] = note("train again")
    if open_reviews:
        steps["mining"] = note("{n} to check", n=open_reviews)
    elif run and not scanned and not diff:
        steps["mining"] = note("test the model")

    def nxt(step: str, title: str, text: str, action: str | None = None, **params) -> dict:
        """Texts are templates with {name} placeholders: the UI translates the template and fills in the params."""
        return {"step": step, "title": fill(title, params), "text": fill(text, params), "action": action,
                "tpl": {"title": title, "text": text}, "params": params}

    ready = setup.quick()
    if not ready["training"] or not ready["generation"]:
        missing = [k for k in ("training", "generation") if not ready[k]]
        what = {("training",): "training", ("generation",): "sample generation"}.get(tuple(missing), "training and sample generation")
        rec = nxt("setup", "Download the shared data first",
                  f"This machine is missing data for {what} (speech and noise datasets, voices, models; about 50 GB the "
                  "first time). The data page downloads and prepares everything in one go.", "Open the data page")
    elif mine:
        step = KIND_STEP.get(mine["kind"], "train")
        rec = nxt(step, KIND_LABEL.get(mine["kind"], "A job is running"),
                  "You can leave this page; progress shows in the top bar. The next step appears here when it is done.")
    elif not positives:
        rec = nxt("generate", "Generate synthetic samples",
                  "Thousands of cloned voices saying the wake word are the base of every model. Check the pronunciation "
                  "first, then generate 20,000 clips (about 1.5 hours).", "Generate samples")
    elif not run:
        rec = nxt("train", "Train your first model",
                  "{positives} wake word clips are ready. A fast run takes about 20 minutes and already gives a model to "
                  "try; take thorough (about 40 minutes) for the one to keep.", "Train a model", positives=positives)
    elif open_reviews:
        rec = nxt("mining", "Check {n} triggers",
                  "The automatic check could not decide these. Listen and label them; afterwards train again so the "
                  "model learns from them.", "Review triggers", n=open_reviews)
    elif diff:
        rec = nxt("train", "Train again: the model does not know the new data yet",
                  "Since the last model ({run}): {changes}. Clips only take effect in a new training run; then scan again "
                  "to see whether the false triggers went down.", "Train again", run=run["id"], changes=describe(diff))
    elif not scanned:
        rec = nxt("mining", "Test the model on real speech",
                  "Mining runs the newest model over hours of speech and collects what triggers it. The clear false "
                  "triggers are labeled automatically; feeding them back makes the model much more robust.",
                  "Scan for false triggers")
    else:
        last = next((s for s in scans if s.get("run") == run["id"]), None)
        faph = last.get("faph") if last else None
        tail = ("and every trigger is reviewed. Download it from the training step and try it on the device; scan more "
                "audio or record your own rooms to find more false triggers.")
        if faph is not None:
            rec = nxt("train", "The model is up to date",
                      "The newest model has been scanned ({faph} false triggers per hour of speech) " + tail,
                      "Download the model", faph=round(faph, 2))
        else:
            rec = nxt("train", "The model is up to date", "The newest model has been scanned " + tail, "Download the model")
    return {"next": rec, "steps": steps, "changes": diff, "run": run["id"] if run else None,
            "wake_word": data.get("wake_word")}


def fill(template: str, params: dict) -> str:
    return template.format(**{k: f"{v:,}" if isinstance(v, int) else v for k, v in params.items()})
