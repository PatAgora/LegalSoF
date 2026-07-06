// SARs & DAML tab — every recorded SAR with its DAML state machine,
// live working-day countdowns, and outcome recording.
import { useCallback, useEffect, useState } from 'react';
import { ConfirmModal } from '../ui/RationaleModal';
import {
  DAML_STATUS_LABELS, SarInfo, StatusChip, calendarDaysUntil,
  fmtDate, fmtDateTime, mlroGet, mlroSend, workingDaysUntil,
} from './mlro';

function DamlCountdown({ sar }: { sar: SarInfo }) {
  if (sar.daml_status === 'awaiting_consent') {
    const wd = workingDaysUntil(sar.consent_deadline);
    const urgent = wd < 2;
    return (
      <span className={`text-xs font-semibold tabular-nums ${urgent ? 'text-red-700' : 'text-amber-700'}`}>
        {wd < 0
          ? 'Notice period ended — check the portal'
          : `${wd} working day${wd === 1 ? '' : 's'} to ${fmtDate(sar.consent_deadline)}`}
      </span>
    );
  }
  if (sar.daml_status === 'consent_refused_moratorium') {
    const cd = calendarDaysUntil(sar.moratorium_end);
    return (
      <span className="text-xs font-semibold tabular-nums text-red-700">
        {cd > 0 ? `Moratorium: ${cd} day${cd === 1 ? '' : 's'} to ${fmtDate(sar.moratorium_end)}` : 'Moratorium period has ended'}
      </span>
    );
  }
  return null;
}

export default function SarsTab({ onChanged }: { onChanged: () => void }) {
  const [sars, setSars] = useState<SarInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<{ sarId: number; status: string; label: string } | null>(null);
  const [, setTick] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await mlroGet<SarInfo[]>('/mlro/sars');
      setSars(rows);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'Failed to load SAR records.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 60_000);
    return () => clearInterval(t);
  }, []);

  const recordOutcome = async () => {
    if (!pending) return;
    await mlroSend(`/mlro/sars/${pending.sarId}/daml-outcome`, 'POST', { status: pending.status });
    setPending(null);
    load();
    onChanged();
  };

  return (
    <div className="space-y-4">
      <div className="rounded border border-zinc-200 bg-zinc-50 px-4 py-3 text-xs text-zinc-600 leading-snug">
        SARs are filed by a person on the <span className="font-semibold">NCA SAR Portal</span> — this
        platform prepares and records; it does not submit. DAML consent: 7 working days notice from
        filing, then a 31-calendar-day moratorium if refused. Work on the matter must not proceed while
        awaiting consent or during an active moratorium.
      </div>

      {error && <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="bg-white border border-zinc-200 rounded-md overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-10">
            <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-600" />
          </div>
        ) : sars.length === 0 ? (
          <div className="px-6 py-8 text-center text-sm text-zinc-500">
            No SARs recorded. Record filings from a report's detail drawer once decided.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 border-b border-zinc-200">
                <tr>
                  {['NCA reference', 'Matter', 'Filed', 'DAML status', 'Clock', 'Actions'].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {sars.map((s) => (
                  <tr key={s.id} className="hover:bg-zinc-50">
                    <td className="px-4 py-2.5 font-mono text-zinc-800">{s.sar_reference || `#${s.id}`}</td>
                    <td className="px-4 py-2.5 text-zinc-700">{s.matter_reference || '—'}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-zinc-700">
                      {fmtDateTime(s.filed_at)}
                      <span className="block text-xs text-zinc-400">by {s.filed_by_name || '—'}</span>
                    </td>
                    <td className="px-4 py-2.5"><StatusChip status={s.daml_status} map={DAML_STATUS_LABELS} /></td>
                    <td className="px-4 py-2.5"><DamlCountdown sar={s} /></td>
                    <td className="px-4 py-2.5">
                      {s.daml_status === 'awaiting_consent' && (
                        <div className="flex gap-2">
                          <button type="button"
                            onClick={() => setPending({ sarId: s.id, status: 'consent_granted', label: 'record that the NCA has granted DAML consent — work on the matter may proceed' })}
                            className="px-2.5 py-1 text-xs font-semibold rounded bg-green-700 text-white hover:bg-green-800">
                            Consent granted
                          </button>
                          <button type="button"
                            onClick={() => setPending({ sarId: s.id, status: 'consent_refused_moratorium', label: 'record that the NCA has refused consent — the 31-calendar-day moratorium starts now and work must not proceed' })}
                            className="px-2.5 py-1 text-xs font-semibold rounded bg-red-700 text-white hover:bg-red-800">
                            Refused — start moratorium
                          </button>
                        </div>
                      )}
                      {s.daml_status === 'consent_refused_moratorium' && calendarDaysUntil(s.moratorium_end) <= 0 && (
                        <button type="button"
                          onClick={() => setPending({ sarId: s.id, status: 'moratorium_expired', label: 'mark the 31-day moratorium as expired — work on the matter may resume' })}
                          className="px-2.5 py-1 text-xs font-semibold rounded border border-zinc-300 text-zinc-700 hover:bg-zinc-50">
                          Mark moratorium expired
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmModal
        isOpen={pending !== null}
        title="Record DAML outcome"
        message={pending ? `You are about to ${pending.label}. This is recorded in the audit trail.` : ''}
        confirmLabel="Record outcome"
        destructive={pending?.status === 'consent_refused_moratorium'}
        onConfirm={recordOutcome}
        onClose={() => setPending(null)}
      />
    </div>
  );
}
