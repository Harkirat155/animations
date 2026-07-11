import type { TemplateSummary } from '../types'

interface Props {
  templates: TemplateSummary[]
  selected: string | null
  onSelect: (name: string) => void
}

export default function TemplateGallery({ templates, selected, onSelect }: Props) {
  return (
    <div data-testid="template-gallery" className="flex gap-2 overflow-x-auto scroll-thin pb-1">
      {templates.map((t) => (
        <button
          key={t.name}
          type="button"
          data-testid={`template-${t.name}`}
          onClick={() => onSelect(t.name)}
          className={`shrink-0 rounded-2xl border px-4 py-3 text-left transition outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
            selected === t.name
              ? 'border-[var(--accent)] bg-[var(--accent)]/10'
              : 'border-[var(--border)] bg-black/20 hover:border-[var(--border-strong)]'
          }`}
        >
          <div className="text-sm font-medium text-[var(--fg)]">{t.label}</div>
          <div className="mt-0.5 max-w-[10rem] truncate text-[11px] text-[var(--fg-muted)]">{t.blurb}</div>
        </button>
      ))}
    </div>
  )
}
