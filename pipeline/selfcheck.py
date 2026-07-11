"""Regression check for the composer's schema + preview layer.

Not a pytest suite (the repo has no test dependency) — a plain script that
exercises every hero template through the same path the backend API will use:
schema validation -> preview render -> non-empty PNG, fast. Run after any
schema.py/preview.py change:

    .venv/bin/python -m pipeline.selfcheck
"""
from __future__ import annotations

import sys

from pipeline.preview import render_preview_motion, render_preview_still
from pipeline.schema import ATTRACTOR_PARAM_SPECS, TEMPLATES, clamp_and_validate


def check_schema_defaults_are_authoritative() -> list[str]:
    """Regression test: clamp_and_validate(name, {}) must resolve every field
    to the SCHEMA's declared default, not silently fall through to the
    template's own DEFAULTS. Those two differ on purpose in a few places
    (julia's c_theta_start=1.5708 vs the template's 0.0, chosen because 0.0
    renders as near-invisible dust) — an earlier version of this function
    only processed keys present in the input dict, so calling it with {} (or
    any partial dict) silently ignored every schema default that diverges
    from the template's own, for every field the caller didn't happen to
    mention. Caught only by looking at julia's rendered image."""
    failures = []
    for name, schema in TEMPLATES.items():
        resolved = clamp_and_validate(name, {})
        for f in schema.fields:
            if resolved.get(f.key) != f.default:
                failures.append(
                    f"{name}.{f.key}: clamp_and_validate({{}}) returned {resolved.get(f.key)!r}, "
                    f"expected the schema default {f.default!r}"
                )
    return failures


def check_defaults_render() -> list[str]:
    failures = []
    for name in TEMPLATES:
        try:
            png, info = render_preview_still(name, {})
            if not png:
                failures.append(f"{name}: empty PNG")
            # reaction-diffusion intentionally keeps long warmup so the preview
            # looks bloomed (~2–3s); other templates should stay under 2s.
            budget = 5.0 if name == "reaction-diffusion" else 3.0
            if info["render_seconds"] > budget:
                failures.append(
                    f"{name}: preview took {info['render_seconds']}s (>{budget}s budget)"
                )
        except Exception as e:
            failures.append(f"{name}: {type(e).__name__}: {e}")
    return failures


def check_validation_rejects_bad_input() -> list[str]:
    failures = []
    cases = [
        ("domain-coloring", {"func": "not_a_real_func"}, ValueError),
        ("chladni", {"not_a_real_key": 1}, ValueError),
        ("chladni", {"line_color": [[0.5, [1, 2, 3]], [0.1, [4, 5, 6]]]}, ValueError),
        ("mandelbrot", {"interior_color": [1, 2]}, ValueError),
    ]
    for name, bad_params, expected_exc in cases:
        try:
            clamp_and_validate(name, bad_params)
            failures.append(f"{name}: expected {expected_exc.__name__} for {bad_params}, got none")
        except expected_exc:
            pass
        except Exception as e:
            failures.append(f"{name}: expected {expected_exc.__name__}, got {type(e).__name__}: {e}")
    return failures


def check_preview_overrides_capture_the_last_step() -> list[str]:
    """Structural invariant: `step % capture_every == 0` is only true at
    step=0 when capture_every == steps, so a preview_overrides with
    capture_every equal to (or greater than) steps silently captures just
    the empty starting frame no matter how many steps run — exactly what
    happened to flow-field (steps=60, capture_every=60 rendered a blank
    canvas; selfcheck's non-empty-PNG/fast checks passed anyway because the
    background color itself isn't literally zero). This doesn't replace
    looking at the images — it can't tell "renders" from "looks good" — but
    it guards the one narrow, mechanical way that mistake recurs."""
    failures = []
    for name, schema in TEMPLATES.items():
        po = schema.preview_overrides
        steps, capture_every = po.get("steps", 1), po.get("capture_every", 1)
        if steps > 1 and capture_every >= steps:
            failures.append(
                f"{name}: preview_overrides steps={steps} capture_every={capture_every} "
                f"only ever captures step 0 — use capture_every=1 (or < steps)"
            )
    return failures


def check_no_dead_preview_controls() -> list[str]:
    """Regression test: a preview_overrides key must never shadow a
    user-exposed field, or that field's slider becomes a no-op in the
    preview — found for real in mandelbrot's max_iter and flow-field's
    n_particles, both fixed by simply not overriding them (they're fast
    enough at their full user-facing range not to need it)."""
    failures = []
    for name, schema in TEMPLATES.items():
        exposed = {f.key for f in schema.fields}
        clash = exposed & set(schema.preview_overrides)
        if clash:
            failures.append(f"{name}: preview_overrides shadows exposed field(s) {clash} — dead control(s)")
    return failures


def check_out_of_range_clamps() -> list[str]:
    failures = []
    clean = clamp_and_validate("mandelbrot", {"max_iter": 99999})
    if clean["max_iter"] != 1000:
        failures.append(f"mandelbrot.max_iter: expected clamp to 1000, got {clean['max_iter']}")
    return failures


def check_attractor_type_switch_backfills_params() -> list[str]:
    """Regression test: switching strange-attractor's `type` without also
    resubmitting a/b/c/d must backfill that type's own defaults, not leave
    the previous type's (wildly different-scale) values in place — an
    earlier version of this schema left Clifford's a/b/c/d on a Lorenz
    request and rendered an almost-blank preview."""
    failures = []
    for attractor_type, specs in ATTRACTOR_PARAM_SPECS.items():
        clean = clamp_and_validate("strange-attractor", {"type": attractor_type})
        for param, spec in specs.items():
            got = clean.get(f"params_start.{param}")
            if got != spec["default"]:
                failures.append(
                    f"strange-attractor type={attractor_type}: expected params_start.{param}="
                    f"{spec['default']} after backfill, got {got}"
                )
        png, info = render_preview_still("strange-attractor", {"type": attractor_type})
        if not png:
            failures.append(f"strange-attractor type={attractor_type}: empty preview")
    return failures


def check_motion_preview_smoke() -> list[str]:
    """Every hero template must produce a non-empty motion (or still-fallback)
    payload within a looser budget than single-frame stills."""
    failures = []
    # Spot-check a closed-form + a sequential template thoroughly; smoke the rest.
    samples = ["harmonograph", "strange-attractor", "flow-field", "mandelbrot"]
    for name in samples:
        try:
            payload, info = render_preview_motion(name, {}, n_frames=4)
            if not payload:
                failures.append(f"{name}: empty motion payload")
            elif info["render_seconds"] > 6.0:
                failures.append(
                    f"{name}: motion took {info['render_seconds']}s (>6s budget for n=4)"
                )
            elif info.get("n_frames", 0) < 2 and name != "unused":
                # All samples should multi-frame
                failures.append(f"{name}: expected multi-frame motion, got n={info.get('n_frames')}")
        except Exception as e:
            failures.append(f"{name} motion: {type(e).__name__}: {e}")
    return failures


def main() -> int:
    all_failures = [
        *check_schema_defaults_are_authoritative(),
        *check_defaults_render(),
        *check_validation_rejects_bad_input(),
        *check_preview_overrides_capture_the_last_step(),
        *check_no_dead_preview_controls(),
        *check_out_of_range_clamps(),
        *check_attractor_type_switch_backfills_params(),
        *check_motion_preview_smoke(),
    ]
    if all_failures:
        print(f"FAILED ({len(all_failures)}):")
        for f in all_failures:
            print(f"  - {f}")
        return 1
    print(f"OK: {len(TEMPLATES)} hero templates pass schema + preview checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
