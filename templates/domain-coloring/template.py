"""Domain coloring template.

Domain coloring is a technique for visualizing complex functions f: ℂ → ℂ.
Each pixel z = x + iy is colored by:
  • Hue    = arg(f(z)) / 2π  (phase angle → full color wheel)
  • Value  = log-normalized magnitude (creates contour rings at each decade)
  • Poles  → bright white spike; zeros → dark pit

This is NOT an escape-time fractal — every point gets a well-defined color
from a single function evaluation.  The result is a vivid kaleidoscope of
color that reveals the topological structure of the function: winding numbers,
residues, and Riemann sheets.

Supported function types (set via "func"):
  z_pow        f(z) = z^n                  (pinwheel with n petals)
  rational     f(z) = (z^p - 1)/(z^q + c) (zeros vs poles)
  blaschke     f(z) = Π (z - aᵢ)/(1 - āᵢz)  (unit-disk self-maps)
  trig         f(z) = sin(z), cos(z), etc.
  mobius       f(z) = (az + b)/(cz + d)    (circle-preserving maps)

Animation: the exponent n or parameter c sweeps over time, morphing the pattern.
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

    # View: real axis ∈ [re_min, re_max], imag axis ∈ [im_min, im_max]
    "re_min": -2.0,
    "re_max":  2.0,
    "im_min": -2.0,
    "im_max":  2.0,

    # Function type
    "func": "z_pow",   # "z_pow" | "rational" | "trig_sin" | "trig_cos" | "blaschke" | "mobius"

    # z^n: n sweeps from n_start to n_end (can be non-integer!)
    "n_start":   2.0,
    "n_end":     5.0,

    # rational: f(z) = (z^p - 1) / (z^q + c*(t parameter))
    "p_start":   3.0,
    "p_end":     3.0,
    "q_start":   2.0,
    "q_end":     2.0,
    "c_re_start": 0.5,
    "c_re_end":   0.5,
    "c_im_start": 0.0,
    "c_im_end":   1.0,

    # Rendering: magnitude contour rings
    "mag_rings":      True,   # show log-magnitude contour lines
    "ring_strength":  0.3,    # how dark the ring modulation is (0=off, 1=full)
    "saturation":     0.9,    # HSV saturation
    "phase_shift":    0.0,    # rotate hue wheel (0–1)

    # Zoom animation (optional)
    "zoom_end":  1.0,
    "zoom_cr":   0.0,
    "zoom_ci":   0.0,
}


def _domain_color(fz, saturation, ring_strength, phase_shift):
    """Convert complex array fz → RGB image array."""
    phase = (np.angle(fz) / (2 * np.pi) + phase_shift) % 1.0
    mag   = np.abs(fz)

    # Value: log-scale contour modulation
    log_mag = np.log(mag + 1e-30)
    if ring_strength > 0:
        # Rings at each log-decade
        ring = (log_mag % 1.0)           # 0..1 sawtooth at each factor-e step
        ring = 0.5 + 0.5 * np.cos(ring * 2 * np.pi)
        value = 0.5 + (1 - ring_strength) * 0.5 + ring_strength * ring * 0.5
    else:
        value = np.ones_like(phase) * 0.85

    # Near zeros: dark; near poles (very large mag): bright
    value = value * np.clip(mag / (mag + 1.0), 0.1, 1.0)
    value = np.clip(value, 0.0, 1.0)

    # HSV → RGB
    h = phase * 6.0
    s = np.full_like(h, saturation)
    v = value

    i = h.astype(int) % 6
    f = h - np.floor(h)
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))

    r = np.select([i==0, i==1, i==2, i==3, i==4, i==5], [v, q, p, p, t, v])
    g = np.select([i==0, i==1, i==2, i==3, i==4, i==5], [t, v, v, q, p, p])
    b = np.select([i==0, i==1, i==2, i==3, i==4, i==5], [p, p, t, v, v, q])

    rgb = np.stack([r, g, b], axis=-1)
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8)


def _evaluate_func(z, func, n, p, q, c):
    if func == "z_pow":
        # z^n for non-integer n: use polar form
        r   = np.abs(z)
        arg = np.angle(z)
        return (r ** n) * np.exp(1j * n * arg)

    elif func == "rational":
        num = z**int(round(p)) - 1.0
        den = z**int(round(q)) + c
        # Guard division by near-zero
        safe_den = np.where(np.abs(den) < 1e-10, 1e-10 * np.exp(1j*np.angle(den + 1e-10j)), den)
        return num / safe_den

    elif func == "trig_sin":
        return np.sin(z + c)

    elif func == "trig_cos":
        return np.cos(z * n)

    elif func == "blaschke":
        # Degree-3 Blaschke product with poles on the unit circle
        a0 = 0.5 * np.exp(1j * 2 * np.pi * 0 / 3 + 1j * np.real(c))
        a1 = 0.5 * np.exp(1j * 2 * np.pi * 1 / 3 + 1j * np.real(c))
        a2 = 0.5 * np.exp(1j * 2 * np.pi * 2 / 3 + 1j * np.real(c))
        B = ((z - a0) * (z - a1) * (z - a2)) / \
            ((1 - np.conj(a0)*z) * (1 - np.conj(a1)*z) * (1 - np.conj(a2)*z))
        return B

    elif func == "mobius":
        a, b, cv, d_coef = 1.0, c, -c, 1.0
        return (a*z + b) / (cv*z + d_coef)

    elif func == "exp_z":
        # e^z: hue = Im(z), rings encode exponential growth — rainbow wave bands
        return np.exp(z)

    elif func == "joukowski":
        # Joukowski map z + 1/z — conformal aerodynamic wing structure with 2 poles
        safe_z = np.where(np.abs(z) < 1e-8, 1e-8 * np.exp(1j * np.angle(z + 1e-8j)), z)
        return safe_z + 1.0 / safe_z

    elif func == "newton":
        # Newton fractal for z^n - 1; iteration reveals n basins of attraction
        deg = max(2, int(round(n)))
        w = z.copy()
        for _ in range(20):
            fw  = w**deg - 1.0
            dfw = deg * w**(deg - 1)
            safe_dfw = np.where(np.abs(dfw) < 1e-12, 1e-12, dfw)
            w = w - fw / safe_dfw
        return w

    else:  # default: identity
        return z


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    size = p["size"]

    # Build coordinate grid
    re_vals = np.linspace(p["re_min"], p["re_max"], size, dtype=np.float64)
    im_vals = np.linspace(p["im_min"], p["im_max"], size, dtype=np.float64)
    re_grid, im_grid = np.meshgrid(re_vals, im_vals)
    z_base = re_grid + 1j * im_grid

    frame_idx = 0
    for step in range(p["steps"]):
        if step < p["warmup"] or step % p["capture_every"] != 0:
            continue

        t = step / max(p["steps"] - 1, 1)

        # Zoom animation
        zoom = p["zoom_end"] ** t if p["zoom_end"] < 1 else p["zoom_end"] ** (1 - t)
        cr = p["zoom_cr"]; ci = p["zoom_ci"]
        re_min = cr + (p["re_min"] - cr) * zoom
        re_max = cr + (p["re_max"] - cr) * zoom
        im_min = ci + (p["im_min"] - ci) * zoom
        im_max = ci + (p["im_max"] - ci) * zoom
        re_vals_t = np.linspace(re_min, re_max, size, dtype=np.float64)
        im_vals_t = np.linspace(im_min, im_max, size, dtype=np.float64)
        re_g, im_g = np.meshgrid(re_vals_t, im_vals_t)
        z = re_g + 1j * im_g

        # Interpolate function parameters
        n = p["n_start"] + t * (p["n_end"] - p["n_start"])
        pp = p["p_start"] + t * (p["p_end"] - p["p_start"])
        q = p["q_start"] + t * (p["q_end"] - p["q_start"])
        c = complex(
            p["c_re_start"] + t * (p["c_re_end"] - p["c_re_start"]),
            p["c_im_start"] + t * (p["c_im_end"] - p["c_im_start"]),
        )
        phase_shift = t * 0.5  # slowly rotate hue over time

        fz = _evaluate_func(z, p["func"], n, pp, q, c)

        frame = _domain_color(fz, p["saturation"], p["ring_strength"],
                              p["phase_shift"] + phase_shift)
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
