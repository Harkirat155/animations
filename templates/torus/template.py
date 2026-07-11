"""Torus template: 3D parametric torus rendered as a glowing point cloud.

Generates a donut surface sampled at (n_u × n_v) points, rotated continuously
around X and Y axes, and projected onto the 2D canvas.  Scatter accumulation
into an HDR buffer gives natural density gradients — the inner rim concentrates
more points per pixel, glowing brighter like a lit rim.

Depth-based shading (fog) dims points behind the equatorial plane, giving 3D
form cues without explicit ray-tracing.  Optional colour-by-depth maps the
front-to-back z range onto the palette.

Rotation: each frame advances angle_y by ry_rate and angle_x by rx_rate (both
in radians/frame).  An initial tilt (tilt_x, tilt_y) orients the torus at
the start so it is never viewed edge-on.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size":          512,
    "fps":           30,
    "steps":         240,
    "seed":          0,

    # Torus geometry (fractions of half-canvas)
    "R":             0.55,   # major radius (centre → tube centre)
    "r":             0.21,   # tube radius

    # Sampling density
    "n_u":           1400,   # major-circle samples
    "n_v":           700,    # tube samples  → ~1M surface pts

    # Initial orientation and per-frame rotation speeds (radians/frame)
    "tilt_x":        0.55,   # initial X-tilt (radians, ~31°)
    "tilt_y":        0.0,
    "ry_rate":       0.025,  # Y-axis rotation speed
    "rx_rate":       0.008,  # X-axis wobble speed

    # Depth shading
    "fog_amount":    0.55,   # 0=none, 1=full fog (back points invisible)

    # Rendering
    "gamma":         0.38,
    "density_clip":  0.997,
    "bg_color":      [2, 3, 12],

    "palette": [
        [0.0,  [2,    3,   12]],
        [0.10, [0,   25,  100]],
        [0.25, [0,   90,  210]],
        [0.44, [0,  175,  255]],
        [0.63, [80,  225, 255]],
        [0.80, [190, 245, 255]],
        [1.0,  [255, 255, 255]],
    ],
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs  = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for c in range(3):
        lut[:, c] = np.clip(np.interp(xs, positions, colors[:, c]), 0, 255).astype(np.uint8)
    return lut


def _torus_surface(R: float, r: float, n_u: int, n_v: int):
    """Return unit-scale torus point cloud (x, y, z) — all in [-R-r, R+r]."""
    u = np.linspace(0.0, 2.0 * np.pi, n_u, endpoint=False)
    v = np.linspace(0.0, 2.0 * np.pi, n_v, endpoint=False)
    UU, VV = np.meshgrid(u, v)
    UU = UU.ravel()
    VV = VV.ravel()
    tube_r = R + r * np.cos(VV)
    x = tube_r * np.cos(UU)
    y = tube_r * np.sin(UU)
    z = r * np.sin(VV)
    return x, y, z


def _rotate(x, y, z, rx: float, ry: float):
    """Rotate 3D points: first around X axis, then around Y axis."""
    # X-axis rotation
    cos_rx, sin_rx = np.cos(rx), np.sin(rx)
    y2 =  y * cos_rx - z * sin_rx
    z2 =  y * sin_rx + z * cos_rx
    # Y-axis rotation
    cos_ry, sin_ry = np.cos(ry), np.sin(ry)
    x3 =  x * cos_ry + z2 * sin_ry
    z3 = -x * sin_ry + z2 * cos_ry
    return x3, y2, z3


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    p = {**DEFAULTS, **params}

    n           = p["size"]
    R           = p["R"]
    r           = p["r"]
    n_u         = p["n_u"]
    n_v         = p["n_v"]
    tilt_x      = p["tilt_x"]
    tilt_y      = p["tilt_y"]
    ry_rate     = p["ry_rate"]
    rx_rate     = p["rx_rate"]
    fog         = p["fog_amount"]
    gamma       = p["gamma"]
    density_clip = p["density_clip"]
    lut         = _build_lut(p["palette"])
    bg          = np.array(p["bg_color"], dtype=np.float64) / 255.0

    # Pre-build torus in canonical orientation
    x0, y0, z0 = _torus_surface(R, r, n_u, n_v)
    # Apply initial tilt once (static part of rotation)
    x0, y0, z0 = _rotate(x0, y0, z0, tilt_x, tilt_y)

    half = (n - 1) * 0.5
    max_coord = R + r  # max coordinate magnitude

    for frame_idx in range(p["steps"]):
        angle_y = frame_idx * ry_rate
        angle_x = frame_idx * rx_rate

        xr, yr, zr = _rotate(x0, y0, z0, angle_x, angle_y)

        # Orthographic projection: x → screen_x, y → screen_y (z is depth)
        # Scale: max_coord maps to ≈0.9 * half
        scale = half * 0.88 / max_coord
        px = (xr * scale + half).astype(np.float64)
        py = (-yr * scale + half).astype(np.float64)  # flip y for screen coords

        # Depth-based weight: z in [-max_coord, max_coord], front = bright
        z_norm = (zr / max_coord + 1.0) * 0.5          # [0, 1], front = 1
        weight = 1.0 - fog * (1.0 - z_norm)             # [1-fog, 1]

        # Only render points on the visible hemisphere (basic backface culling)
        visible = zr > -(max_coord * 0.92)
        px_v = px[visible]; py_v = py[visible]; w_v = weight[visible]

        pxi = px_v.astype(np.intp).clip(0, n - 1)
        pyi = py_v.astype(np.intp).clip(0, n - 1)

        density = np.zeros((n, n), dtype=np.float64)
        np.add.at(density, (pyi, pxi), w_v)

        # Tonemap
        nonzero = density[density > 0]
        clip_val = np.percentile(nonzero, density_clip * 100) if nonzero.size > 0 else 1.0
        d = np.clip(density / max(clip_val, 1e-9), 0.0, 1.0)
        d = np.power(d, gamma)

        idx    = (d * 255).astype(np.intp).clip(0, 255)
        canvas = lut[idx].astype(np.float64) / 255.0
        alpha  = d[:, :, None]
        canvas = canvas * alpha + bg[None, None, :] * (1.0 - alpha)
        frame  = (canvas * 255.0).astype(np.uint8)
        write_frame(frames_dir, frame_idx, frame)

    return {
        "fps":      p["fps"],
        "n_frames": p["steps"],
        "width":    n,
        "height":   n,
        "seed":     p["seed"],
        "config":   p,
    }
