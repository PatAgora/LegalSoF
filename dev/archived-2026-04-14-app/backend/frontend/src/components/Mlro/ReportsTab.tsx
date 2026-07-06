// MLRO reports queue → detail drawer with the decide flow and SAR
// recording form.
//
// Legal notes surfaced in this UI:
//  * LSAG 11.7 — BOTH outcomes (SAR / no SAR) require a documented
//    rationale of at least 30 characters.
//  * SAR filing is HUMAN-ONLY via the NCA SAR Portal — the platform
//    prepares and records; it never submits.
//  * Everything in this tab is MLRO-only. The reporter and client team
//    never see report status (POCA s.333A tipping off).
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Modal from '../ui/Modal';
import {
  DAML_STATUS_LABELS, MlroReportDetail, MlroReportSummary,
  REPORT_STATUS_LABELS, StatusChip, fmtDateTime, mlroGet, mlroSend,
} from './mlro';

// ---------------------------------------------------------------------------
// Decision modal — RationaleModal pattern extended with the privilege
// section. Both outcomes route through here and both demand rationale.
// ---------------------------------------------------------------------------

function DecisionModal({
  isOpen, outcome, reportId, onClose, onDone,
}: {
  isOpen: boolean;
  outcome: 'sar' | 'no_sar';
  reportId: number | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const MIN = 30;
  const [rationale, setRationale] = useState('');
  const [privilegeConsidered, setPrivilegeConsidered] = useState(false);
  const [privilegeNotes, setPrivilegeNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setRationale('');
      setPrivilegeConsidered(false);
      setPrivilegeNotes('');
      setError(null);
      setSubmitting(false);
    }
  }, [isOpen, outcome, reportId]);

  const confirm = async () => {
    if (reportId == null) return;
    const trimmed = rationale.trim();
    if (trimmed.length < MIN) {
      setError(`Please enter at least ${MIN} characters of rationale (LSAG 11.7).`);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await mlroSend(`/mlro/reports/${reportId}/decide`, 'POST', {
        outcome,
        rationale: trimmed,
        privilege_considered: privilegeConsidered,
        privilege_notes: privilegeNotes.trim() || null,
      });
      onDone();
    } catch (e: any) {
      setError(e?.message || 'The request failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={submitting ? () => {} : onClose}
      title={outcome === 'sar' ? 'Decision: file a SAR' : 'Decision: no SAR to be filed'}
      size="lg"
      footer={
        <>
          <button type="button" onClick={onClose} disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-zinc-600 bg-white border border-zinc-200 rounded hover:bg-zinc-50 disabled:opacity-50">
            Cancel
          </button>
          <button type="button" onClick={confirm}
            disabled={submitting || rationale.trim().length < MIN}
            className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed">
            {submitting ? 'Recording…' : 'Record decision'}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-sm text-zinc-600 leading-snug">
          {outcome === 'sar'
            ? 'Record the decision to file. The SAR itself must then be filed by a person on the NCA SAR Portal and recorded against this report.'
            : 'LSAG ch.11 requires the decision NOT to file to be documented as thoroughly as a decision to file.'}
        </p>
        <div>
          <div className="flex items-baseline justify-between mb-1">
            <label className="block text-xs font-semibold text-zinc-600">
              Decision rationale (required, min {MIN} characters)
            </label>
            <span className={`text-[10px] font-medium ${rationale.trim().length >= MIN ? 'text-green-700' : 'text-zinc-400'}`}>
              {rationale.trim().length} / {MIN} min
            </span>
          </div>
          <textarea
            autoFocus value={rationale} onChange={(e) => setRationale(e.target.value)} rows={4}
            placeholder="What was considered, what information it was weighed against, and why this outcome…"
            className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
        </div>
        <div className="border border-zinc-200 rounded p-3 space-y-2 bg-zinc-50/50">
          <label className="flex items-center gap-2 text-sm text-zinc-700">
            <input type="checkbox" checked={privilegeConsidered}
              onChange={(e) => setPrivilegeConsidered(e.target.checked)}
              className="rounded border-zinc-300" />
            Legal professional privilege has been considered
          </label>
          <textarea
            value={privilegeNotes} onChange={(e) => setPrivilegeNotes(e.target.value)} rows={2}
            placeholder="Privilege analysis — does any of the information attract LPP / the s.330(6) defence?"
            className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
          />
        </div>
        {error && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>
        )}
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// SAR recording form (inside the drawer)
// ---------------------------------------------------------------------------

function SarRecordingForm({ reportId, onDone }: { reportId: number; onDone: () => void }) {
  const [sarReference, setSarReference] = useState('');
  const [damlRequested, setDamlRequested] = useState(false);
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (sarReference.trim().length < 3) {
      setError('Enter the NCA-issued SAR reference.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await mlroSend(`/mlro/reports/${reportId}/sar`, 'POST', {
        sar_reference: sarReference.trim(),
        daml_requested: damlRequested,
        notes: notes.trim() || null,
      });
      onDone();
    } catch (e: any) {
      setError(e?.message || 'Failed to record the SAR filing.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="border border-purple-200 rounded-md p-4 space-y-3 bg-purple-50/40">
      <h4 className="text-sm font-bold text-zinc-900">Record SAR filing</h4>
      <p className="text-xs text-zinc-600 leading-snug">
        <span className="font-semibold">File via the NCA SAR Portal</span> — this platform prepares
        and records; it does not submit. Enter the NCA-issued reference after filing.
      </p>
      <div>
        <label className="block text-xs font-semibold text-zinc-600 mb-1">NCA SAR reference</label>
        <input type="text" value={sarReference} onChange={(e) => setSarReference(e.target.value)}
          placeholder="e.g. 0000-0000000000"
          className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300" />
      </div>
      <label className="flex items-start gap-2 text-sm text-zinc-700">
        <input type="checkbox" checked={damlRequested} onChange={(e) => setDamlRequested(e.target.checked)}
          className="mt-0.5 rounded border-zinc-300" />
        <span>
          DAML consent requested with this SAR
          <span className="block text-xs text-zinc-500">
            Starts the 7-working-day notice period. Work on the matter must not proceed while awaiting consent.
          </span>
        </span>
      </label>
      <div>
        <label className="block text-xs font-semibold text-zinc-600 mb-1">Notes (optional)</label>
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2}
          className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300" />
      </div>
      {error && <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>}
      <button type="button" onClick={submit} disabled={submitting || sarReference.trim().length < 3}
        className="px-4 py-2 text-sm font-semibold rounded bg-purple-700 text-white hover:bg-purple-800 disabled:opacity-50 disabled:cursor-not-allowed">
        {submitting ? 'Recording…' : 'Record SAR filing'}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail drawer
// ---------------------------------------------------------------------------

function ContextSection({ context }: { context: Record<string, unknown[]> }) {
  const entries = Object.entries(context || {}).filter(([, v]) => Array.isArray(v));
  if (entries.length === 0) {
    return <p className="text-xs text-zinc-500">No firm-held records found for this matter (or the report is not matter-linked).</p>;
  }
  return (
    <div className="space-y-2">
      {entries.map(([key, rows]) => (
        <div key={key} className="border border-zinc-200 rounded p-2.5">
          <p className="text-xs font-semibold text-zinc-600 mb-1">
            {key.replace(/_/g, ' ')} <span className="text-zinc-400">({rows.length})</span>
          </p>
          {rows.length === 0 ? (
            <p className="text-xs text-zinc-400">None recorded.</p>
          ) : (
            <ul className="space-y-0.5">
              {rows.slice(0, 8).map((row, i) => (
                <li key={i} className="text-xs text-zinc-600 font-mono truncate">
                  {JSON.stringify(row)}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

function ReportDrawer({
  reportId, onClose, onChanged,
}: {
  reportId: number | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [detail, setDetail] = useState<MlroReportDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState<'sar' | 'no_sar' | null>(null);

  const load = useCallback(async () => {
    if (reportId == null) return;
    try {
      const d = await mlroGet<MlroReportDetail>(`/mlro/reports/${reportId}`);
      setDetail(d);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'Failed to load the report.');
    }
  }, [reportId]);

  useEffect(() => {
    setDetail(null);
    load();
  }, [load]);

  if (reportId == null) return null;

  const decided = detail?.status === 'sar_filed' || detail?.status === 'no_sar_decision';
  const decisionToFileRecorded = !!detail?.decision_rationale && detail.status !== 'no_sar_decision';

  return (
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} aria-hidden="true" />
      <div className="absolute right-0 top-0 h-full w-full max-w-2xl bg-white shadow-xl border-l border-zinc-200 flex flex-col">
        <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-200 bg-zinc-50">
          <h3 className="text-sm font-bold text-zinc-900">
            Internal report #{reportId}
            <span className="ml-2 font-normal text-zinc-500">MLRO only — never visible to the client team</span>
          </h3>
          <button onClick={onClose} className="p-1 rounded text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100" aria-label="Close">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {error && <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
          {!detail && !error && (
            <div className="flex justify-center py-10">
              <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-600" />
            </div>
          )}
          {detail && (
            <>
              <div className="flex items-center justify-between">
                <StatusChip status={detail.status} map={REPORT_STATUS_LABELS} />
                <span className="text-xs text-zinc-500">Submitted {fmtDateTime(detail.submitted_at)} by {detail.reporter_name || 'unknown'}</span>
              </div>

              <div>
                <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Subject</p>
                <p className="text-sm text-zinc-800">{detail.subject_summary || '—'}</p>
              </div>

              <div>
                <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Suspicion details</p>
                <p className="text-sm text-zinc-800 whitespace-pre-wrap border border-zinc-200 rounded p-3 bg-zinc-50/50">
                  {detail.suspicion_details}
                </p>
              </div>

              <div>
                <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Matter</p>
                {detail.matter_id ? (
                  <Link to={`/matters/${detail.matter_id}`} className="text-sm text-blue-700 hover:underline">
                    {detail.matter_reference || `Matter #${detail.matter_id}`} →
                  </Link>
                ) : (
                  <p className="text-sm text-zinc-500">Not linked to a matter (client-level suspicion).</p>
                )}
              </div>

              <div>
                <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">
                  Firm-held context (reg 21(5) — weigh against all information held)
                </p>
                <ContextSection context={detail.matter_context} />
              </div>

              <div>
                <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Privilege</p>
                <p className="text-sm text-zinc-700">
                  {detail.privilege_considered ? 'Privilege considered.' : 'Privilege not yet considered.'}
                  {detail.privilege_notes ? ` — ${detail.privilege_notes}` : ''}
                </p>
              </div>

              {detail.decision_rationale && (
                <div>
                  <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Decision (LSAG 11.7)</p>
                  <p className="text-sm text-zinc-800 whitespace-pre-wrap border border-zinc-200 rounded p-3 bg-green-50/40">
                    {detail.decision_rationale}
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">
                    Decided {fmtDateTime(detail.decided_at)} by {detail.decided_by_name || '—'}
                  </p>
                </div>
              )}

              {!decided && (
                <div className="flex gap-3 border-t border-zinc-200 pt-4">
                  <button type="button" onClick={() => setDecision('sar')}
                    className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800">
                    Decide: file a SAR
                  </button>
                  <button type="button" onClick={() => setDecision('no_sar')}
                    className="px-4 py-2 text-sm font-semibold rounded border border-zinc-300 text-zinc-700 hover:bg-zinc-50">
                    Decide: no SAR (document rationale)
                  </button>
                </div>
              )}

              {decisionToFileRecorded && detail.status !== 'sar_filed' && (
                <SarRecordingForm reportId={detail.id} onDone={() => { load(); onChanged(); }} />
              )}

              {detail.sars.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">SAR records</p>
                  <ul className="space-y-2">
                    {detail.sars.map((s) => (
                      <li key={s.id} className="border border-zinc-200 rounded p-3 text-sm flex items-center justify-between">
                        <span className="font-mono text-zinc-800">{s.sar_reference || `SAR #${s.id}`}</span>
                        <StatusChip status={s.daml_status} map={DAML_STATUS_LABELS} />
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <DecisionModal
        isOpen={decision !== null}
        outcome={decision || 'no_sar'}
        reportId={reportId}
        onClose={() => setDecision(null)}
        onDone={() => { setDecision(null); load(); onChanged(); }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Queue
// ---------------------------------------------------------------------------

export default function ReportsTab({ onChanged }: { onChanged: () => void }) {
  const [reports, setReports] = useState<MlroReportSummary[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : '';
      const rows = await mlroGet<MlroReportSummary[]>(`/mlro/reports${qs}`);
      setReports(rows);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'Failed to load reports.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500">
          Internal suspicion reports (POCA s.330). This queue is visible to the MLRO only.
        </p>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-zinc-300 rounded px-2.5 py-1.5 text-sm text-zinc-700 bg-white">
          <option value="">All statuses</option>
          <option value="received">Received</option>
          <option value="under_review">Under review</option>
          <option value="sar_filed">SAR filed</option>
          <option value="no_sar_decision">No SAR decision</option>
        </select>
      </div>

      {error && <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="bg-white border border-zinc-200 rounded-md overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-10">
            <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-600" />
          </div>
        ) : reports.length === 0 ? (
          <div className="px-6 py-8 text-center text-sm text-zinc-500">No internal reports.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 border-b border-zinc-200">
                <tr>
                  {['#', 'Submitted', 'Reporter', 'Matter', 'Subject', 'Status', ''].map((h) => (
                    <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {reports.map((r) => (
                  <tr key={r.id} className="hover:bg-zinc-50 cursor-pointer" onClick={() => setOpenId(r.id)}>
                    <td className="px-4 py-2.5 tabular-nums text-zinc-500">{r.id}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-zinc-700">{fmtDateTime(r.submitted_at)}</td>
                    <td className="px-4 py-2.5 text-zinc-700">{r.reporter_name || '—'}</td>
                    <td className="px-4 py-2.5 text-zinc-700">{r.matter_reference || '—'}</td>
                    <td className="px-4 py-2.5 text-zinc-700 max-w-xs truncate">{r.subject_summary || '—'}</td>
                    <td className="px-4 py-2.5"><StatusChip status={r.status} map={REPORT_STATUS_LABELS} /></td>
                    <td className="px-4 py-2.5 text-right text-zinc-400">→</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ReportDrawer
        reportId={openId}
        onClose={() => { setOpenId(null); load(); }}
        onChanged={() => { load(); onChanged(); }}
      />
    </div>
  );
}
