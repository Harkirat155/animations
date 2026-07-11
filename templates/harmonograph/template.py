"""Harmonograph template: damped Lissajous / spirograph.

A harmonograph simulates two pairs of pendulums — one driving x, one driving y.
Near-integer frequency ratios produce elegant closed curves; slight detuning
causes the pattern to slowly rotate, giving silky animation.

Each frame renders the FULL damped curve from t=0 to t_max, but with per-frame
phase offsets that rotate the pattern across the clip.  The result is a seamless
morphing loop.

Intensity is built by scatter-accumulation: N_POINTS plotted per frame, so high-
crossing-density regions glow brighter — natural depth without any extra pass.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.float64)
    for c in range(3):
        lut[:, c] = np.interp(xs, positions, colors[:, c])
    return lut / 255.0

DEFAULTS = {
    "size":     512,
    "seed":     0,
    "n_points": 300_000,    # scatter points per frame; more → smoother curves
    "t_max":    60.0,       # pendulum time span
    "fps":      30,
    "steps":    360,        # frames (360 @ 30fps = 12s seamless loop)
    "capture_every": 1,
    "warmup":   0,

    # Frequency pairs (x = p1+p2, y = p3+p4) — near-integer ratios
    "freq_x1": 2.0,
    "freq_x2": 3.0,
    "freq_y1": 2.0,
    "freq_y2": 3.0,

    # Tiny detuning → pattern drifts / rotates over the clip
    "detune_x1":  0.004,
    "detune_x2": -0.003,
    "detune_y1":  0.002,
    "detune_y2": -0.005,

    # Phase offsets (radians); shape of the initial figure
    "phase_x1": 0.0,
    "phase_x2": 1.0,
    "phase_y1": 0.5,
    "phase_y2": 1.5,

    # Per-frame phase advance — drives the rotation animation
    # One full rotation per clip: 2π / steps → seamless loop
    "phase_advance": 0.01745,   # ≈ 2π/360

    # Exponential damping (0 → no decay; 0.01 → fully decayed well before t_max)
    "damping": 0.006,

    # Amplitude weights
    "amp_x1": 1.0,
    "amp_x2": 0.7,
    "amp_y1": 1.0,
    "amp_y2": 0.7,

    # Visual
    "bg_color":   [8,  5, 20],
    "line_color": [220, 180,  80],   # warm gold
    "glow_color": [255, 220, 120],   # brighter inner glow (None → use line_color)
    "intensity":  0.004,             # brightness per scatter point
    "glow_boost": 2.0,               # multiplier for the inner-glow pass (None → no glow)
    # palette: if set, each point is coloured by its t-position (early=0, late=1).
    # Overrides line_color/glow_color.  Set to None to use the flat-colour mode.
    "palette": None,
}


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    n        = p["size"]
    bg       = np.array(p["bg_color"],   dtype=np.float64) / 255.0
    lc       = np.array(p["line_color"], dtype=np.float64) / 255.0
    gc       = (np.array(p["glow_color"], dtype=np.float64) / 255.0
                if p["glow_color"] else lc)
    lut      = _build_lut(p["palette"]) if p["palette"] else None

    t     = np.linspace(0, p["t_max"], p["n_points"])
    t_norm = t / p["t_max"]                            # [0, 1] for palette lookup
    decay  = np.exp(-p["damping"] * t)

    frame_idx = 0
    phase_offset = 0.0
    audio_trace: list[float] = []

    for step in range(p["steps"]):
        phase_offset = step * p["phase_advance"]

        x = (
            p["amp_x1"] * np.sin((p["freq_x1"] + p["detune_x1"]) * t
                                  + p["phase_x1"] + phase_offset)
            + p["amp_x2"] * np.sin((p["freq_x2"] + p["detune_x2"]) * t
                                    + p["phase_x2"])
        ) * decay

        y = (
            p["amp_y1"] * np.sin((p["freq_y1"] + p["detune_y1"]) * t
                                  + p["phase_y1"])
            + p["amp_y2"] * np.sin((p["freq_y2"] + p["detune_y2"]) * t
                                    + p["phase_y2"] + phase_offset * 0.7)
        ) * decay

        # Map [-amp_range, amp_range] to [margin, size-margin]
        margin = int(n * 0.05)
        half   = n * 0.5 - margin
        cx = (x / (p["amp_x1"] + p["amp_x2"]) * half + n * 0.5).astype(np.intp)
        cy = (y / (p["amp_y1"] + p["amp_y2"]) * half + n * 0.5).astype(np.intp)

        valid = (cx >= 0) & (cx < n) & (cy >= 0) & (cy < n)
        cx, cy = cx[valid], cy[valid]

        canvas = np.full((n, n, 3), bg, dtype=np.float64)
        iv = p["intensity"]

        if lut is not None:
            # Gradient mode: colour each point by its t-position
            t_valid = t_norm[valid]
            c_idx   = (t_valid * 255).astype(np.intp).clip(0, 255)
            cols    = lut[c_idx] * iv           # (N, 3)
            np.add.at(canvas[:, :, 0], (cy, cx), cols[:, 0])
            np.add.at(canvas[:, :, 1], (cy, cx), cols[:, 1])
            np.add.at(canvas[:, :, 2], (cy, cx), cols[:, 2])
            if p["glow_boost"]:
                g_mask = np.arange(len(cx)) % 5 == 0
                gb_cols = cols[g_mask] * float(p["glow_boost"])
                np.add.at(canvas[:, :, 0], (cy[g_mask], cx[g_mask]), gb_cols[:, 0])
                np.add.at(canvas[:, :, 1], (cy[g_mask], cx[g_mask]), gb_cols[:, 1])
                np.add.at(canvas[:, :, 2], (cy[g_mask], cx[g_mask]), gb_cols[:, 2])
        else:
            # Flat-colour mode (original)
            np.add.at(canvas[:, :, 0], (cy, cx), lc[0] * iv)
            np.add.at(canvas[:, :, 1], (cy, cx), lc[1] * iv)
            np.add.at(canvas[:, :, 2], (cy, cx), lc[2] * iv)
            if p["glow_boost"]:
                g_mask = np.arange(len(cx)) % 5 == 0
                gx, gy = cx[g_mask], cy[g_mask]
                gb = iv * float(p["glow_boost"])
                np.add.at(canvas[:, :, 0], (gy, gx), gc[0] * gb)
                np.add.at(canvas[:, :, 1], (gy, gx), gc[1] * gb)
                np.add.at(canvas[:, :, 2], (gy, gx), gc[2] * gb)

        np.clip(canvas, 0.0, 1.0, out=canvas)

        if step >= p["warmup"] and step % p["capture_every"] == 0:
            write_frame(frames_dir, frame_idx, (canvas * 255.0).astype(np.uint8))
            audio_trace.append(float(phase_offset))
            frame_idx += 1

    return {
        "fps":         p["fps"],
        "n_frames":    frame_idx,
        "width":       n,
        "height":      n,
        "seed":        p["seed"],
        "config":      p,
        "audio_trace": audio_trace,
    }
