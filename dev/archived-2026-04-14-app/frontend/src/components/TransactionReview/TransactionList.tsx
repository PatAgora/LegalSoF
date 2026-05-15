import { useState, useEffect } from 'react';
import { API_BASE_URL, authFetch } from '../../lib/api';

// Country code to full name mapping
const COUNTRY_NAMES: { [key: string]: string } = {
  'GB': 'United Kingdom',
  'US': 'United States',
  'IR': 'Iran',
  'AE': 'UAE',
  'DE': 'Germany',
  'FR': 'France',
  'ES': 'Spain',
  'IT': 'Italy',
  'NL': 'Netherlands',
  'BE': 'Belgium',
  'IE': 'Ireland',
  'CH': 'Switzerland',
  'CN': 'China',
  'RU': 'Russia',
  'IN': 'India',
  'JP': 'Japan',
  'KR': 'South Korea',
  'AU': 'Australia',
  'CA': 'Canada',
  'BR': 'Brazil',
  'MX': 'Mexico',
  'SG': 'Singapore',
  'HK': 'Hong Kong',
  'KY': 'Cayman Islands',
  'VG': 'British Virgin Islands',
  'JE': 'Jersey',
  'GG': 'Guernsey',
  'IM': 'Isle of Man',
  'CY': 'Cyprus',
  'MT': 'Malta',
  'LU': 'Luxembourg',
  'LI': 'Liechtenstein',
  'MC': 'Monaco',
  'PA': 'Panama',
  'BZ': 'Belize',
  'AF': 'Afghanistan',
  'SY': 'Syria',
  'KP': 'North Korea',
  'CU': 'Cuba',
  'VE': 'Venezuela',
  'MM': 'Myanmar',
  'BY': 'Belarus',
  'ZW': 'Zimbabwe',
  'SD': 'Sudan',
  'SS': 'South Sudan',
  'LY': 'Libya',
  'YE': 'Yemen',
  'SO': 'Somalia',
  'IQ': 'Iraq',
  'LB': 'Lebanon',
  'PK': 'Pakistan',
  'NG': 'Nigeria',
  'ZA': 'South Africa',
  'EG': 'Egypt',
  'SA': 'Saudi Arabia',
  'QA': 'Qatar',
  'KW': 'Kuwait',
  'BH': 'Bahrain',
  'OM': 'Oman',
};

// Get display name for country code
const getCountryName = (code: string | null | undefined): string => {
  if (!code) return 'N/A';
  const upperCode = code.toUpperCase();
  return COUNTRY_NAMES[upperCode] || upperCode;
};

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
  const [filterAccount, setFilterAccount] = useState<string>('');

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
        authFetch(txnUrl),
        authFetch(alertUrl)
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
      case 'CRITICAL': return 'bg-status-danger-100 border-status-danger-500 text-status-danger-700';
      case 'HIGH': return 'bg-status-warning-100 border-status-warning-500 text-status-warning-700';
      case 'MEDIUM': return 'bg-status-warning-100 border-status-warning-500 text-status-warning-700';
      case 'LOW': return 'bg-primary-100 border-primary-400 text-primary-800';
      default: return 'bg-brand-surface-alt border-brand-muted text-brand-ink';
    }
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return 'bg-status-danger-700 text-white';
      case 'HIGH': return 'bg-status-warning-700 text-white';
      case 'MEDIUM': return 'bg-status-warning-700 text-white';
      case 'LOW': return 'bg-primary-500 text-white';
      default: return 'bg-brand-ink-tertiary text-white';
    }
  };

  // Get unique accounts from transactions
  const uniqueAccounts = [...new Set(transactions.map(txn => txn.customer_id).filter(Boolean))];

  // Filter transactions based on alert severity AND account
  const filteredTransactions = transactions.filter(txn => {
    // Account filter
    if (filterAccount && txn.customer_id !== filterAccount) {
      return false;
    }
    // Severity filter
    if (filterSeverity) {
      const txnAlerts = getAlertsForTransaction(txn.id);
      return txnAlerts.some(alert => alert.severity === filterSeverity);
    }
    return true;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-brand-ink-secondary">Loading transactions...</p>
          <p className="text-sm text-brand-ink-tertiary mt-2">Matter ID: {matterId}</p>
          <p className="text-xs text-brand-ink-tertiary mt-1">API: {API_BASE_URL}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-card border border-brand-muted p-8 border-l-4 border-status-danger-500">
        <div className="text-center">
          <div className="text-status-danger-700 text-5xl mb-4">⚠️</div>
          <h3 className="text-lg font-semibold text-brand-ink mb-2">Error Loading Data</h3>
          <p className="text-status-danger-700 mb-4">{error}</p>
          <div className="text-sm text-left bg-brand-surface-alt p-4 rounded">
            <p className="font-medium mb-2">Debug Info:</p>
            <p className="text-brand-ink-secondary">Matter ID: {matterId}</p>
            <p className="text-brand-ink-secondary">API Base URL: {API_BASE_URL}</p>
            <p className="text-brand-ink-secondary">Check browser console for details</p>
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
      <div className="bg-white rounded-card border border-brand-muted p-8 text-center">
        <div className="text-brand-ink-tertiary text-5xl mb-4">📊</div>
        <h3 className="text-lg font-semibold text-brand-ink mb-2">No Transactions Yet</h3>
        <p className="text-brand-ink-secondary mb-4">Upload a CSV or PDF bank statement to get started with AML monitoring.</p>
        <div className="text-sm text-left bg-brand-surface-alt p-4 rounded mt-4">
          <p className="font-medium mb-2">Debug Info:</p>
          <p className="text-brand-ink-secondary">Matter ID: {matterId}</p>
          <p className="text-brand-ink-secondary">API Base URL: {API_BASE_URL}</p>
          <p className="text-brand-ink-secondary">Transactions loaded: {transactions.length}</p>
          <p className="text-brand-ink-secondary">Alerts loaded: {alerts.length}</p>
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
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">Total Transactions</div>
          <div className="text-2xl font-bold text-brand-ink">{transactions.length}</div>
        </div>
        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">Accounts</div>
          <div className="text-2xl font-bold text-primary-500">{uniqueAccounts.length}</div>
        </div>
        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">Total Alerts</div>
          <div className="text-2xl font-bold text-status-warning-700">{totalAlerts}</div>
        </div>
        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">Critical Alerts</div>
          <div className="text-2xl font-bold text-status-danger-700">{criticalAlerts}</div>
        </div>
        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">High Alerts</div>
          <div className="text-2xl font-bold text-status-warning-700">{highAlerts}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-card border border-brand-muted p-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Account Filter */}
          {uniqueAccounts.length > 1 && (
            <div className="flex items-center space-x-2">
              <label className="text-sm font-medium text-brand-ink-secondary">Account:</label>
              <select
                value={filterAccount}
                onChange={(e) => setFilterAccount(e.target.value)}
                className="px-3 py-2 border border-brand-muted rounded-md focus:ring-2 focus:ring-primary-500"
              >
                <option value="">All Accounts ({uniqueAccounts.length})</option>
                {uniqueAccounts.map((account) => (
                  <option key={account} value={account}>
                    {account}
                  </option>
                ))}
              </select>
            </div>
          )}
          
          {/* Severity Filter */}
          <div className="flex items-center space-x-2">
            <label className="text-sm font-medium text-brand-ink-secondary">Filter by Alert Severity:</label>
            <select
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              className="px-3 py-2 border border-brand-muted rounded-md focus:ring-2 focus:ring-primary-500"
            >
              <option value="">All Transactions</option>
              <option value="CRITICAL">Critical Only</option>
              <option value="HIGH">High Only</option>
              <option value="MEDIUM">Medium Only</option>
              <option value="LOW">Low Only</option>
            </select>
          </div>
          
          <div className="text-sm text-brand-ink-secondary">
            Showing {filteredTransactions.length} of {transactions.length} transactions
            {filterAccount && ` (Account: ${filterAccount})`}
          </div>
        </div>
      </div>

      {/* Transaction Table */}
      <div className="bg-white rounded-card border border-brand-muted overflow-hidden">
        {/* Table Header */}
        <div className="bg-brand-surface-alt border-b border-brand-muted">
          <div className="grid grid-cols-12 gap-4 px-6 py-4 text-xs font-semibold text-brand-ink-secondary uppercase tracking-wider">
            <div className="col-span-2">Transaction ID</div>
            <div className="col-span-1">Date</div>
            <div className="col-span-1">Severity</div>
            <div className="col-span-4">Description</div>
            <div className="col-span-1 text-right">Amount</div>
            <div className="col-span-2">Country</div>
            <div className="col-span-1 text-center">Actions</div>
          </div>
        </div>

        {/* Table Body */}
        <div className="divide-y divide-brand-muted">
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
              <div key={txn.id}>
                {/* Main Transaction Row */}
                <div className={`grid grid-cols-12 gap-4 px-6 py-4 hover:bg-brand-surface-alt transition-colors border-l-4 ${
                  highestSeverity ? getSeverityColor(highestSeverity.severity) : 'border-transparent'
                }`}>
                  {/* Transaction ID */}
                  <div className="col-span-2">
                    <div className="text-sm font-mono font-semibold text-brand-ink">{txn.id}</div>
                    <div className="text-xs text-brand-ink-tertiary">{txn.customer_id}</div>
                  </div>

                  {/* Date */}
                  <div className="col-span-1">
                    <div className="text-sm text-brand-ink-secondary">{new Date(txn.txn_date).toLocaleDateString('en-GB')}</div>
                  </div>

                  {/* Severity Column */}
                  <div className="col-span-1">
                    {highestSeverity ? (
                      <span className={`inline-flex items-center justify-center w-full px-2 py-1 rounded text-xs font-bold whitespace-nowrap ${
                        highestSeverity.severity === 'CRITICAL' ? 'bg-status-danger-700 text-white' :
                        highestSeverity.severity === 'HIGH' ? 'bg-status-warning-700 text-white' :
                        highestSeverity.severity === 'MEDIUM' ? 'bg-status-warning-700 text-white' :
                        'bg-primary-500 text-white'
                      }`}>
                        {highestSeverity.severity === 'CRITICAL' ? '🔴' : 
                         highestSeverity.severity === 'HIGH' ? '🟠' : 
                         highestSeverity.severity === 'MEDIUM' ? '🟡' : '🔵'}
                        {' '}{highestSeverity.severity}
                      </span>
                    ) : (
                      <span className="inline-flex items-center justify-center w-full px-2 py-1 rounded text-xs font-medium bg-status-success-50 text-status-success-700 border border-status-success-200">
                        ✓ Clean
                      </span>
                    )}
                    {txnAlerts.length > 1 && (
                      <div className="text-xs text-brand-ink-tertiary mt-1 text-center">+{txnAlerts.length - 1} more</div>
                    )}
                  </div>

                  {/* Description */}
                  <div className="col-span-4">
                    <div className="text-sm text-brand-ink-secondary break-words">{txn.narrative}</div>
                  </div>

                  {/* Amount */}
                  <div className="col-span-1 text-right">
                    <div className={`text-sm font-bold ${txn.direction === 'in' || txn.direction === 'credit' ? 'text-status-success-700' : 'text-status-danger-700'}`}>
                      {txn.direction === 'in' || txn.direction === 'credit' ? '+' : '-'} {txn.currency} {txn.amount.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </div>
                  </div>

                  {/* Country */}
                  <div className="col-span-2">
                    <div className="text-sm text-brand-ink-secondary">{getCountryName(txn.country_iso2)}</div>
                  </div>

                  {/* Actions */}
                  <div className="col-span-1 text-center">
                    {txnAlerts.length > 0 && (
                      <button 
                        className="text-primary-600 hover:text-primary-800 text-sm font-medium"
                        onClick={() => {/* Toggle alert details */}}
                      >
                        🔍 Review
                      </button>
                    )}
                  </div>
                </div>

                {/* Alert Details (Expandable) - Only show if there are alerts */}
                {txnAlerts.length > 0 && (
                  <div className="bg-brand-surface-alt px-6 py-4 border-t border-brand-muted">
                    <div className="space-y-3">
                      {txnAlerts.map((alert) => (
                        <div key={alert.id} className="bg-white rounded-md p-4 border border-brand-muted">
                          {/* Alert Header */}
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex items-center space-x-2">
                              <span className={`inline-block px-3 py-1 text-xs font-semibold rounded ${getSeverityBadge(alert.severity)}`}>
                                {alert.severity}
                              </span>
                            </div>
                          </div>

                          {/* Alert Reasons */}
                          <div className="mb-3">
                            <div className="text-xs font-semibold text-brand-ink-secondary mb-1">🚩 Alert Reasons:</div>
                            <div className="space-y-1">
                              {alert.reasons.map((reason, idx) => (
                                <div key={idx} className="text-sm text-brand-ink-secondary flex items-start">
                                  <span className="mr-2 text-status-danger-700">•</span>
                                  <span>{reason}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {filteredTransactions.length === 0 && (
        <div className="bg-white rounded-card border border-brand-muted p-8 text-center">
          <p className="text-brand-ink-secondary">No transactions match the selected filter.</p>
        </div>
      )}
    </div>
  );
}
