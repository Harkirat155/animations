#!/usr/bin/env python3
"""Build curated Look gallery assets for the composer.

Reads ideas/params/*.json for schema-covered templates, flattens nested
params to the UI field shape, copies still.png thumbs into
frontend/public/looks/, and writes frontend/public/looks/manifest.json.

    .venv/bin/python scripts/build_looks.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.schema import TEMPLATES  # noqa: E402

THUMB_SIZE = 320  # square edge; keeps GH Pages bundle small

PARAMS_DIR = ROOT / "ideas" / "params"
OUTPUT_DIR = ROOT / "output"
OUT_DIR = ROOT / "frontend" / "public" / "looks"
THUMBS_DIR = OUT_DIR / "thumbs"

# Filename prefix → template folder name (only schema-covered templates).
PREFIX_TO_TEMPLATE: dict[str, str] = {
    "rd": "reaction-diffusion",
    "ff": "flow-field",
    "sa": "strange-attractor",
    "hg": "harmonograph",
    "ch": "chladni",
    "vo": "voronoi",
    "dc": "domain-coloring",
    "jl": "julia",
    "mb": "mandelbrot",
    "ly": "lyapunov",
    "ks": "kaleidoscope",
    "nw": "newton",
    "to": "torus",
    "vr": "verhulst",
}

# Series taxonomy for the gallery (from ideas/backlog + plan).
SERIES: dict[str, str] = {
    "reaction-diffusion": "Chemical gardens",
    "flow-field": "Field notes",
    "strange-attractor": "Strange forms",
    "harmonograph": "Sacred geometry",
    "chladni": "Sacred geometry",
    "voronoi": "Sacred geometry",
    "domain-coloring": "Complex plane",
    "julia": "Fractals",
    "mandelbrot": "Fractals",
    "lyapunov": "Fractals",
    "kaleidoscope": "Sacred geometry",
    "newton": "Fractals",
    "torus": "Strange forms",
    "verhulst": "Strange forms",
}


def flatten_for_schema(params: dict, schema_keys: set[str]) -> dict:
    """Preset JSON uses nested dicts; the UI uses dotted keys (params_start.a)."""
    out: dict = {}
    for key, value in params.items():
        if isinstance(value, dict):
            for child, cv in value.items():
                dotted = f"{key}.{child}"
                if dotted in schema_keys:
                    out[dotted] = cv
        elif key in schema_keys:
            out[key] = value
    return out


def find_still(preset_id: str) -> Path | None:
    candidates = [
        OUTPUT_DIR / f"{preset_id}-001" / "still.png",
        OUTPUT_DIR / f"{preset_id}-001" / "thumb.jpg",
        OUTPUT_DIR / preset_id / "still.png",
        OUTPUT_DIR / preset_id / "thumb.jpg",
    ]
    # Also accept any output dir starting with preset_id
    for d in sorted(OUTPUT_DIR.glob(f"{preset_id}*")):
        for name in ("still.png", "thumb.jpg"):
            p = d / name
            if p.exists():
                return p
    for c in candidates:
        if c.exists():
            return c
    return None


def human_label(preset_id: str) -> str:
    # rd-mitosis → Mitosis; sa-clifford-violet → Clifford Violet
    parts = preset_id.split("-")[1:]
    return " ".join(p.capitalize() for p in parts) if parts else preset_id


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    looks: list[dict] = []
    skipped_no_thumb = 0
    skipped_unknown = 0

    for path in sorted(PARAMS_DIR.glob("*.json")):
        preset_id = path.stem
        prefix = preset_id.split("-")[0]
        template = PREFIX_TO_TEMPLATE.get(prefix)
        if template is None or template not in TEMPLATES:
            skipped_unknown += 1
            continue

        schema = TEMPLATES[template]
        schema_keys = {f.key for f in schema.fields}
        raw = json.loads(path.read_text())
        params = flatten_for_schema(raw, schema_keys)
        if not params:
            continue

        still = find_still(preset_id)
        if still is None:
            skipped_no_thumb += 1
            # Still include the look — FE falls back to a placeholder
            thumb_url = None
        else:
            dest = THUMBS_DIR / f"{preset_id}.jpg"
            with Image.open(still) as im:
                im = im.convert("RGB")
                im.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
                # Pad to square for uniform gallery tiles
                canvas = Image.new("RGB", (THUMB_SIZE, THUMB_SIZE), (8, 8, 12))
                ox = (THUMB_SIZE - im.width) // 2
                oy = (THUMB_SIZE - im.height) // 2
                canvas.paste(im, (ox, oy))
                canvas.save(dest, format="JPEG", quality=82, optimize=True)
            thumb_url = f"looks/thumbs/{preset_id}.jpg"

        looks.append(
            {
                "id": preset_id,
                "label": human_label(preset_id),
                "template": template,
                "templateLabel": schema.label,
                "series": SERIES.get(template, "Other"),
                "blurb": schema.blurb,
                "thumb": thumb_url,
                "params": params,
            }
        )

    # Stable order: series, then label
    looks.sort(key=lambda L: (L["series"], L["template"], L["label"]))

    manifest = {
        "version": 1,
        "count": len(looks),
        "looks": looks,
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"wrote {len(looks)} looks → {OUT_DIR / 'manifest.json'} "
        f"(skipped unknown={skipped_unknown}, no thumb={skipped_no_thumb})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
