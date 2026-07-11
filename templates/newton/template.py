"""Newton fractal template.

Applies Newton's method for root-finding to the complex polynomial
f(z) = z^n − e^(i·n·θ) on a uniform pixel grid.  Each pixel converges
to one of n evenly-spaced roots; the basin of attraction and the number
of iterations to converge together determine the colour.

Coloring: the LUT is divided into n equal bands (one per root).  Within
each band, the iteration fraction t ∈ [0,1] drives the palette from
dark (interior, fast convergence) through bright (boundary, slow).
Fractal boundaries explode in brightness because those pixels are the
slowest to converge.

Animation: θ sweeps from theta_start → theta_end (radians).  This
rotates the polynomial's roots, spinning the entire fractal pattern
continuously.  One full rotation = 2π/n radians of θ sweep.  Default:
one full rotation over the clip.

Optional zoom: exponential zoom from zoom_start → zoom_end around
(view_cx, view_cy).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size":         512,
    "fps":          30,
    "steps":        240,
    "seed":         0,

    # Polynomial: f(z) = z^n - e^(i*n*theta)
    "n":            3,           # polynomial degree (integer ≥ 2)
    "max_iter":     80,
    "epsilon":      1e-6,        # convergence threshold

    # Animation
    "theta_start":  0.0,         # starting rotation angle (radians)
    "theta_end":    None,        # None → auto (one full rotation = 2π/n)

    # Viewport
    "view_cx":      0.0,
    "view_cy":      0.0,
    "zoom_start":   1.6,         # half-width of view (complex plane units)
    "zoom_end":     1.6,         # set != zoom_start for zoom animation

    # Palette — divided into n equal bands, one per root
    "palette": [
        [0.0,    [10,  0,  40]],
        [0.10,   [60,  0, 160]],
        [0.20,   [0,   0, 255]],
        [0.28,   [255, 255, 255]],
        [0.33,   [0,  40,   0]],
        [0.44,   [0, 160,   0]],
        [0.55,   [80, 255,  80]],
        [0.62,   [255, 255, 255]],
        [0.66,   [80,   0,   0]],
        [0.78,   [200,  40,   0]],
        [0.90,   [255, 180,  40]],
        [1.0,    [255, 255, 255]],
    ],
    "bg_color":     [0, 0, 0],
    "gamma":        1.0,         # usually 1.0 for Newton — palette handles shading
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs  = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for c in range(3):
        lut[:, c] = np.clip(np.interp(xs, positions, colors[:, c]), 0, 255).astype(np.uint8)
    return lut


def _newton_frame(ZR, ZI, n, max_iter, epsilon2, theta):
    """Iterate Newton's method for z^n - e^(i*n*theta) = 0.

    Returns:
        root_idx: (H,W) int  — which root each pixel converged to
        iter_frac: (H,W) float — smooth convergence speed in [0,1]
    """
    Z = ZR.astype(np.complex128) + 1j * ZI.astype(np.complex128)
    c = np.exp(1j * n * theta)          # constant term of polynomial

    # Pre-compute root positions for this theta
    root_angles = theta + 2 * np.pi * np.arange(n) / n
    roots = np.exp(1j * root_angles)    # shape (n,)

    converged = np.zeros(Z.shape, dtype=bool)
    root_idx  = np.full(Z.shape, 0, dtype=np.intp)
    iter_conv = np.full(Z.shape, float(max_iter), dtype=np.float64)

    for it in range(1, max_iter + 1):
        # z^n and z^(n-1) via complex power
        Zn   = Z ** n
        Znm1 = Z ** (n - 1)

        # Newton step: z_new = z - (z^n - c) / (n * z^(n-1))
        denom  = n * Znm1
        # Avoid division by zero at z≈0
        safe   = np.abs(denom) > 1e-12
        step   = np.where(safe, (Zn - c) / np.where(safe, denom, 1.0 + 0j), 0.0 + 0j)
        Z_new  = Z - step

        # Convergence check
        newly = (np.abs(step) ** 2 < epsilon2) & ~converged
        if newly.any():
            # Which root is Z_new nearest to?
            # dist shape: (n, sum(newly))
            z_sub   = Z_new[newly]
            dists   = np.abs(z_sub[None, :] - roots[:, None])  # (n, m)
            nearest = dists.argmin(axis=0)
            root_idx[newly]  = nearest
            iter_conv[newly] = it
            converged[newly] = True

        Z = Z_new
        if converged.all():
            break

    # Unconverged: assign to nearest root from final Z position
    if (~converged).any():
        unc = ~converged
        z_sub = Z[unc]
        dists = np.abs(z_sub[None, :] - roots[:, None])
        root_idx[unc] = dists.argmin(axis=0)

    # Smooth iteration fraction per root band: [0,1] within [0, max_iter]
    iter_frac = iter_conv / max_iter   # 0=instant, 1=never (boundary)
    # Map to palette position within root's band
    band_width = 1.0 / n
    t = root_idx.astype(np.float64) * band_width + iter_frac * band_width * 0.98
    t = np.clip(t, 0.0, 1.0)
    return t


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    p      = {**DEFAULTS, **params}

    n         = int(p["n"])
    max_iter  = p["max_iter"]
    eps2      = p["epsilon"] ** 2
    lut       = _build_lut(p["palette"])

    theta_start = p["theta_start"]
    theta_end   = p["theta_end"]
    if theta_end is None:
        theta_end = theta_start + 2.0 * np.pi / n

    zoom_s = p["zoom_start"]
    zoom_e = p["zoom_end"]
    cx, cy = p["view_cx"], p["view_cy"]
    size   = p["size"]

    for frame_idx in range(p["steps"]):
        t = frame_idx / max(p["steps"] - 1, 1)
        theta = theta_start + t * (theta_end - theta_start)
        zoom  = zoom_s + t * (zoom_e - zoom_s)

        # Build pixel grid in complex plane
        xs = np.linspace(cx - zoom, cx + zoom, size)
        ys = np.linspace(cy - zoom, cy + zoom, size)
        ZR, ZI = np.meshgrid(xs, ys[::-1])  # flip y for screen coords

        col_t = _newton_frame(ZR, ZI, n, max_iter, eps2, theta)

        idx    = (col_t * 255).astype(np.intp).clip(0, 255)
        canvas = lut[idx]
        write_frame(frames_dir, frame_idx, canvas)

    return {
        "fps":      p["fps"],
        "n_frames": p["steps"],
        "width":    size,
        "height":   size,
        "seed":     p["seed"],
        "config":   p,
    }
