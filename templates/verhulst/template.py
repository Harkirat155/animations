"""Verhulst logistic-map bifurcation diagram template.

The logistic map x_{n+1} = r·x_n·(1−x_n) exhibits:
  r < 3.0    → stable fixed point
  r ≈ 3.0    → period-2 bifurcation (Hopf-like)
  r ≈ 3.449  → period-4
  r ≈ 3.544  → period-8
  …          → period-doubling cascade
  r ≈ 3.570  → onset of chaos
  r ∈ [3.83] → period-3 window (chaotic bands narrow)
  r > 3.99   → fully chaotic

Animation: the view window ZOOMS into the intricate self-similar bifurcation
structure, revealing copies of the original diagram at every scale. Coloring is
by orbit-density accumulation using a log-normalized HDR tonemap.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size":    512,
    "seed":    0,
    "fps":     30,
    "steps":   240,
    "capture_every": 1,
    "warmup":  0,

    # View: r in [r_min, r_max], x in [x_min, x_max]
    "r_min":  2.8,
    "r_max":  4.0,
    "x_min":  0.0,
    "x_max":  1.0,

    # Zoom target (end of clip)
    "zoom_end": 1.0,    # ratio: 1.0 = no zoom, 0.1 = 10x zoom
    "zoom_cr":  3.745,  # zoom center r
    "zoom_cx":  0.38,   # zoom center x

    # Iteration counts
    "warmup_iters": 300,   # discard transient
    "n_iters":      400,   # iters plotted per r column
    "n_r":          2048,  # horizontal resolution (r columns)

    # Palette: density → color (dark → bright)
    "bg_color":  [3, 2, 8],
    "palette": [
        [0.0,  [3,   2,   8]],
        [0.15, [20,  10,  60]],
        [0.35, [80,  20, 180]],
        [0.58, [180, 60, 255]],
        [0.80, [240, 150, 255]],
        [1.0,  [255, 240, 255]],
    ],
    "gamma":        0.35,
    "density_clip": 0.998,
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for ch in range(3):
        lut[:, ch] = np.clip(np.interp(xs, positions, colors[:, ch]), 0, 255).astype(np.uint8)
    return lut


def _render_bifurcation(r_min, r_max, x_min, x_max, size, n_r,
                        warmup_iters, n_iters,
                        lut, bg, gamma, density_clip):
    n = size
    density = np.zeros((n, n), dtype=np.float64)

    r_vals = np.linspace(r_min, r_max, n_r, dtype=np.float64)

    # Run each r column in vectorized batches
    x = np.full(n_r, 0.5, dtype=np.float64)

    # Warmup
    for _ in range(warmup_iters):
        x = r_vals * x * (1.0 - x)
        x = np.clip(x, 0.0, 1.0)

    # Accumulate
    x_span = x_max - x_min or 1.0
    r_span = r_max - r_min or 1.0

    # Map r_vals → pixel column
    px_r = ((r_vals - r_min) / r_span * (n - 1)).astype(np.intp).clip(0, n - 1)

    for _ in range(n_iters):
        x = r_vals * x * (1.0 - x)
        x = np.clip(x, 0.0, 1.0)
        # Map x values → pixel row (y axis, origin at bottom → flip)
        px_x = ((x - x_min) / x_span * (n - 1)).astype(np.intp).clip(0, n - 1)
        # Flip y: row 0 = top, x=1 should appear at top
        px_x_flipped = (n - 1) - px_x
        np.add.at(density, (px_x_flipped, px_r), 1.0)

    # Tonemap
    pos = density > 0
    clip_val = np.percentile(density[pos], density_clip * 100) if pos.any() else 1.0
    d = np.clip(density / max(clip_val, 1e-9), 0.0, 1.0)
    d = np.power(d, gamma)

    idx = (d * 255).astype(np.intp).clip(0, 255)
    canvas = lut[idx].astype(np.float64) / 255.0
    alpha = d[:, :, None]
    canvas = canvas * alpha + bg * (1.0 - alpha)
    return (canvas * 255.0).astype(np.uint8)


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    lut = _build_lut(p["palette"])
    bg  = np.array(p["bg_color"], dtype=np.float64) / 255.0
    size = p["size"]

    frame_idx = 0
    for step in range(p["steps"]):
        if step < p["warmup"] or step % p["capture_every"] != 0:
            continue

        t = step / max(p["steps"] - 1, 1)

        # zoom_end < 1 → zoom in (full at t=0, zoomed at t=1 → still is zoomed in)
        # zoom_end > 1 → zoom out (start tight, end at full view → still is full diagram)
        if p["zoom_end"] >= 1.0:
            zoom = p["zoom_end"] ** (1.0 - t)
        else:
            zoom = p["zoom_end"] ** t
        cr, cx = p["zoom_cr"], p["zoom_cx"]

        r_min = cr - (cr - p["r_min"]) * zoom
        r_max = cr + (p["r_max"] - cr) * zoom
        x_min = cx - (cx - p["x_min"]) * zoom
        x_max = cx + (p["x_max"] - cx) * zoom
        x_min = max(x_min, 0.0)
        x_max = min(x_max, 1.0)

        frame = _render_bifurcation(
            r_min, r_max, x_min, x_max, size, p["n_r"],
            p["warmup_iters"], p["n_iters"],
            lut, bg, p["gamma"], p["density_clip"],
        )
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
