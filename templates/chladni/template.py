"""Chladni figure template.

Chladni figures are the nodal-line patterns of standing waves on a vibrating plate.
For a square plate, the vibration mode (m,n) has the form:

  f(x,y) = cos(m·π·x) · cos(n·π·y) − cos(n·π·x) · cos(m·π·y)

(with x,y ∈ [−1, 1])

The zero-set {f = 0} traces the famous geometric mandalas that Chladni revealed
by bowing a violin while sand rested on metal plates.  Coloring by signed distance
to the nodal lines yields soft glowing curves.

Animation: mode numbers (m,n) interpolate non-integer values, continuously
morphing one mandala into the next.  The nodal lines shift, merge, and split.
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

    # Mode (m,n) at start and end — can be non-integer for smooth morphing
    "m_start": 2.0,
    "n_start": 3.0,
    "m_end":   5.0,
    "n_end":   7.0,

    # Node-line rendering
    "line_width": 0.06,     # half-width of the glowing nodal line (in field units)
    "inner_glow": True,     # if True, show faint coloring in the interior regions

    # Palette: nodal line is bright, background dark
    "bg_color": [2, 2, 10],
    "line_color": [
        [0.0,  [2,   2,  10]],
        [0.25, [20,  10,  80]],
        [0.55, [80,  40, 200]],
        [0.80, [180,100, 255]],
        [1.0,  [255, 220, 255]],
    ],
    # If inner_glow, positive-region and negative-region get a faint tint
    "pos_tint":  [30, 10, 50],   # faint purple tint for f > 0
    "neg_tint":  [10, 30, 20],   # faint teal tint for f < 0
    "tint_strength": 0.06,
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for ch in range(3):
        lut[:, ch] = np.clip(np.interp(xs, positions, colors[:, ch]), 0, 255).astype(np.uint8)
    return lut


def _render_chladni(m, n, size, line_width, inner_glow,
                    lut_line, bg, pos_tint, neg_tint, tint_strength):
    sz = size
    # Build coordinate grid x,y ∈ [−1, 1]
    lin = np.linspace(-1.0, 1.0, sz, dtype=np.float64)
    xx, yy = np.meshgrid(lin, lin)

    # Chladni field
    f = (np.cos(m * np.pi * xx) * np.cos(n * np.pi * yy)
         - np.cos(n * np.pi * xx) * np.cos(m * np.pi * yy))

    # Absolute value → proximity to zero
    af = np.abs(f)

    # Soft nodal line: brightness = 1 when f=0, falls off as |f| grows
    # Use a smooth "tent" profile
    brightness = np.clip(1.0 - af / line_width, 0.0, 1.0)
    brightness = brightness ** 0.5  # gamma lift for fuller glow

    # Map brightness → LUT color
    idx    = (brightness * 255).astype(np.intp).clip(0, 255)
    canvas = lut_line[idx].astype(np.float64) / 255.0

    # Background blend based on brightness
    alpha = brightness[:, :, None]
    canvas = canvas * alpha + bg * (1.0 - alpha)

    if inner_glow:
        pos_mask = (f > 0) & (brightness < 0.5)
        neg_mask = (f < 0) & (brightness < 0.5)
        pt = np.array(pos_tint, dtype=np.float64) / 255.0
        nt = np.array(neg_tint, dtype=np.float64) / 255.0
        canvas[pos_mask] = canvas[pos_mask] * (1 - tint_strength) + pt * tint_strength
        canvas[neg_mask] = canvas[neg_mask] * (1 - tint_strength) + nt * tint_strength

    return (np.clip(canvas, 0, 1) * 255.0).astype(np.uint8)


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    lut_line = _build_lut(p["line_color"])
    bg       = np.array(p["bg_color"], dtype=np.float64) / 255.0
    size     = p["size"]

    frame_idx = 0
    for step in range(p["steps"]):
        if step < p["warmup"] or step % p["capture_every"] != 0:
            continue

        t = step / max(p["steps"] - 1, 1)
        m = p["m_start"] + t * (p["m_end"] - p["m_start"])
        n = p["n_start"] + t * (p["n_end"] - p["n_start"])

        frame = _render_chladni(
            m, n, size,
            p["line_width"], p["inner_glow"],
            lut_line, bg,
            p["pos_tint"], p["neg_tint"], p["tint_strength"],
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
