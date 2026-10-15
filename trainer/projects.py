"""Wake word projects: one directory per wake word below PROJECTS.

  <slug>/project.json   settings (wake word, language, TTS spellings, manifest author/website)
  <slug>/recordings/    Sample Studio takes
  <slug>/samples/       sorted real clips (positive/, negative/)
  <slug>/generated/     synthetic positives (TTS corpus shards, previews)
  <slug>/jobs/          pipeline job state and logs
  <slug>/runs/          training runs
  <slug>/models/        exported models

Shared datasets (negatives, RIRs, background noise) stay global below DATA/datasets.

  python -m trainer.projects migrate --wake-word Dscharwis --language de
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from trainer.paths import LEGACY_RECORDINGS, LEGACY_SAMPLES, PROJECTS
from trainer.studio.splitter import sanitize_prefix
from trainer.tts import corpus

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
LANGUAGE_RE = re.compile(r"^[a-z]{2}$")
SETTINGS = ("wake_word", "language", "tts_phrases", "author", "website")


def slugify(text: str) -> str:
    slug = sanitize_prefix(text).lower()
    if not slug:
        raise ValueError("wake word needs at least one letter or digit")
    return slug


def project_dir(slug: str) -> Path:
    if not SLUG_RE.match(slug or ""):
        raise ValueError(f"invalid project: {slug!r}")
    path = PROJECTS / slug
    if not (path / "project.json").is_file():
        raise FileNotFoundError(f"project not found: {slug}")
    return path


def clean_settings(raw: dict) -> dict:
    settings = {k: raw[k] for k in SETTINGS if raw.get(k) is not None}
    if "wake_word" in settings:
        settings["wake_word"] = settings["wake_word"].strip()
        if not settings["wake_word"]:
            raise ValueError("wake word must not be empty")
    if "language" in settings and not LANGUAGE_RE.match(settings["language"]):
        raise ValueError(f"invalid language code: {settings['language']!r}")
    if "tts_phrases" in settings:
        settings["tts_phrases"] = list(dict.fromkeys(p.strip() for p in settings["tts_phrases"] if p.strip()))
    for key in ("author", "website"):
        if key in settings:
            settings[key] = settings[key].strip()
    return settings


def count_files(path: Path, pattern: str = "*.wav") -> int:
    return sum(1 for _ in path.glob(pattern)) if path.is_dir() else 0


def count_dirs(path: Path) -> int:
    return sum(1 for d in path.iterdir() if d.is_dir()) if path.is_dir() else 0


def summary(path: Path) -> dict:
    return {
        "positive": count_files(path / "samples" / "positive"),
        "negative": count_files(path / "samples" / "negative"),
        "sessions": count_dirs(path / "recordings"),
        "generated": corpus.load_index(corpus.corpus_dir(path))["total"],
        "runs": count_dirs(path / "runs"),
        "models": count_files(path / "models", "*.tflite"),
    }


def load(path: Path) -> dict:
    data = json.loads((path / "project.json").read_text(encoding="utf-8"))
    return {**data, "slug": path.name, "summary": summary(path)}


def write(path: Path, data: dict) -> None:
    data = {k: v for k, v in data.items() if k not in ("slug", "summary")}
    (path / "project.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def list_projects() -> list[dict]:
    if not PROJECTS.is_dir():
        return []
    projects = [load(d) for d in PROJECTS.iterdir() if (d / "project.json").is_file()]
    return sorted(projects, key=lambda p: p.get("updated", ""), reverse=True)


def create(raw: dict) -> dict:
    settings = clean_settings(raw)
    if "wake_word" not in settings:
        raise ValueError("wake word is required")
    base = slugify(settings["wake_word"])
    PROJECTS.mkdir(parents=True, exist_ok=True)
    for i in range(1, 100):
        path = PROJECTS / (base if i == 1 else f"{base[:36]}-{i}")
        try:
            path.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise ValueError(f"too many projects named {base!r}")
    now = datetime.now().isoformat(timespec="seconds")
    data = {"language": "de", "author": "", "website": "", **settings, "created": now, "updated": now}
    data.setdefault("tts_phrases", [data["wake_word"]])
    write(path, data)
    return load(path)


def update(slug: str, raw: dict) -> dict:
    path = project_dir(slug)
    data = load(path)
    data.update(clean_settings(raw))
    data["updated"] = datetime.now().isoformat(timespec="seconds")
    write(path, data)
    return load(path)


def touch(path: Path) -> None:
    data = load(path)
    data["updated"] = datetime.now().isoformat(timespec="seconds")
    write(path, data)


def migrate_legacy(wake_word: str, language: str) -> dict:
    """Move the pre-project recordings/ and samples/ into a new project."""
    if not LEGACY_RECORDINGS.is_dir() and not LEGACY_SAMPLES.is_dir():
        raise FileNotFoundError("nothing to migrate")
    project = create({"wake_word": wake_word, "language": language})
    path = PROJECTS / project["slug"]
    for src, dest in ((LEGACY_RECORDINGS, path / "recordings"), (LEGACY_SAMPLES, path / "samples")):
        if src.is_dir():
            shutil.move(src, dest)
    return load(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    migrate = sub.add_parser("migrate", help="move data/recordings and data/samples into a new project")
    migrate.add_argument("--wake-word", required=True)
    migrate.add_argument("--language", default="de")
    sub.add_parser("list")
    args = parser.parse_args()
    if args.command == "migrate":
        print(json.dumps(migrate_legacy(args.wake_word, args.language), indent=2, ensure_ascii=False))
    else:
        for p in list_projects():
            print(f"{p['slug']:24} {p['wake_word']:24} {p['language']}  {p['summary']}")


if __name__ == "__main__":
    main()
