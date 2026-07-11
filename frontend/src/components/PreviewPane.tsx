interface Props {
  imageUrl: string | null
  loading: boolean
  error: string | null
  renderSeconds: number | null
  nFrames?: number | null
  motionMode?: boolean
}

export default function PreviewPane({
  imageUrl,
  loading,
  error,
  renderSeconds,
  nFrames,
  motionMode,
}: Props) {
  return (
    <div className="sticky top-6 flex flex-col items-center gap-3">
      <div className="relative flex aspect-square w-full max-w-md items-center justify-center overflow-hidden rounded-2xl border border-white/10 bg-black/40">
        {imageUrl && (
          <img src={imageUrl} alt="preview" className="h-full w-full object-cover" />
        )}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="size-8 animate-spin rounded-full border-2 border-white/20 border-t-violet-400" />
          </div>
        )}
        {error && !loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/70 p-4 text-center text-sm text-red-300">
            {error}
          </div>
        )}
        {!imageUrl && !loading && !error && (
          <div className="px-6 text-center text-sm text-white/30">
            pick a Look or template to preview
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-white/35">
        {renderSeconds !== null && <span>rendered in {renderSeconds.toFixed(2)}s</span>}
        {motionMode && nFrames != null && nFrames > 1 && (
          <span className="rounded-full border border-emerald-400/20 bg-emerald-500/10 px-2 py-0.5 text-emerald-200/70">
            motion · {nFrames} frames
          </span>
        )}
        <span className="rounded-full border border-white/10 px-2 py-0.5">
          preview is indicative — the full render is higher-fidelity
        </span>
      </div>
    </div>
  )
}
