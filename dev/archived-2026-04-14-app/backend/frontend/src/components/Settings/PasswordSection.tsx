// Settings > Password - change-password form with live policy hints.
//
// Talks to POST /api/v1/auth/change-password
//   body:    { current_password, new_password }
//   success: { message }
//   failure: 400 with { detail } (wrong current password / policy breach)
//
// Typed text is never cleared on error - only on success.
import { useState } from 'react'
import { API_BASE_URL, authFetch } from '../../lib/api'
import { Button, Card, Alert } from '../ui'
import { showToast } from '../../lib/toast'

// Mirrors backend validate_password_policy (core/security.py).
const SPECIAL_RE = /[!@#$%^&*()_+\-=[\]{}|;:'",.<>?/`~]/

const POLICY_RULES: { id: string; label: string; test: (pw: string) => boolean }[] = [
  { id: 'length',  label: 'At least 12 characters',                    test: (pw) => pw.length >= 12 },
  { id: 'upper',   label: 'An uppercase letter (A–Z)',                 test: (pw) => /[A-Z]/.test(pw) },
  { id: 'lower',   label: 'A lowercase letter (a–z)',                  test: (pw) => /[a-z]/.test(pw) },
  { id: 'digit',   label: 'A digit (0–9)',                             test: (pw) => /\d/.test(pw) },
  { id: 'special', label: 'A special character (e.g. ! ? # @)',        test: (pw) => SPECIAL_RE.test(pw) },
]

const inputCls =
  'w-full px-3 py-2 text-sm bg-white border border-zinc-300 rounded text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:border-transparent'

function PolicyHint({ met, label }: { met: boolean; label: string }) {
  return (
    <li className={`flex items-center gap-1.5 text-xs transition-colors ${met ? 'text-green-700' : 'text-zinc-500'}`}>
      {met ? (
        <svg className="h-3.5 w-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <span className="h-3.5 w-3.5 flex-shrink-0 flex items-center justify-center" aria-hidden="true">
          <span className="h-1 w-1 rounded-full bg-zinc-300" />
        </span>
      )}
      {label}
    </li>
  )
}

export default function PasswordSection() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState('')
  const [confirmError, setConfirmError] = useState('')
  const [policyError, setPolicyError] = useState('')

  const policyMet = POLICY_RULES.every((r) => r.test(newPassword))
  const confirmMismatch = confirmPassword.length > 0 && newPassword !== confirmPassword

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setServerError('')
    setConfirmError('')
    setPolicyError('')

    if (!policyMet) {
      setPolicyError('The new password does not meet all the requirements below.')
      return
    }
    if (newPassword !== confirmPassword) {
      setConfirmError('Passwords do not match.')
      return
    }

    setSaving(true)
    try {
      const res = await authFetch(`${API_BASE_URL}/api/v1/auth/change-password`, {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        // Keep everything the user typed - just surface the error.
        setServerError(
          typeof data?.detail === 'string'
            ? data.detail
            : 'Could not change the password. Please try again.'
        )
        return
      }
      showToast('Password changed successfully.', 'success')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch {
      setServerError('Could not reach the server. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <Card.Header>
        <h2 className="text-sm font-semibold text-zinc-900">Password</h2>
        <p className="text-xs text-zinc-500 mt-0.5">
          Change the password you use to sign in.
        </p>
      </Card.Header>
      <Card.Body>
        <form onSubmit={handleSubmit} className="space-y-4 max-w-md">
          {serverError && <Alert variant="error">{serverError}</Alert>}

          <div>
            <label htmlFor="current-password" className="block text-xs font-semibold text-zinc-700 mb-1.5">
              Current password
            </label>
            <input
              id="current-password"
              type="password"
              autoComplete="current-password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className={inputCls}
            />
          </div>

          <div>
            <label htmlFor="new-password" className="block text-xs font-semibold text-zinc-700 mb-1.5">
              New password
            </label>
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              required
              value={newPassword}
              onChange={(e) => { setNewPassword(e.target.value); setPolicyError('') }}
              className={inputCls}
              aria-describedby="password-policy-hints"
            />
            {policyError && (
              <p className="mt-1.5 text-xs text-red-600">{policyError}</p>
            )}
            <ul id="password-policy-hints" className="mt-2 space-y-1">
              {POLICY_RULES.map((rule) => (
                <PolicyHint key={rule.id} met={rule.test(newPassword)} label={rule.label} />
              ))}
            </ul>
          </div>

          <div>
            <label htmlFor="confirm-password" className="block text-xs font-semibold text-zinc-700 mb-1.5">
              Confirm new password
            </label>
            <input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              required
              value={confirmPassword}
              onChange={(e) => { setConfirmPassword(e.target.value); setConfirmError('') }}
              className={inputCls}
            />
            {(confirmError || confirmMismatch) && (
              <p className="mt-1.5 text-xs text-red-600">
                {confirmError || 'Passwords do not match.'}
              </p>
            )}
          </div>

          <div className="pt-1">
            <Button type="submit" variant="primary" size="md" loading={saving}>
              {saving ? 'Changing…' : 'Change password'}
            </Button>
          </div>
        </form>
      </Card.Body>
    </Card>
  )
}
