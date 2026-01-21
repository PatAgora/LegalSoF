import { useState, useEffect } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Transaction {
  id: string;
  txn_date: string;
  customer_id: string;
  direction: string;
  amount: number;
  currency: string;
  country_iso2: string;
  narrative: string;
  channel?: string;
}

interface Alert {
  id: number;
  txn_id: string;
  severity: string;
  score: number;
  reasons: string[];
  rule_tags: string[];
  status: string;
  ai_rationale?: string;
  ai_outreach?: string;
}

interface TransactionListProps {
  matterId: number;
}

export default function TransactionList({ matterId }: TransactionListProps) {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>('');

  // Debug logging
  console.log('🔍 TransactionList mounted with matterId:', matterId);
  console.log('🔍 matterId type:', typeof matterId);
  console.log('🔍 matterId is valid:', matterId && !isNaN(matterId));

  useEffect(() => {
    if (matterId && !isNaN(matterId)) {
      fetchData();
    } else {
      console.error('❌ Invalid matterId:', matterId);
      setLoading(false);
    }
  }, [matterId]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('🔍 Fetching transaction data for matter:', matterId);
      console.log('🔍 API Base URL:', API_BASE_URL);
      
      // Fetch both transactions and alerts
      const txnUrl = `${API_BASE_URL}/api/v1/matters/${matterId}/transactions`;
      const alertUrl = `${API_BASE_URL}/api/v1/matters/${matterId}/transaction-alerts`;
      
      console.log('🔍 Fetching transactions from:', txnUrl);
      console.log('🔍 Fetching alerts from:', alertUrl);
      
      const [txnResponse, alertResponse] = await Promise.all([
        fetch(txnUrl),
        fetch(alertUrl)
      ]);

      console.log('📊 Transaction response status:', txnResponse.status);
      console.log('📊 Alert response status:', alertResponse.status);

      if (!txnResponse.ok) {
        const errorText = await txnResponse.text();
        console.error('❌ Transaction fetch failed:', txnResponse.status, errorText);
        setError(`Failed to load transactions: ${txnResponse.status} ${txnResponse.statusText}`);
        return;
      }

      if (!alertResponse.ok) {
        const errorText = await alertResponse.text();
        console.error('❌ Alert fetch failed:', alertResponse.status, errorText);
        setError(`Failed to load alerts: ${alertResponse.status} ${alertResponse.statusText}`);
        return;
      }

      const txnData = await txnResponse.json();
      const alertData = await alertResponse.json();
      
      console.log('✅ Transactions loaded:', txnData.length);
      console.log('✅ Alerts loaded:', alertData.length);
      console.log('📝 Sample transaction:', txnData[0]);
      console.log('📝 Sample alert:', alertData[0]);
      
      setTransactions(txnData);
      setAlerts(alertData);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      console.error('❌ Error fetching transaction data:', errorMessage);
      console.error('❌ Full error:', error);
      setError(`Error loading data: ${errorMessage}`);
    } finally {
      setLoading(false);
    }
  };

  const getAlertsForTransaction = (txnId: string) => {
    return alerts.filter(alert => alert.txn_id === txnId);
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return 'bg-red-100 border-red-500 text-red-900';
      case 'HIGH': return 'bg-orange-100 border-orange-500 text-orange-900';
      case 'MEDIUM': return 'bg-yellow-100 border-yellow-500 text-yellow-900';
      case 'LOW': return 'bg-blue-100 border-blue-500 text-blue-900';
      default: return 'bg-gray-100 border-gray-500 text-gray-900';
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return 'bg-red-600 text-white';
      case 'HIGH': return 'bg-orange-600 text-white';
      case 'MEDIUM': return 'bg-yellow-600 text-white';
      case 'LOW': return 'bg-blue-600 text-white';
      default: return 'bg-gray-600 text-white';
    }
  };

  // Filter transactions based on alert severity
  const filteredTransactions = filterSeverity
    ? transactions.filter(txn => {
        const txnAlerts = getAlertsForTransaction(txn.id);
        return txnAlerts.some(alert => alert.severity === filterSeverity);
      })
    : transactions;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading transactions...</p>
          <p className="text-sm text-gray-500 mt-2">Matter ID: {matterId}</p>
          <p className="text-xs text-gray-400 mt-1">API: {API_BASE_URL}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-8 border-l-4 border-red-500">
        <div className="text-center">
          <div className="text-red-500 text-5xl mb-4">⚠️</div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Error Loading Data</h3>
          <p className="text-red-600 mb-4">{error}</p>
          <div className="text-sm text-left bg-gray-50 p-4 rounded">
            <p className="font-medium mb-2">Debug Info:</p>
            <p className="text-gray-700">Matter ID: {matterId}</p>
            <p className="text-gray-700">API Base URL: {API_BASE_URL}</p>
            <p className="text-gray-700">Check browser console for details</p>
          </div>
          <button
            onClick={fetchData}
            className="mt-4 px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (transactions.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center">
        <div className="text-gray-400 text-5xl mb-4">📊</div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">No Transactions Yet</h3>
        <p className="text-gray-600 mb-4">Upload a CSV or PDF bank statement to get started with AML monitoring.</p>
        <div className="text-sm text-left bg-gray-50 p-4 rounded mt-4">
          <p className="font-medium mb-2">Debug Info:</p>
          <p className="text-gray-700">Matter ID: {matterId}</p>
          <p className="text-gray-700">API Base URL: {API_BASE_URL}</p>
          <p className="text-gray-700">Transactions loaded: {transactions.length}</p>
          <p className="text-gray-700">Alerts loaded: {alerts.length}</p>
        </div>
      </div>
    );
  }

  const totalAlerts = alerts.length;
  const criticalAlerts = alerts.filter(a => a.severity === 'CRITICAL').length;
  const highAlerts = alerts.filter(a => a.severity === 'HIGH').length;

  return (
    <div className="space-y-4">
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Total Transactions</div>
          <div className="text-2xl font-bold text-gray-900">{transactions.length}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Total Alerts</div>
          <div className="text-2xl font-bold text-orange-600">{totalAlerts}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Critical Alerts</div>
          <div className="text-2xl font-bold text-red-600">{criticalAlerts}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">High Alerts</div>
          <div className="text-2xl font-bold text-orange-600">{highAlerts}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center space-x-4">
          <label className="text-sm font-medium text-gray-700">Filter by Alert Severity:</label>
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All Transactions</option>
            <option value="CRITICAL">Critical Only</option>
            <option value="HIGH">High Only</option>
            <option value="MEDIUM">Medium Only</option>
            <option value="LOW">Low Only</option>
          </select>
          <div className="text-sm text-gray-600">
            Showing {filteredTransactions.length} of {transactions.length} transactions
          </div>
        </div>
      </div>

      {/* Transaction List */}
      <div className="space-y-4">
        {filteredTransactions.map((txn) => {
          const txnAlerts = getAlertsForTransaction(txn.id);
          const highestSeverity = txnAlerts.length > 0
            ? txnAlerts.reduce((prev, curr) => {
                const severityOrder = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
                return (severityOrder[curr.severity as keyof typeof severityOrder] || 0) >
                       (severityOrder[prev.severity as keyof typeof severityOrder] || 0)
                  ? curr
                  : prev;
              })
            : null;

          return (
            <div
              key={txn.id}
              className={`bg-white rounded-lg shadow border-l-4 ${
                highestSeverity ? getSeverityColor(highestSeverity.severity) : 'border-gray-300'
              } overflow-hidden`}
            >
              <div className="p-4">
                {/* Transaction Header */}
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-sm font-mono font-semibold text-gray-900">{txn.id}</span>
                      <span className="text-xs text-gray-500">•</span>
                      <span className="text-sm text-gray-600">{new Date(txn.txn_date).toLocaleDateString()}</span>
                      <span className="text-xs text-gray-500">•</span>
                      <span className="text-sm text-gray-600">{txn.customer_id}</span>
                    </div>
                    <div className="text-sm text-gray-700">{txn.narrative}</div>
                  </div>
                  <div className="text-right">
                    <div className={`text-lg font-bold ${txn.direction === 'in' || txn.direction === 'credit' ? 'text-green-600' : 'text-red-600'}`}>
                      {txn.direction === 'in' || txn.direction === 'credit' ? '+' : '-'} {txn.currency} {txn.amount.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {txn.country_iso2} • {txn.channel || 'Unknown'}
                    </div>
                  </div>
                </div>

                {/* Alerts */}
                {txnAlerts.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <div className="flex items-center mb-2">
                      <span className="text-sm font-semibold text-gray-700 mr-2">
                        🚨 {txnAlerts.length} Alert{txnAlerts.length > 1 ? 's' : ''}:
                      </span>
                    </div>
                    <div className="space-y-3">
                      {txnAlerts.map((alert) => (
                        <div key={alert.id} className="bg-gray-50 rounded-md p-4 border border-gray-200">
                          {/* Alert Header */}
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex items-center space-x-2">
                              <span className={`inline-block px-3 py-1 text-xs font-semibold rounded ${getSeverityBadge(alert.severity)}`}>
                                {alert.severity}
                              </span>
                              <span className="text-xs font-medium text-gray-600">Risk Score: {alert.score}/100</span>
                            </div>
                            <span className={`text-xs font-medium px-2 py-1 rounded ${
                              alert.status === 'open' ? 'bg-yellow-100 text-yellow-800' :
                              alert.status === 'reviewed' ? 'bg-blue-100 text-blue-800' :
                              alert.status === 'closed' ? 'bg-green-100 text-green-800' :
                              'bg-gray-100 text-gray-800'
                            }`}>
                              {alert.status.charAt(0).toUpperCase() + alert.status.slice(1)}
                            </span>
                          </div>

                          {/* Alert Reasons */}
                          <div className="mb-3">
                            <div className="text-xs font-semibold text-gray-700 mb-1">🚩 Alert Reasons:</div>
                            <div className="space-y-1">
                              {alert.reasons.map((reason, idx) => (
                                <div key={idx} className="text-sm text-gray-700 flex items-start">
                                  <span className="mr-2 text-red-500">•</span>
                                  <span>{reason}</span>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* Rule Tags */}
                          {alert.rule_tags.length > 0 && (
                            <div className="mb-3">
                              <div className="text-xs font-semibold text-gray-700 mb-1">🏷️ Triggered Rules:</div>
                              <div className="flex flex-wrap gap-1">
                                {alert.rule_tags.map((tag, idx) => (
                                  <span key={idx} className="inline-block px-2 py-1 bg-blue-100 text-blue-700 text-xs font-medium rounded">
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* AI Rationale */}
                          <div className="mb-3 bg-white rounded p-3 border border-blue-200">
                            <div className="flex items-center mb-2">
                              <span className="text-xs font-semibold text-blue-700">🤖 AI Rationale</span>
                            </div>
                            <p className="text-sm text-gray-700 italic">
                              {alert.ai_rationale || `This ${alert.severity.toLowerCase()} risk transaction from ${txn.country_iso2} for ${txn.currency} ${txn.amount.toLocaleString()} has been flagged due to: ${alert.reasons.slice(0, 2).join(', ')}. ${
                                alert.severity === 'CRITICAL' ? 'Immediate review and enhanced due diligence is strongly recommended before processing.' :
                                alert.severity === 'HIGH' ? 'Enhanced due diligence and additional documentation should be obtained.' :
                                'Standard verification procedures should be followed.'
                              }`}
                            </p>
                          </div>

                          {/* AI Outreach */}
                          <div className="mb-3 bg-white rounded p-3 border border-purple-200">
                            <div className="flex items-center mb-2">
                              <span className="text-xs font-semibold text-purple-700">💬 AI Suggested Outreach</span>
                            </div>
                            <p className="text-sm text-gray-700 italic">
                              {alert.ai_outreach || `Dear ${txn.customer_id}, regarding your recent ${txn.direction === 'in' ? 'incoming' : 'outgoing'} transaction of ${txn.currency} ${txn.amount.toLocaleString()} on ${new Date(txn.txn_date).toLocaleDateString()}, we require additional documentation to complete our compliance review. Please provide: ${
                                alert.severity === 'CRITICAL' ? '1) Source of funds documentation, 2) Proof of business relationship, 3) Purpose of transaction, 4) Beneficial ownership details.' :
                                alert.severity === 'HIGH' ? '1) Transaction purpose statement, 2) Supporting invoices/contracts, 3) Proof of business activity.' :
                                '1) Brief transaction description, 2) Any supporting documentation.'
                              } Thank you for your cooperation.`}
                            </p>
                          </div>

                          {/* Action Buttons */}
                          <div className="flex items-center justify-between pt-3 border-t border-gray-200">
                            <div className="flex space-x-2">
                              <button className="px-3 py-1.5 text-xs font-medium text-white bg-green-600 hover:bg-green-700 rounded">
                                ✓ Approve
                              </button>
                              <button className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded">
                                👁️ Review
                              </button>
                              <button className="px-3 py-1.5 text-xs font-medium text-white bg-red-600 hover:bg-red-700 rounded">
                                🚫 Flag
                              </button>
                            </div>
                            <button className="text-xs text-gray-600 hover:text-gray-800 underline">
                              View Full Details →
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {filteredTransactions.length === 0 && (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <p className="text-gray-600">No transactions match the selected filter.</p>
        </div>
      )}
    </div>
  );
}
