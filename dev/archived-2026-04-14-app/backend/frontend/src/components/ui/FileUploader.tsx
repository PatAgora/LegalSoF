// Drop-in file uploader.
//
// Why it exists: the old upload UI used three different visual
// styles across three call sites, with hidden file inputs, native
// browser styling, and no upload progress. This component
// consolidates everything behind one consistent enterprise look:
//
//   - Dashed dropzone with hover state.
//   - Drag-and-drop AND click-to-browse, both fully working.
//   - Real upload progress via XMLHttpRequest.upload.onprogress.
//   - Status states: idle, validating, uploading (with %), done
//     (verdict chip), error.
//   - Optional verdict + "View" action wired in by the caller so a
//     verification modal can open straight from the uploader row.
//
// API:
//   <FileUploader
//     category="Bank statement"
//     accept=".pdf,.csv,.xlsx"
//     maxSizeMb={50}
//     uploadUrl={...}        // POST URL
//     formField="file"       // FormData key (default "file")
//     extraFormFields={...}  // optional fields to add to FormData
//     helper="PDF, CSV or XLSX up to 50 MB"
//     onComplete={(payload) => ...}
//   />
//
// The caller decides what to do with the parsed JSON response.
import { useCallback, useRef, useState } from 'react'
import { getAccessToken, refreshTokens } from '../../lib/api'
import StatusChip from './StatusChip'
import Alert from './Alert'

interface FileUploaderProps {
  category: string
  uploadUrl: string
  accept?: string
  maxSizeMb?: number
  formField?: string
  extraFormFields?: Record<string, string>
  helper?: string
  // Called when the request returns a 2xx; receives the parsed body.
  onComplete?: (response: any) => void
  // Optional: extract a verdict label from the response so the row can
  // render a StatusChip. Return null to skip the chip.
  extractVerdict?: (response: any) =>
    | { verdict?: string; severity?: 'critical' | 'high' | 'medium' | 'low' | 'info'; label?: string }
    | null
  // Optional: handler for the "View" link shown next to the chip.
  onView?: (response: any) => void
}

type Status = 'idle' | 'uploading' | 'done' | 'error'

interface FileState {
  file: File
  status: Status
  progress: number
  response: any
  error: string | null
}

export default function FileUploader({
  category,
  uploadUrl,
  accept,
  maxSizeMb = 50,
  formField = 'file',
  extraFormFields,
  helper,
  onComplete,
  extractVerdict,
  onView,
}: FileUploaderProps) {
  const [state, setState] = useState<FileState | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const validate = useCallback((f: File): string | null => {
    if (f.size > maxSizeMb * 1024 * 1024) {
      return `File is larger than ${maxSizeMb} MB.`
    }
    if (accept) {
      const allowed = accept.split(',').map((s) => s.trim().toLowerCase())
      const lower = f.name.toLowerCase()
      const ok = allowed.some((a) => {
        if (a.startsWith('.')) return lower.endsWith(a)
        return f.type && a === f.type.toLowerCase()
      })
      if (!ok) return `File type not allowed. Accepted: ${accept}.`
    }
    return null
  }, [accept, maxSizeMb])

  const startUpload = useCallback((file: File, isRetryAfterRefresh = false) => {
    const err = validate(file)
    if (err) {
      setState({ file, status: 'error', progress: 0, response: null, error: err })
      return
    }

    setState({ file, status: 'uploading', progress: 0, response: null, error: null })

    // Build the request. We use XHR rather than fetch so we can show
    // real upload progress - fetch doesn't expose progress events.
    const xhr = new XMLHttpRequest()
    xhr.open('POST', uploadUrl)
    const token = getAccessToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

    xhr.upload.addEventListener('progress', (e) => {
      if (!e.lengthComputable) return
      const pct = Math.round((e.loaded / e.total) * 100)
      setState((prev) => prev ? { ...prev, progress: pct } : prev)
    })

    xhr.addEventListener('load', () => {
      // 401 - access token expired. Try one token refresh, then retry
      // the upload once with the new token. The staged file stays in
      // state, so if the refresh fails the user can retry after
      // signing in again - nothing is lost.
      if (xhr.status === 401) {
        if (!isRetryAfterRefresh) {
          refreshTokens().then((ok) => {
            if (ok) {
              startUpload(file, true)
            } else {
              setState((prev) => prev ? { ...prev, status: 'error', error: 'Session expired — sign in again to upload. Your file is still staged; use Try again after signing in.' } : prev)
            }
          })
        } else {
          setState((prev) => prev ? { ...prev, status: 'error', error: 'Session expired — sign in again to upload. Your file is still staged; use Try again after signing in.' } : prev)
        }
        return
      }
      let body: any = null
      try { body = JSON.parse(xhr.responseText) } catch { body = xhr.responseText }
      if (xhr.status >= 200 && xhr.status < 300) {
        setState((prev) => prev ? { ...prev, status: 'done', progress: 100, response: body } : prev)
        onComplete?.(body)
      } else {
        const detail = (body && body.detail) ? body.detail : `Upload failed (HTTP ${xhr.status})`
        setState((prev) => prev ? { ...prev, status: 'error', error: detail } : prev)
      }
    })
    xhr.addEventListener('error', () => {
      setState((prev) => prev ? { ...prev, status: 'error', error: 'Network error during upload.' } : prev)
    })

    const fd = new FormData()
    fd.append(formField, file)
    if (extraFormFields) {
      for (const [k, v] of Object.entries(extraFormFields)) fd.append(k, v)
    }
    xhr.send(fd)
  }, [uploadUrl, formField, extraFormFields, validate, onComplete])

  const onFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return
    startUpload(files[0])
  }, [startUpload])

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); setDragOver(true) }
  const onDragLeave = (e: React.DragEvent) => { e.preventDefault(); setDragOver(false) }
  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    onFiles(e.dataTransfer.files)
  }

  const reset = () => {
    setState(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div>
      {/* Dropzone - hidden when a file is being processed or shown */}
      {!state && (
        <label
          htmlFor={`file-upload-${category}`}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          className={[
            'flex flex-col items-center justify-center w-full cursor-pointer rounded-md border-2 border-dashed transition-colors',
            'px-6 py-8 text-center',
            dragOver
              ? 'border-zinc-500 bg-zinc-50'
              : 'border-zinc-300 hover:border-zinc-400 hover:bg-zinc-50/50',
          ].join(' ')}
        >
          <UploadIcon />
          <div className="mt-3 text-sm text-zinc-700">
            <span className="font-medium text-zinc-900">Drop {category.toLowerCase()}</span>
            {' '}or <span className="underline underline-offset-2">click to browse</span>
          </div>
          {helper && <div className="mt-1 text-xs text-zinc-400">{helper}</div>}
          <input
            id={`file-upload-${category}`}
            ref={inputRef}
            type="file"
            accept={accept}
            className="sr-only"
            onChange={(e) => onFiles(e.target.files)}
          />
        </label>
      )}

      {/* File row - replaces the dropzone once a file is staged */}
      {state && (
        <div className="rounded-md border border-zinc-200 bg-white">
          <div className="px-4 py-3 flex items-center gap-3">
            <FileIcon name={state.file.name} />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-zinc-900 truncate">{state.file.name}</div>
              <div className="text-xs text-zinc-400 mt-0.5">
                {humanSize(state.file.size)}
                {state.status === 'uploading' && ' · uploading…'}
              </div>
            </div>

            {state.status === 'uploading' && (
              <div className="text-xs font-medium text-zinc-500 tabular-nums w-12 text-right">
                {state.progress}%
              </div>
            )}

            {state.status === 'done' && extractVerdict && (() => {
              const v = extractVerdict(state.response)
              if (!v) return null
              const sev = v.severity ?? verdictSeverity(v.verdict)
              return (
                <div className="flex items-center gap-2">
                  <StatusChip severity={sev} label={v.label || v.verdict?.toUpperCase() || 'DONE'} />
                  {onView && (
                    <button
                      onClick={() => onView(state.response)}
                      className="text-xs font-medium text-zinc-700 hover:text-zinc-900 underline underline-offset-2"
                    >
                      View
                    </button>
                  )}
                </div>
              )
            })()}

            <button
              onClick={reset}
              className="ml-1 text-xs text-zinc-400 hover:text-zinc-700 transition-colors"
              title="Remove"
            >
              ✕
            </button>
          </div>

          {state.status === 'uploading' && (
            <div className="h-1 w-full bg-zinc-100 overflow-hidden rounded-b-md">
              <div
                className="h-full bg-zinc-900 transition-[width] duration-150"
                style={{ width: `${state.progress}%` }}
              />
            </div>
          )}
        </div>
      )}

      {state?.error && (
        <div className="mt-2">
          <Alert variant="error" title="Upload failed">
            {state.error}
            <div className="mt-2">
              <button
                type="button"
                onClick={() => startUpload(state.file)}
                className="text-xs font-semibold text-zinc-900 underline underline-offset-2 hover:text-zinc-700"
              >
                Try again
              </button>
            </div>
          </Alert>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function verdictSeverity(verdict?: string): 'critical' | 'high' | 'medium' | 'info' | 'low' {
  switch (verdict) {
    case 'Verified':       return 'info'
    case 'Suspicious':     return 'high'
    case 'LikelyTampered': return 'critical'
    default:               return 'medium'
  }
}

function UploadIcon() {
  return (
    <svg className="h-8 w-8 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 7.5m0 0L7.5 12m4.5-4.5V21" />
    </svg>
  )
}

function FileIcon({ name }: { name: string }) {
  const ext = name.split('.').pop()?.toUpperCase().slice(0, 4) || 'FILE'
  return (
    <div className="h-10 w-10 rounded border border-zinc-200 bg-zinc-50 flex flex-col items-center justify-center shrink-0">
      <span className="text-[9px] font-semibold text-zinc-500 tracking-wider">{ext}</span>
    </div>
  )
}
