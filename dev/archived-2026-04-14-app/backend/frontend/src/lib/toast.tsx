// Lightweight toast notifications - replaces window.alert() for
// non-blocking error/success messages.
//
// Usage:
//   import { showToast } from '../lib/toast'
//   showToast('Could not save the change.', 'error')
//
// The <Toaster /> host is mounted once in Layout.
import { useEffect, useState } from 'react'

export type ToastVariant = 'error' | 'success' | 'info'

interface ToastItem {
  id: number
  message: string
  variant: ToastVariant
}

let nextId = 1
let pushToast: ((t: ToastItem) => void) | null = null

export function showToast(message: string, variant: ToastVariant = 'error') {
  if (pushToast) {
    pushToast({ id: nextId++, message, variant })
  } else {
    // Toaster not mounted (e.g. login page) - fall back to the console
    // so the message is never silently lost.
    console.warn(`[toast:${variant}]`, message)
  }
}

const VARIANT_STYLES: Record<ToastVariant, { box: string; dot: string }> = {
  error:   { box: 'border-red-200 bg-red-50 text-red-800',     dot: 'bg-red-500' },
  success: { box: 'border-green-200 bg-green-50 text-green-800', dot: 'bg-green-500' },
  info:    { box: 'border-zinc-200 bg-white text-zinc-800',    dot: 'bg-zinc-400' },
}

export function Toaster() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  useEffect(() => {
    pushToast = (t) => {
      setToasts((prev) => [...prev, t])
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((x) => x.id !== t.id))
      }, 7000)
    }
    return () => { pushToast = null }
  }, [])

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm" role="status" aria-live="polite">
      {toasts.map((t) => {
        const s = VARIANT_STYLES[t.variant]
        return (
          <div
            key={t.id}
            className={`flex items-start gap-2.5 rounded-md border px-4 py-3 shadow-lg text-sm ${s.box}`}
          >
            <span className={`mt-1.5 h-1.5 w-1.5 rounded-full flex-shrink-0 ${s.dot}`} aria-hidden="true" />
            <span className="flex-1 min-w-0 leading-snug">{t.message}</span>
            <button
              onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
              className="flex-shrink-0 p-0.5 rounded text-current opacity-50 hover:opacity-100 transition-opacity"
              aria-label="Dismiss"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )
      })}
    </div>
  )
}
