import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import TransactionList from '../components/TransactionReview/TransactionList'
import SoFAssessment from '../components/SoFAssessment/SoFAssessment'
import StatusUpdateModal from '../components/StatusUpdateModal'
import FundsLineage from '../components/FundsLineage/FundsLineage'
import DocumentVerificationPage from '../components/DocumentVerification/DocumentVerificationPage'
import { API_BASE_URL, authFetch } from '../lib/api'

type TabType = 'sof-assessment' | 'transactions' | 'funds-lineage' | 'verification' | 'audit-trail'

export default function MatterDetailPage() {
  const { id } = useParams()
  const [activeTab, setActiveTab] = useState<TabType>('sof-assessment')
  const [matter, setMatter] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showStatusModal, setShowStatusModal] = useState(false)

  // Fetch matter data from API
  useEffect(() => {
    const fetchMatter = async () => {
      try {
        setLoading(true)
        const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${id}`)
        if (!response.ok) {
          throw new Error('Failed to fetch matter')
        }
        const data = await response.json()
        setMatter(data)
      } catch (err) {
        console.error('Error fetching matter:', err)
        setError('Failed to load matter details. Please try again.')
      } finally {
        setLoading(false)
      }
    }

    if (id) {
      fetchMatter()
    }
  }, [id])

  const tabs = [
    { id: 'sof-assessment' as TabType, name: 'SoF Assessment', count: null },
    { id: 'transactions' as TabType, name: 'Transaction Review', count: null },
    { id: 'funds-lineage' as TabType, name: 'Funds Lineage Model', count: null },
    { id: 'verification' as TabType, name: 'Verification', count: null },
    { id: 'audit-trail' as TabType, name: 'Audit Trail', count: null },
  ]

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
              onClick={() => {
                window.open(`${API_BASE_URL}/api/v1/matters/${id}/report`, '_blank')
              }}
              className="px-4 py-2 text-sm font-medium border border-zinc-300 text-zinc-700 hover:bg-zinc-50 rounded transition-colors"
            >
              Generate Report
            </button>
            <button
              onClick={() => setShowStatusModal(true)}
              className="px-4 py-2 text-sm font-medium bg-zinc-900 text-white rounded hover:bg-zinc-800 transition-colors"
            >
              🔄 Update Status
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-zinc-200 mb-6">
        <nav className="-mb-px flex space-x-8 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium
                ${activeTab === tab.id
                  ? 'border-zinc-900 text-zinc-900'
                  : 'border-transparent text-zinc-400 hover:text-zinc-600 hover:border-zinc-200'
                }
              `}
            >
              {tab.name}
              {tab.count && (
                <span className={`ml-2 py-0.5 px-2 rounded-full text-xs ${
                  activeTab === tab.id ? 'bg-zinc-50 text-zinc-900' : 'bg-zinc-50 text-zinc-400'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="min-h-[600px]">
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
