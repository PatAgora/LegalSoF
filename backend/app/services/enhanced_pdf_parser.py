"""
Enhanced PDF Transaction Parser
Robust extraction for UK bank statements including NatWest, HSBC, Barclays, etc.
"""

import re
import io
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import pdfplumber
import fitz  # PyMuPDF

class EnhancedPDFParser:
    """
    Advanced PDF parser specifically designed for UK bank statements.
    Handles multi-page statements, various formats, and complex table structures.
    """
    
    def __init__(self):
        # UK date formats
        self.date_patterns = [
            (r'(\d{2})[/-](\d{2})[/-](\d{4})', '%d/%m/%Y'),  # DD/MM/YYYY
            (r'(\d{2})[/-](\d{2})[/-](\d{2})', '%d/%m/%y'),  # DD/MM/YY
            (r'(\d{4})[/-](\d{2})[/-](\d{2})', '%Y/%m/%d'),  # YYYY/MM/DD
            (r'(\d{2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})', '%d %b %Y'),  # DD Mon YYYY
        ]
        
        # Amount patterns
        self.amount_pattern = re.compile(r'[£$€]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)')
        
        # Known bank statement headers (case-insensitive)
        self.header_keywords = [
            'date', 'transaction', 'description', 'details', 'narrative', 
            'particulars', 'amount', 'debit', 'credit', 'balance', 
            'paid in', 'paid out', 'money in', 'money out', 'value'
        ]
    
    def parse_pdf(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Main entry point for PDF parsing.
        Returns dict with transactions and metadata.
        """
        try:
            transactions = []
            metadata = {
                'pages_processed': 0,
                'tables_found': 0,
                'text_extraction_used': False,
                'transactions_extracted': 0
            }
            
            # Try pdfplumber first (best for structured PDFs)
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    metadata['pages_processed'] += 1
                    print(f"\n📄 Processing page {page_num}/{len(pdf.pages)}")
                    
                    # Extract tables
                    tables = page.extract_tables()
                    metadata['tables_found'] += len(tables)
                    print(f"   Found {len(tables)} tables")
                    
                    if tables:
                        for table_idx, table in enumerate(tables):
                            table_transactions = self._parse_table(table, page_num, table_idx)
                            transactions.extend(table_transactions)
                            print(f"   Table {table_idx}: extracted {len(table_transactions)} transactions")
                    
                    # Fallback: text extraction if tables didn't work well
                    if not transactions or len(transactions) < page_num:
                        text = page.extract_text()
                        if text:
                            metadata['text_extraction_used'] = True
                            text_transactions = self._parse_text(text, page_num)
                            transactions.extend(text_transactions)
                            print(f"   Text extraction: {len(text_transactions)} transactions")
            
            # Remove duplicates
            transactions = self._deduplicate_transactions(transactions)
            metadata['transactions_extracted'] = len(transactions)
            
            print(f"\n✅ Total extracted: {len(transactions)} transactions")
            print(f"📊 Metadata: {metadata}")
            
            return {
                'success': len(transactions) > 0,
                'transactions': transactions,
                'metadata': metadata,
                'error': None if transactions else "No transactions could be extracted"
            }
        
        except Exception as e:
            print(f"❌ PDF parsing error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'transactions': [],
                'metadata': {},
                'error': str(e)
            }
    
    def _parse_table(self, table: List[List[str]], page_num: int, table_idx: int) -> List[Dict]:
        """
        Parse a table extracted from PDF.
        Handles various table structures and missing headers.
        """
        if not table or len(table) < 2:
            return []
        
        transactions = []
        
        # Find header row (might not be first row)
        header_row_idx = self._find_header_row(table)
        if header_row_idx is None:
            # No header found, use positional parsing
            return self._parse_table_positional(table, page_num, table_idx)
        
        header = [str(cell).lower().strip() if cell else '' for cell in table[header_row_idx]]
        print(f"      Header: {header[:5]}...")  # Debug
        
        # Find column indices
        date_col = self._find_column(header, ['date', 'trans date', 'posting date'])
        desc_col = self._find_column(header, ['description', 'details', 'narrative', 'type', 'transaction'])
        amount_col = self._find_column(header, ['amount', 'value'])
        debit_col = self._find_column(header, ['paid out', 'debit', 'payments', 'money out'])
        credit_col = self._find_column(header, ['paid in', 'credit', 'receipts', 'money in'])
        balance_col = self._find_column(header, ['balance', 'running balance'])
        
        # Parse data rows
        for row_idx in range(header_row_idx + 1, len(table)):
            row = table[row_idx]
            if not row or all(not cell for cell in row):
                continue
            
            txn = self._extract_transaction_from_row(
                row, date_col, desc_col, amount_col, 
                debit_col, credit_col, balance_col,
                page_num, table_idx, row_idx
            )
            
            if txn:
                transactions.append(txn)
        
        return transactions
    
    def _parse_table_positional(self, table: List[List[str]], page_num: int, table_idx: int) -> List[Dict]:
        """
        Parse table without headers using positional heuristics.
        Typical UK bank statement: Date | Description | Paid Out | Paid In | Balance
        """
        transactions = []
        
        for row_idx, row in enumerate(table):
            if not row or len(row) < 3:
                continue
            
            # Try to find date in first few columns
            date_str = None
            date_col = None
            for col_idx in range(min(3, len(row))):
                cell = str(row[col_idx]).strip()
                if self._is_date(cell):
                    date_str = cell
                    date_col = col_idx
                    break
            
            if not date_str:
                continue
            
            # Find amounts (look for patterns like 1,234.56)
            amounts = []
            for col_idx, cell in enumerate(row):
                if col_idx == date_col:
                    continue
                cell_str = str(cell).strip()
                match = self.amount_pattern.search(cell_str)
                if match:
                    try:
                        amount_val = float(match.group(1).replace(',', ''))
                        amounts.append((col_idx, amount_val, cell_str))
                    except:
                        pass
            
            if not amounts:
                continue
            
            # Build description from non-date, non-amount cells
            description_parts = []
            for col_idx, cell in enumerate(row):
                if col_idx == date_col:
                    continue
                if any(col_idx == amt[0] for amt in amounts):
                    continue
                cell_str = str(cell).strip()
                if cell_str and len(cell_str) > 1:
                    description_parts.append(cell_str)
            
            description = ' '.join(description_parts) if description_parts else 'Transaction'
            
            # Parse date
            parsed_date = self._parse_date(date_str)
            if not parsed_date:
                continue
            
            # Determine amount and direction
            # If two amounts, usually: paid out | paid in
            if len(amounts) >= 2:
                # Check which is non-zero
                if amounts[0][1] > 0:
                    amount = amounts[0][1]
                    direction = 'debit'
                else:
                    amount = amounts[1][1]
                    direction = 'credit'
            else:
                amount = amounts[0][1]
                # Check for negative indicator
                if '-' in amounts[0][2] or '(' in amounts[0][2]:
                    direction = 'debit'
                else:
                    direction = 'credit'
            
            transactions.append({
                'account_id': f'PDF_P{page_num}_T{table_idx}',
                'date': parsed_date,
                'amount': abs(amount),
                'currency': 'GBP',
                'direction': direction,
                'description': description[:200],
                'counterparty_name': '',
                'balance': None,
                'source': f'page_{page_num}_table_{table_idx}_row_{row_idx}'
            })
        
        return transactions
    
    def _extract_transaction_from_row(
        self, row: List[str], date_col: Optional[int], desc_col: Optional[int],
        amount_col: Optional[int], debit_col: Optional[int], credit_col: Optional[int],
        balance_col: Optional[int], page_num: int, table_idx: int, row_idx: int
    ) -> Optional[Dict]:
        """Extract single transaction from table row."""
        try:
            # Get date
            date_str = None
            if date_col is not None and date_col < len(row):
                date_str = str(row[date_col]).strip()
            
            if not date_str or not self._is_date(date_str):
                return None
            
            parsed_date = self._parse_date(date_str)
            if not parsed_date:
                return None
            
            # Get description
            description = ''
            if desc_col is not None and desc_col < len(row):
                description = str(row[desc_col]).strip()
            
            # Get amount - try different columns
            amount = None
            direction = None
            
            # Try debit column
            if debit_col is not None and debit_col < len(row):
                debit_str = str(row[debit_col]).strip()
                if debit_str and debit_str.lower() not in ['', 'none', 'null']:
                    match = self.amount_pattern.search(debit_str)
                    if match:
                        amount = float(match.group(1).replace(',', ''))
                        direction = 'debit'
            
            # Try credit column
            if amount is None and credit_col is not None and credit_col < len(row):
                credit_str = str(row[credit_col]).strip()
                if credit_str and credit_str.lower() not in ['', 'none', 'null']:
                    match = self.amount_pattern.search(credit_str)
                    if match:
                        amount = float(match.group(1).replace(',', ''))
                        direction = 'credit'
            
            # Try single amount column
            if amount is None and amount_col is not None and amount_col < len(row):
                amount_str = str(row[amount_col]).strip()
                if amount_str and amount_str.lower() not in ['', 'none', 'null']:
                    match = self.amount_pattern.search(amount_str)
                    if match:
                        amount = float(match.group(1).replace(',', ''))
                        # Determine direction from sign
                        if '-' in amount_str or '(' in amount_str:
                            direction = 'debit'
                        else:
                            direction = 'credit'
            
            if amount is None or amount == 0:
                return None
            
            # Get balance
            balance = None
            if balance_col is not None and balance_col < len(row):
                balance_str = str(row[balance_col]).strip()
                match = self.amount_pattern.search(balance_str)
                if match:
                    try:
                        balance = float(match.group(1).replace(',', ''))
                    except:
                        pass
            
            return {
                'account_id': f'PDF_P{page_num}_T{table_idx}',
                'date': parsed_date,
                'amount': abs(amount),
                'currency': 'GBP',
                'direction': direction or 'credit',
                'description': description[:200] if description else 'Transaction',
                'counterparty_name': '',
                'balance': balance,
                'source': f'page_{page_num}_table_{table_idx}_row_{row_idx}'
            }
        
        except Exception as e:
            print(f"      Row parsing error: {e}")
            return None
    
    def _parse_text(self, text: str, page_num: int) -> List[Dict]:
        """
        Parse transactions from plain text using regex patterns.
        Fallback method when table extraction fails.
        """
        transactions = []
        lines = text.split('\n')
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if len(line) < 15:  # Too short to be a transaction
                continue
            
            # Look for date pattern
            date_match = None
            parsed_date = None
            for pattern, fmt in self.date_patterns:
                match = re.search(pattern, line)
                if match:
                    try:
                        date_str = match.group(0)
                        parsed_date = self._parse_date(date_str)
                        if parsed_date:
                            date_match = match
                            break
                    except:
                        continue
            
            if not date_match or not parsed_date:
                continue
            
            # Look for amount
            amounts = list(self.amount_pattern.finditer(line))
            if not amounts:
                continue
            
            # Extract description (text between date and first amount)
            desc_start = date_match.end()
            desc_end = amounts[0].start()
            description = line[desc_start:desc_end].strip()
            
            # Determine amount and direction
            if len(amounts) >= 2:
                # Usually: debit amount | credit amount
                debit = float(amounts[0].group(1).replace(',', ''))
                credit = float(amounts[1].group(1).replace(',', ''))
                
                if debit > 0:
                    amount = debit
                    direction = 'debit'
                else:
                    amount = credit
                    direction = 'credit'
            else:
                amount = float(amounts[0].group(1).replace(',', ''))
                direction = 'credit'  # Default
            
            if amount > 0:
                transactions.append({
                    'account_id': f'PDF_P{page_num}_TEXT',
                    'date': parsed_date,
                    'amount': amount,
                    'currency': 'GBP',
                    'direction': direction,
                    'description': description[:200] if description else 'Transaction',
                    'counterparty_name': '',
                    'balance': None,
                    'source': f'page_{page_num}_text_line_{line_idx}'
                })
        
        return transactions
    
    def _find_header_row(self, table: List[List[str]]) -> Optional[int]:
        """Find the row that contains column headers."""
        for row_idx in range(min(5, len(table))):  # Check first 5 rows
            row = table[row_idx]
            row_text = ' '.join([str(cell).lower() for cell in row if cell]).strip()
            
            # Count how many header keywords are in this row
            keyword_count = sum(1 for keyword in self.header_keywords if keyword in row_text)
            
            if keyword_count >= 2:  # At least 2 keywords found
                return row_idx
        
        return None
    
    def _find_column(self, header: List[str], keywords: List[str]) -> Optional[int]:
        """Find column index by searching for keywords."""
        for col_idx, cell in enumerate(header):
            cell_lower = cell.lower().strip()
            for keyword in keywords:
                if keyword in cell_lower:
                    return col_idx
        return None
    
    def _is_date(self, text: str) -> bool:
        """Check if text looks like a date."""
        for pattern, _ in self.date_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to YYYY-MM-DD format."""
        for pattern, fmt in self.date_patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    # Handle different date formats
                    if fmt == '%d %b %Y':
                        date_obj = datetime.strptime(match.group(0), fmt)
                    else:
                        date_obj = datetime.strptime(match.group(0), fmt)
                    
                    return date_obj.strftime('%Y-%m-%d')
                except Exception as e:
                    continue
        return None
    
    def _deduplicate_transactions(self, transactions: List[Dict]) -> List[Dict]:
        """Remove duplicate transactions based on date + amount + description."""
        seen = set()
        unique = []
        
        for txn in transactions:
            key = (txn['date'], txn['amount'], txn['description'][:50])
            if key not in seen:
                seen.add(key)
                unique.append(txn)
        
        return unique


# Singleton instance
enhanced_pdf_parser = EnhancedPDFParser()
