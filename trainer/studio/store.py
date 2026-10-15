"""Session storage for the Sample Studio.

A session is a directory below RECORDINGS holding recording.wav, clips/, clips.json and session.json.
A clip's label is derived from which sample set holds a copy of it.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
from dataclasses import asdict, fields
from datetime import datetime
from pathlib import Path

import soundfile as sf

from trainer.paths import NEGATIVE_SAMPLES, POSITIVE_SAMPLES, RECORDINGS
from trainer.studio.splitter import SplitParams, load_prefix, rename_prefix, split_recording

SESSION_RE = re.compile(r"^\d{8}-\d{6}$")
CLIP_RE = re.compile(r"^(?:[A-Za-z0-9-]{1,32}_)?\d{8}-\d{6}_\d{3}\.wav$")
TARGETS = {"positive": POSITIVE_SAMPLES, "negative": NEGATIVE_SAMPLES}
LOCK = threading.Lock()


def session_dir(name: str) -> Path:
    if not SESSION_RE.match(name or ""):
        raise ValueError(f"invalid session name: {name!r}")
    path = RECORDINGS / name
    if not (path / "recording.wav").is_file():
        raise FileNotFoundError(f"session not found: {name}")
    return path


def clip_path(session: str, name: str) -> Path:
    if not CLIP_RE.match(name or ""):
        raise ValueError("invalid clip name")
    path = session_dir(session) / "clips" / name
    if not path.is_file():
        raise FileNotFoundError(f"clip not found: {name}")
    return path


def parse_params(raw: dict | None) -> SplitParams:
    raw = raw or {}
    return SplitParams(**{f.name: float(raw[f.name]) for f in fields(SplitParams) if raw.get(f.name) is not None})


def load_meta(path: Path) -> dict:
    meta_path = path / "clips.json"
    if meta_path.is_file():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {"clips": [], "rejected": 0, "params": asdict(SplitParams())}


def write_meta(path: Path, meta: dict) -> None:
    (path / "clips.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def clip_label(name: str) -> str | None:
    return next((label for label, target in TARGETS.items() if (target / name).is_file()), None)


def place_clip(path: Path, name: str, label: str | None) -> None:
    """Copy a clip into the set for its label and remove it from the other sets."""
    for target_label, target in TARGETS.items():
        dest = target / name
        if target_label == label:
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path / "clips" / name, dest)
        else:
            dest.unlink(missing_ok=True)


def unplace_all(meta: dict) -> None:
    for clip in meta["clips"]:
        for target in TARGETS.values():
            (target / clip["name"]).unlink(missing_ok=True)


def find_clip(meta: dict, name: str) -> dict:
    if not CLIP_RE.match(name or ""):
        raise ValueError("invalid clip name")
    for clip in meta["clips"]:
        if clip["name"] == name:
            return clip
    raise FileNotFoundError(f"clip not found: {name}")


def session_info(path: Path) -> dict:
    meta = load_meta(path)
    clips_dir = path / "clips"
    meta["clips"] = [{**c, "label": clip_label(c["name"])} for c in meta["clips"] if (clips_dir / c["name"]).is_file()]
    meta["name"] = path.name
    meta["prefix"] = load_prefix(path)
    meta["duration"] = round(sf.info(path / "recording.wav").duration, 1)
    return meta


def list_sessions() -> list[dict]:
    if not RECORDINGS.is_dir():
        return []
    dirs = sorted(
        (d for d in RECORDINGS.iterdir() if SESSION_RE.match(d.name) and (d / "recording.wav").is_file()),
        reverse=True,
    )
    return [session_info(d) for d in dirs]


def sample_counts() -> dict:
    return {label: len(list(target.glob("*.wav"))) if target.is_dir() else 0 for label, target in TARGETS.items()}


def new_session(wav: bytes, params: SplitParams, prefix: str) -> dict:
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    while True:
        path = RECORDINGS / datetime.now().strftime("%Y%m%d-%H%M%S")
        try:
            path.mkdir()
            break
        except FileExistsError:
            time.sleep(1)
    (path / "recording.wav").write_bytes(wav)
    return split(path, params, prefix)


def split(path: Path, params: SplitParams, prefix: str | None = None) -> dict:
    unplace_all(load_meta(path))
    clips, rejected = split_recording(path / "recording.wav", params, prefix)
    write_meta(path, {"clips": clips, "rejected": rejected, "params": asdict(params)})
    return session_info(path)


def rename(path: Path, prefix: str) -> dict:
    meta = load_meta(path)
    mapping = rename_prefix(path, prefix)
    for clip in meta["clips"]:
        new_name = mapping.get(clip["name"], clip["name"])
        if new_name != clip["name"]:
            for target in TARGETS.values():
                old_copy = target / clip["name"]
                if old_copy.is_file():
                    old_copy.rename(old_copy.with_name(new_name))
        clip["name"] = new_name
    write_meta(path, meta)
    return session_info(path)


def label(path: Path, names: list[str], value: str | None) -> dict:
    if value is not None and value not in TARGETS:
        raise ValueError(f"invalid label: {value!r}")
    meta = load_meta(path)
    for name in names:
        find_clip(meta, name)
        place_clip(path, name, value)
    return session_info(path)


def label_unsorted(path: Path, value: str) -> dict:
    names = [c["name"] for c in session_info(path)["clips"] if not c.get("label")]
    return label(path, names, value)


def delete_clip(path: Path, name: str) -> dict:
    meta = load_meta(path)
    clip = find_clip(meta, name)
    place_clip(path, name, None)
    (path / "clips" / name).unlink(missing_ok=True)
    meta["clips"].remove(clip)
    write_meta(path, meta)
    return session_info(path)


def delete_session(path: Path) -> None:
    shutil.rmtree(path)
