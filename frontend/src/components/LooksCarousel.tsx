import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import type { Look } from '../types'

interface Props {
  looks: Look[]
  selectedId: string | null
  seriesFilter: string | null
  onSeriesFilter: (series: string | null) => void
  onSelect: (look: Look) => void
  onHoverLook?: (look: Look | null) => void
  onSurprise?: () => void
  intervalMs?: number
}

function thumbUrl(look: Look): string | null {
  if (!look.thumb) return null
  return new URL(look.thumb, window.location.origin + import.meta.env.BASE_URL).href
}

function shuffle<T>(items: T[]): T[] {
  const a = [...items]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

/** Viewport-first carousel — shuffled deck, random start & auto-advance. */
export default function LooksCarousel({
  looks,
  selectedId,
  seriesFilter,
  onSeriesFilter,
  onSelect,
  onHoverLook,
  onSurprise,
  intervalMs = 4800,
}: Props) {
  const withThumbs = useMemo(
    () => looks.filter((l) => Boolean(l.thumb)),
    [looks],
  )
  const deck = useMemo(() => shuffle(withThumbs), [withThumbs])
  const seriesList = useMemo(
    () => Array.from(new Set(withThumbs.map((l) => l.series))),
    [withThumbs],
  )
  const filtered = useMemo(
    () =>
      seriesFilter ? deck.filter((l) => l.series === seriesFilter) : deck,
    [deck, seriesFilter],
  )

  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const [direction, setDirection] = useState(1)
  const touchX = useRef<number | null>(null)
  const seededFor = useRef<string | null>(null)

  useEffect(() => {
    const key = `${seriesFilter ?? 'all'}:${filtered.map((l) => l.id).join(',')}`
    if (filtered.length === 0) {
      setIndex(0)
      seededFor.current = key
      return
    }
    if (seededFor.current === key) return
    seededFor.current = key
    setIndex(Math.floor(Math.random() * filtered.length))
  }, [seriesFilter, filtered])

  const safeIndex =
    filtered.length === 0
      ? 0
      : ((index % filtered.length) + filtered.length) % filtered.length
  const current = filtered[safeIndex] ?? null
  const prevLook =
    filtered.length > 1
      ? filtered[(safeIndex - 1 + filtered.length) % filtered.length]
      : null
  const nextLook =
    filtered.length > 1 ? filtered[(safeIndex + 1) % filtered.length] : null

  const go = useCallback(
    (dir: number) => {
      if (filtered.length === 0) return
      setDirection(dir)
      setIndex((i) => (i + dir + filtered.length) % filtered.length)
    },
    [filtered.length],
  )

  const goRandom = useCallback(() => {
    if (filtered.length < 2) return
    setDirection(1)
    setIndex((i) => {
      let n = Math.floor(Math.random() * filtered.length)
      if (n === i % filtered.length) n = (i + 1) % filtered.length
      return n
    })
  }, [filtered.length])

  useEffect(() => {
    if (paused || filtered.length < 2) return
    const id = window.setInterval(() => goRandom(), intervalMs)
    return () => window.clearInterval(id)
  }, [paused, filtered.length, goRandom, intervalMs])

  useEffect(() => {
    if (current) onHoverLook?.(current)
  }, [current, onHoverLook])

  if (looks.length === 0 || withThumbs.length === 0) {
    return (
      <p className="text-sm text-[var(--fg-muted)]">
        No Looks yet — run{' '}
        <code className="text-[var(--accent)]">python scripts/build_looks.py</code>
      </p>
    )
  }

  if (!current) {
    return (
      <p className="text-sm text-[var(--fg-muted)]">
        No looks with thumbnails in this series.
      </p>
    )
  }

  const currentThumb = thumbUrl(current)
  const prevThumb = prevLook ? thumbUrl(prevLook) : null
  const nextThumb = nextLook ? thumbUrl(nextLook) : null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-center gap-1.5">
        <button
          type="button"
          onClick={() => onSeriesFilter(null)}
          className={`font-label rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.1em] transition ${
            seriesFilter === null
              ? 'border-[var(--accent)]/45 bg-[var(--accent)]/12 text-[var(--accent)]'
              : 'border-white/12 text-white/50 hover:border-white/25 hover:text-white/80'
          }`}
        >
          All · {withThumbs.length}
        </button>
        {seriesList.map((series) => (
          <button
            key={series}
            type="button"
            onClick={() => onSeriesFilter(series === seriesFilter ? null : series)}
            className={`font-label rounded-full border px-2.5 py-1 text-[10px] uppercase tracking-[0.1em] transition ${
              seriesFilter === series
                ? 'border-[var(--accent)]/45 bg-[var(--accent)]/12 text-[var(--accent)]'
                : 'border-white/12 text-white/50 hover:border-white/25 hover:text-white/80'
            }`}
          >
            {series}
          </button>
        ))}
        {onSurprise && (
          <button
            type="button"
            onClick={onSurprise}
            className="font-label ml-1 rounded-full border border-white/15 px-2.5 py-1 text-[10px] uppercase tracking-[0.1em] text-white/60 transition hover:border-white/30 hover:text-white"
          >
            Surprise
          </button>
        )}
      </div>

      <div
        className="relative"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        onFocusCapture={() => setPaused(true)}
        onBlurCapture={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node)) setPaused(false)
        }}
        onTouchStart={(e) => {
          touchX.current = e.touches[0]?.clientX ?? null
          setPaused(true)
        }}
        onTouchEnd={(e) => {
          const start = touchX.current
          touchX.current = null
          setPaused(false)
          if (start == null) return
          const end = e.changedTouches[0]?.clientX
          if (end == null) return
          const dx = end - start
          if (Math.abs(dx) > 48) go(dx < 0 ? 1 : -1)
        }}
      >
        <div className="relative mx-auto flex min-h-[min(68vh,560px)] items-center justify-center">
          {prevLook && prevThumb && (
            <button
              type="button"
              aria-label={`Previous look: ${prevLook.label}`}
              onClick={() => go(-1)}
              className="absolute left-0 top-1/2 z-[1] hidden w-[16%] -translate-y-1/2 opacity-35 transition hover:opacity-65 lg:block xl:w-[18%]"
            >
              <div className="aspect-[3/4] overflow-hidden rounded-2xl border border-white/10">
                <img
                  src={prevThumb}
                  alt=""
                  className="h-full w-full scale-110 object-cover blur-[1px]"
                />
              </div>
            </button>
          )}

          {nextLook && nextThumb && (
            <button
              type="button"
              aria-label={`Next look: ${nextLook.label}`}
              onClick={() => go(1)}
              className="absolute right-0 top-1/2 z-[1] hidden w-[16%] -translate-y-1/2 opacity-35 transition hover:opacity-65 lg:block xl:w-[18%]"
            >
              <div className="aspect-[3/4] overflow-hidden rounded-2xl border border-white/10">
                <img
                  src={nextThumb}
                  alt=""
                  className="h-full w-full scale-110 object-cover blur-[2px]"
                />
                <div className="absolute inset-0 bg-black/25" />
              </div>
            </button>
          )}

          <div
            data-testid="looks-gallery"
            className="relative z-[2] w-full max-w-lg px-1 sm:max-w-xl md:max-w-2xl"
          >
            <AnimatePresence mode="wait" custom={direction}>
              <motion.div
                key={current.id}
                custom={direction}
                initial={{ opacity: 0, x: direction * 48, scale: 0.96 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: direction * -40, scale: 0.97 }}
                transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              >
                <button
                  type="button"
                  data-testid={`look-${current.id}`}
                  data-selected={selectedId === current.id ? 'true' : 'false'}
                  onClick={() => onSelect(current)}
                  className="cinema-card group relative w-full overflow-hidden text-left outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
                  style={{
                    boxShadow:
                      selectedId === current.id
                        ? '0 0 0 1px color-mix(in oklab, var(--art-a) 55%, transparent), 0 30px 80px rgb(0 0 0 / 50%)'
                        : '0 30px 80px rgb(0 0 0 / 45%)',
                  }}
                >
                  <div className="relative aspect-[4/5] max-h-[min(68vh,560px)] w-full sm:aspect-[5/6]">
                    <img
                      src={currentThumb!}
                      alt={current.label}
                      className="h-full w-full object-cover transition duration-700 group-hover:scale-[1.03]"
                    />
                    <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/85 via-black/15 to-transparent" />

                    <div className="absolute left-4 top-4">
                      <span className="font-label rounded-full border border-white/15 bg-black/45 px-2.5 py-1 text-[10px] uppercase tracking-[0.12em] text-white/75 backdrop-blur-md">
                        {current.series}
                      </span>
                    </div>

                    <div className="absolute inset-x-0 bottom-0 p-5 sm:p-6">
                      <p className="font-label text-[10px] uppercase tracking-[0.14em] text-white/50">
                        {current.templateLabel}
                      </p>
                      <h3 className="font-display mt-1 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
                        {current.label}
                      </h3>
                      <span className="mt-4 inline-flex items-center gap-2 rounded-full bg-[var(--fg)] px-4 py-2 text-xs font-bold text-[var(--bg)]">
                        Open
                        <span aria-hidden>→</span>
                      </span>
                    </div>

                    {!paused && filtered.length > 1 && (
                      <div className="absolute inset-x-0 top-0 h-0.5 overflow-hidden bg-white/10">
                        <motion.div
                          key={`prog-${current.id}-${safeIndex}`}
                          className="h-full bg-[var(--accent)]"
                          initial={{ scaleX: 0 }}
                          animate={{ scaleX: 1 }}
                          transition={{ duration: intervalMs / 1000, ease: 'linear' }}
                          style={{ transformOrigin: 'left' }}
                        />
                      </div>
                    )}
                  </div>
                </button>
              </motion.div>
            </AnimatePresence>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-center gap-3">
          <button
            type="button"
            aria-label="Previous look"
            onClick={() => go(-1)}
            className="nav-glass flex size-10 items-center justify-center rounded-full text-white"
          >
            ←
          </button>
          <div className="flex max-w-[10rem] items-center gap-1.5 overflow-hidden sm:max-w-xs">
            {filtered.slice(0, Math.min(filtered.length, 10)).map((look, i) => (
              <button
                key={look.id}
                type="button"
                aria-label={`Go to ${look.label}`}
                aria-current={i === safeIndex ? 'true' : undefined}
                onClick={() => {
                  setDirection(i > safeIndex ? 1 : -1)
                  setIndex(i)
                }}
                className={`h-1.5 rounded-full transition-all ${
                  i === safeIndex
                    ? 'w-5 bg-[var(--accent)]'
                    : 'w-1.5 bg-white/25 hover:bg-white/45'
                }`}
              />
            ))}
          </div>
          <button
            type="button"
            aria-label="Next look"
            onClick={() => go(1)}
            className="nav-glass flex size-10 items-center justify-center rounded-full text-white"
          >
            →
          </button>
        </div>
      </div>
    </div>
  )
}
