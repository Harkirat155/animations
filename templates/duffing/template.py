"""Duffing oscillator: driven nonlinear chaotic attractor visualization.

The Duffing equation:
  ẍ + δẋ - x(1 - x²) = γ·cos(ω·t)   [twin-well variant]
  or equivalently:
  ẋ = y
  ẏ = x(1-x²) - δy + γcos(ω·t)

This is a 2D non-autonomous system (depends on time t explicitly).
The "stroboscopic" Poincaré section — sampling (x,y) every forcing period
T=2π/ω — reveals a fractal strange attractor.

The animation either:
  1. Renders the full phase-space trajectory (x vs y) as a flowing scatter-
     accumulation, morphing the forcing amplitude γ over time, OR
  2. Shows the live trajectory evolving, like a particle tracing the attractor.

Here we use the scatter-accumulation approach: N chains integrate the ODE
for a long time, accumulating (x,y) positions into the HDR buffer.
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
    "capture_every": 1,
    "warmup":    0,

    # ODE parameters
    "delta":     0.3,           # damping
    "gamma_start": 0.20,        # forcing amplitude at frame 0
    "gamma_end":   0.65,        # forcing amplitude at last frame
    "omega":     1.0,           # forcing frequency
    "dt":        0.02,          # ODE integration step

    # Ensemble
    "n_chains":  600,           # independent initial conditions
    "chain_len": 2000,          # ODE steps per chain per frame
    "burn_in":   3000,          # transient steps (not recorded)

    # Visual
    "bg_color":    [4,  2, 10],
    "palette": [
        [0.0,  [4,   2,  10]],
        [0.2,  [20,   8,  80]],
        [0.45, [80,  30, 200]],
        [0.70, [180,  80, 255]],
        [0.88, [240, 160, 255]],
        [1.0,  [255, 255, 255]],
    ],
    "gamma":        0.40,
    "density_clip": 0.998,
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs  = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for c in range(3):
        lut[:, c] = np.clip(np.interp(xs, positions, colors[:, c]), 0, 255).astype(np.uint8)
    return lut


def _collect_duffing(delta, gamma, omega, dt, n_chains, chain_len, burn_in, rng):
    """Vectorised Duffing ODE integration via Euler method."""
    # Initial conditions spread around the two wells
    x = rng.uniform(-1.5, 1.5, n_chains)
    y = rng.uniform(-1.5, 1.5, n_chains)
    t = rng.uniform(0.0, 2 * np.pi / omega, n_chains)  # random phase

    # Burn-in: settle onto attractor
    for _ in range(burn_in):
        dx = y
        dy = x * (1.0 - x * x) - delta * y + gamma * np.cos(omega * t)
        x  = x + dx * dt
        y  = y + dy * dt
        t  = t + dt

    # Record phase-space trajectory
    xs_list = np.empty((chain_len, n_chains))
    ys_list = np.empty((chain_len, n_chains))
    for i in range(chain_len):
        dx = y
        dy = x * (1.0 - x * x) - delta * y + gamma * np.cos(omega * t)
        x  = x + dx * dt
        y  = y + dy * dt
        t  = t + dt
        xs_list[i] = x
        ys_list[i] = y

    return xs_list.ravel(), ys_list.ravel()


def _render(xs, ys, size, lut, bg, gamma, density_clip):
    n = size
    margin = 0.04
    lo, hi   = xs.min(), xs.max()
    lo_y, hi_y = ys.min(), ys.max()
    span_x = hi - lo or 1.0
    span_y = hi_y - lo_y or 1.0

    px = ((xs - lo) / span_x * (1 - 2 * margin) + margin) * (n - 1)
    py = ((ys - lo_y) / span_y * (1 - 2 * margin) + margin) * (n - 1)
    pxi = px.astype(np.intp).clip(0, n - 1)
    pyi = py.astype(np.intp).clip(0, n - 1)

    density = np.zeros((n, n), dtype=np.float64)
    np.add.at(density, (pyi, pxi), 1.0)

    clip_val = (np.percentile(density[density > 0], density_clip * 100)
                if density.max() > 0 else 1.0)
    density  = np.clip(density / max(clip_val, 1e-9), 0.0, 1.0)
    density  = np.power(density, gamma)

    idx    = (density * 255).astype(np.intp).clip(0, 255)
    canvas = lut[idx].astype(np.float64) / 255.0
    alpha  = density[:, :, None]
    canvas = canvas * alpha + bg * (1 - alpha)
    return (canvas * 255.0).astype(np.uint8)


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    size = p["size"]
    lut  = _build_lut(p["palette"])
    bg   = np.array(p["bg_color"], dtype=np.float64) / 255.0
    rng  = np.random.default_rng(p["seed"])

    frame_idx = 0

    for step in range(p["steps"]):
        t = step / max(p["steps"] - 1, 1)
        gamma_val = p["gamma_start"] + t * (p["gamma_end"] - p["gamma_start"])

        xs, ys = _collect_duffing(
            p["delta"], gamma_val, p["omega"], p["dt"],
            p["n_chains"], p["chain_len"], p["burn_in"], rng
        )

        if step >= p["warmup"] and step % p["capture_every"] == 0:
            frame = _render(xs, ys, size, lut, bg, p["gamma"], p["density_clip"])
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
