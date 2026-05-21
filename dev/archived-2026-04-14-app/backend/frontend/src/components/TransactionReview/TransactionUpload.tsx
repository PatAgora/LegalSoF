import { useState } from 'react';
import { API_BASE_URL } from '../../lib/api';
import { Card, FileUploader, Alert } from '../ui';

interface TransactionUploadProps {
  matterId: number;
  onUploadSuccess: () => void;
}

interface UploadResult {
  transactions_created: number;
  alerts_generated: number;
}

export default function TransactionUpload({ matterId, onUploadSuccess }: TransactionUploadProps) {
  const [customerId, setCustomerId] = useState('');
  const [result, setResult] = useState<UploadResult | null>(null);

  return (
    <Card>
      <Card.Header>
        <h3 className="text-base font-semibold text-zinc-900">Upload bank transactions</h3>
        <p className="text-xs text-zinc-500 mt-0.5">
          Drop a CSV file or PDF statement - transactions are parsed and AML-screened automatically.
        </p>
      </Card.Header>

      <Card.Body>
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-semibold text-zinc-700 mb-1.5">
              Customer ID
            </label>
            <input
              type="text"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-zinc-300 rounded focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:border-transparent"
              placeholder="e.g. CUST001"
            />
            <p className="text-[11px] text-zinc-400 mt-1">
              Used to tag the transactions against the customer record.
            </p>
          </div>

          {customerId ? (
            <FileUploader
              key={result ? `done-${result.transactions_created}` : 'idle'}
              category="Bank statement"
              uploadUrl={`${API_BASE_URL}/api/v1/matters/${matterId}/transactions/upload`}
              accept=".csv,.pdf"
              maxSizeMb={25}
              extraFormFields={{ customer_id: customerId }}
              helper="CSV or PDF, up to 25 MB."
              onComplete={(payload) => {
                setResult(payload);
                onUploadSuccess();
              }}
              extractVerdict={() => null}
            />
          ) : (
            <div className="rounded-md border-2 border-dashed border-zinc-200 px-6 py-8 text-center text-sm text-zinc-400">
              Enter a customer ID above to enable upload.
            </div>
          )}

          {result && (
            <Alert variant="success" title="Upload complete">
              {result.transactions_created} transactions imported · {result.alerts_generated} alert
              {result.alerts_generated !== 1 ? 's' : ''} generated.
            </Alert>
          )}

          <details className="text-xs text-zinc-500">
            <summary className="cursor-pointer text-zinc-600 hover:text-zinc-900">
              Accepted formats &amp; sample CSV
            </summary>
            <div className="mt-3 space-y-3">
              <p>PDF bank statements from any bank - transactions extracted automatically by the parser.</p>
              <div>
                <div className="text-[11px] uppercase tracking-wider text-zinc-400 mb-1">Sample CSV</div>
                <pre className="text-[11px] overflow-x-auto bg-zinc-50 border border-zinc-200 p-2 rounded">
{`id,txn_date,customer_id,direction,amount,currency,country_iso2,narrative
TXN001,2024-01-15,CUST001,in,5000,GBP,IR,Payment from supplier
TXN002,2024-01-16,CUST001,out,25000,GBP,GB,Large cash withdrawal`}
                </pre>
              </div>
            </div>
          </details>
        </div>
      </Card.Body>
    </Card>
  );
}
