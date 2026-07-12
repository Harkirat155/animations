import { useEffect, useState, type FormEvent } from 'react'
import { submitWaitlist } from '../api'

const STORAGE_KEY = 'lumen_waitlist_email'

interface Props {
  open: boolean
  onClose: () => void
}

export default function WaitlistModal({ open, onClose }: Props) {
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'already' | 'error'>('idle')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!open) return
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        setEmail(saved)
        setStatus('already')
        setMessage("You're already on the Maker waitlist.")
      }
    } catch {
      /* ignore */
    }
  }, [open])

  if (!open) return null

  async function submit(e: FormEvent) {
    e.preventDefault()
    setStatus('loading')
    try {
      const result = await submitWaitlist(email.trim(), {
        name: name.trim() || undefined,
        source: 'composer',
      })
      try {
        localStorage.setItem(STORAGE_KEY, result.email)
      } catch {
        /* ignore */
      }
      if (result.status === 'already') {
        setStatus('already')
        setMessage("You're already on the list — we'll email when Maker opens.")
      } else {
        setStatus('ok')
        setMessage("You're in. We'll notify you when full video exports open.")
      }
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof Error ? err.message : 'Something went wrong')
    }
  }

  const done = status === 'ok' || status === 'already'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close"
        className="absolute inset-0 bg-black/60 backdrop-blur-md"
        onClick={onClose}
      />
      <div className="dock-glass relative z-10 w-full max-w-md p-7 sm:p-9">
        <p className="font-label text-[10px] uppercase tracking-[0.2em] text-[var(--accent)]">
          Maker waitlist
        </p>
        <h2 className="font-display mt-2 text-2xl font-bold tracking-tight">
          {done ? "You're on the list" : 'Reserve Maker access'}
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-[var(--fg-muted)]">
          Free forever: compose, motion preview, share, download previews. Maker unlocks
          film-quality packs — no payment yet.
        </p>

        {done ? (
          <div className="mt-7 space-y-2">
            <p className="text-sm text-[var(--accent)]">{message}</p>
            <p className="font-label text-[11px] text-[var(--fg-muted)]">{email}</p>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-7 space-y-3">
            <div>
              <label className="font-label mb-1.5 block text-[10px] uppercase tracking-[0.14em] text-[var(--fg-muted)]">
                Email
              </label>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@studio.com"
                className="w-full rounded-xl border border-[var(--border)] bg-black/40 px-4 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--accent)] focus:outline-none"
              />
            </div>
            <div>
              <label className="font-label mb-1.5 block text-[10px] uppercase tracking-[0.14em] text-[var(--fg-muted)]">
                Name <span className="opacity-60">(optional)</span>
              </label>
              <input
                type="text"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="How should we say hi?"
                className="w-full rounded-xl border border-[var(--border)] bg-black/40 px-4 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--accent)] focus:outline-none"
              />
            </div>
            {status === 'error' && <p className="text-xs text-rose-300">{message}</p>}
            <button
              type="submit"
              disabled={status === 'loading'}
              data-magnetic
              className="w-full rounded-xl bg-[var(--fg)] px-4 py-3.5 text-sm font-semibold text-[var(--bg)] transition hover:opacity-90 disabled:opacity-60"
            >
              {status === 'loading' ? 'Joining…' : 'Join waitlist'}
            </button>
            <p className="text-center text-[11px] text-[var(--fg-muted)]">
              No spam. One email when Maker ships.
            </p>
          </form>
        )}

        <button
          type="button"
          onClick={onClose}
          className="mt-5 w-full text-center text-xs text-[var(--fg-muted)] hover:text-[var(--fg)]"
        >
          Keep composing
        </button>
      </div>
    </div>
  )
}
