import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { API_BASE_URL, authFetch } from '../lib/api'
import { Card, StatusChip, Spinner, Alert } from '../components/ui'
import MatterStatusBadge, { MATTER_STATUSES } from '../components/ui/MatterStatusBadge'

// ---------------------------------------------------------------------------
// Dashboard — live rollup of the case load. Single round-trip to
// /api/v1/analytics/dashboard-summary.
// ---------------------------------------------------------------------------

interface FlagRow {
  code: string
  severity: string
  count: number
  label: string
}

interface RecentMatter {
  id: number
  reference_number: string | null
  client_name: string | null
  status: string | null
  risk_rating: string | null
  created_at: string | null
}

interface DashboardSummary {
  total_matters: number
  matters_by_status: Record<string, number>
  matters_by_risk: Record<string, number>
  total_documents_verified: number
  documents_by_verdict: Record<string, number>
  matters_with_blocking_issues: number
  top_flag_codes: FlagRow[]
  recent_matters: RecentMatter[]
}

// Shade for each status segment in the stacked bar — matches the dot
// colours in MatterStatusBadge so the bar reads the same as the badges.
const STATUS_BAR_COLOUR: Record<string, string> = {
  'Draft':                    'bg-zinc-300',
  'Under Review':             'bg-amber-400',
  'Sent to Compliance':       'bg-blue-500',
  'Returned from Compliance': 'bg-red-500',
  'Verified':                 'bg-green-500',
}

const SEVERITY_BAR_COLOUR: Record<string, string> = {
  critical: 'bg-red-500',
  high:     'bg-amber-500',
  medium:   'bg-zinc-400',
  low:      'bg-zinc-300',
  info:     'bg-blue-400',
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        setLoading(true)
        const r = await authFetch(`${API_BASE_URL}/api/v1/analytics/dashboard-summary`)
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const payload = await r.json()
        if (!cancelled) setData(payload)
      } catch (e: any) {
        if (!cancelled) setError(e.message || 'Failed to load dashboard')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="space-y-8">
        <PageHeader />
        <div className="flex items-center justify-center py-20 text-zinc-400">
          <Spinner size="md" />
          <span className="ml-3 text-sm">Loading…</span>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="space-y-8">
        <PageHeader />
        <Alert variant="error" title="Could not load dashboard">
          {error ?? 'Unknown error.'}
        </Alert>
      </div>
    )
  }

  const activeReviews =
    (data.matters_by_status['Under Review'] || 0) +
    (data.matters_by_status['Sent to Compliance'] || 0) +
    (data.matters_by_status['Returned from Compliance'] || 0)

  return (
    <div className="space-y-10">
      <PageHeader />

      {/* Topline strip */}
      <Card>
        <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-zinc-100">
          <Stat label="Total matters" value={data.total_matters} to="/matters" />
          <Stat label="Documents verified" value={data.total_documents_verified} />
          <Stat label="Active reviews" value={activeReviews} />
          <Stat
            label="Blocked"
            value={data.matters_with_blocking_issues}
            tone={data.matters_with_blocking_issues > 0 ? 'danger' : 'normal'}
          />
        </div>
      </Card>

      {/* Matters by status */}
      <section>
        <SectionHeader
          title="Matters by status"
          caption="Live distribution across the case workflow."
        />
        <Card>
          <div className="px-6 py-5">
            <StatusBar status={data.matters_by_status} total={data.total_matters} />
            <StatusLegend status={data.matters_by_status} total={data.total_matters} />
          </div>
        </Card>
      </section>

      {/* Top issues — root cause analysis */}
      <section>
        <SectionHeader
          title="Top verification issues"
          caption="The most common reasons documents are being flagged. Useful for spotting forgery patterns and weak documentation areas."
        />
        <Card>
          {data.top_flag_codes.length === 0 ? (
            <div className="px-6 py-8 text-center text-sm text-zinc-400">
              No flagged documents yet.
            </div>
          ) : (
            <ul className="divide-y divide-zinc-100">
              {data.top_flag_codes.map((row) => {
                const maxCount = Math.max(...data.top_flag_codes.map((r) => r.count))
                const widthPct = Math.max(8, Math.round((row.count / maxCount) * 100))
                return (
                  <li key={row.code} className="px-6 py-3 flex items-center gap-4">
                    <div className="w-28 shrink-0">
                      <StatusChip severity={row.severity as any} label={row.severity.toUpperCase()} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-zinc-900 truncate">{row.label}</div>
                      <div className="mt-1.5 h-1 bg-zinc-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${SEVERITY_BAR_COLOUR[row.severity] || 'bg-zinc-400'}`}
                          style={{ width: `${widthPct}%` }}
                        />
                      </div>
                    </div>
                    <div className="w-16 text-right text-sm font-medium text-zinc-700 tabular-nums">
                      {row.count}
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </Card>
      </section>

      {/* Documents by verdict — small inline strip */}
      <section>
        <SectionHeader
          title="Document verdicts"
          caption="Authenticity outcomes across every document verified by the pipeline."
        />
        <Card>
          <div className="grid grid-cols-3 divide-x divide-zinc-100">
            <Stat
              label="Verified"
              value={data.documents_by_verdict.Verified || 0}
              tone="success"
            />
            <Stat
              label="Suspicious"
              value={data.documents_by_verdict.Suspicious || 0}
              tone="warning"
            />
            <Stat
              label="Likely tampered"
              value={data.documents_by_verdict.LikelyTampered || 0}
              tone="danger"
            />
          </div>
        </Card>
      </section>

      {/* Recent matters */}
      <section>
        <SectionHeader
          title="Recent matters"
          caption="Latest cases created across the platform."
        />
        <Card>
          {data.recent_matters.length === 0 ? (
            <div className="px-6 py-8 text-center text-sm text-zinc-400">
              No matters yet. Create one to get started.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-white border-b border-zinc-100">
                <tr>
                  <th className="text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400 px-6 py-3">Reference</th>
                  <th className="text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400 px-6 py-3">Client</th>
                  <th className="text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400 px-6 py-3">Status</th>
                  <th className="text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400 px-6 py-3">Risk</th>
                  <th className="text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400 px-6 py-3">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {data.recent_matters.map((m) => (
                  <tr key={m.id} className="hover:bg-zinc-50/80 transition-colors">
                    <td className="px-6 py-3">
                      <Link
                        to={`/matters/${m.id}`}
                        className="text-zinc-900 font-medium hover:underline underline-offset-2"
                      >
                        {m.reference_number || `#${m.id}`}
                      </Link>
                    </td>
                    <td className="px-6 py-3 text-zinc-700">{m.client_name || '—'}</td>
                    <td className="px-6 py-3">
                      <MatterStatusBadge status={m.status} />
                    </td>
                    <td className="px-6 py-3 text-zinc-700">{m.risk_rating || '—'}</td>
                    <td className="px-6 py-3 text-zinc-500 tabular-nums">
                      {m.created_at ? new Date(m.created_at).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Local presentational pieces
// ---------------------------------------------------------------------------

function PageHeader() {
  return (
    <div className="border-b border-zinc-200 pb-6">
      <h1 className="font-serif text-3xl font-normal tracking-tight text-zinc-900">
        Dashboard
      </h1>
      <p className="mt-2 text-sm text-zinc-500">
        Source of Funds verification overview
      </p>
    </div>
  )
}

function SectionHeader({ title, caption }: { title: string; caption?: string }) {
  return (
    <div className="mb-3">
      <h2 className="font-serif text-lg font-medium text-zinc-900">{title}</h2>
      {caption && <p className="text-xs text-zinc-500 mt-1 max-w-2xl">{caption}</p>}
    </div>
  )
}

function Stat({ label, value, to, tone = 'normal' }: {
  label: string;
  value: number;
  to?: string;
  tone?: 'normal' | 'success' | 'warning' | 'danger';
}) {
  const toneClass =
    tone === 'success' ? 'text-green-700'
    : tone === 'warning' ? 'text-amber-700'
    : tone === 'danger'  ? 'text-red-700'
    : 'text-zinc-900'

  const body = (
    <div className="px-6 py-5">
      <div className={`font-serif text-3xl font-normal tabular-nums ${toneClass}`}>{value}</div>
      <div className="mt-1 text-xs uppercase tracking-wider text-zinc-400">{label}</div>
    </div>
  )
  return to ? (
    <Link to={to} className="block hover:bg-zinc-50 transition-colors">
      {body}
    </Link>
  ) : body
}

function StatusBar({ status, total }: { status: Record<string, number>; total: number }) {
  if (total === 0) {
    return <div className="text-sm text-zinc-400 py-2">No matters yet.</div>
  }
  return (
    <div className="h-2 w-full rounded-full overflow-hidden bg-zinc-100 flex">
      {MATTER_STATUSES.map((key) => {
        const count = status[key] || 0
        if (count === 0) return null
        const widthPct = (count / total) * 100
        return (
          <div
            key={key}
            className={STATUS_BAR_COLOUR[key] || 'bg-zinc-300'}
            style={{ width: `${widthPct}%` }}
            title={`${key}: ${count}`}
          />
        )
      })}
    </div>
  )
}

function StatusLegend({ status, total }: { status: Record<string, number>; total: number }) {
  if (total === 0) return null
  return (
    <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-zinc-600">
      {MATTER_STATUSES.map((key) => (
        <div key={key} className="inline-flex items-center gap-2">
          <span className={`h-2 w-2 rounded-sm ${STATUS_BAR_COLOUR[key] || 'bg-zinc-300'}`} />
          <span>{key}</span>
          <span className="text-zinc-400 tabular-nums">{status[key] || 0}</span>
        </div>
      ))}
    </div>
  )
}
