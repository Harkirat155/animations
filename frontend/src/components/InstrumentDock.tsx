import type { Params, TemplateSchema } from '../types'
import type { SemanticState } from '../semantic'
import PlayPanel from './PlayPanel'
import ParamPanel from './ParamPanel'

interface Props {
  schema: TemplateSchema
  params: Params
  craftMode: 'play' | 'craft'
  semantic: SemanticState
  onSemanticChange: (s: SemanticState) => void
  onParamsChange: (p: Params) => void
  onOpenCraft: () => void
  onOpenPlay: () => void
  mobileSheet?: boolean
}

export default function InstrumentDock({
  schema,
  params,
  craftMode,
  semantic,
  onSemanticChange,
  onParamsChange,
  onOpenCraft,
  onOpenPlay,
  mobileSheet = false,
}: Props) {
  const body = (
    <>
      <div className="mb-4 flex items-center justify-between border-b border-[var(--border)] pb-3">
        <p className="font-label text-[10px] uppercase tracking-[0.18em] text-[var(--fg-muted)]">
          {craftMode === 'play' ? 'Simple dials' : 'All dials'}
        </p>
        {craftMode === 'craft' && (
          <button
            type="button"
            onClick={onOpenPlay}
            className="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)]"
          >
            Simple
          </button>
        )}
      </div>

      {craftMode === 'play' ? (
        <PlayPanel
          state={semantic}
          onChange={onSemanticChange}
          onOpenCraft={onOpenCraft}
        />
      ) : (
        <ParamPanel schema={schema} params={params} onChange={onParamsChange} />
      )}
    </>
  )

  if (mobileSheet) {
    return (
      <div className="bottom-sheet max-h-[55dvh] overflow-hidden">
        <div className="px-4 pb-2 pt-3">
          <div className="sheet-handle" />
        </div>
        <div className="scroll-thin max-h-[calc(55dvh-28px)] overflow-y-auto px-5 pb-8">
          {body}
        </div>
      </div>
    )
  }

  return (
    <div className="dock-glass scroll-thin max-h-[min(78dvh,860px)] overflow-y-auto overscroll-contain p-5 sm:p-6">
      {body}
    </div>
  )
}
