import { AnimatePresence, motion } from 'motion/react'

interface Props {
  /** Live preview / motion WebP when composing */
  imageUrl: string | null
  /** Featured look thumb on Discover */
  discoverUrl?: string | null
  intensity?: number
  mode: 'looks' | 'systems' | 'focus'
}

export default function LivingBackdrop({
  imageUrl,
  discoverUrl,
  intensity = 0.42,
  mode,
}: Props) {
  const src = mode === 'looks' ? (discoverUrl ?? imageUrl) : imageUrl
  const blur = mode === 'focus' ? 28 : mode === 'systems' ? 56 : 40
  const op = mode === 'focus' ? Math.min(intensity + 0.15, 0.65) : intensity

  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden>
      {!src && <div className="mesh-ambient" />}
      <AnimatePresence mode="sync">
        {src && (
          <motion.div
            key={src}
            className="absolute inset-0"
            initial={{ opacity: 0, scale: 1.08 }}
            animate={{ opacity: 1, scale: 1.12 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
          >
            <img
              src={src}
              alt=""
              className={`h-full w-full object-cover ${mode === 'looks' ? 'ken-burns' : ''}`}
              style={{
                filter: `blur(${blur}px) saturate(1.25) brightness(0.85)`,
                opacity: op,
                transform: 'scale(1.15)',
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>
      <div className="veil" />
    </div>
  )
}
