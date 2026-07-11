import { useCallback, useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import {
  downloadBlob,
  fetchExportStill,
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
import {
  applySemantic,
  DEFAULT_SEMANTIC,
  type SemanticState,
} from './semantic'
import TemplateGallery from './components/TemplateGallery'
import LooksGallery from './components/LooksGallery'
import ParamPanel from './components/ParamPanel'
import PlayPanel from './components/PlayPanel'
import PreviewPane from './components/PreviewPane'
import WaitlistModal from './components/WaitlistModal'

function defaultParams(schema: TemplateSchema): Params {
  return Object.fromEntries(schema.fields.map((f) => [f.key, f.default])) as Params
}

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
  const [motionOn, setMotionOn] = useState(true)
  const [semantic, setSemantic] = useState<SemanticState>(DEFAULT_SEMANTIC)
  const [seriesFilter, setSeriesFilter] = useState<string | null>(null)
  const [waitlistOpen, setWaitlistOpen] = useState(false)

  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null)
  const [renderSeconds, setRenderSeconds] = useState<number | null>(null)
  const [nFrames, setNFrames] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState<'json' | 'share' | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [bootstrapped, setBootstrapped] = useState(false)

  useEffect(() => {
    Promise.all([fetchTemplates(), fetchLooks()])
      .then(([t, l]) => {
        setTemplates(t)
        setLooks(l)
      })
      .catch((e) => setError(String(e)))
  }, [])

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
        setMode('craft')
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

  const loadTemplate = useCallback(async (name: string, partial?: Params, lookId: string | null = null) => {
    setSelected(name)
    setView(null)
    setError(null)
    try {
      const schema = await fetchSchema(name)
      const base = partial ? mergeParams(schema, partial) : defaultParams(schema)
      setView({ schema, params: base, lookId })
      setSemantic(DEFAULT_SEMANTIC)
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

  const onSemanticChange = useCallback(
    (next: SemanticState) => {
      setSemantic(next)
      setView((current) => {
        if (!current) return current
        // Foundation: schema defaults, then any look/share params that were loaded
        // (we keep lookId so UI can show selection, but semantic rewrites dials).
        const foundation = defaultParams(current.schema)
        return {
          schema: current.schema,
          params: applySemantic(current.schema, foundation, next),
          lookId: current.lookId,
        }
      })
    },
    [],
  )

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => {
    if (!selected || !view) return
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setLoading(true)
      setError(null)
      const fetcher = motionOn
        ? fetchMotionPreview(selected, view.params, 6)
        : fetchPreview(selected, view.params)
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
        .catch((e) => setError(e instanceof PreviewApiError ? e.message : String(e)))
        .finally(() => setLoading(false))
    }, motionOn ? 600 : 350)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [selected, view, motionOn])

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

  async function handleDownloadPreview() {
    if (!selected || !view) return
    setExporting(true)
    try {
      if (motionOn && previewBlob) {
        const ext = previewBlob.type.includes('webp') ? 'webp' : 'png'
        downloadBlob(previewBlob, `lumen-${selected}-motion.${ext}`)
      } else {
        const blob = await fetchExportStill(selected, view.params)
        downloadBlob(blob, `lumen-${selected}.png`)
      }
    } catch (e) {
      setError(e instanceof PreviewApiError ? e.message : String(e))
    } finally {
      setExporting(false)
    }
  }

  const hasStudio = Boolean(view)

  return (
    <div className="relative min-h-dvh text-[var(--fg)]">
      <div aria-hidden className="aurora-field">
        <div className="aurora-blob" />
        <div className="aurora-blob" />
        <div className="aurora-blob" />
      </div>

      <div className="relative z-10">
        <header className="border-b border-[var(--border)]/80 bg-black/20 backdrop-blur-xl">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-4 sm:px-8">
            <div className="flex items-center gap-3">
              <span className="live-dot size-2 rounded-full bg-[var(--accent)]" />
              <div>
                <div className="font-display text-lg font-bold tracking-tight">Lumen</div>
                <div className="font-label text-[10px] uppercase tracking-[0.16em] text-[var(--fg-muted)]">
                  Compose living math
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="flex rounded-pill border border-[var(--border)] bg-black/30 p-1">
                <button
                  type="button"
                  onClick={() => setMode('play')}
                  className={`rounded-pill px-3.5 py-1.5 text-xs font-semibold transition ${
                    mode === 'play' ? 'bg-[var(--fg)] text-[var(--bg)]' : 'text-[var(--fg-muted)]'
                  }`}
                >
                  Play
                </button>
                <button
                  type="button"
                  onClick={() => setMode('craft')}
                  className={`rounded-pill px-3.5 py-1.5 text-xs font-semibold transition ${
                    mode === 'craft' ? 'bg-[var(--fg)] text-[var(--bg)]' : 'text-[var(--fg-muted)]'
                  }`}
                >
                  Craft
                </button>
              </div>
              <button
                type="button"
                onClick={() => setWaitlistOpen(true)}
                className="rounded-pill bg-[var(--accent)] px-4 py-2 text-xs font-bold text-[#0b0710] transition hover:-translate-y-0.5"
              >
                Maker access
              </button>
            </div>
          </div>
        </header>

        {!hasStudio && (
          <section className="mx-auto max-w-7xl px-5 pb-10 pt-14 sm:px-8 sm:pt-20">
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
              className="max-w-3xl"
            >
              <p className="font-label inline-flex items-center gap-2 rounded-pill border border-[var(--border)] px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-[var(--fg-muted)]">
                <span className="size-1.5 rounded-full bg-[var(--accent)]" />
                Living systems studio
              </p>
              <h1
                className="font-display mt-6 font-extrabold tracking-tight"
                style={{ fontSize: 'clamp(2.6rem, 7vw, 5.5rem)', lineHeight: 0.98 }}
              >
                Compose organisms
                <br />
                <span className="text-[var(--accent)]">that move &amp; breathe.</span>
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-[var(--fg-muted)]">
                Not AI mush — deterministic mathematical systems. Pick a Look, feel the dials,
                share a living link. Full film packs when Maker opens.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => {
                    if (looks[0]) onSelectLook(looks[0])
                  }}
                  className="rounded-xl bg-[var(--fg)] px-6 py-3 text-sm font-semibold text-[var(--bg)] transition hover:-translate-y-0.5"
                >
                  Start with a Look
                </button>
                <button
                  type="button"
                  onClick={() => document.getElementById('looks')?.scrollIntoView({ behavior: 'smooth' })}
                  className="rounded-xl border border-[var(--border-strong)] px-6 py-3 text-sm font-semibold transition hover:border-[var(--accent)]"
                >
                  Browse gallery
                </button>
              </div>
            </motion.div>
          </section>
        )}

        <main className="mx-auto max-w-7xl space-y-10 px-5 py-8 sm:px-8">
          <section id="looks" className="glass p-5 sm:p-7">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="font-label text-[10px] uppercase tracking-[0.18em] text-[var(--fg-muted)]">Gallery</p>
                <h2 className="font-display text-2xl font-semibold tracking-tight">Looks</h2>
              </div>
              <p className="text-xs text-[var(--fg-muted)]">{looks.length} curated starting points</p>
            </div>
            <LooksGallery
              looks={looks}
              selectedId={view?.lookId ?? null}
              seriesFilter={seriesFilter}
              onSeriesFilter={setSeriesFilter}
              onSelect={onSelectLook}
            />
          </section>

          <section className="space-y-3">
            <div className="flex items-end justify-between gap-3">
              <div>
                <p className="font-label text-[10px] uppercase tracking-[0.18em] text-[var(--fg-muted)]">Systems</p>
                <h2 className="font-display text-xl font-semibold">Templates</h2>
              </div>
            </div>
            <TemplateGallery templates={templates} selected={selected} onSelect={onSelectTemplate} />
          </section>

          {view && (
            <section className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
              <div className="order-1 space-y-4">
                <PreviewPane
                  imageUrl={previewUrl}
                  loading={loading}
                  error={error}
                  renderSeconds={renderSeconds}
                  nFrames={nFrames}
                  motionMode={motionOn}
                  templateLabel={view.schema.label}
                />

                <div className="glass flex flex-wrap items-center justify-center gap-2 p-3">
                  <button
                    type="button"
                    onClick={() => setMotionOn((m) => !m)}
                    className={`rounded-pill border px-3.5 py-2 text-xs font-semibold transition ${
                      motionOn
                        ? 'border-[var(--accent)]/40 bg-[var(--accent)]/10 text-[var(--accent)]'
                        : 'border-[var(--border)] text-[var(--fg-muted)]'
                    }`}
                  >
                    {motionOn ? '▶ Motion' : '■ Still'}
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
                    className="rounded-pill border border-[var(--border)] px-3.5 py-2 text-xs font-semibold text-[var(--fg)] hover:border-[var(--border-strong)]"
                  >
                    🎲 Surprise
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setView({
                        schema: view.schema,
                        params: defaultParams(view.schema),
                        lookId: null,
                      })
                    }
                    className="rounded-pill border border-[var(--border)] px-3.5 py-2 text-xs font-semibold text-[var(--fg-muted)]"
                  >
                    Reset
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void navigator.clipboard.writeText(toPresetJson(view.params))
                      setCopied('json')
                      setTimeout(() => setCopied(null), 1500)
                    }}
                    className="rounded-pill border border-[var(--border)] px-3.5 py-2 text-xs font-semibold text-[var(--fg-muted)]"
                  >
                    {copied === 'json' ? '✓ JSON' : 'JSON'}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleShare()}
                    className="rounded-pill border border-[var(--accent)]/35 bg-[var(--accent)]/10 px-3.5 py-2 text-xs font-bold text-[var(--accent)]"
                  >
                    {copied === 'share' ? '✓ Link copied' : '↗ Share'}
                  </button>
                  <button
                    type="button"
                    disabled={exporting || !previewUrl}
                    onClick={() => void handleDownloadPreview()}
                    className="rounded-pill border border-[var(--border-strong)] px-3.5 py-2 text-xs font-semibold text-[var(--fg)] disabled:opacity-40"
                  >
                    {exporting ? '…' : '↓ Download preview'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setWaitlistOpen(true)}
                    className="rounded-pill bg-[var(--fg)] px-3.5 py-2 text-xs font-bold text-[var(--bg)]"
                  >
                    🔒 Full video
                  </button>
                </div>
                {shareError && <p className="text-center text-xs text-amber-200">{shareError}</p>}
              </div>

              <div className="order-2">
                <div className="glass scroll-thin max-h-[min(80dvh,900px)] overflow-y-auto p-5 sm:p-6">
                  <div className="mb-5 border-b border-[var(--border)] pb-4">
                    <h2 className="font-display text-lg font-semibold">{view.schema.label}</h2>
                    <p className="mt-1 text-xs leading-relaxed text-[var(--fg-muted)]">{view.schema.blurb}</p>
                  </div>
                  {mode === 'play' ? (
                    <PlayPanel
                      state={semantic}
                      onChange={onSemanticChange}
                      onOpenCraft={() => setMode('craft')}
                    />
                  ) : (
                    <ParamPanel
                      schema={view.schema}
                      params={view.params}
                      onChange={(params) => setView({ schema: view.schema, params, lookId: null })}
                    />
                  )}
                </div>
              </div>
            </section>
          )}

          <footer className="border-t border-[var(--border)] py-10 text-center">
            <p className="font-display text-lg font-semibold">Lumen</p>
            <p className="mt-2 text-sm text-[var(--fg-muted)]">
              Deterministic generative systems · free to compose · Maker for film packs
            </p>
            <p className="font-label mt-4 text-[10px] uppercase tracking-[0.16em] text-[var(--fg-muted)]">
              Built for the scroll — meant for craft
            </p>
          </footer>
        </main>
      </div>

      <WaitlistModal open={waitlistOpen} onClose={() => setWaitlistOpen(false)} />
    </div>
  )
}
