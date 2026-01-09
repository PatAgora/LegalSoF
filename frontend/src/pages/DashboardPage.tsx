import { useAuthStore } from '../stores/authStore'

export default function DashboardPage() {
  const { user } = useAuthStore()

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-2">Welcome back, {user?.full_name}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Total Matters"
          value="12"
          change="+2 this week"
          trend="up"
        />
        <StatCard
          title="Under Review"
          value="5"
          change="3 awaiting client"
          trend="neutral"
        />
        <StatCard
          title="Approved"
          value="6"
          change="+1 today"
          trend="up"
        />
        <StatCard
          title="High Risk"
          value="2"
          change="Requires attention"
          trend="down"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Recent Activity
          </h2>
          <div className="space-y-4">
            <ActivityItem
              title="New matter created"
              description="Client: ABC Corp Ltd - Business Purchase"
              time="2 hours ago"
            />
            <ActivityItem
              title="Documents uploaded"
              description="5 bank statements added to Matter #REF-2024-001"
              time="4 hours ago"
            />
            <ActivityItem
              title="Matter approved"
              description="XYZ Holdings - SoF assessment completed"
              time="1 day ago"
            />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Pending Actions
          </h2>
          <div className="space-y-4">
            <PendingAction
              title="Review Required"
              description="3 matters awaiting your review"
              priority="high"
            />
            <PendingAction
              title="Client Documents"
              description="2 clients yet to complete uploads"
              priority="medium"
            />
            <PendingAction
              title="Checks Flagged"
              description="4 automatic checks need resolution"
              priority="high"
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({
  title,
  value,
  change,
  trend,
}: {
  title: string
  value: string
  change: string
  trend: 'up' | 'down' | 'neutral'
}) {
  const trendColor = {
    up: 'text-green-600',
    down: 'text-red-600',
    neutral: 'text-gray-600',
  }[trend]

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="text-sm font-medium text-gray-600 mb-2">{title}</div>
      <div className="text-3xl font-bold text-gray-900 mb-2">{value}</div>
      <div className={`text-sm ${trendColor}`}>{change}</div>
    </div>
  )
}

function ActivityItem({
  title,
  description,
  time,
}: {
  title: string
  description: string
  time: string
}) {
  return (
    <div className="border-l-4 border-primary-500 pl-4">
      <div className="text-sm font-medium text-gray-900">{title}</div>
      <div className="text-sm text-gray-600">{description}</div>
      <div className="text-xs text-gray-500 mt-1">{time}</div>
    </div>
  )
}

function PendingAction({
  title,
  description,
  priority,
}: {
  title: string
  description: string
  priority: 'high' | 'medium' | 'low'
}) {
  const priorityColor = {
    high: 'bg-red-100 text-red-800',
    medium: 'bg-yellow-100 text-yellow-800',
    low: 'bg-green-100 text-green-800',
  }[priority]

  return (
    <div className="flex items-start space-x-3">
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${priorityColor}`}>
        {priority}
      </span>
      <div className="flex-1">
        <div className="text-sm font-medium text-gray-900">{title}</div>
        <div className="text-sm text-gray-600">{description}</div>
      </div>
    </div>
  )
}
