// KYB — company due diligence via Companies House for a matter.
// Route: /matters/:matterId/kyb
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Alert, Spinner } from '../components/ui'
import CompanySearch from '../components/KYB/CompanySearch'
import KybCheckDetail from '../components/KYB/KybCheckDetail'
import {
  KybCheck,
  createKybCheck,
  listKybChecks,
  refreshKybCheck,
  reportPscDiscrepancy,
} from '../components/KYB/kybApi'
import { showToast } from '../lib/toast'

const REG_28_9_FALLBACK =
  'MLR 2017 reg 28(9): the PSC register alone is NOT verification of beneficial owners. ' +
  'Use PSC data as a cross-check only — each beneficial owner holding more than 25% must be ' +
  'identified and verified individually (see E-IDV).'

export default function KybPage() {
  const { matterId } = useParams<{ matterId: string }>()
  const [checks, setChecks] = useState<KybCheck[]>([])
  const [regNote, setRegNote] = useState<string>(REG_28_9_FALLBACK)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [refreshingId, setRefreshingId] = useState<number | null>(null)

  const load = useCallback(async () => {
    if (!matterId) return
    try {
      const data = await listKybChecks(matterId)
      setChecks(data.items)
      if (data.reg_28_9_note) setRegNote(data.reg_28_9_note)
      setError(null)
    } catch (e: any) {
      setError(e?.message || 'Could not load KYB checks.')
    } finally {
      setLoading(false)
    }
  }, [matterId])

  useEffect(() => {
    load()
  }, [load])

  const handleRunCheck = async (companyNumber: string) => {
    if (!matterId) return
    setRunning(true)
    try {
      const created = await createKybCheck(matterId, companyNumber)
      setChecks((prev) => [created, ...prev])
      showToast(`KYB check completed for ${created.company_name || companyNumber}.`, 'success')
    } catch (e: any) {
      showToast(e?.message || 'KYB check failed.', 'error')
    } finally {
      setRunning(false)
    }
  }

  const handleRefresh = async (checkId: number) => {
    if (!matterId) return
    setRefreshingId(checkId)
    try {
      const updated = await refreshKybCheck(matterId, checkId)
      setChecks((prev) => prev.map((c) => (c.id === checkId ? { ...c, ...updated } : c)))
      showToast('Snapshot refreshed from Companies House.', 'success')
    } catch (e: any) {
      showToast(e?.message || 'Refresh failed.', 'error')
    } finally {
      setRefreshingId(null)
    }
  }

  const handleReportDiscrepancy = async (checkId: number, details: string) => {
    if (!matterId) return
    const updated = await reportPscDiscrepancy(matterId, checkId, details)
    setChecks((prev) => prev.map((c) => (c.id === checkId ? { ...c, ...updated } : c)))
    showToast(
      'Discrepancy recorded. Remember: the firm must report it to Companies House (reg 30A).',
      'info',
    )
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
        <div className="flex items-center gap-3">
          <h1 className="font-serif text-3xl text-zinc-900">Company Due Diligence (KYB)</h1>
        </div>
        <p className="mt-2 text-sm text-zinc-500">
          Search Companies House, capture the company profile, officers and PSC register for this
          matter, and record any material PSC discrepancies.{' '}
          <Link to={`/matters/${matterId}`} className="underline hover:text-zinc-700">
            Back to matter
          </Link>
        </p>
      </div>

      {/* reg 28(9) — persistent compliance banner */}
      <Alert variant="warning" title="PSC register is a cross-check, not verification">
        {regNote}{' '}
        <Link to={`/matters/${matterId}/eidv`} className="font-semibold underline">
          Go to E-IDV →
        </Link>
      </Alert>

      {error && <Alert variant="error">{error}</Alert>}

      <CompanySearch onRunCheck={handleRunCheck} running={running} />

      {checks.length === 0 ? (
        <p className="py-8 text-center text-sm text-zinc-500">
          No KYB checks on this matter yet — search for a company above to run the first check.
        </p>
      ) : (
        <div className="space-y-8">
          {checks.map((check) => (
            <KybCheckDetail
              key={check.id}
              matterId={matterId || ''}
              check={check}
              onRefresh={handleRefresh}
              onReportDiscrepancy={handleReportDiscrepancy}
              refreshing={refreshingId === check.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}
