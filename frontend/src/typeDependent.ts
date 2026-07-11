import type { Field, Params, TemplateSchema } from './types'

/** Resolve a field's EFFECTIVE min/max/default/label for the currently active
 * value of whatever switch field it depends on (e.g. strange-attractor's
 * a/b/c/d ranges depend on `type` — Lorenz needs sigma~[5,15], Clifford
 * needs ~[-2.2,2.2]; some types don't use a param at all).
 *
 * Returns null when the resolved spec is `fixed` — the equation doesn't
 * read that parameter for the active type, so the control should be hidden
 * rather than shown as a live slider that provably does nothing (the same
 * category of dead control eliminated for mandelbrot's `seed`).
 *
 * Mirrors the backend's `_type_dependent_spec` in pipeline/schema.py — the
 * server enforces this authoritatively; this is so the UI reflects the same
 * ranges instead of showing Clifford's ±2.2 slider bounds while the backend
 * has already resolved/clamped the value to Lorenz's ~[5,15].
 */
export function resolveField(field: Field, schema: TemplateSchema, params: Params): Field | null {
  if (!schema.typeDependent) return field
  const paramName = field.key.includes('.') ? field.key.split('.').pop()! : field.key
  for (const [switchKey, table] of Object.entries(schema.typeDependent)) {
    const specs = table[String(params[switchKey])]
    const spec = specs?.[paramName]
    if (!spec) continue
    if (spec.fixed) return null
    return { ...field, min: spec.min, max: spec.max, label: spec.label ?? field.label }
  }
  return field
}
