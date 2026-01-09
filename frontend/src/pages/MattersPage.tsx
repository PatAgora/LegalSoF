import { useState } from 'react'
import { Link } from 'react-router-dom'

export default function MattersPage() {
  const [searchTerm, setSearchTerm] = useState('')

  // Mock data - in real app, this would come from API
  const matters = [
    {
      id: 1,
      reference_number: 'REF-2024-001',
      client_name: 'ABC Corp Ltd',
      target_amount: 1500000,
      target_currency: 'GBP',
      status: 'under_review',
      risk_rating: 'medium',
      created_at: '2024-01-15',
    },
    {
      id: 2,
      reference_number: 'REF-2024-002',
      client_name: 'XYZ Holdings',
      target_amount: 2500000,
      target_currency: 'GBP',
      status: 'approved',
      risk_rating: 'low',
      created_at: '2024-01-10',
    },
    {
      id: 3,
      reference_number: 'REF-2024-003',
      client_name: 'Smith Industries',
      target_amount: 500000,
      target_currency: 'GBP',
      status: 'awaiting_client',
      risk_rating: 'high',
      created_at: '2024-01-18',
    },
  ]

  const getStatusBadge = (status: string) => {
    const styles = {
      draft: 'bg-gray-100 text-gray-800',
      awaiting_client: 'bg-yellow-100 text-yellow-800',
      client_uploading: 'bg-blue-100 text-blue-800',
      under_review: 'bg-purple-100 text-purple-800',
      queries_raised: 'bg-orange-100 text-orange-800',
      approved: 'bg-green-100 text-green-800',
      rejected: 'bg-red-100 text-red-800',
      completed: 'bg-gray-100 text-gray-800',
    }[status] || 'bg-gray-100 text-gray-800'

    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${styles}`}>
        {status.replace(/_/g, ' ').toUpperCase()}
      </span>
    )
  }

  const getRiskBadge = (risk: string) => {
    const styles = {
      low: 'bg-green-100 text-green-800',
      medium: 'bg-yellow-100 text-yellow-800',
      high: 'bg-red-100 text-red-800',
      critical: 'bg-red-200 text-red-900',
    }[risk] || 'bg-gray-100 text-gray-800'

    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${styles}`}>
        {risk.toUpperCase()}
      </span>
    )
  }

  return (
    <div>
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Matters</h1>
          <p className="text-gray-600 mt-2">Manage and review SoF matters</p>
        </div>
        <button className="bg-primary-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2">
          Create New Matter
        </button>
      </div>

      {/* Filters and Search */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <input
            type="text"
            placeholder="Search by client name or reference..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
          <select className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent">
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="awaiting_client">Awaiting Client</option>
            <option value="under_review">Under Review</option>
            <option value="approved">Approved</option>
          </select>
          <select className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent">
            <option value="">All Risk Levels</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      </div>

      {/* Matters Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Reference
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Client Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Amount
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Risk
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Created
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {matters.map((matter) => (
              <tr key={matter.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <Link
                    to={`/matters/${matter.id}`}
                    className="text-sm font-medium text-primary-600 hover:text-primary-900"
                  >
                    {matter.reference_number}
                  </Link>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm font-medium text-gray-900">{matter.client_name}</div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900">
                    £{matter.target_amount.toLocaleString()}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {getStatusBadge(matter.status)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {getRiskBadge(matter.risk_rating)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {new Date(matter.created_at).toLocaleDateString()}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <Link
                    to={`/matters/${matter.id}`}
                    className="text-primary-600 hover:text-primary-900 mr-4"
                  >
                    View
                  </Link>
                  <button className="text-gray-600 hover:text-gray-900">
                    More
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
