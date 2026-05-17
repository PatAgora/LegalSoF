import { useState, useEffect } from 'react'
import { API_BASE_URL, authFetch } from '../lib/api'

interface StatusSuggestion {
  status: string
  reason: string
  auto_recommended: boolean
}

interface StatusSuggestionsData {
  current_status: string
  completion_percentage: number
  suggestions: StatusSuggestion[]
  auto_transitions_available: boolean
  auto_transition_preview: string[]
}

interface StatusUpdateModalProps {
  matterId: number
  currentStatus: string
  onClose: () => void
  onSuccess: () => void
}

export default function StatusUpdateModal({ 
  matterId, 
  currentStatus, 
  onClose, 
  onSuccess 
}: StatusUpdateModalProps) {
  const [suggestions, setSuggestions] = useState<StatusSuggestionsData | null>(null)
  const [selectedStatus, setSelectedStatus] = useState<string>('')
  const [reason, setReason] = useState<string>('')
  const [autoTransition, setAutoTransition] = useState<boolean>(false)
  const [loading, setLoading] = useState<boolean>(true)
  const [updating, setUpdating] = useState<boolean>(false)
  const [error, setError] = useState<string>('')

  useEffect(() => {
    fetchSuggestions()
  }, [matterId])

  const fetchSuggestions = async () => {
    try {
      setLoading(true)
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/status/suggestions`)
      if (!response.ok) {
        throw new Error('Failed to fetch status suggestions')
      }
      const data = await response.json()
      setSuggestions(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleUpdate = async () => {
    if (!selectedStatus) {
      setError('Please select a new status')
      return
    }

    try {
      setUpdating(true)
      setError('')

      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({
          new_status: selectedStatus,
          reason: reason || undefined,
          auto_transition: autoTransition
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to update status')
      }

      const result = await response.json()
      
      // Show success message
      alert(`✅ ${result.message}`)
      
      // Callback to refresh parent component
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setUpdating(false)
    }
  }

  const getStatusColor = (status: string) => {
    const colors: { [key: string]: string } = {
      'DRAFT': 'bg-zinc-50 text-zinc-900',
      'AWAITING_CLIENT': 'bg-zinc-100 text-zinc-900',
      'CLIENT_UPLOADING': 'bg-blue-100 text-blue-700',
      'UNDER_REVIEW': 'bg-amber-100 text-amber-700',
      'QUERIES_RAISED': 'bg-amber-100 text-amber-700',
      'APPROVED': 'bg-green-100 text-green-700',
      'REJECTED': 'bg-red-100 text-red-700',
      'COMPLETED': 'bg-zinc-100 text-zinc-900',
    }
    return colors[status] || 'bg-zinc-50 text-zinc-900'
  }

  const formatStatusLabel = (status: string) => {
    return status.replace(/_/g, ' ')
  }

  return (
    <div className="fixed inset-0 bg-zinc-900/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-md shadow-lg border border-zinc-200 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="border-b border-zinc-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <h2 className="text-section-title text-zinc-900">Update Matter Status</h2>
            <button
              onClick={onClose}
              className="text-zinc-400 hover:text-zinc-600 text-2xl"
            >
              ×
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          {loading ? (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-600"></div>
              <p className="mt-2 text-zinc-600">Loading suggestions...</p>
            </div>
          ) : suggestions ? (
            <div className="space-y-6">
              {/* Current Status */}
              <div>
                <label className="block text-sm font-medium text-zinc-600 mb-2">
                  Current Status
                </label>
                <div className="flex items-center space-x-3">
                  <span className={`px-4 py-2 rounded-full text-sm font-medium ${getStatusColor(suggestions.current_status)}`}>
                    {formatStatusLabel(suggestions.current_status)}
                  </span>
                  <span className="text-zinc-600">
                    • {suggestions.completion_percentage}% Complete
                  </span>
                </div>
              </div>

              {/* Progress Bar */}
              <div>
                <div className="w-full bg-zinc-200 rounded-full h-2">
                  <div
                    className="bg-zinc-800 h-2 rounded-full transition-all"
                    style={{ width: `${suggestions.completion_percentage}%` }}
                  />
                </div>
              </div>

              {/* Auto-Transition Alert */}
              {suggestions.auto_transitions_available && (
                <div className="bg-zinc-50 border border-zinc-200 rounded-md p-4">
                  <div className="flex items-start">
                    <span className="text-2xl mr-3">🤖</span>
                    <div className="flex-1">
                      <h3 className="font-semibold text-zinc-900 mb-1">
                        Automatic Transition Available
                      </h3>
                      <p className="text-sm text-zinc-700 mb-2">
                        The system can automatically transition this matter based on current data:
                      </p>
                      <ul className="text-sm text-zinc-700 space-y-1">
                        {suggestions.auto_transition_preview.map((preview, idx) => (
                          <li key={idx} className="flex items-start">
                            <span className="mr-2">→</span>
                            <span>{preview}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {/* Status Selection */}
              <div>
                <label className="block text-sm font-medium text-zinc-600 mb-2">
                  New Status *
                </label>
                <div className="space-y-2">
                  {suggestions.suggestions.length > 0 ? (
                    suggestions.suggestions.map((suggestion) => (
                      <div
                        key={suggestion.status}
                        onClick={() => setSelectedStatus(suggestion.status)}
                        className={`
                          border rounded-md p-4 cursor-pointer transition-all
                          ${selectedStatus === suggestion.status
                            ? 'border-zinc-500 bg-zinc-50'
                            : 'border-zinc-200 hover:border-zinc-300'
                          }
                        `}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-3">
                            <input
                              type="radio"
                              checked={selectedStatus === suggestion.status}
                              onChange={() => setSelectedStatus(suggestion.status)}
                              className="w-4 h-4 text-zinc-700"
                            />
                            <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(suggestion.status)}`}>
                              {formatStatusLabel(suggestion.status)}
                            </span>
                          </div>
                          {suggestion.auto_recommended && (
                            <span className="text-xs font-semibold text-green-700 bg-green-50 px-2 py-1 rounded">
                              ⚡ AUTO
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-zinc-600 mt-2 ml-7">
                          {suggestion.reason}
                        </p>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-4 bg-zinc-50 rounded-md">
                      <p className="text-zinc-600">
                        No status transitions available from {formatStatusLabel(suggestions.current_status)}
                      </p>
                      <p className="text-sm text-zinc-400 mt-1">
                        This is a terminal state or requires manual intervention
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Reason/Notes */}
              <div>
                <label className="block text-sm font-medium text-zinc-600 mb-2">
                  Reason / Notes (Optional)
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full px-3 py-2 border border-zinc-200 rounded-md focus:outline-none focus:ring-2 focus:ring-zinc-500"
                  rows={3}
                  placeholder="Add any notes about this status change..."
                />
              </div>

              {/* Auto-Transition Checkbox */}
              {suggestions.auto_transitions_available && (
                <div className="flex items-start space-x-3 bg-zinc-50 border border-zinc-200 rounded-md p-4">
                  <input
                    type="checkbox"
                    checked={autoTransition}
                    onChange={(e) => setAutoTransition(e.target.checked)}
                    className="mt-1 w-4 h-4 text-zinc-700 rounded"
                  />
                  <div>
                    <label className="font-medium text-zinc-900 cursor-pointer">
                      Apply automatic transitions after this update
                    </label>
                    <p className="text-sm text-zinc-600 mt-1">
                      The system will automatically apply additional status changes based on workflow rules
                    </p>
                  </div>
                </div>
              )}

              {/* Error Message */}
              {error && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4 text-red-700">
                  <strong>Error:</strong> {error}
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="border-t border-zinc-200 px-6 py-4 bg-zinc-50">
          <div className="flex justify-end space-x-3">
            <button
              onClick={onClose}
              disabled={updating}
              className="px-4 py-2 border border-zinc-200 rounded text-zinc-600 hover:bg-zinc-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleUpdate}
              disabled={updating || !selectedStatus || suggestions?.suggestions.length === 0}
              className="px-6 py-2 bg-zinc-900 text-white rounded hover:bg-zinc-900 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {updating ? 'Updating...' : 'Update Status'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
