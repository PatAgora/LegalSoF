// Start-verification form: subject details + provider choice.
// Beneficial owners arrive here conceptually from KYB's PSC tree.
import { FormEvent, useState } from 'react'
import { Button, Card } from '../ui'
import { EidvSubjectType, SUBJECT_TYPE_LABELS } from './eidvApi'

interface StartVerificationFormProps {
  onStart: (payload: {
    subject_type: EidvSubjectType
    subject_name: string
    subject_dob?: string
    subject_email?: string
    provider: 'manual' | 'complycube'
  }) => Promise<void>
  starting: boolean
}

export default function StartVerificationForm({ onStart, starting }: StartVerificationFormProps) {
  const [subjectType, setSubjectType] = useState<EidvSubjectType>('client')
  const [name, setName] = useState('')
  const [dob, setDob] = useState('')
  const [email, setEmail] = useState('')
  const [provider, setProvider] = useState<'manual' | 'complycube'>('manual')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (name.trim().length < 2) {
      setError('Enter the subject’s full name.')
      return
    }
    setError(null)
    try {
      await onStart({
        subject_type: subjectType,
        subject_name: name.trim(),
        subject_dob: dob || undefined,
        subject_email: email.trim() || undefined,
        provider,
      })
      setName('')
      setDob('')
      setEmail('')
    } catch (err: any) {
      setError(err?.message || 'Could not start the verification.')
    }
  }

  const inputCls =
    'w-full rounded border border-zinc-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400'

  return (
    <Card>
      <Card.Header>
        <h3 className="text-sm font-semibold text-zinc-900">Start an identity verification</h3>
      </Card.Header>
      <Card.Body>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
                Subject type
              </span>
              <select
                value={subjectType}
                onChange={(e) => setSubjectType(e.target.value as EidvSubjectType)}
                className={inputCls}
              >
                {(Object.keys(SUBJECT_TYPE_LABELS) as EidvSubjectType[]).map((t) => (
                  <option key={t} value={t}>
                    {SUBJECT_TYPE_LABELS[t]}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
                Full name
              </span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Angharad Mair Jones"
                className={inputCls}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
                Date of birth (optional)
              </span>
              <input
                type="date"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                className={inputCls}
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
                Email (optional)
              </span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="subject@example.com"
                className={inputCls}
              />
            </label>
          </div>

          <fieldset>
            <legend className="mb-1 block text-xs font-medium uppercase tracking-wide text-zinc-500">
              Verification method
            </legend>
            <div className="space-y-2">
              <label className="flex items-start gap-2 text-sm text-zinc-700">
                <input
                  type="radio"
                  name="provider"
                  checked={provider === 'manual'}
                  onChange={() => setProvider('manual')}
                  className="mt-0.5"
                />
                <span>
                  <span className="font-medium">Manual (traditional)</span> — solicitor inspects
                  the identity document and records the checklist.{' '}
                  <span className="text-amber-700">
                    Not DIATF-certified digital identity verification.
                  </span>
                </span>
              </label>
              <label className="flex items-start gap-2 text-sm text-zinc-700">
                <input
                  type="radio"
                  name="provider"
                  checked={provider === 'complycube'}
                  onChange={() => setProvider('complycube')}
                  className="mt-0.5"
                />
                <span>
                  <span className="font-medium">ComplyCube (electronic)</span> — DIATF-certifiable
                  digital identity verification. Requires a provider contract and
                  COMPLYCUBE_API_KEY.
                </span>
              </label>
            </div>
          </fieldset>

          {error && (
            <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {error}
            </div>
          )}

          <div className="flex justify-end">
            <Button type="submit" loading={starting}>
              Start verification
            </Button>
          </div>
        </form>
      </Card.Body>
    </Card>
  )
}
