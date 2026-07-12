import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import type { Params, TemplateSchema, TemplateSummary } from '../../types'
import type { SemanticState } from '../../semantic'
import StageLens from '../StageLens'
import InstrumentDock from '../InstrumentDock'
import ActionCluster from '../ActionCluster'
import SystemRail from '../SystemRail'

interface Props {
  templates: TemplateSummary[]
  selectedTemplate: string | null
  schema: TemplateSchema | null
  params: Params | null
  craftMode: 'play' | 'craft'
  semantic: SemanticState
  previewUrl: string | null
  loading: boolean
  error: string | null
  renderSeconds: number | null
  nFrames: number | null
  motionOn: boolean
  copied: 'json' | 'share' | null
  exporting: boolean
  shareError: string | null
  onCraftMode: (m: 'play' | 'craft') => void
  onSemanticChange: (s: SemanticState) => void
  onParamsChange: (p: Params) => void
  onSelectTemplate: (name: string) => void
  onToggleMotion: () => void
  onSurprise: () => void
  onReset: () => void
  onShare: () => void
  onDownload: () => void
  onJson: () => void
  onFullVideo: () => void
  onFocus: () => void
}

function useIsNarrow(breakpointPx = 1280) {
  const [narrow, setNarrow] = useState(false)
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${breakpointPx - 1}px)`)
    const sync = () => setNarrow(mq.matches)
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [breakpointPx])
  return narrow
}

/** Systems studio — instrument rail + large stage + dials. */
export default function SystemsPage({
  templates,
  selectedTemplate,
  schema,
  params,
  craftMode,
  semantic,
  previewUrl,
  loading,
  error,
  renderSeconds,
  nFrames,
  motionOn,
  copied,
  exporting,
  shareError,
  onCraftMode,
  onSemanticChange,
  onParamsChange,
  onSelectTemplate,
  onToggleMotion,
  onSurprise,
  onReset,
  onShare,
  onDownload,
  onJson,
  onFullVideo,
  onFocus,
}: Props) {
  const isNarrow = useIsNarrow(1280)
  const ready = Boolean(schema && params && selectedTemplate)

  return (
    <motion.div
      id="main-content"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.35 }}
      className={`relative z-10 mx-auto max-w-[1440px] px-3 pt-1 sm:px-6 sm:pt-2 ${
        isNarrow && ready ? 'pb-28' : 'pb-12'
      }`}
    >
      <div className="mb-4">
        <SystemRail
          templates={templates}
          selected={selectedTemplate}
          onSelect={onSelectTemplate}
        />
      </div>

      {!ready && (
        <div className="dock-glass flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
          <p className="font-display text-lg font-semibold">Loading system…</p>
        </div>
      )}

      {ready && schema && params && selectedTemplate && (
        <div
          className={`grid grid-cols-1 gap-5 xl:items-start ${
            isNarrow ? '' : 'xl:grid-cols-[minmax(0,1fr)_360px]'
          }`}
        >
          <div className="order-1 space-y-3">
            <StageLens
              imageUrl={previewUrl}
              loading={loading}
              error={error}
              renderSeconds={renderSeconds}
              nFrames={nFrames}
              motionMode={motionOn}
              templateLabel={schema.label}
              onToggleMotion={onToggleMotion}
              onFocus={onFocus}
            />
            <ActionCluster
              motionOn={motionOn}
              onToggleMotion={onToggleMotion}
              onSurprise={onSurprise}
              onReset={onReset}
              onShare={onShare}
              onDownload={onDownload}
              onJson={onJson}
              onFullVideo={onFullVideo}
              copied={copied}
              exporting={exporting}
              canDownload={Boolean(previewUrl)}
              shareError={shareError}
            />
          </div>

          {!isNarrow && (
            <div className="order-2 xl:sticky xl:top-24">
              <InstrumentDock
                schema={schema}
                params={params}
                craftMode={craftMode}
                semantic={semantic}
                onSemanticChange={onSemanticChange}
                onParamsChange={onParamsChange}
                onOpenCraft={() => onCraftMode('craft')}
                onOpenPlay={() => onCraftMode('play')}
              />
            </div>
          )}
        </div>
      )}

      {ready && schema && params && isNarrow && (
        <div className="fixed inset-x-0 bottom-0 z-30">
          <InstrumentDock
            schema={schema}
            params={params}
            craftMode={craftMode}
            semantic={semantic}
            onSemanticChange={onSemanticChange}
            onParamsChange={onParamsChange}
            onOpenCraft={() => onCraftMode('craft')}
            onOpenPlay={() => onCraftMode('play')}
            mobileSheet
          />
        </div>
      )}
    </motion.div>
  )
}
