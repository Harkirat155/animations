"""Declarative UI schema for the hero templates the composer exposes.

Templates have no formal parameter schema of their own — `DEFAULTS` dicts with
inline comments only (see templates/*/template.py). This module is the additive
layer that turns each hero template's parameters into something a UI can render:
labeled fields with types/ranges/enum choices, grouping, conditional visibility,
and how to build a cheap preview from a user's chosen params. It never modifies
templates/*/template.py.

Two empirical facts (measured via a throwaway timing spike, see
ideas/backlog.md history / the composer plan) drive `preview_overrides`:

  - mandelbrot, chladni, domain-coloring, voronoi, harmonograph and
    strange-attractor compute each frame independently from a closed-form
    `t = step / (steps - 1)` — nothing carries over between frames. So
    `steps=1, warmup=0` renders exactly the frame at t=0 (the "start" of
    each template's *_start/*_end params) in well under 0.2s, with zero
    need for a timeline scrubber in v1.
  - reaction-diffusion and flow-field are genuinely sequential (a PDE grid /
    accumulating particle trails) — there is no way to jump to a
    representative frame without running the simulation up to it. Their
    `preview_overrides` shrink grid size but preserve step counts close to
    the original, since that's physics time, not resolution time.

A handful of DEFAULTS keys only affect how the pattern *morphs across a full
video* (e.g. mandelbrot's `mode`, chladni's `m_end`/`n_end`, harmonograph's
`detune_*`/`phase_advance`, voronoi's `hue_cycle`) and are invisible at t=0.
Those are kept out of the schema (or pushed to the "advanced" group with a
note) rather than presented as prominent dials that appear to do nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Group = str  # "shape" | "color" | "advanced"


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str  # "int" | "float" | "bool" | "enum" | "gradient" | "swatch" | "seed"
    default: Any
    group: Group = "shape"
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: tuple[str, ...] | None = None
    unit: str | None = None
    help: str | None = None
    visible_if: tuple[str, Any] | None = None  # (other_field_key, required_value)


@dataclass(frozen=True)
class TemplateSchema:
    name: str            # folder name under templates/
    label: str            # display name for the gallery
    blurb: str            # one-line gallery-card description
    color_paradigm: str   # descriptive label only — widget choice is per-field via Field.kind
    fields: tuple[Field, ...]
    preview_overrides: dict
    # Optional: {switch_field_key: {switch_value: {param_key: {default,min,max,fixed?}}}}
    # for fields whose valid range depends on another field's value (only
    # strange-attractor needs this today — see ATTRACTOR_PARAM_SPECS below).
    type_dependent: dict[str, dict[str, dict]] | None = None

    def defaults(self) -> dict:
        return {f.key: f.default for f in self.fields}


def _gradient(key: str, label: str, default: list, **kw) -> Field:
    return Field(key, label, "gradient", default, group="color", **kw)


def _swatch(key: str, label: str, default: list, **kw) -> Field:
    return Field(key, label, "swatch", default, group="color", **kw)


# strange-attractor's a/b/c/d are not one generic [-3,3] range — each attractor
# `type` uses them for a physically different equation, at a different scale
# (Lorenz needs sigma~10/rho~28; Halvorsen's a/b/c are one damping value
# replicated three times; several types don't use c/d at all). Grounded in the
# real curated presets (ideas/params/sa-*.json), not guessed — an earlier,
# generic single-range version of this schema produced a near-blank preview
# for Lorenz because Clifford-scaled defaults (-1.7..1.3) are nowhere near a
# real Lorenz attractor's basin. `fixed=True` means the frontend should hide
# the slider — the equation doesn't read that parameter for this type.
ATTRACTOR_PARAM_SPECS: dict[str, dict[str, dict]] = {
    "clifford":   {"a": {"default": -1.7, "min": -2.2, "max": 2.2},
                   "b": {"default": 1.3, "min": -2.2, "max": 2.2},
                   "c": {"default": -0.1, "min": -2.2, "max": 2.2},
                   "d": {"default": -1.2, "min": -2.2, "max": 2.2}},
    "dejong":     {"a": {"default": -2.0, "min": -2.7, "max": 2.7},
                   "b": {"default": -2.0, "min": -2.7, "max": 2.7},
                   "c": {"default": -1.2, "min": -2.7, "max": 2.7},
                   "d": {"default": 2.0, "min": -2.7, "max": 2.7}},
    "henon":      {"a": {"default": 1.4, "min": 0.8, "max": 1.5},
                   "b": {"default": 0.3, "min": -0.5, "max": 0.5},
                   "c": {"default": 0.0, "min": 0.0, "max": 0.0, "fixed": True},
                   "d": {"default": 0.0, "min": 0.0, "max": 0.0, "fixed": True}},
    "tinkerbell": {"a": {"default": 0.9, "min": 0.5, "max": 1.2},
                   "b": {"default": -0.6, "min": -1.0, "max": -0.2},
                   "c": {"default": 2.0, "min": 1.0, "max": 3.0},
                   "d": {"default": 0.5, "min": 0.0, "max": 1.0}},
    "bedhead":    {"a": {"default": -0.81, "min": -1.5, "max": 1.5},
                   "b": {"default": 75.0, "min": 10.0, "max": 150.0},
                   "c": {"default": 0.0, "min": 0.0, "max": 0.0, "fixed": True},
                   "d": {"default": 0.0, "min": 0.0, "max": 0.0, "fixed": True}},
    "hopalong":   {"a": {"default": 2.0, "min": -5.0, "max": 10.0},
                   "b": {"default": 1.0, "min": 0.0, "max": 2.0},
                   "c": {"default": 0.0, "min": -1.0, "max": 1.0},
                   "d": {"default": 0.0, "min": 0.0, "max": 0.0, "fixed": True}},
    "halvorsen":  {"a": {"default": 1.89, "min": 1.0, "max": 3.0},
                   "b": {"default": 1.89, "min": 1.0, "max": 3.0},
                   "c": {"default": 1.89, "min": 1.0, "max": 3.0},
                   "d": {"default": 0.0, "min": 0.0, "max": 6.283, "label": "View angle"}},
    "rossler":    {"a": {"default": 0.2, "min": 0.0, "max": 0.5},
                   "b": {"default": 0.2, "min": 0.0, "max": 0.5},
                   "c": {"default": 5.7, "min": 1.0, "max": 20.0},
                   "d": {"default": 0.0, "min": 0.0, "max": 6.283, "label": "View angle"}},
    "aizawa":     {"a": {"default": 0.95, "min": 0.7, "max": 1.2},
                   "b": {"default": 0.7, "min": 0.4, "max": 1.0},
                   "c": {"default": 0.6, "min": 0.3, "max": 0.9},
                   "d": {"default": 0.0, "min": 0.0, "max": 6.283, "label": "View angle"}},
    "lorenz":     {"a": {"default": 10.0, "min": 5.0, "max": 15.0, "label": "Sigma"},
                   "b": {"default": 28.0, "min": 15.0, "max": 40.0, "label": "Rho"},
                   "c": {"default": 2.667, "min": 1.0, "max": 5.0, "label": "Beta"},
                   "d": {"default": 0.0, "min": 0.0, "max": 6.283, "label": "View angle"}},
}


TEMPLATES: dict[str, TemplateSchema] = {

    "mandelbrot": TemplateSchema(
        name="mandelbrot", label="Mandelbrot",
        blurb="The classic escape-time fractal, with Burning Ship and Tricorn variants.",
        color_paradigm="gradient palette + a discrete interior color",
        fields=(
            Field("fractal", "Fractal", "enum", "mandelbrot",
                  choices=("mandelbrot", "burning_ship", "tricorn"), group="shape"),
            Field("zoom_cx", "View center (real)", "float", -0.7269, min=-2.0, max=2.0, step=0.0001, group="shape"),
            Field("zoom_cy", "View center (imag)", "float", 0.1889, min=-2.0, max=2.0, step=0.0001, group="shape"),
            Field("zoom_start", "Zoom level", "float", 1.5, min=0.02, max=2.5, step=0.01, group="shape",
                  help="Smaller = more zoomed in."),
            _gradient("palette", "Palette", [
                [0.0, [0, 0, 0]], [0.08, [0, 10, 50]], [0.2, [0, 60, 180]],
                [0.38, [0, 180, 220]], [0.55, [180, 240, 255]], [0.70, [255, 200, 60]],
                [0.84, [255, 40, 0]], [1.0, [255, 255, 255]],
            ]),
            _swatch("interior_color", "Interior color", [0, 0, 0]),
            Field("hue_shift", "Hue shift", "float", 0.0, min=0.0, max=1.0, step=0.01, group="color"),
            Field("max_iter", "Detail (max iterations)", "int", 512, min=50, max=1000, step=10, group="advanced"),
            Field("cycle_len", "Color band frequency", "float", 32.0, min=4.0, max=128.0, step=1.0, group="advanced"),
            Field("mode", "Animation mode", "enum", "zoom", choices=("zoom", "hue", "orbit"), group="advanced",
                  help="Only affects how the full video evolves — this still preview looks the same across modes."),
        ),
        # max_iter is NOT overridden — it's a user-exposed slider (50-1000);
        # hardcoding it here would make that control a no-op in the preview.
        # Measured: even max_iter=1000 at size=320 renders in ~0.48s.
        preview_overrides={"steps": 1, "warmup": 0, "capture_every": 1, "size": 320},
    ),

    "reaction-diffusion": TemplateSchema(
        name="reaction-diffusion", label="Reaction-Diffusion",
        blurb="Gray-Scott chemistry — coral, spots, mazes and mitosis-like organic growth.",
        color_paradigm="gradient palette",
        fields=(
            Field("feed", "Feed rate", "float", 0.0367, min=0.01, max=0.09, step=0.0005, group="shape",
                  help="Small changes here dramatically change the pattern family."),
            Field("kill", "Kill rate", "float", 0.0649, min=0.03, max=0.07, step=0.0005, group="shape"),
            Field("seed_pattern", "Seed pattern", "enum", "random", choices=("random", "center"), group="shape"),
            Field("n_spots", "Seed spot count", "int", 14, min=1, max=150, step=1, group="shape",
                  visible_if=("seed_pattern", "random")),
            _gradient("palette", "Palette", [
                [0.0, [4, 8, 28]], [0.4, [10, 60, 120]], [0.6, [30, 160, 200]],
                [0.8, [180, 230, 240]], [1.0, [255, 255, 255]],
            ]),
            Field("v_max", "Brightness ceiling", "float", 0.40, min=0.2, max=0.6, step=0.01, group="advanced",
                  help="Maps the chemical field into the palette; tune per feed/kill regime."),
            Field("Dv", "Diffusion rate (V)", "float", 0.5, min=0.3, max=0.7, step=0.01, group="advanced",
                  help="Du and dt are fixed — keep Du*dt < ~1.25 for a stable simulation."),
        ),
        # warmup=600 (the template's own default) only clears the boring
        # near-black opening — it does NOT mean "bloomed." Gray-Scott
        # mitosis-style growth multiplies spots outward over the FULL
        # 9000-step production render; at 600 steps the pattern is still
        # just 1-2 barely-visible dots (confirmed by actually looking at
        # the image, not just checking it's non-empty and fast). warmup=3000
        # is the earliest point it reads as a recognizable multiplying-spot
        # pattern rather than "is this broken?" — at the cost of being the
        # one hero template whose preview takes ~2.3s instead of <1s. Sized
        # down to 160 (from 256) to partially offset that extra warmup cost.
        preview_overrides={"steps": 3001, "warmup": 3000, "capture_every": 1, "size": 160},
    ),

    "strange-attractor": TemplateSchema(
        name="strange-attractor", label="Strange Attractor",
        blurb="Clifford, De Jong, Lorenz and 7 more chaotic point-cloud attractors.",
        color_paradigm="gradient palette + a discrete background color",
        fields=(
            Field("type", "Attractor type", "enum", "clifford", group="shape", choices=(
                "clifford", "dejong", "henon", "tinkerbell", "bedhead", "hopalong",
                "halvorsen", "rossler", "aizawa", "lorenz",
            )),
            # a/b/c/d have no single valid range across types — see ATTRACTOR_PARAM_SPECS
            # and TemplateSchema.type_dependent. Defaults/min/max here are Clifford's
            # (the default `type`); the frontend must re-read type_dependent and reset
            # these sliders whenever `type` changes, and the backend re-validates
            # against the submitted `type`, not these fallback bounds.
            Field("params_start.a", "Parameter a", "float", -1.7, min=-2.2, max=2.2, step=0.01, group="shape"),
            Field("params_start.b", "Parameter b", "float", 1.3, min=-2.2, max=2.2, step=0.01, group="shape"),
            Field("params_start.c", "Parameter c", "float", -0.1, min=-2.2, max=2.2, step=0.01, group="shape"),
            Field("params_start.d", "Parameter d", "float", -1.2, min=-2.2, max=2.2, step=0.01, group="shape",
                  help="a-d define the attractor's shape; small changes can morph it completely."),
            _gradient("palette", "Palette", [
                [0.0, [10, 5, 60]], [0.2, [60, 0, 180]], [0.5, [180, 0, 220]],
                [0.75, [220, 100, 255]], [1.0, [255, 240, 255]],
            ]),
            _swatch("bg_color", "Background", [4, 3, 14]),
            Field("gamma", "Glow gamma", "float", 0.45, min=0.2, max=0.8, step=0.01, group="color",
                  help="Lower = brighter faint traces."),
            Field("n_chains", "Detail (chain count)", "int", 800, min=200, max=2000, step=100, group="advanced"),
        ),
        preview_overrides={"steps": 1, "warmup": 0, "capture_every": 1, "size": 320},
        type_dependent={"type": ATTRACTOR_PARAM_SPECS},
    ),

    "flow-field": TemplateSchema(
        name="flow-field", label="Flow Field",
        blurb="Thousands of particles drifting through a smooth noise field, leaving glowing trails.",
        color_paradigm="gradient palette",
        fields=(
            Field("noise_scale", "Flow scale", "float", 80.0, min=20.0, max=200.0, step=1.0, group="shape"),
            Field("noise_octaves", "Flow detail (octaves)", "int", 3, min=1, max=5, step=1, group="shape"),
            Field("step_size", "Particle speed", "float", 1.8, min=0.5, max=4.0, step=0.1, group="shape"),
            Field("n_particles", "Particle count", "int", 3000, min=500, max=6000, step=100, group="advanced"),
            Field("trail_alpha", "Trail brightness", "float", 0.012, min=0.004, max=0.03, step=0.001, group="advanced"),
            Field("fade_alpha", "Trail persistence", "float", 0.998, min=0.99, max=0.999, step=0.001, group="advanced",
                  help="Closer to 1 = trails last longer before fading."),
            _swatch("bg_color", "Background", [6, 6, 16]),
            _gradient("palette", "Palette", [
                [0.0, [20, 20, 200]], [0.33, [140, 0, 220]], [0.66, [220, 0, 160]], [1.0, [0, 220, 255]],
            ]),
            Field("seed", "Seed", "seed", 42, group="shape"),
        ),
        # n_particles is NOT overridden here — it's a user-exposed slider
        # (500-6000), and hardcoding it in preview_overrides would make that
        # control a no-op in the preview (measured: even 6000 particles at
        # size=256/60 steps renders in ~0.08s, so there's no speed reason to).
        # capture_every MUST be 1, not `steps` — `step % capture_every == 0`
        # is only true at step=0 when they're equal, so an earlier version
        # of this (capture_every=60) captured just the empty starting
        # canvas every time regardless of `steps`, not the accumulated
        # trails after 60 steps. Caught by actually looking at the preview
        # output, not by the (fast, non-empty-PNG) automated checks.
        preview_overrides={"steps": 60, "warmup": 0, "capture_every": 1, "size": 256},
    ),

    "chladni": TemplateSchema(
        name="chladni", label="Chladni Figures",
        blurb="Nodal-line mandalas from vibrating-plate resonance modes.",
        color_paradigm="gradient (family-specific key: line_color) + discrete tints",
        fields=(
            Field("m_start", "Mode m", "float", 2.0, min=1.0, max=14.0, step=0.1, group="shape"),
            Field("n_start", "Mode n", "float", 3.0, min=1.0, max=14.0, step=0.1, group="shape",
                  help="m and n define the mandala's symmetry — try non-integer values."),
            Field("line_width", "Line thickness", "float", 0.06, min=0.02, max=0.15, step=0.005, group="shape"),
            Field("inner_glow", "Inner glow tint", "bool", True, group="shape"),
            _gradient("line_color", "Line color", [
                [0.0, [2, 2, 10]], [0.25, [20, 10, 80]], [0.55, [80, 40, 200]],
                [0.80, [180, 100, 255]], [1.0, [255, 220, 255]],
            ]),
            _swatch("bg_color", "Background", [2, 2, 10]),
            _swatch("pos_tint", "Positive-region tint", [30, 10, 50], visible_if=("inner_glow", True)),
            _swatch("neg_tint", "Negative-region tint", [10, 30, 20], visible_if=("inner_glow", True)),
            Field("tint_strength", "Tint strength", "float", 0.06, min=0.0, max=0.2, step=0.01, group="color",
                  visible_if=("inner_glow", True)),
            Field("m_end", "Mode m (video end)", "float", 5.0, min=1.0, max=14.0, step=0.1, group="advanced",
                  help="Only affects the full video's morph target, not this still preview."),
            Field("n_end", "Mode n (video end)", "float", 7.0, min=1.0, max=14.0, step=0.1, group="advanced",
                  help="Only affects the full video's morph target, not this still preview."),
        ),
        preview_overrides={"steps": 1, "warmup": 0, "capture_every": 1, "size": 320},
    ),

    "harmonograph": TemplateSchema(
        name="harmonograph", label="Harmonograph",
        blurb="A twin-pendulum curve — elegant damped Lissajous rosettes.",
        color_paradigm="discrete RGB triplets (not a gradient)",
        fields=(
            Field("freq_x1", "Frequency x1", "float", 2.0, min=1.0, max=8.0, step=0.1, group="shape"),
            Field("freq_x2", "Frequency x2", "float", 3.0, min=1.0, max=8.0, step=0.1, group="shape"),
            Field("freq_y1", "Frequency y1", "float", 2.0, min=1.0, max=8.0, step=0.1, group="shape"),
            Field("freq_y2", "Frequency y2", "float", 3.0, min=1.0, max=8.0, step=0.1, group="shape",
                  help="Near-integer ratios between the frequencies give the cleanest rosettes."),
            Field("damping", "Damping", "float", 0.006, min=0.0, max=0.02, step=0.0005, group="shape",
                  help="How quickly the curve decays inward."),
            Field("t_max", "Curve length", "float", 60.0, min=20.0, max=120.0, step=1.0, group="shape"),
            _swatch("bg_color", "Background", [8, 5, 20]),
            _swatch("line_color", "Line color", [220, 180, 80]),
            _swatch("glow_color", "Glow color", [255, 220, 120]),
            Field("intensity", "Brightness", "float", 0.004, min=0.001, max=0.01, step=0.0005, group="color"),
            Field("glow_boost", "Glow boost", "float", 2.0, min=0.0, max=5.0, step=0.1, group="color"),
            Field("amp_x1", "Amplitude x1", "float", 1.0, min=0.0, max=1.5, step=0.05, group="advanced"),
            Field("amp_x2", "Amplitude x2", "float", 0.7, min=0.0, max=1.5, step=0.05, group="advanced"),
            Field("amp_y1", "Amplitude y1", "float", 1.0, min=0.0, max=1.5, step=0.05, group="advanced"),
            Field("amp_y2", "Amplitude y2", "float", 0.7, min=0.0, max=1.5, step=0.05, group="advanced"),
        ),
        preview_overrides={"steps": 1, "warmup": 0, "capture_every": 1, "size": 320, "n_points": 100_000},
    ),

    "voronoi": TemplateSchema(
        name="voronoi", label="Voronoi Cells",
        blurb="Orbiting seed points carve an iridescent cellular mosaic.",
        color_paradigm="HSV scalars — hue is derived geometrically, not directly set",
        fields=(
            Field("n_seeds", "Cell count", "int", 24, min=6, max=60, step=1, group="shape"),
            Field("orbit_amp", "Seed spread", "float", 0.28, min=0.05, max=0.45, step=0.01, group="shape"),
            Field("border_width", "Border width", "float", 3.0, min=0.0, max=8.0, step=0.5, group="shape"),
            Field("border_bright", "Border brightness", "float", 2.5, min=1.0, max=4.0, step=0.1, group="shape"),
            Field("saturation", "Saturation", "float", 0.85, min=0.0, max=1.0, step=0.01, group="color"),
            Field("value", "Brightness", "float", 0.90, min=0.0, max=1.0, step=0.01, group="color"),
            Field("seed", "Seed", "seed", 42, group="shape"),
            Field("orbit_speed", "Orbit speed", "float", 0.018, min=0.0, max=0.05, step=0.001, group="advanced",
                  help="Only affects motion across the full video, not this still preview."),
        ),
        preview_overrides={"steps": 1, "warmup": 0, "capture_every": 1, "size": 320},
    ),

    "domain-coloring": TemplateSchema(
        name="domain-coloring", label="Domain Coloring",
        blurb="Complex-function phase portraits — color reveals the math itself.",
        color_paradigm="algorithmic — hue is the function's phase angle, no direct color control",
        fields=(
            Field("func", "Function", "enum", "z_pow", group="shape", choices=(
                "z_pow", "rational", "trig_sin", "trig_cos", "blaschke", "mobius", "exp_z", "joukowski", "newton",
            )),
            Field("n_start", "Exponent / degree (n)", "float", 2.0, min=1.0, max=9.0, step=0.1, group="shape",
                  visible_if=("func", "z_pow")),
            Field("p_start", "Numerator degree (p)", "float", 3.0, min=1.0, max=6.0, step=1.0, group="shape",
                  visible_if=("func", "rational")),
            Field("q_start", "Denominator degree (q)", "float", 2.0, min=1.0, max=6.0, step=1.0, group="shape",
                  visible_if=("func", "rational")),
            Field("c_re_start", "Constant c (real)", "float", 0.5, min=-2.0, max=2.0, step=0.05, group="shape",
                  visible_if=("func", "rational")),
            Field("c_im_start", "Constant c (imag)", "float", 0.0, min=-2.0, max=2.0, step=0.05, group="shape",
                  visible_if=("func", "rational")),
            Field("mag_rings", "Magnitude rings", "bool", True, group="shape"),
            Field("ring_strength", "Ring strength", "float", 0.3, min=0.0, max=1.0, step=0.05, group="shape",
                  visible_if=("mag_rings", True)),
            Field("saturation", "Saturation", "float", 0.9, min=0.0, max=1.0, step=0.01, group="color"),
            Field("phase_shift", "Hue wheel rotation", "float", 0.0, min=0.0, max=1.0, step=0.01, group="color",
                  help="The only direct color control — color is otherwise generated from the math."),
        ),
        preview_overrides={"steps": 1, "warmup": 0, "capture_every": 1, "size": 320},
    ),

    "julia": TemplateSchema(
        name="julia", label="Julia Set",
        blurb="Escape-time fractal — c traces a circle, producing an endless family of shapes.",
        color_paradigm="gradient palette + a discrete interior color",
        fields=(
            Field("c_radius", "c radius", "float", 0.7885, min=0.3, max=1.2, step=0.001, group="shape",
                  help="Distance of c from the origin — the single biggest shape driver."),
            # Default 1.5708 (pi/2), NOT the template's own 0.0 default — at
            # theta=0 this renders as near-invisible disconnected dust
            # (confirmed visually); pi/2 gives the classic, richly-detailed
            # dendrite fractal. The schema is free to pick a better starting
            # point than DEFAULTS for the composer's first impression, since
            # it's just a value passed through generate_frames like any other.
            Field("c_theta_start", "c angle", "float", 1.5708, min=0.0, max=6.283, step=0.01, group="shape"),
            Field("view_cx", "View center (real)", "float", 0.0, min=-2.0, max=2.0, step=0.01, group="shape"),
            Field("view_cy", "View center (imag)", "float", 0.0, min=-2.0, max=2.0, step=0.01, group="shape"),
            Field("zoom_start", "Zoom level", "float", 1.5, min=0.05, max=2.5, step=0.01, group="shape",
                  help="Smaller = more zoomed in."),
            _gradient("palette", "Palette", [
                [0.0, [0, 0, 0]], [0.12, [20, 0, 80]], [0.28, [0, 80, 200]],
                [0.45, [0, 200, 220]], [0.60, [200, 240, 255]], [0.75, [255, 200, 60]],
                [0.88, [255, 80, 0]], [1.0, [255, 255, 255]],
            ]),
            _swatch("interior_color", "Interior color", [0, 0, 0]),
            Field("max_iter", "Detail (max iterations)", "int", 256, min=50, max=700, step=10, group="advanced"),
            Field("cycle_len", "Color band frequency", "float", 64.0, min=8.0, max=256.0, step=1.0, group="advanced"),
        ),
        preview_overrides={"steps": 1, "warmup": 0, "capture_every": 1, "size": 320},
    ),

    "lyapunov": TemplateSchema(
        name="lyapunov", label="Lyapunov Fractal",
        blurb="Parameter-space map of order vs. chaos in the logistic map — stable blues, chaotic golds.",
        color_paradigm="dual gradient — one palette for the stable regime, one for the chaotic regime",
        fields=(
            Field("sequence", "A/B sequence", "enum", "AB", group="shape",
                  choices=("AB", "BA", "AAB", "ABB", "AABB", "AAAB", "ABBB", "AABBB"),
                  help="Alternation pattern between the two growth rates — reshapes the whole fractal."),
            Field("a_min", "a range: min", "float", 2.0, min=1.0, max=4.5, step=0.05, group="shape"),
            Field("a_max", "a range: max", "float", 4.0, min=1.0, max=4.5, step=0.05, group="shape"),
            Field("b_min", "b range: min", "float", 2.0, min=1.0, max=4.5, step=0.05, group="shape"),
            Field("b_max", "b range: max", "float", 4.0, min=1.0, max=4.5, step=0.05, group="shape"),
            _gradient("palette_stable", "Stable-region palette", [
                [0.0, [10, 8, 30]], [0.3, [10, 40, 100]], [0.65, [20, 120, 200]], [1.0, [100, 220, 255]],
            ]),
            _gradient("palette_chaos", "Chaotic-region palette", [
                [0.0, [10, 8, 30]], [0.25, [80, 30, 5]], [0.55, [220, 100, 10]], [1.0, [255, 230, 80]],
            ]),
            Field("stable_peak", "Stability contrast", "float", -4.0, min=-8.0, max=-1.0, step=0.1, group="color"),
            Field("chaos_peak", "Chaos contrast", "float", 2.0, min=0.5, max=5.0, step=0.1, group="color"),
            Field("warmup_iters", "Transient discarded", "int", 100, min=20, max=300, step=10, group="advanced"),
            Field("n_iters", "Detail (iterations averaged)", "int", 200, min=50, max=500, step=10, group="advanced"),
        ),
        preview_overrides={"steps": 1, "warmup": 0, "capture_every": 1, "size": 256},
    ),

    "kaleidoscope": TemplateSchema(
        name="kaleidoscope", label="Kaleidoscope",
        blurb="N-fold mirror-symmetric plasma — psychedelic, richly textured mandalas.",
        color_paradigm="gradient palette",
        fields=(
            Field("n_fold", "Symmetry (n-fold)", "int", 6, min=3, max=16, step=1, group="shape"),
            Field("scale1", "Texture scale 1", "float", 55.0, min=10.0, max=100.0, step=1.0, group="shape"),
            Field("scale2", "Texture scale 2", "float", 45.0, min=10.0, max=100.0, step=1.0, group="shape"),
            Field("scale3", "Texture scale 3", "float", 38.0, min=10.0, max=100.0, step=1.0, group="shape"),
            Field("scale4", "Texture scale 4", "float", 60.0, min=10.0, max=100.0, step=1.0, group="shape"),
            _gradient("palette", "Palette", [
                [0.0, [0, 0, 0]], [0.18, [30, 0, 80]], [0.35, [0, 80, 200]], [0.52, [0, 200, 200]],
                [0.68, [200, 240, 255]], [0.82, [255, 200, 60]], [0.92, [255, 60, 0]], [1.0, [255, 255, 255]],
            ]),
            Field("rate1", "Motion rate 1", "float", 1.0, min=0.1, max=3.0, step=0.05, group="advanced",
                  help="Only affects motion across the full video — has no effect on this still preview."),
            Field("rate2", "Motion rate 2", "float", 0.73, min=0.1, max=3.0, step=0.05, group="advanced",
                  help="Only affects motion across the full video — has no effect on this still preview."),
            Field("rate3", "Motion rate 3", "float", 1.31, min=0.1, max=3.0, step=0.05, group="advanced",
                  help="Only affects motion across the full video — has no effect on this still preview."),
            Field("rate4", "Motion rate 4", "float", 0.57, min=0.1, max=3.0, step=0.05, group="advanced",
                  help="Only affects motion across the full video — has no effect on this still preview."),
            Field("field_rate", "Rotation speed", "float", 0.018, min=0.0, max=0.06, step=0.001, group="advanced",
                  help="Only affects motion across the full video — has no effect on this still preview."),
        ),
        preview_overrides={"steps": 1, "warmup": 0, "capture_every": 1, "size": 320},
    ),

    "newton": TemplateSchema(
        name="newton", label="Newton Fractal",
        blurb="Root-finding basins for zⁿ − 1 — each root gets its own color band.",
        color_paradigm="gradient palette, banded by root",
        fields=(
            Field("n", "Polynomial degree", "int", 3, min=2, max=9, step=1, group="shape",
                  help="Number of roots — sets the fractal's rotational symmetry."),
            Field("theta_start", "Rotation angle", "float", 0.0, min=0.0, max=6.283, step=0.01, group="shape"),
            Field("zoom_start", "Zoom level", "float", 1.6, min=0.1, max=3.0, step=0.01, group="shape"),
            Field("view_cx", "View center (real)", "float", 0.0, min=-2.0, max=2.0, step=0.01, group="shape"),
            Field("view_cy", "View center (imag)", "float", 0.0, min=-2.0, max=2.0, step=0.01, group="shape"),
            _gradient("palette", "Palette", [
                [0.0, [10, 0, 40]], [0.10, [60, 0, 160]], [0.20, [0, 0, 255]], [0.28, [255, 255, 255]],
                [0.33, [0, 40, 0]], [0.44, [0, 160, 0]], [0.55, [80, 255, 80]], [0.62, [255, 255, 255]],
                [0.66, [80, 0, 0]], [0.78, [200, 40, 0]], [0.90, [255, 180, 40]], [1.0, [255, 255, 255]],
            ]),
            Field("max_iter", "Detail (max iterations)", "int", 80, min=20, max=150, step=5, group="advanced"),
        ),
        # newton has no warmup/capture_every params at all (writes every step
        # unconditionally) — passing them would fail unknown-key validation.
        preview_overrides={"steps": 1, "size": 320},
    ),

    "torus": TemplateSchema(
        name="torus", label="Torus",
        blurb="A glowing 3D donut, rendered as a rotating point cloud with depth fog.",
        color_paradigm="gradient palette + a discrete background color",
        fields=(
            Field("R", "Major radius", "float", 0.55, min=0.3, max=0.7, step=0.01, group="shape"),
            Field("r", "Tube radius", "float", 0.21, min=0.05, max=0.35, step=0.01, group="shape"),
            Field("tilt_x", "Tilt", "float", 0.55, min=0.0, max=1.57, step=0.01, group="shape"),
            Field("tilt_y", "Tilt (secondary axis)", "float", 0.0, min=-1.57, max=1.57, step=0.01, group="shape"),
            Field("fog_amount", "Depth fog", "float", 0.55, min=0.0, max=1.0, step=0.01, group="shape"),
            _gradient("palette", "Palette", [
                [0.0, [2, 3, 12]], [0.10, [0, 25, 100]], [0.25, [0, 90, 210]], [0.44, [0, 175, 255]],
                [0.63, [80, 225, 255]], [0.80, [190, 245, 255]], [1.0, [255, 255, 255]],
            ]),
            _swatch("bg_color", "Background", [2, 3, 12]),
            Field("gamma", "Glow gamma", "float", 0.38, min=0.2, max=0.8, step=0.01, group="color"),
            Field("n_u", "Detail (major-circle samples)", "int", 1400, min=200, max=2000, step=100, group="advanced"),
            Field("n_v", "Detail (tube samples)", "int", 700, min=100, max=1000, step=50, group="advanced"),
            Field("ry_rate", "Rotation speed (Y)", "float", 0.025, min=0.0, max=0.08, step=0.001, group="advanced",
                  help="Only affects rotation across the full video — has no effect on this still preview."),
            Field("rx_rate", "Rotation speed (X)", "float", 0.008, min=0.0, max=0.03, step=0.001, group="advanced",
                  help="Only affects rotation across the full video — has no effect on this still preview."),
        ),
        # torus has no warmup/capture_every params either — same as newton.
        preview_overrides={"steps": 1, "size": 320},
    ),

    "verhulst": TemplateSchema(
        name="verhulst", label="Verhulst Bifurcation",
        blurb="The logistic map's period-doubling cascade into chaos, as a density-glow diagram.",
        color_paradigm="gradient palette",
        fields=(
            Field("r_min", "View: r min", "float", 2.8, min=2.5, max=4.0, step=0.01, group="shape"),
            Field("r_max", "View: r max", "float", 4.0, min=2.5, max=4.0, step=0.01, group="shape"),
            Field("x_min", "View: x min", "float", 0.0, min=0.0, max=1.0, step=0.01, group="shape"),
            Field("x_max", "View: x max", "float", 1.0, min=0.0, max=1.0, step=0.01, group="shape"),
            _gradient("palette", "Palette", [
                [0.0, [3, 2, 8]], [0.15, [20, 10, 60]], [0.35, [80, 20, 180]],
                [0.58, [180, 60, 255]], [0.80, [240, 150, 255]], [1.0, [255, 240, 255]],
            ]),
            _swatch("bg_color", "Background", [3, 2, 8]),
            Field("gamma", "Glow gamma", "float", 0.35, min=0.15, max=0.7, step=0.01, group="color"),
            Field("n_iters", "Detail (iterations plotted)", "int", 400, min=100, max=800, step=25, group="advanced"),
            Field("warmup_iters", "Transient discarded", "int", 300, min=50, max=600, step=25, group="advanced"),
        ),
        preview_overrides={"steps": 1, "warmup": 0, "capture_every": 1, "size": 320},
    ),
}


def list_templates() -> list[dict]:
    return [
        {"name": s.name, "label": s.label, "blurb": s.blurb, "colorParadigm": s.color_paradigm}
        for s in TEMPLATES.values()
    ]


def get(name: str) -> TemplateSchema:
    try:
        return TEMPLATES[name]
    except KeyError:
        raise KeyError(f"no schema for template {name!r} (available: {sorted(TEMPLATES)})") from None


def to_json(schema: TemplateSchema) -> dict:
    """Render a schema to a plain-JSON shape the frontend can consume directly."""
    return {
        "name": schema.name,
        "label": schema.label,
        "blurb": schema.blurb,
        "colorParadigm": schema.color_paradigm,
        "typeDependent": schema.type_dependent,
        "fields": [
            {
                "key": f.key,
                "label": f.label,
                "kind": f.kind,
                "default": f.default,
                "group": f.group,
                **({"min": f.min} if f.min is not None else {}),
                **({"max": f.max} if f.max is not None else {}),
                **({"step": f.step} if f.step is not None else {}),
                **({"choices": list(f.choices)} if f.choices is not None else {}),
                **({"unit": f.unit} if f.unit is not None else {}),
                **({"help": f.help} if f.help is not None else {}),
                **({"visibleIf": {"key": f.visible_if[0], "value": f.visible_if[1]}}
                   if f.visible_if is not None else {}),
            }
            for f in schema.fields
        ],
    }


def _validate_gradient(stops: Any, field_key: str) -> list:
    if not isinstance(stops, list) or not stops:
        raise ValueError(f"{field_key}: expected a non-empty list of [position, [r,g,b]] stops")
    positions = []
    clean = []
    for stop in stops:
        if not (isinstance(stop, (list, tuple)) and len(stop) == 2):
            raise ValueError(f"{field_key}: each stop must be [position, [r,g,b]]")
        pos, rgb = stop
        pos = float(pos)
        if not (0.0 <= pos <= 1.0):
            raise ValueError(f"{field_key}: stop position {pos} out of [0,1]")
        rgb = _validate_rgb(rgb, field_key)
        positions.append(pos)
        clean.append([pos, rgb])
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        raise ValueError(f"{field_key}: stop positions must be strictly increasing")
    return clean


def _validate_rgb(rgb: Any, field_key: str) -> list:
    if not (isinstance(rgb, (list, tuple)) and len(rgb) == 3):
        raise ValueError(f"{field_key}: expected [r, g, b]")
    out = []
    for c in rgb:
        c = int(c)
        if not (0 <= c <= 255):
            raise ValueError(f"{field_key}: color channel {c} out of [0,255]")
        out.append(c)
    return out


def _type_dependent_spec(schema: TemplateSchema, field_key: str, active_switch: dict[str, str]) -> dict | None:
    """Look up the range/default override for a field whose valid range
    depends on a sibling field's value (e.g. strange-attractor's a/b/c/d
    depend on `type`). `field_key` like "params_start.a" maps to param "a"."""
    if not schema.type_dependent:
        return None
    for switch_key, table in schema.type_dependent.items():
        specs_for_value = table.get(active_switch.get(switch_key))
        if not specs_for_value:
            continue
        param_name = field_key.rsplit(".", 1)[-1]
        if param_name in specs_for_value:
            return specs_for_value[param_name]
    return None


def clamp_and_validate(name: str, params: dict) -> dict:
    """Server-side validation boundary: clamp numeric params into the schema's
    declared range, reject unknown keys and invalid enum/color values. This is
    the security/cost boundary for a public endpoint — never trust the client
    to have enforced its own slider bounds.

    Always returns a value for EVERY schema field, seeded from the schema's
    own declared defaults before applying `params` on top — not just whatever
    keys happen to be in `params`. A schema field's default is sometimes
    intentionally different from the underlying template's own `DEFAULTS`
    (e.g. julia's `c_theta_start` — the template defaults to 0.0, which
    renders as near-invisible dust; the schema defaults to a more interesting
    angle). Processing only submitted keys would let any omitted field fall
    through to the template's DEFAULTS instead, silently ignoring the
    schema's choice — this bit an early version of this function for exactly
    that field, caught only by looking at the rendered image.

    For type-dependent fields (strange-attractor's a/b/c/d), the range used is
    whichever attractor `type` is active *in this same request* — not the
    field's generic fallback range — so switching type and forgetting to also
    move a/b/c/d degrades gracefully into that type's valid range instead of
    silently rendering a near-blank preview.
    """
    schema = get(name)
    by_key = {f.key: f for f in schema.fields}
    unknown = set(params) - set(by_key)
    if unknown:
        raise ValueError(f"unknown param keys for {name}: {sorted(unknown)}")

    submitted = set(params)
    full = {**schema.defaults(), **params}

    active_switch = {
        switch_key: full.get(switch_key, by_key[switch_key].default)
        for switch_key in (schema.type_dependent or {})
    }

    clean: dict = {}
    for key, value in full.items():
        f = by_key[key]
        type_spec = _type_dependent_spec(schema, key, active_switch)
        if type_spec and type_spec.get("fixed"):
            clean[key] = type_spec["default"]
            continue
        if f.kind in ("int", "float"):
            value = int(value) if f.kind == "int" else float(value)
            lo = type_spec["min"] if type_spec else f.min
            hi = type_spec["max"] if type_spec else f.max
            if lo is not None:
                value = max(lo, value)
            if hi is not None:
                value = min(hi, value)
        elif f.kind == "bool":
            value = bool(value)
        elif f.kind == "enum":
            if value not in f.choices:
                raise ValueError(f"{name}.{key}: {value!r} not in {f.choices}")
        elif f.kind == "gradient":
            value = _validate_gradient(value, f"{name}.{key}")
        elif f.kind == "swatch":
            value = _validate_rgb(value, f"{name}.{key}")
        elif f.kind == "seed":
            value = int(value)
        else:
            raise ValueError(f"{name}.{key}: unknown field kind {f.kind!r}")
        clean[key] = value

    # Backfill: if a switch field (e.g. `type`) was explicitly submitted but
    # its dependent params (e.g. params_start.a/b/c/d) weren't, fill them
    # with THAT type's own defaults rather than the schema-default type's
    # values `full` already gave them above. Never overrides a value the
    # caller explicitly submitted themselves.
    for switch_key, table in (schema.type_dependent or {}).items():
        if switch_key not in submitted:
            continue
        specs_for_value = table.get(active_switch[switch_key], {})
        for field_key, f in by_key.items():
            param_name = field_key.rsplit(".", 1)[-1]
            if field_key in submitted or param_name not in specs_for_value:
                continue
            clean[field_key] = specs_for_value[param_name]["default"]

    return clean


def _expand_dotted_keys(params: dict) -> dict:
    """`params_start.a` (strange-attractor's UI-facing field naming) expands to
    the nested `{"params_start": {"a": ...}}` shape templates/*/template.py
    actually expects."""
    out: dict = {}
    for key, value in params.items():
        if "." in key:
            parent, child = key.split(".", 1)
            out.setdefault(parent, {})[child] = value
        else:
            out[key] = value
    return out


def build_render_params(name: str, params: dict) -> dict:
    """User params, validated, expanded, and ready to merge over the template's
    own DEFAULTS (i.e. what pipeline.generate.render_master expects)."""
    return _expand_dotted_keys(clamp_and_validate(name, params))


def build_preview_params(name: str, params: dict) -> dict:
    """Same as build_render_params, but with this template's cheap preview
    overrides applied on top — the shape this function returns is what
    pipeline.preview.render_preview_still passes to generate_frames."""
    schema = get(name)
    clean = build_render_params(name, params)
    return {**clean, **schema.preview_overrides}
