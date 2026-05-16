import { useState, useEffect } from 'react';
import { API_BASE_URL, authFetch } from '../../lib/api';
import DocumentVerificationModal from './DocumentVerificationModal';

interface VerificationData {
  id: number;
  matter_id: number;
  filename: string;
  disk_filename?: string;
  file_category?: string;
  authenticity_score: number;
  verdict: string;
  verification_phase?: string;
  verification_method?: string;
  structural_pipeline_score?: number;
  statement_pipeline_score?: number;
  identified_bank_template?: string;
  created_at?: string;
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
  matterId: number;
}

export default function DocumentVerificationPage({ matterId }: Props) {
  const [verifications, setVerifications] = useState<VerificationData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedVerification, setSelectedVerification] = useState<VerificationData | null>(null);

  useEffect(() => {
    const fetchVerifications = async () => {
      try {
        setLoading(true);
        const response = await authFetch(
          `${API_BASE_URL}/api/v1/matters/${matterId}/document-verifications`
        );
        if (!response.ok) throw new Error('Failed to fetch verifications');
        const data = await response.json();
        setVerifications(data);
      } catch (err) {
        console.error('Error fetching verifications:', err);
        setError('Failed to load document verifications.');
      } finally {
        setLoading(false);
      }
    };

    if (matterId) fetchVerifications();
  }, [matterId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
          <p className="mt-2 text-sm text-brand-ink-secondary">Loading verifications...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-status-danger-50 border border-status-danger-200 rounded-card p-6 text-center">
        <p className="text-sm text-status-danger-700">{error}</p>
      </div>
    );
  }

  if (verifications.length === 0) {
    return (
      <div className="bg-white border border-brand-muted rounded-card p-8 text-center">
        <svg className="w-12 h-12 text-brand-ink-tertiary mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-sm text-brand-ink-secondary">No documents have been verified yet.</p>
        <p className="text-xs text-brand-ink-tertiary mt-1">Upload documents in the SoF Assessment tab to run verification.</p>
      </div>
    );
  }

  const verdictConfig = (verdict: string) => {
    switch (verdict) {
      case 'Verified':
        return { label: 'VERIFIED', bgClass: 'bg-status-success-200', textClass: 'text-status-success-900', borderClass: 'border-status-success-200', cardBg: 'bg-white' };
      case 'Suspicious':
        return { label: 'SUSPICIOUS — REVIEW', bgClass: 'bg-status-warning-200', textClass: 'text-status-warning-900', borderClass: 'border-status-warning-200', cardBg: 'bg-white' };
      case 'LikelyTampered':
        return { label: 'LIKELY TAMPERED', bgClass: 'bg-status-danger-200', textClass: 'text-status-danger-900', borderClass: 'border-status-danger-200', cardBg: 'bg-white' };
      default:
        return { label: verdict, bgClass: 'bg-brand-surface-alt', textClass: 'text-brand-ink', borderClass: 'border-brand-muted', cardBg: 'bg-white' };
    }
  };

  const fileIcon = (v: VerificationData) => {
    const isPDF = v.verification_phase !== 'statement_only';
    if (isPDF) {
      return (
        <div className="w-10 h-10 rounded-lg bg-status-danger-100 flex items-center justify-center flex-shrink-0">
          <svg className="w-5 h-5 text-status-danger-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        </div>
      );
    }
    return (
      <div className="w-10 h-10 rounded-lg bg-status-success-100 flex items-center justify-center flex-shrink-0">
        <svg className="w-5 h-5 text-status-success-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0112 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M13.125 12h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125M20.625 12c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5M12 14.625v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 14.625c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125m0 0v1.5c0 .621-.504 1.125-1.125 1.125" />
        </svg>
      </div>
    );
  };

  // Summary counts
  const verified = verifications.filter(v => v.verdict === 'Verified').length;
  const suspicious = verifications.filter(v => v.verdict === 'Suspicious').length;
  const tampered = verifications.filter(v => v.verdict === 'LikelyTampered').length;

  return (
    <div className="space-y-6">
      {/* Summary header */}
      <div className="bg-white border border-brand-muted rounded-card p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <svg className="w-5 h-5 text-primary-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            <span className="text-sm font-semibold text-brand-ink">Document Verification</span>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="text-brand-ink-secondary">{verifications.length} document{verifications.length !== 1 ? 's' : ''}</span>
            {verified > 0 && <span className="text-status-success-700 font-medium">{verified} passed</span>}
            {suspicious > 0 && <span className="text-status-warning-700 font-medium">{suspicious} review</span>}
            {tampered > 0 && <span className="text-status-danger-700 font-medium">{tampered} failed</span>}
          </div>
        </div>
      </div>

      {/* Card Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {verifications.map((v) => {
          const vc = verdictConfig(v.verdict);
          const score = Math.round(v.authenticity_score ?? 0);
          const actionableFlags = (v.flags || []).filter(
            (f) => f.severity !== 'info' && !f.code?.endsWith('_OK') && f.code !== 'FINAL_SCORE' && f.code !== 'NON_PDF_FILE' && f.code !== 'SINGLE_EOF'
          );

          return (
            <button
              key={v.id}
              onClick={() => setSelectedVerification(v)}
              className={`${vc.cardBg} border ${vc.borderClass} rounded-card p-4 text-left hover:shadow-lg transition-shadow group cursor-pointer`}
            >
              {/* File icon + name */}
              <div className="flex items-start gap-3 mb-3">
                {fileIcon(v)}
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-brand-ink truncate group-hover:text-primary-700 transition-colors">
                    {v.filename}
                  </div>
                  <div className="text-[10px] text-brand-ink-tertiary mt-0.5">
                    {v.file_category?.replace(/_/g, ' ') || (v.verification_phase === 'statement_only' ? 'CSV Statement' : 'PDF Document')}
                  </div>
                </div>
              </div>

              {/* Score + flags summary */}
              <div className="flex items-center justify-between mb-3">
                <span className={`text-xs font-bold px-2 py-0.5 rounded-badge ${
                  score >= 75 ? 'bg-status-success-200 text-status-success-900' :
                  score >= 45 ? 'bg-status-warning-200 text-status-warning-900' :
                  'bg-status-danger-200 text-status-danger-900'
                }`}>
                  {score}/100
                </span>
                {actionableFlags.length > 0 && (
                  <span className="text-[10px] text-brand-ink-tertiary">
                    {actionableFlags.length} issue{actionableFlags.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>

              {/* Verdict badge */}
              <div className={`text-center py-1.5 rounded-badge text-xs font-bold ${vc.bgClass} ${vc.textClass}`}>
                {vc.label}
              </div>
            </button>
          );
        })}
      </div>

      {/* Modal */}
      {selectedVerification && (
        <DocumentVerificationModal
          verification={selectedVerification}
          isOpen={!!selectedVerification}
          onClose={() => setSelectedVerification(null)}
        />
      )}
    </div>
  );
}
