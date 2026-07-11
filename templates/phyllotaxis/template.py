"""Phyllotaxis template: golden-angle Fibonacci spiral.

Plants grow leaves/seeds at the golden angle (≈ 137.508°) to pack densely without
crowding.  The result is a spiral pattern with simultaneous clockwise AND counter-
clockwise families — the exact counts are consecutive Fibonacci numbers.

Animation: dots accumulate in golden-angle order (the "growing" reveal), while
color cycles along each spiral arm, and a slow zoom / bloom unfolds the geometry.

Fast render: each frame is pure numpy scatter, no simulation loops — suitable for
overnight batch or rapid iteration.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

GOLDEN_ANGLE = np.pi * (3.0 - np.sqrt(5.0))   # ≈ 2.39996 rad ≈ 137.508°

DEFAULTS = {
    "size":         512,
    "seed":         0,
    "n_dots_final": 1400,    # total seeds at the end of the animation
    "dot_radius":   4,       # pixel radius of each seed dot
    "fps":          30,
    "steps":        300,     # frames (300 @ 30fps = 10s)
    "capture_every": 1,
    "warmup":       0,

    # Geometry
    "scale":        0.46,    # spiral scale: fraction of half-canvas radius
    "offset_angle": 0.0,     # rotate whole spiral (radians); vary across presets

    # Animation mode: "grow" | "rotate" | "bloom"
    # grow  – dots appear one by one (reveal)
    # rotate – all dots present, whole spiral slowly rotates
    # bloom  – all dots present, scale pulses in/out (breathe)
    "anim_mode":    "grow",

    # Colour: position along spiral arm drives the palette
    "bg_color":     [6,   5,  18],
    "palette": [
        [0.0,  [255, 200,  50]],
        [0.3,  [255, 130,  30]],
        [0.6,  [220,  50,  80]],
        [1.0,  [140,   0, 180]],
    ],
    "glow":         True,    # soft glow halo around each dot
    "glow_boost":   2.0,     # intensity multiplier for inner glow
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for c in range(3):
        lut[:, c] = np.clip(np.interp(xs, positions, colors[:, c]), 0, 255).astype(np.uint8)
    return lut


def _scatter_discs(canvas: np.ndarray, cx_arr: np.ndarray, cy_arr: np.ndarray,
                   colors_f: np.ndarray, offsets_y: np.ndarray,
                   offsets_x: np.ndarray, intensity: float = 1.0) -> None:
    """Fully vectorised disc splat: 3 np.add.at calls regardless of dot count.

    Expands each dot centre to all disc-pixel coordinates, clips to canvas,
    and scatters per-channel in one operation.
    """
    n = canvas.shape[0]
    D = len(offsets_y)
    N = len(cx_arr)

    # (N, D) pixel coordinates
    ys = cy_arr[:, None] + offsets_y[None, :]
    xs = cx_arr[:, None] + offsets_x[None, :]
    valid = (ys >= 0) & (ys < n) & (xs >= 0) & (xs < n)

    flat_y  = ys[valid]
    flat_x  = xs[valid]
    # colors_f: (N, 3) → expand to (N*D, 3) then filter
    colors_exp = np.repeat(colors_f, D, axis=0)[valid.ravel()]

    if intensity != 1.0:
        colors_exp = colors_exp * intensity

    np.add.at(canvas[:, :, 0], (flat_y, flat_x), colors_exp[:, 0])
    np.add.at(canvas[:, :, 1], (flat_y, flat_x), colors_exp[:, 1])
    np.add.at(canvas[:, :, 2], (flat_y, flat_x), colors_exp[:, 2])


def _draw_dots(canvas: np.ndarray, cx_arr: np.ndarray, cy_arr: np.ndarray,
               colors: np.ndarray, r: int, glow: bool, glow_boost: float) -> None:
    """Splat filled circles + optional glow ring. Fully vectorised."""
    dy, dx = np.mgrid[-r:r + 1, -r:r + 1]
    disc = dy * dy + dx * dx <= r * r
    ddy, ddx = dy[disc], dx[disc]

    colors_f = colors.astype(np.float64) / 255.0
    _scatter_discs(canvas, cx_arr, cy_arr, colors_f, ddy, ddx)

    if glow and r >= 2:
        gr   = r + 3
        dgy, dgx = np.mgrid[-gr:gr + 1, -gr:gr + 1]
        dist2 = dgy * dgy + dgx * dgx
        ring  = (dist2 > r * r) & (dist2 <= gr * gr)
        rrdy, rrdx = dgy[ring], dgx[ring]
        _scatter_discs(canvas, cx_arr, cy_arr, colors_f, rrdy, rrdx,
                       intensity=0.3 * glow_boost)


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    n     = p["size"]
    N     = int(p["n_dots_final"])
    lut   = _build_lut(p["palette"])
    bg    = np.array(p["bg_color"], dtype=np.float64) / 255.0
    r_max = int(p["dot_radius"])
    scale = float(p["scale"])
    mode  = p["anim_mode"]

    # Pre-compute all dot positions and colors
    indices   = np.arange(N)
    theta_all = indices * GOLDEN_ANGLE + float(p["offset_angle"])
    rr_all    = np.sqrt(indices / max(N - 1, 1))   # [0, 1]
    half      = n * 0.5
    radius_px = half * scale * rr_all

    # Adaptive dot radius: proportional to local inter-dot spacing (∝ sqrt(r)).
    # This prevents the center from saturating — inner dots get radius 1.
    r_each = np.maximum(1, (rr_all * r_max).astype(np.intp))

    color_t   = rr_all
    color_idx = (color_t * 255).astype(np.intp).clip(0, 255)
    colors_all = lut[color_idx]

    frame_idx = 0
    for step in range(p["steps"]):
        t = (step + 1) / p["steps"]

        if mode == "grow":
            n_active = max(1, int(t * N))
            theta  = theta_all[:n_active]
            rpx    = radius_px[:n_active]
            colors = colors_all[:n_active]
            radii  = r_each[:n_active]
        elif mode == "rotate":
            rot_offset = t * 2 * np.pi * 0.1
            theta  = theta_all + rot_offset
            rpx    = radius_px
            colors = colors_all
            radii  = r_each
            n_active = N
        else:  # bloom
            bloom_scale = 0.5 + 0.5 * np.sin(t * 2 * np.pi)
            theta  = theta_all
            rpx    = radius_px * bloom_scale
            colors = colors_all
            radii  = r_each
            n_active = N

        # Group by radius level and draw each group with matching disc
        canvas = np.full((n, n, 3), bg, dtype=np.float64)
        for rv in np.unique(radii):
            mask = radii == rv
            safe_margin = int(rv) + 4
            cxr = (half + rpx[mask] * np.cos(theta[mask])).astype(np.intp).clip(safe_margin, n - safe_margin - 1)
            cyr = (half + rpx[mask] * np.sin(theta[mask])).astype(np.intp).clip(safe_margin, n - safe_margin - 1)
            _draw_dots(canvas, cxr, cyr, colors[mask], int(rv),
                       bool(p["glow"]), float(p["glow_boost"]))
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
