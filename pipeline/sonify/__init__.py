"""Generative audio: synthesize a WAV from a template's own per-frame
simulation trace, deterministically, from the same params/seed that drove the
visuals — not a neural model, not a canned track.

Public API:
  synthesize_to_wav() — template + info -> a WAV path, or None if uncovered.
  resolve_audio()     — the single shared --audio/--no-audio/default-on
                         precedence decision, called by both pipeline.generate
                         and pipeline.batch so it can't drift between them.
"""
from __future__ import annotations

from pathlib import Path

from . import core, music, registry


def synthesize_to_wav(template_name: str, info: dict, loop: str, out_path: Path) -> Path | None:
    """Returns None (caller stays silent) if `template_name` has no recipe or
    `info["audio_trace"]` is missing/empty — never raises for an uncovered
    template.
    """
    if not registry.has_recipe(template_name):
        return None
    trace = info.get("audio_trace") or []
    if not trace:
        return None

    if loop == "boomerang":
        trace = core.mirror_trace(trace)

    fps = info["fps"]
    # Over-provision ~150ms so ffmpeg's `-stream_loop -1 -shortest` in
    # post.add_audio() always TRIMS rather than ever wraps a too-short track,
    # which would otherwise produce an audible seam glitch.
    duration_s = len(trace) / fps + 0.15

    structural_keys = registry.STRUCTURAL_KEYS.get(template_name, ())
    musical = music.musical_frame_for_config(template_name, info["config"], structural_keys)

    samples = registry.RECIPES[template_name](
        trace=trace, config=info["config"], musical=musical,
        fps=fps, duration_s=duration_s, sr=core.SR,
    )
    core.write_wav(out_path, core.normalize_and_soft_clip(samples), sr=core.SR)
    return out_path


def resolve_audio(
    template_name: str,
    info: dict,
    audio_arg: Path | None,
    no_audio_arg: bool,
    loop: str,
    out_path: Path,
) -> Path | None:
    """The one shared precedence decision — call this from every entry point
    that can produce audio (pipeline.generate, pipeline.batch), never
    reimplement the precedence inline at each call site:

      --audio FILE  -> static bed, unchanged behavior, skip synthesis entirely
      --no-audio    -> explicit silence
      recipe exists -> synthesize (default-on for the templates it covers)
      else          -> silence (unchanged for the templates it doesn't cover)
    """
    if audio_arg is not None:
        return audio_arg
    if no_audio_arg:
        return None
    return synthesize_to_wav(template_name, info, loop, out_path)
