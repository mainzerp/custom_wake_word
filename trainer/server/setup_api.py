"""API for the data setup page: what a machine still needs below data/, the download job, moving projects."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

from trainer import jobs, projects, setup
from trainer.paths import DATA, SYSTEM
from trainer.server.train_api import py_train

router = APIRouter(prefix="/api")
ITEM_IDS = {i.id for i in setup.items()}


class SetupBody(BaseModel):
    items: list[str] = Field(default_factory=list)  # empty: everything that is not ready
    speech_shards: int = Field(default=1, ge=1, le=len(setup.SPEECH_SHARDS))


@router.get("/setup")
def status(speech_shards: int | None = None) -> dict:
    return {**setup.status(speech_shards), "job": jobs.latest(SYSTEM, "setup"), "active": jobs.active()}


@router.get("/setup/quick")
def quick() -> dict:
    return {"ready_for": setup.quick()}


@router.post("/setup/start")
def start(body: SetupBody) -> dict:
    unknown = [i for i in body.items if i not in ITEM_IDS]
    if unknown:
        raise ValueError(f"unknown items: {', '.join(unknown)}")
    cmd = [py_train(), "-m", "trainer.setup", "run", "--speech-shards", str(body.speech_shards)]
    if body.items:
        cmd += ["--only", *body.items]
    return jobs.start(SYSTEM, "setup", cmd, body.model_dump())


@router.post("/setup/stop")
def stop() -> dict:
    job = jobs.latest(SYSTEM, "setup")
    if not job:
        raise FileNotFoundError("no setup job")
    return jobs.stop(jobs.job_dir(SYSTEM, job["id"]))


@router.get("/projects/{slug}/export")
def export(slug: str) -> FileResponse:
    """The whole project as one .zip (clips, recordings, models, mining), to import on another machine."""
    path = setup.export_project(projects.project_dir(slug).name)
    # The server copy is only the vehicle for the download.
    return FileResponse(path, media_type="application/zip", filename=path.name, background=BackgroundTask(path.unlink, missing_ok=True))


@router.post("/projects/import")
async def import_project(request: Request, slug: str | None = None) -> dict:
    """Body: a .zip made by the export (streamed to disk, projects can be gigabytes)."""
    upload = DATA / "imports" / f"upload-{os.getpid()}.zip"
    upload.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(upload, "wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
        new = await run_in_threadpool(setup.import_project, Path(upload), slug or None)
    finally:
        upload.unlink(missing_ok=True)
    return projects.load(projects.project_dir(new))
