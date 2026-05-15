import { useState, useMemo } from 'react';
import { Dialog } from '@headlessui/react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import PDFViewer, { scrollPDFToPage } from './PDFViewer';
import { translateFlag } from './flagTranslations';
import { API_BASE_URL } from '../../lib/api';

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
}

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

export default function DocumentVerificationModal({ verification, isOpen, onClose }: Props) {
  const [activeFlagIdx, setActiveFlagIdx] = useState<number | null>(null);
  const [highlightPages, setHighlightPages] = useState<number[]>([]);

  const isPDF = verification.verification_phase !== 'statement_only';
  const fileUrl = verification.disk_filename
    ? `${API_BASE_URL}/api/v1/matters/${verification.matter_id}/documents/${verification.disk_filename}`
    : null;
  const authToken = localStorage.getItem('access_token') || '';

  // Sort flags by severity
  const sortedFlags = useMemo(() => {
    return [...(verification.flags || [])]
      .filter(f => f.severity !== 'info' && !f.code?.endsWith('_OK') && f.code !== 'FINAL_SCORE' && f.code !== 'NON_PDF_FILE' && f.code !== 'SINGLE_EOF')
      .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 5) - (SEVERITY_ORDER[b.severity] ?? 5));
  }, [verification.flags]);

  // Donut chart data
  const score = Math.round(verification.authenticity_score ?? 0);
  const donutData = [
    { name: 'Score', value: score },
    { name: 'Remaining', value: 100 - score },
  ];
  const scoreColor = score >= 75 ? '#22c55e' : score >= 45 ? '#eab308' : '#ef4444';

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
        return { dot: 'bg-status-danger-500', bg: 'bg-status-danger-50', border: 'border-status-danger-200', text: 'text-status-danger-700', label: 'CRITICAL' };
      case 'high':
        return { dot: 'bg-status-warning-500', bg: 'bg-status-warning-50', border: 'border-status-warning-200', text: 'text-status-warning-700', label: 'HIGH' };
      case 'medium':
        return { dot: 'bg-brand-ink-tertiary', bg: 'bg-brand-surface-alt', border: 'border-brand-muted', text: 'text-brand-ink', label: 'MEDIUM' };
      default:
        return { dot: 'bg-brand-ink-tertiary', bg: 'bg-white', border: 'border-brand-muted', text: 'text-brand-ink-secondary', label: severity.toUpperCase() };
    }
  };

  const verdictLabel = verification.verdict === 'Verified' ? 'VERIFIED'
    : verification.verdict === 'Suspicious' ? 'NEEDS REVIEW'
    : verification.verdict === 'LikelyTampered' ? 'FAILED'
    : verification.verdict;

  const verdictColor = verification.verdict === 'Verified' ? 'bg-status-success-200 text-status-success-900'
    : verification.verdict === 'Suspicious' ? 'bg-status-warning-200 text-status-warning-900'
    : 'bg-status-danger-200 text-status-danger-900';

  return (
    <Dialog open={isOpen} onClose={onClose} className="relative z-50">
      <div className="fixed inset-0 bg-black/60" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <Dialog.Panel className="w-full h-[90vh] max-w-7xl bg-white rounded-card shadow-2xl flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-3 border-b border-brand-muted bg-brand-surface">
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-primary-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <Dialog.Title className="text-sm font-semibold text-brand-ink">
                {verification.filename}
              </Dialog.Title>
              {verification.identified_bank_template && (
                <span className="text-xs text-brand-ink-secondary">({verification.identified_bank_template})</span>
              )}
              <span className={`px-2 py-0.5 text-xs font-bold rounded-badge ${verdictColor}`}>
                {verdictLabel}
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-brand-surface-alt text-brand-ink-tertiary hover:text-brand-ink transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Body: split layout */}
          <div className="flex-1 flex overflow-hidden">
            {/* Left: PDF Viewer (or placeholder) */}
            <div className={`${isPDF && fileUrl ? 'w-[60%]' : 'hidden'} border-r border-brand-muted overflow-hidden`}>
              {isPDF && fileUrl && (
                <PDFViewer
                  fileUrl={fileUrl}
                  authToken={authToken}
                  highlightPages={highlightPages}
                />
              )}
            </div>

            {/* Right: Score + Checks */}
            <div className={`${isPDF && fileUrl ? 'w-[40%]' : 'w-full'} flex flex-col overflow-hidden`}>
              {/* Donut Score */}
              <div className="px-6 py-4 border-b border-brand-muted flex items-center gap-6">
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
                    <span className="text-lg font-bold text-brand-ink">{score}</span>
                    <span className="text-[10px] text-brand-ink-tertiary block -mt-1">/100</span>
                  </div>
                </div>
                <div>
                  <div className="text-sm font-semibold text-brand-ink">Authenticity Score</div>
                  <div className="text-xs text-brand-ink-secondary mt-1">
                    {score >= 75 ? 'Document appears authentic' : score >= 45 ? 'Issues found requiring review' : 'Significant concerns identified'}
                  </div>
                  <div className="flex gap-2 mt-2">
                    {verification.structural_pipeline_score != null && (
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-badge ${
                        verification.structural_pipeline_score >= 75 ? 'bg-[#86efac]/40 text-green-800' :
                        verification.structural_pipeline_score >= 45 ? 'bg-[#fcd34d]/40 text-amber-800' :
                        'bg-[#fca5a5]/40 text-red-800'
                      }`}>
                        Structure: {Math.round(verification.structural_pipeline_score)}
                      </span>
                    )}
                    {verification.statement_pipeline_score != null && (
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-badge ${
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
                <div className="text-xs font-semibold text-brand-ink uppercase tracking-wide mb-3">
                  Verification Checks ({sortedFlags.length} issue{sortedFlags.length !== 1 ? 's' : ''})
                </div>
                {sortedFlags.length === 0 ? (
                  <div className="text-center py-8">
                    <svg className="w-10 h-10 text-status-success-400 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-sm text-brand-ink-secondary">All checks passed. No issues detected.</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {sortedFlags.map((flag, idx) => {
                      const sc = severityConfig(flag.severity);
                      const t = translateFlag(flag);
                      const hasPageData = flag.details?.page_numbers && Array.isArray(flag.details.page_numbers) && flag.details.page_numbers.length > 0;
                      const isActive = activeFlagIdx === idx;

                      return (
                        <button
                          key={idx}
                          onClick={() => handleFlagClick(flag, idx)}
                          className={`w-full text-left rounded-card border p-3 transition-all ${sc.bg} ${sc.border} ${
                            isActive ? 'ring-2 ring-primary-400 ring-offset-1' : ''
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
                              <div className="text-xs text-brand-ink-secondary mt-0.5 leading-relaxed">{t.explanation}</div>
                              {hasPageData && (
                                <div className="mt-1.5 flex items-center gap-1 text-[10px] text-primary-600 font-medium">
                                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                  </svg>
                                  Pages: {flag.details!.page_numbers.map((p: number) => p + 1).join(', ')} — click to view
                                </div>
                              )}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </Dialog.Panel>
      </div>
    </Dialog>
  );
}
