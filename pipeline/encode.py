"""Shared rendering helpers: numpy frames -> PNG -> mp4 via ffmpeg.

This is the toolchain spine. Every template renders deterministic numpy frames;
this module turns them into a video. Pure CPU, no GPU/browser context required,
so it runs unattended (the load-bearing property for a daily batch cadence).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


def run_checked(cmd: list[str], text: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess and, on failure, raise with the captured stderr included.

    subprocess.run(check=True) alone reports only 'exit status N' — useless for
    debugging an unattended overnight batch. This surfaces ffmpeg's actual error.
    """
    r = subprocess.run(cmd, capture_output=True, text=text)
    if r.returncode != 0:
        err = r.stderr if text else (r.stderr or b"").decode(errors="replace")
        raise RuntimeError(f"command failed (exit {r.returncode}): {' '.join(cmd)}\n{err}")
    return r


def require_ffmpeg() -> str:
    """Return the ffmpeg binary path or raise a clear error."""
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install it (brew install ffmpeg) and retry."
        )
    return path


def require_ffprobe() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise RuntimeError("ffprobe not found on PATH (comes with ffmpeg).")
    return path


def probe_dims(video: str | Path) -> tuple[int, int]:
    """Return (width, height) of a video's first video stream."""
    out = run_checked(
        [require_ffprobe(), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(video)],
        text=True,
    ).stdout.strip()
    w, h = out.split("x")
    return int(w), int(h)


def write_frame(frames_dir: str | Path, index: int, rgb: np.ndarray) -> Path:
    """Write a single (H, W, 3) uint8 array as a zero-padded PNG frame."""
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    if rgb.dtype != np.uint8:
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    out = frames_dir / f"frame_{index:05d}.png"
    Image.fromarray(rgb, mode="RGB").save(out)
    return out


def frames_to_mp4(
    frames_dir: str | Path,
    out_path: str | Path,
    fps: int = 30,
    pattern: str = "frame_%05d.png",
) -> Path:
    """Encode a PNG frame sequence into an H.264 mp4 (yuv420p, broadly compatible)."""
    ffmpeg = require_ffmpeg()
    frames_dir = Path(frames_dir)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / pattern),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-movflags", "+faststart",
        str(out_path),
    ]
    run_checked(cmd)
    return out_path
