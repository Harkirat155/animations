"""Fast, cheap preview rendering for the composer UI.

Reuses the exact same template contract as pipeline.generate (`load_template`,
`generate_frames`) — this module adds nothing to that contract, it just skips
`frames_to_mp4`/ffmpeg entirely. Combined with pipeline.schema's
`preview_overrides`, a still preview renders in well under a second for every
hero template (measured; see schema.py).

Motion previews sample multiple frames for closed-form templates (or a short
growth strip for sequential ones) and package them as an animated WebP.
"""
from __future__ import annotations

import io
import tempfile
import time
from pathlib import Path

from PIL import Image

from pipeline.generate import load_template
from pipeline.schema import TEMPLATES, build_preview_params

# Templates whose each frame is independent of prior simulation state — we can
# jump along t cheaply by raising steps with capture_every=1.
_CLOSED_FORM = frozenset({
    "mandelbrot",
    "julia",
    "strange-attractor",
    "chladni",
    "harmonograph",
    "voronoi",
    "domain-coloring",
    "lyapunov",
    "kaleidoscope",
    "newton",
    "torus",
    "verhulst",
})

# Sequential physics: full multi-frame at preview fidelity is expensive.
# Keep a short strip with reduced steps so something still moves.
_SEQUENTIAL = frozenset({
    "reaction-diffusion",
    "flow-field",
})


class PreviewError(Exception):
    pass


def render_preview_still(template_name: str, params: dict) -> tuple[bytes, dict]:
    """Render one representative frame for `template_name` with `params`
    (already the user's raw, unvalidated slider values).

    Returns (png_bytes, info) where info includes render_seconds + the fully
    resolved config, for surfacing in the UI / logs.
    """
    preview_params = build_preview_params(template_name, params)
    module = load_template(template_name)

    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        info = module.generate_frames(preview_params, tmp)
        if info["n_frames"] == 0:
            raise PreviewError(
                f"{template_name} produced 0 frames for these params "
                f"(check warmup/steps interaction)"
            )
        frames = sorted(Path(tmp).glob("frame_*.png"))
        png_bytes = frames[-1].read_bytes()
    elapsed = time.perf_counter() - t0

    return png_bytes, {
        "render_seconds": round(elapsed, 3),
        "width": info["width"],
        "height": info["height"],
        "config": info["config"],
        "n_frames": 1,
        "media_type": "image/png",
    }


# Escape-time / heavy closed-form: multi-frame at full max_iter is too slow
# for live dials (mandelbrot ~1s/frame at size 320). Motion is deliberately
# lower-fidelity; still preview keeps the user's full controls.
_HEAVY_CLOSED = frozenset({
    "mandelbrot", "julia", "newton", "lyapunov", "domain-coloring", "verhulst",
})


def _motion_overrides(template_name: str, n_frames: int) -> dict:
    """Extra overrides on top of schema preview_overrides for multi-frame."""
    n = max(2, min(int(n_frames), 16))
    if template_name in _CLOSED_FORM:
        # Each step is an independent t = step/(steps-1) sample.
        if template_name in _HEAVY_CLOSED:
            n = min(n, 6)
            out: dict = {
                "steps": n,
                "warmup": 0,
                "capture_every": 1,
                "size": 160,
            }
            # Intentionally shadow user max_iter only in motion mode so a
            # 6-frame scrub stays under ~2s. Still preview respects the dial.
            if template_name in ("mandelbrot", "julia", "newton"):
                out["max_iter"] = 128
            return out
        return {
            "steps": n,
            "warmup": 0,
            "capture_every": 1,
            "size": 256,
        }
    if template_name in _SEQUENTIAL:
        # Growth strip: fewer steps than a full clip, capture evenly.
        # reaction-diffusion needs real warmup; flow-field accumulates trails.
        if template_name == "reaction-diffusion":
            steps = 1800
            capture = max(1, steps // n)
            return {"steps": steps, "capture_every": capture, "warmup": 350, "size": 160}
        # flow-field
        steps = max(n * 4, 40)
        capture = max(1, steps // n)
        return {
            "steps": steps,
            "capture_every": capture,
            "warmup": 0,
            "size": 192,
            "n_particles": 400,
        }
    # Unknown family: still-only via n=1 path
    return {"steps": 1, "warmup": 0, "capture_every": 1}


def render_preview_motion(
    template_name: str,
    params: dict,
    n_frames: int = 12,
) -> tuple[bytes, dict]:
    """Render a short multi-frame preview as animated WebP.

    Falls back to a single-frame PNG (media_type image/png) if only one frame
    is produced. Budget is intentionally looser than still (~4s) because this
    is the delight path.
    """
    if template_name not in TEMPLATES:
        raise PreviewError(f"unknown template {template_name!r}")

    base = build_preview_params(template_name, params)
    motion = _motion_overrides(template_name, n_frames)
    preview_params = {**base, **motion}

    module = load_template(template_name)
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        info = module.generate_frames(preview_params, tmp)
        frame_paths = sorted(Path(tmp).glob("frame_*.png"))
        if not frame_paths:
            raise PreviewError(
                f"{template_name} produced 0 frames for motion preview"
            )

        images = [Image.open(p).convert("RGB") for p in frame_paths]
        # Cap how many we encode if the template over-produced
        max_n = max(2, min(int(n_frames), 24))
        if len(images) > max_n:
            # Evenly sample
            idxs = [round(i * (len(images) - 1) / (max_n - 1)) for i in range(max_n)]
            images = [images[i] for i in idxs]

        if len(images) == 1:
            buf = io.BytesIO()
            images[0].save(buf, format="PNG")
            payload = buf.getvalue()
            media_type = "image/png"
            fps = 1
        else:
            buf = io.BytesIO()
            # ~8 fps feels alive without being huge; duration is ms per frame.
            fps = 8
            duration_ms = int(1000 / fps)
            images[0].save(
                buf,
                format="WEBP",
                save_all=True,
                append_images=images[1:],
                duration=duration_ms,
                loop=0,
                quality=80,
                method=0,
            )
            payload = buf.getvalue()
            media_type = "image/webp"
            for im in images:
                im.close()

    elapsed = time.perf_counter() - t0
    n_out = min(len(frame_paths), max_n)
    return payload, {
        "render_seconds": round(elapsed, 3),
        "width": info["width"],
        "height": info["height"],
        "config": info.get("config"),
        "n_frames": n_out,
        "fps": fps,
        "media_type": media_type,
        "kind": (
            "closed_form" if template_name in _CLOSED_FORM
            else "sequential" if template_name in _SEQUENTIAL
            else "still"
        ),
    }
