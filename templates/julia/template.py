"""Julia set fractal template.

Iterates f_c(z) = z² + c over the complex plane.  Escape-time
smooth colouring (Mandelbrot-style continuous renormalisation):

  smooth = iter + 1 - log2(log2(|z|))

maps every pixel to a continuous value in [0, ∞) regardless of
iteration count, eliminating banding.  The value is reduced modulo
a colour cycle length and mapped through a custom LUT.

Animation: c traces a circle of radius `c_radius` in the complex
plane.  The view window can zoom in/out and pan, controlled by
`zoom_start` / `zoom_end`.
"""
from __future__ import annotations

from pathlib import Path
import math

import numpy as np

from pipeline.encode import write_frame


def _build_lut(palette: list, size: int = 2048) -> np.ndarray:
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

    # Complex parameter c = c_radius * exp(i * theta)
    # theta sweeps from c_theta_start to c_theta_end over the clip
    "c_radius":      0.7885,
    "c_theta_start": 0.0,
    "c_theta_end":   6.2832,  # ≈ 2π  (full sweep)

    # View window (real / imaginary axis)
    "view_cx":  0.0,   # centre real part
    "view_cy":  0.0,   # centre imaginary part
    "zoom_start": 1.5, # half-width of view at frame 0
    "zoom_end":   1.5, # half-width of view at last frame (constant = no zoom)

    "max_iter":      256,
    "escape_radius": 128.0,
    "cycle_len":     64.0,  # iteration range per full palette cycle

    "palette": [
        [0.0,  [0,    0,   0]],
        [0.12, [20,   0,  80]],
        [0.28, [0,   80, 200]],
        [0.45, [0,  200, 220]],
        [0.60, [200, 240, 255]],
        [0.75, [255, 200,  60]],
        [0.88, [255,  80,   0]],
        [1.0,  [255, 255, 255]],
    ],

    # Interior colour (non-escaping points)
    "interior_color": [0, 0, 0],
}


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    n   = p["size"]
    lut = _build_lut(p["palette"])
    L   = len(lut)
    ic  = np.array(p["interior_color"], dtype=np.float64) / 255.0

    max_iter     = int(p["max_iter"])
    escape2      = float(p["escape_radius"]) ** 2
    log_escape   = math.log2(math.log2(float(p["escape_radius"])))
    cycle_len    = float(p["cycle_len"])

    frame_idx = 0

    for step in range(p["steps"]):
        t_f = step / max(1, p["steps"] - 1)   # [0, 1]

        # Parameter c
        theta = p["c_theta_start"] + t_f * (p["c_theta_end"] - p["c_theta_start"])
        cr = p["c_radius"] * math.cos(theta)
        ci = p["c_radius"] * math.sin(theta)

        # View window
        zoom = p["zoom_start"] + t_f * (p["zoom_end"] - p["zoom_start"])
        re = np.linspace(p["view_cx"] - zoom, p["view_cx"] + zoom, n, dtype=np.float64)
        im = np.linspace(p["view_cy"] - zoom, p["view_cy"] + zoom, n, dtype=np.float64)
        ZR, ZI = np.meshgrid(re, im)

        # Escape-time iteration — full-array unmasked (faster than per-pixel masking)
        iters       = np.zeros((n, n), dtype=np.int32)
        escaped     = np.zeros((n, n), dtype=bool)
        cap_zmod2   = np.zeros((n, n), dtype=np.float64)  # |z|² captured at escape step
        ZR_run      = ZR.copy()
        ZI_run      = ZI.copy()

        for it in range(1, max_iter + 1):
            zr_new = ZR_run * ZR_run - ZI_run * ZI_run + cr
            zi_new = 2.0 * ZR_run * ZI_run + ci
            ZR_run = zr_new
            ZI_run = zi_new
            mod2    = ZR_run * ZR_run + ZI_run * ZI_run
            newly   = (mod2 > escape2) & ~escaped
            if newly.any():
                iters[newly]     = it
                cap_zmod2[newly] = mod2[newly]
                escaped         |= newly
            if escaped.all():
                break

        # Smooth colouring for escaped pixels
        canvas = np.full((n, n, 3), ic, dtype=np.float64)
        mask   = escaped
        if mask.any():
            log_z   = 0.5 * np.log2(np.maximum(cap_zmod2[mask], 1e-10))
            smooth  = iters[mask].astype(np.float64) + 1.0 - np.log2(np.maximum(log_z, 1e-10)) + log_escape
            t_col   = (smooth % cycle_len) / cycle_len
            idx_lut = (t_col * (L - 1)).astype(np.intp).clip(0, L - 1)
            canvas[mask] = lut[idx_lut]

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
