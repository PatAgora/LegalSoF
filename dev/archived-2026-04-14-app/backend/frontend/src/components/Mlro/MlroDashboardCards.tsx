// MLRO dashboard cards — open reports, DAML clocks (live working-day
// countdown, red under 2 working days), active moratoria, training
// expiry and overdue policy reviews.
import { useEffect, useState } from 'react';
import {
  MlroDashboard, calendarDaysUntil, fmtDate, mlroGet, workingDaysUntil,
} from './mlro';

export default function MlroDashboardCards({ refreshKey }: { refreshKey: number }) {
  const [data, setData] = useState<MlroDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const d = await mlroGet<MlroDashboard>('/mlro/dashboard');
        if (!cancelled) { setData(d); setError(null); }
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load MLRO dashboard.');
      }
    })();
    return () => { cancelled = true; };
  }, [refreshKey]);

  // Live countdowns — re-render every 60s so the working-day clocks stay honest.
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 60_000);
    return () => clearInterval(t);
  }, []);

  if (error) {
    return <div className="bg-red-50 border border-red-200 rounded-md p-4 text-sm text-red-700">{error}</div>;
  }
  if (!data) {
    return (
      <div className="flex items-center justify-center py-10">
        <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-600" />
      </div>
    );
  }

  const cards = [
    { label: 'Open reports', value: data.open_reports, sub: 'received + under review', cls: 'text-blue-700' },
    { label: 'Awaiting DAML consent', value: data.daml_deadlines_within_7_days.length, sub: 'deadline within 7 days', cls: 'text-amber-700' },
    { label: 'Active moratoria', value: data.active_moratoria.filter((m) => m.active).length, sub: '31-day clocks running', cls: 'text-red-700' },
    { label: 'Training expiring', value: data.training_expiring_within_60_days, sub: 'within 60 days', cls: 'text-purple-700' },
    { label: 'Policy reviews overdue', value: data.overdue_policy_reviews, sub: 'approved policies past review date', cls: 'text-zinc-700' },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="bg-white border border-zinc-200 rounded-md p-4">
            <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">{c.label}</p>
            <p className={`text-3xl font-bold tabular-nums ${c.cls}`}>{c.value}</p>
            <p className="text-[11px] text-zinc-400 mt-0.5">{c.sub}</p>
          </div>
        ))}
      </div>

      {data.daml_deadlines_within_7_days.length > 0 && (
        <div className="bg-white border border-amber-200 rounded-md overflow-hidden">
          <div className="bg-amber-50 border-b border-amber-200 px-4 py-2.5">
            <h3 className="text-sm font-bold text-amber-800">
              DAML notice periods ending soon — work on these matters must not proceed
            </h3>
          </div>
          <ul className="divide-y divide-zinc-100">
            {data.daml_deadlines_within_7_days.map((d) => {
              const wd = workingDaysUntil(d.consent_deadline);
              const urgent = d.overdue || wd < 2;
              return (
                <li key={d.sar_id} className="px-4 py-2.5 flex items-center justify-between text-sm">
                  <span className="text-zinc-700">
                    SAR <span className="font-mono">{d.sar_reference || `#${d.sar_id}`}</span>
                    <span className="text-zinc-400"> · deadline {fmtDate(d.consent_deadline)}</span>
                  </span>
                  <span className={`font-semibold tabular-nums ${urgent ? 'text-red-700' : 'text-amber-700'}`}>
                    {d.overdue || wd < 0
                      ? 'Notice period ended — check the NCA portal'
                      : `${wd} working day${wd === 1 ? '' : 's'} left`}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {data.active_moratoria.some((m) => m.active) && (
        <div className="bg-white border border-red-200 rounded-md overflow-hidden">
          <div className="bg-red-50 border-b border-red-200 px-4 py-2.5">
            <h3 className="text-sm font-bold text-red-800">
              Active moratorium periods (31 calendar days from refusal)
            </h3>
          </div>
          <ul className="divide-y divide-zinc-100">
            {data.active_moratoria.filter((m) => m.active).map((m) => {
              const cd = calendarDaysUntil(m.moratorium_end);
              return (
                <li key={m.sar_id} className="px-4 py-2.5 flex items-center justify-between text-sm">
                  <span className="text-zinc-700">
                    SAR <span className="font-mono">{m.sar_reference || `#${m.sar_id}`}</span>
                    <span className="text-zinc-400"> · ends {fmtDate(m.moratorium_end)}</span>
                  </span>
                  <span className="font-semibold tabular-nums text-red-700">
                    {cd} calendar day{cd === 1 ? '' : 's'} remaining
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
