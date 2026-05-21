import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { API_BASE_URL, authFetch } from '../../lib/api';
import { translateFlag } from '../DocumentVerification/flagTranslations';
import { FileUploader, StatusChip } from '../ui';
import { useAuthStore } from '../../stores/authStore';

// Helper to format dates as dd/mm/yyyy
const formatDate = (dateStr: string | undefined): string => {
  if (!dateStr) return 'Unknown date';
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    const day = date.getDate().toString().padStart(2, '0');
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
  } catch {
    return dateStr;
  }
};

interface UploadedFile {
  filename: string;
  category: string;
  file_type: string;
  uploaded_at: string;
  records_count: number;
}

interface AssessmentStatus {
  matter_id: number;
  status: string;
  uploaded_files: UploadedFile[];
  files_summary?: {
    client_info: string;
    bank_statements_count: number;
    supporting_docs_count: number;
  };
  ready_for_assessment: boolean;
  last_updated: string | null;
}

interface AssessmentOutcome {
  status: 'sufficient' | 'borderline' | 'insufficient';
  confidence: number;
  rationale: string;
}

interface FundsLineageData {
  exists: boolean;
  summary?: {
    totalAmount: number;
    tracedAmount: number;
    untracedAmount: number;
    matchedTransfers: number;
    externalOrigins: number;
    requiresEvidence: number;
    accumulationPeriodDays: number;
    ambiguousAccounts?: number;
    circularReferences?: number;
  };
  unresolved_items?: Array<{
    date: string;
    amount: number;
    description: string;
    account: string;
    reason?: string;
    severity?: string;
    message?: string;
  }>;
  ambiguous_accounts?: Array<{
    account_id: string;
    classified_as: string;
    confidence: string;
    transaction_count: number;
  }>;
  run_at?: string;
}

interface AssessmentResult {
  client_info?: {
    client_name?: string;
    client_risk_rating?: string;
    business_sector?: string;
    is_pep?: boolean;
  };
  purchase?: {
    amount?: number;
    currency?: string;
    description?: string;
    expected_payment_date?: string;
  };
  claims: any[];
  evidence_matches: any[];
  funding_paths: any[];
  red_flags: any[];
  // Per-claim reviewer / compliance actions, keyed by claim index.
  claim_actions?: Record<string, any>;
  // The matter's compliance review status (none | in_review | cleared | returned).
  matter_compliance_status?: string;
  // Module master switches from the Configuration page. A results tile
  // is hidden entirely when its module is switched off.
  sections_enabled?: {
    document_verification: boolean;
    transaction_review: boolean;
    funds_lineage: boolean;
  };
  // The fee earner's Evidence Checklist tick-offs, persisted on the
  // matter. claim_evidence maps a claim index to the suggested-evidence
  // lines ticked; transaction_alerts is the list of alert keys ticked.
  evidence_checklist?: {
    claim_evidence?: Record<string, string[]>;
    transaction_alerts?: string[];
  };
  document_verification?: {
    overall_verification_rate: number;
    missing_documents: string[];
    verifications: any[];
  };
  validation_summary?: {
    total_statements: number;
    trusted?: number;
    trusted_count?: number;
    review_required?: number;
    review_count?: number;
    high_risk?: number;
    high_risk_count?: number;
    statements?: any[];
    validations?: any[];
    average_score?: number;
    has_blocking_issues?: boolean;
  };
  transaction_review_summary: {
    total_alerts: number;
    critical_alerts: number;
    high_alerts: number;
    medium_alerts: number;
    key_concerns: string[];
  };
  outcome: AssessmentOutcome;
  next_actions: {
    questions: string[];
    documents: string[];
  };
  file_note_summary: string;
}

interface SoFAssessmentProps {
  matterId: number;
}

// Render the numbered list of files already uploaded for one category
// inside a tile body. Used by the bank-statement and supporting-doc
// accordion bodies so reviewers can see what's there before deciding
// whether to add another file.
function renderUploadedList(
  status: any,
  verificationResults: Record<string, { verdict: string; score?: number }>,
  category: 'client_info' | 'bank_statement' | 'supporting_doc',
  emptyCopy: string,
  onDelete?: (filename: string) => void,
  onDownload?: (filename: string) => void,
) {
  const files: Array<{ filename: string; category: string; records_count?: number }> =
    (status?.uploaded_files ?? []).filter((f: any) => f.category === category);

  if (files.length === 0) {
    return <p className="mb-4 text-xs text-zinc-400">{emptyCopy}</p>;
  }

  const verdictBadge = (verdict?: string) => {
    if (!verdict) return null;
    if (verdict === 'Verified')
      return <span className="text-[10px] font-semibold tracking-wider px-2 py-0.5 rounded bg-green-50 text-green-700 ring-1 ring-inset ring-green-200">VERIFIED</span>;
    if (verdict === 'Suspicious')
      return <span className="text-[10px] font-semibold tracking-wider px-2 py-0.5 rounded bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200">SUSPICIOUS</span>;
    if (verdict === 'LikelyTampered')
      return <span className="text-[10px] font-semibold tracking-wider px-2 py-0.5 rounded bg-red-50 text-red-700 ring-1 ring-inset ring-red-200">LIKELY TAMPERED</span>;
    return null;
  };

  return (
    <ol className="mb-4 space-y-1.5">
      {files.map((file, idx) => {
        const ver = verificationResults[file.filename];
        return (
          <li key={`${file.filename}-${idx}`} className="flex items-center justify-between gap-3 px-3 py-2 bg-zinc-50 border border-zinc-200 rounded">
            <span className="text-sm text-zinc-800 truncate flex items-baseline gap-2 min-w-0">
              <span className="text-xs text-zinc-400 tabular-nums">{idx + 1}.</span>
              <span className="truncate">{file.filename}</span>
            </span>
            <div className="flex items-center gap-2 flex-shrink-0">
              {verdictBadge(ver?.verdict)}
              {onDownload && (
                <button
                  type="button"
                  onClick={() => onDownload(file.filename)}
                  title="Download this document"
                  className="p-1 text-zinc-400 hover:text-zinc-900 hover:bg-zinc-100 rounded transition-colors"
                  aria-label={`Download ${file.filename}`}
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
                  </svg>
                </button>
              )}
              {onDelete && (
                <button
                  type="button"
                  onClick={() => onDelete(file.filename)}
                  title="Remove this file"
                  className="p-1 text-zinc-400 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
                  aria-label={`Remove ${file.filename}`}
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

// FLAG_TRANSLATIONS and translateFlag imported from shared module above

const SoFAssessment: React.FC<SoFAssessmentProps> = ({ matterId }) => {
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const isAdmin = String(currentUser?.role || '').toLowerCase() === 'admin';
  const [status, setStatus] = useState<AssessmentStatus | null>(null);
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState<{ [key: string]: boolean }>({});
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const [activeStep, setActiveStep] = useState<'upload' | 'results'>('upload');
  const [fundsLineageData, setFundsLineageData] = useState<FundsLineageData | null>(null);
  
  // Client Info input method
  const [clientInfoInputMethod, setClientInfoInputMethod] = useState<'manual' | 'file' | null>(null);
  
  // Manual input form state
  const [manualClientInfo, setManualClientInfo] = useState({
    client_name: '',
    client_risk_rating: 'medium' as 'low' | 'medium' | 'high',
    pep_status: false,
    business_sector: '',
  });
  
  const [manualPurchase, setManualPurchase] = useState({
    amount: '',
    currency: 'GBP',
    expected_payment_date: '',
    description: '',
  });
  
  const [manualSofExplanation, setManualSofExplanation] = useState('');
  
  // Alert management state
  const [alertRationales, setAlertRationales] = useState<{ [key: number]: string }>({});
  const [alertSatisfied, setAlertSatisfied] = useState<{ [key: number]: boolean }>({});

  // Validation summary state (used by assessment run response — now unified with document verification)
  const [validationSummary, setValidationSummary] = useState<any>(null);

  // Document Verification state
  const [docVerificationSummary, setDocVerificationSummary] = useState<any>(null);
  const [docVerOverrideModalOpen, setDocVerOverrideModalOpen] = useState<number | null>(null);
  const [docVerOverrideRationale, setDocVerOverrideRationale] = useState('');
  const [docVerOverrideSubmitting, setDocVerOverrideSubmitting] = useState(false);
  const [fileVerificationResults, setFileVerificationResults] = useState<{ [filename: string]: { verdict: string; score: number; method?: string } }>({});

  // Load funds lineage data.
  //
  // The GET endpoint wraps the payload as
  //   { exists: true, funds_lineage: { summary, unresolved_items, ... } }
  // but the rest of this component reads fields off the top level
  // (fundsLineageData.summary, fundsLineageData.unresolved_items).
  // Flatten on receipt so the tile reflects the real run instead of
  // showing the "No analysis run yet" empty state.
  const loadFundsLineageData = async () => {
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/funds-lineage`);
      if (response.ok) {
        const raw = await response.json();
        if (raw && raw.exists && raw.funds_lineage) {
          setFundsLineageData({
            exists: true,
            ...raw.funds_lineage,
          });
        } else {
          setFundsLineageData(raw);
        }
      }
    } catch (err) {
      console.error('Error loading funds lineage:', err);
    }
  };

  useEffect(() => {
    fetchStatus();
    loadFundsLineageData();
    loadDocVerificationSummary();
  }, [matterId]);

  const fetchStatus = async () => {
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/status`);
      const data = await response.json();
      setStatus(data);
      
      // If assessment completed, fetch results
      if (data.status === 'completed') {
        fetchResults();
      }
    } catch (error) {
      console.error('Error fetching status:', error);
    }
  };

  const fetchResults = async () => {
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/results`);
      const data = await response.json();
      setResult(data.assessment);
      setValidationSummary(data.document_verification_summary || data.statement_validation_summary || null);
      setActiveStep('results');
    } catch (error) {
      console.error('Error fetching results:', error);
    }
    // Also load document verification summary
    loadDocVerificationSummary();
  };

  const loadDocVerificationSummary = async () => {
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/document-verifications/summary`);
      if (response.ok) {
        const data = await response.json();
        if (data.total_documents > 0) {
          setDocVerificationSummary(data);
        }
      }
    } catch (err) {
      console.error('Error loading document verification summary:', err);
    }
  };

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>,
    category: 'client_info' | 'bank_statement' | 'supporting_doc'
  ) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    setUploadingFiles(prev => ({ ...prev, [category]: true }));
    setErrors(prev => ({ ...prev, [category]: '' }));

    const formData = new FormData();
    formData.append('file', file);
    formData.append('file_category', category);

    try {
      const response = await authFetch(
        `${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/upload`,
        {
          method: 'POST',
          body: formData,
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const uploadResult = await response.json();

      // Capture document verification result if present
      if (uploadResult.verification_verdict && uploadResult.filename) {
        setFileVerificationResults(prev => ({
          ...prev,
          [uploadResult.filename]: {
            verdict: uploadResult.verification_verdict,
            score: uploadResult.verification_score,
            method: uploadResult.verification_method,
          },
        }));
      }

      // Auto-populate the manual form when client_info was uploaded as
      // a file. The user can then review / edit / submit. We don't
      // overwrite fields the user has already typed.
      if (category === 'client_info' && uploadResult.parsed_client_info) {
        const p = uploadResult.parsed_client_info;
        const ci = p.client_info || {};
        const pu = p.purchase || {};
        setManualClientInfo(prev => ({
          client_name:        ci.client_name        || prev.client_name,
          client_risk_rating: (['low','medium','high'].includes(ci.client_risk_rating) ? ci.client_risk_rating : prev.client_risk_rating) as 'low' | 'medium' | 'high',
          pep_status:         typeof ci.pep_status === 'boolean' ? ci.pep_status : prev.pep_status,
          business_sector:    ci.business_sector    || prev.business_sector,
        }));
        setManualPurchase(prev => ({
          amount:                 pu.amount != null ? String(pu.amount) : prev.amount,
          currency:               pu.currency               || prev.currency,
          expected_payment_date:  pu.expected_payment_date  || prev.expected_payment_date,
          description:            pu.description            || prev.description,
        }));
        if (p.sof_explanation) {
          // Defensive: backend should always flatten this to a string
          // already, but if a richer object ever leaks through, render
          // it as JSON rather than letting React produce "[object Object]"
          // in the textarea.
          const sofText = typeof p.sof_explanation === 'string'
            ? p.sof_explanation
            : (() => {
                try { return JSON.stringify(p.sof_explanation, null, 2); }
                catch { return String(p.sof_explanation); }
              })();
          setManualSofExplanation(prev => prev || sofText);
        }
        // Show the uploaded-success state, NOT the manual form.
        //
        // The uploaded JSON is already stored on the backend with its
        // full structure intact — including any `sources` array or
        // explicit `claims`. If we flipped to manual mode here the user
        // would re-submit the form, and handleManualSubmit rebuilds the
        // payload with sof_explanation flattened to prose text and no
        // sources/claims — which destroys the structured data and the
        // assessment then finds zero claims. The pre-filled fields
        // above are still kept, so 'View / edit' works if the user
        // explicitly chooses to revise the upload.
        setClientInfoInputMethod(null);
      }

      await fetchStatus();
    } catch (error: any) {
      setErrors(prev => ({ ...prev, [category]: error.message }));
    } finally {
      setUploadingFiles(prev => ({ ...prev, [category]: false }));
    }
  };

  const handleManualSubmit = async () => {
    setUploadingFiles(prev => ({ ...prev, client_info: true }));
    setErrors(prev => ({ ...prev, client_info: '' }));

    try {
      // Validate required fields
      if (!manualClientInfo.client_name) {
        throw new Error('Client name is required');
      }
      if (!manualPurchase.amount || !manualPurchase.currency) {
        throw new Error('Purchase amount and currency are required');
      }
      if (!manualSofExplanation) {
        throw new Error('Source of Funds explanation is required');
      }

      // Create JSON structure
      const clientInfoJson = {
        client_info: {
          client_name: manualClientInfo.client_name,
          client_risk_rating: manualClientInfo.client_risk_rating,
          pep_status: manualClientInfo.pep_status,
          business_sector: manualClientInfo.business_sector || 'Not specified',
        },
        purchase: {
          amount: parseFloat(manualPurchase.amount),
          currency: manualPurchase.currency,
          expected_payment_date: manualPurchase.expected_payment_date || new Date().toISOString().split('T')[0],
          description: manualPurchase.description || 'Business purchase',
        },
        sof_explanation: manualSofExplanation,
        known_documents: [],
        flags: {
          pep: manualClientInfo.pep_status,
          high_risk_jurisdictions: [],
        },
        constraints: {},
      };

      // Convert to JSON blob and upload
      const blob = new Blob([JSON.stringify(clientInfoJson, null, 2)], { type: 'application/json' });
      const file = new File([blob], 'client_info_manual.json', { type: 'application/json' });

      const formData = new FormData();
      formData.append('file', file);
      formData.append('file_category', 'client_info');

      const response = await authFetch(
        `${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/upload`,
        {
          method: 'POST',
          body: formData,
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      await fetchStatus();
      setClientInfoInputMethod(null); // Reset to show success state
    } catch (error: any) {
      setErrors(prev => ({ ...prev, client_info: error.message }));
    } finally {
      setUploadingFiles(prev => ({ ...prev, client_info: false }));
    }
  };

  const runAssessment = async () => {
    setLoading(true);
    setErrors({});

    try {
      const response = await authFetch(
        `${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/run`,
        {
          method: 'POST',
          headers: {
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache'
          }
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        // Handle both string and object error details
        let errorMessage = 'Assessment failed';
        if (errorData.detail) {
          if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail;
          } else if (typeof errorData.detail === 'object') {
            errorMessage = errorData.detail.error || 'Assessment failed';
            // Log full traceback to console for debugging
            if (errorData.detail.traceback) {
              console.error('=== ASSESSMENT ERROR TRACEBACK ===');
              console.error(errorData.detail.traceback);
              console.error('==================================');
              // Add first line of traceback to error message
              const tbLines = errorData.detail.traceback.split('\n').filter((l: string) => l.trim());
              const lastLine = tbLines[tbLines.length - 1] || '';
              errorMessage += ` (${lastLine})`;
            }
          }
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      console.log('Assessment result received:', data.assessment);
      console.log('Evidence matches:', data.assessment.evidence_matches);
      console.log('Funds lineage run:', data.funds_lineage_run);
      console.log('Document verification summary:', data.document_verification_summary);
      setResult(data.assessment);
      setValidationSummary(data.document_verification_summary || data.statement_validation_summary || null);
      setActiveStep('results');
      await fetchStatus();
      
      // Load funds lineage data (may have been auto-run during assessment)
      await loadFundsLineageData();

      // Load document verification summary
      await loadDocVerificationSummary();
    } catch (error: any) {
      setErrors({ assessment: error.message });
    } finally {
      setLoading(false);
    }
  };

  const downloadFileNote = () => {
    window.open(
      `${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/file-note`,
      '_blank'
    );
  };

  // ── Per-claim reviewer / compliance actions ────────────────────
  // Each updates result.claim_actions in place from the endpoint's
  // response so the Evidence Checklist re-renders without a refetch.
  const applyClaimActions = (claimActions: any) => {
    setResult((prev) => (prev ? ({ ...prev, claim_actions: claimActions } as any) : prev));
  };

  const markClaimSufficient = async (claimIndex: number) => {
    if (!confirm('Mark this claim as having sufficient evidence? It will be treated as verified.')) return;
    try {
      const r = await authFetch(
        `${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/claims/${claimIndex}/sufficient-evidence`,
        { method: 'POST' },
      );
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        alert(`Could not update: ${err.detail || r.statusText}`);
        return;
      }
      const data = await r.json();
      applyClaimActions(data.claim_actions);
    } catch (e: any) {
      alert(`Could not update: ${e?.message || 'Unknown error'}`);
    }
  };

  const sendClaimToCompliance = async (claimIndex: number) => {
    const reason = window.prompt(
      'Send this claim to compliance. Give the reason for the referral (required) — '
      + 'the compliance team sees this so they know why it has come to them.',
      '',
    );
    if (reason === null) return;
    if (reason.trim().length < 10) {
      alert('A reason of at least 10 characters is required.');
      return;
    }
    try {
      const r = await authFetch(
        `${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/claims/${claimIndex}/send-to-compliance`,
        { method: 'POST', body: JSON.stringify({ reason: reason.trim() }) },
      );
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        alert(`Could not send: ${err.detail || r.statusText}`);
        return;
      }
      const data = await r.json();
      applyClaimActions(data.claim_actions);
    } catch (e: any) {
      alert(`Could not send: ${e?.message || 'Unknown error'}`);
    }
  };

  const cancelClaimCompliance = async (claimIndex: number) => {
    const rationale = window.prompt(
      'This claim no longer needs compliance review. Give a rationale (required) — it is recorded in the audit trail.',
      '',
    );
    if (rationale === null) return;
    if (rationale.trim().length < 10) {
      alert('A rationale of at least 10 characters is required.');
      return;
    }
    try {
      const r = await authFetch(
        `${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/claims/${claimIndex}/cancel-compliance`,
        { method: 'POST', body: JSON.stringify({ rationale: rationale.trim() }) },
      );
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        alert(`Could not cancel: ${err.detail || r.statusText}`);
        return;
      }
      const data = await r.json();
      applyClaimActions(data.claim_actions);
    } catch (e: any) {
      alert(`Could not cancel: ${e?.message || 'Unknown error'}`);
    }
  };

  // Compliance officer (admin) responds to a referred claim and returns
  // it to the fee earner — the compliance side of the conversation.
  const complianceReturnClaim = async (claimIndex: number) => {
    const response = window.prompt(
      'Return this claim to the fee earner. Give your response (required) — '
      + 'the fee earner sees this so they know what compliance found.',
      '',
    );
    if (response === null) return;
    if (response.trim().length < 10) {
      alert('A response of at least 10 characters is required.');
      return;
    }
    try {
      const r = await authFetch(
        `${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/claims/${claimIndex}/compliance-return`,
        { method: 'POST', body: JSON.stringify({ response: response.trim() }) },
      );
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        alert(`Could not return: ${err.detail || r.statusText}`);
        return;
      }
      const data = await r.json();
      applyClaimActions(data.claim_actions);
    } catch (e: any) {
      alert(`Could not return: ${e?.message || 'Unknown error'}`);
    }
  };

  // ── Evidence Checklist worklist ─────────────────────────────────
  // The fee earner's tick-offs live on result.evidence_checklist and are
  // persisted to the matter so worklist progress survives a refresh.
  const saveChecklist = async (next: { claim_evidence: Record<string, string[]>; transaction_alerts: string[] }) => {
    setResult((prev) => (prev ? ({ ...prev, evidence_checklist: next } as any) : prev));
    try {
      await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/checklist`, {
        method: 'PUT',
        body: JSON.stringify(next),
      });
    } catch {
      /* optimistic — the tick stays and re-syncs on the next results load */
    }
  };

  const toggleClaimEvidence = (claimIdx: number, item: string) => {
    const ec = result?.evidence_checklist || {};
    const claimEvidence: Record<string, string[]> = { ...(ec.claim_evidence || {}) };
    const set = new Set(claimEvidence[String(claimIdx)] || []);
    if (set.has(item)) set.delete(item); else set.add(item);
    claimEvidence[String(claimIdx)] = Array.from(set);
    saveChecklist({ claim_evidence: claimEvidence, transaction_alerts: ec.transaction_alerts || [] });
  };

  const toggleTransactionAlert = (alertKey: string) => {
    const ec = result?.evidence_checklist || {};
    const set = new Set(ec.transaction_alerts || []);
    if (set.has(alertKey)) set.delete(alertKey); else set.add(alertKey);
    saveChecklist({ claim_evidence: ec.claim_evidence || {}, transaction_alerts: Array.from(set) });
  };

  // Remove one uploaded file from this matter. Cleans up storage,
  // DocumentVerification rows, and the file on disk. Triggers a
  // status refresh on success so the uploaded-files list re-renders.
  const deleteUploadedFile = async (
    filename: string,
    category: 'client_info' | 'bank_statement' | 'supporting_doc',
  ) => {
    if (!confirm(`Remove "${filename}"? This will clear it from the assessment.`)) return;

    try {
      const url = `${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/uploaded-file?filename=${encodeURIComponent(filename)}&category=${encodeURIComponent(category)}`;
      const response = await authFetch(url, { method: 'DELETE' });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        alert(`Could not remove file: ${err.detail || response.statusText}`);
        return;
      }
      setFileVerificationResults((prev) => {
        const { [filename]: _, ...rest } = prev;
        return rest;
      });
      // Stale results aren't useful once the inputs change.
      setResult(null);
      await fetchStatus();
    } catch (error: any) {
      console.error('Error deleting file:', error);
      alert(`Could not remove file: ${error?.message || 'Unknown error'}`);
    }
  };

  // Download an uploaded document so another reviewer can see the
  // original file. Fetched through authFetch (an anchor href would have
  // no auth header) and handed to the browser as a download.
  const downloadUploadedFile = async (filename: string) => {
    try {
      const r = await authFetch(
        `${API_BASE_URL}/api/v1/matters/${matterId}/documents/${encodeURIComponent(filename)}`,
      );
      if (!r.ok) {
        alert(`Could not download "${filename}" (HTTP ${r.status}). The original file may not be available.`);
        return;
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(`Could not download: ${e?.message || 'Unknown error'}`);
    }
  };

  const deleteMatter = async () => {
    if (!confirm('This will permanently delete this matter, every uploaded file, and every assessment record. This cannot be undone. Continue?')) {
      return;
    }

    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        alert(`Could not delete matter: ${err.detail || response.statusText}`);
        return;
      }
      navigate('/matters');
    } catch (error: any) {
      console.error('Error deleting matter:', error);
      alert(`Could not delete matter: ${error?.message || 'Unknown error'}`);
    }
  };

  const getStatusColor = (status: string) => {
    // Use cream/tan color to match the screenshot
    return 'bg-zinc-100';
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-red-700';
      case 'HIGH':
        return 'bg-amber-500'; // Warm tan/brown for high severity
      case 'MEDIUM':
        return 'bg-zinc-50'; // Light cream for medium
      default:
        return 'bg-zinc-200';
    }
  };

  const extractFinalAssessmentText = (rationale: string): string[] => {
    // This function is no longer used - we'll build from result data directly
    return [];
  };

  const renderStructuredRationale = (result: AssessmentResult) => {
    // Renders only the Transaction Review section, which genuinely
    // needs the engine's free-text rationale. The Source of Funds
    // Analysis tile is rendered separately and directly from
    // result.claims (see the renderResult body) so it can never be
    // lost to a header-less or malformed rationale. Null-guarded —
    // rationale may be empty on a degraded result.
    const rationale = (result.outcome && result.outcome.rationale) || '';
    const sections = rationale.split('===').filter(s => s.trim());

    return (
      <div className="space-y-6">
        {sections.map((section) => {
          const lines = section.trim().split('\n');
          const title = (lines[0] || '').trim().toUpperCase();
          const content = lines.slice(1).join('\n');
          if (title.includes('TRANSACTION REVIEW')) {
            return renderTransactionReviewSection(content, result);
          }
          // CLIENT INFORMATION / SOURCE OF FUNDS / FINAL ASSESSMENT
          // are handled elsewhere or intentionally not shown here.
          return null;
        })}
      </div>
    );
  };

  const renderClientInfoSection = (content: string) => {
    return (
      <div key="client-info" className="bg-white border border-zinc-200 rounded-md overflow-hidden">
        {/* Header */}
        <div className="bg-zinc-50 border-b border-zinc-200 px-6 py-4">
          <h3 className="text-lg font-bold text-zinc-900">Client Information</h3>
        </div>
        
        {/* Client Details */}
        <div className="px-6 py-4">
          <pre className="whitespace-pre-wrap text-sm text-zinc-900 font-mono">{content}</pre>
        </div>
      </div>
    );
  };

  // Source of Funds Claims — one row per declared claim, with a
  // Pass / Information Required status driven by the evidence the
  // client has provided for that claim.
  const renderSoFSection = (_content: string, result: AssessmentResult) => {
    const claimList = result.claims || [];

    // Claim status is reviewer-driven, one of four states:
    //   verified  — the reviewer pressed "Sufficient Evidence Provided"
    //   sent      — the claim has been sent to compliance
    //   returned  — compliance returned the matter with queries
    //   review    — the default; still under review
    const claimStatus = (idx: number): 'verified' | 'sent' | 'returned' | 'review' => {
      const action = (result.claim_actions || {})[String(idx)] || {};
      if (action.sufficient) return 'verified';
      const comp = action.compliance || {};
      if (comp.state === 'in_review') return 'sent';
      if (comp.state === 'returned') return 'returned';
      return 'review';
    };

    return (
      <details key="sof" className="bg-white border border-zinc-200 rounded-md overflow-hidden group" open>
        {/* Header — clickable summary, chevron rotates when open */}
        <summary className="bg-zinc-50 border-b border-zinc-200 px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-zinc-100 list-none">
          <h3 className="text-lg font-bold text-zinc-900">Source of Funds Claims</h3>
          <svg className="h-4 w-4 text-zinc-400 transition-transform group-open:rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </summary>

        {/* Explicit empty state — a zero-claim result must be loud, not
            an invisible missing tile. */}
        {claimList.length === 0 && (
          <div className="px-6 py-8 text-center">
            <div className="text-sm font-semibold text-amber-700">
              No source-of-funds claims were extracted
            </div>
            <p className="mt-1.5 text-xs text-zinc-500 max-w-md mx-auto">
              The client's explanation could not be resolved into any declared
              source of funds. Check that a Client Info file or explanation was
              provided, then re-run the assessment. Manual review required.
            </p>
          </div>
        )}

        {claimList.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-zinc-200">
              <thead className="bg-zinc-50">
                <tr>
                  <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Claim</th>
                  <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Status</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-zinc-100">
                {claimList.map((claim, idx) => {
                  const status = claimStatus(idx);
                  const sourceLabel = String(claim.source_type || '').replace(/_/g, ' ');
                  const amountStr = `£${Number(claim.expected_amount || 0).toLocaleString()}`;
                  const STATUS_CHIP: Record<string, { label: string; cls: string; dot: string }> = {
                    verified: { label: 'Verified', cls: 'bg-green-50 text-green-700 ring-green-200/80', dot: 'bg-green-500' },
                    sent:     { label: 'Sent to Compliance', cls: 'bg-blue-50 text-blue-700 ring-blue-200/80', dot: 'bg-blue-500' },
                    returned: { label: 'Returned from Compliance', cls: 'bg-red-50 text-red-700 ring-red-200/80', dot: 'bg-red-500' },
                    review:   { label: 'Under Review', cls: 'bg-amber-50 text-amber-700 ring-amber-200/80', dot: 'bg-amber-500' },
                  };
                  const chip = STATUS_CHIP[status];
                  return (
                    <tr key={idx} className="hover:bg-zinc-50/60">
                      <td className="px-5 py-3.5 text-sm text-zinc-900">
                        <span className="font-medium capitalize">{sourceLabel}</span>
                        <span className="ml-2 text-xs text-zinc-500 tabular-nums">{amountStr}</span>
                      </td>
                      <td className="px-5 py-3.5 text-sm whitespace-nowrap">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-xs font-semibold ring-1 ring-inset ${chip.cls}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${chip.dot}`} />{chip.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </details>
    );
  };

  const renderTransactionReviewSection = (content: string, result: AssessmentResult) => {
    // Hidden entirely when the Transaction Review module is switched
    // off on the Configuration page.
    if (result.sections_enabled?.transaction_review === false) return null;
    const overallMatch = content.match(/OVERALL STATUS:([^\n]+)/);
    const overallStatus = overallMatch ? overallMatch[1].trim() : '';

    const hasCritical = overallStatus.includes('CRITICAL') || content.includes('CRITICAL');

    return (
      <details key="tr" id="tile-transaction-review" className="bg-white border border-zinc-200 rounded-md overflow-hidden group">
        <summary className="bg-zinc-50 border-b border-zinc-200 px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-zinc-100 list-none">
          <h3 className="text-lg font-bold text-zinc-900">Transaction Review</h3>
          <svg className="h-4 w-4 text-zinc-400 transition-transform group-open:rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </summary>
        
        {/* Overall Status */}
        <div className={`px-6 py-4 border-b ${hasCritical ? 'bg-red-50 border-red-200' : 'bg-zinc-50 border-zinc-200'}`}>
          <p className={`font-semibold ${hasCritical ? 'text-red-700' : 'text-zinc-900'}`}>
            {overallStatus}
          </p>
        </div>
        
        {/* Alert Stats */}
        {result.transaction_review_summary && result.transaction_review_summary.total_alerts > 0 && (
          <div className="px-6 py-4 border-b border-zinc-200">
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-zinc-100 rounded-md p-3 text-center">
                <div className="text-2xl font-bold text-zinc-900">{result.transaction_review_summary.total_alerts}</div>
                <div className="text-xs text-zinc-600 mt-1">Total Alerts</div>
              </div>
              <div className="bg-red-100 rounded-md p-3 text-center">
                <div className="text-2xl font-bold text-red-700">{result.transaction_review_summary.critical_alerts}</div>
                <div className="text-xs text-red-700 mt-1">Critical</div>
              </div>
              <div className="bg-zinc-200 rounded-md p-3 text-center">
                <div className="text-2xl font-bold text-zinc-900">{result.transaction_review_summary.high_alerts}</div>
                <div className="text-xs text-zinc-600 mt-1">High</div>
              </div>
              <div className="bg-zinc-50 rounded-md p-3 text-center">
                <div className="text-2xl font-bold text-zinc-900">{result.transaction_review_summary.medium_alerts}</div>
                <div className="text-xs text-zinc-600 mt-1">Medium</div>
              </div>
            </div>
          </div>
        )}
        
        {/* Alert Table or No Alerts Message */}
        {result.transaction_review_summary && (result.transaction_review_summary.alerts || result.transaction_review_summary.alert_details) && (result.transaction_review_summary.alerts?.length > 0 || result.transaction_review_summary.alert_details?.length > 0) ? (
          <div className="px-6 py-4">
            <h4 className="text-sm font-bold text-zinc-600 mb-3">Alert Analysis</h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-brand-muted">
                <thead className="bg-zinc-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-600 uppercase tracking-wider">Severity</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-600 uppercase tracking-wider">Issue Identified</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-600 uppercase tracking-wider">Transaction Details</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-600 uppercase tracking-wider">Alert Rationale</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-600 uppercase tracking-wider">Alert Satisfied</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-600 uppercase tracking-wider">Summary</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-brand-muted">
                  {(result.transaction_review_summary.alerts || result.transaction_review_summary.alert_details || []).slice(0, 5).map((alert, idx) => {
                    const severity = alert.severity || 'HIGH';
                    // Handle both flat structure (alerts) and nested structure (alert_details with transaction object)
                    const txn = alert.transaction || alert;
                    const amount = txn.amount || alert.amount;
                    const date = txn.date || alert.date;
                    const narrative = txn.narrative || alert.counterparty || '';
                    
                    return (
                      <tr key={idx} className="hover:bg-zinc-50">
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-bold whitespace-nowrap ${
                            severity === 'CRITICAL' ? 'bg-red-700 text-white' : 'bg-amber-500 text-white'
                          }`}>
                            <span>{severity === 'CRITICAL' ? '🔴' : '🟠'}</span>
                            <span>{severity}</span>
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-zinc-900">
                          {alert.reasons && alert.reasons.length > 0 ? alert.reasons[0] : 'AML concern'}
                          <div className="text-xs text-zinc-400 mt-1">
                            {narrative || 'No description'}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-zinc-900">
                          <div>Amount: £{amount?.toLocaleString('en-GB', {minimumFractionDigits: 2, maximumFractionDigits: 2}) || '0.00'}</div>
                          <div className="text-xs text-zinc-400">Date: {date || 'Unknown'}</div>
                          {narrative && <div className="text-xs text-zinc-400">Details: {narrative}</div>}
                        </td>
                        <td className="px-4 py-3">
                          <textarea
                            value={alertRationales[idx] || ''}
                            onChange={(e) => setAlertRationales({...alertRationales, [idx]: e.target.value})}
                            placeholder="Enter rationale..."
                            className="w-full px-2 py-1 text-sm border border-zinc-200 rounded focus:outline-none focus:ring-2 focus:ring-zinc-500"
                            rows={2}
                          />
                        </td>
                        <td className="px-4 py-3 text-center">
                          <input
                            type="checkbox"
                            checked={alertSatisfied[idx] || false}
                            onChange={(e) => setAlertSatisfied({...alertSatisfied, [idx]: e.target.checked})}
                            className="w-5 h-5 text-zinc-700 border-zinc-200 rounded focus:ring-zinc-500"
                          />
                        </td>
                        <td className="px-4 py-3">
                          {alertSatisfied[idx] ? (
                            <div className="space-y-1">
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-medium whitespace-nowrap bg-green-100 text-green-700">
                                <span>✅</span>
                                <span>SATISFIED</span>
                              </span>
                              <div className="text-xs text-zinc-600">
                                <div>By: Current User</div>
                                <div>Date: {new Date().toLocaleDateString('en-GB')}</div>
                                {alertRationales[idx] && (
                                  <div className="italic mt-1">"{alertRationales[idx].slice(0, 50)}{alertRationales[idx].length > 50 ? '...' : ''}"</div>
                                )}
                              </div>
                            </div>
                          ) : (
                            <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-medium whitespace-nowrap ${
                              severity === 'CRITICAL' ? 'bg-red-100 text-red-700' : 'bg-zinc-100 text-zinc-900'
                            }`}>
                              <span>{severity === 'CRITICAL' ? '❌' : '⚠️'}</span>
                              <span>{severity === 'CRITICAL' ? 'BLOCKS COMPLETION' : 'REQUIRES REVIEW'}</span>
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="px-6 py-8">
            <div className="text-center text-zinc-400">
              <div className="text-4xl mb-2">✓</div>
              <p className="font-medium">No alerts found within transactions</p>
            </div>
          </div>
        )}


      </details>
    );
  };


  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900">Source of Funds Assessment</h2>
        </div>
        <button
          onClick={deleteMatter}
          className="px-4 py-2 text-sm text-red-700 hover:text-red-700 border border-red-200 rounded hover:bg-red-50"
        >
          Delete Matter
        </button>
      </div>

      {/* Step Tabs */}
      <div className="border-b border-zinc-200">
        <div className="flex space-x-8">
          <button
            onClick={() => setActiveStep('upload')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeStep === 'upload'
                ? 'border-zinc-500 text-zinc-700'
                : 'border-transparent text-zinc-400 hover:text-zinc-600 hover:border-zinc-200'
            }`}
          >
            Documents
          </button>
          <button
            onClick={() => setActiveStep('results')}
            disabled={!result}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeStep === 'results'
                ? 'border-zinc-500 text-zinc-700'
                : result
                ? 'border-transparent text-zinc-400 hover:text-zinc-600 hover:border-zinc-200'
                : 'border-transparent text-zinc-400 cursor-not-allowed'
            }`}
          >
            Assessment Results
          </button>
        </div>
      </div>

      {/* Upload Step */}
      {activeStep === 'upload' && (
        <div className="space-y-6">
          {/* Upload tiles — full-width accordion rows. Each tile collapses
              once its category has at least one upload, so reviewers see
              counts at a glance and only expand the section they're
              working on. Uses native <details> for the open/close
              behaviour (no extra state needed). */}
          <div className="space-y-3">
            {/* Client Info — tile #1.
                key includes the uploaded flag so the tile remounts —
                and therefore reliably re-applies its `open` default —
                the moment the category flips to uploaded. React does
                not consistently reconcile the uncontrolled <details
                open> attribute on its own. */}
            <details
              key={`tile-client-${!!(status && status.files_summary && status.files_summary.client_info === 'uploaded')}`}
              className="bg-white border border-zinc-200 rounded-md group"
              open={!(status && status.files_summary && status.files_summary.client_info === 'uploaded')}
            >
              <summary className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-zinc-50/60 list-none">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-sm font-semibold text-zinc-900">Client info</span>
                  <span className="text-xs text-zinc-500">
                    {status && status.files_summary && status.files_summary.client_info === 'uploaded'
                      ? 'Provided'
                      : 'Not provided'}
                  </span>
                </div>
                <svg className="h-4 w-4 text-zinc-400 transition-transform group-open:rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </summary>
              <div className="px-5 pb-5 pt-4 border-t border-zinc-100">
                {/* List of client-info files already provided. The toggle
                    below acts as the "Add document" mechanism. */}
                {renderUploadedList(status, fileVerificationResults, 'client_info', 'No client info provided yet.', (fn) => deleteUploadedFile(fn, 'client_info'), downloadUploadedFile)}
                <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-400 mb-3">Add document</div>
                <div className="text-center">
                  <h3 className="text-lg font-semibold text-zinc-900 mb-2">Client Info</h3>
                
                {/* Branch priority:
                    1. clientInfoInputMethod === 'manual' — the form is
                       open for review/edit (either user clicked Enter
                       Manually, or an uploaded file pre-filled the
                       fields and switched mode). Falls through to the
                       final else branch where the form is rendered.
                    2. Uploaded AND not currently editing — show the
                       success state with a View / Edit button to enter
                       the form.
                    3. Otherwise initial choice / file picker.
                */}
                {clientInfoInputMethod !== 'manual' && status && status.files_summary && status.files_summary.client_info === 'uploaded' ? (
                  <>
                    <div className="mt-3 text-green-700 text-sm font-medium">✓ Uploaded</div>
                    <button
                      onClick={() => setClientInfoInputMethod('manual')}
                      className="mt-2 text-xs text-zinc-700 hover:text-zinc-900 underline"
                    >
                      View / edit
                    </button>
                  </>
                ) : clientInfoInputMethod === null ? (
                  // Initial choice
                  <>
                    <p className="text-sm text-zinc-600 mb-4">
                      Choose how to provide client information
                    </p>
                    <div className="space-y-2">
                      <button
                        onClick={() => setClientInfoInputMethod('manual')}
                        className="w-full px-4 py-2 border-2 border-zinc-400 text-zinc-900 rounded-md hover:bg-zinc-50 font-medium"
                      >
                        ✏️ Enter Manually
                      </button>
                      <button
                        onClick={() => setClientInfoInputMethod('file')}
                        className="w-full px-4 py-2 border border-zinc-200 text-zinc-600 rounded-md hover:bg-zinc-50"
                      >
                        📁 Upload File
                      </button>
                    </div>
                  </>
                ) : clientInfoInputMethod === 'file' ? (
                  // File upload mode
                  <>
                    <p className="text-sm text-zinc-600 mb-4">
                      Upload CSV, JSON, Word Doc, or PDF
                    </p>
                    <label className="cursor-pointer">
                      <input
                        type="file"
                        accept=".json,.csv,.pdf,.doc,.docx"
                        onChange={(e) => handleFileUpload(e, 'client_info')}
                        className="hidden"
                        disabled={uploadingFiles.client_info}
                      />
                      <span className="inline-flex items-center px-4 py-2 border border-zinc-200 rounded-md text-sm font-medium text-zinc-600 bg-white hover:bg-zinc-50 disabled:opacity-50">
                        {uploadingFiles.client_info ? 'Uploading...' : 'Choose File'}
                      </span>
                    </label>
                    <button
                      onClick={() => setClientInfoInputMethod(null)}
                      className="mt-2 text-xs text-zinc-600 hover:text-zinc-600 underline block mx-auto"
                    >
                      ← Back
                    </button>
                    {errors.client_info && (
                      <div className="mt-3 text-red-700 text-sm">{errors.client_info}</div>
                    )}
                  </>
                ) : (
                  // Manual input mode
                  <div className="text-left space-y-3 mt-4">
                    {/* Pre-filled banner — shown when an uploaded
                        client-info file populated the form. The user
                        should review and edit before submitting. */}
                    {status && status.files_summary && status.files_summary.client_info === 'uploaded' && manualClientInfo.client_name && (
                      <div className="rounded border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-900">
                        <span className="font-semibold">Pre-filled from your uploaded file.</span>{' '}
                        Review the details below and click Submit to save them to this matter.
                      </div>
                    )}
                    <div>
                      <label className="block text-xs font-medium text-zinc-600 mb-1">
                        Client Name *
                      </label>
                      <input
                        type="text"
                        value={manualClientInfo.client_name}
                        onChange={(e) => setManualClientInfo({...manualClientInfo, client_name: e.target.value})}
                        className="w-full px-3 py-2 border border-zinc-200 rounded-md text-sm"
                        placeholder="ABC Corp Ltd"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-zinc-600 mb-1">
                        Risk Rating *
                      </label>
                      <select
                        value={manualClientInfo.client_risk_rating}
                        onChange={(e) => setManualClientInfo({...manualClientInfo, client_risk_rating: e.target.value as any})}
                        className="w-full px-3 py-2 border border-zinc-200 rounded-md text-sm"
                      >
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                      </select>
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-zinc-600 mb-1">
                        Business Sector
                      </label>
                      <input
                        type="text"
                        value={manualClientInfo.business_sector}
                        onChange={(e) => setManualClientInfo({...manualClientInfo, business_sector: e.target.value})}
                        className="w-full px-3 py-2 border border-zinc-200 rounded-md text-sm"
                        placeholder="Manufacturing"
                      />
                    </div>
                    
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        checked={manualClientInfo.pep_status}
                        onChange={(e) => setManualClientInfo({...manualClientInfo, pep_status: e.target.checked})}
                        className="mr-2"
                      />
                      <label className="text-xs text-zinc-600">
                        Politically Exposed Person (PEP)
                      </label>
                    </div>
                    
                    <div className="border-t pt-3">
                      <label className="block text-xs font-medium text-zinc-600 mb-1">
                        Purchase Amount * (£)
                      </label>
                      <input
                        type="number"
                        value={manualPurchase.amount}
                        onChange={(e) => setManualPurchase({...manualPurchase, amount: e.target.value})}
                        className="w-full px-3 py-2 border border-zinc-200 rounded-md text-sm"
                        placeholder="500000"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-zinc-600 mb-1">
                        Purchase Description
                      </label>
                      <input
                        type="text"
                        value={manualPurchase.description}
                        onChange={(e) => setManualPurchase({...manualPurchase, description: e.target.value})}
                        className="w-full px-3 py-2 border border-zinc-200 rounded-md text-sm"
                        placeholder="Business acquisition"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-zinc-600 mb-1">
                        Expected Payment Date
                      </label>
                      <input
                        type="date"
                        value={manualPurchase.expected_payment_date}
                        onChange={(e) => setManualPurchase({...manualPurchase, expected_payment_date: e.target.value})}
                        className="w-full px-3 py-2 border border-zinc-200 rounded-md text-sm"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-zinc-600 mb-1">
                        Source of Funds Explanation *
                      </label>
                      <textarea
                        value={manualSofExplanation}
                        onChange={(e) => setManualSofExplanation(e.target.value)}
                        className="w-full px-3 py-2 border border-zinc-200 rounded-md text-sm"
                        rows={4}
                        placeholder="Explain where the funds came from (e.g., inheritance, property sale, savings, loan...)"
                      />
                    </div>
                    
                    <div className="pt-2 space-y-2">
                      <button
                        onClick={handleManualSubmit}
                        disabled={uploadingFiles.client_info}
                        className="w-full px-4 py-2 bg-zinc-900 text-white rounded-md hover:bg-zinc-900 disabled:opacity-50 text-sm font-medium"
                      >
                        {uploadingFiles.client_info ? 'Submitting...' : '✓ Submit'}
                      </button>
                      <button
                        onClick={() => setClientInfoInputMethod(null)}
                        className="w-full text-xs text-zinc-600 hover:text-zinc-600 underline"
                      >
                        ← Back
                      </button>
                    </div>
                    
                    {errors.client_info && (
                      <div className="mt-3 text-red-700 text-xs">{errors.client_info}</div>
                    )}
                  </div>
                )}
              </div>
            </div>
            </details>

            {/* Bank Statements — tile #2.
                Keyed on the uploaded flag so it remounts and collapses
                on the first upload (see Client Info tile note). */}
            <details
              key={`tile-bank-${(status?.files_summary?.bank_statements_count ?? 0) > 0}`}
              className="bg-white border border-zinc-200 rounded-md group"
              open={!status || !status.files_summary || status.files_summary.bank_statements_count === 0}
            >
              <summary className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-zinc-50/60 list-none">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-sm font-semibold text-zinc-900">Bank statements</span>
                  <span className="text-xs text-zinc-500">
                    {status && status.files_summary && status.files_summary.bank_statements_count > 0
                      ? `${status.files_summary.bank_statements_count} transaction record${status.files_summary.bank_statements_count !== 1 ? 's' : ''} extracted`
                      : 'None uploaded'}
                  </span>
                </div>
                <svg className="h-4 w-4 text-zinc-400 transition-transform group-open:rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </summary>
              <div className="px-5 pb-5 pt-4 border-t border-zinc-100">
              {/* Numbered list of bank statements already uploaded */}
              {renderUploadedList(status, fileVerificationResults, 'bank_statement', 'No bank statements uploaded yet.', (fn) => deleteUploadedFile(fn, 'bank_statement'), downloadUploadedFile)}

              {/* Add document */}
              <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-400 mb-2">Add document</div>
              <FileUploader
                key={`bank-${status?.files_summary?.bank_statements_count ?? 0}`}
                category="Bank statement"
                uploadUrl={`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/upload`}
                accept=".csv,.pdf"
                maxSizeMb={25}
                extraFormFields={{ file_category: 'bank_statement' }}
                helper="CSV or PDF, up to 25 MB"
                onComplete={(payload) => {
                  if (payload?.verification_verdict && payload?.filename) {
                    setFileVerificationResults(prev => ({
                      ...prev,
                      [payload.filename]: {
                        verdict: payload.verification_verdict,
                        score: payload.verification_score,
                        method: payload.verification_method,
                      },
                    }));
                  }
                  fetchStatus();
                }}
                extractVerdict={(payload) => payload?.verification_verdict
                  ? { verdict: payload.verification_verdict }
                  : null}
              />
              </div>
            </details>

            {/* Supporting Documents — tile #3.
                Keyed on the uploaded flag so it remounts and collapses
                on the first upload (see Client Info tile note). */}
            <details
              key={`tile-docs-${(status?.files_summary?.supporting_docs_count ?? 0) > 0}`}
              className="bg-white border border-zinc-200 rounded-md group"
              open={!status || !status.files_summary || status.files_summary.supporting_docs_count === 0}
            >
              <summary className="px-5 py-3 flex items-center justify-between cursor-pointer hover:bg-zinc-50/60 list-none">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-sm font-semibold text-zinc-900">Supporting documents</span>
                  <span className="text-xs text-zinc-500">
                    {status && status.files_summary && status.files_summary.supporting_docs_count > 0
                      ? `${status.files_summary.supporting_docs_count} document${status.files_summary.supporting_docs_count !== 1 ? 's' : ''} uploaded`
                      : 'None uploaded'}
                  </span>
                </div>
                <svg className="h-4 w-4 text-zinc-400 transition-transform group-open:rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </summary>
              <div className="px-5 pb-5 pt-4 border-t border-zinc-100">
              {/* Numbered list of supporting documents already uploaded */}
              {renderUploadedList(status, fileVerificationResults, 'supporting_doc', 'No supporting documents uploaded yet.', (fn) => deleteUploadedFile(fn, 'supporting_doc'), downloadUploadedFile)}

              {/* Add document */}
              <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-400 mb-2">Add document</div>
              <FileUploader
                key={`doc-${status?.files_summary?.supporting_docs_count ?? 0}`}
                category="Supporting document"
                uploadUrl={`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/upload`}
                accept=".pdf"
                maxSizeMb={25}
                extraFormFields={{ file_category: 'supporting_doc' }}
                helper="PDF, up to 25 MB"
                onComplete={(payload) => {
                  if (payload?.verification_verdict && payload?.filename) {
                    setFileVerificationResults(prev => ({
                      ...prev,
                      [payload.filename]: {
                        verdict: payload.verification_verdict,
                        score: payload.verification_score,
                        method: payload.verification_method,
                      },
                    }));
                  }
                  fetchStatus();
                }}
                extractVerdict={(payload) => payload?.verification_verdict
                  ? { verdict: payload.verification_verdict }
                  : null}
              />
              </div>
            </details>
          </div>

          {/* Run Assessment Button */}
          {status && status.ready_for_assessment && (
            <div className="flex justify-center">
              <button
                onClick={runAssessment}
                disabled={loading}
                className="px-8 py-3 bg-zinc-900 text-white rounded hover:bg-zinc-900 disabled:opacity-50 disabled:cursor-not-allowed font-semibold text-lg"
              >
                {loading ? 'Running assessment...' : 'Run SoF Assessment'}
              </button>
            </div>
          )}

          {errors.assessment && (
            <div className="bg-red-50 border border-red-200 rounded-md p-4 text-red-700">
              <strong>Assessment Error:</strong> {errors.assessment}
            </div>
          )}

          {!status || !status.ready_for_assessment && (
            <div className="bg-zinc-50 border border-zinc-200 rounded-md p-4 text-zinc-900">
              <strong>Required:</strong> Upload Client Info (JSON) and at least one Bank Statement (CSV/PDF) to run assessment.
            </div>
          )}
        </div>
      )}

      {/* Results Step */}
      {activeStep === 'results' && result && (
        <div className="space-y-6">
          {/* Verdict summary card — the top-of-page "what's the answer" panel.
              Replaces the previous emoji-decorated bold-text header. */}
          {(() => {
            const status = (result.outcome.status || '').toLowerCase();
            const verdictMap: Record<string, { label: string; severity: 'critical' | 'high' | 'medium' | 'info'; headline: string }> = {
              sufficient: { label: 'PASS',           severity: 'info',    headline: 'Source of funds is sufficiently evidenced.' },
              borderline: { label: 'REVIEW REQUIRED',severity: 'high',    headline: 'Manual review required before approval.' },
              insufficient:{label: 'FAIL',           severity: 'critical',headline: 'Source of funds is not adequately evidenced.' },
            };
            const v = verdictMap[status] || { label: status.toUpperCase() || 'UNKNOWN', severity: 'medium' as const, headline: 'Assessment complete.' };
            // Count from result.claims — the same array the Claims
            // table renders — so the card and the table can never
            // disagree on how many claims there are.
            const total = (result.claims?.length || result.evidence_matches?.length) || 0;
            // A claim "passed" only if EITHER:
            //   - an analyst has manually accepted any differences, OR
            //   - the document was verified AND the confidence is high
            //     (>= 0.999, the existing "no manual review needed"
            //     threshold used elsewhere in this file).
            //
            // Anything else — failed, no document, low confidence, awaiting
            // review — counts as needing review. e.verified alone is not
            // sufficient because the pipeline sometimes flags it true on
            // claims that still failed downstream document checks.
            const passed = result.evidence_matches?.filter((e: any) => {
              if (e.document_verification?.manual_review_status === 'accepted') return true;
              const confidence = e.document_verification?.confidence ?? 0;
              return e.document_verified === true && confidence >= 0.999;
            }).length || 0;
            const needsReview = Math.max(0, total - passed);
            return (
              <div className="bg-white border border-zinc-200 rounded-md">
                <div className="px-6 py-5 flex items-start gap-6 border-b border-zinc-100">
                  <div className="flex-1 min-w-0">
                    <div className="font-serif text-3xl font-normal text-zinc-900 tracking-tight">
                      {v.label}
                    </div>
                    <p className="mt-2 text-sm text-zinc-600">{v.headline}</p>
                  </div>
                  <StatusChip severity={v.severity} label={v.label} />
                </div>
                <div className="grid grid-cols-3 divide-x divide-zinc-100">
                  <div className="px-6 py-4">
                    <div className="font-serif text-2xl font-normal text-zinc-900 tabular-nums">{total}</div>
                    <div className="mt-1 text-[11px] uppercase tracking-wider text-zinc-400">Claims made</div>
                  </div>
                  <div className="px-6 py-4">
                    <div className={`font-serif text-2xl font-normal tabular-nums ${needsReview > 0 ? 'text-amber-700' : 'text-zinc-900'}`}>{needsReview}</div>
                    <div className="mt-1 text-[11px] uppercase tracking-wider text-zinc-400">Claims requiring review</div>
                  </div>
                  <div className="px-6 py-4">
                    <div className={`font-serif text-2xl font-normal tabular-nums ${(docVerificationSummary?.likely_tampered_count ?? 0) > 0 ? 'text-red-700' : 'text-zinc-900'}`}>
                      {docVerificationSummary?.total_documents ?? 0}
                    </div>
                    <div className="mt-1 text-[11px] uppercase tracking-wider text-zinc-400">Documents reviewed</div>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Source of Funds Analysis — the claims table.
              Rendered DIRECTLY from result.claims, always. It used to
              be gated behind finding a "SOURCE OF FUNDS" header inside
              the free-text rationale, which silently deleted the whole
              tile whenever the rationale was header-less. */}
          {renderSoFSection('', result)}

          {/* Source of Funds evidence checklist. For each claim that is
              NOT yet verified, splits the expected evidence into what
              has been provided (ticked) and what is still suggested to
              obtain. Verified claims are omitted — nothing further is
              needed. Provided-detection is a filename heuristic against
              the matter's uploads. */}
          {(() => {
            const uploaded: any[] = status?.uploaded_files || [];

            // Heuristic: which uploaded file (if any) satisfies this
            // expected-evidence line? Bank-statement lines are met by
            // any bank statement; document lines are keyword-matched
            // against supporting-doc / client-info filenames. Returns
            // the matching filename, or null when nothing matches.
            const matchedFile = (text: string): string | null => {
              const t = text.toLowerCase();
              if (t.includes('bank statement')) {
                const f = uploaded.find((f) => f.category === 'bank_statement');
                return f ? (f.filename || null) : null;
              }
              const docFiles = uploaded.filter(
                (f) => f.category === 'supporting_doc' || f.category === 'client_info',
              );
              if (docFiles.length === 0) return null;
              const TERMS = [
                'completion', 'contract', 'memorandum', 'probate', 'administration',
                'will', 'executor', 'estate', 'death certificate', 'payslip', 'p60',
                'tax return', 'employment', 'pension', 'annuity', 'dividend', 'voucher',
                'loan', 'mortgage', 'gift', 'settlement', 'redundancy', 'insurance',
                'endowment', 'title', 'land registry', 'accounts', 'brokerage', 'invoice',
              ];
              for (const term of TERMS) {
                if (!t.includes(term)) continue;
                const first = term.split(' ')[0];
                const f = docFiles.find((f) => String(f.filename || '').toLowerCase().includes(first));
                if (f) return f.filename || null;
              }
              return null;
            };

            // A claim is Verified only once the reviewer has pressed
            // "Sufficient Evidence Provided" — status is user-driven.
            const claimVerified = (idx: number): boolean =>
              !!((result.claim_actions || {})[String(idx)] || {}).sufficient;

            const fmtMoney = (n: any) => `£${Math.round(Number(n) || 0).toLocaleString()}`;
            const fmtGapDate = (s: any): string => {
              if (!s) return 'an unknown date';
              const str = String(s);
              if (str.includes('-')) {
                const p = str.split('-');
                if (p.length === 3) return `${p[2]}/${p[1]}/${p[0]}`;
              }
              return str;
            };

            // What the other modules have flagged for review against
            // THIS claim — the per-claim gap detail the Documents
            // Required tile used to carry, now folded into the checklist
            // so the fee earner sees it claim-by-claim.
            const claimGaps = (claim: any, ev: any, verified: boolean, hasProvided: boolean): string[] => {
              const out: string[] = [];
              const dv = ev?.document_verification || {};
              const diffs = Array.isArray(dv.differences) ? dv.differences : [];
              const claimAmt = Number(claim?.expected_amount || 0);
              for (const d of diffs) {
                const field = String(d.field || '');
                const amt = Number(d.amount || 0);
                if (field === 'untraced_funds' && amt > 0) {
                  out.push(`${fmtMoney(amt)} received on ${fmtGapDate(d.date)} is not traced in Funds Lineage${d.found ? ` (${d.found})` : ''}.`);
                } else if (field === 'funds_discrepancy' && Number(d.discrepancy_amount || 0) > 0) {
                  const gap = Number(d.discrepancy_amount);
                  const pct = claimAmt > 0 ? Math.round((gap / claimAmt) * 100) : 0;
                  out.push(`${pct > 0 ? `≈${pct}% of the ${fmtMoney(claimAmt)} claimed` : fmtMoney(gap)} is not yet evidenced — further statements confirming ${fmtMoney(gap)} required.`);
                } else if (field === 'statement_gap') {
                  out.push(`Bank statements for ${d.gap_account || 'the source account'} before ${fmtGapDate(d.gap_account_earliest || d.date)} are required to close a statement gap.`);
                } else if (d.severity === 'missing') {
                  out.push(`A document showing ${field.replace(/_/g, ' ')} is required.`);
                }
              }
              const verdict = dv.verdict;
              if (verdict === 'Suspicious' || verdict === 'LikelyTampered') {
                out.push('Document Verification flagged this claim’s evidence — see the Document Verification tile.');
              }
              if (!verified && !hasProvided && out.length === 0) {
                out.push('No corroborating evidence has been matched yet — obtain and upload the suggested evidence above.');
              }
              return out;
            };

            // Build the rows — every claim with a checklist or an open
            // gap. Provided / Suggested / Gaps are precomputed here.
            const rows = (result.claims || []).map((claim: any, idx: number) => {
              const docs: string[] = claim.expected_evidence || [];
              const ev = result.evidence_matches[idx] || {};
              const action = (result.claim_actions || {})[String(idx)] || {};
              const verified = claimVerified(idx);
              const provided = docs
                .map((d: string) => ({ doc: d, file: matchedFile(d) }))
                .filter((x: any) => x.file);
              const suggested = docs.filter((d: string) => !matchedFile(d));
              const gaps = claimGaps(claim, ev, verified, provided.length > 0);
              return { claim, idx, docs, verified, action, provided, suggested, gaps };
            }).filter((r: any) => r.docs.length > 0 || r.gaps.length > 0);

            if (rows.length === 0) return null;

            return (
              <details className="bg-white border border-zinc-200 rounded-md overflow-hidden group">
                <summary className="bg-zinc-50 border-b border-zinc-200 px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-zinc-100 list-none">
                  <h3 className="text-lg font-bold text-zinc-900">Evidence Checklist</h3>
                  <svg className="h-4 w-4 text-zinc-400 transition-transform group-open:rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </summary>
                <div className="px-6 py-4">
                  <p className="text-xs text-zinc-500 mb-4">
                    The fee earner's worklist: what has been provided for each claim, what is
                    still suggested to obtain (tick each item off as you go), and what the
                    other modules have flagged as outstanding for that claim. Tiered to the
                    matter's risk rating (LSAG §6.8).
                  </p>
                  <div className="space-y-4">
                    {rows.map((row: any) => {
                      const label = String(row.claim.source_type || 'Source').replace(/_/g, ' ');
                      const amt = `£${Number(row.claim.expected_amount || 0).toLocaleString()}`;
                      const provided = row.provided;
                      const suggested = row.suggested;
                      const ticked: string[] = (result.evidence_checklist?.claim_evidence || {})[String(row.idx)] || [];
                      return (
                        <div key={row.idx} className="border border-zinc-100 rounded p-3">
                          <div className="text-sm font-medium text-zinc-900 capitalize">
                            {label} <span className="text-zinc-400 tabular-nums">· {amt}</span>
                          </div>

                          {provided.length > 0 && (
                            <div className="mt-2">
                              <div className="text-[10px] font-semibold uppercase tracking-wider text-green-600 mb-1">
                                Provided
                              </div>
                              <ul className="space-y-1.5">
                                {provided.map((item: any, di: number) => (
                                  <li key={di} className="flex items-start gap-3 text-xs leading-snug">
                                    <svg className="mt-0.5 h-3.5 w-3.5 text-green-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                    </svg>
                                    <span className="flex-1 min-w-0 text-zinc-700">{item.doc}</span>
                                    <span className="flex-shrink-0 max-w-[14rem] truncate text-[11px] text-zinc-500 font-mono" title={item.file}>
                                      {item.file}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {suggested.length > 0 && (
                            <div className="mt-2.5">
                              {/* Tickable worklist — the fee earner ticks
                                  each item off as they obtain it. Provided
                                  items are auto-matched and not listed here. */}
                              <div className={`text-[10px] font-semibold uppercase tracking-wider mb-1 ${
                                row.verified ? 'text-zinc-400' : 'text-amber-600'
                              }`}>
                                {row.verified ? 'Other possible evidence' : 'Suggested Evidence to Obtain'}
                              </div>
                              <ul className="space-y-1">
                                {suggested.map((doc: string, di: number) => {
                                  const done = ticked.includes(doc);
                                  return (
                                    <li key={di}>
                                      <label className="flex items-start gap-2 text-xs leading-snug cursor-pointer">
                                        <input
                                          type="checkbox"
                                          checked={done}
                                          onChange={() => toggleClaimEvidence(row.idx, doc)}
                                          className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 rounded border-zinc-300 text-green-600 focus:ring-green-500"
                                        />
                                        <span className={done ? 'text-zinc-400 line-through' : 'text-zinc-700'}>{doc}</span>
                                      </label>
                                    </li>
                                  );
                                })}
                              </ul>
                            </div>
                          )}

                          {/* What the other modules have flagged for this
                              specific claim — the per-claim gap detail. */}
                          {row.gaps.length > 0 && (
                            <div className="mt-2.5">
                              <div className="text-[10px] font-semibold uppercase tracking-wider text-red-600 mb-1">
                                Outstanding / flagged for review
                              </div>
                              <ul className="space-y-1">
                                {row.gaps.map((g: string, gi: number) => (
                                  <li key={gi} className="flex items-start gap-2 text-xs text-zinc-700 leading-snug">
                                    <span className="mt-[5px] h-1.5 w-1.5 rounded-full flex-shrink-0 bg-red-400" />
                                    {g}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* Compliance conversation — the audit trail of
                              messages between the fee earner and compliance. */}
                          {(() => {
                            const thread: any[] = (row.action.compliance || {}).thread || [];
                            if (thread.length === 0) return null;
                            const fmtTs = (s: string) => {
                              const d = new Date(s);
                              return isNaN(d.getTime())
                                ? ''
                                : d.toLocaleString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
                            };
                            return (
                              <div className="mt-3 pt-3 border-t border-zinc-100">
                                <div className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">
                                  Compliance conversation
                                </div>
                                <ul className="space-y-2">
                                  {thread.map((m: any, ti: number) => {
                                    const isCompliance = m.actor === 'compliance';
                                    const who = isCompliance ? 'Compliance' : 'Fee earner';
                                    const verb = m.action === 'returned'
                                      ? 'returned to fee earner'
                                      : m.action === 'cancelled'
                                        ? 'cancelled referral'
                                        : 'sent to compliance';
                                    return (
                                      <li key={ti} className="text-xs leading-snug">
                                        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                                          isCompliance ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'
                                        }`}>
                                          {who}
                                        </span>
                                        <span className="ml-1.5 text-zinc-400">
                                          {verb} · {m.by || 'unknown'}{m.at ? ` · ${fmtTs(m.at)}` : ''}
                                        </span>
                                        <div className="mt-0.5 italic text-zinc-700">"{m.message}"</div>
                                      </li>
                                    );
                                  })}
                                </ul>
                              </div>
                            );
                          })()}

                          {/* Per-claim actions — bottom-right. */}
                          {(() => {
                            const compState = (row.action.compliance || {}).state;
                            const inReview = compState === 'in_review';
                            const sufficient = !!row.action.sufficient;
                            return (
                              <div className="mt-3 pt-3 border-t border-zinc-100 flex items-center justify-end gap-2">
                                {isAdmin && inReview && (
                                  <button
                                    type="button"
                                    onClick={() => complianceReturnClaim(row.idx)}
                                    className="px-3 py-1.5 text-xs font-medium rounded border border-red-300 text-red-700 hover:bg-red-50 transition-colors"
                                  >
                                    Return to Fee Earner
                                  </button>
                                )}
                                {inReview ? (
                                  <button
                                    type="button"
                                    onClick={() => cancelClaimCompliance(row.idx)}
                                    className="px-3 py-1.5 text-xs font-medium rounded border border-zinc-300 text-zinc-700 hover:bg-zinc-50 transition-colors"
                                  >
                                    Cancel Compliance Referral
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => sendClaimToCompliance(row.idx)}
                                    className="px-3 py-1.5 text-xs font-medium rounded border border-zinc-300 text-zinc-700 hover:bg-zinc-50 transition-colors"
                                  >
                                    Send to Compliance
                                  </button>
                                )}
                                {sufficient ? (
                                  <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-full bg-green-50 text-green-700 ring-1 ring-inset ring-green-200">
                                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                    </svg>
                                    Sufficient Evidence Provided
                                  </span>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => markClaimSufficient(row.idx)}
                                    className="px-3.5 py-1.5 text-xs font-semibold rounded-full bg-green-600 text-white hover:bg-green-700 transition-colors"
                                  >
                                    Sufficient Evidence Provided
                                  </button>
                                )}
                              </div>
                            );
                          })()}
                        </div>
                      );
                    })}
                  </div>

                  {/* Transaction Review worklist — alerts as tickable
                      items, so the fee earner works through them here
                      and uses the Transaction Review tile for detail. */}
                  {(() => {
                    if (result.sections_enabled?.transaction_review === false) return null;
                    const trs = result.transaction_review_summary;
                    const alerts: any[] = (trs?.alerts || (trs as any)?.alert_details || []);
                    if (alerts.length === 0) return null;
                    const trTicked: string[] = result.evidence_checklist?.transaction_alerts || [];
                    return (
                      <div className="mt-6 pt-4 border-t border-zinc-200">
                        <div className="text-sm font-semibold text-zinc-900">Transaction Review</div>
                        <p className="text-xs text-zinc-500 mt-0.5 mb-3">
                          Alerts raised against the transactions — work through each and tick it
                          once reviewed. Open the Transaction Review tile for the full detail.
                        </p>
                        <ul className="space-y-2">
                          {alerts.map((alert: any, ai: number) => {
                            const key = String(ai);
                            const done = trTicked.includes(key);
                            const severity = String(alert.severity || 'HIGH').toUpperCase();
                            const txn = alert.transaction || alert;
                            const amount = txn.amount ?? alert.amount;
                            const date = txn.date || alert.date || '';
                            const narrative = txn.narrative || alert.counterparty || '';
                            const issue = (alert.reasons && alert.reasons.length > 0) ? alert.reasons[0] : 'AML concern';
                            return (
                              <li key={ai}>
                                <label className="flex items-start gap-2 text-xs leading-snug cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={done}
                                    onChange={() => toggleTransactionAlert(key)}
                                    className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 rounded border-zinc-300 text-green-600 focus:ring-green-500"
                                  />
                                  <span className="min-w-0">
                                    <span className={done ? 'text-zinc-400 line-through' : 'text-zinc-900 font-medium'}>{issue}</span>
                                    <span className={`ml-1.5 text-[10px] font-semibold uppercase ${
                                      severity === 'CRITICAL' ? 'text-red-600' : severity === 'HIGH' ? 'text-amber-600' : 'text-zinc-400'
                                    }`}>{severity}</span>
                                    <div className={done ? 'text-zinc-300' : 'text-zinc-500'}>
                                      {amount != null && `£${Number(amount).toLocaleString()}`}{date && ` · ${date}`}{narrative && ` · ${narrative}`}
                                    </div>
                                  </span>
                                </label>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    );
                  })()}
                </div>
              </details>
            );
          })()}

          {/* Remaining rationale sections (Transaction Review). */}
          {renderStructuredRationale(result)}

          {/* ============================================================ */}
          {/* FUNDS LINEAGE SECTION (collapsible by default)                */}
          {/* ============================================================ */}
          {result.sections_enabled?.funds_lineage !== false && (
          <details id="tile-funds-lineage" className="bg-white border border-zinc-200 rounded-md overflow-hidden group">
            <summary className="bg-zinc-50 border-b border-zinc-200 px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-zinc-100 list-none">
              <h3 className="text-lg font-bold text-zinc-900">Funds Lineage</h3>
              <svg className="h-4 w-4 text-zinc-400 transition-transform group-open:rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </summary>

            {fundsLineageData?.exists && fundsLineageData.summary ? (
              (() => {
                const s = fundsLineageData.summary!;
                const total = s.totalAmount || 0;
                const traced = s.tracedAmount || 0;
                const untraced = s.untracedAmount || 0;
                const tracedPct = total > 0 ? Math.round((traced / total) * 100) : 0;
                const fmt = (n: number) => `£${Math.round(n).toLocaleString()}`;
                const unresolvedCount = fundsLineageData.unresolved_items?.length || 0;
                return (
                  <>
                    {/* Stat strip */}
                    <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-zinc-100">
                      <div className="px-6 py-4">
                        <div className="font-serif text-2xl font-normal text-zinc-900 tabular-nums">{fmt(total)}</div>
                        <div className="mt-1 text-[11px] uppercase tracking-wider text-zinc-400">Total amount</div>
                      </div>
                      <div className="px-6 py-4">
                        <div className="font-serif text-2xl font-normal text-zinc-900 tabular-nums">{fmt(traced)}</div>
                        <div className="mt-1 text-[11px] uppercase tracking-wider text-zinc-400">Traced ({tracedPct}%)</div>
                      </div>
                      <div className="px-6 py-4">
                        <div className={`font-serif text-2xl font-normal tabular-nums ${untraced > 0 ? 'text-amber-700' : 'text-zinc-900'}`}>{fmt(untraced)}</div>
                        <div className="mt-1 text-[11px] uppercase tracking-wider text-zinc-400">Untraced ({Math.max(0, 100 - tracedPct)}%)</div>
                      </div>
                      <div className="px-6 py-4">
                        <div className="font-serif text-2xl font-normal text-zinc-900 tabular-nums">{s.matchedTransfers || 0}</div>
                        <div className="mt-1 text-[11px] uppercase tracking-wider text-zinc-400">Matched transfers</div>
                      </div>
                    </div>

                    {/* Progress bar — traced vs untraced */}
                    {total > 0 && (
                      <div className="px-6 py-4 border-t border-zinc-100">
                        <div className="h-2 w-full rounded-full overflow-hidden bg-zinc-100 flex">
                          {traced > 0 && (
                            <div className="bg-green-500" style={{ width: `${tracedPct}%` }} title={`Traced ${fmt(traced)}`} />
                          )}
                          {untraced > 0 && (
                            <div className="bg-amber-500" style={{ width: `${Math.max(0, 100 - tracedPct)}%` }} title={`Untraced ${fmt(untraced)}`} />
                          )}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-zinc-500">
                          <span className="inline-flex items-center gap-2">
                            <span className="h-2 w-2 rounded-sm bg-green-500" />
                            Traced to source
                          </span>
                          <span className="inline-flex items-center gap-2">
                            <span className="h-2 w-2 rounded-sm bg-amber-500" />
                            Untraced / requires evidence
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Period + unresolved summary */}
                    <div className="px-6 py-4 border-t border-zinc-100 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                      {s.accumulationPeriodDays > 0 && (
                        <div>
                          <div className="text-[11px] uppercase tracking-wider text-zinc-400 mb-1">Accumulation period</div>
                          <div className="text-zinc-700">{s.accumulationPeriodDays} day{s.accumulationPeriodDays !== 1 ? 's' : ''}</div>
                        </div>
                      )}
                      {(s.externalOrigins ?? 0) > 0 && (
                        <div>
                          <div className="text-[11px] uppercase tracking-wider text-zinc-400 mb-1">External origins</div>
                          <div className="text-zinc-700">{s.externalOrigins}</div>
                        </div>
                      )}
                      {(s.requiresEvidence ?? 0) > 0 && (
                        <div>
                          <div className="text-[11px] uppercase tracking-wider text-zinc-400 mb-1">Requires evidence</div>
                          <div className="text-amber-700 font-medium">{s.requiresEvidence}</div>
                        </div>
                      )}
                    </div>

                    {/* Circular references — high-priority callout */}
                    {(s.circularReferences ?? 0) > 0 && (
                      <div className="px-6 py-4 border-t border-zinc-100 bg-red-50/50">
                        <div className="flex items-start gap-3">
                          <span className="mt-1 h-2 w-2 rounded-full bg-red-500 shrink-0" />
                          <div>
                            <div className="text-sm font-semibold text-red-900">
                              {s.circularReferences} circular reference{(s.circularReferences ?? 0) !== 1 ? 's' : ''} detected
                            </div>
                            <p className="text-xs text-red-700 mt-0.5">
                              One or more transactions reference funding that loops back to an earlier point in the chain.
                              This can indicate round-tripping. Open the full lineage to review.
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Ambiguous account classification — medium-priority */}
                    {((s.ambiguousAccounts ?? 0) > 0 || (fundsLineageData.ambiguous_accounts?.length ?? 0) > 0) && (
                      <div className="px-6 py-4 border-t border-zinc-100 bg-amber-50/50">
                        <div className="flex items-start gap-3">
                          <span className="mt-1 h-2 w-2 rounded-full bg-amber-500 shrink-0" />
                          <div className="min-w-0">
                            <div className="text-sm font-semibold text-amber-900">
                              Account type could not be confidently identified
                            </div>
                            <p className="text-xs text-amber-800 mt-0.5">
                              The classifier wasn't sure whether the following account(s) were savings or current —
                              this can break matching between accounts. Rename / re-upload with a clearer filename.
                            </p>
                            <ul className="mt-2 space-y-1 text-xs text-amber-900">
                              {(fundsLineageData.ambiguous_accounts || []).slice(0, 3).map((acc, idx) => (
                                <li key={idx} className="font-mono">
                                  {acc.account_id} — guessed as <span className="font-semibold">{acc.classified_as}</span> ({acc.confidence} confidence)
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Unresolved items preview (top 3) */}
                    {unresolvedCount > 0 && (
                      <div className="px-6 py-4 border-t border-zinc-100">
                        <div className="text-[11px] uppercase tracking-wider text-zinc-400 mb-2">
                          Unresolved items ({unresolvedCount})
                        </div>
                        <ul className="space-y-1.5">
                          {fundsLineageData.unresolved_items!.slice(0, 3).map((item, idx) => (
                            <li key={idx} className="text-sm text-zinc-700 flex items-baseline justify-between gap-3">
                              <span className="truncate">
                                <span className="text-zinc-400 mr-2 tabular-nums">{item.date}</span>
                                {item.reason === 'circular_reference' && (
                                  <span className="mr-2 text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-red-100 text-red-700">
                                    CIRCULAR
                                  </span>
                                )}
                                {item.description || item.message || '—'}
                              </span>
                              <span className="text-amber-700 tabular-nums font-medium shrink-0">{fmt(item.amount)}</span>
                            </li>
                          ))}
                        </ul>
                        {unresolvedCount > 3 && (
                          <Link
                            to={`/matters/${matterId}?tab=funds-lineage`}
                            className="mt-2 inline-block text-xs text-zinc-700 hover:text-zinc-900 underline-offset-2 hover:underline"
                          >
                            + {unresolvedCount - 3} more — open full lineage
                          </Link>
                        )}
                      </div>
                    )}
                  </>
                );
              })()
            ) : (
              <div className="px-6 py-8 text-center">
                <p className="text-sm text-zinc-600">
                  No funds-lineage analysis has been run yet for this matter.
                </p>
                <p className="text-xs text-zinc-400 mt-1">
                  Funds lineage traces credits in the bank statements back to their source. Open the tab to run it.
                </p>
                <Link
                  to={`/matters/${matterId}?tab=funds-lineage`}
                  className="inline-block mt-3 px-3 py-1.5 text-xs font-medium bg-zinc-900 text-white rounded hover:bg-zinc-800 transition-colors"
                >
                  Open Funds Lineage
                </Link>
              </div>
            )}
          </details>
          )}

          {/* ============================================================ */}
          {/* DOCUMENT VERIFICATION SECTION (collapsible by default)        */}
          {/* ============================================================ */}
          {docVerificationSummary && docVerificationSummary.total_documents > 0 &&
            result.sections_enabled?.document_verification !== false && (
            <details id="tile-doc-verification" className="bg-white border border-zinc-200 rounded-md overflow-hidden group">
              <summary className="bg-zinc-50 border-b border-zinc-200 px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-zinc-100 list-none">
                <h3 className="text-lg font-bold text-zinc-900 flex items-center gap-2">
                  Document Verification
                  {docVerificationSummary.has_blocking_issues ? (
                    <span className="ml-2 px-2 py-0.5 text-xs font-bold rounded bg-red-100 text-red-700 border border-red-200">BLOCKED</span>
                  ) : docVerificationSummary.suspicious_count > 0 ? (
                    <span className="ml-2 px-2 py-0.5 text-xs font-bold rounded bg-amber-100 text-amber-700 border border-amber-200">REVIEW</span>
                  ) : (
                    <span className="ml-2 px-2 py-0.5 text-xs font-bold rounded bg-green-100 text-green-700 border border-green-200">VERIFIED</span>
                  )}
                </h3>
                <svg className="h-4 w-4 text-zinc-400 transition-transform group-open:rotate-180" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </summary>
              <div className="px-6 py-4">
              {/* Summary counts */}
              <div className="flex items-center flex-wrap gap-4 mb-5 text-sm text-zinc-600">
                <span>{docVerificationSummary.total_documents} document{docVerificationSummary.total_documents !== 1 ? 's' : ''} checked</span>
                <span className="text-zinc-200">|</span>
                {docVerificationSummary.verified_count > 0 && (
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-green-500" />
                    <span className="text-green-700 font-medium">{docVerificationSummary.verified_count} passed</span>
                  </span>
                )}
                {docVerificationSummary.suspicious_count > 0 && (
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-500" />
                    <span className="text-amber-700 font-medium">{docVerificationSummary.suspicious_count} need{docVerificationSummary.suspicious_count === 1 ? 's' : ''} review</span>
                  </span>
                )}
                {docVerificationSummary.likely_tampered_count > 0 && (
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-red-500" />
                    <span className="text-red-700 font-medium">{docVerificationSummary.likely_tampered_count} failed</span>
                  </span>
                )}
              </div>

              {/* Per-Document Detail */}
              <div className="space-y-3">
                {(docVerificationSummary.verifications || []).map((v: any, idx: number) => {
                  const isCSVDoc = v.verification_phase === 'statement_only';
                  const isVerified = v.verdict === 'Verified';
                  const isSuspicious = v.verdict === 'Suspicious';
                  const isTampered = v.verdict === 'LikelyTampered';

                  const verdictConfig = isVerified
                    ? { label: isCSVDoc ? 'CHECKS PASSED' : 'VERIFIED', sublabel: 'No issues detected', borderClass: 'border-zinc-200 border-l-2 border-l-green-500', bgClass: 'bg-white', textClass: 'text-zinc-600', badgeClass: 'bg-green-50 text-green-700 ring-1 ring-inset ring-green-200' }
                    : isSuspicious
                    ? { label: 'NEEDS REVIEW', sublabel: 'Issues found that require attention', borderClass: 'border-zinc-200 border-l-2 border-l-amber-500', bgClass: 'bg-white', textClass: 'text-zinc-600', badgeClass: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200' }
                    : { label: 'FAILED', sublabel: 'Serious concerns identified', borderClass: 'border-zinc-200 border-l-2 border-l-red-500', bgClass: 'bg-white', textClass: 'text-zinc-600', badgeClass: 'bg-red-50 text-red-700 ring-1 ring-inset ring-red-200' };

                  // Filter to actionable flags only
                  const actionableFlags = (v.flags || []).filter(
                    (f: any) => f.severity !== 'info' && !f.code?.endsWith('_OK') && f.code !== 'FINAL_SCORE' && f.code !== 'NON_PDF_FILE' && f.code !== 'SINGLE_EOF'
                  );
                  const criticalFlags = actionableFlags.filter((f: any) => f.severity === 'critical');
                  const highFlags = actionableFlags.filter((f: any) => f.severity === 'high');
                  const mediumFlags = actionableFlags.filter((f: any) => f.severity === 'medium');
                  const minorFlags = actionableFlags.filter((f: any) => f.severity === 'low');

                  return (
                    <div key={idx} className={`border rounded-md ${verdictConfig.borderClass} ${verdictConfig.bgClass}`}>
                      {/* Header: icon + filename + verdict badge */}
                      <div className="flex items-center justify-between p-4 pb-0">
                        <div className="flex items-center gap-3">
                          {isVerified ? (
                            <svg className="w-5 h-5 text-green-700 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                          ) : isSuspicious ? (
                            <svg className="w-5 h-5 text-amber-700 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>
                          ) : (
                            <svg className="w-5 h-5 text-red-700 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                          )}
                          <div>
                            <span className="font-semibold text-zinc-900 text-sm">{v.filename}</span>
                            {v.identified_bank_template && (
                              <span className="ml-2 text-xs text-zinc-600">({v.identified_bank_template})</span>
                            )}
                          </div>
                        </div>
                        <span className={`px-3 py-1 text-xs font-bold rounded ${verdictConfig.badgeClass}`}>
                          {verdictConfig.label}
                        </span>
                      </div>

                      {/* Sub-label + Scoring */}
                      <div className="px-4 pt-1 pb-3">
                        <span className={`text-xs ${verdictConfig.textClass}`}>{verdictConfig.sublabel}</span>
                        {/* Scoring metrics row */}
                        {v.authenticity_score != null && (
                          <div className="flex items-center gap-2 mt-2 flex-wrap">
                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                              v.authenticity_score >= 75 ? 'bg-green-100 text-green-700' :
                              v.authenticity_score >= 45 ? 'bg-amber-100 text-amber-700' :
                              'bg-red-100 text-red-700'
                            }`}>
                              Score: {Math.round(v.authenticity_score)}/100
                            </span>
                            {/* Per-pipeline stage pills */}
                            {(() => {
                              const stages = isCSVDoc
                                ? [
                                    { key: 'statement_pipeline_score', label: 'Statement' },
                                  ]
                                : [
                                    { key: 'structural_pipeline_score', label: 'Structure' },
                                  ];
                              return stages.map((s) => {
                                const score = v[s.key];
                                if (score == null) return null;
                                const rounded = Math.round(score);
                                const pillClass = rounded >= 75 ? 'bg-[#86efac]/40 text-green-800' :
                                  rounded >= 45 ? 'bg-[#fcd34d]/40 text-amber-800' :
                                  'bg-[#fca5a5]/40 text-red-800';
                                return (
                                  <span key={s.key} className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${pillClass}`}>
                                    {s.label}: {rounded}
                                  </span>
                                );
                              });
                            })()}
                          </div>
                        )}
                      </div>

                      {/* Issues list — plain-English bullet points, no
                          coloured boxes (matches the Evidence Checklist). */}
                      {actionableFlags.length > 0 && !isVerified && (
                        <div className="border-t border-zinc-200 mx-4 pt-3 pb-4">
                          <div className="text-xs font-semibold text-zinc-900 uppercase tracking-wide mb-2">Why this document was flagged</div>

                          <ul className="space-y-2.5">
                            {[...criticalFlags, ...highFlags, ...mediumFlags].map((f: any, fi: number) => {
                              const t = translateFlag(f);
                              const sev = String(f.severity || '').toLowerCase();
                              const dot = sev === 'critical' ? 'bg-red-500'
                                : sev === 'high' ? 'bg-amber-500'
                                : 'bg-zinc-400';
                              return (
                                <li key={fi} className="flex gap-2.5 items-start">
                                  <span className={`mt-[5px] flex-shrink-0 w-1.5 h-1.5 rounded-full ${dot}`} />
                                  <div className="min-w-0">
                                    <div className="text-sm font-medium text-zinc-900">{t.headline}</div>
                                    <div className="text-xs text-zinc-600 mt-0.5 leading-relaxed">{t.explanation}</div>
                                  </div>
                                </li>
                              );
                            })}
                          </ul>

                          {minorFlags.length > 0 && (
                            <div className="text-xs text-zinc-400 pl-4 mt-2.5">
                              + {minorFlags.length} minor observation{minorFlags.length !== 1 ? 's' : ''}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Admin Override UI for LikelyTampered / Suspicious */}
                      {(v.verdict === 'LikelyTampered' || v.verdict === 'Suspicious') && v.blocked && !v.admin_override && (
                        <div className="mt-3 pt-3 border-t border-zinc-200">
                          <div className="flex items-center gap-2 text-sm text-red-700 mb-2">
                            <span className="font-semibold">Upload blocked -- downstream processing halted.</span>
                          </div>
                          {v.override_proposed_by && !v.admin_override && (
                            <div className="mb-3 px-3 py-2 rounded border border-amber-200 bg-amber-50 text-xs text-amber-700">
                              <div className="font-semibold">Awaiting second-reviewer approval (four-eyes).</div>
                              <div className="mt-1">
                                Override proposed by <span className="font-mono">{v.override_proposed_by}</span>
                                {v.override_proposed_at && (
                                  <span> on {new Date(v.override_proposed_at).toLocaleString()}</span>
                                )}.
                              </div>
                              {v.override_proposed_rationale && (
                                <div className="mt-1 italic">"{v.override_proposed_rationale}"</div>
                              )}
                              <div className="mt-1 text-amber-700">
                                A different admin must now click Override to approve.
                              </div>
                            </div>
                          )}
                          {docVerOverrideModalOpen === v.id ? (
                            <div className="bg-white rounded-md p-3 border border-zinc-200 space-y-2">
                              <div className="flex items-baseline justify-between">
                                <label className="block text-xs font-semibold text-zinc-600">
                                  Admin Override Rationale (required, min 10 chars):
                                </label>
                                <span
                                  className={`text-[10px] font-medium ${
                                    docVerOverrideRationale.length >= 10
                                      ? 'text-green-700'
                                      : 'text-zinc-400'
                                  }`}
                                >
                                  {docVerOverrideRationale.length} / 10 min
                                </span>
                              </div>
                              <textarea
                                className="w-full border border-zinc-200 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-300"
                                rows={3}
                                value={docVerOverrideRationale}
                                onChange={(e) => setDocVerOverrideRationale(e.target.value)}
                                placeholder="Provide rationale for overriding the block (e.g., confirmed with client that document is genuine)..."
                              />
                              <div className="flex gap-2">
                                <button
                                  disabled={docVerOverrideRationale.length < 10 || docVerOverrideSubmitting}
                                  onClick={async () => {
                                    setDocVerOverrideSubmitting(true);
                                    try {
                                      const resp = await authFetch(
                                        `${API_BASE_URL}/api/v1/matters/${matterId}/document-verifications/${v.id}/admin-override`,
                                        {
                                          method: 'POST',
                                          body: JSON.stringify({
                                            admin_user: 'admin',
                                            rationale: docVerOverrideRationale,
                                          }),
                                        }
                                      );
                                      if (resp.ok) {
                                        const updatedVerifications = [...(docVerificationSummary.verifications || [])];
                                        updatedVerifications[idx] = {
                                          ...updatedVerifications[idx],
                                          admin_override: true,
                                          admin_override_by: 'admin',
                                          admin_override_rationale: docVerOverrideRationale,
                                          blocked: false,
                                        };
                                        setDocVerificationSummary({
                                          ...docVerificationSummary,
                                          verifications: updatedVerifications,
                                          blocked_count: Math.max(0, docVerificationSummary.blocked_count - 1),
                                          overridden_count: (docVerificationSummary.overridden_count || 0) + 1,
                                          has_blocking_issues: updatedVerifications.some((uv: any) => uv.blocked && !uv.admin_override),
                                        });
                                        setDocVerOverrideModalOpen(null);
                                        setDocVerOverrideRationale('');
                                      } else {
                                        const err = await resp.json();
                                        alert(`Override failed: ${err.detail || 'Unknown error'}`);
                                      }
                                    } catch (err: any) {
                                      alert(`Override error: ${err.message}`);
                                    } finally {
                                      setDocVerOverrideSubmitting(false);
                                    }
                                  }}
                                  className="px-4 py-1.5 bg-red-700 text-white text-sm rounded hover:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed font-semibold"
                                >
                                  {docVerOverrideSubmitting ? 'Submitting...' : 'Confirm Override'}
                                </button>
                                <button
                                  onClick={() => { setDocVerOverrideModalOpen(null); setDocVerOverrideRationale(''); }}
                                  className="px-4 py-1.5 bg-zinc-200 text-zinc-600 text-sm rounded hover:bg-zinc-200"
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={() => setDocVerOverrideModalOpen(v.id)}
                              className="px-4 py-1.5 bg-amber-100 text-amber-700 text-sm rounded border border-amber-200 hover:bg-amber-100 font-semibold"
                            >
                              Admin Override
                            </button>
                          )}
                        </div>
                      )}

                      {/* Show override confirmation */}
                      {v.admin_override && (
                        <div className="mt-2 pt-2 border-t border-zinc-200 text-xs text-zinc-600">
                          <span className="font-semibold text-green-700">Overridden</span> by {v.admin_override_by || 'admin'}
                          {v.admin_override_rationale && (
                            <span> -- "{v.admin_override_rationale}"</span>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              </div>
            </details>
          )}

          {/* Action Buttons */}
          <div className="flex justify-center gap-4">
            <button
              onClick={() => setActiveStep('upload')}
              className="px-6 py-3 bg-zinc-50 text-zinc-900 border-2 border-zinc-400 rounded hover:bg-zinc-100 font-semibold"
            >
              📎 Add Further Documentation
            </button>
            <button
              onClick={downloadFileNote}
              className="px-6 py-3 bg-zinc-900 text-white rounded hover:bg-zinc-900 font-semibold"
            >
              📥 Download Audit File Note
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SoFAssessment;
