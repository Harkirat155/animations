import { useState } from 'react'
import type { Field, Params, TemplateSchema } from '../types'
import { resolveField } from '../typeDependent'
import FieldControl from './FieldControl'

interface Props {
  schema: TemplateSchema
  params: Params
  onChange: (params: Params) => void
}

const GROUP_LABEL: Record<Field['group'], string> = {
  shape: 'Shape',
  color: 'Color',
  advanced: 'Advanced',
}

/** A field is renderable only if its `visibleIf` condition holds AND (for
 * type-dependent fields like strange-attractor's a/b/c/d) the active type
 * actually reads that parameter. Returns the field with min/max/label
 * resolved to the active type's spec — e.g. Lorenz's `a` slider must show
 * [5,15] (Sigma), not Clifford's static [-2.2,2.2] fallback range. */
function resolveVisibleField(field: Field, schema: TemplateSchema, params: Params): Field | null {
  if (field.visibleIf && params[field.visibleIf.key] !== field.visibleIf.value) return null
  return resolveField(field, schema, params)
}

export default function ParamPanel({ schema, params, onChange }: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false)

  function setField(field: Field, value: Params[string]) {
    const next: Params = { ...params, [field.key]: value }

    // Mirror the backend's type-dependent backfill so the UI updates
    // instantly instead of waiting on a round trip: switching strange-
    // attractor's `type` resets a/b/c/d to THAT type's own defaults,
    // since the previous type's values are usually the wrong scale
    // entirely (Clifford's ~[-2,2] vs Lorenz's sigma~10/rho~28).
    if (schema.typeDependent?.[field.key]) {
      const specs = schema.typeDependent[field.key][value as string]
      if (specs) {
        for (const [param, spec] of Object.entries(specs)) {
          const depField = schema.fields.find((f) => f.key.endsWith(`.${param}`))
          if (depField) next[depField.key] = spec.default
        }
      }
    }
    onChange(next)
  }

  const groups: Field['group'][] = ['shape', 'color', 'advanced']

  return (
    <div className="space-y-6">
      {groups.map((group) => {
        const fields = schema.fields
          .filter((f) => f.group === group)
          .map((f) => resolveVisibleField(f, schema, params))
          .filter((f): f is Field => f !== null)
        if (fields.length === 0) return null

        if (group === 'advanced') {
          return (
            <div key={group}>
              <button
                type="button"
                onClick={() => setAdvancedOpen((v) => !v)}
                className="flex w-full items-center justify-between text-xs font-medium uppercase tracking-wide text-white/40 hover:text-white/60"
              >
                {GROUP_LABEL[group]}
                <span>{advancedOpen ? '−' : '+'}</span>
              </button>
              {advancedOpen && (
                <div className="mt-3 space-y-4">
                  {fields.map((f) => (
                    <FieldRow key={f.key} field={f} value={params[f.key]} onChange={(v) => setField(f, v)} />
                  ))}
                </div>
              )}
            </div>
          )
        }

        return (
          <div key={group}>
            <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-white/40">
              {GROUP_LABEL[group]}
            </h3>
            <div className="space-y-4">
              {fields.map((f) => (
                <FieldRow key={f.key} field={f} value={params[f.key]} onChange={(v) => setField(f, v)} />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function FieldRow({ field, value, onChange }: { field: Field; value: Params[string]; onChange: (v: Params[string]) => void }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <label className="text-sm text-white/80">{field.label}</label>
      </div>
      <FieldControl field={field} value={value} onChange={onChange} />
      {field.help && <p className="mt-1 text-[11px] text-white/35">{field.help}</p>}
    </div>
  )
}
