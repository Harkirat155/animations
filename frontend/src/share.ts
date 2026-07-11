import type { Params } from './types'

/** Share-link payload version — bump if the encoded shape changes. */
const VERSION = 1

export interface ShareState {
  v: number
  t: string
  p: Params
  look?: string
}

function toBase64Url(bytes: Uint8Array): string {
  let bin = ''
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]!)
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function fromBase64Url(s: string): Uint8Array {
  const pad = s.length % 4 === 0 ? '' : '='.repeat(4 - (s.length % 4))
  const b64 = s.replace(/-/g, '+').replace(/_/g, '/') + pad
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

/** Prefer native compression so gradient-heavy params still fit in a URL. */
async function compress(text: string): Promise<string> {
  if (typeof CompressionStream === 'undefined') {
    return 'u' + toBase64Url(new TextEncoder().encode(text))
  }
  const stream = new Blob([text]).stream().pipeThrough(new CompressionStream('deflate-raw'))
  const buf = await new Response(stream).arrayBuffer()
  return 'z' + toBase64Url(new Uint8Array(buf))
}

async function decompress(token: string): Promise<string> {
  const kind = token[0]
  const body = token.slice(1)
  const bytes = fromBase64Url(body)
  if (kind === 'u') {
    return new TextDecoder().decode(bytes)
  }
  if (kind === 'z') {
    if (typeof DecompressionStream === 'undefined') {
      throw new Error('compressed share link needs a modern browser')
    }
    const stream = new Blob([bytes.buffer as ArrayBuffer])
      .stream()
      .pipeThrough(new DecompressionStream('deflate-raw'))
    return await new Response(stream).text()
  }
  // Legacy: raw base64url JSON without prefix
  return new TextDecoder().decode(fromBase64Url(token))
}

export async function encodeShare(template: string, params: Params, lookId?: string): Promise<string> {
  const state: ShareState = { v: VERSION, t: template, p: params }
  if (lookId) state.look = lookId
  return compress(JSON.stringify(state))
}

export async function decodeShare(token: string): Promise<ShareState | null> {
  try {
    const text = await decompress(token)
    const data = JSON.parse(text) as ShareState
    if (!data || typeof data.t !== 'string' || typeof data.p !== 'object' || !data.p) {
      return null
    }
    return data
  } catch {
    return null
  }
}

/** Hash format: `#c=<token>` — works on GitHub Pages without SPA server rewrites. */
export function shareHashFromToken(token: string): string {
  return `#c=${token}`
}

export function tokenFromLocation(hash = window.location.hash): string | null {
  if (!hash) return null
  const raw = hash.startsWith('#') ? hash.slice(1) : hash
  if (raw.startsWith('c=')) return decodeURIComponent(raw.slice(2))
  // Also accept #/c/<token>
  const m = raw.match(/^\/?c\/(.+)$/)
  return m ? decodeURIComponent(m[1]!) : null
}

export async function writeShareUrl(template: string, params: Params, lookId?: string): Promise<string> {
  const token = await encodeShare(template, params, lookId)
  const hash = shareHashFromToken(token)
  const url = `${window.location.origin}${window.location.pathname}${hash}`
  // Soft length guard — browsers / messengers choke past ~8k
  if (url.length > 7500) {
    throw new Error('This composition is too complex to fit in a share link — try fewer gradient stops.')
  }
  return url
}
