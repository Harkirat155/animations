import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'

export type NavPage = 'looks' | 'systems' | 'focus'

interface Props {
  page: NavPage
  systemLabel?: string | null
  onNavigate: (page: 'looks' | 'systems') => void
  onMaker: () => void
  onExitFocus?: () => void
}

/**
 * Three destinations: Looks · Systems · Maker.
 * Glossy glass pill — readable over dark living backdrops.
 */
export default function TopBar({
  page,
  systemLabel,
  onNavigate,
  onMaker,
  onExitFocus,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])

  useEffect(() => {
    setMenuOpen(false)
  }, [page])

  if (page === 'focus') {
    return (
      <>
        <div className="nav-scrim" aria-hidden />
        <header className="pointer-events-none fixed inset-x-0 top-0 z-40 flex justify-center px-4 pt-4">
          <div className="nav-glass pointer-events-auto flex w-full max-w-md items-center justify-between rounded-full px-4 py-2.5">
            <p className="font-label truncate text-[10px] uppercase tracking-[0.16em] text-white/70">
              {systemLabel ?? 'Lumen'}
            </p>
            <button
              type="button"
              onClick={onExitFocus}
              className="shrink-0 rounded-full bg-[var(--fg)] px-3.5 py-1.5 text-xs font-semibold text-[var(--bg)]"
            >
              Exit Focus
            </button>
          </div>
        </header>
      </>
    )
  }

  return (
    <>
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-[var(--accent)] focus:px-4 focus:py-2 focus:text-[var(--bg)]"
      >
        Skip to content
      </a>

      <div className="nav-scrim" aria-hidden />

      <header className="fixed inset-x-0 top-0 z-40 flex justify-center px-3 pt-3 sm:px-4 sm:pt-5">
        <div className="w-full max-w-2xl">
          <nav
            aria-label="Primary"
            className="nav-glass flex h-13 items-center justify-between gap-2 rounded-full px-3 sm:h-14 sm:px-5"
            style={{ minHeight: '3.25rem' }}
          >
            <button
              type="button"
              onClick={() => onNavigate('looks')}
              className="flex shrink-0 items-center gap-2.5 rounded-full px-1.5 py-1 text-left"
              aria-label="Lumen home"
            >
              <span className="live-dot size-2 shrink-0 rounded-full bg-[var(--accent)] shadow-[0_0_12px_var(--accent)]" />
              <span className="font-display text-base font-bold tracking-tight text-white sm:text-lg">
                Lumen
              </span>
            </button>

            <ul className="hidden items-center gap-1 sm:flex">
              <li>
                <NavLink
                  label="Looks"
                  active={page === 'looks'}
                  onClick={() => onNavigate('looks')}
                />
              </li>
              <li>
                <NavLink
                  label="Systems"
                  active={page === 'systems'}
                  onClick={() => onNavigate('systems')}
                />
              </li>
              <li>
                <button
                  type="button"
                  onClick={onMaker}
                  className="ml-1 rounded-full bg-[var(--fg)] px-4 py-1.5 text-sm font-bold text-[var(--bg)] transition hover:opacity-90"
                >
                  Maker
                </button>
              </li>
            </ul>

            <div className="flex items-center gap-1.5 sm:hidden">
              <button
                type="button"
                onClick={onMaker}
                className="rounded-full bg-[var(--fg)] px-3 py-1.5 text-[11px] font-bold text-[var(--bg)]"
              >
                Maker
              </button>
              <button
                type="button"
                aria-expanded={menuOpen}
                aria-controls="mobile-nav-menu"
                aria-label={menuOpen ? 'Close menu' : 'Open menu'}
                onClick={() => setMenuOpen((v) => !v)}
                className="flex size-9 items-center justify-center rounded-full border border-white/25 bg-white/10 text-white"
              >
                <HamburgerIcon open={menuOpen} />
              </button>
            </div>
          </nav>

          <AnimatePresence>
            {menuOpen && (
              <motion.div
                id="mobile-nav-menu"
                initial={{ opacity: 0, y: -8, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -8, scale: 0.98 }}
                transition={{ duration: 0.18 }}
                className="nav-glass mt-2 overflow-hidden rounded-2xl sm:hidden"
              >
                <ul>
                  <MobileItem
                    label="Looks"
                    hint="Browse the carousel"
                    active={page === 'looks'}
                    onClick={() => {
                      setMenuOpen(false)
                      onNavigate('looks')
                    }}
                  />
                  <MobileItem
                    label="Systems"
                    hint="Generate & tweak dials"
                    active={page === 'systems'}
                    onClick={() => {
                      setMenuOpen(false)
                      onNavigate('systems')
                    }}
                  />
                  <MobileItem
                    label="Maker"
                    hint="Join the waitlist"
                    onClick={() => {
                      setMenuOpen(false)
                      onMaker()
                    }}
                  />
                </ul>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </header>

      <div className="h-[4.25rem] sm:h-[5rem]" aria-hidden />
    </>
  )
}

function NavLink({
  label,
  onClick,
  active,
}: {
  label: string
  onClick: () => void
  active: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${
        active
          ? 'bg-white/18 text-white shadow-[0_0_0_1px_rgb(255_255_255/0.12)_inset]'
          : 'text-white/65 hover:bg-white/8 hover:text-white'
      }`}
    >
      {label}
    </button>
  )
}

function MobileItem({
  label,
  hint,
  onClick,
  active,
}: {
  label: string
  hint: string
  onClick: () => void
  active?: boolean
}) {
  return (
    <li className="border-b border-white/10 last:border-0">
      <button
        type="button"
        onClick={onClick}
        className="flex w-full flex-col items-start px-5 py-3.5 text-left"
      >
        <span
          className={`text-base font-semibold ${active ? 'text-[var(--accent)]' : 'text-white'}`}
        >
          {label}
        </span>
        <span className="mt-0.5 text-xs text-white/50">{hint}</span>
      </button>
    </li>
  )
}

function HamburgerIcon({ open }: { open: boolean }) {
  return (
    <span className="relative block size-4" aria-hidden>
      <span
        className={`absolute left-0 block h-0.5 w-4 bg-current transition ${
          open ? 'top-1/2 -translate-y-1/2 rotate-45' : 'top-0.5'
        }`}
      />
      <span
        className={`absolute left-0 top-1/2 block h-0.5 w-4 -translate-y-1/2 bg-current transition ${
          open ? 'opacity-0' : 'opacity-100'
        }`}
      />
      <span
        className={`absolute left-0 block h-0.5 w-4 bg-current transition ${
          open ? 'top-1/2 -translate-y-1/2 -rotate-45' : 'bottom-0.5'
        }`}
      />
    </span>
  )
}
