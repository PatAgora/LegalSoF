import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API_BASE_URL, authFetch } from '../lib/api';
import MatterStatusBadge from '../components/ui/MatterStatusBadge';

interface ComplianceMatter {
  id: number;
  reference_number: string;
  client_name: string;
  status: string;
  compliance_status: string;
  compliance_submitted_at: string | null;
  compliance_submitted_by: string | null;
  compliance_reason: string | null;
  compliance_reviewed_at: string | null;
  compliance_reviewed_by: string | null;
  risk_rating: string;
}

function fmtDate(s: string | null): string {
  if (!s) return '—';
  const d = new Date(s);
  return isNaN(d.getTime())
    ? '—'
    : d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function ComplianceMattersPage() {
  const [matters, setMatters] = useState<ComplianceMatter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('in_review');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await authFetch(`${API_BASE_URL}/api/v1/compliance/matters`);
        if (!r.ok) throw new Error(`Could not load (${r.status})`);
        const d = await r.json();
        if (!cancelled) setMatters(d);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load compliance matters.');
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
  if (error) {
    return <div className="bg-red-50 border border-red-200 rounded-md p-6 text-sm text-red-700">{error}</div>;
  }

  const shown = filter === 'all' ? matters : matters.filter((m) => m.compliance_status === filter);
  const filters: { id: string; label: string }[] = [
    { id: 'in_review', label: 'In review' },
    { id: 'returned', label: 'Returned' },
    { id: 'cleared', label: 'Cleared' },
    { id: 'all', label: 'All' },
  ];

  return (
    <div className="space-y-6">
      <div className="border-b border-zinc-200 pb-6">
        <h1 className="font-serif text-3xl text-zinc-900">Compliance Matters</h1>
        <p className="mt-2 text-sm text-zinc-500">
          Every matter sent to the compliance team. Open a matter to review it and either
          clear it or return it with queries.
        </p>
      </div>

      <div className="flex gap-2">
        {filters.map((f) => (
          <button
            key={f.id}
            onClick={() => setFilter(f.id)}
            className={`px-3 py-1.5 text-sm rounded border transition-colors ${
              filter === f.id
                ? 'bg-zinc-900 text-white border-zinc-900'
                : 'bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-50'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="bg-white border border-zinc-200 rounded-md overflow-hidden">
        {shown.length === 0 ? (
          <div className="px-6 py-10 text-center text-sm text-zinc-500">
            No matters in this view.
          </div>
        ) : (
          <table className="min-w-full divide-y divide-zinc-200 text-sm">
            <thead className="bg-zinc-50">
              <tr>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Reference</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Client</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Risk</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Status</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Submitted</th>
                <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Reviewed</th>
                <th className="px-5 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-zinc-400"></th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-zinc-100">
              {shown.map((m) => (
                <tr key={m.id} className="hover:bg-zinc-50/60">
                  <td className="px-5 py-3">
                    <Link to={`/matters/${m.id}`} className="font-semibold text-zinc-900 hover:underline">
                      {m.reference_number}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-zinc-700">
                    {m.client_name}
                    {m.compliance_reason && (
                      <div className="mt-0.5 text-xs italic text-zinc-500 max-w-xs">
                        "{m.compliance_reason}"
                      </div>
                    )}
                  </td>
                  <td className="px-5 py-3 text-zinc-600 capitalize">{(m.risk_rating || 'medium').toLowerCase()}</td>
                  <td className="px-5 py-3"><MatterStatusBadge status={m.status} /></td>
                  <td className="px-5 py-3 text-zinc-500">
                    {fmtDate(m.compliance_submitted_at)}
                    {m.compliance_submitted_by && (
                      <div className="text-xs text-zinc-400">{m.compliance_submitted_by}</div>
                    )}
                  </td>
                  <td className="px-5 py-3 text-zinc-500">
                    {fmtDate(m.compliance_reviewed_at)}
                    {m.compliance_reviewed_by && (
                      <div className="text-xs text-zinc-400">{m.compliance_reviewed_by}</div>
                    )}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Link
                      to={`/matters/${m.id}`}
                      className="text-xs font-medium text-zinc-700 hover:text-zinc-900 underline"
                    >
                      Review →
                    </Link>
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
