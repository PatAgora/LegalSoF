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

  const runAssessment = async () => {
    setLoading(true);
    setErrors({});

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/run`,
        { method: 'POST' }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Assessment failed');
      }

      const data = await response.json();
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
    switch (status) {
      case 'sufficient':
        return 'bg-green-600';
      case 'borderline':
        return 'bg-yellow-600';
      case 'insufficient':
        return 'bg-red-600';
      default:
        return 'bg-gray-600';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-red-600';
      case 'HIGH':
        return 'bg-orange-600';
      case 'MEDIUM':
        return 'bg-yellow-600';
      default:
        return 'bg-gray-600';
    }
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
                <p className="text-sm text-gray-600 mb-4">
                  JSON file with client details, purchase info, and SoF explanation
                </p>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    accept=".json"
                    onChange={(e) => handleFileUpload(e, 'client_info')}
                    className="hidden"
                    disabled={uploadingFiles.client_info}
                  />
                  <span className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50">
                    {uploadingFiles.client_info ? 'Uploading...' : 'Choose JSON File'}
                  </span>
                </label>
                {status && status.files_summary && status.files_summary.client_info === 'uploaded' && (
                  <div className="mt-3 text-green-600 text-sm font-medium">✓ Uploaded</div>
                )}
                {errors.client_info && (
                  <div className="mt-3 text-red-600 text-sm">{errors.client_info}</div>
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
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Uploaded Files</h3>
              <div className="space-y-2">
                {status.uploaded_files.map((file, idx) => (
                  <div key={idx} className="flex items-center justify-between text-sm">
                    <div className="flex items-center space-x-2">
                      <span className="text-green-600">✓</span>
                      <span className="font-medium text-gray-900">{file.filename}</span>
                      <span className="text-gray-500">({file.category.replace('_', ' ')})</span>
                    </div>
                    <span className="text-gray-600">{file.records_count} record(s)</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Run Assessment Button */}
          {status && status.ready_for_assessment && (
            <div className="flex justify-center">
              <button
                onClick={runAssessment}
                disabled={loading}
                className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-semibold text-lg shadow-lg"
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
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-800">
              <strong>Required:</strong> Upload Client Info (JSON) and at least one Bank Statement (CSV/PDF) to run assessment.
            </div>
          )}
        </div>
      )}

      {/* Results Step */}
      {activeStep === 'results' && result && (
        <div className="space-y-6">
          {/* Overall Decision */}
          <div className={`rounded-lg p-6 text-white ${getStatusColor(result.outcome.status)}`}>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-2xl font-bold mb-2">
                  {result.outcome.status.toUpperCase()}
                </h3>
                <p className="text-lg opacity-90">Confidence: {result.outcome.confidence}%</p>
              </div>
              <div className="text-5xl">
                {result.outcome.status === 'sufficient' ? '✅' :
                 result.outcome.status === 'borderline' ? '⚠️' : '❌'}
              </div>
            </div>
            <p className="mt-4 text-white/90">{result.outcome.rationale}</p>
          </div>

          {/* Transaction Review Integration */}
          {result.transaction_review_summary && result.transaction_review_summary.total_alerts > 0 && (
            <div className="bg-red-50 border-l-4 border-red-600 rounded-lg p-6">
              <h3 className="text-lg font-bold text-red-900 mb-3">
                🚨 Transaction Review Alerts
              </h3>
              <div className="grid grid-cols-4 gap-4 mb-4">
                <div className="bg-white rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-gray-900">
                    {result.transaction_review_summary.total_alerts}
                  </div>
                  <div className="text-sm text-gray-600">Total Alerts</div>
                </div>
                <div className="bg-red-100 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-red-600">
                    {result.transaction_review_summary.critical_alerts}
                  </div>
                  <div className="text-sm text-red-800">Critical</div>
                </div>
                <div className="bg-orange-100 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-orange-600">
                    {result.transaction_review_summary.high_alerts}
                  </div>
                  <div className="text-sm text-orange-800">High</div>
                </div>
                <div className="bg-yellow-100 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-yellow-600">
                    {result.transaction_review_summary.medium_alerts}
                  </div>
                  <div className="text-sm text-yellow-800">Medium</div>
                </div>
              </div>
              {result.transaction_review_summary.key_concerns.length > 0 && (
                <div>
                  <h4 className="font-semibold text-red-900 mb-2">Key Concerns:</h4>
                  <ul className="list-disc list-inside space-y-1">
                    {result.transaction_review_summary.key_concerns.map((concern, idx) => (
                      <li key={idx} className="text-red-800">{concern}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Red Flags */}
          {result.red_flags && result.red_flags.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-lg p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4">
                🚩 Red Flags ({result.red_flags.length})
              </h3>
              <div className="space-y-3">
                {result.red_flags.slice(0, 10).map((flag, idx) => (
                  <div key={idx} className="flex items-start space-x-3 p-3 bg-gray-50 rounded">
                    <span className={`px-2 py-1 rounded text-xs font-bold text-white ${getSeverityColor(flag.severity)}`}>
                      {flag.severity}
                    </span>
                    <div className="flex-1">
                      <p className="text-sm text-gray-900">{flag.flag}</p>
                      <p className="text-xs text-gray-600 mt-1">Source: {flag.source}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

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

          {/* Download File Note */}
          <div className="flex justify-center">
            <button
              onClick={downloadFileNote}
              className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold shadow-lg"
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
