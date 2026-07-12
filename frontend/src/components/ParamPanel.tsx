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

function resolveVisibleField(field: Field, schema: TemplateSchema, params: Params): Field | null {
  if (field.visibleIf && params[field.visibleIf.key] !== field.visibleIf.value) return null
  return resolveField(field, schema, params)
}

export default function ParamPanel({ schema, params, onChange }: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false)

  function setField(field: Field, value: Params[string]) {
    const next: Params = { ...params, [field.key]: value }
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
    <div className="space-y-5">
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
                className="font-label sticky top-0 z-[1] flex w-full items-center justify-between bg-[rgb(12_12_16/0.85)] py-2 text-[10px] uppercase tracking-[0.16em] text-[var(--fg-muted)] backdrop-blur-sm hover:text-[var(--fg)]"
              >
                {GROUP_LABEL[group]}
                <span className="text-sm">{advancedOpen ? '−' : '+'}</span>
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
            <h3 className="font-label sticky top-0 z-[1] mb-3 bg-[rgb(12_12_16/0.85)] py-1 text-[10px] uppercase tracking-[0.16em] text-[var(--fg-muted)] backdrop-blur-sm">
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

function FieldRow({
  field,
  value,
  onChange,
}: {
  field: Field
  value: Params[string]
  onChange: (v: Params[string]) => void
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <label className="text-sm text-[var(--fg)]">{field.label}</label>
      </div>
      <FieldControl field={field} value={value} onChange={onChange} />
      {field.help && (
        <p className="mt-1.5 text-[11px] leading-relaxed text-[var(--fg-muted)]">{field.help}</p>
      )}
    </div>
  )
}
