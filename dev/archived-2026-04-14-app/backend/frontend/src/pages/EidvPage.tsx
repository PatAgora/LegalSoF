// E-IDV — identity verification for clients, beneficial owners and
// giftors on a matter. Route: /matters/:matterId/eidv
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Alert, Spinner } from '../components/ui'
import EidvResultsList from '../components/Eidv/EidvResultsList'
import ManualChecklistForm from '../components/Eidv/ManualChecklistForm'
import StartVerificationForm from '../components/Eidv/StartVerificationForm'
import {
  EidvCheck,
  EidvSubjectType,
  ManualResultPayload,
  createEidvCheck,
  listEidvChecks,
  submitManualResult,
} from '../components/Eidv/eidvApi'
import { showToast } from '../lib/toast'

const MANUAL_CAVEAT_FALLBACK =
  'Manual (traditional) verification does NOT constitute DIATF-certified electronic identity ' +
  'verification. Only services certified under the UK Digital Identity and Attributes Trust ' +
  'Framework satisfy MLR 2017 reg 28(19) automatically.'

export default function EidvPage() {
  const { matterId } = useParams<{ matterId: string }>()
  const [checks, setChecks] = useState<EidvCheck[]>([])
  const [caveat, setCaveat] = useState<string>(MANUAL_CAVEAT_FALLBACK)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [completing, setCompleting] = useState<EidvCheck | null>(null)

  const load = useCallback(async () => {
    if (!matterId) return
    try {
      const data = await listEidvChecks(matterId)
      setChecks(data.items)
      if (data.manual_caveat) setCaveat(data.manual_caveat)
      setError(null)
    } catch (e: any) {
      setError(e?.message || 'Could not load identity verifications.')
    } finally {
      setLoading(false)
    }
  }, [matterId])

  useEffect(() => {
    load()
  }, [load])

  const handleStart = async (payload: {
    subject_type: EidvSubjectType
    subject_name: string
    subject_dob?: string
    subject_email?: string
    provider: 'manual' | 'complycube'
  }) => {
    if (!matterId) return
    setStarting(true)
    try {
      const created = await createEidvCheck(matterId, payload)
      setChecks((prev) => [created, ...prev])
      if (created.provider === 'manual') {
        showToast('Manual verification started — complete the checklist to record the result.', 'info')
      } else if (created.client_url) {
        showToast('Electronic verification started — send the client the verification link.', 'success')
      }
    } finally {
      // Errors (incl. the 409 ComplyCube guidance) are shown inline by the form.
      setStarting(false)
    }
  }

  const handleManualResult = async (checkId: number, payload: ManualResultPayload) => {
    if (!matterId) return
    const updated = await submitManualResult(matterId, checkId, payload)
    setChecks((prev) => prev.map((c) => (c.id === checkId ? { ...c, ...updated } : c)))
    setCompleting(null)
    showToast(`Verification recorded — ${updated.status}.`, updated.status === 'passed' ? 'success' : 'info')
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-zinc-500">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="border-b border-zinc-200 pb-6">
        <h1 className="font-serif text-3xl text-zinc-900">Identity Verification (E-IDV)</h1>
        <p className="mt-2 text-sm text-zinc-500">
          Verify the identity of the client, beneficial owners and giftors on this matter.
          Beneficial owners identified in{' '}
          <Link to={`/matters/${matterId}/kyb`} className="underline hover:text-zinc-700">
            company due diligence (KYB)
          </Link>{' '}
          should each be verified here.{' '}
          <Link to={`/matters/${matterId}`} className="underline hover:text-zinc-700">
            Back to matter
          </Link>
        </p>
      </div>

      <Alert variant="warning" title="Manual verification is the traditional route">
        {caveat}
      </Alert>

      {error && <Alert variant="error">{error}</Alert>}

      <StartVerificationForm onStart={handleStart} starting={starting} />

      <EidvResultsList checks={checks} onCompleteManual={(check) => setCompleting(check)} />

      <ManualChecklistForm
        check={completing}
        caveat={caveat}
        onSubmit={handleManualResult}
        onClose={() => setCompleting(null)}
      />
    </div>
  )
}
