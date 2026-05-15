import { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { API_BASE_URL, authFetch } from '../lib/api'

export default function MattersPage() {
  const navigate = useNavigate()
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [riskFilter, setRiskFilter] = useState('')
  const [matters, setMatters] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newMatter, setNewMatter] = useState({
    client_name: '',
    reference: '',
    transaction_value: '',
    risk_level: 'medium',
    description: ''
  })

  // Fetch matters from API
  useEffect(() => {
    const fetchMatters = async () => {
      try {
        setLoading(true)
        const response = await authFetch(`${API_BASE_URL}/api/v1/matters`)
        if (!response.ok) {
          throw new Error('Failed to fetch matters')
        }
        const data = await response.json()
        setMatters(data)
      } catch (err) {
        console.error('Error fetching matters:', err)
        setError('Failed to load matters. Please try again.')
      } finally {
        setLoading(false)
      }
    }

    fetchMatters()
  }, [])

  const handleCreateMatter = async () => {
    if (!newMatter.client_name || !newMatter.transaction_value) {
      alert('Please fill in client name and transaction value')
      return
    }

    setCreating(true)
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters`, {
        method: 'POST',
        body: JSON.stringify({
          client_name: newMatter.client_name,
          reference: newMatter.reference || `MAT-${new Date().getFullYear()}-${String(Math.floor(Math.random() * 900) + 100).padStart(3, '0')}`,
          transaction_value: parseFloat(newMatter.transaction_value),
          risk_level: newMatter.risk_level,
          description: newMatter.description || 'Property purchase',
          status: 'draft'
        }),
      })

      if (response.ok) {
        const created = await response.json()
        setShowCreateModal(false)
        setNewMatter({ client_name: '', reference: '', transaction_value: '', risk_level: 'medium', description: '' })
        // Navigate to the new matter
        navigate(`/matters/${created.id}`)
      } else {
        throw new Error('Failed to create matter')
      }
    } catch (err) {
      console.error('Error creating matter:', err)
      alert('Failed to create matter. Please try again.')
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
        !statusFilter || (matter.status || '').toLowerCase() === statusFilter
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

  // --- Status badge ---
  const getStatusBadge = (status: string) => {
    const s = (status || 'draft').toLowerCase()
    const config: Record<string, { bg: string; text: string; dot: string; label: string }> = {
      draft:            { bg: 'bg-brand-surface-alt border border-brand-muted',    text: 'text-brand-ink-secondary',   dot: 'bg-brand-ink-tertiary',    label: 'Draft' },
      awaiting_client:  { bg: 'bg-status-warning-50 border border-status-warning-200',   text: 'text-status-warning-700',  dot: 'bg-status-warning-500',   label: 'Awaiting Client' },
      client_uploading: { bg: 'bg-primary-50',  text: 'text-primary-700', dot: 'bg-primary-400', label: 'Client Uploading' },
      under_review:     { bg: 'bg-status-warning-50 border border-status-warning-200',   text: 'text-status-warning-700',  dot: 'bg-status-warning-500',   label: 'Under Review' },
      queries_raised:   { bg: 'bg-status-warning-100 border border-status-warning-200',  text: 'text-status-warning-700', dot: 'bg-status-warning-500',  label: 'Queries Raised' },
      approved:         { bg: 'bg-status-success-50 border border-status-success-200', text: 'text-status-success-700', dot: 'bg-status-success-500', label: 'Approved' },
      rejected:         { bg: 'bg-status-danger-50 border border-status-danger-200',     text: 'text-status-danger-700',    dot: 'bg-status-danger-500',     label: 'Rejected' },
      completed:        { bg: 'bg-brand-surface-alt border border-brand-muted',    text: 'text-brand-ink-secondary',   dot: 'bg-brand-ink-tertiary',    label: 'Completed' },
    }
    const c = config[s] || config.draft
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-badge text-xs font-semibold ${c.bg} ${c.text}`}>
        <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} aria-hidden="true" />
        {c.label}
      </span>
    )
  }

  // --- Risk badge ---
  const getRiskBadge = (risk: string) => {
    const r = (risk || 'medium').toLowerCase()
    const config: Record<string, { bg: string; text: string; dot: string; label: string }> = {
      low:      { bg: 'bg-status-success-50 border border-status-success-200', text: 'text-status-success-700', dot: 'bg-status-success-500', label: 'Low' },
      medium:   { bg: 'bg-status-warning-50 border border-status-warning-200',   text: 'text-status-warning-700',   dot: 'bg-status-warning-500',   label: 'Medium' },
      high:     { bg: 'bg-status-danger-50 border border-status-danger-200',     text: 'text-status-danger-700',     dot: 'bg-status-danger-500',     label: 'High' },
      critical: { bg: 'bg-status-danger-100 border border-status-danger-200',    text: 'text-status-danger-900',     dot: 'bg-status-danger-600',     label: 'Critical' },
    }
    const c = config[r] || config.medium
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-badge text-xs font-semibold ${c.bg} ${c.text}`}>
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
          <div className="h-12 w-12 rounded-full border-4 border-primary-100" />
          <div className="absolute top-0 left-0 h-12 w-12 rounded-full border-4 border-transparent border-t-primary-600 animate-spin" />
        </div>
        <p className="mt-5 text-sm font-medium text-brand-ink-tertiary tracking-wide">Loading matters...</p>
      </div>
    )
  }

  // --- Error state ---
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <div className="w-14 h-14 rounded-card bg-status-danger-50 flex items-center justify-center mb-4">
          <svg className="w-7 h-7 text-status-danger-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
        </div>
        <p className="text-brand-ink font-semibold text-lg mb-1">Unable to load matters</p>
        <p className="text-brand-ink-tertiary text-sm mb-6">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-colors"
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
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-primary-800 tracking-tight">Matters</h1>
          <p className="mt-1 text-sm text-brand-ink-tertiary">
            Manage source-of-funds verification matters
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-primary-700 rounded-button hover:bg-primary-800 focus:outline-none focus:ring-2 focus:ring-primary-400 focus:ring-offset-2 transition-colors"
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

      {/* ───────── Filter bar ───────── */}
      <div className="bg-white border border-brand-muted rounded-card p-4">
        <div className="flex flex-col md:flex-row gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
              <svg className="h-4 w-4 text-brand-ink-tertiary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
              </svg>
            </div>
            <input
              type="text"
              placeholder="Search by client name or reference..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="block w-full rounded-input border border-brand-muted bg-white py-2.5 pl-10 pr-4 text-sm text-brand-ink placeholder:text-brand-ink-tertiary focus:border-primary-300 focus:bg-white focus:ring-2 focus:ring-primary-100 focus:outline-none transition-colors"
            />
          </div>
          {/* Status filter */}
          <div className="relative min-w-[170px]">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="block w-full appearance-none rounded-input border border-brand-muted bg-white py-2.5 pl-4 pr-10 text-sm text-brand-ink-secondary focus:border-primary-300 focus:bg-white focus:ring-2 focus:ring-primary-100 focus:outline-none transition-colors"
            >
              <option value="">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="awaiting_client">Awaiting Client</option>
              <option value="client_uploading">Client Uploading</option>
              <option value="under_review">Under Review</option>
              <option value="queries_raised">Queries Raised</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="completed">Completed</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
              <svg className="h-4 w-4 text-brand-ink-tertiary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
              </svg>
            </div>
          </div>
          {/* Risk filter */}
          <div className="relative min-w-[160px]">
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="block w-full appearance-none rounded-input border border-brand-muted bg-white py-2.5 pl-4 pr-10 text-sm text-brand-ink-secondary focus:border-primary-300 focus:bg-white focus:ring-2 focus:ring-primary-100 focus:outline-none transition-colors"
            >
              <option value="">All Risk Levels</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
              <svg className="h-4 w-4 text-brand-ink-tertiary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
              </svg>
            </div>
          </div>
        </div>
        {/* Active filter pills */}
        {(searchTerm || statusFilter || riskFilter) && (
          <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-brand-muted">
            <span className="text-xs text-brand-ink-tertiary font-medium">Filters:</span>
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
              className="text-xs text-primary-600 hover:text-primary-800 font-medium ml-1 transition-colors"
            >
              Clear all
            </button>
          </div>
        )}
      </div>

      {/* ───────── Matters table ───────── */}
      {filteredMatters.length === 0 ? (
        <EmptyState
          hasFilters={!!(searchTerm || statusFilter || riskFilter)}
          onClearFilters={() => { setSearchTerm(''); setStatusFilter(''); setRiskFilter('') }}
          onCreateMatter={() => setShowCreateModal(true)}
        />
      ) : (
        <div className="bg-white border border-brand-muted rounded-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-brand-muted">
              <thead>
                <tr className="bg-brand-surface-alt">
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-brand-ink-tertiary uppercase tracking-wider">
                    Reference
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-brand-ink-tertiary uppercase tracking-wider">
                    Client
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-brand-ink-tertiary uppercase tracking-wider">
                    Transaction Value
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-brand-ink-tertiary uppercase tracking-wider">
                    Status
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-brand-ink-tertiary uppercase tracking-wider">
                    Risk
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-left text-xs font-semibold text-brand-ink-tertiary uppercase tracking-wider">
                    Created
                  </th>
                  <th scope="col" className="px-6 py-3.5 text-right text-xs font-semibold text-brand-ink-tertiary uppercase tracking-wider">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-muted">
                {filteredMatters.map((matter) => (
                  <tr
                    key={matter.id}
                    onClick={() => navigate(`/matters/${matter.id}`)}
                    className="group cursor-pointer hover:bg-brand-surface transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm font-semibold text-primary-700 group-hover:text-primary-900 transition-colors">
                        {matter.reference_number}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        <div className="flex-shrink-0 w-8 h-8 rounded-card bg-primary-50 flex items-center justify-center">
                          <span className="text-xs font-bold text-primary-700">
                            {(matter.client_name || '?').charAt(0).toUpperCase()}
                          </span>
                        </div>
                        <span className="text-sm font-medium text-brand-ink">{matter.client_name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm tabular-nums text-brand-ink font-medium">
                        {'\u00A3'}{(matter.target_amount ?? 0).toLocaleString('en-GB', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getStatusBadge(matter.status)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getRiskBadge(matter.risk_rating)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm text-brand-ink-tertiary">
                        {formatDate(matter.created_at)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <Link
                        to={`/matters/${matter.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center gap-1 text-sm font-medium text-primary-600 opacity-0 group-hover:opacity-100 hover:text-primary-800 transition-all"
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
          <div className="border-t border-brand-muted bg-brand-surface-alt px-6 py-3">
            <p className="text-xs text-brand-ink-tertiary">
              Showing <span className="font-semibold text-brand-ink-secondary">{filteredMatters.length}</span>{' '}
              of <span className="font-semibold text-brand-ink-secondary">{matters.length}</span> matter{matters.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
      )}

      {/* ───────── Create Matter Modal ───────── */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-brand-ink/40 transition-opacity"
            onClick={() => setShowCreateModal(false)}
          />
          {/* Modal panel */}
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="relative w-full max-w-lg bg-white rounded-card shadow-dropdown border border-brand-muted">
              {/* Header */}
              <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-brand-muted">
                <div>
                  <h2 className="text-lg font-bold text-primary-800">Create New Matter</h2>
                  <p className="text-xs text-brand-ink-tertiary mt-0.5">Fill in the details below to open a new matter</p>
                </div>
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-lg p-1.5 text-brand-ink-tertiary hover:text-brand-ink-secondary hover:bg-brand-surface-alt transition-colors"
                  aria-label="Close"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              {/* Body */}
              <div className="px-6 py-5 space-y-5">
                {/* Client Name */}
                <div>
                  <label className="block text-sm font-medium text-brand-ink-secondary mb-1.5">
                    Client Name <span className="text-status-danger-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={newMatter.client_name}
                    onChange={(e) => setNewMatter({...newMatter, client_name: e.target.value})}
                    placeholder="e.g., John Smith Ltd"
                    className="w-full rounded-input border border-brand-muted bg-white px-4 py-2.5 text-sm text-brand-ink placeholder:text-brand-ink-tertiary focus:border-primary-300 focus:bg-white focus:ring-2 focus:ring-primary-100 focus:outline-none transition-colors"
                  />
                </div>
                {/* Reference */}
                <div>
                  <label className="block text-sm font-medium text-brand-ink-secondary mb-1.5">
                    Reference <span className="text-brand-ink-tertiary font-normal">(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={newMatter.reference}
                    onChange={(e) => setNewMatter({...newMatter, reference: e.target.value})}
                    placeholder="e.g., MAT-2024-010"
                    className="w-full rounded-input border border-brand-muted bg-white px-4 py-2.5 text-sm text-brand-ink placeholder:text-brand-ink-tertiary focus:border-primary-300 focus:bg-white focus:ring-2 focus:ring-primary-100 focus:outline-none transition-colors"
                  />
                </div>
                {/* Two-column row */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Transaction Value */}
                  <div>
                    <label className="block text-sm font-medium text-brand-ink-secondary mb-1.5">
                      Transaction Value ({'\u00A3'}) <span className="text-status-danger-500">*</span>
                    </label>
                    <div className="relative">
                      <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5">
                        <span className="text-brand-ink-tertiary text-sm">{'\u00A3'}</span>
                      </div>
                      <input
                        type="number"
                        value={newMatter.transaction_value}
                        onChange={(e) => setNewMatter({...newMatter, transaction_value: e.target.value})}
                        placeholder="450,000"
                        className="w-full rounded-input border border-brand-muted bg-white pl-8 pr-4 py-2.5 text-sm text-brand-ink placeholder:text-brand-ink-tertiary focus:border-primary-300 focus:bg-white focus:ring-2 focus:ring-primary-100 focus:outline-none transition-colors"
                      />
                    </div>
                  </div>
                  {/* Risk Level */}
                  <div>
                    <label className="block text-sm font-medium text-brand-ink-secondary mb-1.5">Risk Level</label>
                    <div className="relative">
                      <select
                        value={newMatter.risk_level}
                        onChange={(e) => setNewMatter({...newMatter, risk_level: e.target.value})}
                        className="block w-full appearance-none rounded-input border border-brand-muted bg-white px-4 py-2.5 pr-10 text-sm text-brand-ink focus:border-primary-300 focus:bg-white focus:ring-2 focus:ring-primary-100 focus:outline-none transition-colors"
                      >
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                      </select>
                      <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
                        <svg className="h-4 w-4 text-brand-ink-tertiary" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-brand-ink-secondary mb-1.5">
                    Description <span className="text-brand-ink-tertiary font-normal">(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={newMatter.description}
                    onChange={(e) => setNewMatter({...newMatter, description: e.target.value})}
                    placeholder="e.g., Residential property purchase"
                    className="w-full rounded-input border border-brand-muted bg-white px-4 py-2.5 text-sm text-brand-ink placeholder:text-brand-ink-tertiary focus:border-primary-300 focus:bg-white focus:ring-2 focus:ring-primary-100 focus:outline-none transition-colors"
                  />
                </div>
              </div>
              {/* Footer */}
              <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-brand-muted bg-brand-surface-alt rounded-b-card">
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2.5 text-sm font-medium text-brand-ink-secondary bg-white border border-brand-muted rounded-button hover:bg-brand-surface-alt focus:outline-none focus:ring-2 focus:ring-primary-100 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreateMatter}
                  disabled={creating}
                  className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-primary-700 rounded-button hover:bg-primary-800 focus:outline-none focus:ring-2 focus:ring-primary-400 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
              </div>
            </div>
          </div>
        </div>
      )}
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
    primary: { value: 'text-primary-700', icon: 'text-primary-400' },
    amber:   { value: 'text-status-warning-700',   icon: 'text-status-warning-400' },
    emerald: { value: 'text-status-success-700', icon: 'text-status-success-400' },
    red:     { value: 'text-status-danger-700',     icon: 'text-status-danger-400' },
  }
  const s = styles[color]

  return (
    <div className="bg-white border border-brand-muted rounded-card p-5">
      <p className="text-xs font-semibold text-brand-ink-tertiary uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-2xl font-bold tabular-nums ${s.value}`}>{value}</p>
    </div>
  )
}

function FilterPill({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-badge bg-primary-50 border border-primary-100 px-2.5 py-0.5 text-xs font-medium text-primary-700 capitalize">
      {label}
      <button
        onClick={onRemove}
        className="ml-0.5 rounded-full p-0.5 hover:bg-primary-100 transition-colors"
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
    <div className="bg-white border border-brand-muted rounded-card">
      <div className="flex flex-col items-center justify-center py-16 px-6">
        <div className="w-16 h-16 rounded-card bg-primary-50 flex items-center justify-center mb-5">
          <svg className="w-8 h-8 text-primary-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
          </svg>
        </div>
        {hasFilters ? (
          <>
            <h3 className="text-base font-semibold text-brand-ink mb-1">No matching matters</h3>
            <p className="text-sm text-brand-ink-tertiary mb-5 text-center max-w-sm">
              No matters match your current filters. Try adjusting your search criteria.
            </p>
            <button
              onClick={onClearFilters}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-primary-700 bg-primary-50 border border-primary-100 rounded-lg hover:bg-primary-100 transition-colors"
            >
              Clear filters
            </button>
          </>
        ) : (
          <>
            <h3 className="text-base font-semibold text-brand-ink mb-1">No matters yet</h3>
            <p className="text-sm text-brand-ink-tertiary mb-5 text-center max-w-sm">
              Get started by creating your first source-of-funds verification matter.
            </p>
            <button
              onClick={onCreateMatter}
              className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white bg-primary-700 rounded-button hover:bg-primary-800 focus:outline-none focus:ring-2 focus:ring-primary-400 focus:ring-offset-2 transition-colors"
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
