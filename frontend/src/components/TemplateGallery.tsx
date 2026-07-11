import type { TemplateSummary } from '../types'

interface Props {
  templates: TemplateSummary[]
  selected: string | null
  onSelect: (name: string) => void
}

export default function TemplateGallery({ templates, selected, onSelect }: Props) {
  return (
    <div data-testid="template-gallery" className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {templates.map((t) => (
        <button
          key={t.name}
          type="button"
          data-testid={`template-${t.name}`}
          onClick={() => onSelect(t.name)}
          className={`rounded-xl border p-3 text-left transition outline-none focus-visible:ring-2 focus-visible:ring-white/40 ${
            selected === t.name
              ? 'border-violet-400 bg-violet-500/10'
              : 'border-white/10 bg-white/[0.03] hover:border-white/25 hover:bg-white/[0.06]'
          }`}
        >
          <div className="text-sm font-medium text-white/90">{t.label}</div>
          <div className="mt-1 line-clamp-2 text-xs text-white/45">{t.blurb}</div>
        </button>
      ))}
    </div>
  )
}
