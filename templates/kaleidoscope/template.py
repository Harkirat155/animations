"""Kaleidoscope template.

Generates a source field (plasma sine-sum) and applies N-fold
rotational mirror symmetry.  Each wedge of 2π/N radians is filled
with the source field reflected at the wedge boundary, creating a
seamless symmetric pattern.

The source field rotates at `field_rate` rad/frame, which makes the
whole kaleidoscope morph continuously without any seams.

Algorithm:
  1. Convert each pixel to polar (r, θ).
  2. Fold θ into the canonical wedge [0, π/N) with alternating mirror.
  3. Convert back to Cartesian and look up the plasma value.
  4. Map through LUT.
"""
from __future__ import annotations

from pathlib import Path
import math

import numpy as np

from pipeline.encode import write_frame


def _build_lut(palette: list, size: int = 512) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, size)
    lut = np.empty((size, 3), dtype=np.float64)
    for ch in range(3):
        lut[:, ch] = np.interp(xs, positions, colors[:, ch])
    return np.clip(lut / 255.0, 0.0, 1.0)


DEFAULTS = {
    "size":    512,
    "fps":     30,
    "steps":   240,
    "capture_every": 1,
    "warmup":  0,

    "n_fold":  6,      # rotational symmetry order (3, 4, 6, 8, 12 all work well)

    # Source plasma parameters
    "scale1": 55.0,
    "scale2": 45.0,
    "scale3": 38.0,
    "scale4": 60.0,
    "rate1":  1.0,
    "rate2":  0.73,
    "rate3":  1.31,
    "rate4":  0.57,
    "dt":     0.06,

    # How fast the source field rotates (drives morphing)
    "field_rate": 0.018,   # radians per frame

    "palette": [
        [0.0,  [0,   0,   0]],
        [0.18, [30,   0,  80]],
        [0.35, [0,   80, 200]],
        [0.52, [0,  200, 200]],
        [0.68, [200, 240, 255]],
        [0.82, [255, 200,  60]],
        [0.92, [255,  60,   0]],
        [1.0,  [255, 255, 255]],
    ],
}


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    n    = p["size"]
    lut  = _build_lut(p["palette"])
    L    = len(lut)
    N    = int(p["n_fold"])
    wedge = math.pi / N         # half-wedge = π/N
    TWO_PI = 2.0 * math.pi

    # Output pixel coordinates in normalised [-1, 1] space
    linsp = np.linspace(-1.0, 1.0, n)
    ox, oy = np.meshgrid(linsp, linsp)
    r_out   = np.sqrt(ox * ox + oy * oy)
    # Avoid atan2(0,0) = 0 edge case — fine for our use
    theta_out = np.arctan2(oy, ox)     # [-π, π]
    theta_pos = theta_out % TWO_PI     # [0, 2π)

    # Fold into canonical wedge [0, wedge)
    sector   = (theta_pos / (2.0 * wedge)).astype(np.intp)   # which sector
    theta_in = theta_pos - sector * 2.0 * wedge              # [0, 2*wedge)
    # Mirror alternate sectors
    mirror   = (sector % 2).astype(bool)
    theta_in = np.where(mirror, 2.0 * wedge - theta_in, theta_in)
    # theta_in is now in [0, wedge) (the canonical half-wedge)

    s1, s2, s3, s4 = p["scale1"], p["scale2"], p["scale3"], p["scale4"]
    r1, r2, r3, r4 = p["rate1"],  p["rate2"],  p["rate3"],  p["rate4"]
    dt     = float(p["dt"])
    fr     = float(p["field_rate"])
    frame_idx = 0

    for step in range(p["steps"]):
        t     = step * dt
        theta_rot = step * fr    # rotate the source field

        # Source coordinates from folded polar → Cartesian
        # Add rotation to animate
        th_src = theta_in + theta_rot
        sx = r_out * np.cos(th_src) * (n * 0.5)
        sy = r_out * np.sin(th_src) * (n * 0.5)

        # Plasma field on (sx, sy)
        radial_src = np.sqrt(sx * sx + sy * sy)
        v = (np.sin(sx / s1 + t * r1)
           + np.sin(sy / s2 + t * r2)
           + np.sin((sx + sy) / s3 + t * r3)
           + np.sin(radial_src / s4 + t * r4))

        v_norm  = ((v + 4.0) / 8.0).clip(0.0, 1.0)
        idx_lut = (v_norm * (L - 1)).astype(np.intp)
        canvas  = lut[idx_lut]   # (n, n, 3)

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
