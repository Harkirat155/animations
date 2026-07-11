import type { Params, ParamValue, TemplateSchema } from './types'

/** Mirrors pipeline/schema.py's `_expand_dotted_keys` — strange-attractor's
 * UI-facing "params_start.a" becomes the nested `{"params_start": {"a": ...}}`
 * shape each template's generate_frames() actually expects. Exporting this (rather
 * than the raw UI params) means the copied JSON is a real, valid preset the
 * existing CLI pipeline can render as-is:
 *   python -m pipeline.generate --template <name> --params preset.json --name out
 */
export function toPresetJson(params: Params): string {
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(params)) {
    if (key.includes('.')) {
      const [parent, child] = key.split('.', 2)
      const parentObj = (out[parent] ??= {}) as Record<string, unknown>
      parentObj[child] = value
    } else {
      out[key] = value
    }
  }
  return JSON.stringify(out, null, 2)
}

/** Flatten a nested preset (CLI shape) into the dotted UI param dict, keeping
 * only keys the current schema knows about. */
export function flattenPreset(raw: Record<string, unknown>, schema: TemplateSchema): Params {
  const keys = new Set(schema.fields.map((f) => f.key))
  const out: Params = {}
  for (const [key, value] of Object.entries(raw)) {
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      for (const [child, cv] of Object.entries(value as Record<string, unknown>)) {
        const dotted = `${key}.${child}`
        if (keys.has(dotted)) out[dotted] = cv as ParamValue
      }
    } else if (keys.has(key)) {
      out[key] = value as ParamValue
    }
  }
  return out
}

/** Merge look/share params onto schema defaults so every field has a value. */
export function mergeParams(schema: TemplateSchema, partial: Params): Params {
  const base = Object.fromEntries(schema.fields.map((f) => [f.key, f.default])) as Params
  return { ...base, ...partial }
}
