interface Props {
  imageUrl: string | null
  loading: boolean
  error: string | null
  renderSeconds: number | null
  nFrames?: number | null
  motionMode?: boolean
  templateLabel?: string | null
}

export default function PreviewPane({
  imageUrl,
  loading,
  error,
  renderSeconds,
  nFrames,
  motionMode,
  templateLabel,
}: Props) {
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="preview-glow relative aspect-square w-full max-w-xl overflow-hidden rounded-[28px] border border-[var(--border)] bg-black/50">
        {imageUrl && (
          <img
            src={imageUrl}
            alt="preview"
            data-template={templateLabel ?? undefined}
            className="h-full w-full object-cover"
          />
        )}
        {loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/45 backdrop-blur-sm">
            <div className="size-10 animate-spin rounded-full border-2 border-white/15 border-t-[var(--accent)]" />
            <span className="font-label text-[10px] uppercase tracking-[0.16em] text-[var(--fg-muted)]">
              Rendering
            </span>
          </div>
        )}
        {error && !loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/70 p-6 text-center text-sm text-rose-200">
            {error}
          </div>
        )}
        {!imageUrl && !loading && !error && (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
            <span className="font-label text-[10px] uppercase tracking-[0.2em] text-[var(--accent)]">Lumen</span>
            <p className="font-display text-2xl font-semibold tracking-tight text-[var(--fg)]">
              Pick a Look to begin
            </p>
            <p className="max-w-xs text-sm text-[var(--fg-muted)]">
              Curated mathematical organisms — tweak, watch them move, share the living link.
            </p>
          </div>
        )}

        {imageUrl && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-4 pt-12">
            <div className="flex flex-wrap items-center gap-2">
              {motionMode && nFrames != null && nFrames > 1 && (
                <span className="font-label rounded-pill border border-[var(--accent)]/30 bg-[var(--accent)]/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.12em] text-[var(--accent)]">
                  Motion · {nFrames}f
                </span>
              )}
              {templateLabel && (
                <span className="font-label rounded-pill border border-white/10 bg-black/30 px-2.5 py-1 text-[10px] uppercase tracking-[0.12em] text-white/70">
                  {templateLabel}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-[var(--fg-muted)]">
        {renderSeconds != null && (
          <span className="font-label">{renderSeconds.toFixed(2)}s</span>
        )}
        <span className="rounded-pill border border-[var(--border)] px-2.5 py-1">
          Preview is indicative — full render is higher fidelity
        </span>
      </div>
    </div>
  )
}
