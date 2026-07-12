import type { TemplateSummary } from '../types'

interface Props {
  templates: TemplateSummary[]
  selected: string | null
  onSelect: (name: string) => void
  orientation?: 'horizontal' | 'vertical'
}

/** Dense instrument chips — name only. */
export default function SystemRail({
  templates,
  selected,
  onSelect,
  orientation = 'horizontal',
}: Props) {
  if (orientation === 'vertical') {
    return (
      <div
        data-testid="template-gallery"
        className="scroll-thin flex max-h-[50vh] flex-col gap-1 overflow-y-auto pr-1"
      >
        {templates.map((t) => (
          <SystemChip
            key={t.name}
            t={t}
            selected={selected === t.name}
            onSelect={onSelect}
          />
        ))}
      </div>
    )
  }

  return (
    <div
      data-testid="template-gallery"
      className="scroll-thin flex gap-1.5 overflow-x-auto pb-0.5"
    >
      {templates.map((t) => (
        <SystemChip
          key={t.name}
          t={t}
          selected={selected === t.name}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}

function SystemChip({
  t,
  selected,
  onSelect,
}: {
  t: TemplateSummary
  selected: boolean
  onSelect: (name: string) => void
}) {
  return (
    <button
      type="button"
      data-testid={`template-${t.name}`}
      onClick={() => onSelect(t.name)}
      title={t.blurb}
      className={`shrink-0 rounded-full border px-3.5 py-1.5 text-sm font-medium transition outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
        selected
          ? 'border-[var(--art-a)]/50 bg-[var(--art-a)]/15 text-[var(--fg)]'
          : 'border-white/12 bg-white/5 text-white/70 hover:border-white/25 hover:text-white'
      }`}
    >
      {t.label}
    </button>
  )
}
