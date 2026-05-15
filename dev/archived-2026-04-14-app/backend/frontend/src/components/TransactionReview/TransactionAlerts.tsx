import { useState, useEffect } from 'react';
import { API_BASE_URL, authFetch } from '../../lib/api';

interface Alert {
  id: number;
  txn_id: string;
  severity: string;
  score: number;
  reasons: string[];
  rule_tags: string[];
  status: string;
  transaction_date: string;
  amount: number;
  currency: string;
  country_iso2: string;
}

interface TransactionAlertsProps {
  matterId: number;
}

export default function TransactionAlerts({ matterId }: TransactionAlertsProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState('');

  useEffect(() => {
    fetchAlerts();
  }, [matterId, severityFilter]);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      let url = `${API_BASE_URL}/api/v1/matters/${matterId}/transaction-alerts`;
      if (severityFilter) url += `?severity=${severityFilter}`;
      
      const response = await authFetch(url);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setAlerts(data);
    } catch (error) {
      console.error('Error fetching alerts:', error);
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    const colors = {
      CRITICAL: 'bg-status-danger-100 text-status-danger-700',
      HIGH: 'bg-status-warning-100 text-status-warning-700',
      MEDIUM: 'bg-status-warning-100 text-status-warning-700',
      LOW: 'bg-primary-100 text-primary-700',
      INFO: 'bg-brand-surface-alt text-brand-ink',
    };
    return colors[severity as keyof typeof colors] || colors.INFO;
  };

  if (loading) {
    return <div className="text-center py-8">Loading alerts...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold">Transaction Alerts ({alerts.length})</h3>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="px-3 py-2 border border-brand-muted rounded-md"
        >
          <option value="">All Severities</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
      </div>

      {alerts.length === 0 ? (
        <div className="text-center py-8 text-brand-ink-tertiary">
          No alerts found. Upload transactions to generate alerts.
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <div key={alert.id} className="bg-white rounded-card border border-brand-muted p-4">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${getSeverityBadge(alert.severity)}`}>
                    {alert.severity}
                  </span>
                </div>
                <div className="text-sm text-brand-ink-tertiary">
                  {alert.transaction_date} • {alert.currency} {alert.amount?.toFixed(2)}
                </div>
              </div>

              <div className="mb-2">
                <p className="text-sm font-medium text-brand-ink-secondary">Transaction: {alert.txn_id}</p>
                {alert.country_iso2 && (
                  <p className="text-sm text-brand-ink-secondary">Country: {alert.country_iso2}</p>
                )}
              </div>

              <div className="mb-2">
                <p className="text-sm font-semibold text-brand-ink-secondary">Reasons:</p>
                <ul className="list-disc list-inside text-sm text-brand-ink-secondary">
                  {alert.reasons.map((reason, idx) => (
                    <li key={idx}>{reason}</li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
