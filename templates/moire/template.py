"""Moiré pattern template.

Overlays two (or more) regular patterns — concentric rings, radial lines,
or linear gratings — with a slow angular or spatial offset between them.
The beating between the two periods produces large-scale moiré fringes that
rotate or morph as the offset advances each frame.

Each layer's intensity:
  layer_i(x, y) = 0.5 * (1 + cos(2π * freq_i(x, y) + phase_i * t))

The layers are multiplicatively or additively combined and mapped through a LUT.
"""
from __future__ import annotations

from pathlib import Path
import math

import numpy as np

from pipeline.encode import write_frame


def _build_lut(palette: list, size: int = 512) -> np.ndarray:
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

    # Layers: list of {type, freq, phase_rate}
    # type: "rings" | "radial" | "linear_x" | "linear_y" | "linear_d"
    # freq: spatial frequency (cycles per canvas)
    # phase_rate: phase advance per frame (radians)
    # angle: for linear gratings — rotation in radians at t=0 (default 0)
    # angle_rate: angular advance per frame
    "layers": [
        {"type": "rings",    "freq": 18.0, "phase_rate":  0.15, "angle": 0.0, "angle_rate": 0.0},
        {"type": "rings",    "freq": 18.0, "phase_rate": -0.12, "angle": 0.0, "angle_rate": 0.008},
    ],

    # Blend mode: "product" | "sum" | "difference"
    "blend": "product",

    "palette": [
        [0.0,  [0,   0,   0]],
        [0.35, [20,  20,  80]],
        [0.6,  [100, 160, 255]],
        [0.82, [220, 240, 255]],
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
    L   = len(lut)
    cx, cy = n * 0.5, n * 0.5
    TWO_PI = 2.0 * math.pi

    # Pixel grids
    xs, ys = np.meshgrid(np.linspace(-1.0, 1.0, n), np.linspace(-1.0, 1.0, n))
    radial = np.sqrt(xs * xs + ys * ys)
    angle_grid = np.arctan2(ys, xs)

    layers = p["layers"]
    frame_idx = 0

    for step in range(p["steps"]):
        t = float(step)
        vals_list = []

        for lay in layers:
            ltype       = lay.get("type", "rings")
            freq        = float(lay.get("freq", 10.0))
            phase_rate  = float(lay.get("phase_rate", 0.1))
            angle_start = float(lay.get("angle", 0.0))
            angle_rate  = float(lay.get("angle_rate", 0.0))
            angle_t     = angle_start + angle_rate * t
            phase_t     = phase_rate * t

            if ltype == "rings":
                field = freq * radial
            elif ltype == "radial":
                field = freq * angle_grid / TWO_PI
            elif ltype == "linear_x":
                field = freq * (xs * math.cos(angle_t) + ys * math.sin(angle_t))
            elif ltype == "linear_y":
                field = freq * (-xs * math.sin(angle_t) + ys * math.cos(angle_t))
            elif ltype == "linear_d":
                field = freq * ((xs + ys) * math.cos(angle_t))
            else:
                field = freq * radial

            v = 0.5 * (1.0 + np.cos(TWO_PI * field + phase_t))
            vals_list.append(v)

        # Combine layers
        if p["blend"] == "product":
            combined = vals_list[0]
            for v in vals_list[1:]:
                combined = combined * v
        elif p["blend"] == "sum":
            combined = np.zeros_like(vals_list[0])
            for v in vals_list:
                combined = combined + v / len(vals_list)
        else:  # difference
            combined = vals_list[0]
            for v in vals_list[1:]:
                combined = np.abs(combined - v)

        v_norm  = combined.clip(0.0, 1.0)
        idx_lut = (v_norm * (L - 1)).astype(np.intp)
        canvas  = lut[idx_lut]

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
