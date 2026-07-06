// ReportSuspicionButton — mountable on ANY page (matter detail, layout,
// dashboards) to let ANY authenticated user file an internal suspicion
// report with the MLRO (POCA 2002 s.330).
//
// After submission the reporter sees a receipt only — never the status
// or outcome (POCA 2002 s.333A tipping off). The confirmation message
// makes the confidentiality duty explicit.
//
// Not mounted anywhere by this module — the integration pass wires it
// into the pages that need it. Pass matterId to pre-link the report to
// a matter; omit it for client-level suspicion.
import { useEffect, useState } from 'react';
import Modal from '../ui/Modal';
import { mlroSend } from './mlro';

interface ReportSuspicionButtonProps {
  matterId?: number;
  matterReference?: string;
  // Optional styling override for the trigger button.
  className?: string;
}

export default function ReportSuspicionButton({
  matterId, matterReference, className,
}: ReportSuspicionButtonProps) {
  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState('');
  const [details, setDetails] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [receipt, setReceipt] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setSubject('');
      setDetails('');
      setError(null);
      setSubmitting(false);
      setReceipt(null);
    }
  }, [open]);

  const canSubmit = subject.trim().length >= 3 && details.trim().length >= 10;

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const r = await mlroSend<{ id: number; message: string }>('/mlro/internal-reports', 'POST', {
        matter_id: matterId ?? null,
        subject_summary: subject.trim(),
        suspicion_details: details.trim(),
      });
      setReceipt(r.message);
    } catch (e: any) {
      setError(e?.message || 'Failed to submit the report. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={className || 'px-3 py-1.5 text-xs font-semibold rounded border border-red-300 text-red-700 hover:bg-red-50 transition-colors'}
      >
        Report suspicion to MLRO
      </button>

      <Modal
        isOpen={open}
        onClose={submitting ? () => {} : () => setOpen(false)}
        title="Report suspicion to the MLRO"
        size="lg"
        footer={
          receipt ? (
            <button type="button" onClick={() => setOpen(false)}
              className="px-4 py-2 text-sm font-semibold rounded bg-zinc-900 text-white hover:bg-zinc-800">
              Close
            </button>
          ) : (
            <>
              <button type="button" onClick={() => setOpen(false)} disabled={submitting}
                className="px-4 py-2 text-sm font-medium text-zinc-600 bg-white border border-zinc-200 rounded hover:bg-zinc-50 disabled:opacity-50">
                Cancel
              </button>
              <button type="button" onClick={submit} disabled={submitting || !canSubmit}
                className="px-4 py-2 text-sm font-semibold rounded bg-red-700 text-white hover:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed">
                {submitting ? 'Submitting…' : 'Submit report'}
              </button>
            </>
          )
        }
      >
        {receipt ? (
          <div className="space-y-3">
            <div className="rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">
              {receipt}
            </div>
            <p className="text-xs text-zinc-500 leading-snug">
              Disclosing that a report has been made may amount to tipping off
              (POCA 2002 s.333A), which is a criminal offence.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-zinc-600 leading-snug">
              If you know or suspect money laundering you must report it to the
              nominated officer (POCA 2002 s.330). Your report goes to the MLRO
              only. You will not be told what happens next, and you must not
              discuss it with the client or colleagues.
            </p>
            {matterId != null && (
              <p className="text-xs text-zinc-500">
                This report will be linked to matter{' '}
                <span className="font-semibold">{matterReference || `#${matterId}`}</span>.
              </p>
            )}
            <div>
              <label className="block text-xs font-semibold text-zinc-600 mb-1">Subject (who/what the concern is about)</label>
              <input
                type="text" value={subject} onChange={(e) => setSubject(e.target.value)}
                placeholder="e.g. Third-party payment from an unrelated overseas company"
                className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-600 mb-1">What you know or suspect, and why</label>
              <textarea
                value={details} onChange={(e) => setDetails(e.target.value)} rows={5}
                placeholder="Set out the facts, the source of your knowledge, and why it gives rise to suspicion…"
                className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
              />
            </div>
            {error && (
              <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>
            )}
          </div>
        )}
      </Modal>
    </>
  );
}
