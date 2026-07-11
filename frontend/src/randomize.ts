import type { Field, GradientStop, Params, TemplateSchema } from './types'
import { resolveField } from './typeDependent'

function randInt(min: number, max: number): number {
  return Math.floor(min + Math.random() * (max - min + 1))
}

function randFloat(min: number, max: number): number {
  return min + Math.random() * (max - min)
}

function randomRgb(): [number, number, number] {
  return [randInt(0, 255), randInt(0, 255), randInt(0, 255)]
}

function randomizeField(field: Field, current: Params[string]): Params[string] {
  switch (field.kind) {
    case 'int':
      return field.min !== undefined && field.max !== undefined ? randInt(field.min, field.max) : current
    case 'float':
      return field.min !== undefined && field.max !== undefined ? randFloat(field.min, field.max) : current
    case 'bool':
      return Math.random() < 0.5
    case 'enum':
      return field.choices ? field.choices[randInt(0, field.choices.length - 1)] : current
    case 'swatch':
      return randomRgb()
    case 'gradient':
      // keep the same stop positions, randomize each stop's color — a
      // fresh palette from the same rhythm, not a different shape entirely
      return (current as GradientStop[]).map(([pos]) => [pos, randomRgb()] as GradientStop)
    case 'seed':
      return randInt(0, 1_000_000)
    default:
      return current
  }
}

/** True for fields whose valid range depends on a sibling "switch" field
 * (e.g. strange-attractor's a/b/c/d depend on `type` — Lorenz needs
 * sigma~[5,15], Clifford needs ~[-2.2,2.2]) — checked against every table,
 * not just the currently active value, since the point is to route these
 * into the second, range-aware randomization pass below. */
function isTypeDependentField(field: Field, schema: TemplateSchema): boolean {
  if (!schema.typeDependent) return false
  const paramName = field.key.includes('.') ? field.key.split('.').pop()! : field.key
  return Object.values(schema.typeDependent).some((table) =>
    Object.values(table).some((specs) => paramName in specs),
  )
}

/** Randomize every exposed field. Controls with no visual effect (e.g.
 * mandelbrot's hardcoded seed) are never in `schema.fields` to begin with —
 * see pipeline/schema.py — so there's nothing here to exclude explicitly.
 *
 * Two passes because of strange-attractor: randomizing `type` and a/b/c/d
 * independently against their static schema bounds would happily produce
 * e.g. `type=lorenz` with `a=-1.7` (a Clifford-scaled value nowhere near a
 * real Lorenz basin — the same near-blank-preview failure mode the backend's
 * type-dependent backfill exists to prevent). Pass 1 randomizes independent
 * fields, including switch fields themselves; pass 2 re-resolves each
 * dependent field's range against the (possibly just-changed) switch value
 * before randomizing it. */
export function randomizeAll(schema: TemplateSchema, params: Params): Params {
  const next: Params = { ...params }
  for (const field of schema.fields) {
    if (isTypeDependentField(field, schema)) continue
    next[field.key] = randomizeField(field, params[field.key])
  }
  for (const field of schema.fields) {
    if (!isTypeDependentField(field, schema)) continue
    const resolved = resolveField(field, schema, next)
    if (!resolved) continue // fixed for the active type — leave it alone
    next[field.key] = randomizeField(resolved, next[field.key])
  }
  return next
}
