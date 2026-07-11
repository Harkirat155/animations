"""Composer backend — v1: browse templates, fetch schema, render previews.

Public, unauthenticated, free. Preview compute runs in a bounded thread pool
(never on the asyncio event loop) so one slow request can't stall every other
visitor's request; a simple per-IP token bucket caps abuse — no Redis needed
at this scale, this is a single-instance in-memory guard.

Full-quality render/export (subscription-gated) is a v2 concern and doesn't
exist yet — see the product plan for the phase boundary.

Run: .venv/bin/uvicorn backend.main:app --reload --port 8000
Deploy: fly deploy (see Dockerfile / fly.toml)
"""
from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from pipeline.preview import PreviewError, render_preview_motion, render_preview_still
from pipeline.schema import TEMPLATES, get, list_templates, to_json

app = FastAPI(title="Animation Composer API")

# Comma-separated origins. Dev defaults include Vite; production sets
# CORS_ORIGINS to the GitHub Pages URL via `fly secrets set`.
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

# CPU-bound numpy work must never run on the event loop, or one slow preview
# stalls every other visitor. Sized to CPU count so a small box isn't
# oversubscribed.
_POOL = ThreadPoolExecutor(max_workers=max(2, os.cpu_count() or 4))

_RATE_LIMIT_WINDOW_S = 60.0
_RATE_LIMIT_MAX_REQUESTS = 30
_request_log: dict[str, list[float]] = defaultdict(list)


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
    # Fly terminates TLS and sets Fly-Client-IP; fall back to peer.
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
    """Multi-frame preview as animated WebP (closed-form) or short growth strip.

    Always returns image/webp when possible; falls back to a single PNG if the
    template cannot produce multiple frames cheaply.
    """
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


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "templates": len(TEMPLATES),
        "cors_origins": _cors_origins,
    }
