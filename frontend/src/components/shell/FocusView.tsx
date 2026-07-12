import { motion } from 'motion/react'
import StageLens from '../StageLens'

interface Props {
  imageUrl: string | null
  loading: boolean
  error: string | null
  templateLabel: string | null
  motionOn: boolean
  nFrames: number | null
  onExit: () => void
  onShare: () => void
  onToggleMotion: () => void
}

export default function FocusView({
  imageUrl,
  loading,
  error,
  templateLabel,
  motionOn,
  nFrames,
  onExit,
  onShare,
  onToggleMotion,
}: Props) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="relative z-10 flex min-h-dvh flex-col items-center justify-center px-4 pb-16 pt-20"
    >
      <StageLens
        imageUrl={imageUrl}
        loading={loading}
        error={error}
        renderSeconds={null}
        nFrames={nFrames}
        motionMode={motionOn}
        templateLabel={templateLabel}
        focus
        onToggleMotion={onToggleMotion}
      />
      <div className="mt-6 flex gap-2">
        <button
          type="button"
          onClick={onShare}
          data-magnetic
          className="dock-glass-soft rounded-pill px-4 py-2 text-xs font-semibold"
        >
          Share
        </button>
        <button
          type="button"
          onClick={onExit}
          data-magnetic
          className="dock-glass-soft rounded-pill px-4 py-2 text-xs font-semibold"
        >
          Exit Focus
        </button>
      </div>
    </motion.div>
  )
}
