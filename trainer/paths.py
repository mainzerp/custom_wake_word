"""Filesystem layout below the data root (git-ignored, bind-mounted into the container)."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("CWW_DATA", REPO_ROOT / "data")).resolve()

PROJECTS = DATA / "projects"
VOICES = DATA / "voices"
DATASETS = DATA / "datasets"
FEATURE_CACHE = DATA / "cache" / "features"
DOWNLOADS = DATA / "downloads"
SYSTEM = DATA / "system"  # jobs that belong to no project (setup), as SYSTEM/jobs/<id>/
UI_DIST = REPO_ROOT / "ui" / "dist"

# Pre-project layout, only read by `python -m trainer.projects migrate`.
LEGACY_RECORDINGS = DATA / "recordings"
LEGACY_SAMPLES = DATA / "samples"
