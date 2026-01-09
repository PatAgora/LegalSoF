import { useParams } from 'react-router-dom'
import { useState } from 'react'

type TabType = 'overview' | 'documents' | 'funds-chain' | 'checks' | 'questionnaire' | 'notes' | 'audit'

export default function MatterDetailPage() {
  const { id } = useParams()
  const [activeTab, setActiveTab] = useState<TabType>('overview')

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
    { id: 'overview' as TabType, name: 'Overview', count: null },
    { id: 'questionnaire' as TabType, name: 'Questionnaire', count: '3/8' },
    { id: 'documents' as TabType, name: 'Documents', count: 5 },
    { id: 'funds-chain' as TabType, name: 'Funds Chain', count: 12 },
    { id: 'checks' as TabType, name: 'Checks', count: '2 flags' },
    { id: 'notes' as TabType, name: 'Notes', count: 3 },
    { id: 'audit' as TabType, name: 'Audit Trail', count: null },
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
        {activeTab === 'overview' && <OverviewTab matter={matter} />}
        {activeTab === 'questionnaire' && <QuestionnaireTab matter={matter} />}
        {activeTab === 'documents' && <DocumentsTab matter={matter} />}
        {activeTab === 'funds-chain' && <FundsChainTab matter={matter} />}
        {activeTab === 'checks' && <ChecksTab matter={matter} />}
        {activeTab === 'notes' && <NotesTab matter={matter} />}
        {activeTab === 'audit' && <AuditTab matter={matter} />}
      </div>
    </div>
  )
}

// Overview Tab
function OverviewTab({ matter }: { matter: any }) {
  return (
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
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Progress Breakdown</h2>
          <div className="space-y-4">
            <ProgressItem label="Questionnaire Completion" percentage={38} status="3 of 8 sources" />
            <ProgressItem label="Documents Uploaded" percentage={60} status="5 of 8 required" />
            <ProgressItem label="Funds Chain Reconstruction" percentage={40} status="Pending documents" />
            <ProgressItem label="Automated Checks" percentage={80} status="2 flags raised" />
          </div>
        </div>

        {/* Recent Activity */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h2>
          <div className="space-y-4">
            <ActivityLog
              action="Document uploaded"
              details="Bank statement - Barclays (Jan-Dec 2023)"
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
              action="Questionnaire updated"
              details="Business sale proceeds - evidence pending"
              user="Client Portal"
              time="5 hours ago"
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
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                  High Risk
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
              <div className="mt-1 text-sm text-gray-900">{matter.assigned_analyst}</div>
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
            <button className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg border border-gray-200">
              📧 Generate Portal Link
            </button>
            <button className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg border border-gray-200">
              📄 Request Documents
            </button>
            <button className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg border border-gray-200">
              📝 Add Note
            </button>
            <button className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 rounded-lg border border-gray-200">
              📊 Export Report
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// Questionnaire Tab
function QuestionnaireTab({ matter }: { matter: any }) {
  const sources = [
    {
      id: 1,
      type: 'Business Sale Proceeds',
      amount: 2500000,
      status: 'complete',
      completeness: 100,
      required_docs: ['Sale & Purchase Agreement', 'Completion Statement', 'Bank Statement showing receipt'],
      uploaded_docs: 3,
      total_docs: 3,
    },
    {
      id: 2,
      type: 'Savings & Investments',
      amount: 1200000,
      status: 'in_progress',
      completeness: 75,
      required_docs: ['Bank Statements (12 months)', 'Investment Statements', 'Source of savings explanation'],
      uploaded_docs: 2,
      total_docs: 3,
    },
    {
      id: 3,
      type: 'Loan from Bank',
      amount: 1500000,
      status: 'in_progress',
      completeness: 50,
      required_docs: ['Loan Agreement', 'Bank Approval Letter', 'Repayment Schedule'],
      uploaded_docs: 1,
      total_docs: 3,
    },
    {
      id: 4,
      type: 'Dividends',
      amount: 0,
      status: 'pending',
      completeness: 0,
      required_docs: [],
      uploaded_docs: 0,
      total_docs: 0,
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Source of Funds Questionnaire</h2>
            <p className="text-sm text-gray-600 mt-1">Client has declared {sources.filter(s => s.status !== 'pending').length} sources totaling £{(sources.reduce((acc, s) => acc + s.amount, 0)).toLocaleString()}</p>
          </div>
          <button className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            + Add Source
          </button>
        </div>
      </div>

      {/* Sources List */}
      <div className="space-y-4">
        {sources.map((source) => (
          <div key={source.id} className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-start mb-4">
              <div className="flex-1">
                <div className="flex items-center space-x-3">
                  <h3 className="text-base font-semibold text-gray-900">{source.type}</h3>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    source.status === 'complete' ? 'bg-green-100 text-green-800' :
                    source.status === 'in_progress' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {source.status === 'complete' ? '✓ Complete' :
                     source.status === 'in_progress' ? '⏳ In Progress' :
                     '○ Not Started'}
                  </span>
                </div>
                {source.amount > 0 && (
                  <p className="text-sm text-gray-600 mt-1">Amount: £{source.amount.toLocaleString()}</p>
                )}
              </div>
              <button className="text-sm text-primary-600 hover:text-primary-700">
                Edit
              </button>
            </div>

            {source.status !== 'pending' && (
              <>
                {/* Progress */}
                <div className="mb-4">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-gray-600">Completeness</span>
                    <span className="text-gray-900 font-medium">{source.completeness}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${source.completeness === 100 ? 'bg-green-600' : 'bg-yellow-600'}`}
                      style={{ width: `${source.completeness}%` }}
                    />
                  </div>
                </div>

                {/* Required Documents */}
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">
                    Required Evidence ({source.uploaded_docs}/{source.total_docs})
                  </h4>
                  <ul className="space-y-2">
                    {source.required_docs.map((doc, idx) => (
                      <li key={idx} className="flex items-center text-sm">
                        <span className={`mr-2 ${idx < source.uploaded_docs ? 'text-green-600' : 'text-gray-400'}`}>
                          {idx < source.uploaded_docs ? '✓' : '○'}
                        </span>
                        <span className={idx < source.uploaded_docs ? 'text-gray-900' : 'text-gray-500'}>
                          {doc}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// Documents Tab
function DocumentsTab({ matter }: { matter: any }) {
  const documents = [
    { id: 1, name: 'Business_Sale_SPA.pdf', type: 'Sale & Purchase Agreement', size: '2.4 MB', uploaded: '2024-01-15', status: 'verified' },
    { id: 2, name: 'Completion_Statement.pdf', type: 'Completion Statement', size: '156 KB', uploaded: '2024-01-15', status: 'verified' },
    { id: 3, name: 'Barclays_Statement_2023.pdf', type: 'Bank Statement', size: '1.8 MB', uploaded: '2024-01-16', status: 'processing' },
    { id: 4, name: 'Investment_Portfolio_Stmt.pdf', type: 'Investment Statement', size: '890 KB', uploaded: '2024-01-16', status: 'verified' },
    { id: 5, name: 'Loan_Agreement_HSBC.pdf', type: 'Loan Agreement', size: '3.2 MB', uploaded: '2024-01-17', status: 'flagged' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Documents</h2>
            <p className="text-sm text-gray-600 mt-1">{documents.length} documents uploaded</p>
          </div>
          <button className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            + Upload Document
          </button>
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Document
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Type
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Size
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Uploaded
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {documents.map((doc) => (
              <tr key={doc.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <span className="text-2xl mr-3">📄</span>
                    <div className="text-sm font-medium text-gray-900">{doc.name}</div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {doc.type}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {doc.size}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {new Date(doc.uploaded).toLocaleDateString()}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    doc.status === 'verified' ? 'bg-green-100 text-green-800' :
                    doc.status === 'processing' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {doc.status === 'verified' ? '✓ Verified' :
                     doc.status === 'processing' ? '⏳ Processing' :
                     '⚠ Flagged'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button className="text-primary-600 hover:text-primary-900 mr-3">View</button>
                  <button className="text-gray-600 hover:text-gray-900">Download</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// Funds Chain Tab
function FundsChainTab({ matter }: { matter: any }) {
  const events = [
    { id: 1, date: '2023-06-15', type: 'Business Sale', description: 'Sale of Previous Business Ltd', amount: 2500000, account: 'Barclays ****1234', verified: true },
    { id: 2, date: '2023-06-16', type: 'Transfer', description: 'Transfer to savings account', amount: 2500000, account: 'Barclays ****5678', verified: true },
    { id: 3, date: '2023-08-01', type: 'Investment Redemption', description: 'Vanguard ISA withdrawal', amount: 500000, account: 'Barclays ****5678', verified: true },
    { id: 4, date: '2023-09-12', type: 'Investment Redemption', description: 'Property investment sale', amount: 700000, account: 'HSBC ****9012', verified: true },
    { id: 5, date: '2023-12-01', type: 'Loan Approval', description: 'Business acquisition loan', amount: 1500000, account: 'HSBC ****3456', verified: false },
    { id: 6, date: '2024-01-10', type: 'Transfer', description: 'Consolidation for purchase', amount: 3700000, account: 'HSBC ****3456', verified: false },
    { id: 7, date: '2024-01-15', type: 'Payment (Pending)', description: 'Payment for Target Business', amount: 5200000, account: 'HSBC ****3456', verified: false },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Funds Chain Timeline</h2>
            <p className="text-sm text-gray-600 mt-1">
              Tracking £{matter.target_amount.toLocaleString()} from {events.length} events across {new Set(events.map(e => e.account)).size} accounts
            </p>
          </div>
          <div className="flex space-x-2">
            <button className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50">
              Graph View
            </button>
            <button className="px-4 py-2 bg-primary-600 text-white rounded-lg text-sm hover:bg-primary-700">
              + Add Event
            </button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Total Traced</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">£3.7M</div>
          <div className="text-xs text-gray-500 mt-1">71% of target (£5.2M)</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Verified Events</div>
          <div className="text-2xl font-bold text-green-600 mt-1">4 of 7</div>
          <div className="text-xs text-gray-500 mt-1">3 pending verification</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Shortfall</div>
          <div className="text-2xl font-bold text-red-600 mt-1">£1.5M</div>
          <div className="text-xs text-gray-500 mt-1">Awaiting loan drawdown</div>
        </div>
      </div>

      {/* Timeline */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-base font-semibold text-gray-900 mb-6">Event Timeline</h3>
        <div className="space-y-4">
          {events.map((event, idx) => (
            <div key={event.id} className="relative">
              {/* Timeline Line */}
              {idx < events.length - 1 && (
                <div className="absolute left-4 top-8 bottom-0 w-0.5 bg-gray-200" />
              )}
              
              {/* Event */}
              <div className="flex items-start space-x-4">
                {/* Icon */}
                <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                  event.verified ? 'bg-green-100' : 'bg-gray-100'
                }`}>
                  <span className={event.verified ? 'text-green-600' : 'text-gray-400'}>
                    {event.verified ? '✓' : '○'}
                  </span>
                </div>

                {/* Content */}
                <div className="flex-1 bg-gray-50 rounded-lg p-4">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-semibold text-gray-900">{event.type}</span>
                        <span className="text-xs text-gray-500">{new Date(event.date).toLocaleDateString()}</span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{event.description}</p>
                      <p className="text-xs text-gray-500 mt-1">Account: {event.account}</p>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold text-gray-900">
                        £{event.amount.toLocaleString()}
                      </div>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mt-1 ${
                        event.verified ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {event.verified ? 'Verified' : 'Pending'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// Checks Tab
function ChecksTab({ matter }: { matter: any }) {
  const checks = [
    { 
      id: 1, 
      name: 'Amount Consistency', 
      status: 'flagged', 
      severity: 'high',
      description: 'Variance detected between declared amount and traced funds',
      details: 'Declared: £5.2M | Traced: £3.7M | Variance: £1.5M (28.8%)',
      recommendation: 'Verify loan drawdown documentation',
    },
    { 
      id: 2, 
      name: 'Date Alignment', 
      status: 'flagged', 
      severity: 'medium',
      description: 'Timeline discrepancy in fund transfers',
      details: 'Business sale completion (Jun 15) to savings transfer (Jun 16) - acceptable',
      recommendation: 'No action required - within tolerance',
    },
    { 
      id: 3, 
      name: 'Identity Consistency', 
      status: 'passed', 
      severity: 'low',
      description: 'All accounts belong to declared entity',
      details: 'All bank accounts verified in name of ABC Corp Ltd',
      recommendation: null,
    },
    { 
      id: 4, 
      name: 'Document Completeness', 
      status: 'passed', 
      severity: 'low',
      description: 'All required documents present',
      details: '5 of 5 required documents uploaded and verified',
      recommendation: null,
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900">Automated Consistency Checks</h2>
        <p className="text-sm text-gray-600 mt-1">
          {checks.filter(c => c.status === 'flagged').length} flags raised from {checks.length} checks performed
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Total Checks</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{checks.length}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Passed</div>
          <div className="text-2xl font-bold text-green-600 mt-1">
            {checks.filter(c => c.status === 'passed').length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Flagged</div>
          <div className="text-2xl font-bold text-red-600 mt-1">
            {checks.filter(c => c.status === 'flagged').length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">High Severity</div>
          <div className="text-2xl font-bold text-red-600 mt-1">
            {checks.filter(c => c.severity === 'high').length}
          </div>
        </div>
      </div>

      {/* Checks List */}
      <div className="space-y-4">
        {checks.map((check) => (
          <div key={check.id} className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center space-x-3">
                <div className={`w-3 h-3 rounded-full ${
                  check.status === 'passed' ? 'bg-green-500' : 'bg-red-500'
                }`} />
                <h3 className="text-base font-semibold text-gray-900">{check.name}</h3>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  check.severity === 'high' ? 'bg-red-100 text-red-800' :
                  check.severity === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {check.severity} severity
                </span>
              </div>
              <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                check.status === 'passed' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}>
                {check.status === 'passed' ? '✓ Passed' : '⚠ Flagged'}
              </span>
            </div>

            <p className="text-sm text-gray-700 mb-2">{check.description}</p>
            <div className="bg-gray-50 rounded-lg p-3 mb-2">
              <p className="text-xs font-mono text-gray-600">{check.details}</p>
            </div>

            {check.recommendation && (
              <div className="flex items-start space-x-2 mt-3">
                <span className="text-primary-600">💡</span>
                <p className="text-sm text-gray-700">
                  <span className="font-medium">Recommendation:</span> {check.recommendation}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// Notes Tab
function NotesTab({ matter }: { matter: any }) {
  const notes = [
    { id: 1, author: 'John Smith', date: '2024-01-17 14:30', content: 'Spoke with client regarding the £1.5M loan. Confirmed drawdown expected by Jan 20th. Will need to verify loan agreement terms.' },
    { id: 2, author: 'John Smith', date: '2024-01-16 09:15', content: 'Amount variance flagged - appears to be due to pending loan. Acceptable explanation provided by client.' },
    { id: 3, author: 'System', date: '2024-01-15 16:45', content: 'Automated check completed. 2 flags raised for manual review.' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900">Case Notes</h2>
          <button className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">
            + Add Note
          </button>
        </div>
      </div>

      {/* Notes List */}
      <div className="space-y-4">
        {notes.map((note) => (
          <div key={note.id} className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-start mb-3">
              <div>
                <div className="text-sm font-semibold text-gray-900">{note.author}</div>
                <div className="text-xs text-gray-500">{note.date}</div>
              </div>
            </div>
            <p className="text-sm text-gray-700">{note.content}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// Audit Trail Tab
function AuditTab({ matter }: { matter: any }) {
  const auditLogs = [
    { id: 1, timestamp: '2024-01-17 14:35:22', user: 'John Smith', action: 'Added note', details: 'Note about client call regarding loan' },
    { id: 2, timestamp: '2024-01-17 10:15:08', user: 'System', action: 'Check executed', details: 'Amount consistency check flagged' },
    { id: 3, timestamp: '2024-01-16 16:42:19', user: 'Client Portal', action: 'Document uploaded', details: 'Barclays_Statement_2023.pdf' },
    { id: 4, timestamp: '2024-01-16 09:23:11', user: 'John Smith', action: 'Status updated', details: 'Changed from "Awaiting Client" to "Under Review"' },
    { id: 5, timestamp: '2024-01-15 10:30:00', user: 'System Administrator', action: 'Matter created', details: 'REF-2024-001 - ABC Corp Ltd' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900">Complete Audit Trail</h2>
        <p className="text-sm text-gray-600 mt-1">Full history of all actions and changes</p>
      </div>

      {/* Audit Log */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Action</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {auditLogs.map((log) => (
              <tr key={log.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                  {log.timestamp}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {log.user}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {log.action}
                </td>
                <td className="px-6 py-4 text-sm text-gray-600">
                  {log.details}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// Helper Components
function ProgressItem({ label, percentage, status }: { label: string; percentage: number; status: string }) {
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="font-medium text-gray-700">{label}</span>
        <span className="text-gray-500">{status}</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-primary-600 h-2 rounded-full transition-all"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}

function ActivityLog({ action, details, user, time }: { action: string; details: string; user: string; time: string }) {
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
