"""The audio a mining run can scan, as 16 kHz float32 blocks.

  kartoffelphon   data/downloads/kartoffelphon/*.arrow: German podcasts + LibriVox (CC-BY 4.0), one row per utterance
                  (~10 s, MP3 at 24 kHz) with its transcript. Offered for German projects only.
  folder:<name>   any folder below data/datasets/mining/ with .wav/.flac/.mp3/.ogg files (TV, radio, own rooms);
                  long files are read in blocks.

A task is a slice of one source that one worker process scans as one continuous stream: 64 Arrow rows (the
utterances back to back with a short pause, like a radio programme) or one file (read in blocks).
Pure Python (pyarrow, soundfile, scipy): the server lists sources, the worker reads them.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache
from math import gcd
from pathlib import Path
from typing import Iterator

import numpy as np
import soundfile as sf

from trainer.paths import DATA, DATASETS

SAMPLE_RATE = 16000
KARTOFFELPHON = DATA / "downloads" / "kartoffelphon"
FOLDERS = DATASETS / "mining"
AUDIO_EXT = {".wav", ".flac", ".mp3", ".ogg"}
ROWS_PER_TASK = 64
BLOCK_S = 600
GAP_S = 0.3  # pause between two utterances of a stream


@dataclass
class Task:
    source: str
    path: str
    rows: tuple[int, int] | None = None  # Arrow row range, None for a file
    seconds: float = 0.0


@dataclass
class Segment:
    start: float  # seconds into the block
    ref: str  # utterance id or file path, shown in the review
    offset: float  # seconds of ref at `start`
    text: str | None = None


@dataclass
class Block:
    audio: np.ndarray  # 16 kHz float32 mono
    segments: list[Segment]

    def at(self, t: float) -> tuple[Segment, float]:
        """The segment playing at t seconds into the block, and the position within its ref."""
        seg = next((s for s in reversed(self.segments) if s.start <= t), self.segments[0])
        return seg, seg.offset + t - seg.start


def to_16k(audio: np.ndarray, sr: int) -> np.ndarray:
    audio = audio.mean(axis=1) if audio.ndim == 2 else audio
    if sr != SAMPLE_RATE:
        from scipy.signal import resample_poly

        g = gcd(sr, SAMPLE_RATE)
        audio = resample_poly(audio, SAMPLE_RATE // g, sr // g)
    return audio.astype(np.float32, copy=False)


def arrow_files() -> list[Path]:
    return sorted(KARTOFFELPHON.glob("*.arrow")) if KARTOFFELPHON.is_dir() else []


@lru_cache(maxsize=16)
def _arrow_table(path: str, mtime_ns: int):
    import pyarrow as pa
    import pyarrow.ipc as ipc

    return ipc.open_stream(pa.memory_map(path)).read_all()  # zero-copy view of the mapped file


def arrow_table(path: Path):
    return _arrow_table(str(path), path.stat().st_mtime_ns)


@lru_cache(maxsize=16)
def _arrow_seconds(path: str, mtime_ns: int) -> tuple[int, float]:
    t = _arrow_table(path, mtime_ns).select(["start", "end"])
    return t.num_rows, float((t.column("end").to_numpy() - t.column("start").to_numpy()).sum())


def folder_files(name: str) -> list[Path]:
    root = FOLDERS / name
    return sorted(f for f in root.rglob("*") if f.suffix.lower() in AUDIO_EXT and f.is_file()) if root.is_dir() else []


@lru_cache(maxsize=4096)
def _file_seconds(path: str, size: int, mtime_ns: int) -> float:
    try:
        return float(sf.info(path).duration)
    except (sf.LibsndfileError, RuntimeError):
        return 0.0


def file_seconds(path: Path) -> float:
    st = path.stat()
    return _file_seconds(str(path), st.st_size, st.st_mtime_ns)


def sources(language: str) -> list[dict]:
    """What can be mined for a project: id, label, hours, files, note."""
    out = []
    shards = arrow_files()
    if shards and language == "de":
        rows, secs = 0, 0.0
        for f in shards:
            r, s = _arrow_seconds(str(f), f.stat().st_mtime_ns)
            rows, secs = rows + r, secs + s + r * GAP_S
        out.append({"id": "kartoffelphon", "label": "Kartoffelphon (German podcasts + LibriVox)", "hours": round(secs / 3600, 2),
                    "files": rows, "note": "with transcripts; also the source of the voice bank"})
    if FOLDERS.is_dir():
        for d in sorted(p for p in FOLDERS.iterdir() if p.is_dir()):
            files = folder_files(d.name)
            if files:
                out.append({"id": f"folder:{d.name}", "label": d.name, "hours": round(sum(map(file_seconds, files)) / 3600, 2),
                            "files": len(files), "note": f"datasets/mining/{d.name}"})
    return out


def tasks(source: str) -> list[Task]:
    if source == "kartoffelphon":
        out = []
        for f in arrow_files():
            t = arrow_table(f).select(["start", "end"])
            secs = t.column("end").to_numpy() - t.column("start").to_numpy() + GAP_S
            out += [Task(source, str(f), (a, min(a + ROWS_PER_TASK, t.num_rows)), float(secs[a:a + ROWS_PER_TASK].sum()))
                    for a in range(0, t.num_rows, ROWS_PER_TASK)]
        return out
    if source.startswith("folder:"):
        return [Task(source, str(f), None, file_seconds(f)) for f in folder_files(source.split(":", 1)[1])]
    raise ValueError(f"unknown mining source: {source!r}")


def blocks(task: Task) -> Iterator[Block]:
    if task.rows is not None:
        t = arrow_table(Path(task.path))
        a, b = task.rows
        rows = t.slice(a, b - a).select(["audio", "text", "episode_name"]).to_pylist()
        parts, segments, pos = [], [], 0
        gap = np.zeros(int(GAP_S * SAMPLE_RATE), dtype=np.float32)
        for i, row in enumerate(rows, a):
            audio, sr = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32", always_2d=True)
            audio = to_16k(audio, sr)
            segments.append(Segment(pos / SAMPLE_RATE, f"{Path(task.path).stem}#{i} {row['episode_name']}", 0.0,
                                    (row["text"] or "").strip()))
            parts += [audio, gap]
            pos += len(audio) + len(gap)
        yield Block(np.concatenate(parts), segments)
        return
    ref = str(Path(task.path).relative_to(DATA)) if Path(task.path).is_relative_to(DATA) else task.path
    with sf.SoundFile(task.path) as f:
        sr, offset = f.samplerate, 0.0
        for chunk in f.blocks(blocksize=BLOCK_S * sr, dtype="float32", always_2d=True):
            yield Block(to_16k(chunk, sr), [Segment(0.0, ref, offset)])
            offset += len(chunk) / sr
