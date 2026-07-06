import { useParams, useSearchParams, Link } from 'react-router-dom'
import { useState, useEffect } from 'react'
import TransactionList from '../components/TransactionReview/TransactionList'
import SoFAssessment from '../components/SoFAssessment/SoFAssessment'
import FundsLineage from '../components/FundsLineage/FundsLineage'
import DocumentVerificationPage from '../components/DocumentVerification/DocumentVerificationPage'
import ScreeningPanel from '../components/Screening/ScreeningPanel'
import ReportSuspicionButton from '../components/Mlro/ReportSuspicionButton'
import { API_BASE_URL, authFetch } from '../lib/api'
import { useCurrentMatter } from '../stores/currentMatterStore'
import { useAuthStore } from '../stores/authStore'
import MatterStatusBadge from '../components/ui/MatterStatusBadge'
import Modal from '../components/ui/Modal'
import { RationaleModal } from '../components/ui/RationaleModal'
import { showToast } from '../lib/toast'
import { formatCurrencyWhole, formatDate, formatDateTime } from '../lib/format'

type TabType = 'sof-assessment' | 'transactions' | 'funds-lineage' | 'verification' | 'screening' | 'audit-trail'

const VALID_TABS: TabType[] = [
  'sof-assessment', 'transactions', 'funds-lineage', 'verification', 'screening', 'audit-trail',
]

export default function MatterDetailPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const tabParam = searchParams.get('tab') as TabType | null
  const activeTab: TabType = (tabParam && VALID_TABS.includes(tabParam)) ? tabParam : 'sof-assessment'
  // The compliance review panel is the compliance team's surface. It
  // shows when the matter is opened from a Compliance route
  // (?from=compliance) and, for admin (compliance officer) users, on the
  // normal Workspace route too.
  const fromCompliance = searchParams.get('from') === 'compliance'
  const currentUser = useAuthStore((s) => s.user)
  const isAdmin = String(currentUser?.role || '').toLowerCase() === 'admin'
  const showCompliancePanel = fromCompliance || isAdmin

  const [matter, setMatter] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showClientLinksModal, setShowClientLinksModal] = useState(false)

  const setCurrentMatter = useCurrentMatter((s) => s.setMatter)
  const clearCurrentMatter = useCurrentMatter((s) => s.clearMatter)

  // Fetch (or re-fetch) the matter from the API.
  const refreshMatter = async (showSpinner = false) => {
    try {
      if (showSpinner) setLoading(true)
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${id}`)
      if (!response.ok) throw new Error('Failed to fetch matter')
      const data = await response.json()
      setMatter(data)
      setCurrentMatter({
        id: data.id,
        reference_number: data.reference_number ?? null,
        client_name: data.client_name ?? null,
        transaction_type: data.transaction_type ?? null,
      })
    } catch (err) {
      console.debug('Error fetching matter:', err)
      if (showSpinner) setError('Failed to load matter details. Please try again.')
    } finally {
      if (showSpinner) setLoading(false)
    }
  }

  useEffect(() => {
    if (id) refreshMatter(true)
    // Clear the sidebar context when leaving the matter detail page.
    return () => {
      clearCurrentMatter()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-zinc-600"></div>
          <p className="mt-4 text-zinc-600">Loading matter details...</p>
        </div>
      </div>
    )
  }

  if (error || !matter) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-red-700 text-lg">{error || 'Matter not found'}</p>
          <button
            onClick={() => refreshMatter(true)}
            className="mt-4 bg-zinc-900 text-white px-4 py-2 rounded"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* Header - serif title above hairline rule */}
      <div className="mb-8 border-b border-zinc-200 pb-6">
        <div className="flex justify-between items-end">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-serif text-3xl font-normal tracking-tight text-zinc-900">{matter.reference_number}</h1>
              <MatterStatusBadge status={matter.status} />
            </div>
            <p className="mt-2 text-sm text-zinc-500">
              {matter.client_name} - {matter.transaction_type?.replace(/_/g, ' ') || 'Transaction'}
            </p>
            <MatterMetaRow matter={matter} onSaved={() => refreshMatter()} />
          </div>
          <div className="flex-shrink-0 flex items-center gap-2">
            <ReportSuspicionButton
              matterId={matter.id}
              matterReference={matter.reference_number}
            />
            <button
              onClick={() => setShowClientLinksModal(true)}
              className="px-3.5 py-2 text-sm font-medium rounded border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 transition-colors"
            >
              Request client documents
            </button>
          </div>
        </div>
        {/* Compliance quick-links: the AML workflow steps for this matter. */}
        <div className="mt-4 flex flex-wrap gap-2 border-t border-zinc-100 pt-3">
          <Link
            to={`/matters/${matter.id}/risk-assessment`}
            className="px-3 py-1.5 text-xs font-medium rounded border border-zinc-200 bg-zinc-50 text-zinc-700 hover:bg-zinc-100 transition-colors"
          >
            Risk assessment
          </Link>
          <Link
            to={`/matters/${matter.id}/eidv`}
            className="px-3 py-1.5 text-xs font-medium rounded border border-zinc-200 bg-zinc-50 text-zinc-700 hover:bg-zinc-100 transition-colors"
          >
            Identity verification
          </Link>
          <Link
            to={`/matters/${matter.id}/kyb`}
            className="px-3 py-1.5 text-xs font-medium rounded border border-zinc-200 bg-zinc-50 text-zinc-700 hover:bg-zinc-100 transition-colors"
          >
            Company checks (KYB)
          </Link>
        </div>
      </div>

      <ClientUploadLinksModal
        matterId={matter.id}
        isOpen={showClientLinksModal}
        onClose={() => setShowClientLinksModal(false)}
      />

      {/* Compliance review panel - Compliance route, plus admins anywhere. */}
      {showCompliancePanel && (
        <ComplianceReviewPanel matter={matter} onReviewed={() => refreshMatter()} />
      )}

      {/* Tab Content - sidebar drives `?tab=`; no in-page tab bar. */}
      <div className="min-h-[600px]">
        {activeTab === 'sof-assessment' && (
          <div className="space-y-6">
            {/* PEP/sanctions screening is strict-liability and applies to every
                matter regardless of risk, so it sits prominently above the
                risk-based SoF assessment. Also reachable via ?tab=screening. */}
            <ScreeningPanel matterId={matter.id} clientName={matter.client_name} />
            <SoFAssessment matterId={matter.id} />
          </div>
        )}
        {activeTab === 'transactions' && <TransactionReviewTab matterId={matter.id} />}
        {activeTab === 'funds-lineage' && <FundsLineageTab matterId={matter.id} />}
        {activeTab === 'verification' && <DocumentVerificationPage matterId={matter.id} />}
        {activeTab === 'screening' && <ScreeningPanel matterId={matter.id} clientName={matter.client_name} />}
        {activeTab === 'audit-trail' && <AuditTrailTab matterId={matter.id} />}
      </div>
    </div>
  )
}

// ──────────────────────────────────────────
// Client evidence-upload links (portal)
// ──────────────────────────────────────────

interface ClientUploadLink {
  id: number
  token: string
  url_path: string
  expires_at: string | null
  max_uploads: number
  upload_count: number
  revoked: boolean
  active: boolean
  created_at: string | null
}

function ClientUploadLinksModal({ matterId, isOpen, onClose }: {
  matterId: number
  isOpen: boolean
  onClose: () => void
}) {
  const [links, setLinks] = useState<ClientUploadLink[]>([])
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [expiresInDays, setExpiresInDays] = useState('14')
  const [copiedId, setCopiedId] = useState<number | null>(null)

  const fullUrl = (link: ClientUploadLink) => `${window.location.origin}${link.url_path}`

  const loadLinks = async () => {
    setLoading(true)
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/client-upload-links`)
      if (r.ok) {
        const d = await r.json()
        setLinks(d.links || [])
      }
    } catch {
      // Non-blocking — the list simply stays empty.
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) loadLinks()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, matterId])

  const generateLink = async () => {
    setGenerating(true)
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/client-upload-link`, {
        method: 'POST',
        body: JSON.stringify({ expires_in_days: Number(expiresInDays) }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        showToast(`Could not create the link: ${err.detail || r.statusText}`, 'error')
        return
      }
      showToast('Client upload link created.', 'success')
      await loadLinks()
    } catch (e: any) {
      showToast(`Could not create the link: ${e?.message || 'Unknown error'}`, 'error')
    } finally {
      setGenerating(false)
    }
  }

  const copyLink = async (link: ClientUploadLink) => {
    try {
      await navigator.clipboard.writeText(fullUrl(link))
      setCopiedId(link.id)
      window.setTimeout(() => setCopiedId((prev) => (prev === link.id ? null : prev)), 2000)
    } catch {
      showToast('Could not copy the link — copy it manually from the box.', 'error')
    }
  }

  const revokeLink = async (link: ClientUploadLink) => {
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/client-upload-link/${link.id}`, {
        method: 'DELETE',
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        showToast(`Could not revoke the link: ${err.detail || r.statusText}`, 'error')
        return
      }
      showToast('Upload link revoked.', 'success')
      await loadLinks()
    } catch (e: any) {
      showToast(`Could not revoke the link: ${e?.message || 'Unknown error'}`, 'error')
    }
  }

  const activeLinks = links.filter((l) => l.active)
  const inactiveCount = links.length - activeLinks.length

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Request client documents" size="lg">
      <div className="space-y-5">
        <p className="text-sm text-zinc-600 leading-relaxed">
          Generate a secure link the client can use to upload bank statements
          and supporting documents directly to this matter — no account
          needed. Links are time-limited and can be revoked at any time.
        </p>

        {/* Generate */}
        <div className="flex items-end gap-3 rounded-md border border-zinc-200 bg-zinc-50/60 px-4 py-3">
          <div>
            <label htmlFor="client-link-expiry" className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1">
              Link valid for
            </label>
            <select
              id="client-link-expiry"
              value={expiresInDays}
              onChange={(e) => setExpiresInDays(e.target.value)}
              className="rounded border border-zinc-200 bg-white px-2 py-1.5 text-sm text-zinc-900 focus:border-zinc-300 focus:ring-2 focus:ring-zinc-200 focus:outline-none"
            >
              <option value="7">7 days</option>
              <option value="14">14 days</option>
              <option value="30">30 days</option>
            </select>
          </div>
          <button
            onClick={generateLink}
            disabled={generating}
            className="px-3.5 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-60 transition-colors"
          >
            {generating ? 'Generating…' : 'Generate link'}
          </button>
        </div>

        {/* Active links */}
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">
            Active links
          </div>
          {loading ? (
            <div className="py-6 text-center text-sm text-zinc-400">Loading…</div>
          ) : activeLinks.length === 0 ? (
            <div className="py-4 text-sm text-zinc-400 italic">
              No active links. Generate one above and send it to the client.
            </div>
          ) : (
            <ul className="space-y-2">
              {activeLinks.map((link) => (
                <li key={link.id} className="rounded-md border border-zinc-200 px-4 py-3">
                  <div className="flex items-center gap-2">
                    <input
                      readOnly
                      value={fullUrl(link)}
                      onFocus={(e) => e.target.select()}
                      className="flex-1 min-w-0 rounded border border-zinc-200 bg-zinc-50 px-2 py-1.5 text-xs text-zinc-700 font-mono focus:outline-none"
                    />
                    <button
                      onClick={() => copyLink(link)}
                      className="flex-shrink-0 px-3 py-1.5 text-xs font-medium rounded border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 transition-colors"
                    >
                      {copiedId === link.id ? 'Copied' : 'Copy'}
                    </button>
                    <button
                      onClick={() => revokeLink(link)}
                      className="flex-shrink-0 px-3 py-1.5 text-xs font-medium rounded border border-red-200 bg-white text-red-700 hover:bg-red-50 transition-colors"
                    >
                      Revoke
                    </button>
                  </div>
                  <div className="mt-1.5 text-xs text-zinc-400">
                    Expires {formatDate(link.expires_at)}
                    <span className="mx-1.5">·</span>
                    {link.upload_count} of {link.max_uploads} uploads used
                  </div>
                </li>
              ))}
            </ul>
          )}
          {inactiveCount > 0 && (
            <p className="mt-2 text-xs text-zinc-400">
              {inactiveCount} expired or revoked link{inactiveCount === 1 ? '' : 's'} not shown.
            </p>
          )}
        </div>
      </div>
    </Modal>
  )
}

// ──────────────────────────────────────────
// Assignment + target date meta row (header)
// ──────────────────────────────────────────

interface PickerUser {
  id: number
  full_name: string
  email: string
  role: string
}

function MatterMetaRow({ matter, onSaved }: { matter: any; onSaved: () => void }) {
  const currentUser = useAuthStore((s) => s.user)
  const role = String(currentUser?.role || '').toLowerCase()
  // Mirrors the backend policy on PATCH /matters/{id}/assign: admins
  // and partners always; otherwise only the currently assigned analyst.
  const canAssign =
    role === 'admin' || role === 'partner' ||
    (currentUser?.id != null && matter.assigned_analyst_id === currentUser.id)

  const [users, setUsers] = useState<PickerUser[]>([])
  const [editingAssign, setEditingAssign] = useState(false)
  const [assignValue, setAssignValue] = useState<string>('')
  const [savingAssign, setSavingAssign] = useState(false)
  const [editingTarget, setEditingTarget] = useState(false)
  const [targetValue, setTargetValue] = useState<string>('')
  const [savingTarget, setSavingTarget] = useState(false)

  useEffect(() => {
    if (!canAssign) return
    let cancelled = false
    ;(async () => {
      try {
        const r = await authFetch(`${API_BASE_URL}/api/v1/users`)
        if (r.ok && !cancelled) setUsers(await r.json())
      } catch {
        // Non-blocking — the picker simply stays empty.
      }
    })()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canAssign])

  const saveAssignment = async () => {
    setSavingAssign(true)
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matter.id}/assign`, {
        method: 'PATCH',
        body: JSON.stringify({
          assigned_analyst_id: assignValue ? Number(assignValue) : null,
        }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        showToast(`Could not update assignment: ${err.detail || r.statusText}`, 'error')
        return
      }
      const d = await r.json()
      showToast(
        d.assigned_analyst_name
          ? `Matter assigned to ${d.assigned_analyst_name}.`
          : 'Matter unassigned.',
        'success',
      )
      setEditingAssign(false)
      onSaved()
    } catch (e: any) {
      showToast(`Could not update assignment: ${e?.message || 'Unknown error'}`, 'error')
    } finally {
      setSavingAssign(false)
    }
  }

  const saveTargetDate = async () => {
    setSavingTarget(true)
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matter.id}/target-date`, {
        method: 'PATCH',
        body: JSON.stringify({ target_completion_date: targetValue || null }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        showToast(`Could not update target date: ${err.detail || r.statusText}`, 'error')
        return
      }
      const d = await r.json()
      showToast(
        d.target_completion_date
          ? `Target completion date set to ${formatDate(d.target_completion_date)}.`
          : 'Target completion date cleared.',
        'success',
      )
      setEditingTarget(false)
      onSaved()
    } catch (e: any) {
      showToast(`Could not update target date: ${e?.message || 'Unknown error'}`, 'error')
    } finally {
      setSavingTarget(false)
    }
  }

  const inlineButton =
    'px-2.5 py-1 text-xs font-medium rounded border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 disabled:opacity-60 transition-colors'

  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-8 gap-y-2 text-sm">
      {/* Assigned analyst */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Assigned to</span>
        {editingAssign ? (
          <span className="inline-flex items-center gap-2">
            <select
              value={assignValue}
              onChange={(e) => setAssignValue(e.target.value)}
              className="rounded border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-900 focus:border-zinc-300 focus:ring-2 focus:ring-zinc-200 focus:outline-none"
            >
              <option value="">Unassigned</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.full_name} ({u.role})</option>
              ))}
            </select>
            <button onClick={saveAssignment} disabled={savingAssign} className={inlineButton}>
              {savingAssign ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={() => setEditingAssign(false)}
              disabled={savingAssign}
              className="text-xs text-zinc-400 hover:text-zinc-600"
            >
              Cancel
            </button>
          </span>
        ) : (
          <span className="inline-flex items-center gap-2">
            {matter.assigned_analyst_name ? (
              <span className="text-zinc-900 font-medium">{matter.assigned_analyst_name}</span>
            ) : (
              <span className="text-zinc-400 italic">Unassigned</span>
            )}
            {canAssign && (
              <button
                onClick={() => {
                  setAssignValue(matter.assigned_analyst_id ? String(matter.assigned_analyst_id) : '')
                  setEditingAssign(true)
                }}
                className={inlineButton}
              >
                {matter.assigned_analyst_id ? 'Reassign' : 'Assign'}
              </button>
            )}
          </span>
        )}
      </div>

      {/* Target completion date */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Target date</span>
        {editingTarget ? (
          <span className="inline-flex items-center gap-2">
            <input
              type="date"
              value={targetValue}
              onChange={(e) => setTargetValue(e.target.value)}
              className="rounded border border-zinc-200 bg-white px-2 py-1 text-xs text-zinc-900 focus:border-zinc-300 focus:ring-2 focus:ring-zinc-200 focus:outline-none"
            />
            <button onClick={saveTargetDate} disabled={savingTarget} className={inlineButton}>
              {savingTarget ? 'Saving...' : 'Save'}
            </button>
            <button
              onClick={() => setEditingTarget(false)}
              disabled={savingTarget}
              className="text-xs text-zinc-400 hover:text-zinc-600"
            >
              Cancel
            </button>
          </span>
        ) : (
          <span className="inline-flex items-center gap-2">
            {matter.target_completion_date ? (
              <span className={`tabular-nums ${matter.is_overdue ? 'text-red-700 font-semibold' : 'text-zinc-900 font-medium'}`}>
                {formatDate(matter.target_completion_date)}
              </span>
            ) : (
              <span className="text-zinc-400 italic">Not set</span>
            )}
            {matter.is_overdue && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-red-50 border border-red-200 text-red-700">
                Overdue
              </span>
            )}
            <button
              onClick={() => {
                setTargetValue(matter.target_completion_date || '')
                setEditingTarget(true)
              }}
              className={inlineButton}
            >
              {matter.target_completion_date ? 'Edit' : 'Set date'}
            </button>
          </span>
        )}
      </div>
    </div>
  )
}

// Transaction Review Tab
function TransactionReviewTab({ matterId }: { matterId: number }) {
  return (
    <div className="space-y-6">
      <TransactionList matterId={matterId} />
    </div>
  )
}

// Funds Lineage Tab - Only active for savings claims
function FundsLineageTab({ matterId }: { matterId: number }) {
  const [transactions, setTransactions] = useState<any[]>([])
  const [sofClaims, setSofClaims] = useState<any[]>([])
  const [hasSavingsClaim, setHasSavingsClaim] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        
        // Fetch transactions - request ALL (set high limit to get both accounts)
        const txnResponse = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/transactions?limit=1000`)
        let txnData: any[] = []
        if (txnResponse.ok) {
          txnData = await txnResponse.json()
        }
        
        // Fetch SoF assessment to check for savings claims
        let claims: any[] = []
        let isSavingsClaim = false
        
        // Try results endpoint first
        const sofResponse = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/results`)
        
        if (sofResponse.ok) {
          const sofData = await sofResponse.json()

          // Data is nested inside 'assessment' object
          const assessment = sofData.assessment || sofData

          claims = assessment.claims || sofData.claims || []

          // Check if any claim is savings-related
          if (claims.length > 0) {
            isSavingsClaim = claims.some((claim: any) => {
              const sourceType = (claim.source_type || '').toLowerCase()
              return sourceType.includes('saving') || sourceType.includes('accumul')
            })
          }

          // Also check evidence for savings claims
          const evidence = assessment.evidence || sofData.evidence || []

          if (!isSavingsClaim && evidence.length > 0) {
            for (const ev of evidence) {
              const claimSource = (ev.claim_source || '').toLowerCase()
              if (claimSource.includes('saving') || claimSource.includes('accumul')) {
                isSavingsClaim = true
                if (claims.length === 0) {
                  claims = evidence.map((e: any) => ({ source_type: e.claim_source, expected_amount: e.amount || 0 }))
                }
                break
              }
            }
          }
          
          // Also check questionnaire answers for savings
          const questionnaireAnswers = assessment.questionnaire_answers || sofData.questionnaire_answers
          if (!isSavingsClaim && questionnaireAnswers) {
            for (const key in questionnaireAnswers) {
              const answer = String(questionnaireAnswers[key] || '').toLowerCase()
              if (answer.includes('saving') || answer.includes('accumul')) {
                isSavingsClaim = true
                break
              }
            }
          }
        }

        // If no results yet or no savings found, also check the status endpoint
        if (!isSavingsClaim) {
          const statusResponse = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/status`)
          if (statusResponse.ok) {
            const statusData = await statusResponse.json()

            // Check questionnaire answers
            if (statusData.questionnaire_answers) {
              const answers = statusData.questionnaire_answers
              for (const key in answers) {
                const answer = String(answers[key] || '').toLowerCase()
                if (answer.includes('saving') || answer.includes('accumul')) {
                  isSavingsClaim = true
                  break
                }
              }
            }
            
            // Check the entire response as JSON string for savings keywords
            if (!isSavingsClaim) {
              const statusStr = JSON.stringify(statusData).toLowerCase()
              if (statusStr.includes('saving') || statusStr.includes('accumul')) {
                isSavingsClaim = true
              }
            }
          }
        }

        // Transform transaction data
        const formattedTransactions = (txnData || []).map((t: any, idx: number) => {
          const directionLower = (t.direction || '').toLowerCase()
          const isCredit = directionLower === 'in' || directionLower === 'credit'
          
          // Build account identifier from backend fields
          // CRITICAL: customer_id is ALWAYS populated by the backend with the account_id value
          // account_id field might be null/undefined for older data
          let accountId = t.customer_id || t.account_id || 'Unknown'
          
          // If we have bank_name and account_type, make it more descriptive
          let accountDisplay = accountId
          if (t.bank_name && t.account_type && t.bank_name !== '' && t.account_type !== '') {
            accountDisplay = `${t.bank_name} ${t.account_type} (${accountId})`
          } else if (t.bank_name && t.bank_name !== '') {
            accountDisplay = `${t.bank_name} (${accountId})`
          } else if (t.account_type && t.account_type !== '') {
            accountDisplay = `${t.account_type} (${accountId})`
          } else if (accountId && accountId !== 'Unknown' && accountId !== '') {
            // Just use the account ID if that's all we have - this should work for distinguishing accounts
            accountDisplay = `Account ${accountId}`
          }

          return {
            id: t.id?.toString() || `TXN-${idx}`,
            date: t.txn_date || t.date || t.transaction_date,
            description: t.narrative || t.description || '',
            amount: t.amount,
            type: isCredit ? 'credit' : 'debit',
            balance: t.balance,
            counterparty: t.counterparty || t.payee || '',
            account: accountDisplay,
            currency: t.currency || 'GBP',
            direction: t.direction
          }
        })
        
        setTransactions(formattedTransactions)
        setSofClaims(claims)
        setHasSavingsClaim(isSavingsClaim)

      } catch (err) {
        console.debug('Funds Lineage: error fetching data:', err)
      } finally {
        setLoading(false)
      }
    }

    if (matterId) {
      fetchData()
    }
  }, [matterId])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-600"></div>
          <p className="mt-2 text-zinc-600">Loading funds lineage data...</p>
        </div>
      </div>
    )
  }

  // Show message if no savings claim
  if (!hasSavingsClaim) {
    return (
      <div className="space-y-6">
        <div className="bg-white border border-zinc-200 rounded-md p-6">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">🔗</span>
            <h2 className="text-xl font-bold text-zinc-900">Backward Funds Lineage</h2>
          </div>
          
          <div className="bg-zinc-50 border border-zinc-200 rounded-md p-4">
            <div className="text-zinc-900">
              <div className="font-semibold mb-2">ℹ️ Funds Lineage Not Required</div>
              <p className="text-sm">
                The Backward Funds Lineage tool is designed for <strong>savings accumulation claims</strong> where
                funds need to be traced through multiple accounts over time.
              </p>
              <p className="text-sm mt-2">
                The current SoF claims for this matter do not include savings-based sources.
                This tool will become active if a savings claim is added.
              </p>
              <div className="mt-4 p-3 bg-white rounded border border-zinc-200">
                <div className="text-xs font-semibold text-zinc-600 mb-2">Current Claims:</div>
                {sofClaims.length > 0 ? (
                  <ul className="text-xs text-zinc-600 space-y-1">
                    {sofClaims.map((claim, idx) => (
                      <li key={idx}>• {claim.source_type}: {formatCurrencyWhole(claim.expected_amount)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-zinc-400">No claims recorded yet. Complete the SoF Assessment first.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <FundsLineage matterId={matterId} transactions={transactions} sofClaims={sofClaims} />
    </div>
  )
}

// Audit Trail Tab
interface AuditEntry {
  id: number
  action: string
  entity_type: string | null
  entity_id: number | null
  description: string
  details: Record<string, any> | null
  user_name: string | null
  user_email: string | null
  created_at: string | null
}

interface StatusHistoryEntry {
  id: number
  old_status: string
  new_status: string
  reason: string | null
  changed_by_name: string | null
  changed_by_email: string | null
  changed_at: string | null
}

function AuditTrailTab({ matterId }: { matterId: number }) {
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([])
  const [statusHistory, setStatusHistory] = useState<StatusHistoryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [activeSection, setActiveSection] = useState<'audit' | 'status'>('audit')

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const [auditRes, statusRes] = await Promise.all([
          authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/audit-trail`),
          authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/status-history`),
        ])

        if (auditRes.ok) {
          setAuditLogs(await auditRes.json())
        }
        if (statusRes.ok) {
          setStatusHistory(await statusRes.json())
        }
      } catch (err) {
        console.debug('Error fetching audit data:', err)
      } finally {
        setLoading(false)
      }
    }

    if (matterId) fetchData()
  }, [matterId])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-600"></div>
          <p className="mt-2 text-zinc-600">Loading audit trail...</p>
        </div>
      </div>
    )
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '--'
    const d = new Date(dateStr)
    return d.toLocaleString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

  const actionBadgeColor = (action: string) => {
    switch (action) {
      case 'matter_created':
      case 'created':
        return 'bg-green-100 text-green-700'
      case 'status_changed':
        return 'bg-blue-100 text-blue-700'
      case 'report_generated':
      case 'exported':
        return 'bg-zinc-100 text-zinc-900'
      case 'alert_reviewed':
        return 'bg-amber-100 text-amber-700'
      case 'approved':
        return 'bg-green-100 text-green-700'
      case 'rejected':
        return 'bg-red-100 text-red-700'
      default:
        return 'bg-zinc-50 text-zinc-900'
    }
  }

  const statusBadgeColor = (status: string) => {
    switch (status) {
      case 'Verified':
        return 'bg-green-100 text-green-700 border-green-200'
      case 'Returned from Compliance':
        return 'bg-red-100 text-red-700 border-red-200'
      case 'Sent to Compliance':
        return 'bg-blue-100 text-blue-700 border-blue-200'
      case 'Under Review':
        return 'bg-amber-100 text-amber-700 border-amber-200'
      default:
        return 'bg-zinc-50 text-zinc-600 border-zinc-200'
    }
  }

  return (
    <div className="space-y-6">
      {/* Section toggle */}
      <div className="flex space-x-2 border-b border-zinc-200 pb-2">
        <button
          onClick={() => setActiveSection('audit')}
          className={`px-4 py-2 text-sm font-medium rounded-t-lg ${
            activeSection === 'audit'
              ? 'bg-zinc-50 text-zinc-900 border-b-2 border-zinc-900'
              : 'text-zinc-400 hover:text-zinc-600'
          }`}
        >
          Activity Log ({auditLogs.length})
        </button>
        <button
          onClick={() => setActiveSection('status')}
          className={`px-4 py-2 text-sm font-medium rounded-t-lg ${
            activeSection === 'status'
              ? 'bg-zinc-50 text-zinc-900 border-b-2 border-zinc-900'
              : 'text-zinc-400 hover:text-zinc-600'
          }`}
        >
          Status History ({statusHistory.length})
        </button>
      </div>

      {/* Activity Log */}
      {activeSection === 'audit' && (
        <div className="bg-white border border-zinc-200 rounded-md overflow-hidden">
          {auditLogs.length === 0 ? (
            <div className="px-6 py-8 text-center text-sm text-zinc-400">
              No audit log entries yet.
            </div>
          ) : (
            <div className="divide-y divide-brand-muted">
              {auditLogs.map(entry => (
                <div key={entry.id} className="px-6 py-4 flex items-start gap-4">
                  <div className="flex-shrink-0 mt-0.5">
                    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${actionBadgeColor(entry.action)}`}>
                      {entry.action?.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-900">{entry.description}</p>
                    <p className="text-xs text-zinc-400 mt-1">
                      {entry.user_name || entry.user_email || 'System'} -- {formatDate(entry.created_at)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Status History */}
      {activeSection === 'status' && (
        <div className="bg-white border border-zinc-200 rounded-md overflow-hidden">
          {statusHistory.length === 0 ? (
            <div className="px-6 py-8 text-center text-sm text-zinc-400">
              No status changes recorded yet.
            </div>
          ) : (
            <div className="divide-y divide-brand-muted">
              {statusHistory.map(entry => (
                <div key={entry.id} className="px-6 py-4">
                  <div className="flex items-center gap-3 mb-2">
                    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded border ${statusBadgeColor(entry.old_status)}`}>
                      {entry.old_status?.replace(/_/g, ' ')}
                    </span>
                    <svg className="w-4 h-4 text-zinc-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                    </svg>
                    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded border ${statusBadgeColor(entry.new_status)}`}>
                      {entry.new_status?.replace(/_/g, ' ')}
                    </span>
                  </div>
                  {entry.reason && (
                    <p className="text-sm text-zinc-600 mt-1">
                      <span className="font-medium">Reason:</span> {entry.reason}
                    </p>
                  )}
                  <p className="text-xs text-zinc-400 mt-1">
                    {entry.changed_by_name || entry.changed_by_email || 'System'} -- {formatDate(entry.changed_at)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ──────────────────────────────────────────
// Compliance review panel
// ──────────────────────────────────────────

function ComplianceReviewPanel({ matter, onReviewed }: { matter: any; onReviewed: () => void }) {
  const user = useAuthStore((s) => s.user)
  const isAdmin = String(user?.role || '').toLowerCase() === 'admin'
  const status = matter.compliance_status || 'none'
  const [referrals, setReferrals] = useState<any[]>([])
  // Referral load failure must DISABLE "Return to Fee Earner" - the
  // list of referred claims is the evidence the return decision rests
  // on, so a silent failure cannot be allowed to unlock the button.
  const [referralsError, setReferralsError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [showReturnModal, setShowReturnModal] = useState(false)

  const loadReferrals = async () => {
    if (!isAdmin || status !== 'in_review') return
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matter.id}/compliance-referrals`)
      if (r.ok) {
        const d = await r.json()
        setReferrals(d.referrals || [])
        setReferralsError(false)
      } else {
        setReferralsError(true)
      }
    } catch {
      setReferralsError(true)
    }
  }
  useEffect(() => { loadReferrals() /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [matter.id, status])

  // No standing panel once the matter has been returned — the matter
  // status badge already conveys "Returned from Compliance", and the
  // compliance conversation lives on each claim.
  if (status === 'none' || status === 'returned') return null

  const fmt = (s: string | null) => (s ? formatDateTime(s) : '')

  const markReviewed = async (claimIndex: number) => {
    setBusy(true)
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matter.id}/sof-assessment/claims/${claimIndex}/mark-reviewed`, { method: 'POST' })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        showToast(`Could not mark reviewed: ${err.detail || r.statusText}`, 'error')
        return
      }
      await loadReferrals()
    } catch (e: any) {
      showToast(`Could not mark reviewed: ${e?.message || 'Unknown error'}`, 'error')
    } finally {
      setBusy(false)
    }
  }

  const returnToFeeEarner = async (rationale: string) => {
    setBusy(true)
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matter.id}/return-to-fee-earner`, {
        method: 'POST',
        body: JSON.stringify({ rationale }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        throw new Error(err.detail || r.statusText || 'The return failed.')
      }
      setShowReturnModal(false)
      onReviewed()
    } finally {
      setBusy(false)
    }
  }

  const allReviewed = referrals.length > 0 && referrals.every((r) => r.reviewed)
  // A matter can be returned once every per-claim referral has been
  // reviewed - or when there are none (it was sent to compliance as a
  // whole rather than claim-by-claim). If the referrals could not be
  // loaded we cannot know either way, so the return stays disabled.
  const canReturn = !referralsError && (referrals.length === 0 || allReviewed)
  const tone =
    status === 'returned' ? 'border-red-200 bg-red-50'
      : status === 'cleared' ? 'border-green-200 bg-green-50'
      : 'border-amber-200 bg-amber-50'

  return (
    <div className={`mb-6 rounded-md border px-5 py-4 ${tone}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="text-sm">
          {status === 'in_review' && (
            <>
              <div className="font-semibold text-amber-800">Under compliance review</div>
              <div className="mt-0.5 text-xs text-amber-700">
                Sent by {matter.compliance_submitted_by || 'a reviewer'}
                {matter.compliance_submitted_at ? ` on ${fmt(matter.compliance_submitted_at)}` : ''}.
              </div>
              {matter.compliance_reason && (
                <div className="mt-1.5 text-xs text-amber-800">
                  <span className="font-semibold">Reason for referral:</span>{' '}
                  <span className="italic">"{matter.compliance_reason}"</span>
                </div>
              )}
            </>
          )}
          {status === 'cleared' && (
            <>
              <div className="font-semibold text-green-800">Cleared by compliance</div>
              <div className="mt-0.5 text-xs text-green-700">
                {matter.compliance_reviewed_by || 'Compliance'}{matter.compliance_reviewed_at ? ` · ${fmt(matter.compliance_reviewed_at)}` : ''}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Compliance officer surface - per-referral review + return. */}
      {isAdmin && status === 'in_review' && (
        <div className="mt-4 border-t border-amber-200 pt-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-amber-700 mb-2">
            Referred claims - review each, then return the matter
          </div>
          {referralsError ? (
            <div className="flex items-center justify-between gap-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              <span>Could not load referrals — the matter cannot be returned until they are reviewed.</span>
              <button
                onClick={loadReferrals}
                className="flex-shrink-0 px-3 py-1 text-xs font-medium rounded border border-red-300 bg-white text-red-700 hover:bg-red-50"
              >
                Retry
              </button>
            </div>
          ) : referrals.length === 0 ? (
            <div className="text-xs text-amber-700">
              This matter was sent to compliance as a whole - there are no
              individual claim referrals to review. Add a rationale and return
              it to the fee earner below.
            </div>
          ) : (
            <ul className="space-y-2">
              {referrals.map((r) => (
                <li key={r.claim_index} className="flex items-start justify-between gap-3 rounded border border-amber-200 bg-white px-3 py-2">
                  <div className="min-w-0 text-xs">
                    <div className="font-medium text-zinc-900 capitalize">
                      {r.source_type} <span className="text-zinc-400 tabular-nums">· {formatCurrencyWhole(r.amount)}</span>
                    </div>
                    {r.reason && <div className="mt-0.5 italic text-zinc-600">"{r.reason}"</div>}
                    <div className="mt-0.5 text-zinc-400">Referred by {r.sent_by || 'unknown'}</div>
                  </div>
                  {r.reviewed ? (
                    <span className="flex-shrink-0 inline-flex items-center gap-1 text-xs font-semibold text-green-700">
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                      Reviewed
                    </span>
                  ) : (
                    <button
                      onClick={() => markReviewed(r.claim_index)}
                      disabled={busy}
                      className="flex-shrink-0 px-3 py-1 text-xs font-medium rounded border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 disabled:opacity-60"
                    >
                      Mark reviewed
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex items-center justify-end gap-3">
            {!canReturn && (
              <span className="text-xs text-amber-700">
                {referralsError
                  ? 'Referrals could not be loaded — retry above to enable return.'
                  : 'Review every referral to enable return.'}
              </span>
            )}
            <button
              onClick={() => setShowReturnModal(true)}
              disabled={busy || !canReturn}
              className={`px-3.5 py-1.5 text-xs font-semibold rounded-full transition-colors ${
                canReturn && !busy
                  ? 'bg-zinc-900 text-white hover:bg-zinc-800'
                  : 'bg-zinc-200 text-zinc-400 cursor-not-allowed'
              }`}
            >
              Return to Fee Earner
            </button>
          </div>
        </div>
      )}

      <RationaleModal
        isOpen={showReturnModal}
        title="Return matter to fee earner"
        description="Give the rationale for the return - the fee earner sees this so they know what compliance found."
        confirmLabel="Return to Fee Earner"
        onConfirm={returnToFeeEarner}
        onClose={() => setShowReturnModal(false)}
      />
    </div>
  )
}
