import { useParams } from 'react-router-dom'

export default function MatterDetailPage() {
  const { id } = useParams()

  // Mock data
  const matter = {
    id: Number(id),
    reference_number: 'REF-2024-001',
    client_name: 'ABC Corp Ltd',
    client_entity_name: 'ABC Corp Ltd',
    transaction_type: 'Business Purchase',
    target_business_name: 'Target Business Ltd',
    target_amount: 1500000,
    target_currency: 'GBP',
    status: 'under_review',
    risk_rating: 'medium',
    description: 'Acquisition of Target Business Ltd by ABC Corp Ltd',
    created_at: '2024-01-15T10:30:00Z',
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{matter.reference_number}</h1>
            <p className="text-gray-600 mt-2">{matter.client_name}</p>
          </div>
          <div className="flex space-x-3">
            <button className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
              Generate Report
            </button>
            <button className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
              Update Status
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8">
          <button className="border-b-2 border-primary-500 py-4 px-1 text-sm font-medium text-primary-600">
            Overview
          </button>
          <button className="border-b-2 border-transparent py-4 px-1 text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300">
            Documents
          </button>
          <button className="border-b-2 border-transparent py-4 px-1 text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300">
            Funds Chain
          </button>
          <button className="border-b-2 border-transparent py-4 px-1 text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300">
            Checks
          </button>
          <button className="border-b-2 border-transparent py-4 px-1 text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300">
            Notes
          </button>
          <button className="border-b-2 border-transparent py-4 px-1 text-sm font-medium text-gray-500 hover:text-gray-700 hover:border-gray-300">
            Audit Trail
          </button>
        </nav>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Matter Details */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Matter Details</h2>
            <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <dt className="text-sm font-medium text-gray-500">Client Entity</dt>
                <dd className="mt-1 text-sm text-gray-900">{matter.client_entity_name}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Transaction Type</dt>
                <dd className="mt-1 text-sm text-gray-900">{matter.transaction_type}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Target Business</dt>
                <dd className="mt-1 text-sm text-gray-900">{matter.target_business_name}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">Target Amount</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  £{matter.target_amount.toLocaleString()} {matter.target_currency}
                </dd>
              </div>
              <div className="md:col-span-2">
                <dt className="text-sm font-medium text-gray-500">Description</dt>
                <dd className="mt-1 text-sm text-gray-900">{matter.description}</dd>
              </div>
            </dl>
          </div>

          {/* Progress Overview */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Progress Overview</h2>
            <div className="space-y-4">
              <ProgressItem
                label="Questionnaire Completion"
                percentage={75}
                status="In Progress"
              />
              <ProgressItem
                label="Documents Uploaded"
                percentage={60}
                status="5 of 8 required"
              />
              <ProgressItem
                label="Funds Chain Reconstruction"
                percentage={40}
                status="Pending documents"
              />
              <ProgressItem
                label="Checks Completed"
                percentage={80}
                status="2 flags raised"
              />
            </div>
          </div>

          {/* Recent Activity */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h2>
            <div className="space-y-4">
              <ActivityLog
                action="Document uploaded"
                details="Bank statement (Jan-Dec 2023)"
                user="Client Portal"
                time="2 hours ago"
              />
              <ActivityLog
                action="Check flagged"
                details="Amount consistency: £50k variance detected"
                user="System"
                time="3 hours ago"
              />
              <ActivityLog
                action="Status updated"
                details="Changed from 'Awaiting Client' to 'Under Review'"
                user="John Smith"
                time="1 day ago"
              />
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Status Card */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-4">Current Status</h3>
            <div className="space-y-3">
              <div>
                <span className="text-xs font-medium text-gray-500">Status</span>
                <div className="mt-1">
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-purple-100 text-purple-800">
                    Under Review
                  </span>
                </div>
              </div>
              <div>
                <span className="text-xs font-medium text-gray-500">Risk Rating</span>
                <div className="mt-1">
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800">
                    Medium Risk
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Assignment */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-4">Assignment</h3>
            <div className="space-y-3">
              <div>
                <span className="text-xs font-medium text-gray-500">Assigned Analyst</span>
                <div className="mt-1 text-sm text-gray-900">John Smith</div>
              </div>
              <div>
                <span className="text-xs font-medium text-gray-500">Created By</span>
                <div className="mt-1 text-sm text-gray-900">System Administrator</div>
              </div>
              <div>
                <span className="text-xs font-medium text-gray-500">Created Date</span>
                <div className="mt-1 text-sm text-gray-900">
                  {new Date(matter.created_at).toLocaleDateString()}
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 mb-4">Quick Actions</h3>
            <div className="space-y-2">
              <button className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg">
                Generate Portal Link
              </button>
              <button className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg">
                Request Additional Documents
              </button>
              <button className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg">
                Add Note
              </button>
              <button className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg">
                Export Report
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ProgressItem({
  label,
  percentage,
  status,
}: {
  label: string
  percentage: number
  status: string
}) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="font-medium text-gray-700">{label}</span>
        <span className="text-gray-500">{status}</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-primary-600 h-2 rounded-full"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}

function ActivityLog({
  action,
  details,
  user,
  time,
}: {
  action: string
  details: string
  user: string
  time: string
}) {
  return (
    <div className="border-l-4 border-primary-500 pl-4">
      <div className="text-sm font-medium text-gray-900">{action}</div>
      <div className="text-sm text-gray-600">{details}</div>
      <div className="text-xs text-gray-500 mt-1">
        {user} · {time}
      </div>
    </div>
  )
}
