import React, { useState, useEffect } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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

const SoFAssessment: React.FC<SoFAssessmentProps> = ({ matterId }) => {
  const [status, setStatus] = useState<AssessmentStatus | null>(null);
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState<{ [key: string]: boolean }>({});
  const [errors, setErrors] = useState<{ [key: string]: string }>({});
  const [activeStep, setActiveStep] = useState<'upload' | 'results'>('upload');
  
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

  useEffect(() => {
    fetchStatus();
  }, [matterId]);

  const fetchStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/status`);
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
      const response = await fetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/results`);
      const data = await response.json();
      setResult(data.assessment);
      setActiveStep('results');
    } catch (error) {
      console.error('Error fetching results:', error);
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
      const response = await fetch(
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

      const response = await fetch(
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
      const response = await fetch(
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
        throw new Error(errorData.detail || 'Assessment failed');
      }

      const data = await response.json();
      console.log('Assessment result received:', data.assessment);
      console.log('Evidence matches:', data.assessment.evidence_matches);
      setResult(data.assessment);
      setActiveStep('results');
      await fetchStatus();
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
      await fetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/reset`, {
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
    return 'bg-[#EAD8C0]';
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-red-600';
      case 'HIGH':
        return 'bg-[#D4A574]'; // Warm tan/brown for high severity
      case 'MEDIUM':
        return 'bg-[#E8D5C4]'; // Light cream for medium
      default:
        return 'bg-gray-600';
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
        {/* Client Information Header */}
        {result.client_info && result.purchase && (
          <div className="bg-[#EAD8C0] border border-[#D4C4B0] rounded-lg p-4">
            <h5 className="font-semibold text-gray-800 mb-3 text-lg">Client Information</h5>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-gray-700 font-medium">Client Name:</span>
                <span className="text-gray-900 ml-2">{result.client_info.client_name || 'Not provided'}</span>
              </div>
              <div>
                <span className="text-gray-700 font-medium">Risk Rating:</span>
                <span className="text-gray-900 ml-2">{(result.client_info.client_risk_rating || 'Not specified').toUpperCase()}</span>
              </div>
              <div>
                <span className="text-gray-700 font-medium">Business Sector:</span>
                <span className="text-gray-900 ml-2">{result.client_info.business_sector || 'Not specified'}</span>
              </div>
              <div>
                <span className="text-gray-700 font-medium">PEP Status:</span>
                <span className="text-gray-900 ml-2">{result.client_info.is_pep ? 'Yes' : 'No'}</span>
              </div>
              <div>
                <span className="text-gray-700 font-medium">Purchase Amount:</span>
                <span className="text-gray-900 ml-2">£{result.purchase.amount?.toLocaleString() || 0} {result.purchase.currency || 'GBP'}</span>
              </div>
              <div>
                <span className="text-gray-700 font-medium">Purchase Description:</span>
                <span className="text-gray-900 ml-2">{result.purchase.description || 'Not specified'}</span>
              </div>
              <div className="col-span-2">
                <span className="text-gray-700 font-medium">Expected Payment Date:</span>
                <span className="text-gray-900 ml-2">{result.purchase.expected_payment_date || 'Not specified'}</span>
              </div>
            </div>
          </div>
        )}

        {/* Claims Overview */}
        <div>
          <h5 className="font-semibold text-gray-900 mb-2">Client's SoF Explanation:</h5>
          <ul className="space-y-1 text-sm">
            {result.claims.map((claim, idx) => {
              const evidence = result.evidence_matches[idx];
              const hasBank = evidence?.verified || false;
              const hasDocs = evidence?.document_verified || false;
              
              let status = '';
              let icon = '';
              if (hasBank && hasDocs) {
                status = 'FULLY VERIFIED';
                icon = '✅';
              } else if (hasBank) {
                status = 'BANK PAYMENT FOUND - DOCS REQUIRED';
                icon = '⚠️';
              } else if (hasDocs) {
                status = 'DOCS PROVIDED - BANK PAYMENT REQUIRED';
                icon = '⚠️';
              } else {
                status = 'NOT VERIFIED';
                icon = '❌';
              }
              
              return (
                <li key={idx} className="flex items-center space-x-2">
                  <span>{icon}</span>
                  <span>
                    {claim.source_type}: £{claim.expected_amount.toLocaleString()} 
                    <span className="ml-2 font-semibold">[{status}]</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Evidence Summary */}
        <div>
          <h5 className="font-semibold text-gray-900 mb-2">Evidence Review:</h5>
          <p className="text-sm mb-2 text-gray-900">
            Bank transactions: {verified_count}/{total_claims} claims matched to bank statement entries.
          </p>
          <p className="text-sm mb-2 text-gray-900">
            Supporting documents: {result.evidence_matches.filter(e => e.document_verified).length}/{total_claims} claims verified with source documentation.
          </p>
          <p className="text-sm mb-2 text-gray-900 font-semibold">
            FULLY VERIFIED (both bank + docs): {result.evidence_matches.filter(e => e.verified && e.document_verified).length}/{total_claims} claims.
          </p>
          
          {/* Only show warning if NOT all claims are fully verified */}
          {result.evidence_matches.filter(e => e.verified && e.document_verified).length < total_claims && (
            <div className="bg-[#D4C4B0] border border-[#C4B4A0] rounded p-3 mb-3 text-sm">
              <p className="font-semibold text-gray-800 mb-1">⚠️ IMPORTANT:</p>
              <p className="text-gray-900">
                Bank statements alone are INSUFFICIENT. Corroborating source documents (e.g., probate grants, 
                completion statements) are REQUIRED to prove legitimacy. Bank payments verify receipt, NOT lawful origin.
              </p>
            </div>
          )}
          
          {/* Show positive message if ALL claims are fully verified */}
          {result.evidence_matches.filter(e => e.verified && e.document_verified).length === total_claims && total_claims > 0 && (
            <div className="bg-green-50 border border-green-200 rounded p-3 mb-3 text-sm">
              <p className="font-semibold text-green-800 mb-1">✅ VERIFICATION COMPLETE:</p>
              <p className="text-green-900">
                All claims have been fully verified with both bank statement evidence and supporting documents. 
                AML compliance requirements for source documentation have been met.
              </p>
            </div>
          )}
          <ul className="space-y-2 text-sm">
            {result.evidence_matches.map((evidence, idx) => {
              const hasBank = evidence.verified;
              const hasDocs = evidence.document_verified;
              
              return (
                <li key={idx}>
                  {hasBank && hasDocs ? (
                    <div>
                      <div className="font-medium text-green-700">✅ Claim {idx + 1} ({evidence.claim_source}): FULLY VERIFIED</div>
                      {evidence.transactions.length > 0 && (
                        <div className="ml-6 mt-1 space-y-1">
                          {evidence.transactions.map((txn: any, tidx: number) => (
                            <div key={tidx} className="text-xs">
                              <div>• Amount: £{txn.amount.toLocaleString()} | Date: {txn.date}</div>
                              <div>• Transaction: {txn.description || 'N/A'}</div>
                              <div>• Counterparty: {txn.counterparty || 'Not specified'}</div>
                            </div>
                          ))}
                          {evidence.document_verification && (
                            <div className="ml-2 text-green-800 font-semibold mt-1">
                              ✅ SUPPORTING DOCUMENT VERIFIED (Confidence: {Math.round((evidence.document_verification.confidence || 0) * 100)}%)
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : hasBank ? (
                    <div>
                      <div className="font-medium">⚠️ Claim {idx + 1} ({evidence.claim_source}): Bank payment found - SOURCE DOCS REQUIRED</div>
                      {evidence.transactions.length > 0 && (
                        <div className="ml-6 mt-1 space-y-1">
                          {evidence.transactions.map((txn: any, tidx: number) => (
                            <div key={tidx} className="text-xs">
                              <div>• Amount: £{txn.amount.toLocaleString()} | Date: {txn.date}</div>
                              <div>• Transaction: {txn.description || 'N/A'}</div>
                              <div>• Counterparty: {txn.counterparty || 'Not specified'}</div>
                              <div className="ml-2 text-gray-800 font-semibold mt-1">
                                ⚠️ REQUIRES: Source documentation to prove legitimacy
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : hasDocs ? (
                    <div>
                      <div className="font-medium">⚠️ Claim {idx + 1} ({evidence.claim_source}): Document provided - BANK PAYMENT REQUIRED</div>
                      <div className="ml-6 mt-1 text-xs">
                        ⚠️ Supporting document verified but no matching bank transaction found
                      </div>
                    </div>
                  ) : (
                    <>⚠️ Claim {idx + 1} ({evidence.claim_source}): NOT VERIFIED - No bank transaction or supporting documents</>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        {/* Funding Analysis */}
        {best_path && (
          <div>
            <h5 className="font-semibold text-white mb-2">Funding Analysis:</h5>
            <p className="text-sm mb-2">
              Total funding traced: {best_path.coverage}% of purchase amount.
            </p>
            {best_path.coverage >= 90 && verified_count < total_claims && (
              <div className="text-sm space-y-1 mb-2">
                <p className="font-medium">INTERPRETATION:</p>
                <p>While not all individual claims have direct evidence in the provided statements, sufficient aggregate funding has been traced to cover the full purchase amount. This may indicate:</p>
                <ul className="ml-4 space-y-1">
                  <li>• Some source transactions occurred before the statement period</li>
                  <li>• Funds arrived via intermediate accounts not yet documented</li>
                  <li>• Alternative credits provide equivalent funding coverage</li>
                </ul>
                <p className="mt-2 italic">Recommendation: Request specific documentation for unverified claims to complete the audit trail, even though funding is mathematically sufficient.</p>
              </div>
            )}
            {best_path.steps && best_path.steps.length > 0 && (
              <div className="text-sm">
                {(() => {
                  // Separate claimed vs other funding sources
                  const claimedSources = new Set(
                    result.evidence_matches
                      .filter(e => e.verified && e.transactions.length > 0)
                      .flatMap(e => e.transactions.map(t => t.date + t.amount))
                  );
                  
                  const claimedSteps: string[] = [];
                  const otherSteps: string[] = [];
                  
                  best_path.steps.forEach(step => {
                    // Check if this step matches a verified claim transaction
                    const isClaimedSource = result.evidence_matches.some(evidence => {
                      if (!evidence.verified) return false;
                      return evidence.transactions.some(txn => {
                        return step.includes(txn.date) && step.includes(txn.amount.toString());
                      });
                    });
                    
                    if (isClaimedSource) {
                      claimedSteps.push(step);
                    } else {
                      otherSteps.push(step);
                    }
                  });
                  
                  return (
                    <>
                      {claimedSteps.length > 0 && (
                        <div className="mb-3">
                          <p className="font-medium mb-1">Funding pathway (from client explanation):</p>
                          <ul className="ml-4 space-y-1">
                            {claimedSteps.map((step, idx) => (
                              <li key={idx}>• {step}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      
                      {otherSteps.length > 0 && (
                        <div>
                          <p className="font-medium mb-1">Other potential funding pathway:</p>
                          <p className="text-xs italic text-white/70 mb-2">
                            The below are other potential incoming funds that may be used for the purchase. They may need to be clarified by the client.
                          </p>
                          <ul className="ml-4 space-y-1">
                            {otherSteps.map((step, idx) => (
                              <li key={idx}>• {step}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            )}
          </div>
        )}

        {/* Transaction Review Summary */}
        {result.transaction_review_summary && result.transaction_review_summary.total_alerts > 0 && (
          <div>
            <h5 className="font-semibold text-white mb-2">Automated Transaction Monitoring:</h5>
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
            <p className="text-sm italic">Full alert details available in Transaction Review tab. These findings materially impact the SoF assessment.</p>
          </div>
        )}

        {/* Red Flags */}
        {result.red_flags && result.red_flags.length > 0 && (
          <div>
            <h5 className="font-semibold text-white mb-2">Red Flags Identified ({result.red_flags.length}):</h5>
            <ul className="space-y-1 text-sm">
              {result.red_flags.slice(0, 5).map((flag, idx) => (
                <li key={idx}>• [{flag.severity}] {flag.flag}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Final Decision Statement */}
        <div className="pt-3 border-t border-white/30">
          <p className="text-sm font-medium">
            Status: {result.outcome.status.toUpperCase()} (Confidence: {result.outcome.confidence}%)
          </p>
          <p className="text-sm mt-2 italic">
            This assessment was conducted using a risk-based approach in accordance with UK AML regulations. 
            The matter {result.outcome.status === 'sufficient' ? 'CAN' : 'CANNOT'} proceed to completion in its current state.
          </p>
        </div>
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
      <div key="client-info" className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {/* Header */}
        <div className="bg-purple-50 border-b border-purple-200 px-6 py-4">
          <h3 className="text-lg font-bold text-purple-900">👤 Client Information</h3>
        </div>
        
        {/* Client Details */}
        <div className="px-6 py-4">
          <pre className="whitespace-pre-wrap text-sm text-gray-800 font-mono">{content}</pre>
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
    const isGood = displayStatus.includes('✅') || displayStatus.includes('100%');
    const isPartial = displayStatus.includes('⚠️') || displayStatus.includes('Partial');
    
    return (
      <div key="sof" className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {/* Header */}
        <div className="bg-[#EAD8C0] border-b border-[#D4C4B0] px-6 py-4">
          <h3 className="text-lg font-bold text-gray-900">📊 Source of Funds Analysis</h3>
        </div>
        
        {/* Status Lines */}
        <div className="bg-[#F5EBE0] border-b border-[#D4C4B0] px-6 py-4">
          {bankStatus && (
            <p className="font-semibold mb-2 text-gray-900">
              {bankStatus}
            </p>
          )}
          {docStatus && (
            <div>
              <p className="font-semibold text-gray-900 mb-1">{docStatus}</p>
              {content.includes('Bank payments alone are INSUFFICIENT') && (
                <p className="text-sm text-gray-800 italic ml-4">
                  Bank payments alone are INSUFFICIENT for AML compliance.
                </p>
              )}
            </div>
          )}
          {!bankStatus && overallStatus && (
            <p className="font-semibold text-gray-900">
              {overallStatus}
            </p>
          )}
        </div>
        
        {/* Claims Table */}
        <div className="px-6 py-4">
          <h4 className="text-sm font-bold text-gray-700 mb-3">Claim-by-Claim Analysis</h4>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">Claim</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">Evidence Found</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">Outreach Questions</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">Summary</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {result.claims.map((claim, idx) => {
                  const evidence = result.evidence_matches[idx];
                  const verified = evidence?.verified || false;
                  const document_verified = evidence?.document_verified || false;
                  const transactions = evidence?.transactions || [];
                  const fullyVerified = verified && document_verified;
                  
                  return (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm text-gray-900 font-medium">
                        {claim.source_type} £{claim.expected_amount.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {verified && transactions.length > 0 ? (
                          <div className="text-green-700">
                            ✅ {transactions[0].date}: £{transactions[0].amount.toLocaleString()}
                            {transactions.length > 1 && <span className="text-gray-500 ml-1">(+{transactions.length - 1} more)</span>}
                          </div>
                        ) : (
                          <div className="text-red-700">❌ No matching transaction</div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {fullyVerified ? (
                          <span className="text-green-700">✓ Verified</span>
                        ) : verified ? (
                          <span className="text-gray-800">
                            Request {
                              claim.source_type.toLowerCase().includes('inheritance') ? 'probate grant' :
                              claim.source_type.toLowerCase().includes('property') ? 'completion statement' :
                              claim.source_type.toLowerCase().includes('loan') ? 'loan agreement' :
                              claim.source_type.toLowerCase().includes('business') ? 'sale agreement' :
                              'documentation'
                            }
                          </span>
                        ) : (
                          <span className="text-gray-800">
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
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            ✅ FULLY VERIFIED
                          </span>
                        ) : verified ? (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#D4C4B0] text-gray-900">
                            ⚠️ Payment found, docs req'd
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
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
        
        {/* Summary */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
          <h4 className="text-sm font-bold text-gray-700 mb-2">Summary</h4>
          <div className="text-sm text-gray-700 space-y-2">
            {content.split('SOURCE OF FUNDS SUMMARY:')[1]?.split('FUNDING PATH')[0]?.split('\n').filter(line => line.trim()).map((line, idx) => (
              <p key={idx}>{line.trim()}</p>
            ))}
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
      <div key="tr" className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {/* Header */}
        <div className="bg-[#EAD8C0] border-b border-[#D4C4B0] px-6 py-4">
          <h3 className="text-lg font-bold text-gray-900">🚨 Automated Transaction Review</h3>
        </div>
        
        {/* Overall Status */}
        <div className={`px-6 py-4 border-b ${hasCritical ? 'bg-red-50 border-red-200' : 'bg-[#F5EBE0] border-[#D4C4B0]'}`}>
          <p className={`font-semibold ${hasCritical ? 'text-red-900' : 'text-gray-900'}`}>
            {overallStatus}
          </p>
        </div>
        
        {/* Alert Stats */}
        {result.transaction_review_summary && result.transaction_review_summary.total_alerts > 0 && (
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-[#EAD8C0] rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-gray-900">{result.transaction_review_summary.total_alerts}</div>
                <div className="text-xs text-gray-700 mt-1">Total Alerts</div>
              </div>
              <div className="bg-red-100 rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-red-600">{result.transaction_review_summary.critical_alerts}</div>
                <div className="text-xs text-red-800 mt-1">Critical</div>
              </div>
              <div className="bg-[#D4C4B0] rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-gray-800">{result.transaction_review_summary.high_alerts}</div>
                <div className="text-xs text-gray-700 mt-1">High</div>
              </div>
              <div className="bg-[#F5EBE0] rounded-lg p-3 text-center">
                <div className="text-2xl font-bold text-gray-800">{result.transaction_review_summary.medium_alerts}</div>
                <div className="text-xs text-gray-700 mt-1">Medium</div>
              </div>
            </div>
          </div>
        )}
        
        {/* Alert Table */}
        {result.transaction_review_summary && result.transaction_review_summary.key_concerns.length > 0 && (
          <div className="px-6 py-4">
            <h4 className="text-sm font-bold text-gray-700 mb-3">Alert Analysis</h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">Severity</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">Issue Identified</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">Outreach Questions</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider">Summary</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {result.transaction_review_summary.key_concerns.slice(0, 5).map((concern, idx) => {
                    const isSanctioned = concern.toLowerCase().includes('sanctioned') || concern.toLowerCase().includes('prohibited');
                    const isCash = concern.toLowerCase().includes('cash');
                    const severity = isSanctioned || isCash ? 'CRITICAL' : 'HIGH';
                    
                    return (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                            severity === 'CRITICAL' ? 'bg-red-600 text-white' : 'bg-[#D4A574] text-white'
                          }`}>
                            {severity === 'CRITICAL' ? '🔴 CRITICAL' : '🟠 HIGH'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-900">{concern}</td>
                        <td className="px-4 py-3 text-sm text-gray-800">
                          {isSanctioned ? 'Explain all sanctioned transactions' :
                           isCash ? 'Provide cash source documentation' :
                           'Explain business purpose and parties'}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            severity === 'CRITICAL' ? 'bg-red-100 text-red-800' : 'bg-[#EAD8C0] text-gray-800'
                          }`}>
                            {severity === 'CRITICAL' ? '❌ BLOCKS COMPLETION' : '⚠️ REQUIRES REVIEW'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
        
        {/* Summary */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
          <h4 className="text-sm font-bold text-gray-700 mb-2">Summary</h4>
          <div className="text-sm text-gray-700 space-y-2">
            {content.split('TRANSACTION REVIEW SUMMARY:')[1]?.split('ADDITIONAL RED FLAGS')[0]?.split('\n').filter(line => line.trim()).map((line, idx) => (
              <p key={idx}>{line.trim()}</p>
            ))}
          </div>
        </div>
      </div>
    );
  };


  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Source of Funds Assessment</h2>
          <p className="text-sm text-gray-600 mt-1">
            Upload documents and run AI-powered SoF analysis with Transaction Review integration
          </p>
        </div>
        {status && status.status !== 'no_data' && (
          <button
            onClick={resetAssessment}
            className="px-4 py-2 text-sm text-red-600 hover:text-red-700 border border-red-300 rounded-lg hover:bg-red-50"
          >
            Reset Assessment
          </button>
        )}
      </div>

      {/* Step Tabs */}
      <div className="border-b border-gray-200">
        <div className="flex space-x-8">
          <button
            onClick={() => setActiveStep('upload')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeStep === 'upload'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            📤 Upload Documents
          </button>
          <button
            onClick={() => activeStep === 'results' && setActiveStep('results')}
            disabled={!result}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeStep === 'results'
                ? 'border-blue-500 text-blue-600'
                : result
                ? 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                : 'border-transparent text-gray-300 cursor-not-allowed'
            }`}
          >
            📊 Assessment Results
          </button>
        </div>
      </div>

      {/* Upload Step */}
      {activeStep === 'upload' && (
        <div className="space-y-6">
          {/* Upload Boxes */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Client Info Upload */}
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 hover:border-blue-500 transition-colors">
              <div className="text-center">
                <div className="text-4xl mb-3">📋</div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Client Info</h3>
                
                {/* Show success state if already uploaded */}
                {status && status.files_summary && status.files_summary.client_info === 'uploaded' ? (
                  <>
                    <div className="mt-3 text-green-600 text-sm font-medium">✓ Uploaded</div>
                    <button
                      onClick={() => setClientInfoInputMethod(null)}
                      className="mt-2 text-xs text-blue-600 hover:text-blue-700 underline"
                    >
                      Change
                    </button>
                  </>
                ) : clientInfoInputMethod === null ? (
                  // Initial choice
                  <>
                    <p className="text-sm text-gray-600 mb-4">
                      Choose how to provide client information
                    </p>
                    <div className="space-y-2">
                      <button
                        onClick={() => setClientInfoInputMethod('manual')}
                        className="w-full px-4 py-2 border-2 border-[#A8D5BA] text-gray-800 rounded-md hover:bg-[#E8F5E9] font-medium"
                      >
                        ✏️ Enter Manually
                      </button>
                      <button
                        onClick={() => setClientInfoInputMethod('file')}
                        className="w-full px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
                      >
                        📁 Upload File
                      </button>
                    </div>
                  </>
                ) : clientInfoInputMethod === 'file' ? (
                  // File upload mode
                  <>
                    <p className="text-sm text-gray-600 mb-4">
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
                      <span className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50">
                        {uploadingFiles.client_info ? 'Uploading...' : 'Choose File'}
                      </span>
                    </label>
                    <button
                      onClick={() => setClientInfoInputMethod(null)}
                      className="mt-2 text-xs text-gray-600 hover:text-gray-700 underline block mx-auto"
                    >
                      ← Back
                    </button>
                    {errors.client_info && (
                      <div className="mt-3 text-red-600 text-sm">{errors.client_info}</div>
                    )}
                  </>
                ) : (
                  // Manual input mode
                  <div className="text-left space-y-3 mt-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Client Name *
                      </label>
                      <input
                        type="text"
                        value={manualClientInfo.client_name}
                        onChange={(e) => setManualClientInfo({...manualClientInfo, client_name: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                        placeholder="ABC Corp Ltd"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Risk Rating *
                      </label>
                      <select
                        value={manualClientInfo.client_risk_rating}
                        onChange={(e) => setManualClientInfo({...manualClientInfo, client_risk_rating: e.target.value as any})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                      >
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                      </select>
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Business Sector
                      </label>
                      <input
                        type="text"
                        value={manualClientInfo.business_sector}
                        onChange={(e) => setManualClientInfo({...manualClientInfo, business_sector: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
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
                      <label className="text-xs text-gray-700">
                        Politically Exposed Person (PEP)
                      </label>
                    </div>
                    
                    <div className="border-t pt-3">
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Purchase Amount * (£)
                      </label>
                      <input
                        type="number"
                        value={manualPurchase.amount}
                        onChange={(e) => setManualPurchase({...manualPurchase, amount: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                        placeholder="500000"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Purchase Description
                      </label>
                      <input
                        type="text"
                        value={manualPurchase.description}
                        onChange={(e) => setManualPurchase({...manualPurchase, description: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                        placeholder="Business acquisition"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Expected Payment Date
                      </label>
                      <input
                        type="date"
                        value={manualPurchase.expected_payment_date}
                        onChange={(e) => setManualPurchase({...manualPurchase, expected_payment_date: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Source of Funds Explanation *
                      </label>
                      <textarea
                        value={manualSofExplanation}
                        onChange={(e) => setManualSofExplanation(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                        rows={4}
                        placeholder="Explain where the funds came from (e.g., inheritance, property sale, savings, loan...)"
                      />
                    </div>
                    
                    <div className="pt-2 space-y-2">
                      <button
                        onClick={handleManualSubmit}
                        disabled={uploadingFiles.client_info}
                        className="w-full px-4 py-2 bg-[#A8D5BA] text-gray-900 rounded-md hover:bg-[#8BC5A0] disabled:opacity-50 text-sm font-medium"
                      >
                        {uploadingFiles.client_info ? 'Submitting...' : '✓ Submit'}
                      </button>
                      <button
                        onClick={() => setClientInfoInputMethod(null)}
                        className="w-full text-xs text-gray-600 hover:text-gray-700 underline"
                      >
                        ← Back
                      </button>
                    </div>
                    
                    {errors.client_info && (
                      <div className="mt-3 text-red-600 text-xs">{errors.client_info}</div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Bank Statements Upload */}
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 hover:border-blue-500 transition-colors">
              <div className="text-center">
                <div className="text-4xl mb-3">🏦</div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Bank Statements</h3>
                <p className="text-sm text-gray-600 mb-4">
                  CSV or PDF bank statements (can upload multiple)
                </p>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    accept=".csv,.pdf"
                    onChange={(e) => handleFileUpload(e, 'bank_statement')}
                    className="hidden"
                    disabled={uploadingFiles.bank_statement}
                  />
                  <span className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50">
                    {uploadingFiles.bank_statement ? 'Uploading...' : 'Choose CSV/PDF'}
                  </span>
                </label>
                {status && status.files_summary && status.files_summary.bank_statements_count > 0 && (
                  <div className="mt-3 text-green-600 text-sm font-medium">
                    ✓ {status.files_summary.bank_statements_count} transaction(s)
                  </div>
                )}
                {errors.bank_statement && (
                  <div className="mt-3 text-red-600 text-sm">{errors.bank_statement}</div>
                )}
              </div>
            </div>

            {/* Supporting Docs Upload */}
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 hover:border-blue-500 transition-colors">
              <div className="text-center">
                <div className="text-4xl mb-3">📄</div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Supporting Docs</h3>
                <p className="text-sm text-gray-600 mb-4">
                  PDF documents (probate, completion statements, etc.)
                </p>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => handleFileUpload(e, 'supporting_doc')}
                    className="hidden"
                    disabled={uploadingFiles.supporting_doc}
                  />
                  <span className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50">
                    {uploadingFiles.supporting_doc ? 'Uploading...' : 'Choose PDF'}
                  </span>
                </label>
                {status && status.files_summary && status.files_summary.supporting_docs_count > 0 && (
                  <div className="mt-3 text-green-600 text-sm font-medium">
                    ✓ {status.files_summary.supporting_docs_count} doc(s)
                  </div>
                )}
                {errors.supporting_doc && (
                  <div className="mt-3 text-red-600 text-sm">{errors.supporting_doc}</div>
                )}
              </div>
            </div>
          </div>

          {/* Uploaded Files List */}
          {status && status.uploaded_files.length > 0 && (
            <div className="bg-white border-2 border-[#A8D5BA] rounded-lg p-6 shadow-md">
              <h3 className="text-lg font-bold text-gray-900 mb-4">📎 Uploaded Documents</h3>
              <div className="space-y-3">
                {status.uploaded_files.map((file, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 bg-[#F5EBE0] rounded-lg border border-[#D4C4B0]">
                    <div className="flex items-center space-x-3">
                      <span className="text-2xl text-green-600">✓</span>
                      <div>
                        <div className="font-semibold text-gray-900">{file.filename}</div>
                        <div className="text-sm text-gray-600">
                          {file.category.replace('_', ' ')} • {file.records_count} record(s)
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={async () => {
                        if (confirm(`Remove "${file.filename}"?`)) {
                          // TODO: Implement file removal
                          // For now, we'll need to add a backend endpoint to remove individual files
                          alert('File removal will be implemented. For now, use Reset Assessment to clear all files.');
                        }
                      }}
                      className="px-3 py-1 text-sm text-red-600 hover:text-red-800 border border-red-300 rounded hover:bg-red-50"
                    >
                      ✕ Remove
                    </button>
                  </div>
                ))}
              </div>
              <div className="mt-4 text-sm text-gray-600">
                💡 Tip: You can add more documents below. All uploaded files will be used in the assessment.
              </div>
            </div>
          )}

          {/* Run Assessment Button */}
          {status && status.ready_for_assessment && (
            <div className="flex justify-center">
              <button
                onClick={runAssessment}
                disabled={loading}
                className="px-8 py-3 bg-[#A8D5BA] text-gray-900 rounded-lg hover:bg-[#8BC5A0] disabled:opacity-50 disabled:cursor-not-allowed font-semibold text-lg shadow-lg"
              >
                {loading ? '⏳ Running Assessment...' : '🚀 Run SoF Assessment'}
              </button>
            </div>
          )}

          {errors.assessment && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
              <strong>Assessment Error:</strong> {errors.assessment}
            </div>
          )}

          {!status || !status.ready_for_assessment && (
            <div className="bg-[#F5EBE0] border border-[#D4C4B0] rounded-lg p-4 text-gray-800">
              <strong>Required:</strong> Upload Client Info (JSON) and at least one Bank Statement (CSV/PDF) to run assessment.
            </div>
          )}
        </div>
      )}

      {/* Results Step */}
      {activeStep === 'results' && result && (
        <div className="space-y-6">
          {/* Overall Decision Badge with Comprehensive Summary */}
          <div className={`rounded-lg p-6 ${getStatusColor(result.outcome.status)}`}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-2xl font-bold mb-2 text-gray-900">
                  {result.outcome.status.toUpperCase()}
                </h3>
                <p className="text-lg text-gray-700">Confidence: {result.outcome.confidence}%</p>
              </div>
              <div className="text-5xl">
                {result.outcome.status === 'sufficient' ? '✅' :
                 result.outcome.status === 'borderline' ? '⚠️' : '❌'}
              </div>
            </div>
            
            {/* Comprehensive Assessment Summary */}
            <div className="mt-4 pt-4 border-t border-gray-300">
              <h4 className="text-lg font-semibold mb-3 text-gray-900">Assessment Summary</h4>
              <div className="text-gray-800 text-sm leading-relaxed">
                {buildComprehensiveSummary(result)}
              </div>
            </div>
          </div>

          {/* Parsed Rationale Sections */}
          {renderStructuredRationale(result)}

          {/* Next Actions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Questions */}
            {result.next_actions.questions.length > 0 && (
              <div className="bg-white border border-gray-200 rounded-lg p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4">
                  ❓ Questions for Client
                </h3>
                <ol className="list-decimal list-inside space-y-2">
                  {result.next_actions.questions.map((question, idx) => (
                    <li key={idx} className="text-sm text-gray-700">{question}</li>
                  ))}
                </ol>
              </div>
            )}

            {/* Documents Required */}
            {result.next_actions.documents.length > 0 && (
              <div className="bg-white border border-gray-200 rounded-lg p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4">
                  📄 Documents Required
                </h3>
                <ul className="list-disc list-inside space-y-2">
                  {result.next_actions.documents.map((doc, idx) => (
                    <li key={idx} className="text-sm text-gray-700">{doc}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex justify-center gap-4">
            <button
              onClick={() => setActiveStep('upload')}
              className="px-6 py-3 bg-[#F5EBE0] text-gray-900 border-2 border-[#A8D5BA] rounded-lg hover:bg-[#E8D5C4] font-semibold shadow-lg"
            >
              📎 Add Further Documentation
            </button>
            <button
              onClick={downloadFileNote}
              className="px-6 py-3 bg-[#A8D5BA] text-gray-900 rounded-lg hover:bg-[#8BC5A0] font-semibold shadow-lg"
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
