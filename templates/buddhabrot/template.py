"""Buddhabrot template: reverse Mandelbrot escape-path accumulation.

Classic Buddhabrot: random c samples → iterate z²+c → if c escapes,
record every visited z value → accumulate those into a density buffer.
Unlike the Mandelbrot set (which colors each pixel by its iteration
count), this colors each pixel by how many orbits *passed through* it.
The result: a ghostly figure with intricate internal structure.

Animation mode: accumulate continuously across frames (like long-
exposure photography). Early frames look sparse; later ones are richly
detailed. Three channels (R, G, B) use different max_iter thresholds,
giving the image color depth — short orbits light the outer nebula,
long orbits reveal the fine inner structure.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size":            512,
    "seed":            0,
    "fps":             30,
    "steps":           240,
    "capture_every":   1,
    "warmup":          20,          # frames before starting to capture

    # Samples added per frame (cumulative exposure grows over clip)
    "samples_per_frame": 200_000,
    "batch_size":        20_000,    # vectorised batch

    # Three max_iter thresholds → R, G, B
    "max_iter_r":  200,    # red: outer nebula (fast orbits)
    "max_iter_g":  1000,   # green: mid structure
    "max_iter_b":  5000,   # blue: deep inner detail

    # View window
    "cx":        -0.5,
    "cy":         0.0,
    "half_width": 1.6,     # half the width of the view

    # Gamma per channel (lower → brighter faint regions)
    "gamma_r": 0.35,
    "gamma_g": 0.35,
    "gamma_b": 0.40,

    # Gain multipliers (compensate for fewer long-orbit hits)
    "gain_r": 1.0,
    "gain_g": 2.0,
    "gain_b": 8.0,
}


def _add_samples(density, size, cx, cy, hw, max_iter, n_samples, batch_size, rng):
    """Add n_samples escaping-orbit paths to density (in-place)."""
    remaining = n_samples
    while remaining > 0:
        bs = min(batch_size, remaining)
        remaining -= bs

        # Sample c uniformly in the interesting bounding box
        cr = rng.uniform(-2.5, 1.0, bs)
        ci = rng.uniform(-1.25, 1.25, bs)

        zr = np.zeros(bs)
        zi = np.zeros(bs)

        # Store path (max_iter × bs) — manageable for max_iter ≤ 5000, bs = 20000
        # max: 5000 × 20000 × 8B × 2 channels = 1.6 GB — too much at max_iter=5000
        # Use max_iter-chunked approach instead: record per-step, flush at escape
        # Actually, batch_size=20000, max_iter=5000 → 5000×20000×8B = 800MB each (zr/zi)
        # Lower batch_size to 4000 for max_iter >= 1000

        alive   = np.ones(bs, dtype=bool)
        escaped = np.zeros(bs, dtype=bool)
        paths_r = [None] * max_iter
        paths_i = [None] * max_iter

        for it in range(max_iter):
            active = alive
            if not active.any():
                break
            zr_new = zr * zr - zi * zi + cr
            zi_new = 2.0 * zr * zi + ci
            zr = np.where(active, zr_new, zr)
            zi = np.where(active, zi_new, zi)

            just_escaped = active & (zr * zr + zi * zi > 4.0)
            escaped |= just_escaped
            alive = active & ~just_escaped

            paths_r[it] = zr.copy()
            paths_i[it] = zi.copy()

        # For each escaped trajectory, accumulate its full path
        esc_cols = np.where(escaped)[0]
        if len(esc_cols) == 0:
            continue

        for col in esc_cols:
            for it in range(max_iter):
                pr = paths_r[it]
                if pr is None:
                    break
                zr_val = pr[col]
                zi_val = paths_i[it][col]
                if np.isnan(zr_val):
                    break
                # Map to pixel
                px = int((zr_val - (cx - hw)) / (2 * hw) * (size - 1))
                py = int((zi_val - (cy - hw)) / (2 * hw) * (size - 1))
                if 0 <= px < size and 0 <= py < size:
                    density[py, px] += 1.0
                # Mirror (imaginary symmetry)
                py_m = size - 1 - py
                if 0 <= py_m < size:
                    density[py_m, px] += 1.0

    return density


def _add_samples_fast(density, size, cx, cy, hw, max_iter, n_samples, batch_size, rng):
    """Vectorised version for smaller max_iter (fits in memory)."""
    remaining = n_samples
    while remaining > 0:
        bs = min(batch_size, remaining)
        remaining -= bs

        cr = rng.uniform(-2.5, 1.0, bs)
        ci = rng.uniform(-1.25, 1.25, bs)
        zr = np.zeros(bs)
        zi = np.zeros(bs)

        path_r = np.full((max_iter, bs), np.nan, dtype=np.float32)
        path_i = np.full((max_iter, bs), np.nan, dtype=np.float32)

        alive   = np.ones(bs, dtype=bool)
        escaped = np.zeros(bs, dtype=bool)

        for it in range(max_iter):
            if not alive.any():
                break
            zr_new = zr * zr - zi * zi + cr
            zi_new = 2.0 * zr * zi + ci
            zr = np.where(alive, zr_new, zr)
            zi = np.where(alive, zi_new, zi)

            path_r[it] = np.where(alive, zr, np.nan).astype(np.float32)
            path_i[it] = np.where(alive, zi, np.nan).astype(np.float32)

            just_esc = alive & (zr * zr + zi * zi > 4.0)
            escaped |= just_esc
            alive &= ~just_esc

        esc_idx = np.where(escaped)[0]
        if len(esc_idx) == 0:
            continue

        zr_flat = path_r[:, esc_idx].ravel().astype(float)
        zi_flat = path_i[:, esc_idx].ravel().astype(float)
        valid   = ~np.isnan(zr_flat)
        zr_flat = zr_flat[valid]
        zi_flat = zi_flat[valid]

        px = ((zr_flat - (cx - hw)) / (2 * hw) * (size - 1)).astype(int)
        py = ((zi_flat - (cy - hw)) / (2 * hw) * (size - 1)).astype(int)
        mask = (px >= 0) & (px < size) & (py >= 0) & (py < size)
        np.add.at(density, (py[mask], px[mask]), 1.0)

        py_m = size - 1 - py[mask]
        valid2 = (py_m >= 0) & (py_m < size)
        np.add.at(density, (py_m[valid2], px[mask][valid2]), 1.0)


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    size  = p["size"]
    rng   = np.random.default_rng(p["seed"])
    cx    = p["cx"]
    cy    = p["cy"]
    hw    = p["half_width"]

    # Persistent density buffers (accumulate across frames)
    dr = np.zeros((size, size), dtype=np.float64)
    dg = np.zeros((size, size), dtype=np.float64)
    db = np.zeros((size, size), dtype=np.float64)

    frame_idx = 0
    spf = p["samples_per_frame"]
    bs  = p["batch_size"]

    for step in range(p["steps"]):
        # Add new samples to each channel
        _add_samples_fast(dr, size, cx, cy, hw, p["max_iter_r"], spf, bs, rng)
        _add_samples_fast(dg, size, cx, cy, hw, p["max_iter_g"], spf // 4,
                          min(bs, 5000), rng)
        _add_samples_fast(db, size, cx, cy, hw, p["max_iter_b"], spf // 16,
                          min(bs, 2000), rng)

        if step >= p["warmup"] and step % p["capture_every"] == 0:
            def ch(d, gamma, gain):
                v = np.log1p(d * gain)
                mx = v.max()
                if mx == 0:
                    return np.zeros_like(v)
                return np.power(v / mx, gamma)

            r = ch(dr, p["gamma_r"], p["gain_r"])
            g = ch(dg, p["gamma_g"], p["gain_g"])
            b = ch(db, p["gamma_b"], p["gain_b"])

            frame = (np.clip(np.stack([r, g, b], axis=2), 0, 1) * 255).astype(np.uint8)
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
