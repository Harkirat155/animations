import { useState, type FormEvent } from 'react'
import { submitWaitlist } from '../api'

interface Props {
  open: boolean
  onClose: () => void
}

export default function WaitlistModal({ open, onClose }: Props) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle')
  const [message, setMessage] = useState('')

  if (!open) return null

  async function submit(e: FormEvent) {
    e.preventDefault()
    setStatus('loading')
    try {
      await submitWaitlist(email.trim())
      setStatus('ok')
      setMessage("You're on the list — we'll open Maker renders soon.")
    } catch (err) {
      setStatus('error')
      setMessage(err instanceof Error ? err.message : 'Something went wrong')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="glass-strong relative z-10 w-full max-w-md p-6 sm:p-8">
        <p className="font-label text-[10px] uppercase tracking-[0.18em] text-[var(--accent)]">Maker plan</p>
        <h2 className="font-display mt-2 text-2xl font-bold tracking-tight">Full video exports are almost here</h2>
        <p className="mt-3 text-sm leading-relaxed text-[var(--fg-muted)]">
          Free forever: compose, motion preview, share links, and download the live preview.
          Maker unlocks film-quality 9:16 / 1:1 packs with generative audio — join the waitlist.
        </p>

        {status === 'ok' ? (
          <p className="mt-6 text-sm text-[var(--accent)]">{message}</p>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-3">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@studio.com"
              className="w-full rounded-xl border border-[var(--border)] bg-black/40 px-4 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--accent)] focus:outline-none"
            />
            {status === 'error' && <p className="text-xs text-rose-300">{message}</p>}
            <button
              type="submit"
              disabled={status === 'loading'}
              className="w-full rounded-xl bg-[var(--fg)] px-4 py-3 text-sm font-semibold text-[var(--bg)] transition hover:-translate-y-0.5 disabled:opacity-60"
            >
              {status === 'loading' ? 'Joining…' : 'Join waitlist'}
            </button>
          </form>
        )}

        <button
          type="button"
          onClick={onClose}
          className="mt-4 w-full text-center text-xs text-[var(--fg-muted)] hover:text-[var(--fg)]"
        >
          Keep composing
        </button>
      </div>
    </div>
  )
}
