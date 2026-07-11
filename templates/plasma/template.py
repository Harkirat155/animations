"""Plasma template: classic demoscene sine-field plasma effect.

Combines several sine waves at different spatial scales, orientations,
and time offsets to produce a continuously morphing colour field.
No particles — every pixel computed analytically, so renders are instant.

The "plasma value" at each pixel is:

  v = sin(x/s1 + t)
    + sin(y/s2 + t*r2)
    + sin((x+y)/s3 + t*r3)
    + sin(sqrt((cx-x)^2 + (cy-y)^2)/s4 + t*r4)

Mapped through a custom colour LUT (or HSV cycle) for vivid results.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, 512)
    lut = np.empty((512, 3), dtype=np.float64)
    for c in range(3):
        lut[:, c] = np.interp(xs, positions, colors[:, c])
    return np.clip(lut / 255.0, 0.0, 1.0)


DEFAULTS = {
    "size":    512,
    "fps":     30,
    "steps":   240,
    "capture_every": 1,
    "warmup":  0,

    # Spatial scales for each sine component (larger = slower spatial variation)
    "scale1": 60.0,   # horizontal wave
    "scale2": 55.0,   # vertical wave
    "scale3": 45.0,   # diagonal wave
    "scale4": 50.0,   # radial wave from centre

    # Temporal rate multipliers per component
    "rate1":  1.0,
    "rate2":  0.73,
    "rate3":  1.31,
    "rate4":  0.57,

    # Time step per frame (controls animation speed)
    "dt": 0.06,

    # LUT palette — maps plasma value [0,1] to colour.
    # Use HSV cycling (palette=None) or supply control points.
    "palette": None,

    # When palette is None: HSV hue cycling — set hue_range [0,1] fraction
    "hue_offset": 0.0,    # starting hue
    "hue_range":  1.0,    # fraction of hue wheel to span
    "saturation": 1.0,
    "value":      1.0,
}


def _hsv_lut(hue_offset: float, hue_range: float, sat: float, val: float) -> np.ndarray:
    hues = (hue_offset + np.linspace(0.0, hue_range, 512)) % 1.0
    lut = np.empty((512, 3), dtype=np.float64)
    for i, h in enumerate(hues):
        hi = int(h * 6)
        f  = h * 6 - hi
        p  = val * (1 - sat)
        q  = val * (1 - f * sat)
        t  = val * (1 - (1 - f) * sat)
        table = [(val,t,p),(q,val,p),(p,val,t),(p,q,val),(t,p,val),(val,p,q)]
        lut[i] = table[hi % 6]
    return lut * val


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    n  = p["size"]
    lut = (_build_lut(p["palette"]) if p["palette"] is not None
           else _hsv_lut(p["hue_offset"], p["hue_range"], p["saturation"], p["value"]))

    # Precompute coordinate arrays — shape (n, n)
    xs, ys = np.meshgrid(np.arange(n, dtype=np.float64),
                          np.arange(n, dtype=np.float64))
    cx, cy = n * 0.5, n * 0.5
    radial = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)

    s1, s2, s3, s4 = p["scale1"], p["scale2"], p["scale3"], p["scale4"]
    r1, r2, r3, r4 = p["rate1"],  p["rate2"],  p["rate3"],  p["rate4"]
    dt = p["dt"]

    frame_idx = 0

    for step in range(p["steps"]):
        t = step * dt

        v = (np.sin(xs / s1 + t * r1)
           + np.sin(ys / s2 + t * r2)
           + np.sin((xs + ys) / s3 + t * r3)
           + np.sin(radial / s4 + t * r4))

        # Normalise from [-4, 4] to [0, 1]
        v_norm = ((v + 4.0) / 8.0).clip(0.0, 1.0)
        lut_idx = (v_norm * 511).astype(np.intp)
        canvas  = lut[lut_idx]   # (n, n, 3)

        if step >= p["warmup"] and step % p["capture_every"] == 0:
            write_frame(frames_dir, frame_idx, (canvas * 255.0).astype(np.uint8))
            frame_idx += 1

    return {
        "fps":      p["fps"],
        "n_frames": frame_idx,
        "width":    n,
        "height":   n,
        "seed":     0,
        "config":   p,
    }
