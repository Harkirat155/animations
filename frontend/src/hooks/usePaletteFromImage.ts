import { useEffect } from 'react'

/** Sample a couple of average colors from the preview and push to CSS vars. */
export function usePaletteFromImage(imageUrl: string | null) {
  useEffect(() => {
    if (!imageUrl) {
      document.documentElement.style.removeProperty('--art-a')
      document.documentElement.style.removeProperty('--art-b')
      return
    }

    let cancelled = false
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      if (cancelled) return
      try {
        const size = 32
        const canvas = document.createElement('canvas')
        canvas.width = size
        canvas.height = size
        const ctx = canvas.getContext('2d', { willReadFrequently: true })
        if (!ctx) return
        ctx.drawImage(img, 0, 0, size, size)
        const data = ctx.getImageData(0, 0, size, size).data

        const samples = [
          sampleRegion(data, size, 0.15, 0.15, 0.35, 0.35),
          sampleRegion(data, size, 0.55, 0.55, 0.85, 0.85),
          sampleRegion(data, size, 0.4, 0.4, 0.6, 0.6),
        ].filter(Boolean) as string[]

        if (samples[0]) {
          document.documentElement.style.setProperty('--art-a', samples[0])
        }
        if (samples[1] || samples[2]) {
          document.documentElement.style.setProperty(
            '--art-b',
            samples[1] ?? samples[2]!,
          )
        }
      } catch {
        /* blob CORS or canvas taint — keep defaults */
      }
    }
    img.src = imageUrl

    return () => {
      cancelled = true
    }
  }, [imageUrl])
}

function sampleRegion(
  data: Uint8ClampedArray,
  size: number,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
): string | null {
  const ix0 = Math.floor(x0 * size)
  const iy0 = Math.floor(y0 * size)
  const ix1 = Math.ceil(x1 * size)
  const iy1 = Math.ceil(y1 * size)
  let r = 0
  let g = 0
  let b = 0
  let n = 0
  for (let y = iy0; y < iy1; y++) {
    for (let x = ix0; x < ix1; x++) {
      const i = (y * size + x) * 4
      const alpha = data[i + 3]
      if (alpha < 20) continue
      // skip near-black (background)
      if (data[i] + data[i + 1] + data[i + 2] < 30) continue
      r += data[i]
      g += data[i + 1]
      b += data[i + 2]
      n++
    }
  }
  if (n < 4) return null
  r = Math.round(r / n)
  g = Math.round(g / n)
  b = Math.round(b / n)
  // Lift very dark samples toward phosphor readability
  const lift = 40
  r = Math.min(255, r + lift * 0.3)
  g = Math.min(255, g + lift * 0.35)
  b = Math.min(255, b + lift * 0.2)
  return `rgb(${Math.round(r)} ${Math.round(g)} ${Math.round(b)})`
}
