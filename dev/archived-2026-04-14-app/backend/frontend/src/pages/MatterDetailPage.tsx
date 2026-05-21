import { useParams, useSearchParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import TransactionList from '../components/TransactionReview/TransactionList'
import SoFAssessment from '../components/SoFAssessment/SoFAssessment'
import StatusUpdateModal from '../components/StatusUpdateModal'
import FundsLineage from '../components/FundsLineage/FundsLineage'
import DocumentVerificationPage from '../components/DocumentVerification/DocumentVerificationPage'
import { API_BASE_URL, authFetch } from '../lib/api'
import { useCurrentMatter } from '../stores/currentMatterStore'

type TabType = 'risk-cdd' | 'sof-assessment' | 'transactions' | 'funds-lineage' | 'verification' | 'audit-trail'

const VALID_TABS: TabType[] = [
  'risk-cdd', 'sof-assessment', 'transactions', 'funds-lineage', 'verification', 'audit-trail',
]

export default function MatterDetailPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const tabParam = searchParams.get('tab') as TabType | null
  const activeTab: TabType = (tabParam && VALID_TABS.includes(tabParam)) ? tabParam : 'sof-assessment'

  const [matter, setMatter] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showStatusModal, setShowStatusModal] = useState(false)

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
      console.error('Error fetching matter:', err)
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
            onClick={() => window.location.reload()}
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
      {/* Header — serif title above hairline rule */}
      <div className="mb-8 border-b border-zinc-200 pb-6">
        <div className="flex justify-between items-end">
          <div>
            <h1 className="font-serif text-3xl font-normal tracking-tight text-zinc-900">{matter.reference_number}</h1>
            <p className="mt-2 text-sm text-zinc-500">
              {matter.client_name} — {matter.transaction_type?.replace(/_/g, ' ') || 'Transaction'}
            </p>
          </div>
          <div className="flex space-x-3">
            <button
              onClick={async () => {
                // window.open() launches a fresh tab with no auth headers,
                // so the server (require_analyst) returned 401. Fetch
                // through authFetch instead and trigger a browser download.
                try {
                  const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${id}/report`)
                  if (!r.ok) {
                    alert(`Report failed (HTTP ${r.status}). Check you're still logged in.`)
                    return
                  }
                  const blob = await r.blob()
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  // Try to preserve any filename the server suggested
                  // via Content-Disposition; otherwise fall back to a
                  // matter-scoped name.
                  const cd = r.headers.get('Content-Disposition') || ''
                  const m = cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i)
                  a.download = m ? decodeURIComponent(m[1]) : `matter-${id}-report.docx`
                  document.body.appendChild(a)
                  a.click()
                  a.remove()
                  URL.revokeObjectURL(url)
                } catch (err: any) {
                  alert(`Report failed: ${err.message || 'Unknown error'}`)
                }
              }}
              className="px-4 py-2 text-sm font-medium border border-zinc-300 text-zinc-700 hover:bg-zinc-50 rounded transition-colors"
            >
              Generate Report
            </button>
            <SendToComplianceButton
              matterId={matter.id}
              submittedAt={matter.compliance_submitted_at}
              submittedBy={matter.compliance_submitted_by}
              onSent={() => refreshMatter()}
            />
            <button
              onClick={() => setShowStatusModal(true)}
              className="px-4 py-2 text-sm font-medium bg-zinc-900 text-white rounded hover:bg-zinc-800 transition-colors"
            >
              Update Status
            </button>
          </div>
        </div>
      </div>

      {/* Tab Content — sidebar drives `?tab=`; no in-page tab bar. */}
      <div className="min-h-[600px]">
        {activeTab === 'risk-cdd' && <RiskAssessmentTab matter={matter} onSaved={() => refreshMatter()} />}
        {activeTab === 'sof-assessment' && <SoFAssessment matterId={matter.id} />}
        {activeTab === 'transactions' && <TransactionReviewTab matterId={matter.id} />}
        {activeTab === 'funds-lineage' && <FundsLineageTab matterId={matter.id} />}
        {activeTab === 'verification' && <DocumentVerificationPage matterId={matter.id} />}
        {activeTab === 'audit-trail' && <AuditTrailTab matterId={matter.id} />}
      </div>

      {/* Status Update Modal */}
      {showStatusModal && (
        <StatusUpdateModal
          matterId={matter.id}
          currentStatus={matter.status}
          onClose={() => setShowStatusModal(false)}
          onSuccess={() => {
            // Refresh matter data after status update
            if (id) {
              authFetch(`${API_BASE_URL}/api/v1/matters/${id}`)
                .then(res => res.json())
                .then(data => setMatter(data))
                .catch(err => console.error('Error refreshing matter:', err))
            }
          }}
        />
      )}
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
          console.log('🔗 Funds Lineage: Fetched', txnData.length, 'transactions from API')
          if (txnData.length > 0) {
            console.log('🔗 Funds Lineage: First API transaction:', txnData[0])
            console.log('🔗 Funds Lineage: account_id:', txnData[0].account_id)
            console.log('🔗 Funds Lineage: bank_name:', txnData[0].bank_name)
            console.log('🔗 Funds Lineage: account_type:', txnData[0].account_type)
          }
        }
        
        // Fetch SoF assessment to check for savings claims
        let claims: any[] = []
        let isSavingsClaim = false
        
        // Try results endpoint first
        const sofResponse = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/results`)
        
        if (sofResponse.ok) {
          const sofData = await sofResponse.json()
          console.log('🔗 Funds Lineage: SoF results data:', sofData)
          
          // Data is nested inside 'assessment' object
          const assessment = sofData.assessment || sofData
          console.log('🔗 Funds Lineage: Assessment object:', assessment)
          
          claims = assessment.claims || sofData.claims || []
          console.log('🔗 Funds Lineage: Claims array:', claims)
          
          // Check if any claim is savings-related
          if (claims.length > 0) {
            isSavingsClaim = claims.some((claim: any) => {
              const sourceType = (claim.source_type || '').toLowerCase()
              console.log('🔗 Funds Lineage: Checking claim source_type:', sourceType)
              return sourceType.includes('saving') || sourceType.includes('accumul')
            })
          }
          
          // Also check evidence for savings claims
          const evidence = assessment.evidence || sofData.evidence || []
          console.log('🔗 Funds Lineage: Evidence array:', evidence)
          
          if (!isSavingsClaim && evidence.length > 0) {
            for (const ev of evidence) {
              const claimSource = (ev.claim_source || '').toLowerCase()
              console.log('🔗 Funds Lineage: Checking evidence claim_source:', claimSource)
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
                console.log('🔗 Funds Lineage: Found savings in questionnaire answer:', key)
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
            console.log('🔗 Funds Lineage: SoF status data:', statusData)
            
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
                console.log('🔗 Funds Lineage: Found savings keyword in status data')
              }
            }
          }
        }
        
        console.log('🔗 Funds Lineage: FINAL isSavingsClaim =', isSavingsClaim, 'claims =', claims)
        
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
          
          // Debug log first few transactions
          if (idx < 3) {
            console.log(`🔗 DEBUG txn[${idx}]:`, {
              raw_account_id: t.account_id,
              raw_customer_id: t.customer_id,
              raw_bank_name: t.bank_name,
              raw_account_type: t.account_type,
              computed_accountId: accountId,
              computed_accountDisplay: accountDisplay
            })
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
        
        // Debug: Log transformed transactions
        console.log('🔗 Funds Lineage: Transformed transactions:', formattedTransactions.length)
        if (formattedTransactions.length > 0) {
          console.log('🔗 Funds Lineage: First transformed transaction:', formattedTransactions[0])
          // Show unique accounts
          const accounts = new Set(formattedTransactions.map((t: any) => t.account))
          console.log('🔗 Funds Lineage: Unique accounts after transform:', Array.from(accounts))
        }
        
        setSofClaims(claims)
        setHasSavingsClaim(isSavingsClaim)
        
      } catch (err) {
        console.error('🔗 Funds Lineage: Error fetching data:', err)
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
                      <li key={idx}>• {claim.source_type}: £{(claim.expected_amount || 0).toLocaleString()}</li>
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
        console.error('Error fetching audit data:', err)
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
      case 'APPROVED':
      case 'COMPLETED':
        return 'bg-green-100 text-green-700 border-green-200'
      case 'REJECTED':
        return 'bg-red-100 text-red-700 border-red-200'
      case 'UNDER_REVIEW':
        return 'bg-blue-100 text-blue-700 border-blue-200'
      case 'QUERIES_RAISED':
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
// Send to Compliance button
// ──────────────────────────────────────────

function SendToComplianceButton({
  matterId, submittedAt, submittedBy, onSent,
}: {
  matterId: number
  submittedAt?: string | null
  submittedBy?: string | null
  onSent: () => void
}) {
  const [sending, setSending] = useState(false)

  if (submittedAt) {
    const d = new Date(submittedAt)
    const when = isNaN(d.getTime())
      ? ''
      : d.toLocaleString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    return (
      <span
        className="px-4 py-2 text-sm font-medium border border-green-200 bg-green-50 text-green-700 rounded inline-flex items-center gap-1.5"
        title={`Sent to compliance${submittedBy ? ` by ${submittedBy}` : ''}${when ? ` on ${when}` : ''}`}
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Sent to Compliance
      </span>
    )
  }

  const send = async () => {
    if (!confirm('Send this matter and its file to the compliance team for review?')) return
    setSending(true)
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/send-to-compliance`, {
        method: 'POST',
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        alert(`Could not send: ${err.detail || r.statusText}`)
        return
      }
      onSent()
    } catch (e: any) {
      alert(`Could not send: ${e?.message || 'Unknown error'}`)
    } finally {
      setSending(false)
    }
  }

  return (
    <button
      onClick={send}
      disabled={sending}
      className="px-4 py-2 text-sm font-medium border border-zinc-300 text-zinc-700 hover:bg-zinc-50 rounded transition-colors disabled:opacity-60"
    >
      {sending ? 'Sending…' : 'Send to Compliance'}
    </button>
  )
}

// ──────────────────────────────────────────
// Risk & CDD tab — matter risk assessment
// ──────────────────────────────────────────

// MLR 2017 Reg 18 / LSAG §4.4 higher-risk indicator categories.
const RISK_FACTOR_CATEGORIES: { key: string; label: string; factors: string[] }[] = [
  { key: 'client', label: 'Client', factors: [
    'Politically Exposed Person (PEP), family member or close associate',
    'Client unwilling or slow to provide identification',
    'Complex or opaque ownership / control structure',
    'Cash-intensive business',
    'Unexplained use of intermediaries',
    'Adverse media or sanctions exposure',
  ]},
  { key: 'geographic', label: 'Geographic', factors: [
    'High-risk third country (HM Treasury / FATF list)',
    'Jurisdiction with weak AML/CTF controls or significant corruption',
    'Active conflict zone',
    'Sanctioned territory',
  ]},
  { key: 'service', label: 'Service / Product', factors: [
    'Conveyancing (residential or commercial)',
    'Company or trust formation',
    'Tax advice',
    'Large or unusual movements through client account',
    'Pooled-funds arrangement',
    'Use of escrow',
  ]},
  { key: 'transaction', label: 'Transaction', factors: [
    'Unusually high value',
    'Cash or third-party funding',
    'Rapid movement of funds',
    'Pre-payment later refunded',
    'Unexplained change in instructions',
    'Unusual urgency with no business rationale',
  ]},
  { key: 'delivery_channel', label: 'Delivery Channel', factors: [
    'Non-face-to-face onboarding',
    'Use of agents or introducers',
    'Reliance on third-party verification',
    'Client introduced by a party unknown to the firm',
  ]},
]

function RiskAssessmentTab({ matter, onSaved }: { matter: any; onSaved: () => void }) {
  const [rating, setRating] = useState<string>((matter.risk_rating || 'medium').toLowerCase())
  const [factors, setFactors] = useState<Record<string, string[]>>(() => {
    const f = matter.risk_factors || {}
    const out: Record<string, string[]> = {}
    for (const c of RISK_FACTOR_CATEGORIES) out[c.key] = Array.isArray(f[c.key]) ? f[c.key] : []
    return out
  })
  const [notes, setNotes] = useState<string>(matter.risk_notes || '')
  const [saving, setSaving] = useState(false)
  const [savedNote, setSavedNote] = useState<string | null>(null)

  const toggleFactor = (catKey: string, factor: string) => {
    setFactors((prev) => {
      const cur = prev[catKey] || []
      const next = cur.includes(factor) ? cur.filter((x) => x !== factor) : [...cur, factor]
      return { ...prev, [catKey]: next }
    })
  }

  const totalSelected = Object.values(factors).reduce((n, arr) => n + arr.length, 0)

  const save = async () => {
    setSaving(true)
    setSavedNote(null)
    try {
      const r = await authFetch(`${API_BASE_URL}/api/v1/matters/${matter.id}/risk-assessment`, {
        method: 'PUT',
        body: JSON.stringify({
          risk_rating: rating,
          risk_factors: factors,
          risk_notes: notes.trim() || null,
        }),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        alert(`Could not save: ${err.detail || r.statusText}`)
        return
      }
      setSavedNote('Risk assessment saved.')
      setTimeout(() => setSavedNote(null), 4000)
      onSaved()
    } catch (e: any) {
      alert(`Could not save: ${e?.message || 'Unknown error'}`)
    } finally {
      setSaving(false)
    }
  }

  const ratingStyle: Record<string, string> = {
    low: 'border-green-300 bg-green-50 text-green-700',
    medium: 'border-amber-300 bg-amber-50 text-amber-700',
    high: 'border-red-300 bg-red-50 text-red-700',
    critical: 'border-red-400 bg-red-100 text-red-800',
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header + save */}
      <div className="flex items-start justify-between gap-6">
        <div>
          <h2 className="font-serif text-2xl text-zinc-900">Matter Risk Assessment &amp; CDD</h2>
          <p className="mt-1 text-sm text-zinc-500 max-w-2xl">
            The documented matter-level risk assessment (MLR 2017 Reg 18 / LSAG §4.3–4.4).
            The rating set here drives the per-risk-tier rule configuration applied to every
            assessment for this matter.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          <button
            onClick={save}
            disabled={saving}
            className={`px-4 py-2 text-sm font-medium rounded transition-colors whitespace-nowrap ${
              saving ? 'bg-zinc-100 text-zinc-400' : 'bg-zinc-900 text-white hover:bg-zinc-800'
            }`}
          >
            {saving ? 'Saving…' : 'Save risk assessment'}
          </button>
          {savedNote && <span className="text-xs text-green-700">{savedNote}</span>}
        </div>
      </div>

      {/* Overall rating */}
      <section className="bg-white border border-zinc-200 rounded-md p-6">
        <h3 className="text-sm font-bold text-zinc-900 mb-1">Overall risk rating</h3>
        <p className="text-xs text-zinc-500 mb-3">
          Critical-rated matters use the High-tier rule settings.
        </p>
        <div className="flex gap-2">
          {['low', 'medium', 'high', 'critical'].map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRating(r)}
              className={`px-4 py-2 text-sm font-semibold rounded border capitalize transition-colors ${
                rating === r ? ratingStyle[r] : 'border-zinc-200 bg-white text-zinc-500 hover:bg-zinc-50'
              }`}
            >
              {r}
            </button>
          ))}
        </div>
        {matter.risk_assessed_at && (
          <p className="mt-3 text-xs text-zinc-400">
            Last assessed by {matter.risk_assessed_by || 'unknown'} on{' '}
            {formatDate(matter.risk_assessed_at)}.
          </p>
        )}
      </section>

      {/* Risk factors */}
      <section className="bg-white border border-zinc-200 rounded-md p-6">
        <div className="flex items-baseline justify-between">
          <h3 className="text-sm font-bold text-zinc-900">Higher-risk indicators</h3>
          <span className="text-xs text-zinc-400">{totalSelected} selected</span>
        </div>
        <p className="text-xs text-zinc-500 mt-1 mb-4">
          Tick every indicator that applies. These document the basis for the rating above.
        </p>
        <div className="space-y-5">
          {RISK_FACTOR_CATEGORIES.map((cat) => (
            <div key={cat.key}>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 mb-2">
                {cat.label}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-1.5">
                {cat.factors.map((factor) => {
                  const checked = (factors[cat.key] || []).includes(factor)
                  return (
                    <label key={factor} className="flex items-start gap-2 cursor-pointer text-sm text-zinc-700">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleFactor(cat.key, factor)}
                        className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-zinc-900 focus:ring-zinc-500"
                      />
                      <span className="leading-snug">{factor}</span>
                    </label>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Risk reasoning */}
      <section className="bg-white border border-zinc-200 rounded-md p-6">
        <h3 className="text-sm font-bold text-zinc-900 mb-1">Risk reasoning</h3>
        <p className="text-xs text-zinc-500 mb-3">
          Record why this rating was chosen, in a way another reviewer could follow.
        </p>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={4}
          placeholder="e.g. Standard residential conveyancing, UK-resident client met in person, no PEP or adverse-media match, funds from a domestic property sale — assessed Medium."
          className="w-full px-3 py-2 text-sm border border-zinc-200 rounded focus:outline-none focus:ring-2 focus:ring-zinc-300"
        />
      </section>
    </div>
  )
}
