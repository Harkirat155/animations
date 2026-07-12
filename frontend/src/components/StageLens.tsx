import { motion } from 'motion/react'

interface Props {
  imageUrl: string | null
  loading: boolean
  error: string | null
  renderSeconds: number | null
  nFrames?: number | null
  motionMode?: boolean
  templateLabel?: string | null
  layoutId?: string
  focus?: boolean
  onToggleMotion?: () => void
  onFocus?: () => void
}

export default function StageLens({
  imageUrl,
  loading,
  error,
  renderSeconds,
  nFrames,
  motionMode,
  templateLabel,
  layoutId = 'stage-lens',
  focus = false,
  onToggleMotion,
  onFocus,
}: Props) {
  return (
    <div className={`flex flex-col items-center gap-2 ${focus ? 'w-full max-w-4xl' : 'w-full'}`}>
      <motion.div
        layoutId={layoutId}
        className={`stage-lens relative aspect-square w-full ${
          focus ? 'max-w-4xl stage-lens-focus' : 'max-w-2xl'
        }`}
      >
        {imageUrl && (
          <img
            src={imageUrl}
            alt="preview"
            data-template={templateLabel ?? undefined}
            className="h-full w-full object-cover"
          />
        )}

        {loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/40 backdrop-blur-[2px]">
            <div className="loading-ring size-12 rounded-full border border-[var(--art-a)]/30 border-t-[var(--art-a)]" />
            <span className="font-label text-[10px] uppercase tracking-[0.2em] text-white/60">
              Rendering
            </span>
          </div>
        )}

        {error && !loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/75 p-6 text-center text-sm text-rose-200">
            {error}
          </div>
        )}

        {!imageUrl && !loading && !error && (
          <div className="flex h-full items-center justify-center px-8 text-center">
            <p className="text-sm text-[var(--fg-muted)]">Loading preview…</p>
          </div>
        )}

        {imageUrl && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 via-black/15 to-transparent p-3 pt-12">
            <div className="flex flex-wrap items-center gap-2">
              {templateLabel && (
                <span className="font-label rounded-full border border-white/10 bg-black/35 px-2.5 py-1 text-[10px] uppercase tracking-[0.12em] text-white/70">
                  {templateLabel}
                </span>
              )}
              {motionMode && nFrames != null && nFrames > 1 && (
                <span className="font-label rounded-full border border-[var(--art-a)]/25 bg-black/40 px-2.5 py-1 text-[10px] uppercase tracking-[0.12em] text-[var(--art-a)]">
                  Motion · {nFrames}f
                </span>
              )}
              {renderSeconds != null && (
                <span className="font-label text-[10px] text-white/40">
                  {renderSeconds.toFixed(2)}s
                </span>
              )}
            </div>
          </div>
        )}

        <div className="pointer-events-auto absolute right-3 top-3 flex gap-1.5">
          {onToggleMotion && (
            <button
              type="button"
              onClick={onToggleMotion}
              className={`rounded-full border px-3 py-1.5 text-[11px] font-semibold backdrop-blur-md transition ${
                motionMode
                  ? 'border-[var(--art-a)]/35 bg-black/50 text-[var(--art-a)]'
                  : 'border-white/15 bg-black/50 text-white/60'
              }`}
            >
              {motionMode ? 'Motion' : 'Still'}
            </button>
          )}
          {onFocus && imageUrl && (
            <button
              type="button"
              onClick={onFocus}
              className="rounded-full border border-white/15 bg-black/50 px-3 py-1.5 text-[11px] font-semibold text-white/60 backdrop-blur-md transition hover:text-white"
            >
              Focus
            </button>
          )}
        </div>
      </motion.div>
    </div>
  )
}
