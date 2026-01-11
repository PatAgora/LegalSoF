"""
PDF Transaction Parser Service

Extracts transaction data from bank statement PDFs using multiple parsing strategies.
Supports various bank formats and uses AI/pattern matching for extraction.
"""

import re
import io
from typing import List, Dict, Any, Optional
from datetime import datetime
import pdfplumber
import fitz  # PyMuPDF
from decimal import Decimal

class PDFTransactionParser:
    """
    Advanced PDF parser for bank statements.
    
    Supports multiple formats:
    - Standard table-based statements
    - Text-based statements with transaction lines
    - Multi-page statements
    - Various date/amount formats
    """
    
    def __init__(self):
        self.date_patterns = [
            r'\d{2}/\d{2}/\d{4}',  # DD/MM/YYYY
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}-\d{2}-\d{4}',  # DD-MM-YYYY
            r'\d{2}\s+[A-Za-z]{3}\s+\d{4}',  # DD MMM YYYY
        ]
        
        self.amount_patterns = [
            r'£?[\d,]+\.\d{2}',  # £1,234.56 or 1,234.56
            r'[\d,]+\.\d{2}[CR]?',  # 1,234.56CR or 1,234.56
            r'\([\d,]+\.\d{2}\)',  # (1,234.56) for negative
        ]
        
        self.currency_symbols = {'£': 'GBP', '$': 'USD', '€': 'EUR'}
    
    def parse_pdf(self, pdf_file: bytes, customer_id: str) -> List[Dict[str, Any]]:
        """
        Parse PDF bank statement and extract transactions.
        
        Args:
            pdf_file: PDF file bytes
            customer_id: Customer identifier
            
        Returns:
            List of transaction dictionaries
        """
        try:
            # Try pdfplumber first (best for tables)
            transactions = self._parse_with_pdfplumber(pdf_file, customer_id)
            
            if not transactions:
                # Fallback to PyPDF2 for text extraction
                transactions = self._parse_with_pypdf2(pdf_file, customer_id)
            
            return transactions
            
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {str(e)}")
    
    def _parse_with_pdfplumber(self, pdf_file: bytes, customer_id: str) -> List[Dict[str, Any]]:
        """Parse PDF using pdfplumber (best for structured tables)."""
        transactions = []
        
        with pdfplumber.open(io.BytesIO(pdf_file)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract tables
                tables = page.extract_tables()
                
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    
                    # Try to identify header row
                    header_row = table[0]
                    data_rows = table[1:]
                    
                    # Detect column indices
                    date_col = self._find_column(header_row, ['date', 'transaction date', 'posted'])
                    desc_col = self._find_column(header_row, ['description', 'details', 'narrative', 'particulars'])
                    amount_col = self._find_column(header_row, ['amount', 'value', 'debit', 'credit'])
                    
                    # Process rows
                    for row_idx, row in enumerate(data_rows):
                        if not row or len(row) < 3:
                            continue
                        
                        txn = self._extract_transaction_from_row(
                            row, date_col, desc_col, amount_col, 
                            customer_id, page_num, row_idx
                        )
                        
                        if txn:
                            transactions.append(txn)
                
                # If no tables found, try text extraction
                if not transactions:
                    text = page.extract_text()
                    if text:
                        page_transactions = self._parse_text_transactions(text, customer_id, page_num)
                        transactions.extend(page_transactions)
        
        return transactions
    
    def _parse_with_pypdf2(self, pdf_file: bytes, customer_id: str) -> List[Dict[str, Any]]:
        """Fallback parser using PyMuPDF/fitz for text extraction."""
        transactions = []
        
        doc = fitz.open(stream=pdf_file, filetype="pdf")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            if text:
                page_transactions = self._parse_text_transactions(text, customer_id, page_num + 1)
                transactions.extend(page_transactions)
        
        doc.close()
        return transactions
    
    def _parse_text_transactions(self, text: str, customer_id: str, page_num: int) -> List[Dict[str, Any]]:
        """
        Parse transactions from plain text using pattern matching.
        
        Looks for patterns like:
        - 15/01/2024  Payment to Supplier  £1,234.56
        - 2024-01-15  Transfer from Client  $5,000.00
        """
        transactions = []
        lines = text.split('\n')
        
        for line_idx, line in enumerate(lines):
            # Try to extract date
            date_match = None
            for pattern in self.date_patterns:
                match = re.search(pattern, line)
                if match:
                    date_match = match
                    break
            
            if not date_match:
                continue
            
            # Try to extract amount
            amount_match = None
            for pattern in self.amount_patterns:
                match = re.search(pattern, line)
                if match:
                    amount_match = match
                    break
            
            if not amount_match:
                continue
            
            # Extract transaction details
            date_str = date_match.group()
            amount_str = amount_match.group()
            
            # Description is text between date and amount
            desc_start = date_match.end()
            desc_end = amount_match.start()
            description = line[desc_start:desc_end].strip()
            
            # Parse date
            txn_date = self._parse_date(date_str)
            if not txn_date:
                continue
            
            # Parse amount and direction
            amount, direction = self._parse_amount(amount_str)
            if amount is None:
                continue
            
            # Detect currency
            currency = self._detect_currency(amount_str, line)
            
            # Generate transaction ID
            txn_id = f"PDF_P{page_num}_L{line_idx + 1}"
            
            transaction = {
                'txn_id': txn_id,
                'txn_date': txn_date.strftime('%Y-%m-%d'),
                'customer_id': customer_id,
                'direction': direction,
                'amount': float(amount),
                'currency': currency,
                'country_iso2': 'GB',  # Default, can be enhanced with location detection
                'narrative': description[:500],  # Limit length
                'channel': 'unknown',
                'source': 'pdf_statement',
                'page_number': page_num,
                'line_number': line_idx + 1,
            }
            
            transactions.append(transaction)
        
        return transactions
    
    def _extract_transaction_from_row(
        self, row: List[str], date_col: int, desc_col: int, 
        amount_col: int, customer_id: str, page_num: int, row_idx: int
    ) -> Optional[Dict[str, Any]]:
        """Extract a single transaction from a table row."""
        try:
            if date_col == -1 or desc_col == -1 or amount_col == -1:
                return None
            
            date_str = row[date_col] if date_col < len(row) else None
            description = row[desc_col] if desc_col < len(row) else ""
            amount_str = row[amount_col] if amount_col < len(row) else None
            
            if not date_str or not amount_str:
                return None
            
            # Parse date
            txn_date = self._parse_date(date_str)
            if not txn_date:
                return None
            
            # Parse amount
            amount, direction = self._parse_amount(amount_str)
            if amount is None:
                return None
            
            # Detect currency
            currency = self._detect_currency(amount_str, description)
            
            # Generate ID
            txn_id = f"PDF_P{page_num}_R{row_idx + 1}"
            
            return {
                'txn_id': txn_id,
                'txn_date': txn_date.strftime('%Y-%m-%d'),
                'customer_id': customer_id,
                'direction': direction,
                'amount': float(amount),
                'currency': currency,
                'country_iso2': 'GB',
                'narrative': str(description)[:500],
                'channel': 'unknown',
                'source': 'pdf_statement',
                'page_number': page_num,
                'row_number': row_idx + 1,
            }
            
        except Exception as e:
            return None
    
    def _find_column(self, header_row: List[str], keywords: List[str]) -> int:
        """Find column index by matching keywords."""
        if not header_row:
            return -1
        
        for col_idx, cell in enumerate(header_row):
            if not cell:
                continue
            
            cell_lower = str(cell).lower().strip()
            
            for keyword in keywords:
                if keyword.lower() in cell_lower:
                    return col_idx
        
        return -1
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string in various formats."""
        if not date_str:
            return None
        
        date_formats = [
            '%d/%m/%Y',
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%d %b %Y',
            '%d %B %Y',
            '%m/%d/%Y',
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        return None
    
    def _parse_amount(self, amount_str: str) -> tuple[Optional[Decimal], str]:
        """
        Parse amount and determine direction (in/out).
        
        Returns:
            (amount, direction) where direction is 'in' or 'out'
        """
        if not amount_str:
            return None, 'out'
        
        # Clean amount string
        amount_str = amount_str.strip()
        
        # Check for negative indicators
        is_negative = False
        if amount_str.startswith('(') and amount_str.endswith(')'):
            is_negative = True
            amount_str = amount_str[1:-1]
        elif amount_str.endswith('DR') or amount_str.endswith('D'):
            is_negative = True
            amount_str = amount_str[:-2].strip()
        elif amount_str.endswith('-'):
            is_negative = True
            amount_str = amount_str[:-1].strip()
        
        # Check for positive indicators
        if amount_str.endswith('CR') or amount_str.endswith('C'):
            is_negative = False
            amount_str = amount_str[:-2].strip()
        
        # Remove currency symbols and commas
        amount_str = re.sub(r'[£$€,]', '', amount_str)
        
        try:
            amount = Decimal(amount_str)
            
            # Determine direction
            if is_negative:
                direction = 'out'
            else:
                direction = 'in'
            
            return abs(amount), direction
            
        except:
            return None, 'out'
    
    def _detect_currency(self, amount_str: str, context: str = "") -> str:
        """Detect currency from amount string or context."""
        # Check amount string for currency symbol
        for symbol, code in self.currency_symbols.items():
            if symbol in amount_str:
                return code
        
        # Check context for currency keywords
        context_lower = context.lower()
        if 'usd' in context_lower or 'dollar' in context_lower:
            return 'USD'
        elif 'eur' in context_lower or 'euro' in context_lower:
            return 'EUR'
        elif 'gbp' in context_lower or 'pound' in context_lower or 'sterling' in context_lower:
            return 'GBP'
        
        # Default to GBP (can be made configurable)
        return 'GBP'
    
    def extract_metadata(self, pdf_file: bytes) -> Dict[str, Any]:
        """
        Extract metadata from PDF statement.
        
        Returns:
            Dictionary with account info, statement period, etc.
        """
        metadata = {
            'account_number': None,
            'account_name': None,
            'statement_period_start': None,
            'statement_period_end': None,
            'opening_balance': None,
            'closing_balance': None,
            'bank_name': None,
        }
        
        try:
            with pdfplumber.open(io.BytesIO(pdf_file)) as pdf:
                # Extract text from first page (usually has metadata)
                if pdf.pages:
                    first_page_text = pdf.pages[0].extract_text()
                    
                    # Try to extract account number
                    acc_patterns = [
                        r'Account\s*Number:?\s*(\d{8,})',
                        r'A/C\s*No\.?:?\s*(\d{8,})',
                        r'Account:?\s*(\d{8,})',
                    ]
                    for pattern in acc_patterns:
                        match = re.search(pattern, first_page_text, re.IGNORECASE)
                        if match:
                            metadata['account_number'] = match.group(1)
                            break
                    
                    # Try to extract statement period
                    period_patterns = [
                        r'Statement\s+Period:?\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})',
                        r'From:?\s*(\d{2}/\d{2}/\d{4})\s*To:?\s*(\d{2}/\d{2}/\d{4})',
                    ]
                    for pattern in period_patterns:
                        match = re.search(pattern, first_page_text, re.IGNORECASE)
                        if match:
                            metadata['statement_period_start'] = match.group(1)
                            metadata['statement_period_end'] = match.group(2)
                            break
                    
                    # Try to extract bank name
                    bank_keywords = ['Bank', 'Banking', 'HSBC', 'Barclays', 'Lloyds', 'NatWest', 'Santander']
                    for keyword in bank_keywords:
                        if keyword in first_page_text:
                            metadata['bank_name'] = keyword
                            break
        
        except Exception as e:
            pass
        
        return metadata
