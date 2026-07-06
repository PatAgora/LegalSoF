// Policy repository — versioned list with approve flow and per-user
// acknowledgement tracking (who has / hasn't acknowledged).
import { useCallback, useEffect, useState } from 'react';
import Modal from '../ui/Modal';
import { ConfirmModal } from '../ui/RationaleModal';
import { PolicyInfo, fmtDate, mlroGet, mlroSend } from './mlro';

const POLICY_STATUS: Record<string, { label: string; cls: string }> = {
  draft: { label: 'Draft', cls: 'bg-zinc-100 text-zinc-600 ring-zinc-300' },
  approved: { label: 'Approved', cls: 'bg-green-50 text-green-700 ring-green-200' },
  superseded: { label: 'Superseded', cls: 'bg-amber-50 text-amber-600 ring-amber-200' },
};

function NewPolicyModal({ isOpen, onClose, onDone }: { isOpen: boolean; onClose: () => void; onDone: () => void }) {
  const [title, setTitle] = useState('');
  const [version, setVersion] = useState('');
  const [contentNote, setContentNote] = useState('');
  const [reviewDue, setReviewDue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setTitle(''); setVersion(''); setContentNote(''); setReviewDue('');
      setError(null); setSubmitting(false);
    }
  }, [isOpen]);

  const canSave = title.trim().length >= 2 && version.trim().length >= 1;

  const save = async () => {
    if (!canSave) return;
    setSubmitting(true);
    setError(null);
    try {
      await mlroSend('/mlro/policies', 'POST', {
        title: title.trim(),
        version: version.trim(),
        content_note: contentNote.trim() || null,
        review_due: reviewDue ? new Date(reviewDue).toISOString() : null,
      });
      onDone();
    } catch (e: any) {
      setError(e?.message || 'Failed to create the policy.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={submitting ? () => {} : onClose} title="New policy version" size="lg"
      footer={
        <>
          <button type="button" onClick={onClose} disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-zinc-600 bg-white border border-zinc-200 rounded hover:bg-zinc-50 disabled:opacity-50">
            Cancel
          </button>
          <button type="button" onClick={save} disabled={submitting || !canSave}
            className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed">
            {submitting ? 'Saving…' : 'Create draft'}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-xs text-zinc-500">
          Created as a draft. Approving it later supersedes any earlier approved version with the same title.
        </p>
        <div>
          <label className="block text-xs font-semibold text-zinc-600 mb-1">Title</label>
          <input type="text" value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Firm-wide AML Policy"
            className="w-full border border-zinc-200 rounded px-3 py-2 text-sm" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-zinc-600 mb-1">Version</label>
            <input type="text" value={version} onChange={(e) => setVersion(e.target.value)}
              placeholder="e.g. 3.1"
              className="w-full border border-zinc-200 rounded px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-zinc-600 mb-1">Review due (optional)</label>
            <input type="date" value={reviewDue} onChange={(e) => setReviewDue(e.target.value)}
              className="w-full border border-zinc-200 rounded px-3 py-2 text-sm" />
          </div>
        </div>
        <div>
          <label className="block text-xs font-semibold text-zinc-600 mb-1">Summary / document location</label>
          <textarea value={contentNote} onChange={(e) => setContentNote(e.target.value)} rows={3}
            placeholder="Summary of the policy and where the full document lives (DMS ref, intranet link…)"
            className="w-full border border-zinc-200 rounded px-3 py-2 text-sm" />
        </div>
        {error && <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>}
      </div>
    </Modal>
  );
}

export default function PoliciesTab({ onChanged }: { onChanged: () => void }) {
  const [policies, setPolicies] = useState<PolicyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [approving, setApproving] = useState<PolicyInfo | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await mlroGet<PolicyInfo[]>('/mlro/policies');
      setPolicies(rows);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'Failed to load policies.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const approve = async () => {
    if (!approving) return;
    await mlroSend(`/mlro/policies/${approving.id}/approve`, 'POST');
    setApproving(null);
    load();
    onChanged();
  };

  const acknowledge = async (id: number) => {
    try {
      await mlroSend(`/mlro/policies/${id}/acknowledge`, 'POST');
      load();
    } catch (e: any) {
      setError(e?.message || 'Failed to acknowledge the policy.');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500">
          Versioned AML policies and procedures (MLR 2017 reg 19) with staff acknowledgement tracking.
        </p>
        <button type="button" onClick={() => setCreating(true)}
          className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800">
          New policy version
        </button>
      </div>

      {error && <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="space-y-3">
        {loading ? (
          <div className="flex justify-center py-10">
            <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-600" />
          </div>
        ) : policies.length === 0 ? (
          <div className="bg-white border border-zinc-200 rounded-md px-6 py-8 text-center text-sm text-zinc-500">
            No policies recorded yet.
          </div>
        ) : (
          policies.map((p) => {
            const st = POLICY_STATUS[p.status] || POLICY_STATUS.draft;
            const overdue = p.status === 'approved' && p.review_due && new Date(p.review_due) < new Date();
            return (
              <div key={p.id} className="bg-white border border-zinc-200 rounded-md">
                <div className="px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-zinc-900 truncate">
                      {p.title} <span className="text-zinc-400 font-normal">v{p.version}</span>
                    </p>
                    <p className="text-xs text-zinc-500">
                      {p.approved_at ? `Approved ${fmtDate(p.approved_at)} by ${p.approved_by_name || '—'}` : 'Not yet approved'}
                      {p.review_due && (
                        <span className={overdue ? 'text-red-600 font-semibold' : ''}>
                          {' '}· review due {fmtDate(p.review_due)}{overdue ? ' (overdue)' : ''}
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-semibold ring-1 ring-inset ${st.cls}`}>
                      {st.label}
                    </span>
                    {p.status === 'draft' && (
                      <button type="button" onClick={() => setApproving(p)}
                        className="px-2.5 py-1 text-xs font-semibold rounded bg-green-700 text-white hover:bg-green-800">
                        Approve
                      </button>
                    )}
                    {p.status === 'approved' && !p.acknowledged_by_me && (
                      <button type="button" onClick={() => acknowledge(p.id)}
                        className="px-2.5 py-1 text-xs font-semibold rounded border border-zinc-300 text-zinc-700 hover:bg-zinc-50">
                        Acknowledge
                      </button>
                    )}
                    {p.acknowledgements && (
                      <button type="button" onClick={() => setExpanded(expanded === p.id ? null : p.id)}
                        className="px-2.5 py-1 text-xs text-zinc-500 hover:text-zinc-800">
                        {p.acknowledgement_count} ack{p.acknowledgement_count === 1 ? '' : 's'} {expanded === p.id ? '▴' : '▾'}
                      </button>
                    )}
                  </div>
                </div>
                {p.content_note && (
                  <div className="px-4 pb-3 text-xs text-zinc-600 whitespace-pre-wrap">{p.content_note}</div>
                )}
                {expanded === p.id && p.acknowledgements && (
                  <div className="border-t border-zinc-100 px-4 py-3 grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    <div>
                      <p className="font-semibold text-green-700 mb-1">
                        Acknowledged ({p.acknowledgements.length})
                      </p>
                      {p.acknowledgements.length === 0 ? (
                        <p className="text-zinc-400">Nobody yet.</p>
                      ) : (
                        <ul className="space-y-0.5">
                          {p.acknowledgements.map((a) => (
                            <li key={a.user_id} className="text-zinc-600">
                              {a.user_name || `User #${a.user_id}`}
                              <span className="text-zinc-400"> — {fmtDate(a.acknowledged_at)}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <div>
                      <p className="font-semibold text-amber-700 mb-1">
                        Not acknowledged ({p.not_acknowledged?.length ?? 0})
                      </p>
                      {(p.not_acknowledged?.length ?? 0) === 0 ? (
                        <p className="text-zinc-400">Everyone has acknowledged.</p>
                      ) : (
                        <ul className="space-y-0.5">
                          {p.not_acknowledged!.map((u) => (
                            <li key={u.user_id} className="text-zinc-600">{u.user_name || `User #${u.user_id}`}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <NewPolicyModal isOpen={creating} onClose={() => setCreating(false)}
        onDone={() => { setCreating(false); load(); onChanged(); }} />

      <ConfirmModal
        isOpen={approving !== null}
        title="Approve policy"
        message={approving ? `Approve "${approving.title}" v${approving.version}? Any earlier approved version with the same title will be marked superseded.` : ''}
        confirmLabel="Approve"
        onConfirm={approve}
        onClose={() => setApproving(null)}
      />
    </div>
  );
}
