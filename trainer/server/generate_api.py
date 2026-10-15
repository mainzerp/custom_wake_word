"""API for the "Synthetic samples" step: OmniVoice corpus status, generation job, previews and listening."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess

import numpy as np
from fastapi import APIRouter
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, model_validator

from trainer import jobs, projects
from trainer.tts import corpus
from trainer.tts.voices import load_bank

router = APIRouter(prefix="/api/projects/{slug}/generate")
PREVIEW_TIMEOUT_S = 300
ENGINE = {"name": "OmniVoice", "model": "k2-fsa/OmniVoice", "license": "CC-BY-NC 4.0 weights"}


class Range(BaseModel):
    lo: float
    hi: float

    @model_validator(mode="after")
    def ordered(self) -> "Range":
        if self.lo > self.hi:
            raise ValueError("range minimum is larger than maximum")
        if self.lo < 0.5 or self.hi > 2.0:
            raise ValueError("speed must stay within 0.5..2.0")
        return self


class GenerateBody(BaseModel):
    count: int = Field(ge=100, le=500_000)
    speed: Range = Range(lo=0.85, hi=1.2)
    steps: int = Field(default=16, ge=8, le=64)
    design_share: float = Field(default=0.15, ge=0.0, le=1.0)
    filter: bool = True


class PreviewBody(BaseModel):
    phrase: str = Field(min_length=1, max_length=60)
    speed: Range = Range(lo=0.85, hi=1.2)
    steps: int = Field(default=16, ge=8, le=64)


def py_omni() -> str:
    exe = shutil.which("py-omni")
    if not exe:
        raise ValueError("py-omni launcher not found: generation only runs inside the container")
    return exe


def preview_key(phrase: str) -> str:
    return hashlib.sha1(phrase.encode()).hexdigest()[:12]


@router.get("")
def status(slug: str) -> dict:
    path = projects.project_dir(slug)
    project = projects.load(path)
    index = corpus.load_index(corpus.corpus_dir(path))
    return {
        "engine": {**ENGINE, "voices": len(load_bank(project["language"]))},
        "corpus": {k: index[k] for k in ("voice", "phrases", "total", "seconds")} | {"shards": len(index["shards"])},
        "job": jobs.latest(path, "generate"),
        "active": jobs.active(),
    }


@router.post("/start")
def start(slug: str, body: GenerateBody) -> dict:
    path = projects.project_dir(slug)
    cmd = [py_omni(), "-m", "trainer.tts.omni", "run", "--project", str(path), "--count", str(body.count),
           "--speed", str(body.speed.lo), str(body.speed.hi), "--steps", str(body.steps),
           "--design-share", str(body.design_share)]
    if not body.filter:
        cmd.append("--no-filter")
    return jobs.start(path, "generate", cmd, body.model_dump())


@router.post("/reset")
def reset(slug: str) -> dict:
    path = projects.project_dir(slug)
    running = jobs.active()
    if running and running["project"] == slug:
        raise ValueError("stop the running job first")
    corpus.reset(corpus.corpus_dir(path))
    return status(slug)


@router.post("/preview")
def preview(slug: str, body: PreviewBody) -> dict:
    path = projects.project_dir(slug)
    running = jobs.active()
    if running:
        raise ValueError(f"the GPU is busy with a {running['kind']} job; preview after it finished")
    key = preview_key(body.phrase)
    out = path / "generated" / "preview" / key
    shutil.rmtree(out, ignore_errors=True)
    cmd = [py_omni(), "-m", "trainer.tts.omni", "preview", "--project", str(path), "--phrase", body.phrase,
           "--out", str(out), "--speed", str(body.speed.lo), str(body.speed.hi), "--steps", str(body.steps)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=PREVIEW_TIMEOUT_S)
    if res.returncode:
        lines = [line for line in res.stderr.strip().splitlines() if line.strip()]
        raise ValueError(f"preview failed: {lines[-1] if lines else res.returncode}")
    result = json.loads(res.stdout.strip().splitlines()[-1])
    for clip in result["clips"]:
        clip["url"] = f"/api/projects/{slug}/generate/preview/{key}/{clip.pop('file')}"
    return result


@router.get("/preview/{key}/{name}")
def preview_file(slug: str, key: str, name: str) -> FileResponse:
    if not (key.isalnum() and name.removesuffix(".wav").isdigit()):
        raise ValueError("invalid preview file")
    path = projects.project_dir(slug) / "generated" / "preview" / key / name
    if not path.is_file():
        raise FileNotFoundError("preview not found")
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@router.get("/samples")
def samples(slug: str, n: int = 12) -> dict:
    path = corpus.corpus_dir(projects.project_dir(slug))
    clips = corpus.random_clips(path, max(1, min(n, 48)), np.random.default_rng())
    for c in clips:
        c["url"] = f"/api/projects/{slug}/generate/clip/{c['shard']}/{c['clip']}.wav"
    return {"clips": clips}


@router.get("/clip/{shard}/{clip}.wav")
def clip(slug: str, shard: int, clip: int) -> Response:
    audio, _ = corpus.read_clip(corpus.corpus_dir(projects.project_dir(slug)), shard, clip)
    return Response(corpus.wav_bytes(audio), media_type="audio/wav", headers={"Cache-Control": "max-age=3600"})
