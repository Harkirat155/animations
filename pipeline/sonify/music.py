"""Curated musical frame derivation: scale/root/tempo/subdivision, hashed
deterministically from a recipe-declared subset of a render's resolved
config — never from info["seed"]. Verified against the real preset JSONs:
chladni, harmonograph, and most strange-attractor presets pin seed=0 and vary
only via shape params, so hashing the seed alone would put every preset of
those templates in the same key/tempo. Hashing the structural config
generalizes correctly (it reduces to seed-hashing for reaction-diffusion /
flow-field, where seed does vary).

This is a curated guardrail, not the primary driver of the sound — each
recipe's own trace data (the template's simulation state) decides which
scale degree/timing fires; this module only decides which scale/root/tempo
those choices land on, so results stay musical instead of atonal.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass

import numpy as np

SCALES = {
    "major_pentatonic": (0, 2, 4, 7, 9),
    "minor_pentatonic": (0, 3, 5, 7, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "whole_tone": (0, 2, 4, 6, 8, 10),
}

# Bass-register roots (~C2..Bb2); recipes shift octaves as needed for their range.
ROOTS_HZ = {
    "C": 65.41, "D": 73.42, "Eb": 77.78, "F": 87.31,
    "G": 98.00, "A": 110.0, "Bb": 116.54,
}

TEMPOS_BPM = (72, 84, 96, 108, 120, 132)
SUBDIVISIONS = (2, 3, 4)  # notes per beat on the tempo grid


@dataclass(frozen=True)
class MusicalFrame:
    root_hz: float
    scale_semitones: tuple[int, ...]
    bpm: float
    subdivision: int

    @property
    def beat_s(self) -> float:
        return 60.0 / self.bpm

    @property
    def grid_s(self) -> float:
        return self.beat_s / self.subdivision


def musical_frame_for_config(
    template_name: str, config: dict, structural_keys: tuple[str, ...]
) -> MusicalFrame:
    """Derive a deterministic MusicalFrame from the params that define this
    template's audible "shape" (recipe-declared `structural_keys`), not from
    a seed that may not even vary across that template's presets.
    """
    subset = {k: config[k] for k in structural_keys if k in config}
    payload = json.dumps({"template": template_name, "subset": subset}, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode()).digest()
    seed_int = int.from_bytes(digest[:8], "big")
    rnd = random.Random(seed_int)  # stdlib Random — must never perturb the template's own np.random stream
    scale_name = rnd.choice(sorted(SCALES))
    root_name = rnd.choice(sorted(ROOTS_HZ))
    bpm = rnd.choice(TEMPOS_BPM)
    subdivision = rnd.choice(SUBDIVISIONS)
    return MusicalFrame(
        root_hz=ROOTS_HZ[root_name],
        scale_semitones=SCALES[scale_name],
        bpm=float(bpm),
        subdivision=subdivision,
    )


def quantize_hz(hz: float, frame: MusicalFrame, octave_span: int = 4) -> float:
    """Snap `hz` to the nearest pitch in `frame`'s scale relative to
    `frame.root_hz`, searched from one octave below the root up through
    `octave_span` octaves above it.
    """
    if hz <= 0:
        return frame.root_hz
    best_hz, best_dist = frame.root_hz, math.inf
    for octave in range(-1, octave_span + 1):
        octave_root = frame.root_hz * (2.0 ** octave)
        for semitone in frame.scale_semitones:
            candidate = octave_root * (2.0 ** (semitone / 12.0))
            dist = abs(math.log2(candidate / hz))
            if dist < best_dist:
                best_dist, best_hz = dist, candidate
    return best_hz


def grid_times(duration_s: float, frame: MusicalFrame) -> np.ndarray:
    """Tempo-grid tick times covering [0, duration_s)."""
    return np.arange(0.0, duration_s, frame.grid_s)
