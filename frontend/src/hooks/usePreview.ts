import { useEffect, useRef, useState } from 'react'
import {
  fetchMotionPreview,
  fetchPreview,
  PreviewApiError,
} from '../api'
import type { Params } from '../types'

export interface PreviewState {
  previewUrl: string | null
  previewBlob: Blob | null
  renderSeconds: number | null
  nFrames: number | null
  loading: boolean
  error: string | null
}

export function usePreview(
  template: string | null,
  params: Params | null,
  motionOn: boolean,
): PreviewState {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null)
  const [renderSeconds, setRenderSeconds] = useState<number | null>(null)
  const [nFrames, setNFrames] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!template || !params) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setLoading(true)
      setError(null)
      const fetcher = motionOn
        ? fetchMotionPreview(template, params, 6)
        : fetchPreview(template, params)
      fetcher
        .then((result) => {
          setPreviewUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev)
            return result.url
          })
          setPreviewBlob(result.blob ?? null)
          setRenderSeconds(result.renderSeconds)
          setNFrames(result.nFrames ?? 1)
        })
        .catch((e) =>
          setError(e instanceof PreviewApiError ? e.message : String(e)),
        )
        .finally(() => setLoading(false))
    }, motionOn ? 600 : 350)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [template, params, motionOn])

  return { previewUrl, previewBlob, renderSeconds, nFrames, loading, error }
}
