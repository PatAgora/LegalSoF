import { Link } from 'react-router-dom'

// ---------------------------------------------------------------------------
// Dashboard Page -- Agora Consulting AI
// Provides at-a-glance oversight of Source of Funds verification pipeline.
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Page Header — serif title above a hairline rule */}
      <div className="border-b border-zinc-200 pb-6">
        <h1 className="font-serif text-3xl font-normal tracking-tight text-zinc-900">
          Dashboard
        </h1>
        <p className="mt-2 text-sm text-zinc-500">
          Source of Funds verification overview
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Matters"
          value="12"
          change="+2 this week"
          trend="up"
          href="/matters"
          indicator="total"
        />
        <StatCard
          title="Under Review"
          value="5"
          change="3 awaiting client"
          trend="neutral"
          href="/matters"
          indicator="review"
        />
        <StatCard
          title="Approved"
          value="6"
          change="+1 today"
          trend="up"
          href="/matters"
          indicator="approved"
        />
        <StatCard
          title="High Risk"
          value="2"
          change="Requires attention"
          trend="down"
          href="/matters"
          indicator="risk"
        />
      </div>

      {/* Bottom Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        <div className="bg-white rounded-md border border-zinc-200">
          <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-900">
              Recent Activity
            </h2>
            <Link
              to="/matters"
              className="text-xs font-medium text-zinc-700 hover:text-zinc-900 transition-colors"
            >
              View all
            </Link>
          </div>
          <div className="divide-y divide-brand-muted">
            <ActivityItem
              title="New matter created"
              description="Client: ABC Corp Ltd -- Business Purchase"
              time="2 hours ago"
              type="created"
            />
            <ActivityItem
              title="Documents uploaded"
              description="5 bank statements added to Matter #REF-2024-001"
              time="4 hours ago"
              type="upload"
            />
            <ActivityItem
              title="Matter approved"
              description="XYZ Holdings -- SoF assessment completed"
              time="1 day ago"
              type="approved"
            />
            <ActivityItem
              title="Risk flag raised"
              description="Matter #REF-2024-008 flagged for manual review"
              time="2 days ago"
              type="flagged"
            />
          </div>
        </div>

        {/* Pending Actions */}
        <div className="bg-white rounded-md border border-zinc-200">
          <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-900">
              Pending Actions
            </h2>
            <span className="inline-flex items-center justify-center h-5 min-w-[20px] px-1.5 rounded-full bg-zinc-900 text-white text-xs font-bold">
              3
            </span>
          </div>
          <div className="divide-y divide-brand-muted">
            <PendingAction
              title="Review Required"
              description="3 matters awaiting your review"
              priority="high"
              href="/matters"
            />
            <PendingAction
              title="Client Documents"
              description="2 clients yet to complete uploads"
              priority="medium"
              href="/matters"
            />
            <PendingAction
              title="Checks Flagged"
              description="4 automatic checks need resolution"
              priority="high"
              href="/matters"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// StatCard
// ---------------------------------------------------------------------------

type Indicator = 'total' | 'review' | 'approved' | 'risk'

function StatCard({
  title,
  value,
  change,
  trend,
  href,
  indicator,
}: {
  title: string
  value: string
  change: string
  trend: 'up' | 'down' | 'neutral'
  href: string
  indicator: Indicator
}) {
  // Left-border color per card type
  const borderColor: Record<Indicator, string> = {
    total: 'border-l-primary-500',
    review: 'border-l-accent-500',
    approved: 'border-l-status-success-500',
    risk: 'border-l-status-danger-500',
  }

  // Trend styling
  const trendStyles: Record<string, { color: string; arrow: string }> = {
    up: { color: 'text-green-700', arrow: '\u2191' },
    down: { color: 'text-red-700', arrow: '\u2193' },
    neutral: { color: 'text-zinc-400', arrow: '\u2014' },
  }
  const { color: trendColor, arrow: trendArrow } = trendStyles[trend]

  return (
    <Link
      to={href}
      className={
        'group relative block bg-white rounded-md border border-zinc-200 ' +
        'border-l-4 ' +
        borderColor[indicator] +
        ' px-6 py-5 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2'
      }
    >
      {/* Icon area */}
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
            {title}
          </p>
          <p className="mt-2 text-3xl font-bold text-zinc-900">{value}</p>
        </div>
        <StatIcon indicator={indicator} />
      </div>

      {/* Trend line */}
      <div className="mt-3 flex items-center gap-1.5">
        <span
          className={
            'inline-flex items-center justify-center h-5 w-5 rounded-full text-xs font-bold ' +
            (trend === 'up'
              ? 'bg-green-50 text-green-700'
              : trend === 'down'
                ? 'bg-red-50 text-red-700'
                : 'bg-zinc-50 text-zinc-400')
          }
        >
          {trendArrow}
        </span>
        <span className={'text-sm ' + trendColor}>{change}</span>
      </div>

      {/* Hover caret */}
      <span className="absolute right-4 top-1/2 -translate-y-1/2 text-zinc-400 opacity-0 transition-opacity group-hover:opacity-100">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
            clipRule="evenodd"
          />
        </svg>
      </span>
    </Link>
  )
}

// ---------------------------------------------------------------------------
// StatIcon -- small SVG icon per card type (no emoji)
// ---------------------------------------------------------------------------

function StatIcon({ indicator }: { indicator: Indicator }) {
  const base =
    'flex items-center justify-center h-10 w-10 rounded-lg'

  switch (indicator) {
    case 'total':
      return (
        <span className={base + ' bg-zinc-50 text-zinc-700'}>
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
            <path fillRule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd" />
          </svg>
        </span>
      )
    case 'review':
      return (
        <span className={base + ' bg-zinc-50 text-zinc-700'}>
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
          </svg>
        </span>
      )
    case 'approved':
      return (
        <span className={base + ' bg-green-50 text-green-700'}>
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
        </span>
      )
    case 'risk':
      return (
        <span className={base + ' bg-red-50 text-red-700'}>
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        </span>
      )
  }
}

// ---------------------------------------------------------------------------
// ActivityItem
// ---------------------------------------------------------------------------

type ActivityType = 'created' | 'upload' | 'approved' | 'flagged'

function ActivityItem({
  title,
  description,
  time,
  type,
}: {
  title: string
  description: string
  time: string
  type: ActivityType
}) {
  const dotColor: Record<ActivityType, string> = {
    created: 'bg-zinc-500',
    upload: 'bg-zinc-900',
    approved: 'bg-green-500',
    flagged: 'bg-red-500',
  }

  return (
    <div className="flex items-start gap-4 px-6 py-4 transition-colors hover:bg-slate-50">
      {/* Timeline dot */}
      <div className="relative mt-1.5 flex-shrink-0">
        <span
          className={
            'block h-2.5 w-2.5 rounded-full ring-2 ring-white ' +
            dotColor[type]
          }
        />
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-zinc-900">{title}</p>
        <p className="mt-0.5 text-sm text-zinc-400 truncate">{description}</p>
      </div>

      {/* Timestamp */}
      <time className="flex-shrink-0 text-xs text-zinc-400 whitespace-nowrap">
        {time}
      </time>
    </div>
  )
}

// ---------------------------------------------------------------------------
// PendingAction
// ---------------------------------------------------------------------------

function PendingAction({
  title,
  description,
  priority,
  href,
}: {
  title: string
  description: string
  priority: 'high' | 'medium' | 'low'
  href: string
}) {
  const badgeStyles: Record<string, string> = {
    high: 'bg-red-50 text-red-700 ring-1 ring-inset ring-status-danger-200',
    medium: 'bg-zinc-50 text-zinc-700 ring-1 ring-inset ring-zinc-200',
    low: 'bg-zinc-50 text-zinc-900 ring-1 ring-inset ring-zinc-200',
  }

  const priorityLabel: Record<string, string> = {
    high: 'High',
    medium: 'Medium',
    low: 'Low',
  }

  return (
    <Link
      to={href}
      className="flex items-center gap-4 px-6 py-4 transition-colors hover:bg-slate-50 group"
    >
      {/* Priority badge */}
      <span
        className={
          'inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ' +
          badgeStyles[priority]
        }
      >
        {priorityLabel[priority]}
      </span>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-zinc-900">{title}</p>
        <p className="mt-0.5 text-sm text-zinc-400">{description}</p>
      </div>

      {/* Arrow */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="h-4 w-4 text-zinc-400 flex-shrink-0 transition-colors group-hover:text-zinc-500"
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path
          fillRule="evenodd"
          d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
          clipRule="evenodd"
        />
      </svg>
    </Link>
  )
}
