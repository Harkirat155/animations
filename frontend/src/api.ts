import type { Look, Params, TemplateSchema, TemplateSummary } from './types'

/** Production (GitHub Pages) sets VITE_API_URL to the Fly.io origin.
 * Local dev leaves it empty so Vite's `/api` proxy hits the local backend. */
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''

function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}

export class PreviewApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function fetchTemplates(): Promise<TemplateSummary[]> {
  const res = await fetch(apiUrl('/api/templates'))
  if (!res.ok) throw new PreviewApiError('failed to load templates', res.status)
  return res.json()
}

export async function fetchSchema(name: string): Promise<TemplateSchema> {
  const res = await fetch(apiUrl(`/api/templates/${name}/schema`))
  if (!res.ok) throw new PreviewApiError(`failed to load schema for ${name}`, res.status)
  return res.json()
}

export interface PreviewResult {
  url: string
  renderSeconds: number
  nFrames?: number
  mediaType?: string
}

export async function fetchPreview(template: string, params: Params): Promise<PreviewResult> {
  const res = await fetch(apiUrl('/api/preview'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template, params }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new PreviewApiError(body.detail ?? 'preview failed', res.status)
  }
  const blob = await res.blob()
  return {
    url: URL.createObjectURL(blob),
    renderSeconds: Number(res.headers.get('X-Render-Seconds') ?? 0),
    nFrames: 1,
    mediaType: 'image/png',
  }
}

export async function fetchMotionPreview(
  template: string,
  params: Params,
  nFrames = 12,
): Promise<PreviewResult> {
  const res = await fetch(apiUrl('/api/preview/motion'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template, params, n_frames: nFrames }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new PreviewApiError(body.detail ?? 'motion preview failed', res.status)
  }
  const blob = await res.blob()
  return {
    url: URL.createObjectURL(blob),
    renderSeconds: Number(res.headers.get('X-Render-Seconds') ?? 0),
    nFrames: Number(res.headers.get('X-Motion-Frames') ?? 1),
    mediaType: res.headers.get('Content-Type') ?? blob.type,
  }
}

/** Looks manifest is a static asset next to the SPA (built by scripts/build_looks.py). */
export async function fetchLooks(): Promise<Look[]> {
  const url = new URL('looks/manifest.json', window.location.origin + import.meta.env.BASE_URL).href
  const res = await fetch(url)
  if (!res.ok) return []
  const data = await res.json()
  return (data.looks ?? []) as Look[]
}
