import type { SemanticState } from '../semantic'
import { KNOBS } from '../semantic'

interface Props {
  state: SemanticState
  onChange: (next: SemanticState) => void
  onOpenCraft: () => void
}

export default function PlayPanel({ state, onChange, onOpenCraft }: Props) {
  return (
    <div className="space-y-5">
      <div className="space-y-5">
        {KNOBS.map((knob) => {
          const value = state[knob.id as keyof SemanticState]
          const fill = `${((value - knob.min) / (knob.max - knob.min)) * 100}%`
          return (
            <div key={knob.id}>
              <div className="mb-2 flex items-baseline justify-between gap-3">
                <label className="text-sm font-medium text-[var(--fg)]">
                  {knob.label}
                </label>
                <span className="font-label text-[11px] tabular-nums text-[var(--fg-muted)]">
                  {value.toFixed(2)}
                </span>
              </div>
              <div className="relative">
                <div
                  className="pointer-events-none absolute inset-y-0 left-0 rounded-full opacity-40"
                  style={{
                    width: fill,
                    background: `linear-gradient(90deg, var(--art-a), var(--art-b))`,
                    height: 8,
                    top: '50%',
                    transform: 'translateY(-50%)',
                  }}
                />
                <input
                  type="range"
                  className="feel-range relative w-full"
                  min={knob.min}
                  max={knob.max}
                  step={knob.step}
                  value={value}
                  onChange={(e) =>
                    onChange({ ...state, [knob.id]: parseFloat(e.target.value) })
                  }
                />
              </div>
            </div>
          )
        })}
      </div>

      <button
        type="button"
        onClick={onOpenCraft}
        className="w-full rounded-xl border border-white/18 px-4 py-2.5 text-sm font-semibold text-[var(--fg)] transition hover:border-[var(--art-a)]/45"
      >
        Craft
      </button>
    </div>
  )
}
