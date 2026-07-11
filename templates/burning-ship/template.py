"""Burning Ship fractal template.

The Burning Ship fractal replaces the Mandelbrot iteration with:
  z_{n+1} = (|Re(z)| + i|Im(z)|)² + c

This asymmetric modification produces the iconic "burning ship" shape with
fiery masts and hull, and intricate self-similar structures along the edges.
Smooth iteration-count coloring gives a flame-like gradient appearance.

Animation: zoom smoothly into either the main hull, the mast tips, or
the intricate miniature ships visible at higher magnification.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size":      1080,
    "seed":      0,
    "fps":       30,
    "steps":     240,
    "capture_every": 1,
    "warmup":    0,

    # View window at t=0 (full fractal overview)
    # Full ship is roughly Re ∈ [-2.0, 1.0], Im ∈ [-2.0, 0.5]
    "x_min": -2.0,
    "x_max":  1.0,
    "y_min": -2.0,
    "y_max":  0.5,

    # Zoom target at t=1 (zoom into this point)
    "zoom_cx":  -1.76,   # real part of zoom center
    "zoom_cy":  -0.04,   # imag part of zoom center
    "zoom_end":  0.05,   # fraction of original range at end (0.05 = 20× zoom)

    # Iteration parameters
    "max_iter":  256,
    "escape_r":  4.0,

    # Color palette: smooth iter value ∈ [0,1] → color
    "palette": [
        [0.0,  [5,   0,   15]],
        [0.08, [30,   5,   60]],
        [0.18, [120,  20,   0]],
        [0.32, [220,  80,  10]],
        [0.50, [255, 160,  30]],
        [0.70, [255, 230, 120]],
        [0.88, [255, 255, 200]],
        [1.0,  [255, 255, 255]],
    ],

    # Inside color (bounded orbit)
    "inside_color": [0, 0, 0],
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for ch in range(3):
        lut[:, ch] = np.clip(np.interp(xs, positions, colors[:, ch]), 0, 255).astype(np.uint8)
    return lut


def _render_frame(x_min, x_max, y_min, y_max, size, max_iter, escape_r, lut, inside):
    """Render one Burning Ship frame at the given view window."""
    # Build coordinate grid
    cx = np.linspace(x_min, x_max, size, dtype=np.float64)
    cy = np.linspace(y_max, y_min, size, dtype=np.float64)  # flip y: top=positive
    CR, CI = np.meshgrid(cx, cy)
    C = CR + 1j * CI

    Z    = np.zeros_like(C)
    iter_count = np.full(C.shape, max_iter, dtype=np.float64)
    escaped    = np.zeros(C.shape, dtype=bool)

    for i in range(max_iter):
        mask = ~escaped
        if not mask.any():
            break
        # Burning Ship iteration: abs both components before squaring
        xr = np.abs(Z.real)
        xi = np.abs(Z.imag)
        Z_abs = xr + 1j * xi
        Z[mask] = Z_abs[mask] ** 2 + C[mask]

        # Escape check
        mag2 = Z.real**2 + Z.imag**2
        just_escaped = mask & (mag2 > escape_r * escape_r)
        # Smooth iteration count: i + 1 - log2(log2(|z|))
        safe_mag = np.maximum(mag2[just_escaped], 1e-12)
        smooth = (i + 1) - np.log2(np.log2(np.sqrt(safe_mag)))
        iter_count[just_escaped] = np.clip(smooth, 0, max_iter)
        escaped[just_escaped]    = True

    # Colorize
    bounded = iter_count >= max_iter
    t = np.clip(iter_count / max_iter, 0.0, 1.0)
    idx = (t * 255).astype(np.intp).clip(0, 255)
    canvas = lut[idx]
    canvas[bounded] = inside
    return canvas


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    lut    = _build_lut(p["palette"])
    inside = np.array(p["inside_color"], dtype=np.uint8)
    size   = p["size"]

    x_min0, x_max0 = p["x_min"], p["x_max"]
    y_min0, y_max0 = p["y_min"], p["y_max"]
    cx, cy = p["zoom_cx"], p["zoom_cy"]

    frame_idx = 0
    for step in range(p["steps"]):
        if step < p["warmup"] or step % p["capture_every"] != 0:
            continue

        t = step / max(p["steps"] - 1, 1)
        zoom = p["zoom_end"] ** t  # exponential zoom

        x_min = cx - (cx - x_min0) * zoom
        x_max = cx + (x_max0 - cx) * zoom
        y_min = cy - (cy - y_min0) * zoom
        y_max = cy + (y_max0 - cy) * zoom

        frame = _render_frame(x_min, x_max, y_min, y_max, size,
                              p["max_iter"], p["escape_r"], lut, inside)
        write_frame(frames_dir, frame_idx, frame)
        frame_idx += 1

    return {
        "fps":      p["fps"],
        "n_frames": frame_idx,
        "width":    size,
        "height":   size,
        "seed":     p["seed"],
        "config":   p,
    }
