import type { Field, GradientStop, ParamValue } from '../types'
import { hexToRgb, rgbToHex } from '../color'
import GradientEditor from './GradientEditor'

interface Props {
  field: Field
  value: ParamValue
  onChange: (value: ParamValue) => void
}

export default function FieldControl({ field, value, onChange }: Props) {
  switch (field.kind) {
    case 'int':
    case 'float': {
      const num = value as number
      return (
        <div className="flex items-center gap-3">
          <input
            type="range"
            className="lumen-range flex-1"
            min={field.min}
            max={field.max}
            step={field.step ?? (field.kind === 'int' ? 1 : 0.01)}
            value={num}
            onChange={(e) =>
              onChange(field.kind === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value))
            }
          />
          <span className="font-label w-16 shrink-0 text-right text-xs text-[var(--fg-muted)]">
            {field.kind === 'int' ? num : Number(num).toFixed(3)}
          </span>
        </div>
      )
    }
    case 'bool':
      return (
        <button
          type="button"
          role="switch"
          aria-checked={value as boolean}
          onClick={() => onChange(!value)}
          className={`h-7 w-12 rounded-full transition-colors ${
            value ? 'bg-[var(--accent)]' : 'bg-white/15'
          }`}
        >
          <span
            className={`block size-5 rounded-full bg-[var(--bg)] transition-transform ${
              value ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      )
    case 'enum':
      return (
        <select
          value={value as string}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-xl border border-[var(--border)] bg-black/30 px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--accent)] focus:outline-none"
        >
          {field.choices?.map((choice) => (
            <option key={choice} value={choice} className="bg-[#120a18]">
              {choice}
            </option>
          ))}
        </select>
      )
    case 'gradient':
      return <GradientEditor stops={value as GradientStop[]} onChange={onChange} />
    case 'swatch': {
      const rgb = value as [number, number, number]
      return (
        <input
          type="color"
          value={rgbToHex(rgb)}
          onChange={(e) => onChange(hexToRgb(e.target.value))}
          className="h-10 w-16 cursor-pointer rounded-xl border border-[var(--border)] bg-transparent"
        />
      )
    }
    case 'seed':
      return (
        <div className="flex items-center gap-2">
          <span className="font-label text-xs text-[var(--fg-muted)]">{String(value)}</span>
          <button
            type="button"
            onClick={() => onChange(Math.floor(Math.random() * 1_000_000))}
            className="rounded-pill border border-[var(--border)] px-3 py-1 text-xs text-[var(--fg-muted)] hover:border-[var(--border-strong)] hover:text-[var(--fg)]"
          >
            Shuffle
          </button>
        </div>
      )
    default:
      return null
  }
}
