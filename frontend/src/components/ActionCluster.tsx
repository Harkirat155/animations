import { useEffect, useRef, useState } from 'react'

interface Props {
  motionOn: boolean
  onToggleMotion: () => void
  onSurprise: () => void
  onReset: () => void
  onShare: () => void
  onDownload: () => void
  onJson: () => void
  onFullVideo: () => void
  copied: 'json' | 'share' | null
  exporting: boolean
  canDownload: boolean
  shareError?: string | null
}

/** Primary actions only; Reset / JSON under ··· for power users. */
export default function ActionCluster({
  onSurprise,
  onReset,
  onShare,
  onDownload,
  onJson,
  onFullVideo,
  copied,
  exporting,
  canDownload,
  shareError,
}: Props) {
  const [moreOpen, setMoreOpen] = useState(false)
  const moreRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!moreOpen) return
    const onDoc = (e: MouseEvent) => {
      if (!moreRef.current?.contains(e.target as Node)) setMoreOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [moreOpen])

  return (
    <div className="space-y-2">
      <div className="dock-glass flex flex-wrap items-center justify-center gap-1.5 p-2 sm:gap-2 sm:p-2.5">
        <button
          type="button"
          onClick={onSurprise}
          className="rounded-pill border border-[var(--border-strong)] px-3.5 py-2 text-xs font-semibold text-[var(--fg)] transition hover:border-[var(--art-a)]/40"
        >
          Surprise
        </button>
        <button
          type="button"
          onClick={onShare}
          className="rounded-pill border border-[var(--art-a)]/35 bg-[var(--art-a)]/10 px-3.5 py-2 text-xs font-bold text-[var(--art-a)]"
        >
          {copied === 'share' ? 'Link copied' : 'Share'}
        </button>
        <button
          type="button"
          onClick={onDownload}
          disabled={exporting || !canDownload}
          className="rounded-pill border border-[var(--border)] px-3.5 py-2 text-xs font-semibold text-[var(--fg-muted)] transition hover:text-[var(--fg)] disabled:opacity-40"
        >
          {exporting ? '…' : 'Download'}
        </button>
        <button
          type="button"
          onClick={onFullVideo}
          className="rounded-pill bg-[var(--fg)] px-3.5 py-2 text-xs font-bold text-[var(--bg)] transition hover:opacity-90"
        >
          Full video
        </button>

        <div className="relative" ref={moreRef}>
          <button
            type="button"
            aria-label="More actions"
            aria-expanded={moreOpen}
            onClick={() => setMoreOpen((v) => !v)}
            className="rounded-pill border border-[var(--border)] px-3 py-2 text-xs font-semibold text-[var(--fg-muted)] hover:text-[var(--fg)]"
          >
            ···
          </button>
          {moreOpen && (
            <div className="dock-glass absolute bottom-full right-0 z-20 mb-2 min-w-[9rem] overflow-hidden rounded-xl py-1 shadow-2xl">
              <button
                type="button"
                onClick={() => {
                  onReset()
                  setMoreOpen(false)
                }}
                className="block w-full px-4 py-2 text-left text-xs font-semibold text-[var(--fg)] hover:bg-white/8"
              >
                Reset
              </button>
              <button
                type="button"
                onClick={() => {
                  onJson()
                  setMoreOpen(false)
                }}
                className="block w-full px-4 py-2 text-left text-xs font-semibold text-[var(--fg)] hover:bg-white/8"
              >
                {copied === 'json' ? '✓ JSON' : 'JSON'}
              </button>
            </div>
          )}
        </div>
      </div>
      {shareError && <p className="text-center text-xs text-amber-200">{shareError}</p>}
    </div>
  )
}
