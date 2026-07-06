// Client evidence-upload portal — the page a CLIENT (no account) lands
// on from the link their solicitor sends them: /portal/:token
//
// Deliberately standalone: no Layout, no nav, no auth. The token in the
// URL is the only credential; the page calls the two public portal
// endpoints and nothing else. Uploads use bare XMLHttpRequest (for
// progress) with NO Authorization header.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { API_BASE_URL } from '../lib/api'
import { formatDate } from '../lib/format'

type Category = 'bank_statement' | 'supporting_doc'

interface PortalInfo {
  firm_name: string
  matter_reference: string
  client_name: string
  expires_at: string | null
  uploads_remaining: number
}

type ItemStatus = 'uploading' | 'done' | 'error'

interface UploadItem {
  id: number
  file: File
  category: Category
  status: ItemStatus
  progress: number
  error: string | null
}

const CATEGORY_META: Record<Category, { label: string; accept: string; helper: string }> = {
  bank_statement: {
    label: 'Bank statement',
    accept: '.pdf,.csv',
    helper: 'PDF or CSV exported from your bank',
  },
  supporting_doc: {
    label: 'Supporting document',
    accept: '.pdf',
    helper: 'PDF only — e.g. completion statement, gift letter, payslip',
  },
}

let nextItemId = 1

export default function PortalUploadPage() {
  const { token } = useParams()
  const [info, setInfo] = useState<PortalInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [invalid, setInvalid] = useState(false)
  const [category, setCategory] = useState<Category>('bank_statement')
  const [items, setItems] = useState<UploadItem[]>([])
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const r = await fetch(`${API_BASE_URL}/api/v1/portal/${token}`)
        if (cancelled) return
        if (!r.ok) {
          setInvalid(true)
          return
        }
        setInfo(await r.json())
      } catch {
        if (!cancelled) setInvalid(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [token])

  const startUpload = useCallback((file: File, cat: Category) => {
    const meta = CATEGORY_META[cat]
    const id = nextItemId++
    const item: UploadItem = { id, file, category: cat, status: 'uploading', progress: 0, error: null }

    // Client-side validation before any network traffic.
    const allowed = meta.accept.split(',').map((s) => s.trim().toLowerCase())
    const nameLower = file.name.toLowerCase()
    if (!allowed.some((a) => nameLower.endsWith(a))) {
      setItems((prev) => [...prev, { ...item, status: 'error', error: `That file type is not accepted for a ${meta.label.toLowerCase()}. Accepted: ${meta.accept}.` }])
      return
    }
    if (file.size > 50 * 1024 * 1024) {
      setItems((prev) => [...prev, { ...item, status: 'error', error: 'File is larger than 50 MB.' }])
      return
    }

    setItems((prev) => [...prev, item])

    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE_URL}/api/v1/portal/${token}/upload`)

    xhr.upload.addEventListener('progress', (e) => {
      if (!e.lengthComputable) return
      const pct = Math.round((e.loaded / e.total) * 100)
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, progress: pct } : it)))
    })

    xhr.addEventListener('load', () => {
      let body: any = null
      try { body = JSON.parse(xhr.responseText) } catch { body = null }
      if (xhr.status >= 200 && xhr.status < 300) {
        setItems((prev) => prev.map((it) => (it.id === id ? { ...it, status: 'done', progress: 100 } : it)))
        if (body && typeof body.uploads_remaining === 'number') {
          setInfo((prev) => (prev ? { ...prev, uploads_remaining: body.uploads_remaining } : prev))
        }
      } else if (xhr.status === 404) {
        setItems((prev) => prev.map((it) => (it.id === id ? { ...it, status: 'error', error: 'This upload link is no longer valid. Please contact your solicitor for a new one.' } : it)))
      } else {
        const detail = body?.detail || `Upload failed (HTTP ${xhr.status}). Please try again.`
        setItems((prev) => prev.map((it) => (it.id === id ? { ...it, status: 'error', error: String(detail) } : it)))
      }
    })
    xhr.addEventListener('error', () => {
      setItems((prev) => prev.map((it) => (it.id === id ? { ...it, status: 'error', error: 'Network error during upload — please check your connection and try again.' } : it)))
    })

    const fd = new FormData()
    fd.append('file', file)
    fd.append('file_category', cat)
    xhr.send(fd)
  }, [token])

  const onFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return
    Array.from(files).forEach((f) => startUpload(f, category))
    if (inputRef.current) inputRef.current.value = ''
  }, [startUpload, category])

  const meta = CATEGORY_META[category]
  const exhausted = (info?.uploads_remaining ?? 0) <= 0

  return (
    <div className="min-h-screen bg-zinc-50 flex flex-col">
      {/* Firm header */}
      <header className="bg-zinc-900">
        <div className="mx-auto max-w-2xl px-6 py-4 flex items-center justify-between">
          <span className="font-serif text-lg tracking-tight text-white">Agora Consulting AI</span>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Secure document upload</span>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-2xl px-6 py-10">
        {loading && (
          <div className="flex items-center justify-center py-24">
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-zinc-600" />
              <p className="mt-4 text-sm text-zinc-500">Checking your upload link…</p>
            </div>
          </div>
        )}

        {!loading && invalid && (
          <div className="bg-white border border-zinc-200 rounded-md px-8 py-10 text-center">
            <div className="mx-auto h-12 w-12 rounded-full bg-zinc-100 flex items-center justify-center">
              <svg className="h-6 w-6 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H3.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
              </svg>
            </div>
            <h1 className="mt-4 font-serif text-2xl text-zinc-900">This link is no longer available</h1>
            <p className="mt-2 text-sm text-zinc-500 leading-relaxed">
              The upload link you followed is invalid, has expired, or has been
              closed. Upload links are time-limited for your security.
            </p>
            <p className="mt-3 text-sm text-zinc-500">
              Please contact the firm handling your matter and ask them to send
              you a new link.
            </p>
          </div>
        )}

        {!loading && !invalid && info && (
          <>
            {/* Matter context */}
            <div className="mb-6">
              <h1 className="font-serif text-2xl tracking-tight text-zinc-900">Upload your documents</h1>
              <p className="mt-1.5 text-sm text-zinc-500">
                Uploading documents for: <span className="font-medium text-zinc-900">{info.client_name}</span>
                <span className="mx-2 text-zinc-300">·</span>
                Matter reference <span className="font-medium text-zinc-900 tabular-nums">{info.matter_reference}</span>
              </p>
              <p className="mt-1 text-xs text-zinc-400">
                This link expires on {formatDate(info.expires_at)}
                <span className="mx-1.5">·</span>
                {info.uploads_remaining} upload{info.uploads_remaining === 1 ? '' : 's'} remaining
              </p>
            </div>

            <div className="bg-white border border-zinc-200 rounded-md">
              <div className="px-6 py-5 border-b border-zinc-200">
                <div className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                  What are you uploading?
                </div>
                <div className="flex gap-2" role="radiogroup" aria-label="Document category">
                  {(Object.keys(CATEGORY_META) as Category[]).map((cat) => (
                    <button
                      key={cat}
                      role="radio"
                      aria-checked={category === cat}
                      onClick={() => setCategory(cat)}
                      className={[
                        'px-4 py-2 rounded-md border text-sm font-medium transition-colors',
                        category === cat
                          ? 'border-zinc-900 bg-zinc-900 text-white'
                          : 'border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50',
                      ].join(' ')}
                    >
                      {CATEGORY_META[cat].label}
                    </button>
                  ))}
                </div>
                <p className="mt-2 text-xs text-zinc-400">{meta.helper}</p>
              </div>

              <div className="px-6 py-5">
                {exhausted ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    This link has reached its upload limit. If you have more
                    documents to send, please contact the firm handling your
                    matter for a new link.
                  </div>
                ) : (
                  <label
                    htmlFor="portal-file-input"
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                    onDragLeave={(e) => { e.preventDefault(); setDragOver(false) }}
                    onDrop={(e) => { e.preventDefault(); setDragOver(false); onFiles(e.dataTransfer.files) }}
                    className={[
                      'flex flex-col items-center justify-center w-full cursor-pointer rounded-md border-2 border-dashed transition-colors',
                      'px-6 py-10 text-center',
                      dragOver
                        ? 'border-zinc-500 bg-zinc-50'
                        : 'border-zinc-300 hover:border-zinc-400 hover:bg-zinc-50/50',
                    ].join(' ')}
                  >
                    <svg className="h-8 w-8 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 7.5m0 0L7.5 12m4.5-4.5V21" />
                    </svg>
                    <div className="mt-3 text-sm text-zinc-700">
                      <span className="font-medium text-zinc-900">Drop your {meta.label.toLowerCase()}</span>
                      {' '}or <span className="underline underline-offset-2">click to browse</span>
                    </div>
                    <div className="mt-1 text-xs text-zinc-400">{meta.accept.toUpperCase().replace(/\./g, '').replace(/,/g, ' or ')} up to 50 MB</div>
                    <input
                      id="portal-file-input"
                      ref={inputRef}
                      type="file"
                      multiple
                      accept={meta.accept}
                      className="sr-only"
                      onChange={(e) => onFiles(e.target.files)}
                    />
                  </label>
                )}

                {/* Per-file rows */}
                {items.length > 0 && (
                  <ul className="mt-4 space-y-2">
                    {items.map((it) => (
                      <li key={it.id} className="rounded-md border border-zinc-200">
                        <div className="px-4 py-3 flex items-center gap-3">
                          <div className="h-9 w-9 rounded border border-zinc-200 bg-zinc-50 flex items-center justify-center shrink-0">
                            <span className="text-[9px] font-semibold text-zinc-500 tracking-wider">
                              {it.file.name.split('.').pop()?.toUpperCase().slice(0, 4) || 'FILE'}
                            </span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium text-zinc-900 truncate">{it.file.name}</div>
                            <div className="text-xs text-zinc-400 mt-0.5">
                              {CATEGORY_META[it.category].label}
                              {it.status === 'uploading' && ' · uploading…'}
                            </div>
                          </div>
                          {it.status === 'uploading' && (
                            <span className="text-xs font-medium text-zinc-500 tabular-nums">{it.progress}%</span>
                          )}
                          {it.status === 'done' && (
                            <span className="inline-flex items-center gap-1 text-xs font-semibold text-green-700">
                              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                              </svg>
                              Received
                            </span>
                          )}
                          {it.status === 'error' && (
                            <span className="text-xs font-semibold text-red-700">Failed</span>
                          )}
                        </div>
                        {it.status === 'uploading' && (
                          <div className="h-1 w-full bg-zinc-100 overflow-hidden rounded-b-md">
                            <div className="h-full bg-zinc-900 transition-[width] duration-150" style={{ width: `${it.progress}%` }} />
                          </div>
                        )}
                        {it.status === 'error' && it.error && (
                          <div className="px-4 pb-3 flex items-start justify-between gap-3">
                            <p className="text-xs text-red-700 leading-snug">{it.error}</p>
                            {!exhausted && (
                              <button
                                type="button"
                                onClick={() => {
                                  setItems((prev) => prev.filter((x) => x.id !== it.id))
                                  startUpload(it.file, it.category)
                                }}
                                className="flex-shrink-0 text-xs font-semibold text-zinc-900 underline underline-offset-2 hover:text-zinc-700"
                              >
                                Try again
                              </button>
                            )}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Security note */}
            <div className="mt-6 flex items-start gap-2.5 text-xs text-zinc-500 leading-relaxed">
              <svg className="h-4 w-4 mt-0.5 flex-shrink-0 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
              <p>
                Your files are transmitted securely over an encrypted connection
                and are used solely to carry out source of funds checks on your
                matter. They are shared only with the team handling your case.
              </p>
            </div>
          </>
        )}
      </main>

      <footer className="border-t border-zinc-200 bg-white">
        <div className="mx-auto max-w-2xl px-6 py-4 text-xs text-zinc-400">
          Agora Consulting AI · Secure client document portal
        </div>
      </footer>
    </div>
  )
}
