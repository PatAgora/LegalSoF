// Settings > Two-factor authentication - TOTP enrol / disable flows.
//
// API (all authenticated):
//   GET  /api/v1/auth/mfa/status  -> { mfa_enabled: boolean }
//   POST /api/v1/auth/mfa/setup   -> { qr_code (base64 PNG), secret, otpauth_uri }
//   POST /api/v1/auth/mfa/verify  -> body { token }  -> { mfa_enabled: true }
//   POST /api/v1/auth/mfa/disable -> body { token }  -> { mfa_enabled: false }
import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL, authFetch } from '../../lib/api'
import { Button, Card, Alert, Modal, Spinner } from '../ui'
import { showToast } from '../../lib/toast'

interface SetupData {
  qr_code: string
  secret: string
  otpauth_uri: string
}

const inputCls =
  'w-full px-3 py-2 text-sm bg-white border border-zinc-300 rounded text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:border-transparent'
const codeInputCls = `${inputCls} text-center text-lg tracking-[0.5em] font-mono`

async function extractDetail(res: Response, fallback: string): Promise<string> {
  const data = await res.json().catch(() => ({}))
  return typeof data?.detail === 'string' ? data.detail : fallback
}

function CopyRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      showToast('Could not copy to the clipboard.', 'error')
    }
  }
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-zinc-500 mb-1">{label}</div>
      <div className="flex items-center gap-2">
        <code className="flex-1 min-w-0 truncate text-xs bg-zinc-50 border border-zinc-200 rounded px-2.5 py-1.5 text-zinc-800">
          {value}
        </code>
        <Button type="button" variant="secondary" size="sm" onClick={handleCopy}>
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
    </div>
  )
}

export default function MfaSection() {
  // null = still loading status
  const [mfaEnabled, setMfaEnabled] = useState<boolean | null>(null)
  const [statusError, setStatusError] = useState('')

  // Enrolment flow
  const [setup, setSetup] = useState<SetupData | null>(null)
  const [settingUp, setSettingUp] = useState(false)
  const [verifyCode, setVerifyCode] = useState('')
  const [verifying, setVerifying] = useState(false)
  const [verifyError, setVerifyError] = useState('')
  const verifyInputRef = useRef<HTMLInputElement>(null)

  // Disable flow
  const [disableOpen, setDisableOpen] = useState(false)
  const [disableCode, setDisableCode] = useState('')
  const [disabling, setDisabling] = useState(false)
  const [disableError, setDisableError] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await authFetch(`${API_BASE_URL}/api/v1/auth/mfa/status`)
        if (!res.ok) {
          if (!cancelled) setStatusError('Could not load the two-factor authentication status.')
          return
        }
        const data = await res.json()
        if (!cancelled) setMfaEnabled(Boolean(data.mfa_enabled))
      } catch {
        if (!cancelled) setStatusError('Could not load the two-factor authentication status.')
      }
    })()
    return () => { cancelled = true }
  }, [])

  const handleStartSetup = async () => {
    setSettingUp(true)
    setVerifyError('')
    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/auth/mfa/setup`, { method: 'POST' })
      if (!res.ok) {
        showToast(await extractDetail(res, 'Could not start two-factor setup.'), 'error')
        return
      }
      setSetup(await res.json())
      setVerifyCode('')
    } catch {
      showToast('Could not reach the server. Please try again.', 'error')
    } finally {
      setSettingUp(false)
    }
  }

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    if (verifyCode.length !== 6 || verifying) return
    setVerifying(true)
    setVerifyError('')
    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/auth/mfa/verify`, {
        method: 'POST',
        body: JSON.stringify({ token: verifyCode }),
      })
      if (!res.ok) {
        setVerifyError(await extractDetail(res, 'That code was not accepted. Please try again.'))
        setVerifyCode('')
        verifyInputRef.current?.focus()
        return
      }
      setMfaEnabled(true)
      setSetup(null)
      setVerifyCode('')
      showToast('Two-factor authentication is now enabled.', 'success')
    } catch {
      setVerifyError('Could not reach the server. Please try again.')
    } finally {
      setVerifying(false)
    }
  }

  const handleDisable = async () => {
    if (disableCode.length !== 6 || disabling) return
    setDisabling(true)
    setDisableError('')
    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/auth/mfa/disable`, {
        method: 'POST',
        body: JSON.stringify({ token: disableCode }),
      })
      if (!res.ok) {
        setDisableError(await extractDetail(res, 'That code was not accepted. Please try again.'))
        setDisableCode('')
        return
      }
      setMfaEnabled(false)
      setDisableOpen(false)
      setDisableCode('')
      showToast('Two-factor authentication has been disabled.', 'success')
    } catch {
      setDisableError('Could not reach the server. Please try again.')
    } finally {
      setDisabling(false)
    }
  }

  const closeDisableModal = () => {
    if (disabling) return
    setDisableOpen(false)
    setDisableCode('')
    setDisableError('')
  }

  return (
    <Card>
      <Card.Header>
        <h2 className="text-sm font-semibold text-zinc-900">Two-factor authentication</h2>
        <p className="text-xs text-zinc-500 mt-0.5">
          Add a second step at sign-in using an authenticator app (e.g. Microsoft
          Authenticator, Google Authenticator, 1Password).
        </p>
      </Card.Header>
      <Card.Body>
        {statusError ? (
          <Alert variant="error">{statusError}</Alert>
        ) : mfaEnabled === null ? (
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <Spinner size="sm" /> Loading status…
          </div>
        ) : mfaEnabled ? (
          /* ------------------------------ Enabled ------------------------ */
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-2.5">
              <span className="mt-1 h-2 w-2 rounded-full bg-green-500 flex-shrink-0" aria-hidden="true" />
              <div>
                <div className="text-sm font-medium text-zinc-900">Enabled</div>
                <p className="text-xs text-zinc-500 mt-0.5 max-w-md">
                  A code from your authenticator app is required every time you sign in.
                </p>
              </div>
            </div>
            <Button type="button" variant="secondary" size="sm" onClick={() => setDisableOpen(true)}>
              Disable
            </Button>
          </div>
        ) : setup ? (
          /* --------------------------- Enrolment step -------------------- */
          <div className="space-y-5 max-w-md">
            <ol className="list-decimal list-inside space-y-1 text-xs text-zinc-600">
              <li>Scan the QR code with your authenticator app, or enter the secret manually.</li>
              <li>Enter the 6-digit code the app shows to confirm.</li>
            </ol>

            <div className="flex justify-center">
              <img
                src={`data:image/png;base64,${setup.qr_code}`}
                alt="QR code for authenticator app enrolment"
                className="h-44 w-44 border border-zinc-200 rounded"
              />
            </div>

            <div className="space-y-3">
              <CopyRow label="Secret (manual entry)" value={setup.secret} />
              <CopyRow label="Provisioning URI" value={setup.otpauth_uri} />
            </div>

            <form onSubmit={handleVerify} className="space-y-3">
              {verifyError && <Alert variant="error">{verifyError}</Alert>}
              <div>
                <label htmlFor="mfa-verify-code" className="block text-xs font-semibold text-zinc-700 mb-1.5">
                  6-digit code
                </label>
                <input
                  id="mfa-verify-code"
                  ref={verifyInputRef}
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  maxLength={6}
                  value={verifyCode}
                  onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className={codeInputCls}
                  placeholder="••••••"
                />
              </div>
              <div className="flex gap-3">
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  loading={verifying}
                  disabled={verifyCode.length !== 6}
                >
                  {verifying ? 'Verifying…' : 'Verify and enable'}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="md"
                  disabled={verifying}
                  onClick={() => { setSetup(null); setVerifyCode(''); setVerifyError('') }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        ) : (
          /* ------------------------------ Disabled ----------------------- */
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-2.5">
              <span className="mt-1 h-2 w-2 rounded-full bg-zinc-300 flex-shrink-0" aria-hidden="true" />
              <div>
                <div className="text-sm font-medium text-zinc-900">Not enabled</div>
                <p className="text-xs text-zinc-500 mt-0.5 max-w-md">
                  We recommend enabling two-factor authentication to protect client
                  matter data.
                </p>
              </div>
            </div>
            <Button type="button" variant="primary" size="sm" loading={settingUp} onClick={handleStartSetup}>
              {settingUp ? 'Preparing…' : 'Enable'}
            </Button>
          </div>
        )}

        {/* Disable confirmation modal - requires a current TOTP code. */}
        <Modal
          isOpen={disableOpen}
          onClose={closeDisableModal}
          title="Disable two-factor authentication"
          size="sm"
          footer={
            <>
              <Button type="button" variant="secondary" size="md" disabled={disabling} onClick={closeDisableModal}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="danger"
                size="md"
                loading={disabling}
                disabled={disableCode.length !== 6}
                onClick={handleDisable}
              >
                {disabling ? 'Disabling…' : 'Disable'}
              </Button>
            </>
          }
        >
          <div className="space-y-3">
            <p className="text-sm text-zinc-600">
              Your account will no longer require a code at sign-in. Enter a current
              code from your authenticator app to confirm.
            </p>
            {disableError && <Alert variant="error">{disableError}</Alert>}
            <div>
              <label htmlFor="mfa-disable-code" className="block text-xs font-semibold text-zinc-700 mb-1.5">
                6-digit code
              </label>
              <input
                id="mfa-disable-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                autoFocus
                maxLength={6}
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleDisable() } }}
                className={codeInputCls}
                placeholder="••••••"
              />
            </div>
          </div>
        </Modal>
      </Card.Body>
    </Card>
  )
}
