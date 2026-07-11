"""Render spike — the smallest possible proof of the load-bearing assumption:
a SEEDED animation rendered to an mp4 + still PNG with ZERO human interaction.

If this runs unattended and is deterministic for a fixed seed, the numpy+Pillow
-> ffmpeg toolchain is a viable workhorse on this machine. Run:

    .venv/bin/python -m pipeline.spike

Engines still worth spiking later for richer visuals: Manim (math), moderngl/GLSL
(GPU shaders). Both are headless-capable but need heavier setup than this path.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.encode import frames_to_mp4, write_frame

W, H, FPS, SECONDS = 480, 480, 30, 5


def render(seed: int, frames_dir: Path) -> int:
    """Render a deterministic plasma field. Returns the frame count."""
    rng = np.random.default_rng(seed)
    # Random but seeded spatial frequencies / phases -> reproducible pattern.
    fx, fy = rng.uniform(2, 6, 2)
    phase = rng.uniform(0, 2 * np.pi)
    ys, xs = np.mgrid[0:H, 0:W].astype(float)  # pixel-index grids
    xs /= W
    ys /= H
    n_frames = FPS * SECONDS
    for i in range(n_frames):
        t = 2 * np.pi * i / n_frames
        v = (
            np.sin(fx * np.pi * xs + t + phase)
            + np.sin(fy * np.pi * ys - t)
            + np.sin(fx * np.pi * (xs + ys) + 2 * t)
        )
        v = (v - v.min()) / (np.ptp(v) + 1e-9)  # normalize 0..1
        rgb = np.empty((H, W, 3), dtype=np.uint8)
        rgb[..., 0] = (255 * np.clip(0.5 + 0.5 * np.sin(6.28 * v + 0.0), 0, 1)).astype(np.uint8)
        rgb[..., 1] = (255 * np.clip(0.5 + 0.5 * np.sin(6.28 * v + 2.09), 0, 1)).astype(np.uint8)
        rgb[..., 2] = (255 * np.clip(0.5 + 0.5 * np.sin(6.28 * v + 4.18), 0, 1)).astype(np.uint8)
        write_frame(frames_dir, i, rgb)
    return n_frames


def main() -> int:
    out_dir = Path("output/_spike")
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        frames = Path(tmp)
        n = render(seed=42, frames_dir=frames)
        mp4 = frames_to_mp4(frames, out_dir / "spike.mp4", fps=FPS)
        # Still PNG = a representative single frame (the "photo" output).
        Image.open(frames / f"frame_{n // 2:05d}.png").save(out_dir / "spike_still.png")
    print(f"OK: rendered {n} frames -> {mp4} and a still PNG in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
