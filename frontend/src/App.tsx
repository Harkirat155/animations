import { useCallback, useEffect, useState } from 'react'
import {
  downloadBlob,
  fetchExportStill,
  fetchLooks,
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
import { usePreview } from './hooks/usePreview'
import { usePaletteFromImage } from './hooks/usePaletteFromImage'
import LivingBackdrop from './components/LivingBackdrop'
import TopBar from './components/shell/TopBar'
import LooksPage from './components/shell/LooksPage'
import SystemsPage from './components/shell/SystemsPage'
import FocusView from './components/shell/FocusView'
import WaitlistModal from './components/WaitlistModal'

function defaultParams(schema: TemplateSchema): Params {
  return Object.fromEntries(schema.fields.map((f) => [f.key, f.default])) as Params
}

interface View {
  schema: TemplateSchema
  params: Params
  lookId: string | null
}

/** Primary nav pages (+ focus overlay). */
type AppPage = 'looks' | 'systems' | 'focus'
type CraftMode = 'play' | 'craft'

export default function App() {
  const [templates, setTemplates] = useState<TemplateSummary[]>([])
  const [looks, setLooks] = useState<Look[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<View | null>(null)
  const [page, setPage] = useState<AppPage>('looks')
  const [craftMode, setCraftMode] = useState<CraftMode>('play')
  const [motionOn, setMotionOn] = useState(true)
  const [semantic, setSemantic] = useState<SemanticState>(DEFAULT_SEMANTIC)
  const [seriesFilter, setSeriesFilter] = useState<string | null>(null)
  const [waitlistOpen, setWaitlistOpen] = useState(false)
  const [hoverDiscoverUrl, setHoverDiscoverUrl] = useState<string | null>(null)
  const [featuredUrl, setFeaturedUrl] = useState<string | null>(null)

  const [copied, setCopied] = useState<'json' | 'share' | null>(null)
  const [shareError, setShareError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [bootstrapped, setBootstrapped] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const preview = usePreview(selected, view?.params ?? null, motionOn)
  usePaletteFromImage(preview.previewUrl)

  useEffect(() => {
    Promise.all([fetchTemplates(), fetchLooks()])
      .then(([t, l]) => {
        setTemplates(t)
        setLooks(l)
        const withThumb = l.find((x) => x.thumb)
        if (withThumb?.thumb) {
          setFeaturedUrl(
            new URL(withThumb.thumb, window.location.origin + import.meta.env.BASE_URL).href,
          )
        }
      })
      .catch((e) => setLoadError(String(e)))
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
        setCraftMode('craft')
        setPage('systems')
      } catch (e) {
        if (!cancelled) setLoadError(String(e))
      } finally {
        if (!cancelled) setBootstrapped(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [templates, bootstrapped])

  const loadTemplate = useCallback(
    async (
      name: string,
      partial?: Params,
      lookId: string | null = null,
      opts?: { navigate?: boolean },
    ) => {
      setSelected(name)
      setLoadError(null)
      try {
        const schema = await fetchSchema(name)
        const base = partial ? mergeParams(schema, partial) : defaultParams(schema)
        setView({ schema, params: base, lookId })
        setSemantic(DEFAULT_SEMANTIC)
        if (opts?.navigate !== false) {
          setPage((p) => (p === 'focus' ? 'focus' : 'systems'))
        }
      } catch (e) {
        setLoadError(String(e))
      }
    },
    [],
  )

  // Seed Systems with a random instrument so the page is never empty.
  // Runs after share bootstrap; does not leave Looks.
  useEffect(() => {
    if (!bootstrapped || templates.length === 0 || selected) return
    const pick = templates[Math.floor(Math.random() * templates.length)]
    void loadTemplate(pick.name, undefined, null, { navigate: false })
  }, [bootstrapped, templates, selected, loadTemplate])

  const onSelectTemplate = useCallback(
    (name: string) => {
      void loadTemplate(name, undefined, null, { navigate: true })
    },
    [loadTemplate],
  )

  const onSelectLook = useCallback(
    (look: Look) => {
      void loadTemplate(look.template, look.params, look.id, { navigate: true })
    },
    [loadTemplate],
  )

  const onSurpriseLook = useCallback(() => {
    const pool = looks.filter((l) => Boolean(l.thumb))
    if (pool.length === 0) return
    const look = pool[Math.floor(Math.random() * pool.length)]
    onSelectLook(look)
  }, [looks, onSelectLook])

  const onSemanticChange = useCallback((next: SemanticState) => {
    setSemantic(next)
    setView((current) => {
      if (!current) return current
      const foundation = defaultParams(current.schema)
      return {
        schema: current.schema,
        params: applySemantic(current.schema, foundation, next),
        lookId: current.lookId,
      }
    })
  }, [])

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
      if (motionOn && preview.previewBlob) {
        const ext = preview.previewBlob.type.includes('webp') ? 'webp' : 'png'
        downloadBlob(preview.previewBlob, `lumen-${selected}-motion.${ext}`)
      } else {
        const blob = await fetchExportStill(selected, view.params)
        downloadBlob(blob, `lumen-${selected}.png`)
      }
    } catch (e) {
      setLoadError(e instanceof PreviewApiError ? e.message : String(e))
    } finally {
      setExporting(false)
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      if (e.key === '?' || (e.key === '/' && e.shiftKey)) {
        e.preventDefault()
        setHelpOpen((v) => !v)
        return
      }
      if (e.key === 'Escape') {
        if (helpOpen) setHelpOpen(false)
        else if (waitlistOpen) setWaitlistOpen(false)
        else if (page === 'focus') setPage('systems')
        else if (page === 'systems') setPage('looks')
        return
      }
      if (e.key === ' ' && page === 'systems' && view) {
        e.preventDefault()
        setPage('focus')
        return
      }
      if (e.key === '1' && page === 'systems') setCraftMode('play')
      if (e.key === '2' && page === 'systems') setCraftMode('craft')
      if ((e.key === 'm' || e.key === 'M') && view) setMotionOn((m) => !m)
      if ((e.key === 's' || e.key === 'S') && view && page === 'systems' && !e.metaKey && !e.ctrlKey) {
        setView({
          schema: view.schema,
          params: randomizeAll(view.schema, view.params),
          lookId: null,
        })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [page, view, helpOpen, waitlistOpen])

  const discoverBg = hoverDiscoverUrl ?? featuredUrl
  const error = loadError ?? preview.error
  const backdropMode = page === 'looks' ? 'looks' : page === 'focus' ? 'focus' : 'systems'

  return (
    <div className="relative min-h-dvh text-[var(--fg)]">
      <LivingBackdrop
        imageUrl={preview.previewUrl}
        discoverUrl={discoverBg}
        mode={backdropMode}
        intensity={page === 'focus' ? 0.5 : 0.4}
      />

      <div className="relative z-10">
        <TopBar
          page={page}
          systemLabel={view?.schema.label}
          onNavigate={(p) => setPage(p)}
          onMaker={() => setWaitlistOpen(true)}
          onExitFocus={() => setPage('systems')}
        />

        {page === 'looks' && (
          <LooksPage
            looks={looks}
            selectedLookId={view?.lookId ?? null}
            seriesFilter={seriesFilter}
            onSeriesFilter={setSeriesFilter}
            onSelectLook={onSelectLook}
            onSurpriseLook={onSurpriseLook}
            onHoverLook={(look) => {
              if (!look?.thumb) {
                setHoverDiscoverUrl(null)
                return
              }
              setHoverDiscoverUrl(
                new URL(look.thumb, window.location.origin + import.meta.env.BASE_URL).href,
              )
            }}
          />
        )}

        {page === 'systems' && (
          <SystemsPage
            templates={templates}
            selectedTemplate={selected}
            schema={view?.schema ?? null}
            params={view?.params ?? null}
            craftMode={craftMode}
            semantic={semantic}
            previewUrl={preview.previewUrl}
            loading={preview.loading}
            error={error}
            renderSeconds={preview.renderSeconds}
            nFrames={preview.nFrames}
            motionOn={motionOn}
            copied={copied}
            exporting={exporting}
            shareError={shareError}
            onCraftMode={setCraftMode}
            onSemanticChange={onSemanticChange}
            onParamsChange={(params) => {
              if (!view) return
              setView({ schema: view.schema, params, lookId: null })
            }}
            onSelectTemplate={onSelectTemplate}
            onToggleMotion={() => setMotionOn((m) => !m)}
            onSurprise={() => {
              if (!view) return
              setView({
                schema: view.schema,
                params: randomizeAll(view.schema, view.params),
                lookId: null,
              })
            }}
            onReset={() => {
              if (!view) return
              setView({
                schema: view.schema,
                params: defaultParams(view.schema),
                lookId: null,
              })
            }}
            onShare={() => void handleShare()}
            onDownload={() => void handleDownloadPreview()}
            onJson={() => {
              if (!view) return
              void navigator.clipboard.writeText(toPresetJson(view.params))
              setCopied('json')
              setTimeout(() => setCopied(null), 1500)
            }}
            onFullVideo={() => setWaitlistOpen(true)}
            onFocus={() => setPage('focus')}
          />
        )}

        {page === 'focus' && view && (
          <FocusView
            imageUrl={preview.previewUrl}
            loading={preview.loading}
            error={error}
            templateLabel={view.schema.label}
            motionOn={motionOn}
            nFrames={preview.nFrames}
            onExit={() => setPage('systems')}
            onShare={() => void handleShare()}
            onToggleMotion={() => setMotionOn((m) => !m)}
          />
        )}
      </div>

      <WaitlistModal open={waitlistOpen} onClose={() => setWaitlistOpen(false)} />

      {helpOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            aria-label="Close help"
            onClick={() => setHelpOpen(false)}
          />
          <div className="dock-glass relative z-10 w-full max-w-sm p-6">
            <p className="font-label text-[10px] uppercase tracking-[0.18em] text-[var(--fg-muted)]">
              Shortcuts
            </p>
            <ul className="mt-4 space-y-2 font-label text-xs text-[var(--fg-muted)]">
              <li>
                <kbd className="text-[var(--fg)]">Esc</kbd> — back
              </li>
              <li>
                <kbd className="text-[var(--fg)]">Space</kbd> — focus mode
              </li>
              <li>
                <kbd className="text-[var(--fg)]">1</kbd> / <kbd className="text-[var(--fg)]">2</kbd> — simple / craft dials
              </li>
              <li>
                <kbd className="text-[var(--fg)]">M</kbd> — motion / still
              </li>
              <li>
                <kbd className="text-[var(--fg)]">S</kbd> — surprise
              </li>
            </ul>
            <button
              type="button"
              onClick={() => setHelpOpen(false)}
              className="mt-5 w-full text-center text-xs text-[var(--fg-muted)] hover:text-[var(--fg)]"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
