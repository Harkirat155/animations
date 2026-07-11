"""Flagship template: Gray-Scott reaction-diffusion.

A two-chemical PDE that self-organizes into organic, "satisfying" patterns
(coral, spots, mazes, mitosis) — it lands squarely in both the *mathematical*
and *aesthetic/satisfying* buckets. Fully deterministic for a fixed seed, pure
numpy, renders unattended.

Contract used by pipeline/generate.py:
    DEFAULTS: dict           # default parameter set
    generate_frames(params, frames_dir) -> dict
        # writes frames; returns {fps, n_frames, width, height, seed, config}
        # `config` is the fully-resolved param set (DEFAULTS + preset) — the
        # render is a pure function of (this module + config), so storing it
        # makes every output reproducible (see pipeline/post.py manifest).

Tuning the look is all in `feed`/`kill` — see ideas/params/ for named presets.
`v_max` maps the chemical field into the palette (see DEFAULTS note).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size": 512,            # square grid (px); output master is size x size
                            # 512 stays crisp upscaled to 1080; ~1min/clip (overnight-ok)
    "seed": 7,
    "feed": 0.0367,         # Gray-Scott feed rate (f)
    "kill": 0.0649,         # Gray-Scott kill rate (k)   -> "mitosis" look
    "Du": 1.0,              # Karl-Sims diffusion rates (fast, fills the frame)
    "Dv": 0.5,              # NOTE: keep Du*dt < ~1.25 (explicit-Euler stability bound)
    "dt": 1.0,
    "steps": 9000,          # total simulation steps
    "capture_every": 45,    # capture one frame every N steps
    "warmup": 600,          # steps to run before the FIRST captured frame.
                            # >0 skips the dead near-black seed opening so the clip
                            # opens on an already-bloomed (scroll-stopping) frame.
    "fps": 30,
    "seed_pattern": "random",   # "random" | "center"
    "n_spots": 14,          # initial V seed blobs (random pattern)
    # v_max: the chemical field V never reaches 1.0 — its ceiling is set by the
    # feed/kill regime (~0.38-0.42 for these presets). We map V/v_max -> palette,
    # so the FULL palette (incl. the bright payoff stops) actually renders. Set it
    # to roughly the post-warmup steady-state max of V for the preset; too low ->
    # highlights blow out to the top color, too high -> dull (top stops unused).
    # Must be a FIXED constant (not per-frame) or the clip flickers.
    "v_max": 0.40,
    # palette: list of [position 0..1, [r, g, b]] stops (positions strictly increasing)
    "palette": [
        [0.0, [4, 8, 28]],
        [0.4, [10, 60, 120]],
        [0.6, [30, 160, 200]],
        [0.8, [180, 230, 240]],
        [1.0, [255, 255, 255]],
    ],
}


def _laplacian(a: np.ndarray) -> np.ndarray:
    """9-point stencil with toroidal wrap (np.roll). Standard Gray-Scott weights."""
    return (
        -a
        + 0.2 * (np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1))
        + 0.05 * (np.roll(np.roll(a, 1, 0), 1, 1) + np.roll(np.roll(a, 1, 0), -1, 1)
                  + np.roll(np.roll(a, -1, 0), 1, 1) + np.roll(np.roll(a, -1, 0), -1, 1))
    )


def _build_lut(palette: list) -> np.ndarray:
    """256-entry RGB lookup table interpolated from palette stops."""
    positions = np.array([p[0] for p in palette])
    if not np.all(np.diff(positions) > 0):
        raise ValueError("palette stops must be strictly increasing in position")
    colors = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for c in range(3):
        lut[:, c] = np.clip(np.interp(xs, positions, colors[:, c]), 0, 255).astype(np.uint8)
    return lut


def _stamp_disc(U: np.ndarray, V: np.ndarray, cy: int, cx: int, r: int) -> None:
    """Seed a ROUND blob (not an axis-aligned square) so even an early frame reads
    as organic rather than a glitch."""
    yy, xx = np.ogrid[-r:r, -r:r]
    mask = (yy * yy + xx * xx) <= r * r
    V[cy - r:cy + r, cx - r:cx + r][mask] = 1.0
    U[cy - r:cy + r, cx - r:cx + r][mask] = 0.5


def _seed_initial(U: np.ndarray, V: np.ndarray, params: dict, rng) -> None:
    n = params["size"]
    if params["seed_pattern"] == "center":
        _stamp_disc(U, V, n // 2, n // 2, max(4, n // 20))
        return
    for _ in range(params["n_spots"]):
        r = int(rng.integers(3, max(4, n // 16)))
        cy, cx = (int(v) for v in rng.integers(r, n - r, 2))
        _stamp_disc(U, V, cy, cx, r)


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(
            f"unknown param keys: {sorted(unknown)} (known: {sorted(DEFAULTS)})"
        )
    p = {**DEFAULTS, **params}
    n = p["size"]
    rng = np.random.default_rng(p["seed"])

    U = np.ones((n, n), dtype=np.float64)
    V = np.zeros((n, n), dtype=np.float64)
    _seed_initial(U, V, p, rng)

    lut = _build_lut(p["palette"])
    f, k, Du, Dv, dt, vmax = p["feed"], p["kill"], p["Du"], p["Dv"], p["dt"], p["v_max"]

    frame_idx = 0
    for step in range(p["steps"]):
        uvv = U * V * V
        U += (Du * _laplacian(U) - uvv + f * (1.0 - U)) * dt
        V += (Dv * _laplacian(V) + uvv - (f + k) * V) * dt
        np.clip(U, 0.0, 1.0, out=U)
        np.clip(V, 0.0, 1.0, out=V)

        if step >= p["warmup"] and step % p["capture_every"] == 0:
            if not np.isfinite(V).all():
                raise SystemExit("RD diverged — lower Du/dt or move feed/kill in-range")
            # Rescale V/v_max into [0,1] so the FULL palette renders (V caps well
            # below 1.0). Fixed v_max, not a per-frame max, to avoid flicker.
            idx = np.clip((V / vmax) * 255.0, 0, 255).astype(np.intp)
            write_frame(frames_dir, frame_idx, lut[idx])
            frame_idx += 1

    return {
        "fps": p["fps"],
        "n_frames": frame_idx,
        "width": n,
        "height": n,
        "seed": p["seed"],
        "config": p,
    }
