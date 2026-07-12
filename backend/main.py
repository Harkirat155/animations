"""Composer backend — browse templates, previews, free still export, waitlist.

Public preview + export stay free. Maker waitlist is the demand gate until
Stripe + full render land. Waitlist signups persist to Cloudflare R2 when
configured, else local JSONL for dev.
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

from backend import r2
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
_WAITLIST_RATE_MAX = 8  # tighter — form spam
_request_log: dict[str, list[float]] = defaultdict(list)
_waitlist_log: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str, log: dict[str, list[float]], max_req: int) -> None:
    now = time.monotonic()
    bucket = log[client_ip]
    cutoff = now - _RATE_LIMIT_WINDOW_S
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= max_req:
        raise HTTPException(status_code=429, detail="Too many requests — slow down.")
    bucket.append(now)


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
    name: str | None = None
    source: str | None = "composer"


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

    _check_rate_limit(_client_ip(request), _request_log, _RATE_LIMIT_MAX_REQUESTS)

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

    _check_rate_limit(_client_ip(request), _request_log, _RATE_LIMIT_MAX_REQUESTS)

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

    _check_rate_limit(_client_ip(request), _request_log, _RATE_LIMIT_MAX_REQUESTS)

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
    """Register interest for Maker (full video). Durable on R2 when secrets set."""
    ip = _client_ip(request)
    _check_rate_limit(ip, _waitlist_log, _WAITLIST_RATE_MAX)

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: r2.register_waitlist(
                req.email,
                ip=ip,
                source=req.source,
                name=req.name,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except r2.R2NotConfigured:
        # Should not happen — register_waitlist falls back to local — but be loud.
        raise HTTPException(
            status_code=503,
            detail="Waitlist storage is not configured",
        ) from None
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Waitlist storage failed: {e}") from e

    return result


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "product": "lumen",
        "templates": len(TEMPLATES),
        "cors_origins": _cors_origins,
        "r2_configured": r2.configured(),
        "r2_bucket": os.environ.get("R2_BUCKET", "animations"),
    }
