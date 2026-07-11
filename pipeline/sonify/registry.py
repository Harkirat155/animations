"""Recipe registry: which templates have a sonification recipe, and which
resolved-config keys define that template's audible "shape" (used to derive
the musical scale/root/tempo — see music.py). Additive only — a template with
no entry here simply stays silent by default, unchanged from today.

Pilot rollout order (staged, one at a time, listened to before the next):
harmonograph (built), then chladni, strange-attractor, reaction-diffusion,
flow-field.
"""
from __future__ import annotations

from typing import Callable

from .recipes import harmonograph

RECIPES: dict[str, Callable] = {
    "harmonograph": harmonograph.render,
}

STRUCTURAL_KEYS: dict[str, tuple[str, ...]] = {
    "harmonograph": ("freq_x1", "freq_x2", "freq_y1", "freq_y2", "damping", "phase_advance"),
}


def has_recipe(name: str) -> bool:
    return name in RECIPES
