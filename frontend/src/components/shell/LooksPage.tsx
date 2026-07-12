import type { Look } from '../../types'
import LooksCarousel from '../LooksCarousel'

interface Props {
  looks: Look[]
  selectedLookId: string | null
  seriesFilter: string | null
  onSeriesFilter: (s: string | null) => void
  onSelectLook: (look: Look) => void
  onSurpriseLook: () => void
  onHoverLook: (look: Look | null) => void
}

/** Looks — carousel owns the screen. */
export default function LooksPage({
  looks,
  selectedLookId,
  seriesFilter,
  onSeriesFilter,
  onSelectLook,
  onSurpriseLook,
  onHoverLook,
}: Props) {
  return (
    <div
      id="main-content"
      className="relative z-10 mx-auto flex min-h-[calc(100dvh-5rem)] max-w-[1200px] flex-col justify-center px-4 pb-10 pt-1 sm:px-8"
    >
      <LooksCarousel
        looks={looks}
        selectedId={selectedLookId}
        seriesFilter={seriesFilter}
        onSeriesFilter={onSeriesFilter}
        onSelect={onSelectLook}
        onHoverLook={onHoverLook}
        onSurprise={onSurpriseLook}
      />
    </div>
  )
}
