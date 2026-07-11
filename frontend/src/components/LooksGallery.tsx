import type { Look } from '../types'

interface Props {
  looks: Look[]
  selectedId: string | null
  seriesFilter: string | null
  onSeriesFilter: (series: string | null) => void
  onSelect: (look: Look) => void
}

export default function LooksGallery({
  looks,
  selectedId,
  seriesFilter,
  onSeriesFilter,
  onSelect,
}: Props) {
  if (looks.length === 0) {
    return (
      <p className="text-sm text-[var(--fg-muted)]">
        No Looks yet — run <code className="text-[var(--accent)]">python scripts/build_looks.py</code>
      </p>
    )
  }

  const seriesList = Array.from(new Set(looks.map((l) => l.series)))
  const filtered = seriesFilter ? looks.filter((l) => l.series === seriesFilter) : looks

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onSeriesFilter(null)}
          className={`font-label rounded-pill border px-3 py-1.5 text-[10px] uppercase tracking-[0.12em] transition ${
            seriesFilter === null
              ? 'border-[var(--accent)] bg-[var(--accent)]/15 text-[var(--accent)]'
              : 'border-[var(--border)] text-[var(--fg-muted)] hover:border-[var(--border-strong)]'
          }`}
        >
          All · {looks.length}
        </button>
        {seriesList.map((series) => (
          <button
            key={series}
            type="button"
            onClick={() => onSeriesFilter(series === seriesFilter ? null : series)}
            className={`font-label rounded-pill border px-3 py-1.5 text-[10px] uppercase tracking-[0.12em] transition ${
              seriesFilter === series
                ? 'border-[var(--accent)] bg-[var(--accent)]/15 text-[var(--accent)]'
                : 'border-[var(--border)] text-[var(--fg-muted)] hover:border-[var(--border-strong)]'
            }`}
          >
            {series}
          </button>
        ))}
      </div>

      <div
        data-testid="looks-gallery"
        className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5"
      >
        {filtered.map((look) => {
          const selected = selectedId === look.id
          const thumbSrc = look.thumb
            ? new URL(look.thumb, window.location.origin + import.meta.env.BASE_URL).href
            : null
          return (
            <button
              key={look.id}
              type="button"
              data-testid={`look-${look.id}`}
              onClick={() => onSelect(look)}
              className={`group overflow-hidden rounded-2xl border text-left transition duration-300 outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] ${
                selected
                  ? 'border-[var(--accent)] shadow-[0_0_0_1px_var(--accent),0_12px_40px_rgb(215_255_61/0.12)]'
                  : 'border-[var(--border)] hover:border-[var(--border-strong)] hover:-translate-y-0.5'
              }`}
            >
              <div className="aspect-square bg-black/40">
                {thumbSrc ? (
                  <img
                    src={thumbSrc}
                    alt={look.label}
                    loading="lazy"
                    className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.04]"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center font-label text-[10px] text-[var(--fg-muted)]">
                    no thumb
                  </div>
                )}
              </div>
              <div className="border-t border-[var(--border)] bg-black/25 p-2.5">
                <div className="truncate text-sm font-medium text-[var(--fg)]">{look.label}</div>
                <div className="font-label mt-0.5 truncate text-[10px] uppercase tracking-[0.1em] text-[var(--fg-muted)]">
                  {look.templateLabel}
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
