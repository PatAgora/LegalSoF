import { useParams } from 'react-router-dom'
import { useState } from 'react'
import TransactionList from '../components/TransactionReview/TransactionList'
import SoFAssessment from '../components/SoFAssessment/SoFAssessment'

type TabType = 'sof-assessment' | 'transactions'

export default function MatterDetailPage() {
  const { id } = useParams()
  const [activeTab, setActiveTab] = useState<TabType>('sof-assessment')

  // Mock data
  const matter = {
    id: Number(id),
    reference_number: 'REF-2024-001',
    client_name: 'ABC Corp Ltd',
    client_entity_name: 'ABC Corp Ltd',
    transaction_type: 'Business Purchase',
    target_business_name: 'Target Business Ltd',
    target_amount: 5200000,
    target_currency: 'GBP',
    status: 'under_review',
    risk_rating: 'high',
    description: 'Acquisition of Target Business Ltd by ABC Corp Ltd - Source of Funds verification for £5.2M purchase consideration',
    created_at: '2024-01-15T10:30:00Z',
    assigned_analyst: 'John Smith',
    completion_percentage: 45,
  }

  const tabs = [
    { id: 'sof-assessment' as TabType, name: '📋 SoF Assessment', count: null },
    { id: 'transactions' as TabType, name: '🚨 Transaction Review', count: null },
  ]

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{matter.reference_number}</h1>
            <p className="text-gray-600 mt-2">{matter.client_name} - {matter.transaction_type}</p>
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

        {/* Progress Bar */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex justify-between text-sm mb-2">
            <span className="font-medium text-gray-700">Overall Progress</span>
            <span className="text-gray-500">{matter.completion_percentage}% Complete</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-primary-600 h-3 rounded-full transition-all"
              style={{ width: `${matter.completion_percentage}%` }}
            />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="-mb-px flex space-x-8 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`
                whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium
                ${activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              {tab.name}
              {tab.count && (
                <span className={`ml-2 py-0.5 px-2 rounded-full text-xs ${
                  activeTab === tab.id ? 'bg-primary-100 text-primary-600' : 'bg-gray-100 text-gray-600'
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
