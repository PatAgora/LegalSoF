import { useState, useMemo, useEffect } from 'react';
import { Dialog } from '@headlessui/react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import PDFViewer, { scrollPDFToPage } from './PDFViewer';
import { translateFlag } from './flagTranslations';
import { API_BASE_URL, authFetch, getAccessToken } from '../../lib/api';
import { StatusChip, Button } from '../ui';
import { RationaleModal } from '../ui/RationaleModal';
import { showToast } from '../../lib/toast';
import { formatDateTime } from '../../lib/format';

interface VerificationData {
  id: number;
  matter_id: number;
  filename: string;
  disk_filename?: string;
  file_category?: string;
  authenticity_score: number;
  verdict: string;
  verification_phase?: string;
  structural_pipeline_score?: number;
  statement_pipeline_score?: number;
  identified_bank_template?: string;
  admin_override?: boolean;
  admin_override_by?: string | null;
  admin_override_rationale?: string | null;
  admin_override_at?: string | null;
  flags: Array<{
    id?: number;
    code: string;
    severity: string;
    message: string;
    pipeline_stage: string;
    details?: Record<string, any>;
  }>;
}

interface Props {
  verification: VerificationData;
  isOpen: boolean;
  onClose: () => void;
  onAccepted?: (updated: VerificationData) => void;
}

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

interface TransactionRow {
  id: number;
  date?: string;
  description?: string;
  amount?: number;
  direction?: string;
  balance?: number;
  transaction_type?: string;
}

interface AuditEntry {
  id: number;
  action?: string;
  description?: string;
  timestamp?: string;
  user?: string;
  details?: Record<string, any>;
}

type SeverityFilter = 'all' | 'critical' | 'high' | 'medium' | 'low';

export default function DocumentVerificationModal({ verification: incoming, isOpen, onClose, onAccepted }: Props) {
  const [verification, setVerification] = useState<VerificationData>(incoming);
  useEffect(() => { setVerification(incoming); }, [incoming]);
  const [activeFlagIdx, setActiveFlagIdx] = useState<number | null>(null);
  const [highlightPages, setHighlightPages] = useState<number[]>([]);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [downloadingPack, setDownloadingPack] = useState(false);
  const [showAcceptModal, setShowAcceptModal] = useState(false);

  const acceptVerification = async (rationale: string) => {
    const r = await authFetch(
      `${API_BASE_URL}/api/v1/matters/${verification.matter_id}/document-verifications/${verification.id}/accept`,
      {
        method: 'POST',
        body: JSON.stringify({
          // The backend derives the acting reviewer from the
          // authenticated session; this field carries no identity
          // semantics (kept only because the request schema requires
          // a non-empty value).
          admin_user: 'session',
          rationale,
        }),
      },
    );
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || r.statusText || 'The document could not be accepted.');
    }
    const updated = await r.json();
    setVerification((v) => ({ ...v, ...updated }));
    if (onAccepted) onAccepted({ ...verification, ...updated });
    setShowAcceptModal(false);
  };

  const isPDF = verification.verification_phase !== 'statement_only';
  const fileUrl = verification.disk_filename
    ? `${API_BASE_URL}/api/v1/matters/${verification.matter_id}/documents/${verification.disk_filename}`
    : null;
  const authToken = getAccessToken() || '';

  // Load audit trail + (statement-only) transactions when the modal opens
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await authFetch(
          `${API_BASE_URL}/api/v1/matters/${verification.matter_id}/document-verifications/${verification.id}/audit-trail`
        );
        if (!cancelled && r.ok) setAudit(await r.json());
      } catch {
        /* non-blocking */
      }
      if (!isPDF) {
        try {
          const r = await authFetch(
            `${API_BASE_URL}/api/v1/matters/${verification.matter_id}/document-verifications/${verification.id}/transactions`
          );
          if (!cancelled && r.ok) setTransactions(await r.json());
        } catch {
          /* non-blocking */
        }
      }
    })();
    return () => { cancelled = true; };
  }, [isOpen, verification.id, verification.matter_id, isPDF]);

  // Sort flags by severity, then apply user filter
  const filteredFlags = useMemo(() => {
    const base = [...(verification.flags || [])]
      .filter(f => f.severity !== 'info' && !f.code?.endsWith('_OK') && f.code !== 'FINAL_SCORE' && f.code !== 'NON_PDF_FILE' && f.code !== 'SINGLE_EOF')
      .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 5) - (SEVERITY_ORDER[b.severity] ?? 5));
    if (severityFilter === 'all') return base;
    return base.filter(f => f.severity === severityFilter);
  }, [verification.flags, severityFilter]);

  // Sorted flags (no filter applied) - used for the top-issue hint so it
  // always reflects the truly most important problem.
  const sortedFlags = useMemo(() => {
    return [...(verification.flags || [])]
      .filter(f => f.severity !== 'info' && !f.code?.endsWith('_OK') && f.code !== 'FINAL_SCORE' && f.code !== 'NON_PDF_FILE' && f.code !== 'SINGLE_EOF')
      .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 5) - (SEVERITY_ORDER[b.severity] ?? 5));
  }, [verification.flags]);

  // Severity counts for filter chips
  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = { all: sortedFlags.length, critical: 0, high: 0, medium: 0, low: 0 };
    sortedFlags.forEach(f => {
      if (counts[f.severity] !== undefined) counts[f.severity]++;
    });
    return counts;
  }, [sortedFlags]);

  const handleDownloadEvidencePack = async () => {
    setDownloadingPack(true);
    try {
      const r = await authFetch(
        `${API_BASE_URL}/api/v1/matters/${verification.matter_id}/document-verifications/${verification.id}/evidence-pack.pdf`
      );
      if (!r.ok) {
        showToast('The evidence pack could not be downloaded. Please try again.', 'error');
        return;
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `verification-${verification.id}-evidence-pack.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDownloadingPack(false);
    }
  };

  // Donut chart data
  const score = Math.round(verification.authenticity_score ?? 0);
  const donutData = [
    { name: 'Score', value: score },
    { name: 'Remaining', value: 100 - score },
  ];
  // green-500 / amber-500 / red-500 - match the StatusChip palette.
  const scoreColor = score >= 75 ? '#22c55e' : score >= 45 ? '#f59e0b' : '#ef4444';

  const handleFlagClick = (flag: typeof sortedFlags[0], idx: number) => {
    const pageNumbers = flag.details?.page_numbers;
    if (pageNumbers && Array.isArray(pageNumbers) && pageNumbers.length > 0 && fileUrl) {
      setActiveFlagIdx(idx);
      setHighlightPages(pageNumbers);
      // Scroll to the first affected page
      scrollPDFToPage(fileUrl, pageNumbers[0]);
    } else {
      setActiveFlagIdx(idx === activeFlagIdx ? null : idx);
      setHighlightPages([]);
    }
  };

  const severityConfig = (severity: string) => {
    switch (severity) {
      case 'critical':
        return { dot: 'bg-red-500', bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', label: 'CRITICAL' };
      case 'high':
        return { dot: 'bg-amber-500', bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', label: 'HIGH' };
      case 'medium':
        return { dot: 'bg-zinc-400', bg: 'bg-zinc-50', border: 'border-zinc-200', text: 'text-zinc-900', label: 'MEDIUM' };
      default:
        return { dot: 'bg-zinc-400', bg: 'bg-white', border: 'border-zinc-200', text: 'text-zinc-600', label: severity.toUpperCase() };
    }
  };

  // Top-issue action hint - shown above the flag list to point reviewers
  // at the highest-severity flag without needing to scroll.
  const topIssueHint = sortedFlags.length > 0
    ? (() => {
        const top = sortedFlags[0];
        const t = translateFlag(top);
        const action = top.severity === 'critical'
          ? 'Block this document - '
          : top.severity === 'high'
          ? 'Investigate before approving - '
          : 'Worth checking - ';
        return `${action}${t.headline.toLowerCase()}.`;
      })()
    : null;

  // Render flag.details as a small key/value table beneath an active flag.
  // Most callers stash useful diagnostics in details (page_numbers, DPI
  // values, off-by amounts, mismatched fields). page_numbers is already
  // shown as the "Pages" hint, so we hide it here.
  const renderFlagDetails = (details: Record<string, any> | undefined) => {
    if (!details) return null;
    const entries = Object.entries(details).filter(
      ([k]) => k !== 'page_numbers'
    );
    if (entries.length === 0) return null;

    const fmtValue = (v: any): string => {
      if (v === null || v === undefined) return '-';
      if (typeof v === 'boolean') return v ? 'yes' : 'no';
      if (Array.isArray(v)) {
        // Array of primitives → comma-separated. Array of objects → JSON.
        if (v.every(x => typeof x !== 'object' || x === null)) {
          return v.map(x => String(x)).join(', ') || '-';
        }
        return JSON.stringify(v);
      }
      if (typeof v === 'object') return JSON.stringify(v);
      return String(v);
    };

    return (
      <div className="mt-2 rounded border border-zinc-200 bg-white/60 text-[11px]">
        <table className="w-full">
          <tbody>
            {entries.map(([k, v]) => (
              <tr key={k} className="border-b border-zinc-200 last:border-0">
                <td className="px-2 py-1 font-medium text-zinc-600 align-top w-1/3">
                  {k.replace(/_/g, ' ')}
                </td>
                <td className="px-2 py-1 text-zinc-900 break-all">
                  {fmtValue(v)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <Dialog open={isOpen} onClose={onClose} className="relative z-50">
      <div className="fixed inset-0 bg-black/60" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <Dialog.Panel className="w-full h-[90vh] max-w-7xl bg-white rounded-md shadow-2xl flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-zinc-200 bg-slate-50">
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-zinc-900" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <Dialog.Title className="text-sm font-semibold text-zinc-900">
                {verification.filename}
              </Dialog.Title>
              {verification.identified_bank_template && (
                <span className="text-xs text-zinc-600">({verification.identified_bank_template})</span>
              )}
              <StatusChip verdict={verification.verdict} />
            </div>
            <div className="flex items-center gap-2">
              {!verification.admin_override && (
                <button
                  onClick={() => setShowAcceptModal(true)}
                  title="Mark this verification as accepted with a rationale; the action is captured in the audit log."
                  className="px-3.5 py-1.5 text-xs font-semibold rounded-full bg-green-600 text-white hover:bg-green-700 transition-colors"
                >
                  Accept document
                </button>
              )}
              <Button
                variant="secondary"
                size="sm"
                onClick={handleDownloadEvidencePack}
                loading={downloadingPack}
                title="Download a PDF report with verdict, flags and audit trail"
              >
                {downloadingPack ? 'Building…' : 'Download evidence pack'}
              </Button>
              <button
                onClick={onClose}
                className="p-1 rounded hover:bg-zinc-50 text-zinc-400 hover:text-zinc-900 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Acceptance banner - shown when a reviewer has signed off
              this document. Records who, when and why for the audit log. */}
          {verification.admin_override && (
            <div className="px-6 py-3 bg-green-50 border-b border-green-200">
              <div className="flex items-start gap-3">
                <svg className="w-5 h-5 mt-0.5 text-green-700 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div className="text-xs leading-snug text-green-900">
                  <div className="font-semibold tracking-wide">
                    Document accepted by {verification.admin_override_by || 'Reviewer'}
                    {verification.admin_override_at ? ` · ${formatDateTime(verification.admin_override_at)}` : ''}
                  </div>
                  {verification.admin_override_rationale && (
                    <div className="mt-1 italic text-green-800">"{verification.admin_override_rationale}"</div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Body: split layout */}
          <div className="flex-1 flex overflow-hidden">
            {/* Left: PDF viewer OR statement transaction table */}
            <div className={`${isPDF && fileUrl ? 'w-[60%]' : (!isPDF ? 'w-[60%]' : 'hidden')} border-r border-zinc-200 overflow-hidden`}>
              {isPDF && fileUrl && (
                <PDFViewer
                  fileUrl={fileUrl}
                  authToken={authToken}
                  highlightPages={highlightPages}
                />
              )}
              {!isPDF && (
                <div className="h-full overflow-y-auto">
                  <div className="px-4 py-3 border-b border-zinc-200 bg-zinc-50 sticky top-0">
                    <h3 className="text-xs font-semibold text-zinc-900 uppercase tracking-wide">
                      Extracted transactions ({transactions.length})
                    </h3>
                    <p className="text-[11px] text-zinc-400 mt-1">
                      Parsed from the uploaded statement file. Sort order is original document order.
                    </p>
                  </div>
                  {transactions.length === 0 ? (
                    <div className="p-6 text-center text-sm text-zinc-400">
                      No transactions to show.
                    </div>
                  ) : (
                    <table className="w-full text-xs">
                      <thead className="bg-zinc-50 text-zinc-600 sticky top-[58px]">
                        <tr>
                          <th className="px-2 py-2 text-left font-semibold">Date</th>
                          <th className="px-2 py-2 text-left font-semibold">Description</th>
                          <th className="px-2 py-2 text-right font-semibold">In</th>
                          <th className="px-2 py-2 text-right font-semibold">Out</th>
                          <th className="px-2 py-2 text-right font-semibold">Balance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {transactions.map((t) => {
                          const credit = t.direction === 'credit' || (t.amount ?? 0) > 0;
                          const amt = Math.abs(t.amount ?? 0);
                          return (
                            <tr key={t.id} className="border-b border-zinc-200 hover:bg-zinc-50/40">
                              <td className="px-2 py-1.5 whitespace-nowrap text-zinc-600">{t.date || '-'}</td>
                              <td className="px-2 py-1.5 text-zinc-900">{t.description || ''}</td>
                              <td className="px-2 py-1.5 text-right tabular-nums text-green-700">
                                {credit && amt ? amt.toFixed(2) : ''}
                              </td>
                              <td className="px-2 py-1.5 text-right tabular-nums text-red-700">
                                {!credit && amt ? amt.toFixed(2) : ''}
                              </td>
                              <td className="px-2 py-1.5 text-right tabular-nums text-zinc-900">
                                {t.balance != null ? t.balance.toFixed(2) : ''}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>

            {/* Right: Score + Checks */}
            <div className={`${(isPDF && fileUrl) || !isPDF ? 'w-[40%]' : 'w-full'} flex flex-col overflow-hidden`}>
              {/* Donut Score */}
              <div className="px-6 py-4 border-b border-zinc-200 flex items-center gap-6">
                <div className="w-24 h-24 flex-shrink-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={donutData}
                        cx="50%"
                        cy="50%"
                        innerRadius={28}
                        outerRadius={40}
                        startAngle={90}
                        endAngle={-270}
                        dataKey="value"
                        stroke="none"
                      >
                        <Cell fill={scoreColor} />
                        <Cell fill="#e5e7eb" />
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="text-center -mt-[58px]">
                    <span className="text-lg font-bold text-zinc-900">{score}</span>
                    <span className="text-[10px] text-zinc-400 block -mt-1">/100</span>
                  </div>
                </div>
                <div>
                  <div className="text-sm font-semibold text-zinc-900">Authenticity Score</div>
                  <div className="text-xs text-zinc-600 mt-1">
                    {score >= 75 ? 'Document appears authentic' : score >= 45 ? 'Issues found requiring review' : 'Significant concerns identified'}
                  </div>
                  <div className="flex gap-2 mt-2">
                    {verification.structural_pipeline_score != null && (
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                        verification.structural_pipeline_score >= 75 ? 'bg-[#86efac]/40 text-green-800' :
                        verification.structural_pipeline_score >= 45 ? 'bg-[#fcd34d]/40 text-amber-800' :
                        'bg-[#fca5a5]/40 text-red-800'
                      }`}>
                        Structure: {Math.round(verification.structural_pipeline_score)}
                      </span>
                    )}
                    {verification.statement_pipeline_score != null && (
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                        verification.statement_pipeline_score >= 75 ? 'bg-[#86efac]/40 text-green-800' :
                        verification.statement_pipeline_score >= 45 ? 'bg-[#fcd34d]/40 text-amber-800' :
                        'bg-[#fca5a5]/40 text-red-800'
                      }`}>
                        Statement: {Math.round(verification.statement_pipeline_score)}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Flags list */}
              <div className="flex-1 overflow-y-auto px-6 py-4">
                <div className="text-xs font-semibold text-zinc-900 uppercase tracking-wide mb-3">
                  Verification Checks ({sortedFlags.length} issue{sortedFlags.length !== 1 ? 's' : ''})
                </div>
                {topIssueHint && (
                  <div className="mb-3 px-3 py-2 rounded border border-zinc-200 bg-zinc-50 text-xs text-zinc-900">
                    <span className="font-semibold">Next step:</span> {topIssueHint}
                  </div>
                )}
                {sortedFlags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-3">
                    {(['all', 'critical', 'high', 'medium', 'low'] as SeverityFilter[]).map((sev) => {
                      const isActive = severityFilter === sev;
                      const count = severityCounts[sev] || 0;
                      const baseClass = 'px-2 py-0.5 text-[10px] font-semibold rounded-full border transition-colors';
                      const activeClass = isActive
                        ? 'bg-zinc-900 text-white border-zinc-900'
                        : 'bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-50';
                      return (
                        <button
                          key={sev}
                          onClick={() => setSeverityFilter(sev)}
                          disabled={count === 0 && sev !== 'all'}
                          className={`${baseClass} ${activeClass} disabled:opacity-30 disabled:cursor-not-allowed`}
                        >
                          {sev === 'all' ? 'All' : sev.charAt(0).toUpperCase() + sev.slice(1)} ({count})
                        </button>
                      );
                    })}
                  </div>
                )}
                {sortedFlags.length === 0 ? (
                  <div className="text-center py-8">
                    <svg className="w-10 h-10 text-green-400 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-sm text-zinc-600">All checks passed. No issues detected.</p>
                  </div>
                ) : filteredFlags.length === 0 ? (
                  <div className="text-center py-6 text-xs text-zinc-400">
                    No {severityFilter} flags. Clear the filter to see all {sortedFlags.length}.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {filteredFlags.map((flag, idx) => {
                      const sc = severityConfig(flag.severity);
                      const t = translateFlag(flag);
                      const hasPageData = flag.details?.page_numbers && Array.isArray(flag.details.page_numbers) && flag.details.page_numbers.length > 0;
                      const isActive = activeFlagIdx === idx;

                      return (
                        <button
                          key={idx}
                          onClick={() => handleFlagClick(flag, idx)}
                          className={`w-full text-left rounded-md border p-3 transition-all ${sc.bg} ${sc.border} ${
                            isActive ? 'ring-2 ring-zinc-400 ring-offset-1' : ''
                          } ${hasPageData ? 'cursor-pointer hover:shadow-md' : 'cursor-default'}`}
                        >
                          <div className="flex items-start gap-2">
                            <span className={`mt-1.5 flex-shrink-0 w-1.5 h-1.5 rounded-full ${sc.dot}`} />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className={`text-sm font-semibold ${sc.text}`}>{t.headline}</span>
                                <span className={`text-[9px] font-bold px-1 py-0.5 rounded ${sc.bg} ${sc.text} border ${sc.border}`}>
                                  {sc.label}
                                </span>
                              </div>
                              <div className="text-xs text-zinc-600 mt-0.5 leading-relaxed">{t.explanation}</div>
                              {hasPageData && (
                                <div className="mt-1.5 flex items-center gap-1 text-[10px] text-zinc-700 font-medium">
                                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                  </svg>
                                  Pages: {flag.details!.page_numbers.map((p: number) => p + 1).join(', ')} - click to view
                                </div>
                              )}
                              {isActive && renderFlagDetails(flag.details)}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Audit trail */}
              <div className="border-t border-zinc-200 bg-zinc-50/40 px-6 py-3 max-h-48 overflow-y-auto">
                <div className="text-xs font-semibold text-zinc-900 uppercase tracking-wide mb-2">
                  Audit trail ({audit.length})
                </div>
                {audit.length === 0 ? (
                  <p className="text-[11px] text-zinc-400">No audit entries yet for this verification.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {audit.map((e) => (
                      <li key={e.id} className="text-[11px] text-zinc-600">
                        <span className="font-mono text-zinc-400">
                          {e.timestamp ? formatDateTime(e.timestamp) : ''}
                        </span>
                        {' · '}
                        <span className="font-semibold text-zinc-900">{e.action || 'event'}</span>
                        {e.user && <span className="text-zinc-400"> by {e.user}</span>}
                        {e.description && (
                          <div className="ml-2 text-zinc-600 mt-0.5">{e.description}</div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        </Dialog.Panel>
      </div>

      <RationaleModal
        isOpen={showAcceptModal}
        title={`Accept "${verification.filename}"`}
        description="Add a rationale for accepting this document. Required - please include enough detail for the audit log."
        confirmLabel="Accept document"
        onConfirm={acceptVerification}
        onClose={() => setShowAcceptModal(false)}
      />
    </Dialog>
  );
}
