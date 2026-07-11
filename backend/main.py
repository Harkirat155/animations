"""Composer backend — browse templates, previews, free still export, waitlist.

Public preview + export stay free. Full video render remains Maker-gated
(waitlist collects demand until Stripe + worker ship).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from pipeline.preview import PreviewError, render_export_still, render_preview_motion, render_preview_still
from pipeline.schema import TEMPLATES, get, list_templates, to_json

app = FastAPI(title="Lumen Composer API")

_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
_cors_raw = os.environ.get("CORS_ORIGINS", _DEFAULT_ORIGINS)
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Render-Seconds", "X-Motion-Frames", "X-Motion-Fps"],
)

_POOL = ThreadPoolExecutor(max_workers=max(2, os.cpu_count() or 4))

_RATE_LIMIT_WINDOW_S = 60.0
_RATE_LIMIT_MAX_REQUESTS = 45
_request_log: dict[str, list[float]] = defaultdict(list)

_WAITLIST_PATH = Path(os.environ.get("WAITLIST_PATH", "/data/waitlist.jsonl"))
# Local dev fallback when /data isn't mounted
if not _WAITLIST_PATH.parent.exists():
    _WAITLIST_PATH = Path("analytics/waitlist.jsonl")


def _check_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    log = _request_log[client_ip]
    cutoff = now - _RATE_LIMIT_WINDOW_S
    while log and log[0] < cutoff:
        log.pop(0)
    if len(log) >= _RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many preview requests — slow down.")
    log.append(now)


def _client_ip(request: Request) -> str:
    return (
        request.headers.get("fly-client-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


class PreviewRequest(BaseModel):
    template: str
    params: dict[str, Any] = Field(default_factory=dict)


class MotionPreviewRequest(BaseModel):
    template: str
    params: dict[str, Any] = Field(default_factory=dict)
    n_frames: int = Field(default=12, ge=2, le=24)


class WaitlistRequest(BaseModel):
    email: str


@app.get("/api/templates")
def api_list_templates() -> list[dict]:
    return list_templates()


@app.get("/api/templates/{name}/schema")
def api_template_schema(name: str) -> dict:
    try:
        return to_json(get(name))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/api/preview")
async def api_preview(req: PreviewRequest, request: Request) -> Response:
    if req.template not in TEMPLATES:
        raise HTTPException(status_code=404, detail=f"unknown template {req.template!r}")

    _check_rate_limit(_client_ip(request))

    loop = asyncio.get_running_loop()
    try:
        png_bytes, info = await loop.run_in_executor(
            _POOL, render_preview_still, req.template, req.params
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PreviewError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"X-Render-Seconds": str(info["render_seconds"])},
    )


@app.post("/api/preview/motion")
async def api_preview_motion(req: MotionPreviewRequest, request: Request) -> Response:
    if req.template not in TEMPLATES:
        raise HTTPException(status_code=404, detail=f"unknown template {req.template!r}")

    _check_rate_limit(_client_ip(request))

    loop = asyncio.get_running_loop()
    try:
        payload, info = await loop.run_in_executor(
            _POOL,
            lambda: render_preview_motion(req.template, req.params, n_frames=req.n_frames),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PreviewError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return Response(
        content=payload,
        media_type=info.get("media_type", "image/webp"),
        headers={
            "X-Render-Seconds": str(info["render_seconds"]),
            "X-Motion-Frames": str(info.get("n_frames", 1)),
            "X-Motion-Fps": str(info.get("fps", 8)),
        },
    )


@app.post("/api/export/still")
async def api_export_still(req: PreviewRequest, request: Request) -> Response:
    """Free higher-fidelity still (no subscription) — the freemium delight."""
    if req.template not in TEMPLATES:
        raise HTTPException(status_code=404, detail=f"unknown template {req.template!r}")

    _check_rate_limit(_client_ip(request))

    loop = asyncio.get_running_loop()
    try:
        png_bytes, info = await loop.run_in_executor(
            _POOL, render_export_still, req.template, req.params
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PreviewError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "X-Render-Seconds": str(info["render_seconds"]),
            "Content-Disposition": f'attachment; filename="lumen-{req.template}.png"',
        },
    )


@app.post("/api/waitlist")
async def api_waitlist(req: WaitlistRequest, request: Request) -> dict:
    email = req.email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Invalid email")
    _check_rate_limit(_client_ip(request))

    _WAITLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "email": email,
        "ts": time.time(),
        "ip": _client_ip(request),
    }
    with _WAITLIST_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return {"ok": True, "message": "joined"}


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "product": "lumen",
        "templates": len(TEMPLATES),
        "cors_origins": _cors_origins,
    }
