"""FastAPI app: Sample Studio API plus the built Svelte UI.

  py-train -m uvicorn trainer.server.app:app --host 0.0.0.0 --port 8790
"""

from __future__ import annotations

import json
from typing import Literal
from urllib.parse import unquote

import soundfile as sf
from fastapi import APIRouter, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from trainer.paths import UI_DIST
from trainer.studio import store

MAX_UPLOAD_BYTES = 500 * 1024 * 1024

app = FastAPI(title="custom_wake_word")
studio = APIRouter(prefix="/api/studio")


@app.exception_handler(ValueError)
@app.exception_handler(sf.LibsndfileError)
async def bad_request(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=400)


@app.exception_handler(FileNotFoundError)
async def not_found(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=404)


class SessionRef(BaseModel):
    session: str


class SplitBody(SessionRef):
    params: dict | None = None


class RenameBody(SessionRef):
    prefix: str = ""


class LabelBody(SessionRef):
    clips: list[str]
    label: Literal["positive", "negative"] | None


class LabelUnsortedBody(SessionRef):
    label: Literal["positive", "negative"]


class ClipBody(SessionRef):
    clip: str


def with_counts(session: dict) -> dict:
    return {"session": session, "counts": store.sample_counts()}


@studio.get("/sessions")
def sessions() -> dict:
    return {"sessions": store.list_sessions(), "counts": store.sample_counts()}


@studio.post("/upload")
async def upload(request: Request, x_split_params: str = Header("{}"), x_prefix: str = Header("")) -> dict:
    body = await request.body()
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "upload too large")
    params = store.parse_params(json.loads(x_split_params or "{}"))
    with store.LOCK:
        return with_counts(store.new_session(body, params, unquote(x_prefix)))


@studio.post("/split")
def split(body: SplitBody) -> dict:
    with store.LOCK:
        return with_counts(store.split(store.session_dir(body.session), store.parse_params(body.params)))


@studio.post("/rename")
def rename(body: RenameBody) -> dict:
    with store.LOCK:
        return with_counts(store.rename(store.session_dir(body.session), body.prefix))


@studio.post("/label")
def label(body: LabelBody) -> dict:
    with store.LOCK:
        return with_counts(store.label(store.session_dir(body.session), body.clips, body.label))


@studio.post("/label_unsorted")
def label_unsorted(body: LabelUnsortedBody) -> dict:
    with store.LOCK:
        return with_counts(store.label_unsorted(store.session_dir(body.session), body.label))


@studio.post("/delete_clip")
def delete_clip(body: ClipBody) -> dict:
    with store.LOCK:
        return with_counts(store.delete_clip(store.session_dir(body.session), body.clip))


@studio.post("/delete_session")
def delete_session(body: SessionRef) -> dict:
    with store.LOCK:
        store.delete_session(store.session_dir(body.session))
    return {"ok": True, "counts": store.sample_counts()}


@studio.get("/files/{session}/recording.wav")
def recording(session: str) -> FileResponse:
    return FileResponse(store.session_dir(session) / "recording.wav", media_type="audio/wav")


@studio.get("/files/{session}/clips/{name}")
def clip(session: str, name: str) -> FileResponse:
    return FileResponse(store.clip_path(session, name), media_type="audio/wav")


app.include_router(studio)

if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
