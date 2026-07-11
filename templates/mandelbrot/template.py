"""Mandelbrot set template.

Renders the Mandelbrot set f_c(z) = z² + c, c = pixel position.
Smooth escape-time colouring.

Animation modes:
  "zoom"   — exponential zoom into a coordinate (zoom_cx, zoom_cy)
  "rotate" — orbit the view around a centre point (angle sweep)
  "hue"    — static view, palette cycles over time

Fractal types (via `fractal` param):
  "mandelbrot" — classic z² + c  (default)
  "burning_ship" — (|Re(z)| + i|Im(z)|)² + c  (ship-shaped fractal)
  "tricorn"    — conj(z)² + c  (Mandelbar, bilaterally symmetric)
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

    # Animation mode: "zoom" | "hue" | "orbit"
    "mode": "zoom",

    # Zoom target (complex coordinate to zoom into)
    "zoom_cx":    -0.7269,
    "zoom_cy":     0.1889,
    "zoom_start":  1.5,      # initial half-width of view
    "zoom_end":    0.003,    # final half-width (exponential interpolation)

    # View centre (stays fixed during zoom unless orbit mode)
    "view_cx": None,  # defaults to zoom_cx
    "view_cy": None,  # defaults to zoom_cy

    # Orbit mode: sweep angle around centre at fixed zoom
    "orbit_radius": 0.0001,
    "orbit_start":  0.0,
    "orbit_end":    6.2832,

    # Hue mode: palette shift per frame
    "hue_rate": 0.004,

    "max_iter":      512,
    "escape_radius": 128.0,
    "cycle_len":     32.0,

    "palette": [
        [0.0,  [0,   0,   0]],
        [0.08, [0,   10,  50]],
        [0.2,  [0,   60, 180]],
        [0.38, [0,  180, 220]],
        [0.55, [180, 240, 255]],
        [0.70, [255, 200,  60]],
        [0.84, [255,  40,   0]],
        [1.0,  [255, 255, 255]],
    ],

    "interior_color": [0, 0, 0],
    "hue_shift": 0.0,   # starting LUT shift (fraction [0,1])

    # Fractal type: "mandelbrot" | "burning_ship" | "tricorn"
    "fractal": "mandelbrot",
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

    max_iter   = int(p["max_iter"])
    escape2    = float(p["escape_radius"]) ** 2
    log_escape = math.log2(math.log2(float(p["escape_radius"])))
    cycle_len  = float(p["cycle_len"])
    mode       = p["mode"]

    # Zoom: exponential interpolation so zoom feels constant-speed
    log_zs = math.log(p["zoom_start"])
    log_ze = math.log(p["zoom_end"])

    frame_idx = 0

    for step in range(p["steps"]):
        t_f = step / max(1, p["steps"] - 1)

        if mode == "zoom":
            zoom = math.exp(log_zs + t_f * (log_ze - log_zs))
            cx   = p["zoom_cx"] if p["view_cx"] is None else p["view_cx"]
            cy   = p["zoom_cy"] if p["view_cy"] is None else p["view_cy"]
        elif mode == "orbit":
            zoom  = p["zoom_start"]
            angle = p["orbit_start"] + t_f * (p["orbit_end"] - p["orbit_start"])
            cx    = (p["zoom_cx"] if p["view_cx"] is None else p["view_cx"]) + p["orbit_radius"] * math.cos(angle)
            cy    = (p["zoom_cy"] if p["view_cy"] is None else p["view_cy"]) + p["orbit_radius"] * math.sin(angle)
        else:  # hue
            zoom = p["zoom_start"]
            cx   = p["zoom_cx"] if p["view_cx"] is None else p["view_cx"]
            cy   = p["zoom_cy"] if p["view_cy"] is None else p["view_cy"]

        re = np.linspace(cx - zoom, cx + zoom, n, dtype=np.float64)
        im = np.linspace(cy - zoom, cy + zoom, n, dtype=np.float64)
        CR, CI = np.meshgrid(re, im)

        # Iterate: z = 0, orbit depends on fractal type
        ZR = np.zeros_like(CR)
        ZI = np.zeros_like(CI)
        iters     = np.zeros((n, n), dtype=np.int32)
        escaped   = np.zeros((n, n), dtype=bool)
        cap_zmod2 = np.zeros((n, n), dtype=np.float64)
        fractal   = p["fractal"]

        for it in range(1, max_iter + 1):
            if fractal == "burning_ship":
                ZR_new = ZR * ZR - ZI * ZI + CR
                ZI_new = 2.0 * np.abs(ZR * ZI) + CI
            elif fractal == "tricorn":
                ZR_new = ZR * ZR - ZI * ZI + CR
                ZI_new = -2.0 * ZR * ZI + CI
            else:  # mandelbrot
                ZR_new = ZR * ZR - ZI * ZI + CR
                ZI_new = 2.0 * ZR * ZI + CI
            ZR, ZI = ZR_new, ZI_new
            mod2   = ZR * ZR + ZI * ZI
            newly  = (mod2 > escape2) & ~escaped
            if newly.any():
                iters[newly]     = it
                cap_zmod2[newly] = mod2[newly]
                escaped         |= newly
            if escaped.all():
                break

        # Smooth colouring
        hue_shift = step * p["hue_rate"] if mode == "hue" else p["hue_shift"]
        canvas = np.full((n, n, 3), ic, dtype=np.float64)
        mask   = escaped
        if mask.any():
            log_z   = 0.5 * np.log2(np.maximum(cap_zmod2[mask], 1e-10))
            smooth  = iters[mask].astype(np.float64) + 1.0 - np.log2(np.maximum(log_z, 1e-10)) + log_escape
            t_col   = ((smooth % cycle_len) / cycle_len + hue_shift) % 1.0
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
