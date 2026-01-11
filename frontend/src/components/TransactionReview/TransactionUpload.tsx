import { useState } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface TransactionUploadProps {
  matterId: number;
  onUploadSuccess: () => void;
}

export default function TransactionUpload({ matterId, onUploadSuccess }: TransactionUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [customerId, setCustomerId] = useState('');
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!file || !customerId) {
      setMessage({ type: 'error', text: 'Please select a file and enter customer ID' });
      return;
    }

    setUploading(true);
    setMessage(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('customer_id', customerId);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/matters/${matterId}/transactions/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Upload failed');
      }

      const result = await response.json();
      setMessage({
        type: 'success',
        text: `Success! ${result.transactions_created} transactions uploaded, ${result.alerts_generated} alerts generated.`
      });
      setFile(null);
      setCustomerId('');
      onUploadSuccess();
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Upload failed'
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4">📄 Upload Bank Transactions</h3>
      
      <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <h4 className="text-sm font-semibold text-blue-900 mb-2">✨ Now Supports PDF!</h4>
        <p className="text-sm text-blue-800">
          Upload CSV files or PDF bank statements. Our AI automatically extracts transactions from PDFs.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Customer ID
          </label>
          <input
            type="text"
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="e.g., CUST001"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Bank Statement File (CSV or PDF)
          </label>
          <input
            type="file"
            accept=".csv,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            required
          />
          <p className="mt-1 text-xs text-gray-500">
            {file?.name ? (
              <span className="font-medium text-blue-600">
                Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
              </span>
            ) : (
              <>
                Accepted formats: <span className="font-medium">.csv, .pdf</span>
                <br />
                CSV format: id, date, amount, currency, direction, country, narrative
                <br />
                PDF format: Any standard bank statement with transaction tables
              </>
            )}
          </p>
        </div>

        {message && (
          <div className={`p-3 rounded-md ${message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
            {message.text}
          </div>
        )}

        <button
          type="submit"
          disabled={uploading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          {uploading ? (
            <>
              <span className="inline-block animate-spin mr-2">⏳</span>
              Uploading and analyzing...
            </>
          ) : (
            <>
              <span className="mr-2">📤</span>
              Upload Transactions
            </>
          )}
        </button>
      </form>

      <div className="mt-6 space-y-4">
        {/* CSV Example */}
        <div className="p-4 bg-gray-50 rounded-md border border-gray-200">
          <h4 className="text-sm font-semibold mb-2 flex items-center">
            <span className="mr-2">📊</span>
            Sample CSV Format:
          </h4>
          <pre className="text-xs overflow-x-auto bg-white p-2 rounded border">
{`id,txn_date,customer_id,direction,amount,currency,country_iso2,narrative
TXN001,2024-01-15,CUST001,in,5000,GBP,IR,Payment from supplier
TXN002,2024-01-16,CUST001,out,25000,GBP,GB,Large cash withdrawal`}
          </pre>
        </div>

        {/* PDF Info */}
        <div className="p-4 bg-gradient-to-r from-purple-50 to-blue-50 rounded-md border border-purple-200">
          <h4 className="text-sm font-semibold mb-2 flex items-center text-purple-900">
            <span className="mr-2">📄</span>
            PDF Bank Statement Support:
          </h4>
          <ul className="text-xs text-purple-800 space-y-1 ml-4">
            <li>• Upload PDF statements from any bank (HSBC, Barclays, Lloyds, etc.)</li>
            <li>• AI automatically extracts transaction data from tables</li>
            <li>• Detects dates, amounts, descriptions, and currencies</li>
            <li>• Works with multi-page statements</li>
            <li>• Instantly generates AML alerts for suspicious activity</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
