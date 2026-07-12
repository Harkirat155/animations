import { useRef, useState } from 'react'
import type { GradientStop } from '../types'
import { hexToRgb, rgbCss, rgbToHex } from '../color'

interface Props {
  stops: GradientStop[]
  onChange: (stops: GradientStop[]) => void
}

/** Draggable multi-stop gradient editor: matches the pipeline's own
 * `[[position, [r,g,b]], ...]` format exactly, so what's built here is
 * what gets sent straight through to the render backend. */
export default function GradientEditor({ stops, onChange }: Props) {
  const trackRef = useRef<HTMLDivElement>(null)
  const [selected, setSelected] = useState(0)
  const [dragging, setDragging] = useState<number | null>(null)

  const sorted = [...stops].sort((a, b) => a[0] - b[0])
  const css = `linear-gradient(to right, ${sorted
    .map(([pos, rgb]) => `${rgbCss(rgb)} ${pos * 100}%`)
    .join(', ')})`

  function positionFromEvent(e: { clientX: number }): number {
    const track = trackRef.current
    if (!track) return 0
    const rect = track.getBoundingClientRect()
    return Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
  }

  function updateStop(index: number, next: Partial<{ pos: number; rgb: [number, number, number] }>) {
    const copy = stops.map((s) => [s[0], s[1]] as GradientStop)
    if (next.pos !== undefined) copy[index][0] = next.pos
    if (next.rgb !== undefined) copy[index][1] = next.rgb
    onChange(copy)
  }

  function addStopAt(pos: number) {
    // interpolate a starting color from the two neighboring stops
    const before = [...sorted].reverse().find((s) => s[0] <= pos) ?? sorted[0]
    const after = sorted.find((s) => s[0] >= pos) ?? sorted[sorted.length - 1]
    const t = after[0] === before[0] ? 0 : (pos - before[0]) / (after[0] - before[0])
    const rgb: [number, number, number] = [
      Math.round(before[1][0] + t * (after[1][0] - before[1][0])),
      Math.round(before[1][1] + t * (after[1][1] - before[1][1])),
      Math.round(before[1][2] + t * (after[1][2] - before[1][2])),
    ]
    const next = [...stops, [pos, rgb] as GradientStop]
    onChange(next)
    setSelected(next.length - 1)
  }

  function removeStop(index: number) {
    if (stops.length <= 2) return // gradients need >=2 stops
    onChange(stops.filter((_, i) => i !== index))
    setSelected(0)
  }

  return (
    <div className="space-y-2">
      <div
        ref={trackRef}
        className="relative h-9 cursor-copy rounded-xl border border-[var(--border)] shadow-[inset_0_0_20px_rgb(0_0_0/0.35)]"
        style={{ background: css }}
        onDoubleClick={(e) => addStopAt(positionFromEvent(e))}
        onMouseMove={(e) => {
          if (dragging === null) return
          updateStop(dragging, { pos: positionFromEvent(e) })
        }}
        onMouseUp={() => setDragging(null)}
        onMouseLeave={() => setDragging(null)}
      >
        {stops.map((stop, i) => (
          <button
            key={i}
            aria-label={`gradient stop ${i}`}
            onMouseDown={() => {
              setDragging(i)
              setSelected(i)
            }}
            className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 shadow-md"
            style={{
              left: `${stop[0] * 100}%`,
              background: rgbCss(stop[1]),
              borderColor: i === selected ? 'var(--fg)' : 'rgba(255,255,255,0.35)',
            }}
          />
        ))}
      </div>
      <div className="flex items-center gap-2 text-xs text-[var(--fg-muted)]">
        <input
          type="color"
          value={rgbToHex(stops[selected][1])}
          onChange={(e) => updateStop(selected, { rgb: hexToRgb(e.target.value) })}
          className="h-6 w-8 cursor-pointer rounded border-0 bg-transparent"
        />
        <span className="font-label">
          stop {selected + 1}/{stops.length} · {(stops[selected][0] * 100).toFixed(0)}%
        </span>
        <button
          type="button"
          onClick={() => removeStop(selected)}
          disabled={stops.length <= 2}
          className="ml-auto rounded-pill px-2 py-0.5 hover:bg-white/10 disabled:opacity-30"
        >
          remove
        </button>
      </div>
      <p className="text-[11px] text-[var(--fg-muted)] opacity-70">
        Double-click the bar to add a stop · drag a bead to move it
      </p>
    </div>
  )
}
