import type { SemanticState } from '../semantic'
import { KNOBS } from '../semantic'

interface Props {
  state: SemanticState
  onChange: (next: SemanticState) => void
  onOpenCraft: () => void
}

export default function PlayPanel({ state, onChange, onOpenCraft }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <p className="font-label text-[10px] uppercase tracking-[0.18em] text-[var(--fg-muted)]">Play mode</p>
        <h3 className="font-display mt-1 text-xl font-semibold tracking-tight">Feel first. Math later.</h3>
        <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">
          These knobs speak human — energy, chaos, warmth, density — and map onto the real physics of this system.
        </p>
      </div>

      <div className="space-y-5">
        {KNOBS.map((knob) => {
          const value = state[knob.id as keyof SemanticState]
          return (
            <div key={knob.id}>
              <div className="mb-2 flex items-baseline justify-between gap-3">
                <label className="text-sm font-medium text-[var(--fg)]">{knob.label}</label>
                <span className="font-label text-[11px] text-[var(--fg-muted)]">{value.toFixed(2)}</span>
              </div>
              <input
                type="range"
                className="lumen-range w-full"
                min={knob.min}
                max={knob.max}
                step={knob.step}
                value={value}
                onChange={(e) =>
                  onChange({ ...state, [knob.id]: parseFloat(e.target.value) })
                }
              />
              <p className="mt-1.5 text-[11px] text-[var(--fg-muted)]">{knob.help}</p>
            </div>
          )
        })}
      </div>

      <button
        type="button"
        onClick={onOpenCraft}
        className="w-full rounded-xl border border-[var(--border-strong)] px-4 py-3 text-sm font-semibold text-[var(--fg)] transition hover:-translate-y-0.5 hover:border-[var(--accent)]"
      >
        Open Craft dials →
      </button>
    </div>
  )
}
