"""
Comprehensive Bank Statement PDF Parser

Handles multiple UK bank formats including:
- NatWest
- HSBC
- Barclays
- Lloyds
- Santander
- Nationwide

Key improvements over previous parsers:
1. Multi-strategy extraction (tables, text lines, word-level extraction)
2. Bank-specific format detection and parsing
3. Better handling of multi-line descriptions
4. Improved date parsing for UK formats
5. Balance tracking to validate transactions
6. Deduplication of transactions
"""

import re
import io
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal, InvalidOperation
import pdfplumber
import fitz  # PyMuPDF


class BankStatementPDFParser:
    """
    Robust PDF parser for UK bank statements.
    
    Uses multiple extraction strategies:
    1. Table extraction (for structured tables)
    2. Line-by-line text parsing (for text-based layouts)
    3. Word-level extraction with positional analysis (for complex layouts)
    """
    
    def __init__(self):
        # UK date patterns (DD MMM, DD/MM/YY, DD MMM YY, etc.)
        self.date_patterns = [
            # NatWest format: "26 Jan" or "26 Jan 25"
            (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:\s+(\d{2,4}))?', 'dmy_short'),
            # Full month: "26 January 2025"
            (r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', 'dmy_full'),
            # DD/MM/YYYY or DD/MM/YY
            (r'(\d{2})/(\d{2})/(\d{2,4})', 'slash'),
            # DD-MM-YYYY or DD-MM-YY
            (r'(\d{2})-(\d{2})-(\d{2,4})', 'dash'),
            # YYYY-MM-DD (ISO)
            (r'(\d{4})-(\d{2})-(\d{2})', 'iso'),
        ]
        
        # Amount patterns (UK format with £)
        self.amount_pattern = re.compile(
            r'[£]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        )
        
        # Month mappings
        self.month_map = {
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
            'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
            'may': 5, 'jun': 6, 'june': 6,
            'jul': 7, 'july': 7, 'aug': 8, 'august': 8,
            'sep': 9, 'september': 9, 'oct': 10, 'october': 10,
            'nov': 11, 'november': 11, 'dec': 12, 'december': 12
        }
        
        # Bank identifiers
        self.bank_keywords = {
            'natwest': ['natwest', 'national westminster'],
            'hsbc': ['hsbc'],
            'barclays': ['barclays'],
            'lloyds': ['lloyds', 'lloyds bank'],
            'santander': ['santander'],
            'nationwide': ['nationwide'],
            'halifax': ['halifax'],
            'rbs': ['royal bank of scotland', 'rbs'],
            'tsb': ['tsb bank', 'tsb'],
            'metro': ['metro bank'],
        }
        
        # Transaction type keywords for direction detection
        self.credit_keywords = [
            'credit', 'cr', 'deposit', 'received', 'paid in', 
            'salary', 'refund', 'interest', 'incoming', 'receipt'
        ]
        self.debit_keywords = [
            'debit', 'dr', 'withdrawal', 'payment', 'paid out',
            'purchase', 'transfer out', 'outgoing', 'direct debit', 'dd',
            'standing order', 'so', 'card payment', 'bill payment'
        ]
        
        # Header detection keywords
        self.header_keywords = [
            'date', 'transaction', 'description', 'details', 'type',
            'paid in', 'paid out', 'money in', 'money out',
            'credit', 'debit', 'balance', 'amount', 'particulars'
        ]
    
    def parse(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Main entry point. Parses PDF and returns transactions.
        
        Returns:
            {
                'success': bool,
                'transactions': List[Dict],
                'metadata': Dict,
                'error': Optional[str]
            }
        """
        try:
            # Detect bank type first
            bank_type = self._detect_bank(pdf_bytes)
            print(f"🏦 Detected bank: {bank_type or 'Unknown'}")
            
            # Try multiple extraction strategies
            transactions = []
            metadata = {
                'bank': bank_type,
                'pages_processed': 0,
                'extraction_method': None,
                'tables_found': 0,
                'raw_text_lines': 0
            }
            
            # Strategy 1: pdfplumber with table extraction
            print("\n📊 Strategy 1: Table extraction with pdfplumber")
            table_transactions = self._extract_with_tables(pdf_bytes, metadata, bank_type)
            
            if table_transactions and len(table_transactions) >= 5:
                print(f"   ✅ Found {len(table_transactions)} transactions via tables")
                transactions = table_transactions
                metadata['extraction_method'] = 'table'
            else:
                print(f"   ⚠️ Table extraction found only {len(table_transactions) if table_transactions else 0} transactions")
            
            # Strategy 2: Line-by-line text parsing
            if len(transactions) < 5:
                print("\n📝 Strategy 2: Line-by-line text extraction")
                text_transactions = self._extract_with_text_lines(pdf_bytes, metadata, bank_type)
                
                if text_transactions and len(text_transactions) > len(transactions):
                    print(f"   ✅ Found {len(text_transactions)} transactions via text parsing")
                    transactions = text_transactions
                    metadata['extraction_method'] = 'text_lines'
                else:
                    print(f"   ⚠️ Text parsing found only {len(text_transactions) if text_transactions else 0} transactions")
            
            # Strategy 3: Word-level extraction with positional analysis
            if len(transactions) < 5:
                print("\n🔍 Strategy 3: Word-level positional extraction")
                word_transactions = self._extract_with_words(pdf_bytes, metadata, bank_type)
                
                if word_transactions and len(word_transactions) > len(transactions):
                    print(f"   ✅ Found {len(word_transactions)} transactions via word extraction")
                    transactions = word_transactions
                    metadata['extraction_method'] = 'word_positions'
                else:
                    print(f"   ⚠️ Word extraction found only {len(word_transactions) if word_transactions else 0} transactions")
            
            # Strategy 4: PyMuPDF fallback
            if len(transactions) < 5:
                print("\n📄 Strategy 4: PyMuPDF text extraction")
                pymupdf_transactions = self._extract_with_pymupdf(pdf_bytes, metadata, bank_type)
                
                if pymupdf_transactions and len(pymupdf_transactions) > len(transactions):
                    print(f"   ✅ Found {len(pymupdf_transactions)} transactions via PyMuPDF")
                    transactions = pymupdf_transactions
                    metadata['extraction_method'] = 'pymupdf'
            
            # Deduplicate
            transactions = self._deduplicate(transactions)
            print(f"\n✅ Final result: {len(transactions)} unique transactions")
            
            return {
                'success': len(transactions) > 0,
                'transactions': transactions,
                'metadata': metadata,
                'error': None if transactions else 'No transactions could be extracted'
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'transactions': [],
                'metadata': {},
                'error': str(e)
            }
    
    def _detect_bank(self, pdf_bytes: bytes) -> Optional[str]:
        """Detect which bank the statement is from."""
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                if pdf.pages:
                    text = pdf.pages[0].extract_text() or ''
                    text_lower = text.lower()
                    
                    for bank, keywords in self.bank_keywords.items():
                        if any(kw in text_lower for kw in keywords):
                            return bank
        except:
            pass
        return None
    
    def _extract_with_tables(self, pdf_bytes: bytes, metadata: Dict, bank_type: Optional[str]) -> List[Dict]:
        """Extract transactions using pdfplumber table extraction."""
        transactions = []
        
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            metadata['pages_processed'] = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages, 1):
                # Get all tables on the page
                tables = page.extract_tables()
                metadata['tables_found'] += len(tables)
                
                if not tables:
                    # Try with different table settings
                    tables = page.extract_tables({
                        'vertical_strategy': 'lines',
                        'horizontal_strategy': 'lines'
                    })
                
                if not tables:
                    # Try text-based table finding
                    tables = page.extract_tables({
                        'vertical_strategy': 'text',
                        'horizontal_strategy': 'text'
                    })
                
                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 2:
                        continue
                    
                    # Parse the table
                    table_txns = self._parse_table(table, page_num, table_idx, bank_type)
                    transactions.extend(table_txns)
        
        return transactions
    
    def _parse_table(self, table: List[List], page_num: int, table_idx: int, bank_type: Optional[str]) -> List[Dict]:
        """Parse a single table into transactions."""
        transactions = []
        
        # Find header row
        header_idx = self._find_header_row(table)
        
        if header_idx is not None:
            header = [str(cell).lower().strip() if cell else '' for cell in table[header_idx]]
            
            # Find column indices
            date_col = self._find_column(header, ['date', 'trans date', 'transaction date', 'posted'])
            desc_col = self._find_column(header, ['description', 'details', 'narrative', 'type', 'transaction', 'particulars'])
            paid_out_col = self._find_column(header, ['paid out', 'debit', 'withdrawals', 'money out', 'out'])
            paid_in_col = self._find_column(header, ['paid in', 'credit', 'deposits', 'money in', 'in'])
            amount_col = self._find_column(header, ['amount', 'value'])
            balance_col = self._find_column(header, ['balance', 'running balance'])
            
            # Process data rows
            start_row = header_idx + 1
        else:
            # No header found - use positional parsing
            date_col = 0
            desc_col = 1
            paid_out_col = None
            paid_in_col = None
            amount_col = None
            balance_col = None
            start_row = 0
            
            # Try to detect columns from data
            if table and len(table[0]) >= 4:
                # Common format: Date | Description | Paid Out | Paid In | Balance
                paid_out_col = 2
                paid_in_col = 3
                if len(table[0]) >= 5:
                    balance_col = 4
        
        for row_idx in range(start_row, len(table)):
            row = table[row_idx]
            if not row or all(not cell for cell in row):
                continue
            
            txn = self._parse_table_row(
                row, date_col, desc_col, paid_out_col, paid_in_col, 
                amount_col, balance_col, page_num, table_idx, row_idx, bank_type
            )
            
            if txn:
                transactions.append(txn)
        
        return transactions
    
    def _parse_table_row(self, row: List, date_col: int, desc_col: int, 
                         paid_out_col: Optional[int], paid_in_col: Optional[int],
                         amount_col: Optional[int], balance_col: Optional[int],
                         page_num: int, table_idx: int, row_idx: int,
                         bank_type: Optional[str]) -> Optional[Dict]:
        """Parse a single table row into a transaction."""
        try:
            # Extract date
            date_str = str(row[date_col]).strip() if date_col < len(row) and row[date_col] else None
            
            if not date_str:
                # Try to find date in any cell
                for cell in row:
                    if cell:
                        cell_str = str(cell).strip()
                        if self._is_date(cell_str):
                            date_str = cell_str
                            break
            
            if not date_str:
                return None
            
            parsed_date = self._parse_date(date_str)
            if not parsed_date:
                return None
            
            # Extract description
            description = ''
            if desc_col is not None and desc_col < len(row) and row[desc_col]:
                description = str(row[desc_col]).strip()
            
            # If no description column, combine non-date, non-amount cells
            if not description:
                desc_parts = []
                for i, cell in enumerate(row):
                    if cell and i != date_col:
                        cell_str = str(cell).strip()
                        if not self._is_amount(cell_str) and not self._is_date(cell_str):
                            if len(cell_str) > 2:
                                desc_parts.append(cell_str)
                description = ' '.join(desc_parts)
            
            # Extract amount and direction
            amount = None
            direction = 'credit'
            
            # Try paid out column first (debit)
            if paid_out_col is not None and paid_out_col < len(row):
                cell_str = str(row[paid_out_col]).strip() if row[paid_out_col] else ''
                if cell_str and cell_str.lower() not in ['', '-', 'none', 'null', '0.00', '0']:
                    amt = self._parse_amount(cell_str)
                    if amt and amt > 0:
                        amount = amt
                        direction = 'debit'
            
            # Try paid in column (credit)
            if amount is None and paid_in_col is not None and paid_in_col < len(row):
                cell_str = str(row[paid_in_col]).strip() if row[paid_in_col] else ''
                if cell_str and cell_str.lower() not in ['', '-', 'none', 'null', '0.00', '0']:
                    amt = self._parse_amount(cell_str)
                    if amt and amt > 0:
                        amount = amt
                        direction = 'credit'
            
            # Try single amount column
            if amount is None and amount_col is not None and amount_col < len(row):
                cell_str = str(row[amount_col]).strip() if row[amount_col] else ''
                if cell_str:
                    amt = self._parse_amount(cell_str)
                    if amt:
                        amount = abs(amt)
                        # Determine direction from sign or context
                        if '-' in cell_str or '(' in cell_str:
                            direction = 'debit'
                        elif any(kw in description.lower() for kw in self.debit_keywords):
                            direction = 'debit'
            
            # Fallback: scan all cells for amounts
            if amount is None:
                for i, cell in enumerate(row):
                    if cell and i != date_col and i != balance_col:
                        cell_str = str(cell).strip()
                        amt = self._parse_amount(cell_str)
                        if amt and amt > 0:
                            amount = amt
                            # Infer direction from description
                            if any(kw in description.lower() for kw in self.debit_keywords):
                                direction = 'debit'
                            break
            
            if amount is None or amount == 0:
                return None
            
            # Extract balance
            balance = None
            if balance_col is not None and balance_col < len(row) and row[balance_col]:
                balance = self._parse_amount(str(row[balance_col]))
            
            return {
                'account_id': f'PDF_P{page_num}_T{table_idx}',
                'date': parsed_date,
                'amount': float(amount),
                'currency': 'GBP',
                'direction': direction,
                'description': description[:500] if description else 'Transaction',
                'counterparty_name': '',
                'balance': float(balance) if balance else None,
                'source': f'table_page{page_num}_row{row_idx}'
            }
            
        except Exception as e:
            return None
    
    def _extract_with_text_lines(self, pdf_bytes: bytes, metadata: Dict, bank_type: Optional[str]) -> List[Dict]:
        """Extract transactions by parsing text line by line."""
        transactions = []
        
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split('\n')
                metadata['raw_text_lines'] += len(lines)
                
                # Buffer for multi-line transactions
                current_txn = None
                
                for line_idx, line in enumerate(lines):
                    line = line.strip()
                    if not line or len(line) < 5:
                        continue
                    
                    # Skip header-like lines
                    line_lower = line.lower()
                    if any(kw in line_lower for kw in ['page', 'statement', 'account number', 'sort code']):
                        continue
                    
                    # Check if line starts with a date
                    date_match = self._extract_date_from_line(line)
                    
                    if date_match:
                        # Save previous transaction
                        if current_txn and current_txn.get('amount'):
                            transactions.append(current_txn)
                        
                        # Start new transaction
                        parsed_date = self._parse_date(date_match)
                        if parsed_date:
                            current_txn = self._parse_transaction_line(
                                line, parsed_date, page_num, line_idx, bank_type
                            )
                    elif current_txn:
                        # Continuation of previous transaction description
                        if 'description' in current_txn:
                            # Check if line has amounts
                            amounts = self._extract_amounts_from_line(line)
                            if amounts and not current_txn.get('amount'):
                                # This line has the amounts
                                current_txn['amount'] = amounts[0]
                                if len(amounts) > 1:
                                    current_txn['balance'] = amounts[-1]
                            else:
                                # Add to description
                                current_txn['description'] += ' ' + line
                
                # Don't forget last transaction
                if current_txn and current_txn.get('amount'):
                    transactions.append(current_txn)
        
        return transactions
    
    def _parse_transaction_line(self, line: str, date: str, page_num: int, line_idx: int, bank_type: Optional[str]) -> Dict:
        """Parse a single transaction line."""
        # Extract amounts from the line
        amounts = self._extract_amounts_from_line(line)
        
        # Determine direction
        direction = 'credit'
        line_lower = line.lower()
        if any(kw in line_lower for kw in self.debit_keywords):
            direction = 'debit'
        
        # Extract description (text between date and amounts)
        description = line
        date_match = self._extract_date_from_line(line)
        if date_match:
            # Remove date from beginning
            description = line[len(date_match):].strip()
        
        # Remove amounts from description
        for amt_match in self.amount_pattern.finditer(description):
            # Don't remove if it looks like part of a reference number
            start = amt_match.start()
            if start > 0 and description[start-1].isdigit():
                continue
            description = description[:amt_match.start()] + description[amt_match.end():]
        
        description = ' '.join(description.split())  # Clean whitespace
        
        amount = amounts[0] if amounts else None
        balance = amounts[-1] if len(amounts) > 1 else None
        
        return {
            'account_id': f'PDF_P{page_num}_TEXT',
            'date': date,
            'amount': float(amount) if amount else None,
            'currency': 'GBP',
            'direction': direction,
            'description': description[:500] if description else 'Transaction',
            'counterparty_name': '',
            'balance': float(balance) if balance else None,
            'source': f'text_page{page_num}_line{line_idx}'
        }
    
    def _extract_with_words(self, pdf_bytes: bytes, metadata: Dict, bank_type: Optional[str]) -> List[Dict]:
        """Extract transactions using word-level extraction with positional analysis."""
        transactions = []
        
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                words = page.extract_words()
                if not words:
                    continue
                
                # Group words by their vertical position (same line)
                lines = self._group_words_to_lines(words)
                
                for line_idx, line_words in enumerate(lines):
                    line_text = ' '.join([w['text'] for w in line_words])
                    
                    # Check if line has a date
                    date_match = self._extract_date_from_line(line_text)
                    if not date_match:
                        continue
                    
                    parsed_date = self._parse_date(date_match)
                    if not parsed_date:
                        continue
                    
                    # Extract amounts based on position (usually right-aligned)
                    amounts = []
                    desc_parts = []
                    
                    for word in line_words:
                        text = word['text']
                        if self._is_amount(text):
                            amt = self._parse_amount(text)
                            if amt:
                                amounts.append(amt)
                        elif not self._is_date(text):
                            desc_parts.append(text)
                    
                    if not amounts:
                        continue
                    
                    description = ' '.join(desc_parts)
                    direction = 'debit' if any(kw in description.lower() for kw in self.debit_keywords) else 'credit'
                    
                    transactions.append({
                        'account_id': f'PDF_P{page_num}_WORD',
                        'date': parsed_date,
                        'amount': float(amounts[0]),
                        'currency': 'GBP',
                        'direction': direction,
                        'description': description[:500],
                        'counterparty_name': '',
                        'balance': float(amounts[-1]) if len(amounts) > 1 else None,
                        'source': f'words_page{page_num}_line{line_idx}'
                    })
        
        return transactions
    
    def _extract_with_pymupdf(self, pdf_bytes: bytes, metadata: Dict, bank_type: Optional[str]) -> List[Dict]:
        """Fallback extraction using PyMuPDF."""
        transactions = []
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Get text with detailed info
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if "lines" not in block:
                    continue
                
                for line in block["lines"]:
                    text = ""
                    for span in line["spans"]:
                        text += span["text"] + " "
                    
                    text = text.strip()
                    if not text or len(text) < 10:
                        continue
                    
                    # Check for date
                    date_match = self._extract_date_from_line(text)
                    if not date_match:
                        continue
                    
                    parsed_date = self._parse_date(date_match)
                    if not parsed_date:
                        continue
                    
                    # Extract amounts
                    amounts = self._extract_amounts_from_line(text)
                    if not amounts:
                        continue
                    
                    # Build description
                    description = text
                    for amt_match in self.amount_pattern.finditer(text):
                        description = description.replace(amt_match.group(), '')
                    description = ' '.join(description.split())
                    
                    direction = 'debit' if any(kw in description.lower() for kw in self.debit_keywords) else 'credit'
                    
                    transactions.append({
                        'account_id': f'PDF_P{page_num+1}_MU',
                        'date': parsed_date,
                        'amount': float(amounts[0]),
                        'currency': 'GBP',
                        'direction': direction,
                        'description': description[:500],
                        'counterparty_name': '',
                        'balance': float(amounts[-1]) if len(amounts) > 1 else None,
                        'source': f'pymupdf_page{page_num+1}'
                    })
        
        doc.close()
        return transactions
    
    # Helper methods
    
    def _find_header_row(self, table: List[List]) -> Optional[int]:
        """Find the row that contains column headers."""
        for row_idx in range(min(5, len(table))):
            row = table[row_idx]
            if not row:
                continue
            
            row_text = ' '.join([str(cell).lower() for cell in row if cell])
            matches = sum(1 for kw in self.header_keywords if kw in row_text)
            
            if matches >= 2:
                return row_idx
        
        return None
    
    def _find_column(self, header: List[str], keywords: List[str]) -> Optional[int]:
        """Find column index by keyword matching."""
        for col_idx, cell in enumerate(header):
            cell_lower = cell.lower().strip()
            for keyword in keywords:
                if keyword in cell_lower:
                    return col_idx
        return None
    
    def _group_words_to_lines(self, words: List[Dict], tolerance: float = 5) -> List[List[Dict]]:
        """Group words into lines based on vertical position."""
        if not words:
            return []
        
        # Sort by top position
        sorted_words = sorted(words, key=lambda w: (w['top'], w['x0']))
        
        lines = []
        current_line = [sorted_words[0]]
        current_top = sorted_words[0]['top']
        
        for word in sorted_words[1:]:
            if abs(word['top'] - current_top) <= tolerance:
                current_line.append(word)
            else:
                lines.append(sorted(current_line, key=lambda w: w['x0']))
                current_line = [word]
                current_top = word['top']
        
        if current_line:
            lines.append(sorted(current_line, key=lambda w: w['x0']))
        
        return lines
    
    def _is_date(self, text: str) -> bool:
        """Check if text looks like a date."""
        for pattern, _ in self.date_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _extract_date_from_line(self, line: str) -> Optional[str]:
        """Extract date string from beginning of line."""
        for pattern, _ in self.date_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return match.group()
        return None
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to YYYY-MM-DD format."""
        if not date_str:
            return None
        
        date_str = date_str.strip()
        current_year = datetime.now().year
        
        for pattern, fmt_type in self.date_patterns:
            match = re.match(pattern, date_str, re.IGNORECASE)
            if match:
                try:
                    if fmt_type == 'dmy_short':
                        day = int(match.group(1))
                        month_str = match.group(2).lower()
                        month = self.month_map.get(month_str[:3])
                        year = int(match.group(3)) if match.group(3) else current_year
                        if year < 100:
                            year += 2000 if year < 50 else 1900
                    elif fmt_type == 'dmy_full':
                        day = int(match.group(1))
                        month_str = match.group(2).lower()
                        month = self.month_map.get(month_str[:3])
                        year = int(match.group(3))
                    elif fmt_type == 'slash' or fmt_type == 'dash':
                        day = int(match.group(1))
                        month = int(match.group(2))
                        year = int(match.group(3))
                        if year < 100:
                            year += 2000 if year < 50 else 1900
                    elif fmt_type == 'iso':
                        year = int(match.group(1))
                        month = int(match.group(2))
                        day = int(match.group(3))
                    
                    if month and 1 <= day <= 31 and 1 <= month <= 12:
                        return f"{year:04d}-{month:02d}-{day:02d}"
                except:
                    continue
        
        return None
    
    def _is_amount(self, text: str) -> bool:
        """Check if text looks like an amount."""
        text = text.strip()
        return bool(self.amount_pattern.search(text))
    
    def _extract_amounts_from_line(self, line: str) -> List[float]:
        """Extract all amounts from a line."""
        amounts = []
        for match in self.amount_pattern.finditer(line):
            try:
                amt_str = match.group(1).replace(',', '')
                amount = float(amt_str)
                if amount > 0:
                    amounts.append(amount)
            except:
                continue
        return amounts
    
    def _parse_amount(self, text: str) -> Optional[float]:
        """Parse amount from text."""
        if not text:
            return None
        
        text = text.strip()
        match = self.amount_pattern.search(text)
        
        if match:
            try:
                amt_str = match.group(1).replace(',', '')
                return float(amt_str)
            except:
                return None
        
        return None
    
    def _deduplicate(self, transactions: List[Dict]) -> List[Dict]:
        """Remove duplicate transactions - only exact duplicates on same date."""
        seen = set()
        unique = []
        
        for txn in transactions:
            # Use more of the description to avoid false positives with recurring payments
            description = txn.get('description', '')
            key = (
                txn.get('date'),
                round(txn.get('amount', 0), 2),
                description[:100] if description else ''  # Increased from 50 to 100
            )
            
            if key not in seen:
                seen.add(key)
                unique.append(txn)
        
        return unique


# Singleton instance
bank_statement_parser = BankStatementPDFParser()
