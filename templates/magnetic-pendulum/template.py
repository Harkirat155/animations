"""Magnetic pendulum fractal basin template.

A pendulum swings above 3 magnets arranged at the vertices of an equilateral triangle.
Each starting position (x₀, y₀) eventually settles to one of the 3 magnets.
The basin boundary between the three settling regions is an infinitely complex fractal.

ODE (simplified planar model, height h above magnet plane):
  ẍ = −δẋ − κx + Σᵢ (mᵢ_x − x) / rᵢ³
  ÿ = −δẏ − κy + Σᵢ (mᵢ_y − y) / rᵢ³
  rᵢ = sqrt((x − mᵢ_x)² + (y − mᵢ_y)² + h²)

All pixels are integrated simultaneously using vectorized NumPy — feasible at 512×512
because force evaluation per step is O(N²) numpy operations.

Color: final settled magnet (0,1,2) → color from 3-color palette.
Brightness: number of steps to settle → lower step count = brighter (settled fast).

Animation: h decreases over time → magnets become stronger → basin boundaries become
increasingly intricate and fractal near the boundaries.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size":       256,   # keep low for speed — 256 still looks gorgeous
    "seed":       0,
    "fps":        30,
    "steps":      240,
    "capture_every": 1,
    "warmup":     0,

    # Pendulum height above magnet plane: animates from h_start → h_end
    # Smaller h = stronger magnets = more fractal structure
    "h_start":    0.8,
    "h_end":      0.3,

    # Physical params
    "delta":      0.3,   # damping
    "kappa":      0.05,  # restoring force (spring to origin)
    "mag_dist":   1.0,   # distance of magnets from origin
    "mag_strength": 1.0, # magnetic force multiplier

    # Integration
    "dt":         0.02,
    "max_steps":  2000,  # max integration steps per pixel
    "settle_tol": 0.02,  # settled if |v| < this and pendulum near a magnet

    # View: canvas covers [−view, view]² in pendulum coordinates
    "view":       2.5,

    # Colors for the 3 magnets and unsettled
    "color_0":   [255, 80,  60],   # magnet 0 — warm red
    "color_1":   [80, 200, 255],   # magnet 1 — cool blue
    "color_2":   [100, 255, 130],  # magnet 2 — green
    "color_bg":  [10,   8,  20],   # unsettled / background

    # Brightness: step_count→brightness curve
    "brightness_gamma": 0.4,  # brightness = (steps/max_steps)^gamma; lower = log-like
}


def _integrate_pendulum(x0, y0, h, delta, kappa, mag_dist, mag_strength,
                        dt, max_steps, settle_tol):
    """Vectorized: x0, y0 are 2D arrays (size×size)."""
    shape = x0.shape
    x = x0.copy(); y = y0.copy()
    vx = np.zeros_like(x); vy = np.zeros_like(y)

    # Magnet positions at vertices of equilateral triangle
    angles = np.array([np.pi/2, np.pi/2 + 2*np.pi/3, np.pi/2 + 4*np.pi/3])
    mx = mag_dist * np.cos(angles)  # shape (3,)
    my = mag_dist * np.sin(angles)

    settled_magnet = np.full(shape, -1, dtype=np.int32)
    step_count     = np.full(shape, max_steps, dtype=np.float32)
    active         = np.ones(shape, dtype=bool)

    h2 = h * h

    for step in range(max_steps):
        if not active.any():
            break

        # Compute magnetic forces
        fx = np.zeros_like(x); fy = np.zeros_like(y)
        for i in range(3):
            dx = mx[i] - x; dy = my[i] - y
            r3 = (dx*dx + dy*dy + h2) ** 1.5
            r3 = np.maximum(r3, 1e-6)
            fx += mag_strength * dx / r3
            fy += mag_strength * dy / r3

        # Euler step (active pixels only)
        ax = -delta * vx - kappa * x + fx
        ay = -delta * vy - kappa * y + fy
        vx[active] += ax[active] * dt
        vy[active] += ay[active] * dt
        x[active]  += vx[active] * dt
        y[active]  += vy[active] * dt

        # Check if settled
        speed = np.sqrt(vx*vx + vy*vy)
        for i in range(3):
            dx = mx[i] - x; dy = my[i] - y
            dist = np.sqrt(dx*dx + dy*dy)
            near_i = (dist < settle_tol) & (speed < settle_tol) & active & (settled_magnet < 0)
            if near_i.any():
                settled_magnet[near_i] = i
                step_count[near_i] = step
                active[near_i] = False

        if step % 100 == 0 and not active.any():
            break

    return settled_magnet, step_count


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    size   = p["size"]
    view   = p["view"]
    colors = [
        np.array(p["color_0"], dtype=np.float64) / 255.0,
        np.array(p["color_1"], dtype=np.float64) / 255.0,
        np.array(p["color_2"], dtype=np.float64) / 255.0,
    ]
    bg = np.array(p["color_bg"], dtype=np.float64) / 255.0

    # Build coordinate grid
    lin = np.linspace(-view, view, size, dtype=np.float64)
    x0, y0 = np.meshgrid(lin, lin)

    frame_idx = 0
    for step in range(p["steps"]):
        if step < p["warmup"] or step % p["capture_every"] != 0:
            continue

        t = step / max(p["steps"] - 1, 1)
        h = p["h_start"] + t * (p["h_end"] - p["h_start"])

        magnet, n_steps = _integrate_pendulum(
            x0, y0, h,
            p["delta"], p["kappa"], p["mag_dist"], p["mag_strength"],
            p["dt"], p["max_steps"], p["settle_tol"],
        )

        # Colorize
        canvas = np.zeros((size, size, 3), dtype=np.float64)
        brightness = (n_steps / p["max_steps"]) ** p["brightness_gamma"]
        brightness = 1.0 - brightness  # settled fast → bright
        # Ramp: step_count 0 = brightest, max_steps = darkest
        step_norm = n_steps / p["max_steps"]
        bright = np.clip(1.0 - step_norm ** p["brightness_gamma"], 0.05, 1.0)

        for i, col in enumerate(colors):
            mask = magnet == i
            if mask.any():
                canvas[mask] = col * bright[mask, None]

        unsettled = magnet < 0
        if unsettled.any():
            canvas[unsettled] = bg

        frame = (np.clip(canvas, 0, 1) * 255.0).astype(np.uint8)
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
