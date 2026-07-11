"""Batch runner: render every preset in a params dir into ready-to-post outputs.

This is the daily engine — point it at ideas/params/ and let it render a month of
content overnight, one output/<preset-name>/ per JSON. FAULT-TOLERANT by design:
one bad preset logs an error and is skipped, it never aborts the whole batch.

    .venv/bin/python -m pipeline.batch \
        --template reaction-diffusion \
        --params-dir ideas/params \
        --watermark-text "@yourhandle" --audio assets/audio/ambient_placeholder.m4a

Curate the results in the morning (see pipeline/publish/POSTING.md), post the keepers.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline import post, sonify
from pipeline.generate import render_master


def main() -> int:
    p = argparse.ArgumentParser(description="Batch-render every preset in a dir")
    p.add_argument("--template", default="reaction-diffusion", help="templates/<name>")
    p.add_argument("--params-dir", default="ideas/params", help="dir of *.json presets")
    audio_group = p.add_mutually_exclusive_group()
    audio_group.add_argument("--audio", help="static audio bed (looped) — overrides generative audio")
    audio_group.add_argument("--no-audio", action="store_true",
                             help="explicit silence — skip generative audio too")
    p.add_argument("--watermark-text")
    p.add_argument("--watermark-png")
    p.add_argument("--loop", choices=["none", "boomerang"], default="none")
    p.add_argument("--no-blur-bg", action="store_true")
    p.add_argument("--skip-existing", action="store_true",
                   help="skip presets whose output/<name>/ already exists")
    a = p.parse_args()

    presets = sorted(Path(a.params_dir).glob("*.json"))
    if not presets:
        raise SystemExit(f"no *.json presets in {a.params_dir}")

    ok, failed = [], []
    for i, preset in enumerate(presets, 1):
        name = preset.stem
        out_dir = Path("output") / name
        if a.skip_existing and out_dir.exists():
            print(f"[{i}/{len(presets)}] skip {name} (output exists)")
            continue
        print(f"[{i}/{len(presets)}] rendering {name} ...")
        try:
            params = json.loads(preset.read_text())
            master, info = render_master(a.template, params, out_dir)
            audio_path = sonify.resolve_audio(
                a.template, info, Path(a.audio) if a.audio else None, a.no_audio, a.loop,
                out_dir / "audio_generated.wav",
            )
            post.process(
                master=master,
                name=name,
                audio=audio_path,
                watermark_text=a.watermark_text,
                watermark_png=Path(a.watermark_png) if a.watermark_png else None,
                loop=a.loop,
                blur_bg=not a.no_blur_bg,
                n_frames=info["n_frames"],
                render={"template": a.template, "seed": info.get("seed"),
                        "params": info.get("config")},
            )
            ok.append(name)
            print(f"    OK -> output/{name}/")
        except Exception as e:  # continue-on-error: one bad preset must not abort the batch
            failed.append((name, str(e).splitlines()[0] if str(e) else type(e).__name__))
            print(f"    FAILED {name}: {failed[-1][1]}", file=sys.stderr)

    print(f"\nDone: {len(ok)} ok, {len(failed)} failed.")
    for name, err in failed:
        print(f"  FAILED {name}: {err}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
