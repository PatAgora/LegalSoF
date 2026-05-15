import { useState, useEffect } from 'react';
import { API_BASE_URL, authFetch } from '../../lib/api';

interface Stats {
  total_transactions: number;
  total_alerts: number;
  critical_alerts: number;
  high_alerts: number;
  total_in: number;
  total_out: number;
  high_risk_value: number;
  alert_rate: number;
}

interface TransactionDashboardProps {
  matterId: number;
}

export default function TransactionDashboard({ matterId }: TransactionDashboardProps) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboard();
  }, [matterId]);

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/transaction-dashboard`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      setStats(data.stats);
    } catch (error) {
      console.error('Error fetching dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="text-center py-8">Loading dashboard...</div>;
  }

  if (!stats) {
    return <div className="text-center py-8 text-brand-ink-tertiary">No data available</div>;
  }

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold">Transaction Dashboard</h3>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">Total Transactions</div>
          <div className="text-2xl font-bold">{stats.total_transactions}</div>
        </div>

        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">Total Alerts</div>
          <div className="text-2xl font-bold">{stats.total_alerts}</div>
          <div className="text-xs text-brand-ink-tertiary">{stats.alert_rate.toFixed(1)}% of transactions</div>
        </div>

        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">Critical Alerts</div>
          <div className="text-2xl font-bold text-status-danger-700">{stats.critical_alerts}</div>
        </div>

        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">High Risk Alerts</div>
          <div className="text-2xl font-bold text-status-warning-700">{stats.high_alerts}</div>
        </div>
      </div>

      {/* Money Flow */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">Total Money In</div>
          <div className="text-xl font-bold text-status-success-700">£{stats.total_in.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>

        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">Total Money Out</div>
          <div className="text-xl font-bold text-primary-500">£{stats.total_out.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>

        <div className="bg-white rounded-card border border-brand-muted p-4">
          <div className="text-sm text-brand-ink-secondary">High Risk Value</div>
          <div className="text-xl font-bold text-status-danger-700">£{stats.high_risk_value.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>
      </div>
    </div>
  );
}
