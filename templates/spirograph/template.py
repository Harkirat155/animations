"""Spirograph / hypotrochoid + epitrochoid template.

Renders curves traced by a point on a circle rolling inside (hypo)
or outside (epi) a fixed circle:

  Hypotrochoid:  x = (R-r)*cos(t) + d*cos((R-r)/r * t)
                 y = (R-r)*sin(t) - d*sin((R-r)/r * t)

  Epitrochoid:   x = (R+r)*cos(t) - d*cos((R+r)/r * t)
                 y = (R+r)*sin(t) - d*sin((R+r)/r * t)

Multiple arms can be drawn simultaneously with phase offsets.
Animation: `d` (pen distance) or `r` (inner radius ratio) morphs
across the clip, producing smooth shape transitions.

Rendered as scatter accumulation (like harmonograph) — regions with
many crossing strands glow brighter.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.float64)
    for ch in range(3):
        lut[:, ch] = np.interp(xs, positions, colors[:, ch])
    return np.clip(lut / 255.0, 0.0, 1.0)


DEFAULTS = {
    "size":    512,
    "fps":     30,
    "steps":   360,
    "capture_every": 1,
    "warmup":  0,
    "seed":    0,

    # Curve type: "hypo" | "epi"
    "curve_type": "hypo",

    # Outer radius R is normalised to 1.0
    # r_start / r_end: inner radius ratio (fraction of R); morphs across clip
    "r_start": 0.382,
    "r_end":   0.382,

    # d_start / d_end: pen distance ratio (fraction of R); morphs across clip
    "d_start": 0.88,
    "d_end":   0.88,

    # Number of complete parametric rotations per frame (higher → more detail)
    "n_rotations": 1,

    # Phase advance drives the animation (rotation per frame)
    "phase_advance": 0.01745,   # ≈ 2π/360

    # Arms: list of phase offsets in radians; each arm draws the same curve shifted
    "arms": [0.0],

    # Point density per frame
    "n_points": 200_000,

    # Visual
    "bg_color":   [5,  3, 18],
    "intensity":  0.005,
    "glow_boost": 3.0,
    "palette": [
        [0.0,  [255, 220,  60]],
        [0.5,  [255, 140,  10]],
        [1.0,  [255,  60,   0]],
    ],
}


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    n   = p["size"]
    bg  = np.array(p["bg_color"], dtype=np.float64) / 255.0
    lut = _build_lut(p["palette"])
    iv  = float(p["intensity"])
    gb  = float(p["glow_boost"])

    t_arr  = np.linspace(0, 2.0 * np.pi * p["n_rotations"], p["n_points"])
    t_norm = t_arr / (2.0 * np.pi * p["n_rotations"])   # [0,1] for LUT
    c_idx  = (t_norm * 255).astype(np.intp).clip(0, 255)
    base_colors = lut[c_idx]   # (N, 3)

    frame_idx = 0
    margin = int(n * 0.05)
    half   = n * 0.5 - margin

    for step in range(p["steps"]):
        t_f   = step / max(1, p["steps"] - 1)
        r     = p["r_start"] + t_f * (p["r_end"]   - p["r_start"])
        d     = p["d_start"] + t_f * (p["d_end"]   - p["d_start"])
        phase = step * p["phase_advance"]

        canvas = np.full((n, n, 3), bg, dtype=np.float64)

        for arm_phase in p["arms"]:
            tt = t_arr + arm_phase + phase

            if p["curve_type"] == "hypo":
                ratio = (1.0 - r) / r
                x = (1.0 - r) * np.cos(tt) + d * np.cos(ratio * tt)
                y = (1.0 - r) * np.sin(tt) - d * np.sin(ratio * tt)
                scale = 1.0 / (1.0 - r + d) if (1.0 - r + d) > 0 else 1.0
            else:  # epi
                ratio = (1.0 + r) / r
                x = (1.0 + r) * np.cos(tt) - d * np.cos(ratio * tt)
                y = (1.0 + r) * np.sin(tt) - d * np.sin(ratio * tt)
                scale = 1.0 / (1.0 + r + d) if (1.0 + r + d) > 0 else 1.0

            cx = (x * scale * half + n * 0.5).astype(np.intp)
            cy = (y * scale * half + n * 0.5).astype(np.intp)
            valid = (cx >= 0) & (cx < n) & (cy >= 0) & (cy < n)
            cx, cy = cx[valid], cy[valid]
            cols = base_colors[valid]

            np.add.at(canvas[:, :, 0], (cy, cx), cols[:, 0] * iv)
            np.add.at(canvas[:, :, 1], (cy, cx), cols[:, 1] * iv)
            np.add.at(canvas[:, :, 2], (cy, cx), cols[:, 2] * iv)

            if gb:
                gm = np.arange(len(cx)) % 6 == 0
                gc = cols[gm] * iv * gb
                np.add.at(canvas[:, :, 0], (cy[gm], cx[gm]), gc[:, 0])
                np.add.at(canvas[:, :, 1], (cy[gm], cx[gm]), gc[:, 1])
                np.add.at(canvas[:, :, 2], (cy[gm], cx[gm]), gc[:, 2])

        np.clip(canvas, 0.0, 1.0, out=canvas)

        if step >= p["warmup"] and step % p["capture_every"] == 0:
            write_frame(frames_dir, frame_idx, (canvas * 255.0).astype(np.uint8))
            frame_idx += 1

    return {
        "fps":      p["fps"],
        "n_frames": frame_idx,
        "width":    n,
        "height":   n,
        "seed":     p["seed"],
        "config":   p,
    }
