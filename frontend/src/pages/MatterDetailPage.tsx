import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import TransactionList from '../components/TransactionReview/TransactionList'
import SoFAssessment from '../components/SoFAssessment/SoFAssessment'

type TabType = 'sof-assessment' | 'transactions'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

export default function MatterDetailPage() {
  const { id } = useParams()
  const [activeTab, setActiveTab] = useState<TabType>('sof-assessment')
  const [matter, setMatter] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch matter data from API
  useEffect(() => {
    const fetchMatter = async () => {
      try {
        setLoading(true)
        const response = await fetch(`${API_BASE_URL}/api/v1/matters/${id}`)
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
    { id: 'sof-assessment' as TabType, name: '📋 SoF Assessment', count: null },
    { id: 'transactions' as TabType, name: '🚨 Transaction Review', count: null },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
          <p className="mt-4 text-gray-600">Loading matter details...</p>
        </div>
      </div>
    )
  }

  if (error || !matter) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-red-600 text-lg">{error || 'Matter not found'}</p>
          <button 
            onClick={() => window.location.reload()}
            className="mt-4 bg-primary-600 text-white px-4 py-2 rounded-lg"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{matter.reference_number}</h1>
            <p className="text-gray-600 mt-2">
              {matter.client_name} - {matter.transaction_type?.replace(/_/g, ' ') || 'Transaction'}
            </p>
          </div>
          <div className="flex space-x-3">
            <button 
              onClick={() => {
                window.open(`${API_BASE_URL}/api/v1/matters/${id}/report`, '_blank')
              }}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              📊 Generate Report
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
            <span className="text-gray-500">{matter.completion_percentage || 0}% Complete</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-primary-600 h-3 rounded-full transition-all"
              style={{ width: `${matter.completion_percentage || 0}%` }}
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
