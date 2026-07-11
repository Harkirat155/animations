# animations — generative content pipeline

A modular, parameterized engine for making animated visuals (math / nature / aesthetic
"satisfying" loops) for YouTube Shorts, Instagram Reels, and X. Build a *template* once;
it produces dozens of seeded variations. Posting is manual; everything before it is automated.

Full plan: `~/.claude/plans/i-want-to-make-tidy-wall.md`.

## The flow
```
ideate (params) → generate (template → frames → master.mp4) → post (9:16 / 1:1 / still / thumb) → post manually
```

## Setup
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt   # numpy, pillow
# ffmpeg must be on PATH (brew install ffmpeg)
```

## Quick start
```bash
# Prove the toolchain renders unattended:
.venv/bin/python -m pipeline.spike

# Make a full post from the flagship template + a param preset:
.venv/bin/python -m pipeline.generate \
    --template reaction-diffusion \
    --params ideas/params/rd-mitosis.json \
    --name rd-mitosis-001 \
    --loop boomerang --watermark-text "@yourhandle"
# -> output/rd-mitosis-001/{vertical.mp4, square.mp4, still.png, thumb.jpg, metadata.json}
```
Then post by hand following `pipeline/publish/POSTING.md`.

**Loop modes** (`--loop`): `none` (default) plays the natural forward growth — satisfying
for systems that bloom from a seed. `boomerang` plays forward+reverse for a hard-cut-free
loop, but on *growing* patterns it reads as a rewind; use it for ambient/steady-state looks.

## Layout
| Path | What |
|------|------|
| `templates/<name>/template.py` | a seeded generative system; exposes `DEFAULTS` + `generate_frames(params, dir)` |
| `pipeline/encode.py` | frames → mp4 (ffmpeg) |
| `pipeline/generate.py` | runner: template → master → deliverables |
| `pipeline/post.py` | post-production spine: aspect ratios, loop, audio, watermark, still, thumb |
| `pipeline/publish/` | **scaffold only** — manual posting (`POSTING.md`) + future `Publisher` interface |
| `ideas/params/*.json` | parameter presets (one preset ≈ one post) |
| `assets/` | CC/royalty-free audio, fonts, watermark png |
| `output/<name>/` | ready-to-post deliverables |
| `analytics/log.csv` | manual post log → template leaderboard |

## Batch a month overnight
```bash
.venv/bin/python -m pipeline.batch --template reaction-diffusion \
    --params-dir ideas/params --watermark-text "@yourhandle" \
    --audio assets/audio/ambient_placeholder.m4a
```
Renders every `ideas/params/*.json` into its own `output/<preset-name>/`. Fault-tolerant —
one bad preset is logged and skipped, never aborts the batch. Curate in the morning, post keepers.
Each output carries a `metadata.json` with a `render` block (template + seed + resolved params),
so a winning look is fully reproducible and can be varied.

## Adding a template
Create `templates/<name>/template.py` with a `DEFAULTS` dict and
`generate_frames(params, frames_dir) -> {"fps", "n_frames", "width", "height"}` that writes
square PNG frames. `reaction-diffusion` is the reference implementation.

## Composer app (Phase A: Looks + motion + share)

A web UI for composing living mathematical systems: curated **Looks**, live **motion**
preview, schema-driven **Craft** dials, and **share links** (`#c=…`). Full-quality video
export stays subscription-gated (Phase C — not built yet).

Covers 14 of 26 templates (see `pipeline/schema.py`).

```bash
# Terminal 1 — backend (templates/schema/preview API)
.venv/bin/pip install -r requirements.txt   # adds fastapi, uvicorn
.venv/bin/uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend (React + Vite + Tailwind, proxies /api to :8000)
cd frontend && npm install && npm run dev   # http://localhost:5173

# Rebuild Look gallery assets (thumbs + manifest) after adding presets
.venv/bin/python scripts/build_looks.py

# Regression checks
.venv/bin/python -m pipeline.selfcheck      # schema + still + motion smoke
node frontend/scripts/verify.mjs            # Playwright: needs both servers running
```

### Deploy (locked stack)

| Layer | Where |
|-------|--------|
| Frontend | **GitHub Pages** — `.github/workflows/pages.yml` |
| Backend | **Fly.io** — `Dockerfile` + `fly.toml` |
| Blobs (later) | Cloudflare **R2** |
| DB (later) | Cloudflare **D1** when auth/quota need it |

```bash
# Backend
fly launch --no-deploy   # first time only if app name free
fly secrets set CORS_ORIGINS="https://<user>.github.io,http://localhost:5173"
fly deploy

# Frontend — set repo Actions variable VITE_API_URL=https://<app>.fly.dev
# Optional: VITE_BASE=/<repo>/ for project pages
# Then push to main (or workflow_dispatch)
```

| Path | What |
|------|------|
| `pipeline/schema.py` | declarative UI schema per covered template |
| `pipeline/preview.py` | still + multi-frame motion (animated WebP), no ffmpeg |
| `backend/main.py` | `/api/templates`, `/schema`, `/preview`, `/preview/motion`, `/health` |
| `frontend/` | Looks gallery, Play/Craft modes, share links, Craft param panel |
| `scripts/build_looks.py` | builds `frontend/public/looks/` from `ideas/params` + `output/*/still.png` |
| `Dockerfile`, `fly.toml` | Fly deploy for the preview API |

The composer's **JSON** button exports the current dials in the shape
`ideas/params/*.json` uses — render via CLI without waiting on paid export.
**Share** copies a URL that reloads the same composition (state in the hash, no DB).

Adding another template: add a `TemplateSchema` entry to `pipeline/schema.py`, run
`pipeline/selfcheck.py`, then **generate a contact sheet and actually look at it**.

## Roadmap
- **Phase A (now):** Looks + motion + share; deploy Pages + Fly.
- **Phase B:** semantic Play knobs, sonify in the composer, signature content series.
- **Phase C:** Stripe + D1 quota + Fly render worker + R2 deliverables.
- **Later:** batch variations, education packs, optional WebGL previews.
