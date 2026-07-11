"""Flow-field template: Perlin-noise particle trails.

Thousands of particles flow along a smooth vector field derived from multi-octave
gradient noise.  The accumulated trails produce long-exposure-style imagery — the
"satisfying ambient" aesthetic.

Each frame is a snapshot of the growing trail canvas.  `fade_alpha` < 1.0 lets old
trails dissolve so motion stays visible; 1.0 freezes all history.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size": 512,
    "seed": 42,
    "n_particles": 3000,
    "steps": 450,           # frames rendered (30fps → 15s clip)
    "capture_every": 1,
    "fps": 30,
    "noise_scale": 80.0,    # spatial scale of the base noise octave (pixels)
    "noise_octaves": 3,
    "step_size": 1.8,       # pixels per step per particle
    "trail_alpha": 0.012,   # intensity deposited per particle per step
    "fade_alpha": 0.998,    # per-step canvas fade (< 1 → trails dissolve)
    "restart_prob": 0.004,  # probability a dead/oob particle is respawned per step
    "bg_color": [6, 6, 16],
    "palette": [
        [0.0,  [20,  20,  200]],
        [0.33, [140,  0,  220]],
        [0.66, [220,  0,  160]],
        [1.0,  [0,  220,  255]],
    ],
    "warmup": 0,
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.float64)
    for c in range(3):
        lut[:, c] = np.interp(xs, positions, colors[:, c])
    return lut / 255.0  # [0,1] float LUT


def _make_flow_field(H: int, W: int, p: dict) -> np.ndarray:
    """Smooth 2-D angle field via summed noise octaves (no scipy dependency).

    Bilinear interpolation with smoothstep on each octave's coarse random grid,
    summed with halving amplitude.  Returns an (H, W) array of angles in [0, 2π].
    """
    rng = np.random.default_rng(p["seed"])
    result = np.zeros((H, W), dtype=np.float64)
    scale = float(p["noise_scale"])
    amp = 1.0
    total = 0.0
    for _ in range(int(p["noise_octaves"])):
        gH = max(2, int(H / scale) + 2)
        gW = max(2, int(W / scale) + 2)
        grid = rng.uniform(0.0, 2 * np.pi, (gH, gW))

        yi = np.linspace(0, gH - 1, H)
        xi = np.linspace(0, gW - 1, W)
        Y, X = np.meshgrid(yi, xi, indexing="ij")

        y0 = np.floor(Y).astype(np.intp).clip(0, gH - 2)
        x0 = np.floor(X).astype(np.intp).clip(0, gW - 2)
        sy = Y - y0
        sx = X - x0
        # Smoothstep: t² (3 - 2t) — removes first-order discontinuities at cell edges
        sy = sy * sy * (3.0 - 2.0 * sy)
        sx = sx * sx * (3.0 - 2.0 * sx)

        v00 = grid[y0,     x0    ]
        v01 = grid[y0,     x0 + 1]
        v10 = grid[y0 + 1, x0    ]
        v11 = grid[y0 + 1, x0 + 1]

        result += (v00 * (1 - sx) * (1 - sy) + v01 * sx * (1 - sy) +
                   v10 * (1 - sx) * sy        + v11 * sx * sy) * amp
        total += amp
        scale /= 2.0
        amp   *= 0.5

    return result / total  # renormalize to [0, 2π]


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}
    n = p["size"]
    rng = np.random.default_rng(p["seed"] + 1000)  # separate rng for particles

    flow = _make_flow_field(n, n, p)
    lut  = _build_lut(p["palette"])
    bg   = np.array(p["bg_color"], dtype=np.float64) / 255.0

    # Float accumulation canvas (HDR-style, tonemapped on output)
    canvas = np.full((n, n, 3), bg, dtype=np.float64)

    # Particle state
    px  = rng.uniform(0, n, p["n_particles"])
    py  = rng.uniform(0, n, p["n_particles"])
    age = rng.uniform(0, 1, p["n_particles"])  # drives color along palette

    fade = float(p["fade_alpha"])
    alpha = float(p["trail_alpha"])
    step_size = float(p["step_size"])
    restart_prob = float(p["restart_prob"])

    frame_idx = 0
    for step in range(p["steps"]):
        # --- Move particles ---
        xi_i = np.clip(px.astype(np.intp), 0, n - 1)
        yi_i = np.clip(py.astype(np.intp), 0, n - 1)
        angles = flow[yi_i, xi_i]

        px += np.cos(angles) * step_size
        py += np.sin(angles) * step_size

        # Respawn particles that wander off-canvas
        oob = (px < 0) | (px >= n) | (py < 0) | (py >= n)
        random_restart = rng.random(p["n_particles"]) < restart_prob
        respawn = oob | random_restart
        if respawn.any():
            px[respawn]  = rng.uniform(0, n, respawn.sum())
            py[respawn]  = rng.uniform(0, n, respawn.sum())
            age[respawn] = rng.uniform(0, 1, respawn.sum())

        age = (age + 0.003) % 1.0

        # --- Deposit trails ---
        xi_i = np.clip(px.astype(np.intp), 0, n - 1)
        yi_i = np.clip(py.astype(np.intp), 0, n - 1)
        color_idx = (age * 255.0).astype(np.intp).clip(0, 255)
        colors = lut[color_idx] * alpha  # (N, 3) float

        np.add.at(canvas[:, :, 0], (yi_i, xi_i), colors[:, 0])
        np.add.at(canvas[:, :, 1], (yi_i, xi_i), colors[:, 1])
        np.add.at(canvas[:, :, 2], (yi_i, xi_i), colors[:, 2])

        # --- Fade & tonemap ---
        canvas *= fade
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
