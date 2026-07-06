import { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { API_BASE_URL, authFetch } from '../lib/api'
import { formatDate as formatFullDate, formatCurrencyWhole } from '../lib/format'
import { showToast } from '../lib/toast'
import MatterStatusBadge, { MATTER_STATUSES } from '../components/ui/MatterStatusBadge'
import Modal from '../components/ui/Modal'

type ViewTab = 'all' | 'mine' | 'overdue'

interface PickerUser {
  id: number
  full_name: string
  email: string
  role: string
}

export default function MattersPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  // Deep-linkable view (e.g. the Dashboard "Overdue matters" card links
  // to /matters?view=overdue).
  const initialView: ViewTab =
    searchParams.get('view') === 'overdue' ? 'overdue'
      : searchParams.get('view') === 'mine' ? 'mine'
      : 'all'
  const [viewTab, setViewTab] = useState<ViewTab>(initialView)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [riskFilter, setRiskFilter] = useState('')
  const [matters, setMatters] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [users, setUsers] = useState<PickerUser[]>([])
  const [newMatter, setNewMatter] = useState({
    client_name: '',
    reference: '',
    description: '',
    risk_level: 'medium',
    target_completion_date: '',
    assigned_analyst_id: '',
  })

  // Fetch (or re-fetch) matters from the API — the view tab is applied
  // server-side via query params.
  const fetchMatters = async (view: ViewTab = viewTab) => {
    try {
      setLoading(true)
      setError(null)
      const params = new URLSearchParams()
      if (view === 'mine') params.set('assigned_to_me', 'true')
      if (view === 'overdue') params.set('overdue', 'true')
      const qs = params.toString()
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters${qs ? `?${qs}` : ''}`)
      if (!response.ok) {
        throw new Error('Failed to fetch matters')
      }
      const data = await response.json()
      setMatters(data)
    } catch (err) {
      console.debug('Error fetching matters:', err)
      setError('Failed to load matters. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMatters(viewTab)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewTab])

  // Users for the "Assign to" dropdown in the create modal.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const r = await authFetch(`${API_BASE_URL}/api/v1/users`)
        if (r.ok && !cancelled) setUsers(await r.json())
      } catch {
        // Non-blocking — the dropdown simply stays empty.
      }
    })()
    return () => { cancelled = true }
  }, [])

  const handleCreateMatter = async () => {
    if (!newMatter.client_name.trim()) {
      setCreateError('Please enter a client name.')
      return
    }

    setCreating(true)
    setCreateError(null)
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters`, {
        method: 'POST',
        body: JSON.stringify({
          client_name: newMatter.client_name.trim(),
          reference: newMatter.reference.trim() || undefined,
          description: newMatter.description.trim() || undefined,
          risk_level: newMatter.risk_level,
          status: 'draft',
          target_completion_date: newMatter.target_completion_date || undefined,
          assigned_analyst_id: newMatter.assigned_analyst_id
            ? Number(newMatter.assigned_analyst_id)
            : undefined,
        }),
      })

      if (response.ok) {
        const created = await response.json()
        setShowCreateModal(false)
        setNewMatter({
          client_name: '', reference: '', description: '', risk_level: 'medium',
          target_completion_date: '', assigned_analyst_id: '',
        })
        showToast(`Matter ${created.reference_number || ''} created.`.trim(), 'success')
        // Navigate to the new matter
        navigate(`/matters/${created.id}`)
      } else {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to create matter')
      }
    } catch (err) {
      console.debug('Error creating matter:', err)
      setCreateError(
        err instanceof Error && err.message && err.message !== 'Failed to create matter'
          ? err.message
          : 'The matter could not be created. Please try again.'
      )
    } finally {
      setCreating(false)
    }
  }

  // Filtered matters
  const filteredMatters = useMemo(() => {
    return matters.filter((matter) => {
      const term = searchTerm.toLowerCase()
      const matchesSearch =
        !term ||
        (matter.client_name || '').toLowerCase().includes(term) ||
        (matter.reference_number || '').toLowerCase().includes(term)
      const matchesStatus =
        !statusFilter || (matter.status || '') === statusFilter
      const matchesRisk =
        !riskFilter || (matter.risk_rating || '').toLowerCase() === riskFilter
      return matchesSearch && matchesStatus && matchesRisk
    })
  }, [matters, searchTerm, statusFilter, riskFilter])

  // Summary counts
  const counts = useMemo(() => {
    const total = matters.length
    let underReview = 0
    let approved = 0
    let highRisk = 0
    for (const m of matters) {
      const s = (m.status || '').toLowerCase()
      const r = (m.risk_rating || '').toLowerCase()
      if (s === 'under_review' || s === 'awaiting_client' || s === 'client_uploading' || s === 'queries_raised') underReview++
      if (s === 'approved') approved++
      if (r === 'high' || r === 'critical') highRisk++
    }
    return { total, underReview, approved, highRisk }
  }, [matters])


  // --- Risk badge ---
  const getRiskBadge = (risk: string) => {
    const r = (risk || 'medium').toLowerCase()
    const config: Record<string, { bg: string; text: string; dot: string; label: string }> = {
      low:      { bg: 'bg-green-50 border border-green-200', text: 'text-green-700', dot: 'bg-green-500', label: 'Low' },
      medium:   { bg: 'bg-amber-50 border border-amber-200',   text: 'text-amber-700',   dot: 'bg-amber-500',   label: 'Medium' },
      high:     { bg: 'bg-red-50 border border-red-200',     text: 'text-red-700',     dot: 'bg-red-500',     label: 'High' },
      critical: { bg: 'bg-red-100 border border-red-200',    text: 'text-red-700',     dot: 'bg-red-600',     label: 'Critical' },
    }
    const c = config[r] || config.medium
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold ${c.bg} ${c.text}`}>
        <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} aria-hidden="true" />
        {c.label}
      </span>
    )
  }

  // --- Loading state ---
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <div className="relative">
          <div className="h-12 w-12 rounded-full border-4 border-zinc-200" />
          <div className="absolute top-0 left-0 h-12 w-12 rounded-full border-4 border-transparent border-t-primary-600 animate-spin" />
        </div>
        <p className="mt-5 text-sm font-medium text-zinc-400 tracking-wide">Loading matters...</p>
      </div>
    )
  }

  // --- Error state ---
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <div className="w-14 h-14 rounded-md bg-red-50 flex items-center justify-center mb-4">
          <svg className="w-7 h-7 text-red-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
        </div>
        <p className="text-zinc-900 font-semibold text-lg mb-1">Unable to load matters</p>
        <p className="text-zinc-400 text-sm mb-6">{error}</p>
        <button
          onClick={() => fetchMatters()}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-zinc-800 rounded-lg hover:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
          </svg>
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* ───────── Page header ───────── */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 border-b border-zinc-200 pb-6">
        <div>
          <h1 className="font-serif text-3xl font-normal text-zinc-900 tracking-tight">Matters</h1>
          <p className="mt-2 text-sm text-zinc-500">
            Manage source-of-funds verification matters
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-zinc-900 rounded hover:bg-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-500 focus:ring-offset-2 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Matter
        </button>
      </div>

      {/* ───────── Summary cards ───────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard label="Total Matters" value={counts.total} color="primary" />
        <SummaryCard label="In Progress" value={counts.underReview} color="amber" />
        <SummaryCard label="Approved" value={counts.approved} color="emerald" />
        <SummaryCard label="High Risk" value={counts.highRisk} color="red" />
      </div>

      {/* ───────── View tabs (server-side filters) ───────── */}
      <div className="flex items-center gap-1 border-b border-zinc-200" role="tablist" aria-label="Matter views">
        {([
          { key: 'all', label: 'All' },
          { key: 'mine', label: 'My matters' },
          { key: 'overdue', label: 'Overdue' },
        ] as { key: ViewTab; label: string }[]).map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={viewTab === tab.key}
            onClick={() => setViewTab(tab.key)}
            className={`px-4 py-2.5 -mb-px text-sm font-medium border-b-2 transition-colors ${
              viewTab === tab.key
                ? 'border-zinc-900 text-zinc-900'
                : 'border-transparent text-zinc-400 hover:text-zinc-600'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ───────── Filter bar ───────── */}
      <div className="bg-white border border-zinc-200 rounded-md p-4">
        <div className="flex flex-col md:flex-row gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
              <svg className="h-4 w-4 text-zinc-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
              </svg>
            </div>
            <input
              type="text"
              placeholder="Search by client name or reference..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="block w-full rounded border border-zinc-200 bg-white py-2.5 pl-10 pr-4 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-300 focus:bg-white focus:ring-2 focus:ring-zinc-200 focus:outline-none transition-colors"
            />
          </div>
          {/* Status filter */}
          <div className="relative min-w-[170px]">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="block w-full appearance-none rounded border border-zinc-200 bg-white py-2.5 pl-4 pr-10 text-sm text-zinc-600 focus:border-zinc-300 focus:bg-white focus:ring-2 focus:ring-zinc-200 focus:outline-none transition-colors"
            >
              <option value="">All Statuses</option>
              {MATTER_STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
              <svg className="h-4 w-4 text-zinc-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
              </svg>
            </div>
          </div>
          {/* Risk filter */}
          <div className="relative min-w-[160px]">
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="block w-full appearance-none rounded border border-zinc-200 bg-white py-2.5 pl-4 pr-10 text-sm text-zinc-600 focus:border-zinc-300 focus:bg-white focus:ring-2 focus:ring-zinc-200 focus:outline-none transition-colors"
            >
              <option value="">All Risk Levels</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
              <svg className="h-4 w-4 text-zinc-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
              </svg>
            </div>
          </div>
        </div>
        {/* Active filter pills */}
        {(searchTerm || statusFilter || riskFilter) && (
          <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-zinc-200">
            <span className="text-xs text-zinc-400 font-medium">Filters:</span>
            {searchTerm && (
              <FilterPill label={`"${searchTerm}"`} onRemove={() => setSearchTerm('')} />
            )}
            {statusFilter && (
              <FilterPill label={statusFilter.replace(/_/g, ' ')} onRemove={() => setStatusFilter('')} />
            )}
            {riskFilter && (
              <FilterPill label={`${riskFilter} risk`} onRemove={() => setRiskFilter('')} />
            )}
            <button
              onClick={() => { setSearchTerm(''); setStatusFilter(''); setRiskFilter('') }}
              className="text-xs text-zinc-700 hover:text-zinc-900 font-medium ml-1 transition-colors"
            >
              Clear all
            </button>
          </div>
        )}
      </div>

      {/* ───────── Matters table ───────── */}
      {filteredMatters.length === 0 ? (
        <EmptyState
          hasFilters={!!(searchTerm || statusFilter || riskFilter || viewTab !== 'all')}
          onClearFilters={() => { setSearchTerm(''); setStatusFilter(''); setRiskFilter(''); setViewTab('all') }}
          onCreateMatter={() => setShowCreateModal(true)}
        />
      ) : (
        <div className="bg-white border border-zinc-200 rounded-md overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-brand-muted">
              <thead>
                <tr className="bg-zinc-50">
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Reference
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Client
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Transaction Value
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Status
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Risk
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Assigned to
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Target date
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Days in status
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    Created
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-right text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-muted">
                {filteredMatters.map((matter) => (
                  <tr
                    key={matter.id}
                    onClick={() => navigate(`/matters/${matter.id}`)}
                    className="group cursor-pointer hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm font-semibold text-zinc-900 group-hover:text-zinc-900 transition-colors">
                        {matter.reference_number}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        <div className="flex-shrink-0 w-8 h-8 rounded-md bg-zinc-50 flex items-center justify-center">
                          <span className="text-xs font-bold text-zinc-900">
                            {(matter.client_name || '?').charAt(0).toUpperCase()}
                          </span>
                        </div>
                        <span className="text-sm font-medium text-zinc-900">{matter.client_name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm tabular-nums text-zinc-900 font-medium">
                        {formatCurrencyWhole(matter.target_amount)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <MatterStatusBadge status={matter.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getRiskBadge(matter.risk_rating)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {matter.assigned_analyst_name ? (
                        <span className="text-sm text-zinc-700">{matter.assigned_analyst_name}</span>
                      ) : (
                        <span className="text-sm text-zinc-400 italic">Unassigned</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {matter.target_completion_date ? (
                        <span className="inline-flex items-center gap-2">
                          <span className={`text-sm tabular-nums ${matter.is_overdue ? 'text-red-700 font-semibold' : 'text-zinc-700'}`}>
                            {formatFullDate(matter.target_completion_date)}
                          </span>
                          {matter.is_overdue && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-red-50 border border-red-200 text-red-700">
                              Overdue
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-sm text-zinc-400">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm tabular-nums text-zinc-700">
                        {matter.days_in_current_status ?? '-'}
                        {matter.days_in_current_status != null ? 'd' : ''}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm text-zinc-400" title={formatFullDate(matter.created_at)}>
                        {formatDate(matter.created_at)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <Link
                        to={`/matters/${matter.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center gap-1 text-sm font-medium text-zinc-700 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 hover:text-zinc-900 transition-all"
                      >
                        Open
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
                        </svg>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Table footer */}
          <div className="border-t border-zinc-200 bg-zinc-50 px-6 py-3">
            <p className="text-xs text-zinc-400">
              Showing <span className="font-semibold text-zinc-600">{filteredMatters.length}</span>{' '}
              of <span className="font-semibold text-zinc-600">{matters.length}</span> matter{matters.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
      )}

      {/* ───────── Create Matter Modal - shared Modal gives us a real
            dialog (focus trap + Escape-to-close via Headless UI). ───────── */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => { setShowCreateModal(false); setCreateError(null) }}
        title="Create New Matter"
        size="lg"
        footer={
          <>
            <button
              onClick={() => { setShowCreateModal(false); setCreateError(null) }}
              className="px-4 py-2.5 text-sm font-medium text-zinc-600 bg-white border border-zinc-200 rounded hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-zinc-200 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleCreateMatter}
              disabled={creating}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-zinc-900 rounded hover:bg-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {creating ? (
                <>
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Creating...
                </>
              ) : (
                'Create Matter'
              )}
            </button>
          </>
        }
      >
              <div className="space-y-5">
                <p className="text-xs text-zinc-400">Fill in the details below to open a new matter</p>
                {createError && (
                  <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                    {createError}
                  </div>
                )}
                {/* Client Name */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 mb-1.5">
                    Client Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={newMatter.client_name}
                    onChange={(e) => setNewMatter({...newMatter, client_name: e.target.value})}
                    placeholder="e.g., John Smith Ltd"
                    className="w-full rounded border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-300 focus:bg-white focus:ring-2 focus:ring-zinc-200 focus:outline-none transition-colors"
                  />
                </div>
                {/* Reference */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 mb-1.5">
                    Reference <span className="text-zinc-400 font-normal">(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={newMatter.reference}
                    onChange={(e) => setNewMatter({...newMatter, reference: e.target.value})}
                    placeholder="e.g., MAT-2024-010"
                    className="w-full rounded border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-300 focus:bg-white focus:ring-2 focus:ring-zinc-200 focus:outline-none transition-colors"
                  />
                </div>
                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 mb-1.5">
                    Description <span className="text-zinc-400 font-normal">(optional)</span>
                  </label>
                  <textarea
                    value={newMatter.description}
                    onChange={(e) => setNewMatter({...newMatter, description: e.target.value})}
                    placeholder="e.g., Residential property purchase"
                    rows={3}
                    className="w-full rounded border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-300 focus:bg-white focus:ring-2 focus:ring-zinc-200 focus:outline-none transition-colors"
                  />
                </div>
                {/* Initial risk rating - carried through to the matter
                    and used as the per-risk-tier rule configuration
                    until a full assessment is recorded on the Risk &
                    CDD tab. */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 mb-1.5">
                    Initial risk rating
                  </label>
                  <div className="relative">
                    <select
                      value={newMatter.risk_level}
                      onChange={(e) => setNewMatter({...newMatter, risk_level: e.target.value})}
                      className="block w-full appearance-none rounded border border-zinc-200 bg-white px-4 py-2.5 pr-10 text-sm text-zinc-900 focus:border-zinc-300 focus:bg-white focus:ring-2 focus:ring-zinc-200 focus:outline-none transition-colors"
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
                      <svg className="h-4 w-4 text-zinc-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                      </svg>
                    </div>
                  </div>
                </div>
                {/* Target completion date */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 mb-1.5">
                    Target completion date <span className="text-zinc-400 font-normal">(optional)</span>
                  </label>
                  <input
                    type="date"
                    value={newMatter.target_completion_date}
                    onChange={(e) => setNewMatter({...newMatter, target_completion_date: e.target.value})}
                    className="w-full rounded border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-900 focus:border-zinc-300 focus:bg-white focus:ring-2 focus:ring-zinc-200 focus:outline-none transition-colors"
                  />
                </div>
                {/* Assign to */}
                <div>
                  <label className="block text-sm font-medium text-zinc-600 mb-1.5">
                    Assign to <span className="text-zinc-400 font-normal">(optional)</span>
                  </label>
                  <div className="relative">
                    <select
                      value={newMatter.assigned_analyst_id}
                      onChange={(e) => setNewMatter({...newMatter, assigned_analyst_id: e.target.value})}
                      className="block w-full appearance-none rounded border border-zinc-200 bg-white px-4 py-2.5 pr-10 text-sm text-zinc-900 focus:border-zinc-300 focus:bg-white focus:ring-2 focus:ring-zinc-200 focus:outline-none transition-colors"
                    >
                      <option value="">Unassigned</option>
                      {users.map((u) => (
                        <option key={u.id} value={u.id}>{u.full_name} ({u.role})</option>
                      ))}
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
                      <svg className="h-4 w-4 text-zinc-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                      </svg>
                    </div>
                  </div>
                </div>
              </div>
      </Modal>
    </div>
  )
}

// ──────────────────────────────────────────
// Sub-components
// ──────────────────────────────────────────

function SummaryCard({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color: 'primary' | 'amber' | 'emerald' | 'red'
}) {
  const styles: Record<string, { value: string; icon: string }> = {
    primary: { value: 'text-zinc-900', icon: 'text-zinc-400' },
    amber:   { value: 'text-amber-700',   icon: 'text-amber-400' },
    emerald: { value: 'text-green-700', icon: 'text-green-400' },
    red:     { value: 'text-red-700',     icon: 'text-red-400' },
  }
  const s = styles[color]

  return (
    <div className="bg-white border border-zinc-200 rounded-md p-5">
      <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-2xl font-bold tabular-nums ${s.value}`}>{value}</p>
    </div>
  )
}

function FilterPill({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded bg-zinc-50 border border-zinc-200 px-2.5 py-0.5 text-xs font-medium text-zinc-900 capitalize">
      {label}
      <button
        onClick={onRemove}
        className="ml-0.5 rounded-full p-0.5 hover:bg-zinc-100 transition-colors"
        aria-label={`Remove filter: ${label}`}
      >
        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
        </svg>
      </button>
    </span>
  )
}

function EmptyState({
  hasFilters,
  onClearFilters,
  onCreateMatter,
}: {
  hasFilters: boolean
  onClearFilters: () => void
  onCreateMatter: () => void
}) {
  return (
    <div className="bg-white border border-zinc-200 rounded-md">
      <div className="flex flex-col items-center justify-center py-16 px-6">
        <div className="w-16 h-16 rounded-md bg-zinc-50 flex items-center justify-center mb-5">
          <svg className="w-8 h-8 text-zinc-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
          </svg>
        </div>
        {hasFilters ? (
          <>
            <h3 className="text-base font-semibold text-zinc-900 mb-1">No matching matters</h3>
            <p className="text-sm text-zinc-400 mb-5 text-center max-w-sm">
              No matters match your current filters. Try adjusting your search criteria.
            </p>
            <button
              onClick={onClearFilters}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-zinc-900 bg-zinc-50 border border-zinc-200 rounded-lg hover:bg-zinc-100 transition-colors"
            >
              Clear filters
            </button>
          </>
        ) : (
          <>
            <h3 className="text-base font-semibold text-zinc-900 mb-1">No matters yet</h3>
            <p className="text-sm text-zinc-400 mb-5 text-center max-w-sm">
              Get started by creating your first source-of-funds verification matter.
            </p>
            <button
              onClick={onCreateMatter}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-zinc-900 rounded hover:bg-zinc-900 focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              Create First Matter
            </button>
          </>
        )}
      </div>
    </div>
  )
}

// ──────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────

function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '-'
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  })
}
