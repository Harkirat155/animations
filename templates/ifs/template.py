"""IFS (Iterated Function System) fractal template.

The "chaos game": a point is repeatedly mapped by one of N affine transforms
chosen at random with prescribed probabilities, tracing out a fractal attractor.
Classic presets include the Barnsley fern, Sierpinski triangle, Koch snowflake
approximation, and countless organic/crystalline forms.

Each transform: [prob, a, b, c, d, e, f]
  x_new = a*x + b*y + e
  y_new = c*x + d*y + f

Animation: each transform's (a,b,c,d,e,f) can interpolate between two sets
of values across the clip, morphing the fractal continuously.  Set
`transforms_start` = `transforms_end` for a static fractal (colour only).

Rendering: same HDR scatter-accumulation + LUT approach as strange-attractor.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size":      512,
    "seed":      0,
    "fps":       30,
    "steps":     240,

    "n_chains":  1000,
    "chain_len": 600,
    "burn_in":   50,

    # Barnsley Fern (static — transforms_end = transforms_start)
    # Each entry: [prob, a, b, c, d, e, f]
    "transforms_start": [
        [0.01,  0.00,  0.00,  0.00,  0.16,  0.00,  0.00],
        [0.85,  0.85,  0.04, -0.04,  0.85,  0.00,  1.60],
        [0.07,  0.20, -0.26,  0.23,  0.22,  0.00,  1.60],
        [0.07, -0.15,  0.28,  0.26,  0.24,  0.00,  0.44],
    ],
    "transforms_end": None,   # None → same as transforms_start

    "bg_color": [2, 6, 2],
    "palette": [
        [0.0,  [2,   8,   2]],
        [0.2,  [0,  50,  10]],
        [0.5,  [10, 140,  30]],
        [0.75, [80, 210,  80]],
        [0.9,  [180, 250, 160]],
        [1.0,  [255, 255, 255]],
    ],
    "gamma":        0.38,
    "density_clip": 0.995,
    "margin":       0.06,
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs  = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for c in range(3):
        lut[:, c] = np.clip(np.interp(xs, positions, colors[:, c]), 0, 255).astype(np.uint8)
    return lut


def _lerp_transforms(ts, te, t):
    """Interpolate between two transform lists."""
    if te is None or ts == te:
        return ts
    result = []
    for s, e in zip(ts, te):
        prob = s[0] + t * (e[0] - s[0])
        params = [s[i] + t * (e[i] - s[i]) for i in range(1, 7)]
        result.append([prob] + params)
    return result


def _run_chaos_game(transforms, n_chains, chain_len, burn_in, rng):
    """Vectorised chaos game.

    Returns (xs, ys) arrays of collected points.
    """
    probs = np.array([t[0] for t in transforms], dtype=np.float64)
    probs /= probs.sum()
    cum_probs = np.cumsum(probs)

    x = rng.uniform(-0.5, 0.5, n_chains)
    y = rng.uniform(-0.5, 0.5, n_chains)

    # Extract transform matrices
    mats = []  # [(a,b,c,d,e,f), ...]
    for t in transforms:
        mats.append((t[1], t[2], t[3], t[4], t[5], t[6]))

    def apply_transforms(x, y, choices):
        x_new = np.empty_like(x)
        y_new = np.empty_like(y)
        prev = -1.0
        for k, (a, b, c, d, e, f) in enumerate(mats):
            lo = cum_probs[k - 1] if k > 0 else 0.0
            hi = cum_probs[k]
            mask = (choices > lo) & (choices <= hi)
            if mask.any():
                x_new[mask] = a * x[mask] + b * y[mask] + e
                y_new[mask] = c * x[mask] + d * y[mask] + f
        return x_new, y_new

    # Burn-in
    for _ in range(burn_in):
        choices = rng.random(n_chains)
        x, y = apply_transforms(x, y, choices)

    # Collect
    xs_out = np.empty((chain_len, n_chains))
    ys_out = np.empty((chain_len, n_chains))
    for i in range(chain_len):
        choices = rng.random(n_chains)
        x, y = apply_transforms(x, y, choices)
        xs_out[i] = x
        ys_out[i] = y

    return xs_out.ravel(), ys_out.ravel()


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    p      = {**DEFAULTS, **params}

    ts = p["transforms_start"]
    te = p["transforms_end"]
    n  = p["size"]
    lut  = _build_lut(p["palette"])
    bg   = np.array(p["bg_color"], dtype=np.float64) / 255.0
    margin = p["margin"]
    rng  = np.random.default_rng(p["seed"])

    # Compute global bounding box from start transforms (for stable viewport)
    xs0, ys0 = _run_chaos_game(ts, 500, 300, p["burn_in"], rng)
    lo_x, hi_x = xs0.min(), xs0.max()
    lo_y, hi_y = ys0.min(), ys0.max()
    span_x = max(hi_x - lo_x, 1e-6)
    span_y = max(hi_y - lo_y, 1e-6)
    # Add margin
    lo_x -= margin * span_x; hi_x += margin * span_x
    lo_y -= margin * span_y; hi_y += margin * span_y
    span_x = hi_x - lo_x; span_y = hi_y - lo_y
    # Square viewport (keep aspect ratio)
    mid_x = (lo_x + hi_x) / 2; mid_y = (lo_y + hi_y) / 2
    half = max(span_x, span_y) / 2
    lo_x = mid_x - half; hi_x = mid_x + half
    lo_y = mid_y - half; hi_y = mid_y + half

    for frame_idx in range(p["steps"]):
        t = frame_idx / max(p["steps"] - 1, 1)
        tf = _lerp_transforms(ts, te, t)

        xs, ys = _run_chaos_game(tf, p["n_chains"], p["chain_len"],
                                  p["burn_in"], rng)

        # Map to canvas
        px = ((xs - lo_x) / (hi_x - lo_x) * (n - 1)).astype(np.float64)
        py = ((ys - lo_y) / (hi_y - lo_y) * (n - 1)).astype(np.float64)
        # Flip y (IFS coords have y increasing upward)
        py = (n - 1) - py

        pxi = px.astype(np.intp).clip(0, n - 1)
        pyi = py.astype(np.intp).clip(0, n - 1)

        density = np.zeros((n, n), dtype=np.float64)
        np.add.at(density, (pyi, pxi), 1.0)

        # Tonemap
        nonzero = density[density > 0]
        clip_val = np.percentile(nonzero, p["density_clip"] * 100) if nonzero.size > 0 else 1.0
        d = np.clip(density / max(clip_val, 1e-9), 0.0, 1.0)
        d = np.power(d, p["gamma"])

        idx    = (d * 255).astype(np.intp).clip(0, 255)
        canvas = lut[idx].astype(np.float64) / 255.0
        alpha  = d[:, :, None]
        canvas = canvas * alpha + bg[None, None, :] * (1.0 - alpha)
        write_frame(frames_dir, frame_idx, (canvas * 255.0).astype(np.uint8))

    return {
        "fps":      p["fps"],
        "n_frames": p["steps"],
        "width":    n,
        "height":   n,
        "seed":     p["seed"],
        "config":   p,
    }
