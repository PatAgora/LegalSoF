import { useState, useEffect } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/v1/matters/${matterId}/transaction-dashboard`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
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
    return <div className="text-center py-8 text-gray-500">No data available</div>;
  }

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold">Transaction Dashboard</h3>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Total Transactions</div>
          <div className="text-2xl font-bold">{stats.total_transactions}</div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Total Alerts</div>
          <div className="text-2xl font-bold">{stats.total_alerts}</div>
          <div className="text-xs text-gray-500">{stats.alert_rate.toFixed(1)}% of transactions</div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Critical Alerts</div>
          <div className="text-2xl font-bold text-red-600">{stats.critical_alerts}</div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">High Risk Alerts</div>
          <div className="text-2xl font-bold text-orange-600">{stats.high_alerts}</div>
        </div>
      </div>

      {/* Money Flow */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Total Money In</div>
          <div className="text-xl font-bold text-green-600">£{stats.total_in.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">Total Money Out</div>
          <div className="text-xl font-bold text-blue-600">£{stats.total_out.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-600">High Risk Value</div>
          <div className="text-xl font-bold text-red-600">£{stats.high_risk_value.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        </div>
      </div>
    </div>
  );
}
