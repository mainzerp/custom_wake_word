"""Filesystem layout below the data root (git-ignored, bind-mounted into the container)."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("CWW_DATA", REPO_ROOT / "data")).resolve()

RECORDINGS = DATA / "recordings"
SAMPLES = DATA / "samples"
POSITIVE_SAMPLES = SAMPLES / "positive"
NEGATIVE_SAMPLES = SAMPLES / "negative"
UI_DIST = REPO_ROOT / "ui" / "dist"
