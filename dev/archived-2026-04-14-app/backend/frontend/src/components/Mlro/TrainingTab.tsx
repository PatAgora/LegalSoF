// AML training register (MLR 2017 reg 24) — table + add-record modal.
import { useCallback, useEffect, useState } from 'react';
import Modal from '../ui/Modal';
import { API_BASE_URL, authFetch } from '../../lib/api';
import { TrainingRecordInfo, fmtDate, mlroGet, mlroSend } from './mlro';

interface UserOption { id: number; full_name: string; email: string }

function AddTrainingModal({ isOpen, onClose, onDone }: { isOpen: boolean; onClose: () => void; onDone: () => void }) {
  const [userOptions, setUserOptions] = useState<UserOption[]>([]);
  const [userId, setUserId] = useState('');
  const [courseName, setCourseName] = useState('');
  const [provider, setProvider] = useState('');
  const [completedAt, setCompletedAt] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [certificateNote, setCertificateNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setUserId(''); setCourseName(''); setProvider(''); setCompletedAt('');
    setExpiresAt(''); setCertificateNote(''); setError(null); setSubmitting(false);
    (async () => {
      try {
        const r = await authFetch(`${API_BASE_URL}/api/v1/users`);
        if (r.ok) setUserOptions(await r.json());
      } catch { /* picker degrades to empty */ }
    })();
  }, [isOpen]);

  const canSave = userId !== '' && courseName.trim().length >= 2 && completedAt !== '';

  const save = async () => {
    if (!canSave) return;
    setSubmitting(true);
    setError(null);
    try {
      await mlroSend('/mlro/training', 'POST', {
        user_id: Number(userId),
        course_name: courseName.trim(),
        provider: provider.trim() || null,
        completed_at: new Date(completedAt).toISOString(),
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
        certificate_note: certificateNote.trim() || null,
      });
      onDone();
    } catch (e: any) {
      setError(e?.message || 'Failed to save the training record.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={submitting ? () => {} : onClose} title="Add training record" size="lg"
      footer={
        <>
          <button type="button" onClick={onClose} disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-zinc-600 bg-white border border-zinc-200 rounded hover:bg-zinc-50 disabled:opacity-50">
            Cancel
          </button>
          <button type="button" onClick={save} disabled={submitting || !canSave}
            className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed">
            {submitting ? 'Saving…' : 'Add record'}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-semibold text-zinc-600 mb-1">Staff member</label>
          <select value={userId} onChange={(e) => setUserId(e.target.value)}
            className="w-full border border-zinc-200 rounded px-3 py-2 text-sm bg-white">
            <option value="">Select…</option>
            {userOptions.map((u) => <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-zinc-600 mb-1">Course name</label>
          <input type="text" value={courseName} onChange={(e) => setCourseName(e.target.value)}
            placeholder="e.g. AML Annual Refresher"
            className="w-full border border-zinc-200 rounded px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="block text-xs font-semibold text-zinc-600 mb-1">Provider (optional)</label>
          <input type="text" value={provider} onChange={(e) => setProvider(e.target.value)}
            className="w-full border border-zinc-200 rounded px-3 py-2 text-sm" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-zinc-600 mb-1">Completed on</label>
            <input type="date" value={completedAt} onChange={(e) => setCompletedAt(e.target.value)}
              className="w-full border border-zinc-200 rounded px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-zinc-600 mb-1">Expires (optional)</label>
            <input type="date" value={expiresAt} onChange={(e) => setExpiresAt(e.target.value)}
              className="w-full border border-zinc-200 rounded px-3 py-2 text-sm" />
          </div>
        </div>
        <div>
          <label className="block text-xs font-semibold text-zinc-600 mb-1">Certificate note (optional)</label>
          <input type="text" value={certificateNote} onChange={(e) => setCertificateNote(e.target.value)}
            placeholder="Certificate reference or storage location"
            className="w-full border border-zinc-200 rounded px-3 py-2 text-sm" />
        </div>
        {error && <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>}
      </div>
    </Modal>
  );
}

function expiryBadge(expiresAt: string | null): JSX.Element {
  if (!expiresAt) return <span className="text-xs text-zinc-400">No expiry</span>;
  const days = Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 86400000);
  if (days < 0) return <span className="text-xs font-semibold text-red-700">Expired</span>;
  if (days <= 60) return <span className="text-xs font-semibold text-amber-700">Expires in {days}d</span>;
  return <span className="text-xs text-green-700">Valid</span>;
}

export default function TrainingTab({ onChanged }: { onChanged: () => void }) {
  const [records, setRecords] = useState<TrainingRecordInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await mlroGet<TrainingRecordInfo[]>('/mlro/training');
      setRecords(rows);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'Failed to load training records.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (id: number) => {
    try {
      await mlroSend(`/mlro/training/${id}`, 'DELETE');
      load();
      onChanged();
    } catch (e: any) {
      setError(e?.message || 'Failed to delete the record.');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500">AML training register (MLR 2017 reg 24).</p>
        <button type="button" onClick={() => setAdding(true)}
          className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800">
          Add record
        </button>
      </div>

      {error && <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

      <div className="bg-white border border-zinc-200 rounded-md overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-10">
            <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-zinc-600" />
          </div>
        ) : records.length === 0 ? (
          <div className="px-6 py-8 text-center text-sm text-zinc-500">No training records yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 border-b border-zinc-200">
                <tr>
                  {['Staff member', 'Course', 'Provider', 'Completed', 'Expiry', '', ''].map((h, i) => (
                    <th key={i} className="px-4 py-2.5 text-left text-xs font-semibold text-zinc-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {records.map((t) => (
                  <tr key={t.id} className="hover:bg-zinc-50">
                    <td className="px-4 py-2.5 text-zinc-800">{t.user_name || `User #${t.user_id}`}</td>
                    <td className="px-4 py-2.5 text-zinc-700">{t.course_name}</td>
                    <td className="px-4 py-2.5 text-zinc-500">{t.provider || '—'}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-zinc-700">{fmtDate(t.completed_at)}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap">{expiryBadge(t.expires_at)}</td>
                    <td className="px-4 py-2.5 text-zinc-500 max-w-xs truncate">{t.certificate_note || ''}</td>
                    <td className="px-4 py-2.5 text-right">
                      <button type="button" onClick={() => remove(t.id)}
                        className="text-xs text-red-600 hover:text-red-800 hover:underline">
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <AddTrainingModal isOpen={adding} onClose={() => setAdding(false)}
        onDone={() => { setAdding(false); load(); onChanged(); }} />
    </div>
  );
}
