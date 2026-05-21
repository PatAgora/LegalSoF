import { useEffect, useState } from 'react';
import { API_BASE_URL, authFetch } from '../lib/api';

// Root Cause Analysis dashboard - a firm-level rollup of the recurring
// issues, risk concentration and compliance loop across every matter,
// with derived training recommendations to support continuous learning.

interface Gap { key: string; label: string; count: number }
interface SourceType { source_type: string; label: string; total: number; verified: number; outstanding: number }
interface Reason { reason: string; count: number }
interface Rec { title: string; detail: string; basis: string }
interface UserMetric { user: string; referrals: number; verified: number }

interface RCAData {
  total_matters: number;
  matters_assessed: number;
  sof_gap_types: Gap[];
  source_types: SourceType[];
  matters_by_risk: Record<string, number>;
  matters_by_type: Record<string, number>;
  compliance: {
    matters_referred: number;
    matters_returned: number;
    claims_referred: number;
    top_reasons: Reason[];
  };
  user_metrics: UserMetric[];
  training_recommendations: Rec[];
}

function titleCase(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function Panel({ title, caption, children }: { title: string; caption?: string; children: React.ReactNode }) {
  return (
    <section className="bg-white border border-zinc-200 rounded-md overflow-hidden">
      <div className="bg-zinc-50 border-b border-zinc-200 px-6 py-4">
        <h2 className="text-base font-bold text-zinc-900">{title}</h2>
        {caption && <p className="mt-0.5 text-xs text-zinc-500">{caption}</p>}
      </div>
      <div className="px-6 py-5">{children}</div>
    </section>
  );
}

// A simple count-bar row: label on the left, proportional bar, count.
function BarRow({ label, count, max, tone = 'bg-zinc-500' }: { label: string; count: number; max: number; tone?: string }) {
  const pct = max > 0 ? Math.max(6, Math.round((count / max) * 100)) : 0;
  return (
    <li className="flex items-center gap-4 py-2">
      <div className="flex-1 min-w-0">
        <div className="text-sm text-zinc-800">{label}</div>
        <div className="mt-1.5 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
          <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div className="w-12 text-right text-sm font-semibold text-zinc-700 tabular-nums">{count}</div>
    </li>
  );
}

export default function RCADashboardPage() {
  const [data, setData] = useState<RCAData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await authFetch(`${API_BASE_URL}/api/v1/analytics/rca-dashboard`);
        if (!r.ok) throw new Error(`Could not load (${r.status})`);
        const d = await r.json();
        if (!cancelled) setData(d);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load the RCA dashboard.');
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

  const gapMax = Math.max(1, ...data.sof_gap_types.map((g) => g.count));
  const riskEntries = Object.entries(data.matters_by_risk).filter(([, n]) => n > 0);
  const typeEntries = Object.entries(data.matters_by_type)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1]);
  const typeMax = Math.max(1, ...typeEntries.map(([, n]) => n));

  return (
    <div className="space-y-6">
      <div className="border-b border-zinc-200 pb-6">
        <h1 className="font-serif text-3xl text-zinc-900">Root Cause Analysis</h1>
        <p className="mt-2 text-sm text-zinc-500 max-w-3xl">
          Recurring issues, risk concentration and the compliance loop across every matter -
          the firm-level signal for continuous learning and targeted training.
        </p>
      </div>

      {/* Topline */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total matters', value: data.total_matters },
          { label: 'Matters assessed', value: data.matters_assessed },
          { label: 'Matters referred to compliance', value: data.compliance.matters_referred },
          { label: 'Claims referred to compliance', value: data.compliance.claims_referred },
        ].map((s) => (
          <div key={s.label} className="bg-white border border-zinc-200 rounded-md p-5">
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">{s.label}</p>
            <p className="text-3xl font-bold tabular-nums text-zinc-900">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Proposed training areas - lead with the actionable output */}
      <Panel
        title="Proposed training areas"
        caption="Areas to improve, collated from what the system is seeing - each is evidenced by the matters it was drawn from."
      >
        {data.training_recommendations.length === 0 ? (
          <p className="text-sm text-zinc-500">
            No recurring patterns strong enough to recommend training yet. Recommendations appear as case volume builds.
          </p>
        ) : (
          <ul className="space-y-3">
            {data.training_recommendations.map((rec, i) => (
              <li key={i} className="border border-zinc-200 rounded p-3">
                <div className="text-sm font-semibold text-zinc-900">{rec.title}</div>
                <p className="mt-0.5 text-xs text-zinc-600 leading-relaxed">{rec.detail}</p>
                <p className="mt-1 text-[11px] font-medium text-amber-700">Basis: {rec.basis}</p>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {/* Recurring SoF gaps */}
      <Panel title="Recurring source-of-funds gaps" caption="Where source-of-funds checks most often fall short.">
        {data.sof_gap_types.length === 0 ? (
          <p className="text-sm text-zinc-500">No source-of-funds gaps recorded.</p>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {data.sof_gap_types.map((g) => (
              <BarRow key={g.key} label={g.label} count={g.count} max={gapMax} tone="bg-amber-500" />
            ))}
          </ul>
        )}
      </Panel>

      {/* Per-user metrics */}
      <Panel title="Reviewer activity" caption="Who is referring matters to compliance and signing claims off.">
        {data.user_metrics.length === 0 ? (
          <p className="text-sm text-zinc-500">No reviewer activity recorded yet.</p>
        ) : (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400 border-b border-zinc-200">
                <th className="py-2 pr-4">Reviewer</th>
                <th className="py-2 px-4 text-right">Sent to compliance</th>
                <th className="py-2 pl-4 text-right">Claims signed off</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {data.user_metrics.map((u) => (
                <tr key={u.user}>
                  <td className="py-2 pr-4 text-zinc-800">{u.user}</td>
                  <td className="py-2 px-4 text-right tabular-nums text-amber-700">{u.referrals}</td>
                  <td className="py-2 pl-4 text-right tabular-nums text-green-700">{u.verified}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {/* Source type breakdown */}
      <Panel title="Source-of-funds claims by type" caption="Which declared sources are hardest to evidence - a pointer to where training is needed.">
        {data.source_types.length === 0 ? (
          <p className="text-sm text-zinc-500">No claims recorded yet.</p>
        ) : (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400 border-b border-zinc-200">
                <th className="py-2 pr-4">Source type</th>
                <th className="py-2 px-4 text-right">Claims</th>
                <th className="py-2 px-4 text-right">Verified</th>
                <th className="py-2 px-4 text-right">Outstanding</th>
                <th className="py-2 pl-4 text-right">Verified rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {data.source_types.map((s) => {
                const rate = s.total > 0 ? Math.round((s.verified / s.total) * 100) : 0;
                return (
                  <tr key={s.source_type}>
                    <td className="py-2 pr-4 text-zinc-800">{s.label}</td>
                    <td className="py-2 px-4 text-right tabular-nums text-zinc-700">{s.total}</td>
                    <td className="py-2 px-4 text-right tabular-nums text-green-700">{s.verified}</td>
                    <td className="py-2 px-4 text-right tabular-nums text-amber-700">{s.outstanding}</td>
                    <td className={`py-2 pl-4 text-right tabular-nums font-semibold ${rate >= 50 ? 'text-zinc-700' : 'text-red-700'}`}>
                      {rate}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk + type concentration */}
        <Panel title="Risk concentration" caption="Where the firm's matter exposure sits.">
          <div className="space-y-5">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 mb-2">By risk rating</div>
              {riskEntries.length === 0 ? (
                <p className="text-sm text-zinc-500">No rated matters.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {riskEntries.map(([k, n]) => (
                    <span key={k} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-100 text-xs text-zinc-700">
                      <span className="font-semibold capitalize">{k}</span>
                      <span className="tabular-nums text-zinc-500">{n}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 mb-2">By matter type</div>
              {typeEntries.length === 0 ? (
                <p className="text-sm text-zinc-500">No matter types recorded.</p>
              ) : (
                <ul className="divide-y divide-zinc-100">
                  {typeEntries.map(([k, n]) => (
                    <BarRow key={k} label={titleCase(k)} count={n} max={typeMax} tone="bg-zinc-500" />
                  ))}
                </ul>
              )}
            </div>
          </div>
        </Panel>

        {/* Compliance loop */}
        <Panel title="Compliance loop" caption="How often, and why, matters reach the compliance team.">
          <div className="grid grid-cols-3 gap-3 mb-4">
            {[
              { label: 'Referred', value: data.compliance.matters_referred },
              { label: 'Returned', value: data.compliance.matters_returned },
              { label: 'Claims referred', value: data.compliance.claims_referred },
            ].map((s) => (
              <div key={s.label} className="bg-zinc-50 border border-zinc-200 rounded p-3 text-center">
                <div className="text-2xl font-bold tabular-nums text-zinc-900">{s.value}</div>
                <div className="mt-0.5 text-[11px] text-zinc-500">{s.label}</div>
              </div>
            ))}
          </div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400 mb-2">Most common referral reasons</div>
          {data.compliance.top_reasons.length === 0 ? (
            <p className="text-sm text-zinc-500">No referral reasons recorded.</p>
          ) : (
            <ul className="space-y-1.5">
              {data.compliance.top_reasons.map((r, i) => (
                <li key={i} className="flex items-start gap-3 text-xs">
                  <span className="mt-0.5 w-6 shrink-0 text-right font-semibold text-zinc-700 tabular-nums">{r.count}</span>
                  <span className="flex-1 min-w-0 text-zinc-600 italic">"{r.reason}"</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
