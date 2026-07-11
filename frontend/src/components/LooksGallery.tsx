import type { Look } from '../types'

interface Props {
  looks: Look[]
  selectedId: string | null
  onSelect: (look: Look) => void
}

export default function LooksGallery({ looks, selectedId, onSelect }: Props) {
  if (looks.length === 0) {
    return (
      <p className="text-sm text-white/40">
        No curated Looks yet — run <code className="text-white/60">python scripts/build_looks.py</code> or pick a
        template below.
      </p>
    )
  }

  const seriesOrder: string[] = []
  const bySeries = new Map<string, Look[]>()
  for (const look of looks) {
    if (!bySeries.has(look.series)) {
      bySeries.set(look.series, [])
      seriesOrder.push(look.series)
    }
    bySeries.get(look.series)!.push(look)
  }

  return (
    <div data-testid="looks-gallery" className="space-y-6">
      {seriesOrder.map((series) => (
        <section key={series}>
          <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-white/40">{series}</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {bySeries.get(series)!.map((look) => {
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
                  className={`group overflow-hidden rounded-xl border text-left transition outline-none focus-visible:ring-2 focus-visible:ring-violet-400/60 ${
                    selected
                      ? 'border-violet-400 bg-violet-500/10'
                      : 'border-white/10 bg-white/[0.03] hover:border-white/25 hover:bg-white/[0.06]'
                  }`}
                >
                  <div className="aspect-square bg-black/50">
                    {thumbSrc ? (
                      <img
                        src={thumbSrc}
                        alt={look.label}
                        loading="lazy"
                        className="h-full w-full object-cover transition group-hover:scale-[1.02]"
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center text-[10px] text-white/25">
                        no thumb
                      </div>
                    )}
                  </div>
                  <div className="p-2.5">
                    <div className="truncate text-sm font-medium text-white/90">{look.label}</div>
                    <div className="truncate text-[11px] text-white/40">{look.templateLabel}</div>
                  </div>
                </button>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}
