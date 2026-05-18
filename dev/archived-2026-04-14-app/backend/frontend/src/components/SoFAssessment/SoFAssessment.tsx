import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { API_BASE_URL, authFetch } from '../../lib/api';
import { translateFlag } from '../DocumentVerification/flagTranslations';
import { FileUploader, StatusChip } from '../ui';

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
            {verdictBadge(ver?.verdict)}
          </li>
        );
      })}
    </ol>
  );
}

// FLAG_TRANSLATIONS and translateFlag imported from shared module above

const SoFAssessment: React.FC<SoFAssessmentProps> = ({ matterId }) => {
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

  // Load funds lineage data
  const loadFundsLineageData = async () => {
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/funds-lineage`);
      if (response.ok) {
        const data = await response.json();
        setFundsLineageData(data);
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
        // Flip to manual mode so the user sees the pre-filled form and
        // can verify / tweak before submission.
        setClientInfoInputMethod('manual');
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

  const resetAssessment = async () => {
    if (!confirm('This will delete all uploaded files and reset the assessment. Continue?')) {
      return;
    }

    try {
      await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/reset`, {
        method: 'DELETE',
      });
      setStatus(null);
      setResult(null);
      setActiveStep('upload');
      await fetchStatus();
    } catch (error) {
      console.error('Error resetting assessment:', error);
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

  const buildComprehensiveSummary = (result: AssessmentResult): JSX.Element => {
    const verified_count = result.evidence_matches.filter(e => e.verified).length;
    const total_claims = result.claims.length;
    const best_path = result.funding_paths && result.funding_paths.length > 0 
      ? result.funding_paths.reduce((max, p) => p.coverage > max.coverage ? p : max, result.funding_paths[0])
      : null;
    
    return (
      <div className="space-y-4">
        {/* Client Information Header - REMOVED per user request */}

        {/* Claims Overview */}
        <div>
          <h5 className="font-semibold text-zinc-900 mb-2">Client's SoF Explanation:</h5>
          <ul className="space-y-1 text-sm">
            {result.claims.map((claim, idx) => {
              const evidence = result.evidence_matches[idx];
              const hasBank = evidence?.verified || false;
              const hasDocs = evidence?.document_verified || false;
              const hasDocUploaded = evidence?.document_verification && evidence.document_verification.verification_details?.document_used;
              const docIssues = evidence?.document_verification?.issues || [];
              const confidence = evidence?.document_verification?.confidence || 0;
              
              let status = '';
              let icon = '';
              let details = '';
              
              if (hasBank && hasDocs) {
                status = 'FULLY VERIFIED';
                icon = '✅';
              } else if (hasBank && hasDocUploaded && !hasDocs) {
                // Document uploaded but has issues
                status = 'REQUIRES REVIEW';
                icon = '⚠️';
                const firstIssue = docIssues[0] || 'Document verification incomplete';
                details = ` - ${firstIssue}`;
                if (docIssues.length > 1) {
                  details += ` (+${docIssues.length - 1} more)`;
                }
              } else if (hasBank && !hasDocUploaded) {
                status = 'BANK PAYMENT FOUND - DOCS REQUIRED';
                icon = '⚠️';
              } else if (hasDocs) {
                status = 'DOCS PROVIDED - BANK PAYMENT REQUIRED';
                icon = '⚠️';
                // Add document details
                if (evidence.document_verification?.verification_details?.extracted_data) {
                  const extractedData = evidence.document_verification.verification_details.extracted_data;
                  const amount = extractedData.payment_amount || extractedData.net_proceeds || 
                    (extractedData.distributions && extractedData.distributions[0]?.amount);
                  if (amount) {
                    details = ` - Doc shows £${Number(amount).toLocaleString()}`;
                  }
                }
              } else if (hasDocUploaded && !hasDocs) {
                status = 'DOC UPLOADED - NEEDS REVIEW';
                icon = '⚠️';
                details = ` - ${docIssues[0] || 'Verification incomplete'}`;
              } else {
                status = 'NOT VERIFIED';
                icon = '❌';
              }
              
              return (
                <li key={idx} className="flex flex-col space-y-0.5">
                  <div className="flex items-center space-x-2">
                    <span>{icon}</span>
                    <span>
                      {claim.source_type}: £{claim.expected_amount.toLocaleString()} 
                      <span className="ml-2 font-semibold">[{status}]</span>
                    </span>
                  </div>
                  {details && (
                    <div className="ml-6 text-xs text-zinc-600">
                      {details}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        {/* Evidence Summary */}
        <div>
          <h5 className="font-semibold text-zinc-900 mb-2">Evidence Review:</h5>
          <p className="text-sm mb-2 text-zinc-900">
            Bank transactions: {verified_count}/{total_claims} claims matched to bank statement entries.
          </p>
          <p className="text-sm mb-2 text-zinc-900">
            Supporting documents: {result.evidence_matches.filter(e => e.document_verified).length}/{total_claims} claims verified with source documentation.
          </p>
          
          {/* Show requires review count if any */}
          {result.evidence_matches.filter(e => e.document_verified && (e.document_verification?.confidence || 0) < 0.999).length > 0 && (
            <p className="text-sm mb-2 text-amber-700 font-semibold">
              ⚠️ REQUIRES REVIEW: {result.evidence_matches.filter(e => e.document_verified && (e.document_verification?.confidence || 0) < 0.999).length}/{total_claims} claims require manual review.
            </p>
          )}
          
          <ul className="space-y-2 text-sm">
            {result.evidence_matches.map((evidence, idx) => {
              const hasBank = evidence.verified;
              const hasDocs = evidence.document_verified;
              const hasDocUploaded = evidence.document_verification && evidence.document_verification.verification_details?.document_used;
              const hasDocVerificationAttempt = evidence.document_verification && (hasDocUploaded || (evidence.document_verification.issues && evidence.document_verification.issues.length > 0));
              const docIssues = evidence.document_verification?.issues || [];
              const confidence = evidence.document_verification?.confidence || 0;
              const fullyVerified = hasBank && hasDocs && confidence >= 0.999;
              const requiresReview = hasDocVerificationAttempt && !hasDocs;
              
              return (
                <li key={idx}>
                  {fullyVerified ? (
                    <div>
                      {/* Show different message if manually accepted vs auto-verified */}
                      {evidence.document_verification?.manual_review_status === 'accepted' ? (
                        <div className="font-medium text-green-700">✅ Claim {idx + 1} ({evidence.claim_source}): FULLY VERIFIED (following acceptance of differences)</div>
                      ) : (
                        <div className="font-medium text-green-700">✅ Claim {idx + 1} ({evidence.claim_source}): FULLY VERIFIED</div>
                      )}
                      {evidence.transactions.length > 0 && (
                        <div className="ml-6 mt-1 space-y-1">
                          {evidence.transactions.map((txn: any, tidx: number) => (
                            <div key={tidx} className="text-xs">
                              <div>• Amount: £{txn.amount.toLocaleString()}</div>
                              <div>• Date: {formatDate(txn.date)}</div>
                              <div>• Transaction: {txn.description || 'N/A'}</div>
                              <div>• Counterparty: {txn.counterparty || 'Not specified'}</div>
                            </div>
                          ))}
                          {evidence.document_verification && (
                            <div className="ml-2 mt-2 space-y-1">
                              <div className="text-green-700 font-semibold">
                                ✅ SUPPORTING DOCUMENT VERIFIED
                              </div>
                              {evidence.document_verification.verification_details && (
                                <div className="text-xs text-zinc-600 space-y-0.5">
                                  {evidence.document_verification.verification_details.comparison && (
                                    <div className="mt-1 pt-1 border-t border-zinc-200">
                                      <div className="font-semibold">📊 Evidence Comparison:</div>
                                      <div className="ml-2 space-y-0.5">
                                        {evidence.document_verification.verification_details.comparison.customer_claim && (
                                          <div>👤 Customer: £{evidence.document_verification.verification_details.comparison.customer_claim.claimed_amount?.toLocaleString()}</div>
                                        )}
                                        {evidence.document_verification.verification_details.comparison.document_evidence && (
                                          <>
                                            {evidence.document_verification.verification_details.comparison.document_evidence.distribution_amount && (
                                              <div>✅ Document: £{evidence.document_verification.verification_details.comparison.document_evidence.distribution_amount?.toLocaleString()} distribution</div>
                                            )}
                                            {evidence.document_verification.verification_details.comparison.document_evidence.net_proceeds && (
                                              <div>✅ Document: £{evidence.document_verification.verification_details.comparison.document_evidence.net_proceeds?.toLocaleString()} net proceeds</div>
                                            )}
                                            {evidence.document_verification.verification_details.comparison.document_evidence.payment_date && (
                                              <div>📅 Payment: {evidence.document_verification.verification_details.comparison.document_evidence.payment_date}</div>
                                            )}
                                            {evidence.document_verification.verification_details.comparison.document_evidence.completion_date && (
                                              <div>📅 Completion: {evidence.document_verification.verification_details.comparison.document_evidence.completion_date}</div>
                                            )}
                                          </>
                                        )}
                                        {evidence.document_verification.verification_details.comparison.matches?.amount_matches && (
                                          <div className="text-green-700 font-semibold">✅ Amount matches exactly</div>
                                        )}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                          {/* Show manual acceptance details AFTER document verification */}
                          {evidence.document_verification?.manual_review_status === 'accepted' && (
                            <div className="mt-2 p-2 bg-green-50 border border-green-200 rounded text-xs">
                              <div className="font-semibold text-green-700">✅ Differences Accepted:</div>
                              <div className="ml-2 text-zinc-600">
                                <div>• Accepted by: {evidence.document_verification.manually_accepted_by || 'User'}</div>
                                <div>• Date: {evidence.document_verification.manually_accepted_at ? new Date(evidence.document_verification.manually_accepted_at).toLocaleString('en-GB') : 'N/A'}</div>
                                {evidence.document_verification.acceptance_reason && (
                                  <div>• Rationale: {evidence.document_verification.acceptance_reason}</div>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : requiresReview ? (
                    <div>
                      <div className="font-medium text-amber-700">⚠️ Claim {idx + 1} ({evidence.claim_source}): REQUIRES REVIEW</div>
                      {evidence.transactions.length > 0 && (
                        <div className="ml-6 mt-1 space-y-1">
                          {evidence.transactions.map((txn: any, tidx: number) => (
                            <div key={tidx} className="text-xs">
                              <div>• Amount: £{txn.amount.toLocaleString()}</div>
                              <div>• Date: {formatDate(txn.date)}</div>
                              <div>• Transaction: {txn.description || 'N/A'}</div>
                              <div>• Counterparty: {txn.counterparty || 'Not specified'}</div>
                            </div>
                          ))}
                          {evidence.document_verification && (
                            <div className="ml-2 mt-2 space-y-1">
                              <div className="text-amber-700 font-semibold">
                                ⚠️ DOCUMENT VERIFICATION INCOMPLETE
                              </div>
                              
                              {/* Show what WAS found in the document (checks_passed) */}
                              {evidence.document_verification.verification_details?.checks_passed && 
                               evidence.document_verification.verification_details.checks_passed.length > 0 && (
                                <div className="mt-2">
                                  <div className="font-medium text-zinc-600">Document Details Found:</div>
                                  <div className="ml-2 space-y-0.5 text-xs text-zinc-600">
                                    {evidence.document_verification.verification_details.checks_passed.map((check: string, cidx: number) => (
                                      <div key={cidx}>• {check}</div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              
                              {/* DETAILED DIFFERENCES SECTION (for document-specific issues) */}
                              {evidence.document_verification.differences && evidence.document_verification.differences.length > 0 && (
                                <div className="bg-amber-50 border border-amber-200 rounded p-2 mb-2">
                                  <div className="font-semibold text-amber-700 mb-1">📋 Specific Differences Identified:</div>
                                  <div className="space-y-1">
                                    {evidence.document_verification.differences.map((diff: any, didx: number) => {
                                      const docName = evidence.document_verification?.verification_details?.document_used?.filename || 'document';
                                      const shortDocName = docName.length > 80 ? docName.substring(0, 77) + '...' : docName;
                                      
                                      // Check if this is a funds lineage analysis difference
                                      const isLineageAnalysis = diff.field === 'funds_lineage_analysis';
                                      const isUntracedFunds = diff.field === 'untraced_funds';
                                      const isStatementGap = diff.field === 'statement_gap';
                                      const isStatementCoverage = diff.field === 'statement_coverage';
                                      const isFundsDiscrepancy = diff.field === 'funds_discrepancy';
                                      
                                      // Get real lineage data if available
                                      const lineageSummary = evidence.lineage_summary || fundsLineageData?.funds_lineage?.summary;
                                      
                                      // Calculate percentage to 2 decimal places - ALWAYS recalculate for precision
                                      const totalAmt = lineageSummary?.totalAmount || 0;
                                      const tracedAmt = lineageSummary?.tracedAmount || 0;
                                      const tracedPct = totalAmt > 0 
                                        ? (tracedAmt / totalAmt) * 100
                                        : 0;
                                      const untracedAmt = totalAmt - tracedAmt;
                                      const untracedPct = totalAmt > 0
                                        ? (untracedAmt / totalAmt) * 100
                                        : 0;
                                      
                                      // Helper to format currency with 2 decimal places
                                      const fmtCurrency = (amt: number) => `£${amt.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                                      
                                      return (
                                        <div key={didx} className="text-xs bg-white rounded p-2 border border-status-warning-100">
                                          {isLineageAnalysis ? (
                                            <>
                                              <div className="font-semibold text-amber-700">
                                                {tracedPct >= 80 ? '✅' : tracedPct >= 50 ? '⚠️' : '🔴'} Funds Lineage Analysis
                                              </div>
                                              <div className="text-zinc-600 ml-3">
                                                {tracedPct.toFixed(2)}% of {fmtCurrency(totalAmt)} traced to origin
                                              </div>
                                              
                                              {/* Key Metrics - bullet points under lineage */}
                                              {lineageSummary && (
                                                <div className="ml-3 mt-2 space-y-1 text-zinc-600">
                                                  <div>• <span className="font-medium">Total Amount to be Traced:</span> {fmtCurrency(totalAmt)}</div>
                                                  <div>• <span className="font-medium">Traced to Origin:</span> {fmtCurrency(tracedAmt)} ({tracedPct.toFixed(2)}%)</div>
                                                  <div>• <span className="font-medium text-amber-700">Untraced Total:</span> <span className="text-amber-700">{fmtCurrency(untracedAmt)} ({untracedPct.toFixed(2)}%)</span></div>
                                                  <div>• <span className="font-medium">Statement Period:</span> {(() => {
                                                    const days = lineageSummary.accumulationPeriodDays || 0;
                                                    if (days === 0) return 'N/A';
                                                    const years = Math.floor(days / 365);
                                                    const months = Math.floor((days % 365) / 30);
                                                    const remainingDays = days % 30;
                                                    
                                                    const parts = [];
                                                    if (years > 0) parts.push(`${years} year${years !== 1 ? 's' : ''}`);
                                                    if (months > 0) parts.push(`${months} month${months !== 1 ? 's' : ''}`);
                                                    if (parts.length === 0 && remainingDays > 0) parts.push(`${remainingDays} day${remainingDays !== 1 ? 's' : ''}`);
                                                    
                                                    return parts.length > 0 ? parts.join(' ') : 'Less than 1 day';
                                                  })()}</div>
                                                </div>
                                              )}
                                            </>
                                          ) : isUntracedFunds ? (
                                            <>
                                              <div className="font-semibold text-amber-700">
                                                ⚠️ Untraced Funds
                                              </div>
                                              <div className="text-zinc-600 ml-3">
                                                {(() => {
                                                  // Parse the amount and date from the issue text
                                                  const match = diff.issue?.match(/£([\d,]+(?:\.\d+)?)\s+on\s+(\d{4}-\d{2}-\d{2}|\d{2}\/\d{2}\/\d{4})/);
                                                  const amount = match ? match[1] : diff.amount || '0';
                                                  const dateStr = match ? match[2] : diff.date || 'unknown';
                                                  // Format date as DD/MM/YYYY
                                                  let formattedDate = dateStr;
                                                  if (dateStr && dateStr.includes('-')) {
                                                    const parts = dateStr.split('-');
                                                    if (parts.length === 3) {
                                                      formattedDate = `${parts[2]}/${parts[1]}/${parts[0]}`;
                                                    }
                                                  }
                                                  // Get transaction ID if available
                                                  const txnId = diff.transaction_id || diff.id || 'N/A';
                                                  return `Untraced: £${amount} on ${formattedDate}, Transaction ID: ${txnId}`;
                                                })()}
                                              </div>
                                              <div className="text-zinc-600 ml-3 italic">{diff.found || diff.description || 'Source unknown'}</div>
                                            </>
                                          ) : isFundsDiscrepancy ? (
                                            <>
                                              <div className="font-semibold text-red-700">
                                                🔴 Funds Discrepancy
                                              </div>
                                              <div className="text-zinc-600 ml-3">
                                                {diff.issue}
                                              </div>
                                              <div className="text-zinc-600 ml-3">
                                                {diff.expected}
                                              </div>
                                              <div className="text-red-700 ml-3 font-semibold">
                                                → {diff.found}
                                              </div>
                                            </>
                                          ) : isStatementGap ? (
                                            <>
                                              <div className="font-semibold text-zinc-700">
                                                📋 Additional Statements Required
                                              </div>
                                              <div className="text-zinc-600 ml-3">
                                                {(() => {
                                                  const match = diff.issue?.match(/£([\d,]+(?:\.\d+)?)\s+on\s+(\d{4}-\d{2}-\d{2})/);
                                                  const amount = match ? match[1] : diff.amount || '0';
                                                  const dateStr = match ? match[2] : diff.date || 'unknown';
                                                  let formattedDate = dateStr;
                                                  if (dateStr && dateStr.includes('-')) {
                                                    const parts = dateStr.split('-');
                                                    if (parts.length === 3) {
                                                      formattedDate = `${parts[2]}/${parts[1]}/${parts[0]}`;
                                                    }
                                                  }
                                                  const txnId = diff.transaction_id || diff.id || 'N/A';
                                                  return `£${amount} on ${formattedDate} (ID: ${txnId})`;
                                                })()}
                                              </div>
                                              <div className="text-zinc-500 ml-3 font-medium">
                                                → {diff.expected || `Need statements from ${diff.gap_account || 'source account'}`}
                                              </div>
                                              <div className="text-zinc-600 ml-3 italic">{diff.found || 'Transfer identified but source account statements needed'}</div>
                                            </>
                                          ) : isStatementCoverage ? (
                                            <>
                                              <div className="font-semibold text-zinc-600">
                                                📅 Statement Coverage
                                              </div>
                                              <div className="text-zinc-600 ml-3">{diff.found}</div>
                                            </>
                                          ) : (
                                            <>
                                              <div className="font-semibold text-amber-700">
                                                {diff.severity === 'missing' ? '🔴 Missing' : '⚠️ Mismatch'}: {diff.field.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                                              </div>
                                              <div className="text-zinc-600 ml-3">{diff.issue} (from {shortDocName})</div>
                                            </>
                                          )}
                                          {diff.accepted && (
                                            <div className="text-green-700 ml-3 mt-1">
                                              ✅ Accepted by {diff.accepted_by} on {new Date(diff.accepted_at).toLocaleDateString('en-GB')}
                                            </div>
                                          )}
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              )}
                              
                              {/* ISSUES SECTION (for non-document-specific issues like unknown source types) */}
                              {(!evidence.document_verification.differences || evidence.document_verification.differences.length === 0) && 
                               evidence.document_verification.issues && evidence.document_verification.issues.length > 0 && (
                                <div className="bg-amber-50 border border-amber-200 rounded p-2 mb-2">
                                  <div className="font-semibold text-amber-700 mb-1">📋 Specific Differences Identified:</div>
                                  <div className="space-y-1">
                                    {evidence.document_verification.issues.map((issue: string, iidx: number) => (
                                      <div key={iidx} className="text-xs bg-white rounded p-1 border border-status-warning-100">
                                        <div className="font-semibold text-amber-700">
                                          ⚠️ Issue: {issue}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              
                              {/* MANUAL REVIEW STATUS - Show for bank transactions OR savings claims with lineage */}
                              {((evidence.transactions && evidence.transactions.length > 0) || 
                                (evidence.funds_lineage_verified || evidence.lineage_summary)) && 
                               evidence.document_verification.manual_review_status && (
                                <div className={`${evidence.document_verification.manual_review_status === 'accepted' ? 'bg-green-50 border-green-200' : 'bg-zinc-50 border-zinc-200'} border rounded p-2 mb-2`}>
                                  <div className="text-xs">
                                    {evidence.document_verification.manual_review_status === 'accepted' ? (
                                      <>
                                        <div className="font-semibold text-green-700 text-sm mb-1">✅ VERIFIED - Claim Complete</div>
                                        <div className="ml-2 space-y-0.5">
                                          <div className="text-green-700 font-medium">
                                            {evidence.document_verification.verification_note || 'Marked as verified post user acceptance of differences'}
                                          </div>
                                          {evidence.document_verification.manually_accepted_by && (
                                            <div className="text-zinc-600">Accepted by: {evidence.document_verification.manually_accepted_by}</div>
                                          )}
                                          {evidence.document_verification.manually_accepted_at && (
                                            <div className="text-zinc-600">Date: {new Date(evidence.document_verification.manually_accepted_at).toLocaleString('en-GB')}</div>
                                          )}
                                          {evidence.document_verification.acceptance_reason && (
                                            <div className="text-zinc-600 italic mt-1">Reason: {evidence.document_verification.acceptance_reason}</div>
                                          )}
                                        </div>
                                      </>
                                    ) : (
                                      <>
                                        <div className="font-semibold text-zinc-700">Manual Review Status:</div>
                                        <div className="ml-2 text-amber-700">⏳ Pending Manual Review</div>
                                      </>
                                    )}
                                  </div>
                                </div>
                              )}
                              
                              {/* ACCEPT DIFFERENCE BUTTON - Show for bank transactions OR savings claims with lineage */}
                              {((evidence.transactions && evidence.transactions.length > 0) || 
                                (evidence.funds_lineage_verified || evidence.lineage_summary)) && 
                               evidence.document_verification.manual_review_status === 'pending' && (
                                <div className="mt-2">
                                  <button
                                    onClick={async () => {
                                      const reason = prompt('Please provide a reason for accepting these differences (optional):');
                                      if (reason !== null) { // null means cancelled
                                        try {
                                          const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${result.matter_id}/sof-assessment/accept-differences`, {
                                            method: 'POST',
                                            body: JSON.stringify({
                                              claim_index: idx,
                                              accepted_by: 'Current User', // TODO: Get from auth context
                                              reason: reason || 'Manual review completed - differences accepted'
                                            })
                                          });
                                          
                                          if (response.ok) {
                                            alert('Differences accepted successfully!');
                                            // Refresh the assessment data
                                            window.location.reload();
                                          } else {
                                            const error = await response.json();
                                            alert(`Error: ${error.detail || 'Failed to accept differences'}`);
                                          }
                                        } catch (err) {
                                          alert(`Error: ${err}`);
                                        }
                                      }
                                    }}
                                    className="px-3 py-1.5 bg-zinc-900 hover:bg-zinc-900 text-white text-xs font-medium rounded transition-colors"
                                  >
                                    ✓ Accept Differences
                                  </button>
                                  <p className="text-xs text-zinc-600 mt-1 italic">
                                    Review the differences above and click to accept if satisfied upon manual review
                                  </p>
                                </div>
                              )}

                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : hasBank && !hasDocVerificationAttempt ? (
                    <div>
                      <div className="font-medium">⚠️ Claim {idx + 1} ({evidence.claim_source}): Bank payment found - SOURCE DOCS REQUIRED</div>
                      {evidence.transactions.length > 0 && (
                        <div className="ml-6 mt-1 space-y-1">
                          {evidence.transactions.map((txn: any, tidx: number) => (
                            <div key={tidx} className="text-xs">
                              <div>• Amount: £{txn.amount.toLocaleString()}</div>
                              <div>• Date: {formatDate(txn.date)}</div>
                              <div>• Transaction: {txn.description || 'N/A'}</div>
                              <div>• Counterparty: {txn.counterparty || 'Not specified'}</div>
                              <div className="ml-2 text-zinc-900 font-semibold mt-1">
                                ⚠️ REQUIRES: Source documentation to prove legitimacy
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : hasDocs ? (
                    <div>
                      <div className="font-medium text-amber-700">⚠️ Claim {idx + 1} ({evidence.claim_source}): DOCUMENT VERIFIED - BANK PAYMENT REQUIRED</div>
                      
                      {/* DEBUG: Log what we have */}
                      {console.log('=== V17 DEBUG: Claim', idx + 1, '===', {
                        hasDocs,
                        document_verification: evidence.document_verification,
                        verification_details: evidence.document_verification?.verification_details,
                        extracted_data: evidence.document_verification?.verification_details?.extracted_data,
                        hasExtractedData: !!evidence.document_verification?.verification_details?.extracted_data
                      })}
                      
                      {/* Show document details with intelligent verification comparisons */}
                      <div className="ml-6 mt-1 space-y-1 text-xs">
                        {evidence.document_verification?.verification_details?.extracted_data ? (() => {
                          const extracted = evidence.document_verification.verification_details.extracted_data;
                          const comparison = evidence.document_verification.verification_details?.comparison;
                          const claim = result.claims[idx];
                          const clientInfo = result.client_info || {};
                          
                          // Get document values
                          const docAmount = extracted.payment_amount || extracted.net_proceeds || 
                            (extracted.distributions?.[0]?.amount);
                          const docDate = extracted.transfer_date || extracted.completion_date || extracted.payment_date;
                          const docBeneficiary = extracted.executor_beneficiary || extracted.distributions?.[0]?.beneficiary || extracted.vendor_name;
                          const docAccountLast4 = extracted.account_last_4;
                          
                          // Get claim/client values for comparison
                          const claimAmount = evidence.expected_amount || claim?.expected_amount;
                          const claimDate = claim?.expected_date;
                          const clientName = clientInfo.client_name || clientInfo.name || '';
                          
                          // Perform intelligent comparisons
                          const amountMatches = docAmount && claimAmount && 
                            Math.abs(Number(docAmount) - Number(claimAmount)) < Number(claimAmount) * 0.01;
                          
                          const dateMatches = docDate && claimDate && 
                            (docDate.includes(claimDate) || claimDate.includes(docDate) || 
                             new Date(docDate).getTime() === new Date(claimDate).getTime());
                          
                          const beneficiaryMatches = docBeneficiary && clientName && 
                            (docBeneficiary.toLowerCase().includes(clientName.split(' ')[0]?.toLowerCase()) ||
                             clientName.toLowerCase().includes(docBeneficiary.split(' ')[0]?.toLowerCase()));
                          
                          return (
                            <>
                              {/* Amount with match check */}
                              {docAmount && (
                                <div>
                                  • Amount: £{Number(docAmount).toLocaleString()}
                                  {amountMatches ? (
                                    <span className="text-green-700 font-semibold ml-2">✓ Matches SoF claim</span>
                                  ) : claimAmount && Number(docAmount) > Number(claimAmount) ? (
                                    <span className="text-green-700 font-semibold ml-2">✓ Higher than SoF claim (£{Number(claimAmount).toLocaleString()})</span>
                                  ) : claimAmount ? (
                                    <span className="text-amber-700 font-semibold ml-2">⚠️ Lower than SoF claim (£{Number(claimAmount).toLocaleString()})</span>
                                  ) : null}
                                </div>
                              )}
                              
                              {/* Date with match check */}
                              {docDate && (
                                <div>
                                  • Date: {docDate}
                                  {dateMatches ? (
                                    <span className="text-green-700 font-semibold ml-2">✓ Matches SoF claim</span>
                                  ) : claimDate ? (
                                    <span className="text-amber-700 font-semibold ml-2">⚠️ Differs from SoF claim ({claimDate})</span>
                                  ) : null}
                                </div>
                              )}
                              
                              {/* Property address */}
                              {extracted.property_address && (
                                <div>• Property: {extracted.property_address}</div>
                              )}
                              
                              {/* Estate/Deceased */}
                              {extracted.deceased_name && (
                                <div>• Estate of: {extracted.deceased_name}</div>
                              )}
                              
                              {/* Beneficiary/Vendor with client name match check */}
                              {docBeneficiary && (
                                <div>
                                  • {extracted.vendor_name ? 'Vendor' : 'Beneficiary'}: {docBeneficiary}
                                  {beneficiaryMatches ? (
                                    <span className="text-green-700 font-semibold ml-2">✓ Matches client name</span>
                                  ) : clientName ? (
                                    <span className="text-amber-700 font-semibold ml-2">⚠️ Does not match client name ({clientName})</span>
                                  ) : null}
                                </div>
                              )}
                              
                              {/* Bank details - only show match if we can verify against statement */}
                              {(extracted.bank_name || docAccountLast4) && (
                                <div>
                                  • Bank: {extracted.bank_name || 'Unknown'} {docAccountLast4 ? `****${docAccountLast4}` : ''}
                                </div>
                              )}
                              
                              {/* Solicitor */}
                              {extracted.solicitor_firm && (
                                <div>• Solicitor: {extracted.solicitor_firm}</div>
                              )}
                              
                              {/* Reference numbers */}
                              {extracted.probate_reference && (
                                <div>• Probate Ref: {extracted.probate_reference}</div>
                              )}
                              {extracted.title_number && (
                                <div>• Title Number: {extracted.title_number}</div>
                              )}
                              {extracted.transfer_reference && (
                                <div>• Transfer Ref: {extracted.transfer_reference}</div>
                              )}
                            </>
                          );
                        })() : (
                          <div className="text-amber-700">
                            <div>⚠️ Document verified but detailed extraction data not available</div>
                            <div className="text-xs text-zinc-400 mt-1">
                              Debug: verification_details keys: {JSON.stringify(Object.keys(evidence.document_verification?.verification_details || {}))}
                            </div>
                          </div>
                        )}
                      </div>
                      
                      {/* Document Verification Status */}
                      <div className="ml-6 mt-2 text-xs">
                        <div className="text-green-700 font-semibold">
                          ✅ DOCUMENT VERIFICATION COMPLETE
                        </div>
                      </div>
                      
                      {/* Missing Bank Transaction Warning */}
                      <div className="ml-6 mt-2 bg-amber-50 border border-amber-200 rounded p-3">
                        <div className="flex items-center gap-2 font-semibold text-amber-700 mb-2">
                          <span>⚠️</span>
                          <span>Action Required:</span>
                        </div>
                        <div className="flex items-start gap-2">
                          <span className="text-amber-700 mt-0.5">•</span>
                          <div>
                            <div className="font-medium text-amber-700">Missing: Bank Transaction</div>
                            <div className="text-zinc-600">No matching deposit found in bank statement for £{evidence.expected_amount?.toLocaleString() || 'N/A'}</div>
                          </div>
                        </div>
                      </div>
                      
                      {/* NOTE: No Manual Review option here - bank transaction must verify the amount first */}
                    </div>
                  ) : (
                    <>⚠️ Claim {idx + 1} ({evidence.claim_source}): NOT VERIFIED - No bank transaction or supporting documents</>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        {/* Transaction Review Summary */}
        {result.transaction_review_summary && result.transaction_review_summary.total_alerts > 0 && (
          <div>
            <h5 className="font-semibold text-zinc-900 mb-2">Automated Transaction Monitoring:</h5>
            <p className="text-sm mb-2">
              System identified {result.transaction_review_summary.total_alerts} alert(s): 
              {' '}{result.transaction_review_summary.critical_alerts} CRITICAL, 
              {' '}{result.transaction_review_summary.high_alerts} HIGH, 
              {' '}{result.transaction_review_summary.medium_alerts} MEDIUM.
            </p>
            {result.transaction_review_summary.key_concerns && result.transaction_review_summary.key_concerns.length > 0 && (
              <>
                <p className="text-sm font-medium mb-1">Key concerns:</p>
                <ul className="ml-4 space-y-1 text-sm mb-2">
                  {result.transaction_review_summary.key_concerns.map((concern, idx) => (
                    <li key={idx}>• {concern}</li>
                  ))}
                </ul>
              </>
            )}
            {Object.keys(alertSatisfied).some(key => alertSatisfied[parseInt(key)]) && (
              <>
                <p className="text-sm font-medium mt-2 mb-1 text-green-700">✓ Satisfied Alerts:</p>
                <ul className="ml-4 space-y-1 text-sm mb-2">
                  {(result.transaction_review_summary.alerts || result.transaction_review_summary.alert_details || []).map((alert, idx) => (
                    alertSatisfied[idx] && (
                      <li key={idx} className="text-green-700">
                        • Alert {idx + 1}: {alert.reasons?.[0] || 'AML concern'} 
                        {alertRationales[idx] && <span className="text-zinc-600 ml-2">({alertRationales[idx]})</span>}
                      </li>
                    )
                  ))}
                </ul>
              </>
            )}
            <p className="text-sm italic">Full alert details available in Transaction Review tab. These findings materially impact the SoF assessment.</p>
          </div>
        )}

        {/* Document Verification Summary */}
        {result.document_verification && (
          <div>
            <h5 className="font-semibold text-zinc-900 mb-2">📋 Document Verification:</h5>
            <p className="text-sm mb-1">
              Overall verification rate: <span className={`font-bold ${
                result.document_verification.overall_verification_rate >= 0.75 ? 'text-green-700'
                : result.document_verification.overall_verification_rate >= 0.5 ? 'text-amber-700' 
                : 'text-red-700'
              }`}>{Math.round(result.document_verification.overall_verification_rate * 100)}%</span>
            </p>
            {result.document_verification.verifications && result.document_verification.verifications.length > 0 ? (
              <div className="space-y-1 text-sm">
                {result.document_verification.verifications.map((ver: any, idx: number) => (
                  <div key={idx} className="ml-2">
                    {ver.verified ? '✅' : '❌'} {ver.claim_source || ver.document_type || `Document ${idx + 1}`}
                    {ver.confidence !== undefined && (
                      <span className="text-zinc-400 ml-1">(confidence: {Math.round((ver.confidence || 0) * 100)}%)</span>
                    )}
                    {ver.issues && ver.issues.length > 0 && (
                      <span className="text-amber-700 ml-1">— {ver.issues[0]}</span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              result.document_verification.missing_documents && result.document_verification.missing_documents.length > 0 && (
                <div className="text-sm text-amber-700 mt-1">
                  {result.document_verification.missing_documents.map((msg: string, idx: number) => (
                    <div key={idx} className="ml-2">⚠️ {msg}</div>
                  ))}
                </div>
              )
            )}
          </div>
        )}

        {/* Document Verification Summary (inline) */}
        {docVerificationSummary && docVerificationSummary.total_documents > 0 && (
          <div>
            <h5 className="font-semibold text-zinc-900 mb-2">Document Verification:</h5>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-sm">
                {docVerificationSummary.total_documents} document{docVerificationSummary.total_documents !== 1 ? 's' : ''} checked
              </span>
              {docVerificationSummary.has_blocking_issues ? (
                <span className="px-2 py-0.5 text-xs font-bold rounded bg-red-100 text-red-700 border border-red-200">BLOCKED</span>
              ) : docVerificationSummary.suspicious_count > 0 ? (
                <span className="px-2 py-0.5 text-xs font-bold rounded bg-amber-100 text-amber-700 border border-amber-200">REVIEW</span>
              ) : (
                <span className="px-2 py-0.5 text-xs font-bold rounded bg-green-100 text-green-700 border border-green-200">VERIFIED</span>
              )}
            </div>
            {(docVerificationSummary.verifications || []).map((v: any, idx: number) => {
              const verdictIcon = v.verdict === 'Verified' ? '✅' : v.verdict === 'Suspicious' ? '⚠️' : '🚫';
              const verdictLabel = v.verdict === 'Verified' ? 'Passed' : v.verdict === 'Suspicious' ? 'Needs review' : 'Failed';
              const verdictColor = v.verdict === 'Verified' ? 'text-green-700'
                : v.verdict === 'Suspicious' ? 'text-amber-700' : 'text-red-700';
              return (
                <div key={idx} className="text-sm ml-2 mb-1">
                  <span>{verdictIcon} {v.filename}: <span className={`font-semibold ${verdictColor}`}>{verdictLabel}</span></span>
                  {v.admin_override && <span className="ml-1 text-xs text-zinc-500">[Admin Override]</span>}
                </div>
              );
            })}
            <p className="text-sm italic mt-1 text-zinc-400">Full verification details available below.</p>
          </div>
        )}
      </div>
    );
  };

  const renderStructuredRationale = (result: AssessmentResult) => {
    // Parse the rationale into sections
    const rationale = result.outcome.rationale;
    const sections = rationale.split('===').filter(s => s.trim());
    
    return (
      <div className="space-y-6">
        {sections.map((section, idx) => {
          const lines = section.trim().split('\n');
          const title = lines[0].trim();
          const content = lines.slice(1).join('\n');
          
          // Determine section type
          // Skip CLIENT INFORMATION section - not needed in UI
          if (title.includes('CLIENT INFORMATION')) {
            return null; // Hidden
          } else if (title.includes('SOURCE OF FUNDS')) {
            return renderSoFSection(content, result);
          } else if (title.includes('TRANSACTION REVIEW')) {
            return renderTransactionReviewSection(content, result);
          }
          // Don't render Final Assessment here - it's in the top decision box
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
          <h3 className="text-lg font-bold text-zinc-900">👤 Client Information</h3>
        </div>
        
        {/* Client Details */}
        <div className="px-6 py-4">
          <pre className="whitespace-pre-wrap text-sm text-zinc-900 font-mono">{content}</pre>
        </div>
      </div>
    );
  };

  const renderSoFSection = (content: string, result: AssessmentResult) => {
    // Extract status lines (both old and new formats)
    const bankPaymentMatch = content.match(/BANK PAYMENT STATUS:([^\n]+)/);
    const docStatusMatch = content.match(/DOCUMENTATION STATUS:([^\n]+)/);
    const overallMatch = content.match(/OVERALL STATUS:([^\n]+)/); // Legacy format
    
    const bankStatus = bankPaymentMatch ? bankPaymentMatch[1].trim() : '';
    const docStatus = docStatusMatch ? docStatusMatch[1].trim() : '';
    const overallStatus = overallMatch ? overallMatch[1].trim() : '';
    
    const displayStatus = bankStatus || overallStatus;
    const isGood = displayStatus.includes('✅') || displayStatus.includes('VERIFIED');
    const isPartial = displayStatus.includes('⚠️') || displayStatus.includes('Partial');
    
    return (
      <div key="sof" className="bg-white border border-zinc-200 rounded-md overflow-hidden">
        {/* Header */}
        <div className="bg-zinc-50 border-b border-zinc-200 px-6 py-4">
          <h3 className="text-lg font-bold text-zinc-900">📊 Source of Funds Analysis</h3>
        </div>
        
        {/* Status Lines */}
        <div className="bg-zinc-50 border-b border-zinc-200 px-6 py-4">
          {bankStatus && (
            <p className="font-semibold mb-2 text-zinc-900">
              {bankStatus}
            </p>
          )}
          {docStatus && (
            <div>
              <p className="font-semibold text-zinc-900 mb-1">{docStatus}</p>
              {content.includes('Bank payments alone are INSUFFICIENT') && (
                <p className="text-sm text-zinc-900 italic ml-4">
                  Bank payments alone are INSUFFICIENT for AML compliance.
                </p>
              )}
            </div>
          )}
          {!bankStatus && overallStatus && (
            <p className="font-semibold text-zinc-900">
              {overallStatus}
            </p>
          )}
        </div>
        
        {/* Claims Table */}
        <div className="px-6 py-4">
          <h4 className="text-sm font-bold text-zinc-600 mb-3">Claim-by-Claim Analysis</h4>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-brand-muted">
              <thead className="bg-zinc-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-600 uppercase tracking-wider">Claim</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-600 uppercase tracking-wider">Outreach Questions</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-zinc-600 uppercase tracking-wider">Summary</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-brand-muted">
                {result.claims.map((claim, idx) => {
                  const evidence = result.evidence_matches[idx];
                  const verified = evidence?.verified || false;
                  const document_verified = evidence?.document_verified || false;
                  const transactions = evidence?.transactions || [];
                  const confidence = evidence?.document_verification?.confidence || 0;
                  const manuallyAccepted = evidence?.document_verification?.manual_review_status === 'accepted';
                  // Check if there's a document upload attempt (either file or issues)
                  const hasDocUploaded = evidence?.document_verification?.verification_details?.document_used;
                  const hasDocVerificationAttempt = hasDocUploaded || 
                    (evidence?.document_verification?.issues && evidence.document_verification.issues.length > 0);
                  // Only show as FULLY VERIFIED if confidence is 100% (>= 0.999 to account for floating point) OR manually accepted
                  const fullyVerified = (verified && document_verified && confidence >= 0.999) || manuallyAccepted;
                  const requiresReview = hasDocVerificationAttempt && !fullyVerified;
                  
                  return (
                    <tr key={idx} className="hover:bg-zinc-50">
                      <td className="px-4 py-3 text-sm text-zinc-900 font-medium">
                        {claim.source_type} £{claim.expected_amount.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {fullyVerified ? (
                          <div className="text-green-700">
                            <div>✓ Verified</div>
                            {evidence?.document_verification?.verification_details?.document_used?.filename && (
                              <div className="text-xs text-zinc-600 mt-1">
                                Doc: {evidence.document_verification.verification_details.document_used.filename.slice(0, 30)}{evidence.document_verification.verification_details.document_used.filename.length > 30 ? '...' : ''}
                              </div>
                            )}
                          </div>
                        ) : manuallyAccepted ? (
                          <div className="text-green-700 text-xs">
                            <div>✓ Verified via manual acceptance</div>
                          </div>
                        ) : document_verified ? (
                          <div className="text-zinc-900">
                            {evidence?.document_verification?.verification_details?.document_used?.filename && (
                              <div className="text-sm">
                                📄 {evidence.document_verification.verification_details.document_used.filename.slice(0, 25)}{evidence.document_verification.verification_details.document_used.filename.length > 25 ? '...' : ''}
                              </div>
                            )}
                            {evidence?.issues && evidence.issues.length > 0 && (
                              <div className="text-xs text-amber-700 mt-1 space-y-0.5">
                                {evidence.issues.slice(0, 3).map((issue: string, issueIdx: number) => (
                                  <div key={issueIdx}>⚠️ {issue}</div>
                                ))}
                                {evidence.issues.length > 3 && (
                                  <div className="text-zinc-400">+ {evidence.issues.length - 3} more issues</div>
                                )}
                              </div>
                            )}
                          </div>
                        ) : verified ? (
                          <span className="text-zinc-900">
                            Request {
                              claim.source_type.toLowerCase().includes('inheritance') ? 'probate grant' :
                              claim.source_type.toLowerCase().includes('property') ? 'completion statement' :
                              claim.source_type.toLowerCase().includes('loan') ? 'loan agreement' :
                              claim.source_type.toLowerCase().includes('business') ? 'sale agreement' :
                              'documentation'
                            }
                          </span>
                        ) : (
                          <span className="text-zinc-900">
                            Request {
                              claim.source_type.toLowerCase().includes('inheritance') ? 'probate grant' :
                              claim.source_type.toLowerCase().includes('property') ? 'completion statement' :
                              claim.source_type.toLowerCase().includes('loan') ? 'loan agreement' :
                              claim.source_type.toLowerCase().includes('business') ? 'sale agreement' :
                              'documentation'
                            }
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {fullyVerified ? (
                          <div className="space-y-1">
                            {manuallyAccepted ? (
                              <>
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                                  ✅ VERIFIED (following acceptance of differences)
                                </span>
                                <div className="bg-green-50 rounded p-2 mt-1 text-xs">
                                  <div className="text-green-700 font-semibold mb-1">Acceptance Details:</div>
                                  <div className="text-zinc-600">
                                    <div>• Accepted by: {evidence?.document_verification?.manually_accepted_by || 'User'}</div>
                                    <div>• Date: {evidence?.document_verification?.manually_accepted_at 
                                      ? new Date(evidence.document_verification.manually_accepted_at).toLocaleString('en-GB', {
                                          day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
                                        }) 
                                      : 'N/A'}</div>
                                    {evidence?.document_verification?.acceptance_reason && (
                                      <div>• Rationale: {evidence.document_verification.acceptance_reason}</div>
                                    )}
                                  </div>
                                </div>
                              </>
                            ) : (
                              <>
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                                  ✅ FULLY VERIFIED
                                </span>
                                {/* Show verified data summary */}
                                {evidence?.document_verification?.verification_details?.extracted_data && (
                                  <div className="bg-green-50 rounded p-2 mt-1 text-xs">
                                    {Object.entries(evidence.document_verification.verification_details.extracted_data)
                                      .filter(([key]) => ['payment_amount', 'net_proceeds', 'completion_date', 'deceased_name', 'payment_date'].includes(key))
                                      .slice(0, 3)
                                      .map(([key, value]: [string, any]) => (
                                        <div key={key} className="flex justify-between py-0.5">
                                          <span className="text-green-700">{key.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}:</span>
                                          <span className="text-green-700 font-medium ml-2">
                                            {typeof value === 'number' ? `£${value.toLocaleString()}` : String(value).slice(0, 20)}
                                          </span>
                                        </div>
                                      ))
                                    }
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                        ) : requiresReview ? (
                          <div className="text-sm space-y-1">
                            <div className="text-amber-700 font-semibold mb-1">
                              ⚠️ Review Required
                            </div>
                            {/* Simplified: Just show bullet points of what's missing/different */}
                            <ul className="list-disc list-inside text-xs text-zinc-600 space-y-0.5">
                              {evidence?.document_verification?.differences && evidence.document_verification.differences.length > 0 ? (
                                evidence.document_verification.differences.map((diff: any, diffIdx: number) => (
                                  <li key={diffIdx}>
                                    <span className="font-medium">{diff.field.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}:</span> {diff.issue}
                                    {/* Show full details for funds_discrepancy */}
                                    {diff.field === 'funds_discrepancy' && (
                                      <div className="ml-4 mt-1 text-xs space-y-0.5">
                                        <div className="text-zinc-600">{diff.expected}</div>
                                        <div className="text-red-700 font-medium">→ {diff.found}</div>
                                      </div>
                                    )}
                                  </li>
                                ))
                              ) : evidence?.issues && evidence.issues.length > 0 ? (
                                evidence.issues.map((issue: string, issueIdx: number) => (
                                  <li key={issueIdx}>{issue}</li>
                                ))
                              ) : (
                                <li>Document verification incomplete</li>
                              )}
                            </ul>
                          </div>
                        ) : verified ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium bg-zinc-200 text-zinc-900">
                            ⚠️ Payment found, docs req'd
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                            ❌ MISSING
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
        

      </div>
    );
  };

  const renderTransactionReviewSection = (content: string, result: AssessmentResult) => {
    const overallMatch = content.match(/OVERALL STATUS:([^\n]+)/);
    const overallStatus = overallMatch ? overallMatch[1].trim() : '';
    
    const hasCritical = overallStatus.includes('CRITICAL') || content.includes('CRITICAL');
    
    return (
      <div key="tr" className="bg-white border border-zinc-200 rounded-md overflow-hidden">
        {/* Header */}
        <div className="bg-zinc-50 border-b border-zinc-200 px-6 py-4">
          <h3 className="text-lg font-bold text-zinc-900">🚨 Automated Transaction Review</h3>
        </div>
        
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
        

      </div>
    );
  };


  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900">Source of Funds Assessment</h2>
        </div>
        {status && status.status !== 'no_data' && (
          <button
            onClick={resetAssessment}
            className="px-4 py-2 text-sm text-red-700 hover:text-red-700 border border-red-200 rounded hover:bg-red-50"
          >
            Reset Assessment
          </button>
        )}
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
            📤 Upload Documents
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
            📊 Assessment Results
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
            {/* Client Info — tile #1 */}
            <details
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
                {renderUploadedList(status, fileVerificationResults, 'client_info', 'No client info provided yet.')}
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

            {/* Bank Statements — tile #2 */}
            <details
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
              {renderUploadedList(status, fileVerificationResults, 'bank_statement', 'No bank statements uploaded yet.')}

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

            {/* Supporting Documents — tile #3 */}
            <details
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
              {renderUploadedList(status, fileVerificationResults, 'supporting_doc', 'No supporting documents uploaded yet.')}

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
                {loading ? '⏳ Running Assessment...' : '🚀 Run SoF Assessment'}
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
            const total = result.evidence_matches?.length || 0;
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
                <div className="px-6 py-4 border-t border-zinc-100 text-sm text-zinc-700 leading-relaxed">
                  {buildComprehensiveSummary(result)}
                </div>
              </div>
            );
          })()}

          {/* Parsed Rationale Sections */}
          {renderStructuredRationale(result)}

          {/* ============================================================ */}
          {/* FUNDS LINEAGE SECTION (always shown, matches sibling tile     */}
          {/* styling — header band with bg-zinc-50, emoji + bold title)   */}
          {/* ============================================================ */}
          <div className="bg-white border border-zinc-200 rounded-md overflow-hidden">
            <div className="bg-zinc-50 border-b border-zinc-200 px-6 py-4 flex items-center justify-between">
              <h3 className="text-lg font-bold text-zinc-900">🔗 Funds Lineage</h3>
              <Link
                to={`/matters/${matterId}?tab=funds-lineage`}
                className="text-xs text-zinc-700 hover:text-zinc-900 underline-offset-2 hover:underline"
              >
                Open full lineage →
              </Link>
            </div>

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
                        <div className="mt-1 text-[11px] uppercase tracking-wider text-zinc-400">Untraced</div>
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
          </div>

          {/* ============================================================ */}
          {/* DOCUMENT VERIFICATION SECTION (UNIFIED)                      */}
          {/* ============================================================ */}
          {docVerificationSummary && docVerificationSummary.total_documents > 0 && (
            <div className="bg-white border border-zinc-200 rounded-md p-6">
              <h3 className="text-lg font-bold text-zinc-900 mb-4 flex items-center gap-2">
                Document Verification
                {docVerificationSummary.has_blocking_issues ? (
                  <span className="ml-2 px-2 py-0.5 text-xs font-bold rounded bg-red-100 text-red-700 border border-red-200">BLOCKED</span>
                ) : docVerificationSummary.suspicious_count > 0 ? (
                  <span className="ml-2 px-2 py-0.5 text-xs font-bold rounded bg-amber-100 text-amber-700 border border-amber-200">REVIEW</span>
                ) : (
                  <span className="ml-2 px-2 py-0.5 text-xs font-bold rounded bg-green-100 text-green-700 border border-green-200">VERIFIED</span>
                )}
              </h3>

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
                    ? { label: isCSVDoc ? 'CHECKS PASSED' : 'VERIFIED', sublabel: 'No issues detected', borderClass: 'border-green-200', bgClass: 'bg-green-50', textClass: 'text-green-700', badgeClass: 'bg-green-100 text-green-700' }
                    : isSuspicious
                    ? { label: 'NEEDS REVIEW', sublabel: 'Issues found that require attention', borderClass: 'border-amber-200', bgClass: 'bg-amber-50', textClass: 'text-amber-700', badgeClass: 'bg-amber-100 text-amber-700' }
                    : { label: 'FAILED', sublabel: 'Serious concerns identified', borderClass: 'border-red-200', bgClass: 'bg-red-50', textClass: 'text-red-700', badgeClass: 'bg-red-100 text-red-700' };

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

                      {/* Issues list — plain English */}
                      {actionableFlags.length > 0 && !isVerified && (
                        <div className="border-t border-zinc-200 mx-4 pt-3 pb-4 space-y-2">
                          <div className="text-xs font-semibold text-zinc-900 uppercase tracking-wide mb-2">Why this document was flagged</div>

                          {criticalFlags.map((f: any, fi: number) => {
                            const t = translateFlag(f);
                            return (
                              <div key={`c-${fi}`} className="flex gap-3 items-start bg-red-50 border border-red-200 rounded-md p-3">
                                <span className="mt-1 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-red-500" />
                                <div>
                                  <div className="text-sm font-semibold text-red-700">{t.headline}</div>
                                  <div className="text-xs text-red-700 mt-0.5 leading-relaxed">{t.explanation}</div>
                                </div>
                              </div>
                            );
                          })}

                          {highFlags.map((f: any, fi: number) => {
                            const t = translateFlag(f);
                            return (
                              <div key={`h-${fi}`} className="flex gap-3 items-start bg-amber-50 border border-amber-200 rounded-md p-3">
                                <span className="mt-1 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-amber-500" />
                                <div>
                                  <div className="text-sm font-semibold text-amber-700">{t.headline}</div>
                                  <div className="text-xs text-amber-700 mt-0.5 leading-relaxed">{t.explanation}</div>
                                </div>
                              </div>
                            );
                          })}

                          {mediumFlags.map((f: any, fi: number) => {
                            const t = translateFlag(f);
                            return (
                              <div key={`m-${fi}`} className="flex gap-3 items-start bg-zinc-50 border border-zinc-200 rounded-md p-3">
                                <span className="mt-1 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-zinc-400" />
                                <div>
                                  <div className="text-sm font-medium text-zinc-900">{t.headline}</div>
                                  <div className="text-xs text-zinc-600 mt-0.5 leading-relaxed">{t.explanation}</div>
                                </div>
                              </div>
                            );
                          })}

                          {minorFlags.length > 0 && (
                            <div className="text-xs text-zinc-400 pl-1">
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
          )}

          {/* Next Actions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Questions - deduplicated and including lineage-based questions */}
            {(result.next_actions.questions.length > 0 || 
              (fundsLineageData?.funds_lineage?.unresolved_items?.length > 0)) && (
              <div className="bg-white border border-zinc-200 rounded-md p-6">
                <h3 className="text-lg font-bold text-zinc-900 mb-4">
                  ❓ Questions for Client
                </h3>
                <ol className="list-decimal list-inside space-y-2">
                  {/* INTELLIGENT QUESTION GENERATOR - Analyzes all assessment data and generates appropriate questions */}
                  {(() => {
                    const seen = new Set<string>();
                    const uniqueQuestions: string[] = [];
                    
                    // Helper to format currency
                    const formatCurrency = (amount: number) => `£${amount.toLocaleString()}`;
                    
                    // Helper to format date
                    const formatDate = (dateStr: string) => {
                      if (!dateStr) return 'unknown date';
                      if (dateStr.includes('-')) {
                        const parts = dateStr.split('-');
                        if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
                      }
                      return dateStr;
                    };
                    
                    // Helper to add question if not duplicate
                    const addQuestion = (key: string, question: string) => {
                      if (!seen.has(key)) {
                        seen.add(key);
                        uniqueQuestions.push(question);
                      }
                    };
                    
                    // ============================================
                    // INTELLIGENT ANALYSIS: Scan all differences
                    // ============================================
                    result.evidence_matches?.forEach((evidence: any, claimIdx: number) => {
                      const claim = result.claims?.[claimIdx];
                      const claimType = claim?.source_type || 'funds';
                      const claimAmount = claim?.expected_amount || 0;
                      
                      // Analyze each difference and generate appropriate question
                      evidence?.document_verification?.differences?.forEach((diff: any) => {
                        const field = diff.field || '';
                        const severity = diff.severity || '';
                        const amount = diff.amount || diff.discrepancy_amount || 0;
                        
                        // UNTRACED FUNDS - Ask about source
                        if (field === 'untraced_funds' && amount >= 5000) {
                          addQuestion(
                            `untraced-${amount}-${diff.date}`,
                            `What is the source of the ${formatCurrency(amount)} deposit on ${formatDate(diff.date)}? (${diff.found || diff.description || 'No description'})`
                          );
                        }
                        
                        // FUNDS DISCREPANCY - Ask about missing amount
                        else if (field === 'funds_discrepancy') {
                          addQuestion(
                            'funds-discrepancy',
                            `We have traced ${formatCurrency(diff.traced_amount || 0)} to origin and identified ${formatCurrency(diff.untraced_amount || 0)} in deposits requiring evidence, totalling ${formatCurrency(diff.accounted_for || 0)}. Your claimed savings is ${formatCurrency(diff.claimed_amount || 0)}. Please explain or provide evidence for the remaining ${formatCurrency(diff.discrepancy_amount || 0)}.`
                          );
                        }
                        
                        // STATEMENT GAP - Ask for earlier statements
                        else if (field === 'statement_gap') {
                          addQuestion(
                            `gap-${diff.gap_account}-${diff.date}`,
                            `Please provide bank statements for ${diff.gap_account || 'the source account'} covering the period before ${formatDate(diff.gap_account_earliest || diff.date)} to trace the ${formatCurrency(amount)} transfer.`
                          );
                        }
                        
                        // MISSING FIELD on documents (e.g., payment_amount not found)
                        else if (severity === 'missing' || diff.issue?.toLowerCase().includes('not found')) {
                          const fieldName = field.replace(/_/g, ' ');
                          addQuestion(
                            `missing-${field}-${claimIdx}`,
                            `The ${fieldName} could not be found in the provided document for your ${claimType} claim. Please provide documentation showing this information or explain the discrepancy.`
                          );
                        }
                        
                        // AMOUNT MISMATCH
                        else if (field.includes('amount') && (severity === 'mismatch' || diff.issue?.toLowerCase().includes('mismatch'))) {
                          addQuestion(
                            `mismatch-amount-${claimIdx}`,
                            `There is a discrepancy between your claimed ${claimType} amount and the document evidence. ${diff.issue || ''} Please clarify or provide additional documentation.`
                          );
                        }
                        
                        // DATE MISMATCH
                        else if (field.includes('date') && severity === 'mismatch') {
                          addQuestion(
                            `mismatch-date-${claimIdx}`,
                            `The date on your supporting document does not match your claim. ${diff.issue || ''} Please explain this discrepancy.`
                          );
                        }
                        
                        // NAME/BENEFICIARY MISMATCH
                        else if ((field.includes('name') || field.includes('beneficiary')) && severity === 'mismatch') {
                          addQuestion(
                            `mismatch-name-${claimIdx}`,
                            `The name on the document does not match your records. ${diff.issue || ''} Please provide evidence of the connection or explain.`
                          );
                        }
                        
                        // GENERIC CATCH-ALL for any other difference with severity
                        else if (severity && severity !== 'info' && severity !== 'verified' && !field.includes('lineage_analysis') && !field.includes('coverage')) {
                          const fieldName = field.replace(/_/g, ' ');
                          addQuestion(
                            `generic-${field}-${claimIdx}`,
                            `Regarding your ${claimType} claim: ${diff.issue || `Please provide clarification about the ${fieldName}`}.`
                          );
                        }
                      });
                      
                      // Check for unverified claims without specific differences
                      if (!evidence?.verified && !evidence?.document_verified && 
                          (!evidence?.document_verification?.differences || evidence.document_verification.differences.length === 0)) {
                        addQuestion(
                          `unverified-${claimIdx}`,
                          `Your ${claimType} claim of ${formatCurrency(claimAmount)} has not been verified. Please provide supporting documentation.`
                        );
                      }
                    });
                    
                    // ============================================
                    // ADD EXISTING BACKEND QUESTIONS (deduped)
                    // ============================================
                    result.next_actions.questions?.forEach((q: string) => {
                      const amountMatch = q.match(/£[\d,]+(?:\.\d{2})?/);
                      const key = `backend-${amountMatch?.[0] || q.substring(0, 50)}`;
                      addQuestion(key, q);
                    });
                    
                    // ============================================
                    // LINEAGE-BASED QUESTIONS (small items < £5k)
                    // ============================================
                    if (fundsLineageData?.funds_lineage?.unresolved_items?.length > 0) {
                      const smallItems = fundsLineageData.funds_lineage.unresolved_items.filter(
                        (item: any) => item.amount < 5000 && item.amount >= 1000
                      );
                      
                      if (smallItems.length > 0) {
                        const totalSmall = smallItems.reduce((sum: number, i: any) => sum + (i.amount || 0), 0);
                        addQuestion(
                          'small-untraced-items',
                          `There are ${smallItems.length} smaller deposits totalling ${formatCurrency(totalSmall)} that could not be traced to origin. Please provide source documentation or explanation for these amounts.`
                        );
                      }
                    }
                    
                    return uniqueQuestions.map((question, idx) => (
                      <li key={idx} className="text-sm text-zinc-600">{question}</li>
                    ));
                  })()}
                </ol>
              </div>
            )}

            {/* Documents Required - INTELLIGENT DOCUMENT GENERATOR */}
            {(result.next_actions.documents.length > 0 || 
              (fundsLineageData?.funds_lineage?.unresolved_items?.length > 0) ||
              result.evidence_matches?.some((e: any) => e?.document_verification?.differences?.length > 0)) && (
              <div className="bg-white border border-zinc-200 rounded-md p-6">
                <h3 className="text-lg font-bold text-zinc-900 mb-4">
                  📄 Documents Required
                </h3>
                <ul className="list-disc list-inside space-y-2">
                  {/* INTELLIGENT DOCUMENT GENERATOR - Analyzes all differences */}
                  {(() => {
                    const seen = new Set<string>();
                    const documents: {key: string, text: string, priority: number, isSubItem?: boolean}[] = [];
                    
                    // Helper to format currency
                    const formatCurrency = (amount: number) => `£${amount.toLocaleString()}`;
                    
                    // Helper to format date
                    const formatDate = (dateStr: string) => {
                      if (!dateStr) return 'unknown date';
                      if (dateStr.includes('-')) {
                        const parts = dateStr.split('-');
                        if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
                      }
                      return dateStr;
                    };
                    
                    // Helper to add document
                    const addDoc = (key: string, text: string, priority: number = 5, isSubItem: boolean = false) => {
                      if (!seen.has(key)) {
                        seen.add(key);
                        documents.push({key, text, priority, isSubItem});
                      }
                    };
                    
                    // Track manually accepted claims and covered requirements
                    const manuallyAcceptedClaimTypes = new Set<string>();
                    const coveredRequirements = new Set<string>();
                    
                    // Check for manually accepted claims first
                    result.evidence_matches?.forEach((evidence: any, claimIdx: number) => {
                      const claim = result.claims?.[claimIdx];
                      const claimType = claim?.source_type || 'funds';
                      
                      if (evidence?.document_verification?.manual_review_status === 'accepted') {
                        manuallyAcceptedClaimTypes.add(claimType.toLowerCase());
                        // Also mark common document requirements as covered
                        coveredRequirements.add(`doc-${claimType.toLowerCase()}`);
                        coveredRequirements.add(`amount-${claimType.toLowerCase()}`);
                        coveredRequirements.add(`solicitor-${claimType.toLowerCase()}`);
                      }
                      
                      // Check if savings claim has bank statements uploaded (covers savings accumulation)
                      if (claimType.toLowerCase().includes('saving') && 
                          (fundsLineageData?.funds_lineage?.summary?.tracedAmount > 0 ||
                           result.evidence_matches?.some((e: any) => e?.document_verification?.confidence >= 0.5))) {
                        coveredRequirements.add('savings-statements');
                        coveredRequirements.add('historical-statements');
                      }
                    });
                    
                    // ============================================
                    // SCAN ALL DIFFERENCES FOR DOCUMENT NEEDS
                    // ============================================
                    result.evidence_matches?.forEach((evidence: any, claimIdx: number) => {
                      const claim = result.claims?.[claimIdx];
                      const claimType = claim?.source_type || 'funds';
                      
                      // SKIP if claim is manually accepted
                      if (evidence?.document_verification?.manual_review_status === 'accepted') {
                        return; // Skip this claim entirely - already accepted
                      }
                      
                      evidence?.document_verification?.differences?.forEach((diff: any) => {
                        const field = diff.field || '';
                        const amount = diff.amount || diff.discrepancy_amount || 0;
                        
                        // UNTRACED FUNDS - Need source documentation
                        if (field === 'untraced_funds' && amount >= 3000) {
                          const desc = (diff.found || diff.description || '').toUpperCase();
                          const isTransfer = desc.includes('FROM') || desc.includes('TRANSFER') || desc.includes('FP');
                          
                          addDoc(
                            `untraced-doc-${amount}-${diff.date}`,
                            isTransfer 
                              ? `Statement showing outgoing payment of ${formatCurrency(amount)} on/around ${formatDate(diff.date)}`
                              : `Documentation for ${formatCurrency(amount)} received on ${formatDate(diff.date)} (${diff.found || 'source unknown'})`,
                            2,
                            true
                          );
                        }
                        
                        // FUNDS DISCREPANCY - Need evidence for gap
                        else if (field === 'funds_discrepancy' && diff.discrepancy_amount > 0) {
                          addDoc(
                            'discrepancy-evidence',
                            `Evidence for the remaining ${formatCurrency(diff.discrepancy_amount)} not covered by traced funds or identified deposits`,
                            1
                          );
                        }
                        
                        // STATEMENT GAP - Need earlier statements
                        else if (field === 'statement_gap') {
                          addDoc(
                            `gap-doc-${diff.gap_account}`,
                            `Bank statements for ${diff.gap_account || 'source account'} covering period before ${formatDate(diff.gap_account_earliest || diff.date)}`,
                            2
                          );
                        }
                        
                        // MISSING DOCUMENT FIELD - Need document with that info
                        else if (diff.severity === 'missing') {
                          const fieldName = field.replace(/_/g, ' ');
                          addDoc(
                            `missing-doc-${field}-${claimIdx}`,
                            `Document showing ${fieldName} for your ${claimType} claim`,
                            3
                          );
                        }
                      });
                      
                      // Unverified claims need supporting docs
                      if (!evidence?.verified && !evidence?.document_verified) {
                        addDoc(
                          `unverified-doc-${claimIdx}`,
                          `Supporting documentation for your ${claimType} claim`,
                          4
                        );
                      }
                    });
                    
                    // ============================================
                    // ADD EXISTING BACKEND DOCUMENT REQUESTS
                    // (filter out requests for manually accepted claims)
                    // ============================================
                    result.next_actions.documents
                      ?.filter((doc: string) => {
                        const docLower = doc.toLowerCase();
                        // Skip ID/address docs
                        if (docLower.includes('photo id') || docLower.includes('proof of address')) return false;
                        
                        // Skip if document is for a manually accepted claim type
                        for (const acceptedType of manuallyAcceptedClaimTypes) {
                          if (docLower.includes(acceptedType) || docLower.includes(acceptedType.replace('_', ' '))) {
                            return false;
                          }
                        }
                        
                        // Skip historical bank statement requests if savings claim has statements uploaded
                        if ((docLower.includes('historical bank statement') || 
                             docLower.includes('savings accumulation')) && 
                            coveredRequirements.has('savings-statements')) {
                          return false;
                        }
                        
                        // Skip solicitor/amount docs for manually accepted claims
                        if ((docLower.includes('solicitor') || docLower.includes('amount')) &&
                            manuallyAcceptedClaimTypes.size > 0) {
                          for (const acceptedType of manuallyAcceptedClaimTypes) {
                            if (docLower.includes(acceptedType) || docLower.includes(acceptedType.replace('_', ' '))) {
                              return false;
                            }
                          }
                        }
                        
                        return true;
                      })
                      ?.forEach((doc: string, idx: number) => {
                        addDoc(`backend-doc-${idx}`, doc, 5);
                      });
                    
                    // Sort by priority and render
                    documents.sort((a, b) => a.priority - b.priority);
                    
                    // Group by category for better display
                    const hasUntracedDocs = documents.some(d => d.key.startsWith('untraced-doc-'));
                    
                    // If no documents required after filtering, show message
                    if (documents.length === 0) {
                      return (
                        <li className="text-sm text-green-700 font-medium">
                          ✅ All document requirements satisfied or covered by manual acceptance
                        </li>
                      );
                    }
                    
                    return (
                      <>
                        {hasUntracedDocs && (
                          <li className="text-sm text-zinc-600 font-medium">
                            Bank statements/documentation for untraced deposits:
                          </li>
                        )}
                        {documents.map((doc, idx) => (
                          <li 
                            key={doc.key} 
                            className={`text-sm ${doc.key.startsWith('discrepancy') ? 'text-zinc-900 font-medium' : 'text-zinc-600'} ${doc.isSubItem ? 'ml-4' : ''}`}
                          >
                            {doc.text}
                          </li>
                        ))}
                      </>
                    );
                  })()}
                </ul>
              </div>
            )}
          </div>

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
