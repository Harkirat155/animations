"""Strange-attractor template: Clifford, De Jong, Lorenz, Hopalong, Halvorsen, Rossler.

An iterated-function system that produces fractal point clouds with intricate
density gradients.  Small parameter changes morph the form between wildly
different shapes — spirals, knots, spider webs, explosions — making it ideal
for slow-morph animations.

Rendering: N points iterated forward from a random seed, scattered into an
HDR accumulation buffer.  Density normalization yields natural glow at
high-traffic regions.  Types supported:

  clifford:  x' = sin(a*y) + c*cos(a*x)
             y' = sin(b*x) + d*cos(b*y)

  dejong:    x' = sin(a*y) - cos(b*x)
             y' = sin(c*x) - cos(d*y)

  lorenz:    dx/dt = a*(y-x), dy/dt = x*(b-z)-y, dz/dt = x*y-c*z
             [a=sigma, b=rho, c=beta, d=view_angle]

  hopalong:  x' = y - sign(x)*sqrt(|b*x-c|)   (Martin's Hopalong)
             y' = a - x

  halvorsen: dx/dt = -a*x - 4*y - 4*z - y²   (cyclic 3-fold attractor)
             dy/dt = -a*y - 4*z - 4*x - z²
             dz/dt = -a*z - 4*x - 4*y - x²
             [a=damping (~1.89), d=view_angle around Z axis]

  rossler:   dx/dt = -(y+z), dy/dt = x+a*y, dz/dt = b+z*(x-c)
             [a,b,c=standard Rossler params, d=view_angle]

Animation: parameters a,b,c,d interpolate linearly between `params_start`
and `params_end` across the clip, so the attractor morphs continuously.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.encode import write_frame

DEFAULTS = {
    "size":      512,
    "seed":      0,
    "type":      "clifford",  # "clifford" | "dejong"
    # Vectorised parallel chains: n_chains chains × chain_len steps = total scatter pts
    # Keep n_chains high (≥200) so numpy overhead beats Python loop overhead.
    "n_chains":  800,
    "chain_len": 500,         # steps per chain → 400k total pts
    "fps":       30,
    "steps":     240,         # frames (240 @ 30fps = 8s)
    "capture_every": 1,
    "warmup":    0,

    # Attractor parameters at frame 0 and frame N-1
    "params_start": {"a": -1.7, "b":  1.3, "c": -0.1, "d": -1.2},
    "params_end":   {"a": -1.4, "b":  1.6, "c":  0.5, "d": -0.9},

    # Discard first `burn_in` numpy steps per chain (attractor transient)
    "burn_in":   200,

    # Visual
    "bg_color":    [4,   3,  14],
    "palette": [
        [0.0,  [10,   5,  60]],
        [0.2,  [60,   0, 180]],
        [0.5,  [180,  0, 220]],
        [0.75, [220, 100, 255]],
        [1.0,  [255, 240, 255]],
    ],
    "gamma":       0.45,      # gamma correction for density map (< 0.5 → bright faint regions)
    "density_clip": 0.995,    # percentile to clip HDR accumulation before tonemapping
}


def _build_lut(palette: list) -> np.ndarray:
    positions = np.array([p[0] for p in palette])
    colors    = np.array([p[1] for p in palette], dtype=float)
    xs = np.linspace(0.0, 1.0, 256)
    lut = np.empty((256, 3), dtype=np.uint8)
    for c in range(3):
        lut[:, c] = np.clip(np.interp(xs, positions, colors[:, c]), 0, 255).astype(np.uint8)
    return lut


def _collect_attractor(a, b, c, d, attractor_type: str,
                       n_chains: int, chain_len: int, burn_in: int,
                       rng) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised multi-chain collection.

    Runs `n_chains` independent chains in parallel using numpy.
    burn_in steps are discarded to land on the attractor, then chain_len
    steps are recorded.  This is ~n_chains× faster than one Python loop.
    """
    x = rng.uniform(-0.5, 0.5, n_chains)
    y = rng.uniform(-0.5, 0.5, n_chains)

    if attractor_type == "clifford":
        def step(x, y):
            return np.sin(a * y) + c * np.cos(a * x), np.sin(b * x) + d * np.cos(b * y)

        for _ in range(burn_in):
            x, y = step(x, y)

        xs_list = np.empty((chain_len, n_chains))
        ys_list = np.empty((chain_len, n_chains))
        for i in range(chain_len):
            x, y = step(x, y)
            xs_list[i] = x
            ys_list[i] = y
        return xs_list.ravel(), ys_list.ravel()

    elif attractor_type == "dejong":
        def step(x, y):
            return np.sin(a * y) - np.cos(b * x), np.sin(c * x) - np.cos(d * y)

        for _ in range(burn_in):
            x, y = step(x, y)

        xs_list = np.empty((chain_len, n_chains))
        ys_list = np.empty((chain_len, n_chains))
        for i in range(chain_len):
            x, y = step(x, y)
            xs_list[i] = x
            ys_list[i] = y
        return xs_list.ravel(), ys_list.ravel()

    elif attractor_type == "henon":
        # Hénon map: x' = 1 - a*x² + y,  y' = b*x
        # Classic: a=1.4, b=0.3 → banana-shaped strange attractor
        def step_hen(x, y):
            return 1.0 - a * x * x + y, b * x

        x = rng.uniform(-0.5, 0.5, n_chains)
        y = rng.uniform(-0.5, 0.5, n_chains)
        for _ in range(burn_in):
            x, y = step_hen(x, y)
            big = np.abs(x) + np.abs(y) > 20.0
            if big.any():
                x[big] = rng.uniform(-0.5, 0.5, big.sum())
                y[big] = rng.uniform(-0.5, 0.5, big.sum())

        xs_list = np.empty((chain_len, n_chains))
        ys_list = np.empty((chain_len, n_chains))
        for i in range(chain_len):
            x, y = step_hen(x, y)
            xs_list[i] = x
            ys_list[i] = y
        return xs_list.ravel(), ys_list.ravel()

    elif attractor_type == "tinkerbell":
        # Tinkerbell map:
        # x' = x² - y² + a*x + b*y
        # y' = 2*x*y + c*x + d*y
        # Initialize near origin (map diverges for many initial conditions)
        x = rng.uniform(-0.1, 0.1, n_chains)
        y = rng.uniform(-0.1, 0.1, n_chains)

        def step_tb(x, y):
            x_new = x * x - y * y + a * x + b * y
            y_new = 2.0 * x * y + c * x + d * y
            return x_new, y_new

        for _ in range(burn_in):
            x, y = step_tb(x, y)
            # Reset diverged chains to the attractor region
            big = np.abs(x) + np.abs(y) > 10.0
            if big.any():
                x[big] = rng.uniform(-0.1, 0.1, big.sum())
                y[big] = rng.uniform(-0.1, 0.1, big.sum())

        xs_list = np.empty((chain_len, n_chains))
        ys_list = np.empty((chain_len, n_chains))
        for i in range(chain_len):
            x, y = step_tb(x, y)
            xs_list[i] = x
            ys_list[i] = y
        return xs_list.ravel(), ys_list.ravel()

    elif attractor_type == "bedhead":
        # Bedhead attractor:
        # x' = sin(x*y/b) * y + cos(a*x - y)
        # y' = x + sin(y)/b
        def step_bed(x, y):
            x_new = np.sin(x * y / b) * y + np.cos(a * x - y)
            y_new = x + np.sin(y) / b
            return x_new, y_new

        for _ in range(burn_in):
            x, y = step_bed(x, y)

        xs_list = np.empty((chain_len, n_chains))
        ys_list = np.empty((chain_len, n_chains))
        for i in range(chain_len):
            x, y = step_bed(x, y)
            xs_list[i] = x
            ys_list[i] = y
        return xs_list.ravel(), ys_list.ravel()

    elif attractor_type == "hopalong":
        # Martin's Hopalong (Pickover) map:
        # x' = y - sign(x) * sqrt(|b*x - c|)
        # y' = a - x
        def step_hop(x, y):
            return y - np.sign(x) * np.sqrt(np.abs(b * x - c)), a - x

        for _ in range(burn_in):
            x, y = step_hop(x, y)

        xs_list = np.empty((chain_len, n_chains))
        ys_list = np.empty((chain_len, n_chains))
        for i in range(chain_len):
            x, y = step_hop(x, y)
            xs_list[i] = x
            ys_list[i] = y
        return xs_list.ravel(), ys_list.ravel()

    elif attractor_type == "halvorsen":
        # Halvorsen cyclically symmetric attractor
        # dx/dt = -a*x - 4*y - 4*z - y²
        # dy/dt = -a*y - 4*z - 4*x - z²
        # dz/dt = -a*z - 4*x - 4*y - x²
        # a ≈ 1.89 is classic chaotic regime; d = view_angle around Z axis
        dt = 0.005
        av, theta = a, d
        xv = rng.uniform(-1.0, 1.0, n_chains)
        yv = rng.uniform(-1.0, 1.0, n_chains)
        zv = rng.uniform(-1.0, 1.0, n_chains)

        for _ in range(burn_in):
            dxv = -av*xv - 4*yv - 4*zv - yv*yv
            dyv = -av*yv - 4*zv - 4*xv - zv*zv
            dzv = -av*zv - 4*xv - 4*yv - xv*xv
            xv += dxv*dt; yv += dyv*dt; zv += dzv*dt

        xs3 = np.empty((chain_len, n_chains))
        ys3 = np.empty((chain_len, n_chains))
        for i in range(chain_len):
            dxv = -av*xv - 4*yv - 4*zv - yv*yv
            dyv = -av*yv - 4*zv - 4*xv - zv*zv
            dzv = -av*zv - 4*xv - 4*yv - xv*xv
            xv += dxv*dt; yv += dyv*dt; zv += dzv*dt
            xs3[i] = xv
            ys3[i] = yv

        # Project: rotate x,y by theta to get interesting view
        xr = xs3.ravel(); yr = ys3.ravel()
        px = xr * np.cos(theta) - yr * np.sin(theta)
        py = xr * np.sin(theta) + yr * np.cos(theta)
        return px, py

    elif attractor_type == "rossler":
        # Rossler attractor: dx=-(y+z), dy=x+a*y, dz=b+z*(x-c)
        # Classic: a=0.2, b=0.2, c=5.7 → single-banded spiral
        # d = view_angle around Z axis for projection
        dt = 0.01
        av, bv, cv, theta = a, b, c, d
        xv = rng.uniform(-5.0, 5.0, n_chains)
        yv = rng.uniform(-5.0, 5.0, n_chains)
        zv = rng.uniform(0.0, 5.0, n_chains)

        for _ in range(burn_in):
            dxv = -(yv + zv)
            dyv = xv + av * yv
            dzv = bv + zv * (xv - cv)
            xv += dxv*dt; yv += dyv*dt; zv += dzv*dt

        xs3 = np.empty((chain_len, n_chains))
        ys3 = np.empty((chain_len, n_chains))
        for i in range(chain_len):
            dxv = -(yv + zv)
            dyv = xv + av * yv
            dzv = bv + zv * (xv - cv)
            xv += dxv*dt; yv += dyv*dt; zv += dzv*dt
            xs3[i] = xv
            ys3[i] = yv

        xr = xs3.ravel(); yr = ys3.ravel()
        px = xr * np.cos(theta) - yr * np.sin(theta)
        py = xr * np.sin(theta) + yr * np.cos(theta)
        return px, py

    elif attractor_type == "aizawa":
        # Aizawa attractor (toroidal/mushroom shape)
        # dx = (z-b)x - d*y,  dy = d*x + (z-b)y,  dz = c + a*z - z³/3 - (x²+y²)(1+e*z) + f*z*x³
        # Params: a,b,c map to physical a,b,c (d fixed=3.5, e=0.25, f=0.1)
        # Here: param a=a_phys, b=b_phys, c=c_phys, d=view_angle
        dt = 0.01
        a_p, b_p, c_p, theta = a, b, c, d
        d_p, e_p, f_p = 3.5, 0.25, 0.1
        xv = rng.uniform(-0.5, 0.5, n_chains)
        yv = rng.uniform(-0.5, 0.5, n_chains)
        zv = rng.uniform(-0.5, 0.5, n_chains)

        for _ in range(burn_in):
            dxv = (zv - b_p) * xv - d_p * yv
            dyv = d_p * xv + (zv - b_p) * yv
            dzv = c_p + a_p * zv - zv**3/3 - (xv**2 + yv**2) * (1 + e_p * zv) + f_p * zv * xv**3
            xv += dxv*dt; yv += dyv*dt; zv += dzv*dt

        xs3 = np.empty((chain_len, n_chains))
        ys3 = np.empty((chain_len, n_chains))
        for i in range(chain_len):
            dxv = (zv - b_p) * xv - d_p * yv
            dyv = d_p * xv + (zv - b_p) * yv
            dzv = c_p + a_p * zv - zv**3/3 - (xv**2 + yv**2) * (1 + e_p * zv) + f_p * zv * xv**3
            xv += dxv*dt; yv += dyv*dt; zv += dzv*dt
            xs3[i] = xv; ys3[i] = yv

        xr = xs3.ravel(); yr = ys3.ravel()
        px = xr * np.cos(theta) - yr * np.sin(theta)
        py = xr * np.sin(theta) + yr * np.cos(theta)
        return px, py

    else:  # lorenz — a=sigma, b=rho, c=beta, d=view_angle
        dt = 0.01
        sigma, rho, beta, theta = a, b, c, d
        xv = rng.uniform(-10.0, 10.0, n_chains)
        yv = rng.uniform(-10.0, 10.0, n_chains)
        zv = rng.uniform(20.0, 30.0, n_chains)

        for _ in range(burn_in):
            dx = sigma * (yv - xv)
            dy = xv * (rho - zv) - yv
            dz = xv * yv - beta * zv
            xv += dx * dt; yv += dy * dt; zv += dz * dt

        xs3 = np.empty((chain_len, n_chains))
        ys3 = np.empty((chain_len, n_chains))
        zs3 = np.empty((chain_len, n_chains))
        for i in range(chain_len):
            dx = sigma * (yv - xv)
            dy = xv * (rho - zv) - yv
            dz = xv * yv - beta * zv
            xv += dx * dt; yv += dy * dt; zv += dz * dt
            xs3[i] = xv; ys3[i] = yv; zs3[i] = zv

        xr = xs3.ravel(); yr = ys3.ravel(); zr = zs3.ravel()
        px = xr * np.cos(theta) - yr * np.sin(theta)
        py = zr
        return px, py


def _render_attractor(xs, ys, size, lut, bg, gamma, density_clip):
    n = size
    # Normalize to canvas with a small margin
    margin = 0.04
    lo, hi = xs.min(), xs.max()
    span_x = hi - lo or 1.0
    lo_y, hi_y = ys.min(), ys.max()
    span_y = hi_y - lo_y or 1.0

    px = ((xs - lo) / span_x * (1 - 2 * margin) + margin) * (n - 1)
    py = ((ys - lo_y) / span_y * (1 - 2 * margin) + margin) * (n - 1)
    pxi = px.astype(np.intp).clip(0, n - 1)
    pyi = py.astype(np.intp).clip(0, n - 1)

    # Density accumulation
    density = np.zeros((n, n), dtype=np.float64)
    np.add.at(density, (pyi, pxi), 1.0)

    # Tonemap: gamma on normalized density, clamped at percentile
    clip_val = np.percentile(density[density > 0], density_clip * 100) if density.max() > 0 else 1.0
    density = np.clip(density / max(clip_val, 1e-9), 0.0, 1.0)
    density = np.power(density, gamma)  # gamma lift faint traces

    # Map density to palette
    idx    = (density * 255).astype(np.intp).clip(0, 255)
    canvas = lut[idx].astype(np.float64) / 255.0

    # Blend with bg where density is zero
    alpha  = density[:, :, None]
    canvas = canvas * alpha + bg * (1 - alpha)
    return (canvas * 255.0).astype(np.uint8)


def generate_frames(params: dict, frames_dir: str | Path) -> dict:
    params = params or {}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown param keys: {sorted(unknown)}")
    p = {**DEFAULTS, **params}

    # Nested dict merge for params_start / params_end
    ps = {**DEFAULTS["params_start"], **p["params_start"]}
    pe = {**DEFAULTS["params_end"],   **p["params_end"]}

    n      = p["size"]
    lut    = _build_lut(p["palette"])
    bg     = np.array(p["bg_color"], dtype=np.float64) / 255.0
    rng    = np.random.default_rng(p["seed"])

    frame_idx = 0

    for step in range(p["steps"]):
        t = step / max(p["steps"] - 1, 1)
        a = ps["a"] + t * (pe["a"] - ps["a"])
        b = ps["b"] + t * (pe["b"] - ps["b"])
        c = ps["c"] + t * (pe["c"] - ps["c"])
        d = ps["d"] + t * (pe["d"] - ps["d"])

        xs, ys = _collect_attractor(a, b, c, d, p["type"],
                                    p["n_chains"], p["chain_len"],
                                    p["burn_in"], rng)

        if step >= p["warmup"] and step % p["capture_every"] == 0:
            frame = _render_attractor(xs, ys, n, lut, bg,
                                      p["gamma"], p["density_clip"])
            write_frame(frames_dir, frame_idx, frame)
            frame_idx += 1

    return {
        "fps":      p["fps"],
        "n_frames": frame_idx,
        "width":    n,
        "height":   n,
        "seed":     p["seed"],
        "config":   p,
    }
