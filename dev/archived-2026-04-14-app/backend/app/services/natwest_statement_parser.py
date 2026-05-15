"""
NatWest Statement Parser

Handles the specific NatWest PDF format where:
- Date appears on one line
- Description appears on the next line(s)
- Amount appears in paid out / paid in columns
- Balance appears in the last column

This parser specifically targets NatWest's multi-line transaction layout.
"""

import re
import io
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pdfplumber
import fitz  # PyMuPDF


class NatWestStatementParser:
    """
    Specialized parser for NatWest bank statements.
    Handles their specific multi-line transaction format.
    """
    
    def __init__(self):
        # NatWest date patterns (e.g., "15 Dec", "02 Jan 24")
        self.date_patterns = [
            r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:\s+(\d{2,4}))?',
        ]
        
        self.month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        # NatWest transaction type keywords
        self.debit_keywords = [
            'direct debit', 'dd', 'card transaction', 'card payment',
            'debit card', 'contactless', 'standing order', 'so',
            'transfer out', 'payment to', 'paid out', 'withdrawal',
            'atm', 'cash', 'fee', 'charge', 'interest charged',
            'd/d', 's/o', 'ddr', 'bp', 'bill payment'
        ]
        
        self.credit_keywords = [
            'credit', 'salary', 'wages', 'pension', 'bacs',
            'transfer in', 'payment from', 'paid in', 'deposit',
            'refund', 'interest earned', 'cashback', 'reward',
            'automated credit', 'faster payment received', 'bgc'
        ]
    
    def parse(self, content: bytes, filename: str = '') -> Dict[str, Any]:
        """
        Parse NatWest statement PDF.
        
        Uses multiple strategies and picks the best result:
        1. Table extraction with row merging
        2. Text extraction with line grouping
        3. PyMuPDF blocks with position analysis
        """
        all_results = {}
        metadata = {
            'source': 'pdf',
            'parser': 'natwest_specific',
            'pages': 0,
            'extraction_method': None
        }
        
        # Strategy 1: pdfplumber table with row merging
        print("\n📊 NatWest Parser Strategy 1: Table extraction with row merging...")
        try:
            table_txns = self._extract_tables_merged(content, metadata)
            all_results['table'] = table_txns or []
            print(f"   Found {len(all_results['table'])} transactions")
            # Log first few for debugging
            for i, txn in enumerate(all_results['table'][:3]):
                print(f"     [{i}] {txn.get('date')} | {txn.get('description', '')[:40]} | {txn.get('direction')} £{txn.get('amount', 0)}")
        except Exception as e:
            print(f"   ⚠️ Table extraction error: {e}")
            all_results['table'] = []
        
        # Strategy 2: PyMuPDF with positional grouping
        print("\n📊 NatWest Parser Strategy 2: Position-based extraction...")
        try:
            pos_txns = self._extract_by_position(content, metadata)
            all_results['position'] = pos_txns or []
            print(f"   Found {len(all_results['position'])} transactions")
        except Exception as e:
            print(f"   ⚠️ Position extraction error: {e}")
            all_results['position'] = []
        
        # Strategy 3: Text line grouping
        print("\n📊 NatWest Parser Strategy 3: Text line grouping...")
        try:
            line_txns = self._extract_by_line_grouping(content, metadata)
            all_results['line'] = line_txns or []
            print(f"   Found {len(all_results['line'])} transactions")
        except Exception as e:
            print(f"   ⚠️ Line grouping error: {e}")
            all_results['line'] = []
        
        # Pick the best result (most transactions with valid amounts)
        best_method = None
        best_count = 0
        best_transactions = []
        
        for method, txns in all_results.items():
            # Count transactions with valid amounts
            valid_count = sum(1 for t in txns if t.get('amount') and t.get('amount') > 0)
            print(f"   {method}: {valid_count} valid transactions out of {len(txns)}")
            if valid_count > best_count:
                best_count = valid_count
                best_method = method
                best_transactions = txns
        
        if best_method:
            metadata['extraction_method'] = best_method
            print(f"\n✅ Best method: {best_method} with {best_count} transactions")
        
        # Deduplicate
        transactions = self._deduplicate(best_transactions)
        
        # Log summary of directions
        credits = sum(1 for t in transactions if t.get('direction') == 'credit')
        debits = sum(1 for t in transactions if t.get('direction') == 'debit')
        print(f"📊 Final: {len(transactions)} transactions ({credits} credits, {debits} debits)")
        
        return {
            'success': len(transactions) > 0,
            'transactions': transactions,
            'metadata': metadata,
            'error': None if transactions else 'No transactions could be extracted'
        }
        
        # Deduplicate
        transactions = self._deduplicate(transactions)
        
        return {
            'success': len(transactions) > 0,
            'transactions': transactions,
            'metadata': metadata,
            'error': None if transactions else 'No transactions could be extracted'
        }
    
    def _extract_tables_merged(self, content: bytes, metadata: Dict) -> List[Dict]:
        """Extract tables and merge multi-line transactions."""
        transactions = []
        
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                metadata['pages'] = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract tables
                    tables = page.extract_tables()
                    
                    for table in tables or []:
                        if not table or len(table) < 2:
                            continue
                        
                        # Find header row and map columns
                        header_idx, col_map = self._find_header_and_columns(table)
                        if col_map['date'] is None:
                            continue
                        
                        print(f"   Page {page_num}: Found table with header at row {header_idx}")
                        print(f"   Column mapping: {col_map}")
                        
                        # Process rows, merging multi-line transactions
                        current_txn = None
                        
                        for row_idx in range(header_idx + 1, len(table)):
                            row = [str(cell).strip() if cell else '' for cell in table[row_idx]]
                            
                            if not any(row):
                                continue
                            
                            # Skip balance brought forward / carried forward rows
                            row_text = ' '.join(row).lower()
                            if 'brought forward' in row_text or 'carried forward' in row_text:
                                continue
                            
                            # Check if this row has a date (starts a new transaction)
                            date_cell = row[col_map['date']] if col_map['date'] < len(row) else ''
                            date_str = self._find_date_in_text(date_cell)
                            
                            if date_str:
                                # Save previous transaction
                                if current_txn and current_txn.get('amount'):
                                    transactions.append(current_txn)
                                
                                # Parse new transaction
                                parsed_date = self._parse_date(date_str)
                                
                                # Get description from description column
                                description = ''
                                if col_map['description'] is not None and col_map['description'] < len(row):
                                    description = row[col_map['description']]
                                
                                # Get amounts from paid_in and withdrawn columns
                                paid_in = None
                                withdrawn = None
                                
                                if col_map['paid_in'] is not None and col_map['paid_in'] < len(row):
                                    paid_in_str = row[col_map['paid_in']]
                                    if paid_in_str and paid_in_str not in ['-', '', '0', '0.00']:
                                        paid_in = self._parse_amount(paid_in_str)
                                
                                if col_map['withdrawn'] is not None and col_map['withdrawn'] < len(row):
                                    withdrawn_str = row[col_map['withdrawn']]
                                    if withdrawn_str and withdrawn_str not in ['-', '', '0', '0.00']:
                                        withdrawn = self._parse_amount(withdrawn_str)
                                
                                # Determine amount and direction
                                if withdrawn and withdrawn > 0:
                                    amount = withdrawn
                                    direction = 'debit'
                                elif paid_in and paid_in > 0:
                                    amount = paid_in
                                    direction = 'credit'
                                else:
                                    amount = None
                                    direction = 'credit'
                                
                                # Get balance
                                balance = None
                                if col_map['balance'] is not None and col_map['balance'] < len(row):
                                    balance_str = row[col_map['balance']]
                                    if balance_str:
                                        balance = self._parse_amount(balance_str)
                                
                                current_txn = {
                                    'account_id': f'NATWEST_P{page_num}',
                                    'date': parsed_date,
                                    'amount': abs(amount) if amount else None,
                                    'currency': 'GBP',
                                    'direction': direction,
                                    'description': description,
                                    'counterparty_name': '',
                                    'balance': balance,
                                    'source': f'table_merged_p{page_num}'
                                }
                            elif current_txn:
                                # This is a continuation row (no date) - append to description
                                # Get text from description column
                                if col_map['description'] is not None and col_map['description'] < len(row):
                                    continuation = row[col_map['description']]
                                    if continuation and len(continuation) > 1:
                                        current_txn['description'] = (current_txn['description'] + ' ' + continuation).strip()
                                
                                # Also check if amount appears on this continuation row
                                if not current_txn.get('amount'):
                                    paid_in = None
                                    withdrawn = None
                                    
                                    if col_map['paid_in'] is not None and col_map['paid_in'] < len(row):
                                        paid_in_str = row[col_map['paid_in']]
                                        if paid_in_str and paid_in_str not in ['-', '', '0', '0.00']:
                                            paid_in = self._parse_amount(paid_in_str)
                                    
                                    if col_map['withdrawn'] is not None and col_map['withdrawn'] < len(row):
                                        withdrawn_str = row[col_map['withdrawn']]
                                        if withdrawn_str and withdrawn_str not in ['-', '', '0', '0.00']:
                                            withdrawn = self._parse_amount(withdrawn_str)
                                    
                                    if withdrawn and withdrawn > 0:
                                        current_txn['amount'] = withdrawn
                                        current_txn['direction'] = 'debit'
                                    elif paid_in and paid_in > 0:
                                        current_txn['amount'] = paid_in
                                        current_txn['direction'] = 'credit'
                        
                        # Don't forget last transaction
                        if current_txn and current_txn.get('amount'):
                            transactions.append(current_txn)
        
        except Exception as e:
            print(f"   ⚠️ Table extraction error: {e}")
            import traceback
            traceback.print_exc()
        
        return transactions
    
    def _find_header_and_columns(self, table: List[List]) -> Tuple[int, Dict[str, int]]:
        """Find header row and map column indices."""
        col_map = {
            'date': None,
            'description': None,
            'paid_in': None,
            'withdrawn': None,
            'balance': None
        }
        
        # Comprehensive column name variations
        # DEBIT columns (money going OUT)
        debit_column_names = [
            # EXACT matches for NatWest format first
            'withdrawn(£)', 'withdrawn (£)', 'withdrawn(e)', 'withdrawn (e)',
            # English - UK banks
            'withdrawn', 'withdrawals', 'withdrawal',
            'paid out', 'paidout', 'paid_out',
            'money out', 'moneyout', 'money_out',
            'debit', 'debits', 'dr',
            'out', 'outgoing', 'outgoings',
            'payments', 'payment out',
            'expenditure', 'spend', 'spent',
            'charges', 'charge',
            # With currency symbols - various formats
            'withdrawn£', 'paid out(£)', 'paid out (£)',
            'debit(£)', 'debit (£)', 'debit £',
            'out(£)', 'out (£)',
            'money out(£)', 'money out (£)',
            # International
            'ausgaben', 'abbuchung', 'soll',  # German
            'débit', 'dépenses', 'sortie',  # French
            'débito', 'cargo', 'salida',  # Spanish
            'uscita', 'addebito',  # Italian
        ]
        
        # CREDIT columns (money coming IN)
        credit_column_names = [
            # English - UK banks
            'paid in', 'paidin', 'paid_in',
            'money in', 'moneyin', 'money_in',
            'credit', 'credits', 'cr',
            'in', 'incoming', 'incomings',
            'receipts', 'receipt',
            'deposits', 'deposit', 'deposited',
            'income', 'received',
            # With currency symbols
            'paid in(£)', 'paid in (£)', 'paid in £',
            'credit(£)', 'credit (£)', 'credit £',
            'in(£)', 'in (£)',
            'money in(£)', 'money in (£)',
            'deposits(£)', 'deposits (£)',
            # International
            'einnahmen', 'gutschrift', 'haben',  # German
            'crédit', 'entrée', 'recettes',  # French
            'crédito', 'abono', 'entrada',  # Spanish
            'entrata', 'accredito',  # Italian
        ]
        
        # DATE column names
        date_column_names = [
            'date', 'transaction date', 'trans date', 'txn date',
            'posting date', 'posted', 'posted date',
            'value date', 'effective date', 'entry date',
            'booked', 'booked date', 'booking date',
            'created', 'completed', 'settled',
            # International
            'datum', 'buchungstag', 'wertstellung',  # German
            'date opération', 'date valeur',  # French
            'fecha', 'fecha valor',  # Spanish
        ]
        
        # DESCRIPTION column names
        description_column_names = [
            'description', 'details', 'particulars',
            'narrative', 'transaction', 'transaction details',
            'payment details', 'reference', 'memo',
            'merchant', 'payee', 'name', 'beneficiary',
            'counterparty', 'counter party',
            'type', 'transaction type',
            # International
            'verwendungszweck', 'buchungstext', 'empfänger',  # German
            'libellé', 'motif', 'bénéficiaire',  # French
            'concepto', 'descripción', 'beneficiario',  # Spanish
        ]
        
        # BALANCE column names
        balance_column_names = [
            'balance', 'running balance', 'available balance',
            'account balance', 'closing balance', 'bal',
            'total', 'cumulative',
            # With currency
            'balance(£)', 'balance (£)', 'balance £',
            # International
            'saldo', 'kontostand',  # German/Spanish
            'solde',  # French
        ]
        
        # AMOUNT column names (single column for both debit/credit)
        amount_column_names = [
            'amount', 'value', 'sum', 'total',
            'transaction amount', 'txn amount',
            # With currency
            'amount(£)', 'amount (£)', 'amount £',
            'value(£)', 'value (£)',
            # International
            'betrag', 'summe',  # German
            'montant',  # French
            'importe', 'monto',  # Spanish
        ]
        
        # Search for header row
        for idx in range(min(15, len(table))):
            row = table[idx]
            if not row:
                continue
            
            row_lower = [str(cell).lower().strip() if cell else '' for cell in row]
            row_text = ' '.join(row_lower)
            
            # Check if this looks like a header row
            has_date = any(any(date_name in cell for date_name in date_column_names) for cell in row_lower)
            has_money_col = any(
                any(name in cell for name in credit_column_names + debit_column_names + amount_column_names) 
                for cell in row_lower
            )
            has_balance = any(any(bal_name in cell for bal_name in balance_column_names) for cell in row_lower)
            
            if has_date and (has_money_col or has_balance):
                # Found header row - map columns
                for col_idx, cell in enumerate(row_lower):
                    # DATE column
                    if col_map['date'] is None:
                        if any(date_name in cell for date_name in date_column_names):
                            col_map['date'] = col_idx
                            continue
                    
                    # DESCRIPTION column
                    if col_map['description'] is None:
                        if any(desc_name in cell for desc_name in description_column_names):
                            col_map['description'] = col_idx
                            continue
                    
                    # CREDIT/PAID IN column
                    if col_map['paid_in'] is None:
                        if any(credit_name in cell for credit_name in credit_column_names):
                            col_map['paid_in'] = col_idx
                            continue
                    
                    # DEBIT/WITHDRAWN column
                    if col_map['withdrawn'] is None:
                        if any(debit_name in cell for debit_name in debit_column_names):
                            col_map['withdrawn'] = col_idx
                            continue
                    
                    # BALANCE column
                    if col_map['balance'] is None:
                        if any(bal_name in cell for bal_name in balance_column_names):
                            col_map['balance'] = col_idx
                            continue
                    
                    # AMOUNT column (single column for both - will need sign detection)
                    # Only use if we haven't found separate debit/credit columns
                    if col_map['paid_in'] is None and col_map['withdrawn'] is None:
                        if any(amt_name in cell for amt_name in amount_column_names):
                            # Mark as paid_in, we'll determine direction from sign
                            col_map['paid_in'] = col_idx
                            continue
                
                # If description not found, assume it's column after date
                if col_map['description'] is None and col_map['date'] is not None:
                    col_map['description'] = col_map['date'] + 1
                
                print(f"   Header found at row {idx}: {row_lower}")
                print(f"   Column mapping: date={col_map['date']}, desc={col_map['description']}, "
                      f"credit={col_map['paid_in']}, debit={col_map['withdrawn']}, balance={col_map['balance']}")
                
                return idx, col_map
        
        # Fallback: assume standard column order
        print("   No header found, using default column positions")
        return 0, {'date': 0, 'description': 1, 'paid_in': 2, 'withdrawn': 3, 'balance': 4}
    
    def _extract_by_position(self, content: bytes, metadata: Dict) -> List[Dict]:
        """Extract using PyMuPDF with positional analysis for NatWest format."""
        transactions = []
        
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Get text with positions using "dict" mode for detailed structure
                text_dict = page.get_text('dict')
                
                # Collect all text spans with their positions
                spans = []
                for block in text_dict.get('blocks', []):
                    if 'lines' in block:
                        for line in block['lines']:
                            for span in line.get('spans', []):
                                spans.append({
                                    'text': span['text'].strip(),
                                    'x0': span['bbox'][0],
                                    'y0': span['bbox'][1],
                                    'x1': span['bbox'][2],
                                    'y1': span['bbox'][3]
                                })
                
                # Sort by y position, then x position
                spans = sorted(spans, key=lambda s: (round(s['y0'], 0), s['x0']))
                
                # Group spans into rows (same y position)
                rows = []
                current_row = []
                current_y = None
                
                for span in spans:
                    if not span['text']:
                        continue
                    
                    y = round(span['y0'], 0)
                    if current_y is None or abs(y - current_y) < 8:
                        current_row.append(span)
                        current_y = y
                    else:
                        if current_row:
                            rows.append(sorted(current_row, key=lambda s: s['x0']))
                        current_row = [span]
                        current_y = y
                
                if current_row:
                    rows.append(sorted(current_row, key=lambda s: s['x0']))
                
                # Detect column boundaries from header row
                col_boundaries = self._detect_column_boundaries(rows)
                
                # Process rows
                current_txn = None
                
                for row in rows:
                    # Get text by column position
                    row_text = ' '.join([s['text'] for s in row])
                    
                    # Skip header and footer rows
                    row_lower = row_text.lower()
                    if any(skip in row_lower for skip in [
                        'date', 'description', 'paid in', 'withdrawn', 'balance',
                        'brought forward', 'carried forward', 'page', 'statement'
                    ]):
                        continue
                    
                    # Assign text to columns based on x position
                    col_texts = self._assign_text_to_columns(row, col_boundaries)
                    
                    # Check for date in first column
                    date_str = self._find_date_in_text(col_texts.get('date', ''))
                    
                    if date_str:
                        # Save previous transaction
                        if current_txn and current_txn.get('amount'):
                            transactions.append(current_txn)
                        
                        # Parse new transaction
                        parsed_date = self._parse_date(date_str)
                        
                        # Get amounts
                        paid_in = self._parse_amount(col_texts.get('paid_in', ''))
                        withdrawn = self._parse_amount(col_texts.get('withdrawn', ''))
                        
                        if withdrawn and withdrawn > 0:
                            amount = withdrawn
                            direction = 'debit'
                        elif paid_in and paid_in > 0:
                            amount = paid_in
                            direction = 'credit'
                        else:
                            amount = None
                            direction = 'credit'
                        
                        current_txn = {
                            'account_id': f'NATWEST_POS_P{page_num + 1}',
                            'date': parsed_date,
                            'amount': abs(amount) if amount else None,
                            'currency': 'GBP',
                            'direction': direction,
                            'description': col_texts.get('description', ''),
                            'counterparty_name': '',
                            'balance': self._parse_amount(col_texts.get('balance', '')),
                            'source': f'position_p{page_num + 1}'
                        }
                    elif current_txn:
                        # Continuation row - append description
                        desc_text = col_texts.get('description', '')
                        if desc_text and len(desc_text) > 1:
                            current_txn['description'] = (current_txn['description'] + ' ' + desc_text).strip()
                        
                        # Check for amount on continuation row
                        if not current_txn.get('amount'):
                            paid_in = self._parse_amount(col_texts.get('paid_in', ''))
                            withdrawn = self._parse_amount(col_texts.get('withdrawn', ''))
                            
                            if withdrawn and withdrawn > 0:
                                current_txn['amount'] = withdrawn
                                current_txn['direction'] = 'debit'
                            elif paid_in and paid_in > 0:
                                current_txn['amount'] = paid_in
                                current_txn['direction'] = 'credit'
                
                # Don't forget last
                if current_txn and current_txn.get('amount'):
                    transactions.append(current_txn)
            
            doc.close()
        
        except Exception as e:
            print(f"   ⚠️ Position extraction error: {e}")
            import traceback
            traceback.print_exc()
        
        return transactions
    
    def _detect_column_boundaries(self, rows: List[List[Dict]]) -> Dict[str, Tuple[float, float]]:
        """Detect column boundaries from text positions."""
        # Default boundaries for typical NatWest format
        # Date | Description | Paid In | Withdrawn | Balance
        # These are approximate x-positions
        return {
            'date': (0, 80),
            'description': (80, 550),
            'paid_in': (550, 680),
            'withdrawn': (680, 800),
            'balance': (800, 1000)
        }
    
    def _assign_text_to_columns(self, row: List[Dict], boundaries: Dict) -> Dict[str, str]:
        """Assign row text to columns based on x position."""
        result = {'date': '', 'description': '', 'paid_in': '', 'withdrawn': '', 'balance': ''}
        
        for span in row:
            x = span['x0']
            text = span['text']
            
            # Find which column this belongs to
            for col_name, (x_min, x_max) in boundaries.items():
                if x_min <= x < x_max:
                    if result[col_name]:
                        result[col_name] += ' ' + text
                    else:
                        result[col_name] = text
                    break
        
        return result
    
    def _extract_by_line_grouping(self, content: bytes, metadata: Dict) -> List[Dict]:
        """
        Extract transactions using PyMuPDF with proper column position detection.
        NatWest PDFs have: Date | Description | Paid In(£) | Withdrawn(£) | Balance(£)
        
        Key insight: Many rows DON'T have dates - they share the date with previous rows.
        A new transaction is identified when we see a new balance value on a row.
        """
        transactions = []
        
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            
            # Track the last seen date across pages
            last_date = None
            
            for page_num, page in enumerate(doc):
                # Get all text with position info
                blocks = page.get_text("dict")["blocks"]
                
                # Collect all text spans with positions
                all_spans = []
                for block in blocks:
                    if "lines" not in block:
                        continue
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if text:
                                all_spans.append({
                                    "text": text,
                                    "x0": span["bbox"][0],
                                    "y0": span["bbox"][1],
                                    "x1": span["bbox"][2],
                                    "y1": span["bbox"][3]
                                })
                
                # Sort by y position (row), then x position (column)
                all_spans.sort(key=lambda s: (round(s["y0"]/5)*5, s["x0"]))
                
                # NatWest-specific column boundaries (from PDF analysis)
                DATE_MAX = 100
                DESC_MAX = 350
                PAID_IN_MAX = 420
                WITHDRAWN_MAX = 480
                
                # Group spans by row (similar y position)
                rows = []
                current_row = []
                current_y = None
                
                for span in all_spans:
                    y = round(span["y0"]/5)*5
                    if current_y is None or abs(y - current_y) < 8:
                        current_row.append(span)
                        current_y = y
                    else:
                        if current_row:
                            rows.append(current_row)
                        current_row = [span]
                        current_y = y
                
                if current_row:
                    rows.append(current_row)
                
                # Process rows to extract transactions
                # Key: Build up a transaction until we see a balance, then save it
                current_txn = None
                
                for row in rows:
                    # Get text by column position
                    date_text = ""
                    desc_text = ""
                    paid_in_text = ""
                    withdrawn_text = ""
                    balance_text = ""
                    
                    for span in row:
                        x = span["x0"]
                        text = span["text"]
                        
                        if x < DATE_MAX:
                            date_text += " " + text
                        elif x < DESC_MAX:
                            desc_text += " " + text
                        elif x < PAID_IN_MAX:
                            paid_in_text += " " + text
                        elif x < WITHDRAWN_MAX:
                            withdrawn_text += " " + text
                        else:
                            balance_text += " " + text
                    
                    date_text = date_text.strip()
                    desc_text = desc_text.strip()
                    paid_in_text = paid_in_text.strip()
                    withdrawn_text = withdrawn_text.strip()
                    balance_text = balance_text.strip()
                    
                    # Skip header/footer rows
                    row_text = " ".join([s["text"] for s in row]).lower()
                    if any(skip in row_text for skip in [
                        "account name", "account no", "sort code", "page no", 
                        "statement date", "period covered", "previous balance", 
                        "new balance", "paid in(£)", "withdrawn(£)", "balance(£)",
                        "brought forward", "carried forward", "natwest", 
                        "registered", "authorised", "financial services", 
                        "interest", "overdraft", "welcome to", "why file",
                        "bic", "iban", "select account", "summary",
                        "retstmt", "www.natwest", "date description"
                    ]):
                        continue
                    
                    # Check for date in date column - update last_date if found
                    date_str = self._find_date_in_text(date_text)
                    if date_str:
                        last_date = self._parse_date(date_str)
                    
                    # Parse amounts
                    paid_in_amount = self._parse_amount(paid_in_text)
                    withdrawn_amount = self._parse_amount(withdrawn_text)
                    balance_amount = self._parse_amount(balance_text)
                    
                    # Determine if this row has meaningful data
                    has_amount = (paid_in_amount and paid_in_amount > 0) or (withdrawn_amount and withdrawn_amount > 0)
                    has_balance = balance_amount and balance_amount > 0
                    has_desc = desc_text and len(desc_text) > 2
                    
                    # If we have a balance, this completes a transaction
                    if has_balance:
                        if current_txn is None:
                            # Start new transaction
                            current_txn = {
                                "account_id": f"NATWEST_P{page_num+1}",
                                "date": last_date,
                                "amount": None,
                                "currency": "GBP",
                                "direction": "unknown",
                                "description": desc_text if has_desc else "",
                                "counterparty_name": "",
                                "balance": balance_amount,
                                "source": "line_position"
                            }
                        else:
                            # Add to existing transaction
                            if has_desc:
                                current_txn["description"] = (current_txn["description"] + " " + desc_text).strip()
                            current_txn["balance"] = balance_amount
                        
                        # Set amount and direction
                        if withdrawn_amount and withdrawn_amount > 0:
                            current_txn["amount"] = withdrawn_amount
                            current_txn["direction"] = "debit"
                        elif paid_in_amount and paid_in_amount > 0:
                            current_txn["amount"] = paid_in_amount
                            current_txn["direction"] = "credit"
                        elif current_txn.get("amount") is None:
                            # No amount on this row, check if we accumulated one
                            pass
                        
                        # Save transaction if it has an amount
                        if current_txn.get("amount"):
                            # Update date if we have one
                            if current_txn.get("date") is None:
                                current_txn["date"] = last_date
                            transactions.append(current_txn)
                        
                        current_txn = None
                    
                    elif has_desc or has_amount:
                        # Row with description or amount but no balance yet
                        if current_txn is None:
                            current_txn = {
                                "account_id": f"NATWEST_P{page_num+1}",
                                "date": last_date,
                                "amount": None,
                                "currency": "GBP",
                                "direction": "unknown",
                                "description": desc_text if has_desc else "",
                                "counterparty_name": "",
                                "balance": None,
                                "source": "line_position"
                            }
                        else:
                            if has_desc:
                                current_txn["description"] = (current_txn["description"] + " " + desc_text).strip()
                        
                        # Track amounts found on this row
                        if withdrawn_amount and withdrawn_amount > 0:
                            current_txn["amount"] = withdrawn_amount
                            current_txn["direction"] = "debit"
                        elif paid_in_amount and paid_in_amount > 0:
                            current_txn["amount"] = paid_in_amount
                            current_txn["direction"] = "credit"
            
            doc.close()
        
        except Exception as e:
            print(f"   ⚠️ Line grouping error: {e}")
            import traceback
            traceback.print_exc()
        
        return transactions
    
    def _find_header_row(self, table: List[List]) -> Optional[int]:
        """Find the header row in a NatWest table."""
        for idx in range(min(10, len(table))):
            row = table[idx]
            if not row:
                continue
            
            row_text = ' '.join([str(c).lower() for c in row if c])
            
            # NatWest headers typically include these
            if ('date' in row_text or 'transaction' in row_text) and \
               ('paid' in row_text or 'balance' in row_text or 'amount' in row_text):
                return idx
        
        return 0  # Default to first row
    
    def _find_date_in_row(self, row: List[str]) -> Optional[str]:
        """Find a date in a table row."""
        for cell in row:
            date_str = self._find_date_in_text(cell)
            if date_str:
                return date_str
        return None
    
    def _find_date_in_text(self, text: str) -> Optional[str]:
        """Find a NatWest-style date in text."""
        for pattern in self.date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group()
        return None
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse NatWest date format to ISO."""
        if not date_str:
            return None
        
        for pattern in self.date_patterns:
            match = re.match(pattern, date_str, re.IGNORECASE)
            if match:
                day = int(match.group(1))
                month_str = match.group(2).lower()
                month = self.month_map.get(month_str[:3], 1)
                
                # Year might be in group 3
                year = None
                if match.group(3):
                    year = int(match.group(3))
                    if year < 100:
                        year += 2000 if year < 50 else 1900
                
                if not year:
                    year = datetime.now().year
                
                try:
                    return f"{year:04d}-{month:02d}-{day:02d}"
                except:
                    return None
        
        return None
    
    def _extract_amount_from_row(self, row: List[str]) -> Tuple[Optional[float], str]:
        """Extract amount and direction from table row."""
        # NatWest typically has separate paid out / paid in columns
        amounts = []
        
        for i, cell in enumerate(row):
            if cell and self._is_amount(cell):
                val = self._parse_amount(cell)
                if val and val > 0:
                    amounts.append((i, val, cell))
        
        if not amounts:
            return None, 'credit'
        
        # In NatWest format:
        # - Earlier column (lower index) = paid out (debit)
        # - Later column (higher index) = paid in (credit) or balance
        
        if len(amounts) == 1:
            # Single amount - check for negative signs or keywords
            _, amount, original = amounts[0]
            if '-' in original or original.startswith('('):
                return amount, 'debit'
            return amount, 'credit'
        
        elif len(amounts) >= 2:
            # Multiple amounts - first non-zero is usually the transaction amount
            # Last is usually balance
            for idx, amount, original in amounts[:-1]:  # Exclude last (balance)
                if amount > 0:
                    # Determine direction by column position
                    # Typically: Date | Description | Paid Out | Paid In | Balance
                    # So paid out is around column 2-3, paid in is 3-4
                    if idx <= 2:
                        return amount, 'debit'
                    else:
                        return amount, 'credit'
        
        return amounts[0][1], 'credit'
    
    def _extract_amount_from_text(self, text: str) -> Tuple[Optional[float], str]:
        """Extract amount from text string."""
        # Find all amounts
        amounts = re.findall(r'-?£?\s*([\d,]+\.\d{2})', text)
        
        if not amounts:
            return None, 'credit'
        
        # Get first valid amount
        for amt_str in amounts:
            try:
                amount = float(amt_str.replace(',', ''))
                if amount > 0:
                    # Check for debit indicators
                    if '-' in text[:text.find(amt_str)] or \
                       any(kw in text.lower() for kw in self.debit_keywords):
                        return amount, 'debit'
                    return amount, 'credit'
            except:
                continue
        
        return None, 'credit'
    
    def _extract_description_from_row(self, row: List[str], date_str: str) -> str:
        """Extract description from row, excluding date and amounts."""
        parts = []
        
        for cell in row:
            if not cell:
                continue
            if cell == date_str:
                continue
            if self._is_amount(cell):
                continue
            if len(cell) > 2:
                parts.append(cell)
        
        return ' '.join(parts).strip()
    
    def _extract_balance_from_row(self, row: List[str]) -> Optional[float]:
        """Extract balance (typically last amount column)."""
        amounts = []
        for cell in row:
            if cell and self._is_amount(cell):
                val = self._parse_amount(cell)
                if val is not None:
                    amounts.append(val)
        
        if amounts:
            return amounts[-1]  # Last amount is usually balance
        return None
    
    def _clean_description(self, text: str, date_str: str) -> str:
        """Clean description text."""
        # Remove date
        text = text.replace(date_str, '')
        
        # Remove amounts
        text = re.sub(r'-?£?\s*[\d,]+\.\d{2}', '', text)
        
        # Clean up
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _is_amount(self, text: str) -> bool:
        """Check if text looks like an amount."""
        if not text:
            return False
        text = text.strip()
        # Remove currency symbols
        text = re.sub(r'[£$€]', '', text)
        # Check pattern
        return bool(re.match(r'^-?\s*[\d,]+\.\d{2}$', text.strip()))
    
    def _parse_amount(self, text: str) -> Optional[float]:
        """Parse amount from text."""
        if not text:
            return None
        
        text = text.strip()
        text = re.sub(r'[£$€]', '', text)
        text = text.replace(',', '').replace(' ', '')
        
        # Handle negative formats
        is_negative = False
        if text.startswith('(') and text.endswith(')'):
            is_negative = True
            text = text[1:-1]
        elif text.startswith('-'):
            is_negative = True
            text = text[1:]
        elif text.endswith('-'):
            is_negative = True
            text = text[:-1]
        
        try:
            amount = float(text)
            return -amount if is_negative else amount
        except:
            return None
    
    def _deduplicate(self, transactions: List[Dict]) -> List[Dict]:
        """Remove duplicate transactions - only exact duplicates on same date."""
        seen = set()
        unique = []
        
        for txn in transactions:
            # Create a key from date, amount, AND full description
            # Only remove true duplicates (same date, amount, and description)
            description = txn.get('description', '')
            
            # Use more of the description to avoid false positives
            # Truncate at 100 chars to handle minor variations
            key = (
                txn.get('date'),
                round(txn.get('amount', 0), 2),
                description[:100] if description else ''
            )
            
            if key not in seen:
                seen.add(key)
                unique.append(txn)
            else:
                # Log when we skip a duplicate (helps with debugging)
                print(f"   ⚠️ Skipping duplicate: {txn.get('date')} | £{txn.get('amount', 0):,.2f} | {description[:30]}")
        
        if len(transactions) != len(unique):
            print(f"   📊 Deduplication: {len(transactions)} → {len(unique)} transactions ({len(transactions) - len(unique)} duplicates removed)")
        
        return unique


# Create singleton instance
natwest_parser = NatWestStatementParser()
