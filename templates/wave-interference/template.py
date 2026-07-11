"""Wave interference / ripple tank template.

Simulates N point wave sources at fixed positions. Each source emits
circular waves with configurable wavelength, amplitude, and speed.
At each pixel the field value is the sum of contributions from all
sources:

  field[y,x] = sum_i  A_i * cos(2π * (dist_i / λ) - ω * t + φ_i)

The signed field is mapped through a colour LUT.  Constructive and
destructive interference produces the characteristic fringe patterns.
Animated by advancing phase (ω * dt) each frame.

Sources are specified as fractions of the canvas size [0,1]^2 so
layouts are resolution-independent.
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

    # Wave sources: list of [sx, sy, amplitude, phase_offset]
    # Positions are fractions of canvas size [0,1]
    "sources": [
        [0.35, 0.5, 1.0, 0.0],
        [0.65, 0.5, 1.0, 0.0],
    ],

    "wavelength": 40.0,   # pixels at full resolution
    "speed":       1.2,   # pixels per frame
    "dt":          0.08,  # phase advance per frame (radians/frame ~ ω*dt)

    "palette": [
        [0.0,  [0,   0,  30]],
        [0.25, [0,  60, 180]],
        [0.5,  [0, 200, 255]],
        [0.75, [180, 240, 255]],
        [1.0,  [255, 255, 255]],
    ],
}


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    n   = p["size"]
    lut = _build_lut(p["palette"])

    # Coordinate grids — (n, n)
    xs, ys = np.meshgrid(np.arange(n, dtype=np.float64),
                          np.arange(n, dtype=np.float64))

    # Precompute distance maps for each source — (n_sources, n, n)
    sources = p["sources"]
    dists   = []
    amps    = []
    phases  = []
    for sx, sy, amp, phi in sources:
        dx = xs - sx * n
        dy = ys - sy * n
        dists.append(np.sqrt(dx * dx + dy * dy))
        amps.append(float(amp))
        phases.append(float(phi))

    lam  = float(p["wavelength"])
    k    = 2.0 * np.pi / lam     # wave number
    dt   = float(p["dt"])
    n_s  = len(sources)
    frame_idx = 0

    for step in range(p["steps"]):
        t = step * dt
        field = np.zeros((n, n), dtype=np.float64)
        for i in range(n_s):
            field += amps[i] * np.cos(k * dists[i] - t + phases[i])

        # Normalise from [-n_s, n_s] to [0, 1]
        v_norm = ((field + n_s) / (2.0 * n_s)).clip(0.0, 1.0)
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
