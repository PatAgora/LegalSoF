import React, { useState, useEffect, useMemo } from 'react';
import { API_BASE_URL, authFetch } from '../../lib/api';
import { useCurrentMatter } from '../../stores/currentMatterStore';
import { formatCurrency, formatCurrencyWhole, formatDateTime } from '../../lib/format';

// Types
interface Transaction {
  id: string;
  date: string;
  description: string;
  amount: number;
  type: 'credit' | 'debit';
  balance?: number;
  counterparty?: string;
  account: string;
  currency?: string;
  direction?: string;
}

interface AccountSummary {
  accountId: string;
  accountName: string;
  transactions: Transaction[];
  credits: Transaction[];
  debits: Transaction[];
  totalCredits: number;
  totalDebits: number;
}

interface LineageNode {
  id: string;
  level: number;
  transaction: Transaction;
  matchedTransaction?: Transaction;  // The corresponding transaction in another account
  matchType: 'matched' | 'partial' | 'unmatched' | 'external_origin' | 'requires_evidence' | 'statement_gap';
  sourceAccount: string;
  destinationAccount: string;
  children: LineageNode[];
  notes: string;
  isOrigin: boolean;  // True if this is a final external source (salary, sale, etc.)
  date?: string;
  amount?: number;
  description?: string;
  account?: string;
}

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

interface LineageSummary {
  totalAmount: number;
  tracedAmount: number;
  untracedAmount: number;
  matchedTransfers: number;
  externalOrigins: number;
  requiresEvidence: number;
  accumulationPeriodDays: number;
}

interface SavedLineage {
  target_transaction: Transaction | null;
  summary: LineageSummary | null;
  lineage_tree: LineageNode[];
  unresolved_items: any[];
  external_origins: any[];
  traced_percentage: number;
  run_at: string;
}

interface FundsLineageProps {
  matterId: number;
  transactions: Transaction[];
  sofClaims?: any[];  // SoF claims from assessment
  onLineageComplete?: (summary: LineageSummary, unresolvedItems: any[]) => void;  // Callback when lineage completes
}

const FundsLineage: React.FC<FundsLineageProps> = ({ matterId, transactions, onLineageComplete }) => {
  const currentMatter = useCurrentMatter((s) => s.matter);
  const [targetTransaction, setTargetTransaction] = useState<Transaction | null>(null);
  const [lineageTree, setLineageTree] = useState<LineageNode[]>([]);
  const [lineageSummary, setLineageSummary] = useState<LineageSummary | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingSaved, setIsLoadingSaved] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // The analysis ran but could not be persisted - the user must know
  // the results on screen are not on the record.
  const [saveError, setSaveError] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [savedLineageDate, setSavedLineageDate] = useState<string | null>(null);
  const [, setHasUnsavedChanges] = useState(false);

  // Load saved lineage results on mount
  useEffect(() => {
    loadSavedLineage();
  }, [matterId]);

  const loadSavedLineage = async () => {
    setIsLoadingSaved(true);
    try {
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/funds-lineage`);
      
      if (response.ok) {
        const data = await response.json();
        if (data.exists && data.funds_lineage) {
          const saved = data.funds_lineage as SavedLineage;
          
          // Transform backend snake_case to frontend camelCase for lineage nodes
          const transformNode = (node: any): LineageNode => {
            return {
              id: node.id,
              level: node.level || 0,
              transaction: node.transaction,
              matchedTransaction: node.matched_transaction || node.matchedTransaction,
              matchType: node.match_type || node.matchType || 'requires_evidence',
              sourceAccount: node.source_account || node.sourceAccount || 'Unknown',
              destinationAccount: node.destination_account || node.destinationAccount || 'Unknown',
              children: (node.children || []).map(transformNode),
              notes: node.notes || '',
              isOrigin: node.is_origin || node.isOrigin || false,
              date: node.date,
              amount: node.amount,
              description: node.description,
              account: node.account
            };
          };
          
          // Restore saved state
          if (saved.target_transaction) {
            setTargetTransaction(saved.target_transaction);
          }
          if (saved.lineage_tree && saved.lineage_tree.length > 0) {
            const transformedTree = saved.lineage_tree.map(transformNode);
            setLineageTree(transformedTree);
            // Expand root node
            setExpandedNodes(new Set([transformedTree[0].id]));
          }
          if (saved.summary) {
            setLineageSummary(saved.summary);
          }
          if (saved.run_at) {
            setSavedLineageDate(saved.run_at);
          }
        }
      }
    } catch (err) {
      console.debug('Error loading saved lineage:', err);
    } finally {
      setIsLoadingSaved(false);
    }
  };

  const saveLineageResults = async (tree: LineageNode[], summary: LineageSummary, target: Transaction) => {
    setIsSaving(true);
    try {
      // Collect unresolved items
      const unresolvedItems: any[] = [];
      const externalOrigins: any[] = [];
      
      function collectItems(nodes: LineageNode[]) {
        for (const node of nodes) {
          if (node.matchType === 'requires_evidence') {
            unresolvedItems.push({
              date: node.transaction?.date || node.date,
              amount: node.transaction?.amount || node.amount,
              description: node.transaction?.description || node.description,
              account: node.transaction?.account || node.account
            });
          }
          if (node.matchType === 'external_origin') {
            externalOrigins.push({
              date: node.transaction?.date || node.date,
              amount: node.transaction?.amount || node.amount,
              description: node.transaction?.description || node.description,
              source_type: node.notes
            });
          }
          if (Array.isArray(node.children) && node.children.length > 0) {
            collectItems(node.children);
          }
        }
      }
      collectItems(tree);
      
      const tracedPct = summary.totalAmount > 0 
        ? Math.round((summary.tracedAmount / summary.totalAmount) * 100) 
        : 0;
      
      const response = await authFetch(`${API_BASE_URL}/api/v1/matters/${matterId}/sof-assessment/funds-lineage`, {
        method: 'POST',
        body: JSON.stringify({
          target_transaction: target,
          summary: summary,
          lineage_tree: tree,
          unresolved_items: unresolvedItems,
          external_origins: externalOrigins,
          traced_percentage: tracedPct
        })
      });
      
      if (response.ok) {
        setSavedLineageDate(new Date().toISOString());
        setHasUnsavedChanges(false);
        setSaveError(false);

        // Notify parent component
        if (onLineageComplete) {
          onLineageComplete(summary, unresolvedItems);
        }
      } else {
        console.debug('Failed to save lineage:', response.status);
        setSaveError(true);
      }
    } catch (err) {
      console.debug('Error saving lineage:', err);
      setSaveError(true);
    } finally {
      setIsSaving(false);
    }
  };

  // Group transactions by account
  const accountSummaries = useMemo((): AccountSummary[] => {
    const accountMap = new Map<string, Transaction[]>();

    transactions.forEach(txn => {
      const accountId = txn.account || 'Unknown Account';
      if (!accountMap.has(accountId)) {
        accountMap.set(accountId, []);
      }
      accountMap.get(accountId)!.push(txn);
    });

    return Array.from(accountMap.entries()).map(([accountId, txns]) => {
      const credits = txns.filter(t => t.type === 'credit');
      const debits = txns.filter(t => t.type === 'debit');
      
      return {
        accountId,
        accountName: inferAccountName(accountId, txns),
        transactions: txns.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()),
        credits,
        debits,
        totalCredits: credits.reduce((sum, t) => sum + Math.abs(t.amount), 0),
        totalDebits: debits.reduce((sum, t) => sum + Math.abs(t.amount), 0)
      };
    });
  }, [transactions]);

  // Infer account type from transactions and account ID
  function inferAccountName(accountId: string, txns: Transaction[]): string {
    const idLower = accountId.toLowerCase();
    
    // Check for savings indicators
    if (idLower.includes('sav') || idLower.includes('isa')) {
      return 'Savings Account';
    }
    
    // Check transaction descriptions for clues
    const hasSalary = txns.some(t => 
      t.description.toLowerCase().includes('salary') || 
      t.description.toLowerCase().includes('wages') ||
      t.description.toLowerCase().includes('payroll')
    );
    
    if (hasSalary) {
      return 'Current Account';
    }
    
    // Default based on transaction patterns
    const credits = txns.filter(t => t.type === 'credit');
    const debits = txns.filter(t => t.type === 'debit');
    
    // Savings accounts typically have more credits than debits and fewer transactions
    if (credits.length > debits.length * 2 && txns.length < 20) {
      return 'Savings Account';
    }
    
    return accountId.length > 20 ? 'Bank Account' : accountId;
  }

  // Find matching transaction in another account (same amount, close date, opposite direction)
  function findMatchingTransaction(
    sourceTxn: Transaction,
    targetAccountTxns: Transaction[],
    isSourceCredit: boolean
  ): Transaction | null {
    const sourceDate = new Date(sourceTxn.date);
    const sourceAmount = Math.abs(sourceTxn.amount);
    
    // Look for opposite direction transaction with same amount within 3 days
    const matches = targetAccountTxns.filter(txn => {
      const txnDate = new Date(txn.date);
      const daysDiff = Math.abs((txnDate.getTime() - sourceDate.getTime()) / (1000 * 60 * 60 * 24));
      const amountMatch = Math.abs(Math.abs(txn.amount) - sourceAmount) < 0.01;
      const directionMatch = isSourceCredit ? txn.type === 'debit' : txn.type === 'credit';
      
      return amountMatch && daysDiff <= 3 && directionMatch;
    });
    
    // Return the closest date match
    if (matches.length > 0) {
      return matches.sort((a, b) => {
        const aDiff = Math.abs(new Date(a.date).getTime() - sourceDate.getTime());
        const bDiff = Math.abs(new Date(b.date).getTime() - sourceDate.getTime());
        return aDiff - bDiff;
      })[0];
    }
    
    return null;
  }

  // Identify if transaction is an external origin (salary, sale, etc.)
  function identifyExternalOrigin(txn: Transaction): { isExternal: boolean; sourceType: string } {
    const desc = txn.description.toLowerCase();
    
    if (desc.includes('salary') || desc.includes('wages') || desc.includes('payroll') || desc.includes('bacs')) {
      return { isExternal: true, sourceType: 'Salary/Employment Income' };
    }
    if (desc.includes('pension')) {
      return { isExternal: true, sourceType: 'Pension Payment' };
    }
    if (desc.includes('dividend')) {
      return { isExternal: true, sourceType: 'Dividend Income' };
    }
    if (desc.includes('interest') && !desc.includes('transfer')) {
      return { isExternal: true, sourceType: 'Interest Payment' };
    }
    if (desc.includes('hmrc') || desc.includes('tax refund')) {
      return { isExternal: true, sourceType: 'Tax Refund' };
    }
    if (desc.includes('rent') && txn.type === 'credit') {
      return { isExternal: true, sourceType: 'Rental Income' };
    }
    
    return { isExternal: false, sourceType: '' };
  }

  // Build the backward lineage tree from a target transaction
  function buildLineageTree(
    target: Transaction,
    accounts: AccountSummary[],
    visited: Set<string> = new Set(),
    level: number = 0
  ): LineageNode {
    const nodeId = `${target.id}-${level}`;
    
    // Prevent infinite loops
    if (visited.has(target.id) || level > 10) {
      return {
        id: nodeId,
        level,
        transaction: target,
        matchType: 'requires_evidence',
        sourceAccount: 'Unknown',
        destinationAccount: target.account,
        children: [],
        notes: 'Circular reference or max depth reached',
        isOrigin: false
      };
    }
    
    visited.add(target.id);
    
    // Check if this is an external origin
    const externalCheck = identifyExternalOrigin(target);
    if (externalCheck.isExternal) {
      return {
        id: nodeId,
        level,
        transaction: target,
        matchType: 'external_origin',
        sourceAccount: externalCheck.sourceType,
        destinationAccount: target.account,
        children: [],
        notes: /salary|employment/i.test(externalCheck.sourceType)
          ? `Salary of ${formatCurrency(Math.abs(target.amount))} received on ${formatDate(target.date)}`
          : `✅ Origin identified: ${externalCheck.sourceType}`,
        isOrigin: true
      };
    }
    
    // For credit transactions, look for matching debit in other accounts
    if (target.type === 'credit') {
      for (const account of accounts) {
        if (account.accountId === target.account) continue;
        
        const matchedDebit = findMatchingTransaction(target, account.debits, true);
        if (matchedDebit) {
          // Found a match! Now trace back the credits that funded this debit
          const fundingCredits = findFundingCredits(matchedDebit, account, target);
          
          const children: LineageNode[] = fundingCredits.map(credit => 
            buildLineageTree(credit, accounts, new Set(visited), level + 1)
          );
          
          return {
            id: nodeId,
            level,
            transaction: target,
            matchedTransaction: matchedDebit,
            matchType: 'matched',
            sourceAccount: account.accountName,
            destinationAccount: target.account,
            children,
            notes: `✅ Matched: ${account.accountName} sent ${formatCurrencyWhole(Math.abs(matchedDebit.amount))} on ${formatDate(matchedDebit.date)}`,
            isOrigin: false
          };
        }
      }
    }
    
    // No match found - requires evidence
    return {
      id: nodeId,
      level,
      transaction: target,
      matchType: 'requires_evidence',
      sourceAccount: extractPayer(target),
      destinationAccount: target.account,
      children: [],
      notes: `⚠️ Source documentation required for this payment`,
      isOrigin: false
    };
  }

  // Find credits that likely funded a debit (credits before the debit date)
  function findFundingCredits(debit: Transaction, account: AccountSummary, excludeMatch: Transaction): Transaction[] {
    const debitDate = new Date(debit.date);
    const debitAmount = Math.abs(debit.amount);
    
    // Get credits before this debit
    const priorCredits = account.credits
      .filter(c => {
        const creditDate = new Date(c.date);
        return creditDate <= debitDate && c.id !== excludeMatch?.id;
      })
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
    
    // Select credits that could have funded this debit
    const fundingCredits: Transaction[] = [];
    let runningTotal = 0;
    
    for (const credit of priorCredits) {
      if (runningTotal >= debitAmount) break;
      
      fundingCredits.push(credit);
      runningTotal += Math.abs(credit.amount);
      
      // Limit to recent credits (within 90 days)
      const creditDate = new Date(credit.date);
      const daysDiff = (debitDate.getTime() - creditDate.getTime()) / (1000 * 60 * 60 * 24);
      if (daysDiff > 90) break;
    }
    
    return fundingCredits;
  }

  // Extract payer name from transaction description
  function extractPayer(txn: Transaction): string {
    if (txn.counterparty) return txn.counterparty;
    
    const desc = txn.description;
    // Remove common prefixes
    let cleaned = desc
      .replace(/^(FASTER PAYMENT|FP|BACS|CHAPS|DIRECT CREDIT|BGC|TFR|TRANSFER)\s*/i, '')
      .replace(/\d{2}\/\d{2}\/\d{2,4}/g, '')
      .replace(/\d{2}[A-Z]{3}\d{2}/g, '')
      .trim();
    
    // Take first meaningful part
    const parts = cleaned.split(/\s{2,}|\|/);
    return parts[0]?.trim()?.slice(0, 40) || 'Unknown Payer';
  }

  // Calculate lineage summary statistics
  function calculateSummary(nodes: LineageNode[], targetAmount: number): LineageSummary {
    let tracedAmount = 0;
    let matchedTransfers = 0;
    let externalOrigins = 0;
    let requiresEvidence = 0;
    let earliestDate: Date | null = null;
    let latestDate: Date | null = null;

    function traverseNodes(nodeList: LineageNode[]) {
      for (const node of nodeList) {
        const txnDate = new Date(node.transaction.date);
        
        if (!earliestDate || txnDate < earliestDate) earliestDate = txnDate;
        if (!latestDate || txnDate > latestDate) latestDate = txnDate;
        
        if (node.matchType === 'matched') {
          matchedTransfers++;
        } else if (node.matchType === 'external_origin') {
          externalOrigins++;
          tracedAmount += Math.abs(node.transaction.amount);
        } else if (node.matchType === 'requires_evidence') {
          requiresEvidence++;
        }
        
        if (node.children.length > 0) {
          traverseNodes(node.children);
        }
      }
    }

    traverseNodes(nodes);

    // TS cannot see the closure assignments above, so it narrows the
    // dates to `never` - assert the type explicitly.
    const earliest = earliestDate as Date | null;
    const latest = latestDate as Date | null;
    const accumulationDays = earliest && latest
      ? Math.ceil((latest.getTime() - earliest.getTime()) / (1000 * 60 * 60 * 24))
      : 0;

    return {
      totalAmount: targetAmount,
      tracedAmount,
      // Clamped at zero - traced external origins can legitimately sum
      // to more than the target credit (e.g. many salary credits fund
      // one transfer). A negative "untraced" figure is meaningless; the
      // over-tracing is surfaced as a data-quality note instead.
      untracedAmount: Math.max(0, targetAmount - tracedAmount),
      matchedTransfers,
      externalOrigins,
      requiresEvidence,
      accumulationPeriodDays: accumulationDays
    };
  }

  // Generate the lineage trace
  const generateLineage = async () => {
    if (!targetTransaction) {
      setError('Please select a target transaction');
      return;
    }

    setIsProcessing(true);
    setError(null);
    setSaveError(false);

    try {
      const rootNode = buildLineageTree(targetTransaction, accountSummaries);
      setLineageTree([rootNode]);
      
      const summary = calculateSummary([rootNode], Math.abs(targetTransaction.amount));
      setLineageSummary(summary);
      
      // Expand root by default
      setExpandedNodes(new Set([rootNode.id]));
      
      // Auto-save results to backend
      await saveLineageResults([rootNode], summary, targetTransaction);
      
    } catch (err) {
      setError(`Error generating lineage: ${err}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // Clear lineage and re-run (for when new documents are added)
  const reRunLineage = () => {
    setLineageTree([]);
    setLineageSummary(null);
    setSavedLineageDate(null);
    setSaveError(false);
    setHasUnsavedChanges(true);
  };

  // Toggle node expansion
  const toggleNode = (nodeId: string) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(nodeId)) {
      newExpanded.delete(nodeId);
    } else {
      newExpanded.add(nodeId);
    }
    setExpandedNodes(newExpanded);
  };

  // Expand all nodes
  const expandAll = () => {
    const allIds = new Set<string>();
    function collectIds(nodes: LineageNode[]) {
      nodes.forEach(n => {
        allIds.add(n.id);
        if (n.children.length > 0) collectIds(n.children);
      });
    }
    collectIds(lineageTree);
    setExpandedNodes(allIds);
  };

  // Get large credits that could be the claim amount (for selection)
  const significantCredits = useMemo(() => {
    const allCredits = transactions.filter(t => t.type === 'credit');
    // Sort by amount descending
    return allCredits
      .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount))
      .slice(0, 20); // Top 20 largest credits
  }, [transactions]);

  // Render a lineage node and its children
  const renderLineageNode = (node: LineageNode): React.ReactNode => {
    // Defensive: ensure node has required properties
    if (!node || !node.id) {
      console.debug('Invalid lineage node:', node);
      return null;
    }
    
    const isExpanded = expandedNodes.has(node.id);
    const hasChildren = Array.isArray(node.children) && node.children.length > 0;
    
    // Green marks a verified origin (traced or matched); amber marks a
    // point that still requires evidence.
    const statusColor =
      node.matchType === 'requires_evidence' ? 'bg-amber-500' :
      node.matchType === 'statement_gap' ? 'bg-amber-500' :
      'bg-green-500';
    const needsEvidence =
      node.matchType === 'requires_evidence' || node.matchType === 'statement_gap';

    // Get transaction safely
    const txn = node.transaction || {};
    const txnDate = formatDate(txn.date || node.date);
    const txnAmount = txn.amount || node.amount || 0;
    const txnDesc = txn.description || node.description || 'No description';
    const txnId = txn.id || node.id || 'N/A';

    // Account path (source → destination), derived from whatever the
    // node carries.
    const accountLabel = (() => {
      let source = node.sourceAccount;
      let dest = node.destinationAccount;
      if (!source || source === 'Unknown' || source === 'Unknown Source') {
        const desc = (node.description || txnDesc || '').toUpperCase();
        const notes = (node.notes || '').toLowerCase();
        const fromMatch = desc.match(/FROM\s+([\w\s*]+\*{4}\d{4})/i);
        if (fromMatch) {
          source = fromMatch[1].trim();
        } else if (notes.includes('transfer from')) {
          const notesMatch = notes.match(/from\s+([\w\s*]+\*{4}\d{4})/i);
          if (notesMatch) source = notesMatch[1].trim();
        } else if (notes.includes('origin')) {
          const originMatch = notes.match(/origin[:\s]+(.+)/i);
          if (originMatch) source = originMatch[1].trim();
        } else if (node.account) {
          source = node.account;
        }
      }
      if (!dest || dest === 'Unknown' || dest === 'Destination') {
        dest = node.account || 'Destination';
      }
      return `${source || 'Unknown'} → ${dest || 'Destination'}`;
    })();

    const indent = 12 + (node.level || 0) * 20;

    return (
      <div key={node.id}>
        {/* Bank-statement style row — one line, click to expand and see
            the entry from another statement that led to it. */}
        <div
          onClick={() => toggleNode(node.id)}
          className="flex items-center gap-3 px-3 py-2 border-b border-zinc-100 cursor-pointer hover:bg-zinc-50"
          style={{ paddingLeft: `${indent}px` }}
        >
          <span className="w-3 flex-shrink-0 text-zinc-400 text-[10px] font-mono">
            {isExpanded ? '▼' : '▶'}
          </span>
          <span className={`h-2 w-2 rounded-full flex-shrink-0 ${statusColor}`} />
          <span className="w-24 flex-shrink-0 text-xs text-zinc-500 tabular-nums">{txnDate}</span>
          <span className="flex-1 min-w-0 text-sm text-zinc-800 truncate" title={txnDesc}>{txnDesc}</span>
          <span className="flex-shrink-0 text-sm font-semibold text-zinc-900 tabular-nums">
            {formatCurrency(Math.abs(txnAmount))}
          </span>
        </div>

        {/* Expanded detail + the entries that led to this one. */}
        {isExpanded && (
          <>
            <div
              className="bg-zinc-50/70 border-b border-zinc-100 py-2 pr-3 text-xs text-zinc-600 space-y-0.5"
              style={{ paddingLeft: `${indent + 26}px` }}
            >
              <div><span className="font-medium text-zinc-500">Account:</span> {accountLabel}</div>
              <div className="font-mono text-[10px] text-zinc-400">TXN-{txnId}</div>
              {node.matchedTransaction && (
                <div>
                  <span className="font-medium text-zinc-500">Matched with:</span>{' '}
                  {node.matchedTransaction.description} ({formatDate(node.matchedTransaction.date)})
                </div>
              )}
              {node.notes && (
                <div className={needsEvidence ? 'text-amber-700' : 'text-green-700'}>{node.notes}</div>
              )}
            </div>
            {hasChildren && node.children.map((child: LineageNode) =>
              renderLineageNode(child)
            )}
          </>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white border border-zinc-200 rounded-md p-6">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">🔗</span>
          <h2 className="text-xl font-bold text-zinc-900">Backward Funds Lineage</h2>
        </div>
        
        <p className="text-sm text-zinc-600 mb-4">
          Trace funds backward from a credit transaction to identify where the money came from.
          The system cross-references between uploaded account statements to match transfers
          and trace funds to their ultimate origin (salary, investments, etc.).
        </p>

        {/* Account Summary */}
        <div className="bg-zinc-50 border border-zinc-200 rounded-md p-4 mb-4">
          <h3 className="font-semibold text-zinc-900 mb-3">📊 Uploaded Account Statements</h3>
          
          {accountSummaries.length === 0 ? (
            <div className="text-amber-700 text-sm">
              ⚠️ No transaction data available. Please upload bank statements in the Transaction Review tab.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {accountSummaries.map(account => (
                <div key={account.accountId} className="bg-white rounded-md border border-zinc-200 p-3">
                  <div className="font-medium text-zinc-900">{account.accountName}</div>
                  <div className="text-xs text-zinc-400 mb-2">{account.accountId}</div>
                  <div className="text-sm">
                    <span className="text-red-700">↓ {formatCurrencyWhole(account.totalDebits)}</span>
                    <span className="mx-2 text-zinc-400">|</span>
                    <span className="text-green-700">↑ {formatCurrencyWhole(account.totalCredits)}</span>
                  </div>
                  <div className="text-xs text-zinc-400">{account.transactions.length} transactions</div>
                </div>
              ))}
            </div>
          )}
          
          {accountSummaries.length === 1 && (
            <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded text-sm text-amber-700">
              ⚠️ <strong>Only one account uploaded.</strong> For proper funds lineage tracing between accounts 
              (e.g., savings → current), please upload statements for all relevant accounts.
            </div>
          )}
        </div>

        {/* Transaction Selection */}
        <div className="bg-zinc-50 border border-zinc-200 rounded-md p-4 mb-4">
          <h3 className="font-semibold text-zinc-900 mb-3">Select Target Credit to Trace</h3>
          
          {significantCredits.length === 0 ? (
            <div className="text-amber-700 text-sm">
              ⚠️ No credit transactions found.
            </div>
          ) : (
            <div className="space-y-2">
              <select
                className="w-full p-2 border border-zinc-200 rounded-md text-sm"
                value={targetTransaction?.id || ''}
                onChange={(e) => {
                  const selected = significantCredits.find(t => t.id === e.target.value);
                  setTargetTransaction(selected || null);
                  setLineageTree([]);
                  setLineageSummary(null);
                }}
              >
                <option value="">-- Select a credit transaction to trace --</option>
                {significantCredits.map((txn) => (
                  <option key={txn.id} value={txn.id}>
                    {formatDate(txn.date)} | {txn.account} | {formatCurrencyWhole(Math.abs(txn.amount))} | {txn.description.slice(0, 40)}...
                  </option>
                ))}
              </select>

              {targetTransaction && (
                <div className="bg-zinc-50 border border-zinc-200 rounded-md p-3 mt-2">
                  <div className="text-sm font-semibold text-zinc-900">Selected Transaction:</div>
                  <div className="text-sm text-zinc-700 mt-1">
                    <div>• Amount: <strong>{formatCurrency(Math.abs(targetTransaction.amount))}</strong></div>
                    <div>• Date: {formatDate(targetTransaction.date)}</div>
                    <div>• Account: {targetTransaction.account}</div>
                    <div>• Description: {targetTransaction.description}</div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Generate/Re-run Buttons */}
        <div className="flex items-center gap-4">
          <button
            onClick={generateLineage}
            disabled={!targetTransaction || isProcessing || isSaving}
            className={`px-6 py-2 rounded font-semibold transition-colors ${
              !targetTransaction || isProcessing || isSaving
                ? 'bg-zinc-200 text-zinc-400 cursor-not-allowed'
                : 'bg-zinc-900 text-white hover:bg-zinc-900'
            }`}
          >
            {isProcessing ? '⏳ Tracing Funds...' : isSaving ? '💾 Saving...' : '🔍 Trace Backward Lineage'}
          </button>
          
          {lineageSummary && (
            <button
              onClick={reRunLineage}
              className="px-4 py-2 rounded font-semibold bg-zinc-900 text-white hover:bg-zinc-900 transition-colors"
            >
              🔄 Re-run Analysis
            </button>
          )}
        </div>
        
        {/* Saved Status Indicator */}
        {savedLineageDate && !saveError && (
          <div className="mt-3 flex items-center gap-2 text-sm text-green-700 bg-green-50 px-3 py-2 rounded-md">
            <span>✅</span>
            <span>
              Analysis saved on {formatDateTime(savedLineageDate)}
            </span>
          </div>
        )}

        {/* Save failure - the results on screen are NOT on the record. */}
        {saveError && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <span className="font-semibold">Analysis completed but could not be saved</span> — the
            results shown are not persisted. Re-run the analysis to try saving again.
          </div>
        )}
        
        {isLoadingSaved && (
          <div className="mt-3 text-sm text-zinc-400">
            ⏳ Loading saved analysis...
          </div>
        )}

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
            ⚠️ {error}
          </div>
        )}
      </div>

      {/* Lineage Results */}
      {lineageTree.length > 0 && lineageSummary && (
        <div className="bg-white border border-zinc-200 rounded-md overflow-hidden">
          {/* Header */}
          <div className="bg-zinc-50 border-b border-zinc-200 px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-zinc-900">Backward Funds Lineage Ledger</h3>
                <p className="text-xs text-zinc-600 mt-1">
                  Tracing origin of {formatCurrency(Math.abs(targetTransaction?.amount || 0))} credited on {formatDate(targetTransaction?.date)}
                </p>
              </div>
              <button
                onClick={expandAll}
                className="px-3 py-1 text-xs bg-white border border-zinc-200 rounded hover:bg-zinc-50"
              >
                Expand All
              </button>
            </div>
          </div>

          {/* Summary Stats */}
          <div className="px-6 py-4 bg-zinc-50 border-b border-zinc-200">
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 text-center">
              <div>
                <div className="text-xl font-bold text-zinc-900">
                  {formatCurrencyWhole(lineageSummary.totalAmount)}
                </div>
                <div className="text-xs text-zinc-600">Total Amount</div>
              </div>
              <div>
                <div className="text-xl font-bold text-green-700">
                  {formatCurrencyWhole(lineageSummary.tracedAmount)}
                </div>
                <div className="text-xs text-zinc-600">Traced to Origin</div>
              </div>
              <div>
                <div className="text-xl font-bold text-amber-700">
                  {formatCurrencyWhole(Math.max(0, lineageSummary.untracedAmount))}
                </div>
                <div className="text-xs text-zinc-600">Requires Evidence</div>
              </div>
              <div>
                <div className="text-xl font-bold text-zinc-500">
                  {lineageSummary.matchedTransfers}
                </div>
                <div className="text-xs text-zinc-600">Matched Transfers</div>
              </div>
              <div>
                <div className="text-xl font-bold text-zinc-600">
                  {(() => {
                    const days = lineageSummary.accumulationPeriodDays || 0;
                    const years = Math.floor(days / 365);
                    const months = Math.floor((days % 365) / 30);
                    if (years > 0 && months > 0) return `${years}y ${months}m`;
                    if (years > 0) return `${years} year${years > 1 ? 's' : ''}`;
                    if (months > 0) return `${months} month${months > 1 ? 's' : ''}`;
                    return `${days} days`;
                  })()}
                </div>
                <div className="text-xs text-zinc-600">Statement Period</div>
              </div>
            </div>
            {/* Data-quality note - identified external origins can sum to
                more than the traced credit (e.g. many salary credits feeding
                one transfer). Flag it rather than showing a negative gap. */}
            {lineageSummary.tracedAmount > lineageSummary.totalAmount && (
              <div className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 text-left">
                <span className="font-semibold">Data-quality note:</span> the identified external
                origins total {formatCurrencyWhole(lineageSummary.tracedAmount)}, which exceeds the{' '}
                {formatCurrencyWhole(lineageSummary.totalAmount)} credit being traced. Review the
                matched origins - some credits may relate to other spending rather than this transfer.
              </div>
            )}
          </div>

          {/* Lineage Tree */}
          <div className="px-6 py-4">
            <div className="space-y-2">
              {lineageTree.map((node) => renderLineageNode(node))}
            </div>
          </div>

          {/* Legend */}
          <div className="px-6 py-3 bg-zinc-50 border-t border-zinc-200">
            <div className="flex flex-wrap gap-4 text-xs">
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 bg-green-500 rounded-full" />
                <span>Verified origin</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 bg-amber-500 rounded-full" />
                <span>Requires evidence</span>
              </div>
            </div>
          </div>

          {/* Review Required for - enumerated open issues a reviewer
              must clear before this lineage can be signed off.
              Sources walked from the live lineage tree so the list
              stays in sync with the current rendering. */}
          {(() => {
            const evidenceNodes: LineageNode[] = [];
            const gapNodes: LineageNode[] = [];
            const walk = (nodes: LineageNode[]) => {
              for (const n of nodes) {
                if (n.matchType === 'requires_evidence') evidenceNodes.push(n);
                else if (n.matchType === 'statement_gap') gapNodes.push(n);
                if (n.children && n.children.length > 0) walk(n.children);
              }
            };
            walk(lineageTree);

            const untraced = Math.max(0, lineageSummary.untracedAmount || 0);
            const total    = lineageSummary.totalAmount    || 0;
            const untracedPct = total > 0 ? (untraced / total) * 100 : 0;

            const noIssues = untraced <= 0 && evidenceNodes.length === 0 && gapNodes.length === 0;
            if (noIssues) return null;

            const fmtMoney = (n: number) => formatCurrencyWhole(n);

            return (
              <div className="px-6 py-5 bg-amber-50 border-t border-amber-200">
                <div className="text-sm font-bold text-amber-800 mb-3">
                  Review Required for
                </div>
                <ul className="space-y-2">
                  {untraced > 0 && (
                    <li className="flex items-start gap-3 text-sm text-zinc-800">
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                      <span>
                        <strong>{fmtMoney(untraced)}</strong> of the {fmtMoney(total)} credit
                        {untracedPct > 0 && ` (${untracedPct.toFixed(1)}%)`} is not yet traced
                        to a verified origin.
                      </span>
                    </li>
                  )}
                  {evidenceNodes.length > 0 && (
                    <li className="text-sm text-zinc-800">
                      <div className="flex items-start gap-3">
                        <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                        <span>
                          <strong>{evidenceNodes.length} transaction{evidenceNodes.length === 1 ? '' : 's'}</strong> need
                          {evidenceNodes.length === 1 ? 's' : ''} source documentation -
                          obtain proof of origin (payslip, contract, completion statement, etc.).
                        </span>
                      </div>
                      <ul className="mt-1.5 ml-7 space-y-1 text-xs text-zinc-600">
                        {evidenceNodes.slice(0, 6).map((n, i) => (
                          <li key={i}>
                            {fmtMoney(Math.abs(n.transaction?.amount || n.amount || 0))} on{' '}
                            {formatDate(n.transaction?.date || n.date)}
                            {(n.transaction?.account || n.account) && ` - ${n.transaction?.account || n.account}`}
                            {(n.transaction?.description || n.description) && (
                              <span className="text-zinc-500"> · {(n.transaction?.description || n.description || '').slice(0, 60)}</span>
                            )}
                          </li>
                        ))}
                        {evidenceNodes.length > 6 && (
                          <li className="italic">…and {evidenceNodes.length - 6} more - expand the ledger below.</li>
                        )}
                      </ul>
                    </li>
                  )}
                  {gapNodes.length > 0 && (
                    <li className="text-sm text-zinc-800">
                      <div className="flex items-start gap-3">
                        <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-amber-500 flex-shrink-0" />
                        <span>
                          <strong>{gapNodes.length} statement gap{gapNodes.length === 1 ? '' : 's'}</strong> - earlier
                          statements are needed for the source accounts of these inbound transfers.
                        </span>
                      </div>
                      <ul className="mt-1.5 ml-7 space-y-1 text-xs text-zinc-600">
                        {gapNodes.slice(0, 4).map((n, i) => (
                          <li key={i}>
                            {fmtMoney(Math.abs(n.transaction?.amount || n.amount || 0))} on{' '}
                            {formatDate(n.transaction?.date || n.date)}
                            {n.sourceAccount && n.sourceAccount !== 'Unknown' && ` from ${n.sourceAccount}`}
                          </li>
                        ))}
                        {gapNodes.length > 4 && (
                          <li className="italic">…and {gapNodes.length - 4} more.</li>
                        )}
                      </ul>
                    </li>
                  )}
                </ul>
              </div>
            );
          })()}

          {/* Compliance Footer - the matter reference is the REAL
              reference from the matter record (never a fabricated
              MAT-{id}), and the timestamp is the analysis run time
              from the saved payload, not the render time. */}
          <div className="px-6 py-4 bg-zinc-50 border-t border-zinc-200">
            <div className="text-xs text-zinc-600">
              <div className="font-semibold mb-1">📜 Compliance Statement</div>
              <p>
                This backward funds lineage traces credited funds through uploaded bank statements.
                Funds traced to an origin (salary, investments, etc.) are marked as verified.
                Unmatched transactions require additional source documentation.
              </p>
              <div className="mt-2 text-zinc-400">
                Analysis run: {savedLineageDate ? formatDateTime(savedLineageDate) : 'not yet saved'}
                {' | '}
                Matter: {currentMatter?.reference_number || `Matter ID ${matterId}`}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Help Panel */}
      <div className="bg-zinc-50 border border-zinc-200 rounded-md p-4">
        <div className="text-sm text-zinc-900">
          <div className="font-semibold mb-2">💡 How Backward Funds Lineage Works</div>
          <ol className="list-decimal list-inside space-y-2 text-zinc-700">
            <li><strong>Upload all relevant statements</strong> - Current account, savings account, ISA, etc.</li>
            <li><strong>Select the credit to trace</strong> - Usually the large transfer that matches your SoF claim</li>
            <li><strong>System matches transfers</strong> - Automatically finds matching debits/credits between accounts</li>
            <li><strong>Traces to origin</strong> - Follows the chain until it reaches external sources (salary, etc.)</li>
            <li><strong>Flags gaps</strong> - Any funds without a clear origin are marked for manual evidence</li>
          </ol>
          <div className="mt-3 p-2 bg-zinc-100 rounded text-xs">
            <strong>Example:</strong> £100k credit to current account ← matched to £100k debit from savings ← 
            traced to multiple salary credits over 12 months = ✅ Verified accumulation from employment income
          </div>
        </div>
      </div>
    </div>
  );
};

export default FundsLineage;
