import { useCallback, useEffect, useRef, useState } from 'react'
import {
  fetchLooks,
  fetchMotionPreview,
  fetchPreview,
  fetchSchema,
  fetchTemplates,
  PreviewApiError,
} from './api'
import type { Look, Params, TemplateSchema, TemplateSummary } from './types'
import { randomizeAll } from './randomize'
import { mergeParams, toPresetJson } from './preset'
import { decodeShare, tokenFromLocation, writeShareUrl } from './share'
import TemplateGallery from './components/TemplateGallery'
import LooksGallery from './components/LooksGallery'
import ParamPanel from './components/ParamPanel'
import PreviewPane from './components/PreviewPane'

function defaultParams(schema: TemplateSchema): Params {
  return Object.fromEntries(schema.fields.map((f) => [f.key, f.default])) as Params
}

// schema and params must never be observable out of sync with each other —
// a field's visibleIf check reads params keyed by the CURRENT schema's field
// names, so if schema updated to template B while params still held template
// A's values (or vice versa) for even one render, a visibleIf lookup against
// a key the stale params dict doesn't have silently evaluates to false and
// hides fields that should be visible. Keeping them in one state object
// makes that class of bug structurally impossible instead of relying on
// setSchema/setParams happening to batch into the same commit.
interface View {
  schema: TemplateSchema
  params: Params
  lookId: string | null
}

type CraftMode = 'play' | 'craft'

export default function App() {
  const [templates, setTemplates] = useState<TemplateSummary[]>([])
  const [looks, setLooks] = useState<Look[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<View | null>(null)
  const [mode, setMode] = useState<CraftMode>('play')
  const [motion, setMotion] = useState(true)

  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [renderSeconds, setRenderSeconds] = useState<number | null>(null)
  const [nFrames, setNFrames] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState<'json' | 'share' | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)
  const [bootstrapped, setBootstrapped] = useState(false)

  // Load catalogs once
  useEffect(() => {
    Promise.all([fetchTemplates(), fetchLooks()])
      .then(([t, l]) => {
        setTemplates(t)
        setLooks(l)
      })
      .catch((e) => setError(String(e)))
  }, [])

  // Restore share link once catalogs are ready (schema still fetched on select)
  useEffect(() => {
    if (bootstrapped || templates.length === 0) return
    const token = tokenFromLocation()
    if (!token) {
      setBootstrapped(true)
      return
    }
    let cancelled = false
    ;(async () => {
      const state = await decodeShare(token)
      if (cancelled || !state) {
        setBootstrapped(true)
        return
      }
      setSelected(state.t)
      try {
        const schema = await fetchSchema(state.t)
        if (cancelled) return
        setView({
          schema,
          params: mergeParams(schema, state.p),
          lookId: state.look ?? null,
        })
      } catch (e) {
        if (!cancelled) setError(String(e))
      } finally {
        if (!cancelled) setBootstrapped(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [templates, bootstrapped])

  // Template switch (not from look / not from share bootstrap already setting view)
  const loadTemplate = useCallback(async (name: string, partial?: Params, lookId: string | null = null) => {
    setSelected(name)
    setView(null)
    setError(null)
    try {
      const schema = await fetchSchema(name)
      setView({
        schema,
        params: partial ? mergeParams(schema, partial) : defaultParams(schema),
        lookId,
      })
    } catch (e) {
      setError(String(e))
    }
  }, [])

  const onSelectTemplate = useCallback(
    (name: string) => {
      void loadTemplate(name, undefined, null)
    },
    [loadTemplate],
  )

  const onSelectLook = useCallback(
    (look: Look) => {
      void loadTemplate(look.template, look.params, look.id)
    },
    [loadTemplate],
  )

  // Live, debounced preview
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (!selected || !view) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setLoading(true)
      setError(null)
      const fetcher = motion
        ? fetchMotionPreview(selected, view.params, 6)
        : fetchPreview(selected, view.params)
      fetcher
        .then((result) => {
          setPreviewUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev)
            return result.url
          })
          setRenderSeconds(result.renderSeconds)
          setNFrames(result.nFrames ?? 1)
        })
        .catch((e) => setError(e instanceof PreviewApiError ? e.message : String(e)))
        .finally(() => setLoading(false))
    }, motion ? 600 : 350)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [selected, view, motion])

  async function handleShare() {
    if (!selected || !view) return
    setShareError(null)
    try {
      const url = await writeShareUrl(selected, view.params, view.lookId ?? undefined)
      await navigator.clipboard.writeText(url)
      window.history.replaceState(null, '', url.slice(url.indexOf('#')))
      setCopied('share')
      setTimeout(() => setCopied(null), 1800)
    } catch (e) {
      setShareError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-white/90">
      <header className="border-b border-white/10 px-6 py-4">
        <div className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Animation Composer</h1>
            <p className="text-xs text-white/40">
              Compose living math. Export perfect loops — full video needs a subscription.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <button
              type="button"
              onClick={() => setMode('play')}
              className={`rounded-md px-2.5 py-1.5 ${
                mode === 'play' ? 'bg-violet-500/20 text-violet-100' : 'text-white/45 hover:bg-white/5'
              }`}
            >
              Play
            </button>
            <button
              type="button"
              onClick={() => setMode('craft')}
              className={`rounded-md px-2.5 py-1.5 ${
                mode === 'craft' ? 'bg-violet-500/20 text-violet-100' : 'text-white/45 hover:bg-white/5'
              }`}
            >
              Craft
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-10 px-6 py-8">
        <section>
          <div className="mb-4 flex items-baseline justify-between gap-3">
            <div>
              <h2 className="text-sm font-medium text-white/80">Looks</h2>
              <p className="text-xs text-white/35">Start from a curated composition — then make it yours.</p>
            </div>
          </div>
          <LooksGallery looks={looks} selectedId={view?.lookId ?? null} onSelect={onSelectLook} />
        </section>

        <section>
          <div className="mb-3">
            <h2 className="text-sm font-medium text-white/80">Templates</h2>
            <p className="text-xs text-white/35">Or start from a blank system with default dials.</p>
          </div>
          <TemplateGallery templates={templates} selected={selected} onSelect={onSelectTemplate} />
        </section>

        {view && (
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_380px]">
            <div className="order-2 lg:order-1">
              <div className="mb-5 flex items-start justify-between gap-4 border-b border-white/10 pb-4">
                <div>
                  <h2 className="text-base font-medium text-white/90">{view.schema.label}</h2>
                  <p className="mt-0.5 text-xs text-white/40">{view.schema.blurb}</p>
                  <p className="mt-1 text-[11px] text-white/30">Color: {view.schema.colorParadigm}</p>
                </div>
                <div className="flex shrink-0 flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setMotion((m) => !m)}
                    className={`rounded-md border px-2.5 py-1.5 text-xs ${
                      motion
                        ? 'border-emerald-400/30 bg-emerald-500/10 text-emerald-100/90'
                        : 'border-white/10 hover:bg-white/10'
                    }`}
                    title="Toggle multi-frame motion preview"
                  >
                    {motion ? '▶ Motion on' : '■ Still only'}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setView({
                        schema: view.schema,
                        params: randomizeAll(view.schema, view.params),
                        lookId: null,
                      })
                    }
                    className="rounded-md border border-white/10 px-2.5 py-1.5 text-xs hover:bg-white/10"
                    title="Randomize every dial"
                  >
                    🎲 Randomize
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setView({ schema: view.schema, params: defaultParams(view.schema), lookId: null })
                    }
                    className="rounded-md border border-white/10 px-2.5 py-1.5 text-xs hover:bg-white/10"
                    title="Reset every dial to its default"
                  >
                    ↺ Reset
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void navigator.clipboard.writeText(toPresetJson(view.params))
                      setCopied('json')
                      setTimeout(() => setCopied(null), 1500)
                    }}
                    className="rounded-md border border-white/10 px-2.5 py-1.5 text-xs hover:bg-white/10"
                    title="Copy as a preset JSON file usable with the existing CLI pipeline"
                  >
                    {copied === 'json' ? '✓ Copied' : '⧉ JSON'}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleShare()}
                    className="rounded-md border border-violet-400/30 bg-violet-500/15 px-2.5 py-1.5 text-xs text-violet-100 hover:bg-violet-500/25"
                    title="Copy a link that reloads this exact composition"
                  >
                    {copied === 'share' ? '✓ Link copied' : '↗ Share'}
                  </button>
                </div>
              </div>
              {shareError && <p className="mb-3 text-xs text-amber-300/90">{shareError}</p>}

              {mode === 'craft' ? (
                <ParamPanel
                  schema={view.schema}
                  params={view.params}
                  onChange={(params) => setView({ schema: view.schema, params, lookId: null })}
                />
              ) : (
                <div className="space-y-4 rounded-xl border border-white/10 bg-white/[0.02] p-5">
                  <p className="text-sm text-white/70">
                    You&apos;re in <span className="text-violet-200">Play</span> mode — pick a Look, toggle motion,
                    share the link. Open <span className="text-white/90">Craft</span> for every dial.
                  </p>
                  <p className="text-xs text-white/40">
                    Semantic knobs (Warmth / Chaos / Energy) land in the next pass. For now Randomize + Looks are the
                    accessible path.
                  </p>
                  <button
                    type="button"
                    onClick={() => setMode('craft')}
                    className="rounded-md border border-white/15 px-3 py-2 text-sm hover:bg-white/10"
                  >
                    Open Craft dials →
                  </button>
                </div>
              )}
            </div>
            <div className="order-1 lg:order-2">
              <PreviewPane
                imageUrl={previewUrl}
                loading={loading}
                error={error}
                renderSeconds={renderSeconds}
                nFrames={nFrames}
                motionMode={motion}
              />
              <button
                type="button"
                disabled
                title="Subscriptions aren't live yet — coming soon"
                className="mt-4 w-full cursor-not-allowed rounded-lg border border-violet-400/30 bg-violet-500/10 py-2.5 text-sm font-medium text-violet-200/60"
              >
                🔒 Subscribe to render full video
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
