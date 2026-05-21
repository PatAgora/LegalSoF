import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API_BASE_URL, authFetch } from '../lib/api';
import MatterStatusBadge from '../components/ui/MatterStatusBadge';

interface RecentMatter {
  id: number;
  reference_number: string;
  client_name: string;
  status: string;
  compliance_status: string;
  compliance_submitted_at: string | null;
  compliance_submitted_by: string | null;
}
interface DashboardData {
  awaiting_review: number;
  cleared: number;
  returned: number;
  recent: RecentMatter[];
}

// Chip for a matter's compliance status.
export function ComplianceStatusChip({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string; dot: string }> = {
    in_review: { label: 'In review', cls: 'bg-amber-50 text-amber-700 ring-amber-200', dot: 'bg-amber-500' },
    cleared: { label: 'Cleared', cls: 'bg-green-50 text-green-700 ring-green-200', dot: 'bg-green-500' },
    returned: { label: 'Returned', cls: 'bg-red-50 text-red-700 ring-red-200', dot: 'bg-red-500' },
    none: { label: 'Not submitted', cls: 'bg-zinc-50 text-zinc-500 ring-zinc-200', dot: 'bg-zinc-400' },
  };
  const c = map[status] || map.none;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold ring-1 ring-inset ${c.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}

function fmtDate(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  return isNaN(d.getTime())
    ? '—'
    : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function ComplianceDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await authFetch(`${API_BASE_URL}/api/v1/compliance/dashboard`);
        if (!r.ok) throw new Error(`Could not load (${r.status})`);
        const d = await r.json();
        if (!cancelled) setData(d);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load compliance dashboard.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-zinc-600" />
      </div>
    );
  }
  if (error || !data) {
    return <div className="bg-red-50 border border-red-200 rounded-md p-6 text-sm text-red-700">{error}</div>;
  }

  const cards = [
    { label: 'Awaiting review', value: data.awaiting_review, cls: 'text-amber-700' },
    { label: 'Cleared', value: data.cleared, cls: 'text-green-700' },
    { label: 'Returned with queries', value: data.returned, cls: 'text-red-700' },
  ];

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-end justify-between border-b border-zinc-200 pb-6">
        <div>
          <h1 className="font-serif text-3xl text-zinc-900">Compliance Dashboard</h1>
          <p className="mt-2 text-sm text-zinc-500">
            Matters sent to the compliance team for review.
          </p>
        </div>
        <Link
          to="/compliance/matters"
          className="px-4 py-2 text-sm font-medium border border-zinc-300 text-zinc-700 hover:bg-zinc-50 rounded"
        >
          All compliance matters →
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-white border border-zinc-200 rounded-md p-5">
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">{c.label}</p>
            <p className={`text-3xl font-bold tabular-nums ${c.cls}`}>{c.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white border border-zinc-200 rounded-md overflow-hidden">
        <div className="bg-zinc-50 border-b border-zinc-200 px-6 py-4">
          <h2 className="text-base font-bold text-zinc-900">Recent compliance activity</h2>
        </div>
        {data.recent.length === 0 ? (
          <div className="px-6 py-8 text-center text-sm text-zinc-500">
            No matters have been sent to compliance yet.
          </div>
        ) : (
          <table className="min-w-full divide-y divide-zinc-200 text-sm">
            <thead className="bg-zinc-50">
              <tr>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Reference</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Client</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Status</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Submitted</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-zinc-100">
              {data.recent.map((m) => (
                <tr key={m.id} className="hover:bg-zinc-50/60">
                  <td className="px-5 py-3">
                    <Link to={`/matters/${m.id}?from=compliance`} className="font-semibold text-zinc-900 hover:underline">
                      {m.reference_number}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-zinc-700">{m.client_name}</td>
                  <td className="px-5 py-3"><MatterStatusBadge status={m.status} /></td>
                  <td className="px-5 py-3 text-zinc-500">
                    {fmtDate(m.compliance_submitted_at)}
                    {m.compliance_submitted_by && (
                      <span className="text-xs text-zinc-400"> · {m.compliance_submitted_by}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
