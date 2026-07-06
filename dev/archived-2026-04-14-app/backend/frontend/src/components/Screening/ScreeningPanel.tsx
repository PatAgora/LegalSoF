// PEP & Sanctions Screening panel.
//
// Sanctions screening is a STRICT-LIABILITY regime (SAMLA 2018), separate
// from risk-based AML — every party is screened regardless of matter risk.
// The panel offers: a run-screening form (name prefilled from the matter's
// client), the check history with per-hit adjudication (the remediation
// workflow), and the sanctions dataset freshness line.
import { useEffect, useState } from 'react'
import { API_BASE_URL, authFetch } from '../../lib/api'
import { showToast } from '../../lib/toast'
import { formatDate, formatDateTime } from '../../lib/format'
import StatusChip from '../ui/StatusChip'
import { RationaleModal } from '../ui/RationaleModal'

interface ScreeningHit {
  id: number
  check_id: number
  source: string
  category: string
  matched_name: string
  external_ref: string | null
  score: number
  raw: Record<string, any>
  adjudication_status: 'pending' | 'true_match' | 'false_positive'
  adjudication_rationale: string | null
  adjudicated_at: string | null
}

interface ScreeningCheck {
  id: number
  subject_type: string
  subject_name: string
  subject_dob: string | null
  status: 'clear' | 'potential_match' | 'confirmed_match' | 'false_positive'
  requires_escalation: boolean
  dataset_version: string | null
  providers_used: string[]
  created_at: string | null
  hits: ScreeningHit[]
}

interface DatasetStatus {
  available: boolean
  version?: string
  date_generated?: string | null
  imported_at?: string | null
  entry_count?: number
  age_days?: number | null
  stale?: boolean
  warning?: string
}

const SUBJECT_TYPES = [
  { value: 'client', label: 'Client' },
  { value: 'beneficial_owner', label: 'Beneficial owner' },
  { value: 'counterparty', label: 'Counterparty' },
  { value: 'giftor', label: 'Giftor' },
]

const SUBJECT_TYPE_LABEL: Record<string, string> = Object.fromEntries(
  SUBJECT_TYPES.map((t) => [t.value, t.label]),
)

const CATEGORY_SEVERITY: Record<string, 'critical' | 'high' | 'medium'> = {
  sanctions: 'critical',
  pep: 'high',
  adverse_media: 'medium',
}

function checkStatusChip(status: ScreeningCheck['status']) {
  switch (status) {
    case 'confirmed_match':
      return <StatusChip severity="critical" label="CONFIRMED MATCH" />
    case 'potential_match':
      return <StatusChip severity="high" label="POTENTIAL MATCH" />
    case 'false_positive':
      return <StatusChip severity="low" label="FALSE POSITIVE" />
    default:
      return <StatusChip severity="info" label="CLEAR" />
  }
}

async function readError(response: Response, fallback: string): Promise<string> {
  const data = await response.json().catch(() => null)
  if (typeof data?.detail === 'string') return data.detail
  return fallback
}

export default function ScreeningPanel({ matterId, clientName }: {
  matterId: number
  clientName?: string
}) {
  const [checks, setChecks] = useState<ScreeningCheck[]>([])
  const [dataset, setDataset] = useState<DatasetStatus | null>(null)
  const [loading, setLoading] = useState(true)

  // Run form
  const [subjectName, setSubjectName] = useState(clientName || '')
  const [subjectType, setSubjectType] = useState('client')
  const [subjectDob, setSubjectDob] = useState('')
  const [running, setRunning] = useState(false)

  // Adjudication modal
  const [adjudicating, setAdjudicating] = useState<{
    hit: ScreeningHit
    status: 'true_match' | 'false_positive'
  } | null>(null)

  const fetchChecks = async () => {
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/screening`)
      if (!response.ok) throw new Error(await readError(response, 'Failed to load screening checks'))
      const data = await response.json()
      setChecks(data.checks || [])
    } catch (err: any) {
      showToast(err?.message || 'Failed to load screening checks.', 'error')
    }
  }

  const fetchDatasetStatus = async () => {
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/screening/dataset-status`)
      if (response.ok) setDataset(await response.json())
    } catch {
      /* non-blocking */
    }
  }

  useEffect(() => {
    setLoading(true)
    Promise.all([fetchChecks(), fetchDatasetStatus()]).finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matterId])

  useEffect(() => {
    if (clientName && !subjectName) setSubjectName(clientName)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientName])

  const runScreening = async () => {
    const name = subjectName.trim()
    if (name.length < 2) {
      showToast('Enter the subject name to screen.', 'error')
      return
    }
    setRunning(true)
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/screening/run`, {
        method: 'POST',
        body: JSON.stringify({
          subject_name: name,
          subject_type: subjectType,
          subject_dob: subjectDob || null,
        }),
      })
      if (!response.ok) throw new Error(await readError(response, 'Screening run failed'))
      const check: ScreeningCheck & { warning?: string } = await response.json()
      setChecks((prev) => [check, ...prev])
      if (check.warning) showToast(check.warning, 'error')
      if (check.hits.length === 0) {
        showToast(`No matches for "${name}" — check recorded as clear.`, 'success')
      } else {
        showToast(
          `${check.hits.length} potential match(es) for "${name}" — adjudicate each hit below.`,
          'info',
        )
      }
    } catch (err: any) {
      showToast(err?.message || 'Screening run failed.', 'error')
    } finally {
      setRunning(false)
    }
  }

  const submitAdjudication = async (rationale: string) => {
    if (!adjudicating) return
    const { hit, status } = adjudicating
    const response = await authFetch(
      `${API_BASE_URL}/api/v1/matters/${matterId}/screening/hits/${hit.id}/adjudicate`,
      {
        method: 'POST',
        body: JSON.stringify({ status, rationale }),
      },
    )
    if (!response.ok) {
      throw new Error(await readError(response, 'Adjudication failed'))
    }
    const data = await response.json()
    setChecks((prev) => prev.map((c) => (c.id === data.check.id ? data.check : c)))
    setAdjudicating(null)
    if (data.guidance) {
      showToast(data.guidance, 'error')
    } else {
      showToast('Hit adjudicated and recorded in the audit trail.', 'success')
    }
  }

  const hasConfirmedMatch = checks.some(
    (c) => c.status === 'confirmed_match' || c.requires_escalation,
  )

  return (
    <div className="bg-white border border-zinc-200 rounded-md">
      {/* Header */}
      <div className="px-6 pt-5 pb-4 border-b border-zinc-100">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-zinc-900">PEP &amp; Sanctions Screening</h2>
            <p className="mt-1 text-xs text-zinc-500 leading-snug max-w-2xl">
              Sanctions compliance is strict liability and separate from risk-based AML —
              every party is screened against the UK Sanctions List (FCDO) regardless of
              the matter's risk rating.
            </p>
          </div>
        </div>

        {/* Dataset status line */}
        {dataset && (
          <div className="mt-3 text-xs">
            {dataset.available ? (
              <span className={dataset.stale ? 'text-amber-700' : 'text-zinc-500'}>
                UK Sanctions List: version {dataset.version} · {dataset.entry_count?.toLocaleString('en-GB')} entries
                · imported {formatDate(dataset.imported_at)}
                {dataset.stale && (
                  <strong className="ml-1 font-semibold">
                    — dataset is stale (over 7 days old); update it and re-screen open matters.
                  </strong>
                )}
              </span>
            ) : (
              <span className="text-red-700 font-medium">{dataset.warning}</span>
            )}
          </div>
        )}
      </div>

      {/* Confirmed sanctions match banner */}
      {hasConfirmedMatch && (
        <div className="mx-6 mt-4 rounded border-2 border-red-600 bg-red-50 px-4 py-3">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-red-700 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
            <div>
              <p className="text-sm font-bold text-red-800">
                Potential sanctions match — freeze work on this matter and consult your MLRO.
              </p>
              <p className="mt-1 text-xs text-red-700 leading-snug">
                Consider OFSI reporting obligations. Do not deal with any funds or assets:
                breaching an asset freeze is a strict-liability offence under the Sanctions
                and Anti-Money Laundering Act 2018.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Run screening form */}
      <div className="px-6 py-4 border-b border-zinc-100">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[220px]">
            <label className="block text-xs font-semibold text-zinc-600 mb-1">Subject name</label>
            <input
              type="text"
              value={subjectName}
              onChange={(e) => setSubjectName(e.target.value)}
              placeholder="Full name of the person or entity"
              className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-zinc-600 mb-1">Subject type</label>
            <select
              value={subjectType}
              onChange={(e) => setSubjectType(e.target.value)}
              className="border border-zinc-200 rounded px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-zinc-300"
            >
              {SUBJECT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-zinc-600 mb-1">Date of birth (optional)</label>
            <input
              type="date"
              value={subjectDob}
              onChange={(e) => setSubjectDob(e.target.value)}
              className="border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
            />
          </div>
          <button
            onClick={runScreening}
            disabled={running || subjectName.trim().length < 2}
            className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {running ? 'Screening…' : 'Run screening'}
          </button>
        </div>
      </div>

      {/* Checks list */}
      <div className="px-6 py-4">
        {loading ? (
          <p className="text-sm text-zinc-500">Loading screening history…</p>
        ) : checks.length === 0 ? (
          <p className="text-sm text-zinc-500">
            No screening checks have been run on this matter yet. Screen the client and
            every other party (beneficial owners, counterparties, giftors) before funds move.
          </p>
        ) : (
          <div className="space-y-4">
            {checks.map((check) => (
              <div key={check.id} className="border border-zinc-200 rounded-md">
                <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 bg-zinc-50 rounded-t-md">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-zinc-900">{check.subject_name}</span>
                    <span className="text-xs text-zinc-500">
                      {SUBJECT_TYPE_LABEL[check.subject_type] || check.subject_type}
                      {check.subject_dob ? ` · DOB ${formatDate(check.subject_dob)}` : ''}
                    </span>
                    {checkStatusChip(check.status)}
                  </div>
                  <span className="text-[11px] text-zinc-400">
                    {formatDateTime(check.created_at)}
                    {check.dataset_version ? ` · list ${check.dataset_version}` : ''}
                    {check.providers_used?.length ? ` · ${check.providers_used.join(', ')}` : ''}
                  </span>
                </div>

                {check.hits.length === 0 ? (
                  <p className="px-4 py-3 text-xs text-zinc-500">
                    No matches against the screening sources at the time of this check.
                  </p>
                ) : (
                  <ul className="divide-y divide-zinc-100">
                    {check.hits.map((hit) => (
                      <li key={hit.id} className="px-4 py-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-sm font-medium text-zinc-900">{hit.matched_name}</span>
                              <StatusChip
                                severity={CATEGORY_SEVERITY[hit.category] || 'medium'}
                                label={hit.category.replace('_', ' ').toUpperCase()}
                              />
                              <span className="text-[11px] font-semibold text-zinc-600">
                                Score {hit.score}
                              </span>
                            </div>
                            <div className="mt-1 text-[11px] text-zinc-500">
                              Source: {hit.source}
                              {hit.external_ref ? ` · Ref ${hit.external_ref}` : ''}
                              {hit.raw?.matched_alias ? ` · matched alias "${hit.raw.matched_alias}"` : ''}
                              {hit.raw?.dob_note ? ` · DOB ${hit.raw.dob_note}` : ''}
                              {Array.isArray(hit.raw?.regimes) && hit.raw.regimes.length > 0
                                ? ` · ${hit.raw.regimes.join('; ')}`
                                : ''}
                            </div>
                            {hit.adjudication_status !== 'pending' && (
                              <div className="mt-1.5 text-[11px] text-zinc-600">
                                <span className={`font-semibold ${hit.adjudication_status === 'true_match' ? 'text-red-700' : 'text-green-700'}`}>
                                  {hit.adjudication_status === 'true_match' ? 'TRUE MATCH' : 'FALSE POSITIVE'}
                                </span>
                                {hit.adjudicated_at ? ` · ${formatDateTime(hit.adjudicated_at)}` : ''}
                                {hit.adjudication_rationale ? ` — ${hit.adjudication_rationale}` : ''}
                              </div>
                            )}
                          </div>
                          {hit.adjudication_status === 'pending' && (
                            <div className="flex flex-shrink-0 gap-2">
                              <button
                                onClick={() => setAdjudicating({ hit, status: 'false_positive' })}
                                className="px-3 py-1.5 text-xs font-medium rounded border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 transition-colors"
                              >
                                False positive
                              </button>
                              <button
                                onClick={() => setAdjudicating({ hit, status: 'true_match' })}
                                className="px-3 py-1.5 text-xs font-semibold rounded bg-red-700 text-white hover:bg-red-800 transition-colors"
                              >
                                Confirm true match
                              </button>
                            </div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Adjudication rationale modal */}
      <RationaleModal
        isOpen={adjudicating !== null}
        title={
          adjudicating?.status === 'true_match'
            ? `Confirm TRUE sanctions/PEP match: ${adjudicating?.hit.matched_name ?? ''}`
            : `Mark as false positive: ${adjudicating?.hit.matched_name ?? ''}`
        }
        description={
          adjudicating?.status === 'true_match'
            ? 'Confirming a true match places this matter in a sanctions-freeze posture: work must stop, your MLRO must be consulted, and OFSI reporting obligations considered. Record why you are satisfied this is the designated person.'
            : 'Record why this hit does not relate to the subject (e.g. different date of birth, nationality, or entity). The rationale is retained in the audit trail.'
        }
        minLength={10}
        confirmLabel={adjudicating?.status === 'true_match' ? 'Confirm true match' : 'Mark false positive'}
        destructive={adjudicating?.status === 'true_match'}
        placeholder="Explain the evidence supporting this decision…"
        onConfirm={submitAdjudication}
        onClose={() => setAdjudicating(null)}
      />
    </div>
  )
}
