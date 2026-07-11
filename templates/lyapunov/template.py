"""Lyapunov fractal template.

Each pixel (a, b) in parameter space maps to a logistic-map Lyapunov exponent:
the orbit alternates between r=a and r=b according to a symbolic sequence (e.g. "AABB").
  x_{n+1} = r_n · x_n · (1 − x_n)
  λ = (1/N) Σ log|r_n · (1 − 2·x_n)|

Negative λ → stable (periodic) regime → cool blues / teals.
Positive λ → chaotic regime → hot golds / reds.
Near-zero → transition zone → the fractal boundary, where most visual interest lives.

Animation: the view window slowly pans or zooms into the fractal boundary, OR the
sequence morphs between patterns, OR the color hue gently rotates over time.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size":    512,
    "seed":    0,
    "fps":     30,
    "steps":   240,
    "capture_every": 1,
    "warmup":  0,

    # Parameter-space view: a in [a_min, a_max], b in [b_min, b_max]
    # The classic "Zircon Zity" region is around a=[2,4], b=[2,4]
    "a_min":   2.0,
    "a_max":   4.0,
    "b_min":   2.0,
    "b_max":   4.0,

    # Zoom target: at t=1.0 the view has zoomed toward this point
    # Set zoom_end = 1.0 for no zoom
    "zoom_end": 1.0,   # <1.0 zooms in; ratio of final_span / initial_span
    "zoom_cx":  3.4,   # zoom center a
    "zoom_cy":  3.6,   # zoom center b

    # Symbolic sequence (A or B characters, length 2–8)
    # At each iteration step, choose r=a if seq[i%len]=A else r=b
    "sequence": "AB",

    # Lyapunov iterations (more = smoother, slower)
    "warmup_iters": 100,  # transient to discard
    "n_iters":      200,  # iters used for exponent averaging

    # Color mapping
    # Stable (λ < 0): palette_stable maps |λ| 0→peak to a cool palette
    # Chaotic (λ > 0): palette_chaos maps λ 0→peak to a hot palette
    "stable_peak":   -4.0,   # λ below this is saturated-stable color
    "chaos_peak":     2.0,   # λ above this is saturated-chaos color
    "palette_stable": [
        [0.0,  [10,  8,  30]],
        [0.3,  [10, 40, 100]],
        [0.65, [20, 120, 200]],
        [1.0,  [100, 220, 255]],
    ],
    "palette_chaos": [
        [0.0,  [10,  8,  30]],
        [0.25, [80,  30,  5]],
        [0.55, [220, 100, 10]],
        [1.0,  [255, 230,  80]],
    ],

    # Hue rotation over time (degrees per second, 0 = static colors)
    "hue_speed": 0.0,
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for ch in range(3):
        lut[:, ch] = np.clip(np.interp(xs, positions, colors[:, ch]), 0, 255).astype(np.uint8)
    return lut


def _lyapunov_exponents(a_flat, b_flat, sequence, warmup_iters, n_iters):
    """Vectorized Lyapunov exponent for flat arrays a_flat, b_flat (same shape)."""
    seq_arr = np.array([1 if c == 'A' else 0 for c in sequence], dtype=np.int32)
    seq_len = len(seq_arr)
    n = a_flat.shape[0]

    x = np.full(n, 0.5, dtype=np.float64)

    # Warmup phase — discard transient
    for i in range(warmup_iters):
        r = np.where(seq_arr[i % seq_len] == 1, a_flat, b_flat)
        x = r * x * (1.0 - x)
        # Guard against blow-up
        x = np.clip(x, 1e-12, 1.0 - 1e-12)

    # Accumulate log|f'|
    log_sum = np.zeros(n, dtype=np.float64)
    for i in range(n_iters):
        r = np.where(seq_arr[(warmup_iters + i) % seq_len] == 1, a_flat, b_flat)
        x = r * x * (1.0 - x)
        x = np.clip(x, 1e-12, 1.0 - 1e-12)
        deriv = np.abs(r * (1.0 - 2.0 * x))
        deriv = np.maximum(deriv, 1e-30)
        log_sum += np.log(deriv)

    return log_sum / n_iters


def _render_lyapunov(a_min, a_max, b_min, b_max, size, sequence,
                     warmup_iters, n_iters,
                     lut_stable, lut_chaos,
                     stable_peak, chaos_peak):
    n = size
    # Build pixel grid: a varies along x, b varies along y
    a_vals = np.linspace(a_min, a_max, n, dtype=np.float64)
    b_vals = np.linspace(b_min, b_max, n, dtype=np.float64)
    aa, bb = np.meshgrid(a_vals, b_vals)
    a_flat = aa.ravel()
    b_flat = bb.ravel()

    lam = _lyapunov_exponents(a_flat, b_flat, sequence, warmup_iters, n_iters)
    lam = lam.reshape(n, n)

    # Colorize: stable (λ < 0) → cool, chaos (λ > 0) → hot, boundary → dark
    canvas = np.zeros((n, n, 3), dtype=np.uint8)

    stable_mask = lam < 0.0
    chaos_mask  = lam > 0.0

    if stable_mask.any():
        t_s = np.clip(-lam[stable_mask] / max(-stable_peak, 1e-9), 0.0, 1.0)
        idx = (t_s * 255).astype(np.intp).clip(0, 255)
        canvas[stable_mask] = lut_stable[idx]

    if chaos_mask.any():
        t_c = np.clip(lam[chaos_mask] / max(chaos_peak, 1e-9), 0.0, 1.0)
        idx = (t_c * 255).astype(np.intp).clip(0, 255)
        canvas[chaos_mask] = lut_chaos[idx]

    return canvas


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    lut_stable = _build_lut(p["palette_stable"])
    lut_chaos  = _build_lut(p["palette_chaos"])
    size       = p["size"]
    seq        = p["sequence"].upper()

    frame_idx = 0
    for step in range(p["steps"]):
        if step < p["warmup"] or step % p["capture_every"] != 0:
            continue

        t = step / max(p["steps"] - 1, 1)

        # Zoom interpolation (exponential so zoom feels smooth)
        zoom = p["zoom_end"] ** t  # 1.0 → no zoom; <1.0 → zoom in
        cx, cy = p["zoom_cx"], p["zoom_cy"]

        a_span_orig = p["a_max"] - p["a_min"]
        b_span_orig = p["b_max"] - p["b_min"]
        a_min = cx - (cx - p["a_min"]) * zoom
        a_max = cx + (p["a_max"] - cx) * zoom
        b_min = cy - (cy - p["b_min"]) * zoom
        b_max = cy + (p["b_max"] - cy) * zoom

        frame = _render_lyapunov(
            a_min, a_max, b_min, b_max, size, seq,
            p["warmup_iters"], p["n_iters"],
            lut_stable, lut_chaos,
            p["stable_peak"], p["chaos_peak"],
        )
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
