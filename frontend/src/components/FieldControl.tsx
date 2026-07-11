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
            min={field.min}
            max={field.max}
            step={field.step ?? (field.kind === 'int' ? 1 : 0.01)}
            value={num}
            onChange={(e) => onChange(field.kind === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value))}
            className="h-1.5 flex-1 cursor-pointer accent-violet-400"
          />
          <span className="w-16 shrink-0 text-right font-mono text-xs text-white/70">
            {field.kind === 'int' ? num : num.toFixed(3)}
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
          className={`h-6 w-11 rounded-full transition-colors ${value ? 'bg-violet-500' : 'bg-white/15'}`}
        >
          <span
            className={`block size-4.5 rounded-full bg-white transition-transform ${
              value ? 'translate-x-5' : 'translate-x-0.5'
            }`}
          />
        </button>
      )
    case 'enum':
      return (
        <select
          value={value as string}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-md border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-white/90 focus:border-violet-400 focus:outline-none"
        >
          {field.choices?.map((choice) => (
            <option key={choice} value={choice} className="bg-neutral-900">
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
          className="h-8 w-14 cursor-pointer rounded border border-white/10 bg-transparent"
        />
      )
    }
    case 'seed':
      return (
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-white/50">{String(value)}</span>
          <button
            type="button"
            onClick={() => onChange(Math.floor(Math.random() * 1_000_000))}
            className="rounded-md border border-white/10 px-2 py-1 text-xs hover:bg-white/10"
          >
            🎲 Randomize
          </button>
        </div>
      )
    default:
      return null
  }
}
