"""API for the "Synthetic samples" step: Piper corpus status, generation job, previews and listening."""

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
from trainer.tts.catalog import voice_for

router = APIRouter(prefix="/api/projects/{slug}/generate")
PREVIEW_TIMEOUT_S = 180


class Range(BaseModel):
    lo: float
    hi: float

    @model_validator(mode="after")
    def ordered(self) -> "Range":
        if self.lo > self.hi:
            raise ValueError("range minimum is larger than maximum")
        return self


class GenerateBody(BaseModel):
    count: int = Field(ge=100, le=500_000)
    length_scale: Range = Range(lo=0.55, hi=1.0)
    noise_scale: Range = Range(lo=0.3, hi=0.8)
    noise_w: Range = Range(lo=0.2, hi=0.5)

    @model_validator(mode="after")
    def bounds(self) -> "GenerateBody":
        for name, lo, hi in (("length_scale", 0.3, 2.0), ("noise_scale", 0.0, 1.5), ("noise_w", 0.0, 1.5)):
            r = getattr(self, name)
            if r.lo < lo or r.hi > hi:
                raise ValueError(f"{name} must stay within {lo}..{hi}")
        return self


class PreviewBody(BaseModel):
    phrase: str = Field(min_length=1, max_length=60)
    length_scale: Range = Range(lo=0.55, hi=1.0)


def py_tts() -> str:
    exe = shutil.which("py-tts")
    if not exe:
        raise ValueError("py-tts launcher not found: generation only runs inside the container")
    return exe


def preview_key(phrase: str) -> str:
    return hashlib.sha1(phrase.encode()).hexdigest()[:12]


@router.get("")
def status(slug: str) -> dict:
    path = projects.project_dir(slug)
    project = projects.load(path)
    index = corpus.load_index(corpus.corpus_dir(path))
    return {
        "voice": voice_for(project["language"]),
        "corpus": {k: index[k] for k in ("voice", "phrases", "total", "seconds")} | {"shards": len(index["shards"])},
        "job": jobs.latest(path, "generate"),
        "active": jobs.active(),
    }


@router.post("/start")
def start(slug: str, body: GenerateBody) -> dict:
    path = projects.project_dir(slug)
    if not voice_for(projects.load(path)["language"]):
        raise ValueError("no multi-speaker voice for this language yet")
    cmd = [py_tts(), "-m", "trainer.tts.generate", "run", "--project", str(path), "--count", str(body.count)]
    for name in ("length_scale", "noise_scale", "noise_w"):
        r = getattr(body, name)
        cmd += [f"--{name.replace('_', '-')}", str(r.lo), str(r.hi)]
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
    key = preview_key(body.phrase)
    out = path / "generated" / "preview" / key
    shutil.rmtree(out, ignore_errors=True)
    cmd = [py_tts(), "-m", "trainer.tts.generate", "preview", "--project", str(path), "--phrase", body.phrase,
           "--out", str(out), "--length-scale", str(body.length_scale.lo), str(body.length_scale.hi)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=PREVIEW_TIMEOUT_S)
    if res.returncode:
        raise ValueError(f"preview failed: {res.stderr.strip().splitlines()[-1] if res.stderr.strip() else res.returncode}")
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
