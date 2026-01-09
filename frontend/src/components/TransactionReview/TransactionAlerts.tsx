import { useState, useEffect } from 'react';

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
      let url = `http://localhost:8000/api/v1/matters/${matterId}/transaction-alerts`;
      if (severityFilter) url += `?severity=${severityFilter}`;
      
      const response = await fetch(url);
      const data = await response.json();
      setAlerts(data);
    } catch (error) {
      console.error('Error fetching alerts:', error);
    } finally {
      setLoading(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    const colors = {
      CRITICAL: 'bg-red-100 text-red-800',
      HIGH: 'bg-orange-100 text-orange-800',
      MEDIUM: 'bg-yellow-100 text-yellow-800',
      LOW: 'bg-blue-100 text-blue-800',
      INFO: 'bg-gray-100 text-gray-800',
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
          className="px-3 py-2 border border-gray-300 rounded-md"
        >
          <option value="">All Severities</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>
      </div>

      {alerts.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          No alerts found. Upload transactions to generate alerts.
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <div key={alert.id} className="bg-white rounded-lg shadow p-4">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${getSeverityBadge(alert.severity)}`}>
                    {alert.severity}
                  </span>
                  <span className="ml-2 text-sm text-gray-600">Score: {alert.score}</span>
                </div>
                <div className="text-sm text-gray-500">
                  {alert.transaction_date} • {alert.currency} {alert.amount?.toFixed(2)}
                </div>
              </div>

              <div className="mb-2">
                <p className="text-sm font-medium text-gray-700">Transaction: {alert.txn_id}</p>
                {alert.country_iso2 && (
                  <p className="text-sm text-gray-600">Country: {alert.country_iso2}</p>
                )}
              </div>

              <div className="mb-2">
                <p className="text-sm font-semibold text-gray-700">Reasons:</p>
                <ul className="list-disc list-inside text-sm text-gray-600">
                  {alert.reasons.map((reason, idx) => (
                    <li key={idx}>{reason}</li>
                  ))}
                </ul>
              </div>

              <div className="flex gap-2">
                {alert.rule_tags.map((tag, idx) => (
                  <span key={idx} className="inline-block px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
