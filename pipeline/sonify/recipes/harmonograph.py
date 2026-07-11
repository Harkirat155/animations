"""Harmonograph sonification: reuse the template's own oscillator math as the
audio oscillator bank directly — its params (freq_x*/y*, phase_*, damping)
already ARE additive-synthesis parameters, the most direct mapping of the 5
pilot families. Only `phase_offset` is frame-varying (carried in the trace);
everything else reads straight from the resolved config.
"""
from __future__ import annotations

import numpy as np

from .. import core, music


def render(trace, config: dict, musical: music.MusicalFrame, fps: float,
           duration_s: float, sr: int = core.SR) -> np.ndarray:
    n = int(duration_s * sr)
    tau = np.arange(n) / sr

    phase_offset = core.sample_trace(np.asarray(trace, dtype=np.float64), tau, fps)

    # Config frequencies (~2-7) are relative "shape" values, not literal Hz —
    # scale by the curated root before quantizing onto the scale, mirroring
    # the template's own x = f(freq_x1, freq_x2, ...) / y = f(freq_y1, ...).
    root = musical.root_hz
    fx1 = music.quantize_hz(config["freq_x1"] * root, musical)
    fx2 = music.quantize_hz(config["freq_x2"] * root, musical)
    fy1 = music.quantize_hz(config["freq_y1"] * root, musical)
    fy2 = music.quantize_hz(config["freq_y2"] * root, musical)

    audio_x = (
        config["amp_x1"] * np.sin(2 * np.pi * fx1 * tau + config["phase_x1"] + phase_offset)
        + config["amp_x2"] * np.sin(2 * np.pi * fx2 * tau + config["phase_x2"])
    )
    # Same asymmetric coupling as the template: phase_offset lands on x1 at
    # full weight and on y2 at 0.7x — reproducing its own rotation asymmetry.
    audio_y = (
        config["amp_y1"] * np.sin(2 * np.pi * fy1 * tau + config["phase_y1"])
        + config["amp_y2"] * np.sin(2 * np.pi * fy2 * tau + config["phase_y2"] + phase_offset * 0.7)
    )
    signal = 0.5 * audio_x + 0.5 * audio_y

    # Rhythmic tremolo gate synced to the tempo grid (the "rhythmic, not a
    # free drone" design constraint) without touching the harmonograph-native
    # pitch content above. `damping` (how tightly the visual figure spirals
    # in) reuses as how punchy vs. sustained each pulse feels.
    grid_s = musical.grid_s
    phase_in_grid = (tau % grid_s) / grid_s
    damping = float(config.get("damping", 0.003))
    decay_k = float(np.clip(0.02 / max(damping, 1e-4), 2.0, 12.0))
    gate = 0.35 + 0.65 * np.exp(-phase_in_grid * decay_k)
    signal = signal * gate

    # Click-free start/end.
    fade_n = min(n, int(0.02 * sr))
    if fade_n > 0:
        fade = np.ones(n)
        fade[:fade_n] = np.linspace(0.0, 1.0, fade_n)
        fade[-fade_n:] = np.linspace(1.0, 0.0, fade_n)
        signal = signal * fade

    return signal
