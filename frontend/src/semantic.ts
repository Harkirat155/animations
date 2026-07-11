/**
 * Semantic "Play" knobs — human language mapped onto real template params.
 * Not a fake universal physics layer; each template owns its mapping.
 */
import type { Params, TemplateSchema } from './types'

export interface SemanticKnob {
  id: string
  label: string
  help: string
  min: number
  max: number
  step: number
  default: number
}

export interface SemanticState {
  energy: number
  chaos: number
  warmth: number
  density: number
}

export const DEFAULT_SEMANTIC: SemanticState = {
  energy: 0.55,
  chaos: 0.4,
  warmth: 0.45,
  density: 0.5,
}

export const KNOBS: SemanticKnob[] = [
  { id: 'energy', label: 'Energy', help: 'Motion intensity & growth rate', min: 0, max: 1, step: 0.01, default: 0.55 },
  { id: 'chaos', label: 'Chaos', help: 'How wild the structure gets', min: 0, max: 1, step: 0.01, default: 0.4 },
  { id: 'warmth', label: 'Warmth', help: 'Palette temperature', min: 0, max: 1, step: 0.01, default: 0.45 },
  { id: 'density', label: 'Density', help: 'Fill, detail, and thickness', min: 0, max: 1, step: 0.01, default: 0.5 },
]

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

/** Warm (1) → cool (0) palette stops */
function warmthPalette(warmth: number): [number, [number, number, number]][] {
  if (warmth > 0.66) {
    return [
      [0, [8, 2, 4]],
      [0.25, [80, 10, 20]],
      [0.5, [220, 60, 20]],
      [0.75, [255, 180, 40]],
      [1, [255, 250, 220]],
    ]
  }
  if (warmth < 0.33) {
    return [
      [0, [2, 4, 18]],
      [0.25, [10, 40, 120]],
      [0.5, [20, 160, 200]],
      [0.75, [140, 220, 255]],
      [1, [240, 250, 255]],
    ]
  }
  return [
    [0, [10, 4, 28]],
    [0.3, [80, 20, 140]],
    [0.55, [200, 40, 160]],
    [0.8, [255, 120, 180]],
    [1, [255, 240, 255]],
  ]
}

/** Apply semantic knobs onto schema defaults + existing params. */
export function applySemantic(
  schema: TemplateSchema,
  base: Params,
  s: SemanticState,
): Params {
  const next: Params = { ...base }
  const name = schema.name
  const keys = new Set(schema.fields.map((f) => f.key))

  const set = (key: string, value: Params[string]) => {
    if (keys.has(key)) next[key] = value
  }

  // Shared color temperature when a palette field exists
  if (keys.has('palette')) set('palette', warmthPalette(s.warmth))
  if (keys.has('line_color') && Array.isArray(next.line_color) && typeof next.line_color[0] === 'number') {
    // RGB triplet style (harmonograph)
    const warm: [number, number, number] = [255, 180, 80]
    const cool: [number, number, number] = [80, 200, 255]
    set('line_color', [
      Math.round(lerp(cool[0], warm[0], s.warmth)),
      Math.round(lerp(cool[1], warm[1], s.warmth)),
      Math.round(lerp(cool[2], warm[2], s.warmth)),
    ])
  }

  switch (name) {
    case 'reaction-diffusion': {
      // Regimes from backlog: mitosis / coral / spots / mazes
      const regimes = [
        { feed: 0.0367, kill: 0.0649 }, // mitosis
        { feed: 0.0545, kill: 0.062 }, // coral
        { feed: 0.025, kill: 0.06 }, // spots
        { feed: 0.029, kill: 0.057 }, // mazes
      ]
      const idx = Math.min(regimes.length - 1, Math.floor(s.chaos * regimes.length))
      const r = regimes[idx]!
      set('feed', r.feed + (s.energy - 0.5) * 0.008)
      set('kill', r.kill)
      set('n_spots', Math.round(lerp(8, 120, s.density)))
      set('v_max', lerp(0.28, 0.5, s.energy))
      break
    }
    case 'flow-field': {
      set('noise_scale', lerp(140, 30, s.chaos))
      set('trail_alpha', lerp(0.004, 0.04, s.density))
      set('fade_alpha', lerp(0.992, 0.999, s.energy))
      set('step_size', lerp(0.8, 3.2, s.energy))
      break
    }
    case 'strange-attractor': {
      // Chaos → pick wilder attractor types; energy scales morph distance slightly
      const types = ['clifford', 'dejong', 'henon', 'tinkerbell', 'lorenz', 'rossler']
      const t = types[Math.min(types.length - 1, Math.floor(s.chaos * types.length))]!
      set('type', t)
      set('gamma', lerp(0.55, 0.3, s.density))
      set('density_clip', lerp(0.999, 0.98, s.density))
      // Warmth already applied to palette
      void s.energy
      break
    }
    case 'harmonograph': {
      set('damping', lerp(0.012, 0.001, s.energy))
      set('detune_x1', lerp(0.0, 0.012, s.chaos))
      set('detune_y1', lerp(0.0, -0.01, s.chaos))
      set('intensity', lerp(0.002, 0.01, s.density))
      set('glow_boost', lerp(1.0, 3.5, s.energy))
      break
    }
    case 'mandelbrot':
    case 'julia': {
      set('max_iter', Math.round(lerp(80, 700, s.density)))
      set('hue_shift', s.warmth)
      set('cycle_len', lerp(12, 80, s.energy))
      if (name === 'mandelbrot') {
        set('zoom_start', lerp(2.2, 0.08, s.chaos * 0.7 + s.energy * 0.3))
      }
      break
    }
    case 'chladni': {
      set('m_start', lerp(1, 8, s.chaos))
      set('n_start', lerp(1, 7, s.energy))
      break
    }
    case 'domain-coloring': {
      set('saturation', lerp(0.4, 1.0, s.energy))
      set('phase_shift', s.warmth)
      break
    }
    case 'newton': {
      set('max_iter', Math.round(lerp(40, 200, s.density)))
      break
    }
    case 'lyapunov': {
      set('a_min', lerp(1.5, 2.8, s.chaos))
      set('a_max', lerp(3.5, 4.2, s.energy))
      set('stable_peak', lerp(-6, -2, s.density))
      break
    }
    case 'kaleidoscope': {
      set('n_fold', Math.round(lerp(3, 12, s.density)))
      set('field_rate', lerp(0.005, 0.04, s.energy))
      break
    }
    case 'torus': {
      set('R', lerp(0.35, 0.68, s.density))
      set('r', lerp(0.08, 0.32, s.energy))
      set('fog_amount', lerp(0.2, 0.85, s.chaos))
      break
    }
    case 'verhulst': {
      set('r_min', lerp(2.5, 3.2, s.chaos))
      set('r_max', lerp(3.6, 4.0, s.energy))
      break
    }
    case 'voronoi': {
      set('n_seeds', Math.round(lerp(8, 48, s.density)))
      set('saturation', lerp(0.3, 1.0, s.energy))
      set('value', lerp(0.45, 1.0, s.warmth))
      break
    }
    default:
      break
  }

  // Clamp numeric fields to schema bounds when possible
  for (const f of schema.fields) {
    if (!(f.key in next)) continue
    if ((f.kind === 'float' || f.kind === 'int') && typeof next[f.key] === 'number') {
      let v = next[f.key] as number
      if (f.min != null) v = Math.max(f.min, v)
      if (f.max != null) v = Math.min(f.max, v)
      if (f.kind === 'int') v = Math.round(v)
      next[f.key] = v
    }
  }

  return next
}

export function semanticFromParams(_schema: TemplateSchema, _params: Params): SemanticState {
  // Play knobs are intentional overrides — always start from defaults when
  // entering Play mode so the mapping feels causal, not reverse-engineered.
  return { ...DEFAULT_SEMANTIC }
}

export function clampSemantic(s: SemanticState): SemanticState {
  return {
    energy: clamp(s.energy, 0, 1),
    chaos: clamp(s.chaos, 0, 1),
    warmth: clamp(s.warmth, 0, 1),
    density: clamp(s.density, 0, 1),
  }
}
