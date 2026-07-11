"""Flowfield template: particle streams along a trigonometric angle field.

The field angle at each position (x, y) at time t is:
  θ(x, y, t) = Σ_i w_i · sin(fx_i · x + fy_i · y + t_freq_i · t + phase_i)

N particles are initialized uniformly each frame, then advected for
`steps_per_particle` micro-steps. All visited positions scatter-accumulate
into an HDR buffer, producing flow-line structures — aurora, smoke, currents.

The field smoothly evolves each frame via t, morphing the topology.
Multiple competing "sink" and "spiral" regions emerge from interference.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size":              512,
    "seed":              0,
    "fps":               30,
    "steps":             240,
    "capture_every":     1,
    "warmup":            0,

    # Particle simulation
    "n_particles":       4000,       # independent particles per frame
    "steps_per_particle": 300,       # micro-steps per particle
    "step_size":         0.012,      # advection step in field space
    "field_scale":       4.0,        # canvas spans [-scale, scale] in each axis

    # Field terms: list of [fx, fy, t_freq, weight, phase]
    # angle(x,y,t) = sum w_i * sin(fx_i*x + fy_i*y + t_freq_i*t + phase_i)
    "terms": [
        [1.0, 0.5, 1.0, 1.0, 0.0],
        [0.5, 1.2, 1.7, 0.8, 1.0],
        [1.8, 0.8, 2.3, 0.5, 2.2],
    ],

    # Time: t increases by t_speed radians each frame
    "t_speed":           0.25,

    # Visual
    "bg_color":    [3,   4,  12],
    "palette": [
        [0.0,  [3,    4,  12]],
        [0.25, [10,  35,  90]],
        [0.50, [30, 100, 210]],
        [0.75, [100, 190, 255]],
        [0.92, [210, 240, 255]],
        [1.0,  [255, 255, 255]],
    ],
    "gamma":        0.38,
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


def _render(xs, ys, fs, size, lut, bg, gamma, density_clip):
    n = size
    margin = 0.03

    # Map from [-fs, fs] to canvas
    px = ((xs + fs) / (2 * fs) * (1 - 2 * margin) + margin) * (n - 1)
    py = ((ys + fs) / (2 * fs) * (1 - 2 * margin) + margin) * (n - 1)
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

    size   = p["size"]
    lut    = _build_lut(p["palette"])
    bg     = np.array(p["bg_color"], dtype=np.float64) / 255.0
    rng    = np.random.default_rng(p["seed"])
    fs     = p["field_scale"]
    n_p    = p["n_particles"]
    n_steps = p["steps_per_particle"]
    dt     = p["step_size"]
    terms  = p["terms"]
    t_speed = p["t_speed"]

    frame_idx = 0

    for step in range(p["steps"]):
        t = step * t_speed

        # Fresh particles each frame, uniformly distributed
        x = rng.uniform(-fs, fs, n_p)
        y = rng.uniform(-fs, fs, n_p)

        xs_acc = np.empty((n_steps, n_p))
        ys_acc = np.empty((n_steps, n_p))

        for i in range(n_steps):
            # Compute field angle at current positions
            angle = np.zeros(n_p)
            for term in terms:
                fx, fy, t_freq, w = term[0], term[1], term[2], term[3]
                phase = term[4] if len(term) > 4 else 0.0
                angle += w * np.sin(fx * x + fy * y + t_freq * t + phase)

            # Advect
            x = x + dt * np.cos(angle)
            y = y + dt * np.sin(angle)

            # Reinitialize out-of-bounds particles (avoid wrap seam artifacts)
            out = (x < -fs) | (x > fs) | (y < -fs) | (y > fs)
            if out.any():
                x = np.where(out, rng.uniform(-fs, fs, n_p), x)
                y = np.where(out, rng.uniform(-fs, fs, n_p), y)

            xs_acc[i] = x
            ys_acc[i] = y

        if step >= p["warmup"] and step % p["capture_every"] == 0:
            frame = _render(xs_acc.ravel(), ys_acc.ravel(),
                            fs, size, lut, bg, p["gamma"], p["density_clip"])
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
