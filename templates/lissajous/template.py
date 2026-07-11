"""Lissajous-figure template.

Parametric curves x(t)=sin(fx·t + δ), y(t)=sin(fy·t), where
frequency ratio fx:fy and phase offset δ define the figure.
As δ sweeps 0→2π the shape continuously morphs, revealing all members
of that frequency family — figure-eights become pretzel knots become
multi-loop flowers and back again.

Multiple curves can be layered, each with its own frequency pair and
phase trajectory, creating interference patterns.

Rendering: dense parametric scatter into an HDR accumulation buffer.
Turning-point density naturally produces luminous hotspots at loop
intersections — no extra processing needed.
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
    "n_points": 800_000,   # samples per curve per frame

    # List of curves: [freq_x, freq_y, amplitude, phase_start, phase_end]
    # amplitude in [0, 1] — fraction of half-canvas
    # phase_start/end in radians (δ sweeps from → to over the clip)
    "curves": [
        [3, 2, 0.92, 0.0, 6.2832],
    ],

    "intensity":    1.0,       # density weight per point
    "glow_radius":  2,         # post-accumulation blur radius for glowing lines (0=off)
    "gamma":        0.40,
    "density_clip": 0.997,
    "bg_color": [2, 2, 6],

    "palette": [
        [0.0,  [2,    2,   6]],
        [0.12, [10,  20,  80]],
        [0.28, [0,   80, 200]],
        [0.48, [0,  180, 240]],
        [0.68, [80, 230, 255]],
        [0.84, [200, 245, 255]],
        [1.0,  [255, 255, 255]],
    ],
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs  = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for c in range(3):
        lut[:, c] = np.clip(np.interp(xs, positions, colors[:, c]), 0, 255).astype(np.uint8)
    return lut


def _glow(density: np.ndarray, radius: int) -> np.ndarray:
    """Fast separable glow: sum of shifted copies with distance-weighted falloff."""
    if radius <= 0:
        return density
    result = density.copy()
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr == 0 and dc == 0:
                continue
            dist = (dr * dr + dc * dc) ** 0.5
            w = np.exp(-dist * dist / (radius * radius)) * 0.35
            result += w * np.roll(np.roll(density, dr, axis=0), dc, axis=1)
    return result


def _render_frame(curves_data, n, n_points, intensity, glow_radius, lut, bg, gamma, density_clip):
    density = np.zeros((n, n), dtype=np.float64)
    margin = 0.05

    # Pre-allocate t once
    t_arr = np.linspace(0.0, 2.0 * np.pi, n_points, endpoint=False)

    for (fx, fy, amp, phase) in curves_data:
        x = amp * np.sin(fx * t_arr + phase)   # [-amp, amp]
        y = amp * np.sin(fy * t_arr)            # [-amp, amp]

        # Map to pixel coords with margin
        scale = (1.0 - 2.0 * margin) / (2.0 * amp) * (n - 1)
        offset = margin * (n - 1)
        px = (x + amp) * scale + offset
        py = (y + amp) * scale + offset

        pxi = px.astype(np.intp).clip(0, n - 1)
        pyi = py.astype(np.intp).clip(0, n - 1)
        np.add.at(density, (pyi, pxi), intensity)

    # Glow pass
    density = _glow(density, glow_radius)

    # Tonemap
    nonzero = density[density > 0]
    if nonzero.size > 0:
        clip_val = np.percentile(nonzero, density_clip * 100)
    else:
        clip_val = 1.0
    d = np.clip(density / max(clip_val, 1e-9), 0.0, 1.0)
    d = np.power(d, gamma)

    idx    = (d * 255).astype(np.intp).clip(0, 255)
    canvas = lut[idx].astype(np.float64) / 255.0
    alpha  = d[:, :, None]
    canvas = canvas * alpha + bg[None, None, :] * (1.0 - alpha)
    return (canvas * 255.0).astype(np.uint8)


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    p      = {**DEFAULTS, **params}

    n            = p["size"]
    lut          = _build_lut(p["palette"])
    bg           = np.array(p["bg_color"], dtype=np.float64) / 255.0
    curves_spec  = p["curves"]
    n_points     = p["n_points"]
    intensity    = p["intensity"]

    for frame_idx in range(p["steps"]):
        t = frame_idx / max(p["steps"] - 1, 1)

        # Interpolate phase for each curve
        curves_data = []
        for spec in curves_spec:
            fx, fy, amp, ps, pe = spec[:5]
            phase = ps + t * (pe - ps)
            curves_data.append((fx, fy, amp, phase))

        frame = _render_frame(
            curves_data, n, n_points, intensity, p["glow_radius"],
            lut, bg, p["gamma"], p["density_clip"],
        )
        write_frame(frames_dir, frame_idx, frame)

    return {
        "fps":      p["fps"],
        "n_frames": p["steps"],
        "width":    n,
        "height":   n,
        "seed":     p["seed"],
        "config":   p,
    }
