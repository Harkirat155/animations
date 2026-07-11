# Idea backlog

The daily engine: one template + one param preset = one post. Curate, don't crank noise.

## Series concepts (pick ONE to be your signature)
- **"Chemical gardens"** — reaction-diffusion patterns growing in a recognizable palette/style.
- **"Field notes"** — flow-field / particle-flow loops themed on natural phenomena (wind, currents).
- **"Strange forms"** — strange-attractor morphs; mathematical chaos art.
- **"Sacred geometry"** — phyllotaxis / harmonograph / mathematical spirals.
- **"Proof without words"** — Manim math micro-explainers (one elegant idea, 20s). *(Phase 2)*

A signature, recognizable look is the moat — saturation is the #1 risk in this niche.

## Templates (5 now live)

| Template | Aesthetic | Render time | Key params |
|---|---|---|---|
| `reaction-diffusion` | Organic, biological, growing | ~1 min | `feed`, `kill`, `palette`, `v_max` |
| `flow-field` | Fluid, ambient, long-exposure | ~15 sec | `noise_scale`, `trail_alpha`, `fade_alpha` |
| `harmonograph` | Geometric spirograph, damped | ~20 sec | `freq_x1/2`, `freq_y1/2`, `detune_*` |
| `phyllotaxis` | Botanical, Fibonacci spirals | ~10 sec | `n_dots_final`, `anim_mode`, `scale` |
| `strange-attractor` | Chaotic fractal point clouds | ~1 min | `params_start`, `params_end`, `type` |

### Reaction-diffusion presets
- [x] `rd-mitosis` — classic blue/white dividing cells
- [x] `rd-coral` — branching coral from center
- [x] `rd-golden-hour` — warm amber, mitosis regime
- [x] `rd-neon-tokyo` — cyberpunk purple/cyan, mitosis regime
- [x] `rd-forest` — deep green, coral branching
- [x] `rd-rose-quartz` — blush pink, spots regime (f=0.025 k=0.060)
- [x] `rd-maze-ink` — cream/black inverted mazes (f=0.029 k=0.057)
- [x] `rd-aurora` — northern lights, coral branching

### Flow-field presets (all ~15s clips)
- [x] `ff-electric` — neon cyan/purple/pink on black
- [x] `ff-aurora` — aurora borealis green/teal/purple on dark navy
- [x] `ff-desert` — warm gold/amber on dark earth
- [x] `ff-ink` — dark ink trails on cream (Japanese brush aesthetic)

### Harmonograph presets (12s seamless loops)
- [x] `hg-gold` — warm gold Lissajous 2:3 on dark purple
- [x] `hg-neon` — neon cyan/purple 3:5 on black
- [x] `hg-silver` — silver/blue 3:4 on dark navy

### Phyllotaxis presets
- [x] `ph-sunflower` — gold→crimson→violet, grow mode (10s)
- [x] `ph-ocean` — cyan→purple, grow mode (10s)
- [x] `ph-bloom` — rose pink, bloom (pulse) mode (12s)

### Strange-attractor presets (~8s clips)
- [x] `sa-clifford-violet` — violet/lavender Clifford morph
- [x] `sa-clifford-ember` — fire ember orange, Clifford morph
- [x] `sa-dejong-teal` — teal/cyan De Jong morph

## Reaction-diffusion f/k regimes
- mitosis (dividing cells): f≈0.0367, k≈0.0649  ← `rd-mitosis`
- coral / branching: f≈0.0545, k≈0.062          ← `rd-coral`
- mazes / fingerprints: f≈0.029, k≈0.057        ← `rd-maze-ink`
- spots / leopard: f≈0.025, k≈0.06              ← `rd-rose-quartz`
- waves / pulsing: f≈0.014, k≈0.045             ← (not yet rendered)

**Tuning notes:**
- `v_max` maps the chemical field into the palette — set it ≈ post-warmup max of V
  (~0.38–0.42). Too low → blown-out; too high → dull.
- `n_spots` scales with AREA (`size²`). Center-seed looks (coral) fill from one point.
- `warmup` skips the near-black opening so clip opens on already-bloomed frame.

## Strange-attractor tuning notes
- Parameters must land in a non-diverging regime. Clifford: safe range ≈ [-2, 2] for all.
  DeJong: a,b ≈ [-2.5, 2.5] typically works. Start near known-good values (see presets).
- `params_start` → `params_end` morph creates the animation. Large changes = dramatic shift.
  Too large = attractor structure changes completely, loses coherence.
- `density_clip` (0.99–0.999) controls highlight rolloff. Lower = more faint detail visible.
- `gamma` (0.35–0.55): lower lifts the faint traces more aggressively.

## Flow-field tuning notes
- `noise_scale` (pixel units): larger = smoother, more sweeping curves; smaller = tighter spirals.
- `fade_alpha` = 1.0 → no trail decay (accumulating painting). < 1.0 → motion visible, trails dissolve.
- `trail_alpha`: too high → canvas saturates to solid color; too low → invisible traces.

## Weekly ritual
1. LLM-brainstorm 20–30 param variations + hooks/captions for the signature series.
2. Save the best as `ideas/params/*.json`.
3. Batch-render overnight → curate → post the keepers (`pipeline/publish/POSTING.md`).
4. Log results in `analytics/log.csv`; double down on the winning look.
