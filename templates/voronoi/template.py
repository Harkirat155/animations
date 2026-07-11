"""Voronoi / organic cell template.

N seed points move along smooth Lissajous-like orbits. Each pixel
is coloured by its Voronoi cell (nearest seed), with the colour
derived from the seed's angle/distance to canvas centre, creating
rich iridescent mosaics. Distance-to-second-nearest-seed produces
the cell border, which is blended as a dark or bright rim.

All distances computed vectorised: (n*n, N) pairwise matrix built
once per frame with numpy broadcasting — no scipy required.
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
    "seed":    42,

    "n_seeds": 24,
    # Each seed orbits: cx + ax*sin(fx*t + px), cy + ay*cos(fy*t + py)
    # Initial positions and orbit params are derived from seed_rng.
    "orbit_amp":  0.28,   # max orbit radius as fraction of canvas half-width
    "orbit_speed": 0.018, # base angular speed (rad/frame), scrambled per seed

    # Colouring: each cell's hue = angle of seed from canvas centre,
    # lightness = dist to centre (closer = brighter).
    "palette": None,  # if set, maps cell index / seed angle through custom LUT

    # Border glow: highlight the Voronoi edges
    "border_width": 3.0,  # pixels; set to 0 to disable
    "border_bright": 2.5, # multiplier for border pixels

    # Colour cycle: shift all hues over the clip for a morphing effect
    "hue_cycle": 0.4,  # total hue rotation (turns) across full clip

    "saturation": 0.85,
    "value":      0.90,
}


def _hsv_to_rgb(h: np.ndarray, s: float, v: float) -> np.ndarray:
    """Vectorised HSV → RGB. h in [0,1], returns (N,3) float."""
    h6 = h * 6.0
    hi = h6.astype(np.intp) % 6
    f  = h6 - np.floor(h6)
    p  = v * (1.0 - s)
    q  = v * (1.0 - f * s)
    t  = v * (1.0 - (1.0 - f) * s)
    rgb = np.stack([
        np.where(hi==0,v, np.where(hi==1,q, np.where(hi==2,p, np.where(hi==3,p, np.where(hi==4,t, v))))),
        np.where(hi==0,t, np.where(hi==1,v, np.where(hi==2,v, np.where(hi==3,q, np.where(hi==4,p, p))))),
        np.where(hi==0,p, np.where(hi==1,p, np.where(hi==2,t, np.where(hi==3,v, np.where(hi==4,v, q))))),
    ], axis=-1)
    return rgb


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    n    = p["size"]
    rng  = np.random.default_rng(p["seed"])
    lut  = _build_lut(p["palette"]) if p["palette"] else None

    N  = p["n_seeds"]
    # Seed base positions (canvas-relative fraction [0,1])
    bx = rng.uniform(0.1, 0.9, N)
    by = rng.uniform(0.1, 0.9, N)
    # Per-seed orbit parameters
    amp   = p["orbit_amp"]
    a_x   = rng.uniform(0.3, 1.0, N) * amp
    a_y   = rng.uniform(0.3, 1.0, N) * amp
    f_x   = rng.uniform(0.4, 1.6, N) * p["orbit_speed"]
    f_y   = rng.uniform(0.4, 1.6, N) * p["orbit_speed"]
    ph_x  = rng.uniform(0.0, 2 * np.pi, N)
    ph_y  = rng.uniform(0.0, 2 * np.pi, N)

    # Pixel coordinate flat arrays — (n*n,)
    xs_flat, ys_flat = np.meshgrid(np.arange(n), np.arange(n))
    xs_flat = xs_flat.ravel().astype(np.float32)
    ys_flat = ys_flat.ravel().astype(np.float32)

    # Seed angle from canvas centre (stable, used for hue base)
    cx2, cy2 = n * 0.5, n * 0.5
    seed_angle = (np.arctan2(by * n - cy2, bx * n - cx2) / (2 * np.pi)) % 1.0
    seed_dist  = np.sqrt((bx - 0.5) ** 2 + (by - 0.5) ** 2) / 0.7071  # in [0,1]
    # lightness maps distance to [0.55, 1.0]
    seed_val   = 1.0 - seed_dist * 0.45

    bw2  = p["border_width"] ** 2
    frame_idx = 0

    for step in range(p["steps"]):
        t = float(step)
        hue_shift = step / max(1, p["steps"] - 1) * p["hue_cycle"]

        # Current seed positions (pixel coords) — (N,)
        sx = (bx + a_x * np.sin(f_x * t + ph_x)) * n
        sy = (by + a_y * np.cos(f_y * t + ph_y)) * n

        # Pairwise squared distances: (n*n, N)
        dx = xs_flat[:, None] - sx[None, :]   # (P, N)
        dy = ys_flat[:, None] - sy[None, :]
        d2 = dx * dx + dy * dy                 # (P, N)  float32 → fine

        # Nearest and second-nearest seed index
        idx1 = np.argmin(d2, axis=1)           # (P,)
        d1   = d2[np.arange(len(idx1)), idx1]

        # Border: distance to Voronoi edge ≈ d2 - d1 for second nearest
        d2_copy = d2.copy()
        d2_copy[np.arange(len(idx1)), idx1] = np.inf
        d_second = np.min(d2_copy, axis=1)
        edge_dist2 = d_second - d1             # 0 on edge, grows away from it

        # Cell colour: angle of seed from centre + hue cycle
        if lut is not None:
            c_idx = (((seed_angle[idx1] + hue_shift) % 1.0) * 511).astype(np.intp)
            colors = lut[c_idx]                # (P, 3)
        else:
            hues = (seed_angle[idx1] + hue_shift) % 1.0
            vals = seed_val[idx1] * p["value"]
            colors = _hsv_to_rgb(hues, p["saturation"], vals)

        # Border brightening
        if bw2 > 0:
            border_mask = edge_dist2 < bw2
            colors[border_mask] = np.clip(colors[border_mask] * p["border_bright"], 0.0, 1.0)

        canvas = colors.reshape(n, n, 3)

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
