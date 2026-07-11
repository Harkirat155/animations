"""End-to-end runner: template (seeded params) -> master mp4 -> deliverables.

    .venv/bin/python -m pipeline.generate \
        --template reaction-diffusion \
        --params ideas/params/rd-mitosis.json \
        --name rd-mitosis-001 \
        --loop boomerang --watermark-text "@yourhandle"

This is the daily engine in miniature: one template + one param file = one post.
To batch a whole params dir overnight (fault-tolerant), use `python -m pipeline.batch`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

from pipeline import post, sonify
from pipeline.encode import frames_to_mp4

TEMPLATES_DIR = Path("templates")


def load_template(name: str):
    mod_path = TEMPLATES_DIR / name / "template.py"
    if not mod_path.exists():
        raise SystemExit(f"template not found: {mod_path}")
    spec = importlib.util.spec_from_file_location(f"templates.{name}", mod_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def render_master(template_name: str, params: dict, out_dir: Path) -> tuple[Path, dict]:
    """Render frames from a template and encode the square master mp4."""
    module = load_template(template_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        info = module.generate_frames(params, tmp)
        if info["n_frames"] == 0:
            raise SystemExit("template produced 0 frames — check params (warmup/steps).")
        master = out_dir / "master.mp4"
        frames_to_mp4(tmp, master, fps=info["fps"])
    return master, info


def main() -> int:
    p = argparse.ArgumentParser(description="Generate a clip end-to-end")
    p.add_argument("--template", required=True, help="folder name under templates/")
    p.add_argument("--params", help="JSON param file (merged over template DEFAULTS)")
    p.add_argument("--name", required=True, help="output folder name under output/")
    p.add_argument("--master-only", action="store_true", help="render master, skip post")
    audio_group = p.add_mutually_exclusive_group()
    audio_group.add_argument("--audio", help="static audio bed (looped) — overrides generative audio")
    audio_group.add_argument("--no-audio", action="store_true",
                             help="explicit silence — skip generative audio too")
    p.add_argument("--watermark-text")
    p.add_argument("--watermark-png")
    p.add_argument("--loop", choices=["none", "boomerang"], default="none")
    p.add_argument("--no-blur-bg", action="store_true")
    a = p.parse_args()

    params = json.loads(Path(a.params).read_text()) if a.params else {}
    out_dir = Path("output") / a.name
    master, info = render_master(a.template, params, out_dir)
    print(f"master: {master} ({info['n_frames']} frames @ {info['fps']}fps, "
          f"{info['width']}x{info['height']})")

    if a.master_only:
        return 0

    # Provenance: the render is a pure function of (template + resolved params),
    # so storing them makes this output reproducible and lets a winning look be
    # traced back / re-rendered / varied (the whole point of the curate->learn loop).
    render = {
        "template": a.template,
        "seed": info.get("seed"),
        "params": info.get("config"),
    }
    audio_path = sonify.resolve_audio(
        a.template, info, Path(a.audio) if a.audio else None, a.no_audio, a.loop,
        out_dir / "audio_generated.wav",
    )
    meta = post.process(
        master=master,
        name=a.name,
        audio=audio_path,
        watermark_text=a.watermark_text,
        watermark_png=Path(a.watermark_png) if a.watermark_png else None,
        loop=a.loop,
        blur_bg=not a.no_blur_bg,
        n_frames=info["n_frames"],
        render=render,
    )
    print(f"OK: output/{a.name}/ -> {list(meta['deliverables'].values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
