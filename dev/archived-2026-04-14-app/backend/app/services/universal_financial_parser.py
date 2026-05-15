"""
Universal Financial Document Parser

Handles ANY bank statement or financial document format:
- PDFs (native text and scanned)
- Images/Screenshots (PNG, JPG, etc.)
- CSV files (any column format)
- Excel files

Supports ALL banks worldwide:
- UK: NatWest, HSBC, Barclays, Lloyds, Santander, Nationwide, Monzo, Starling, Revolut
- US: Chase, Bank of America, Wells Fargo, Citi
- International: Any bank following standard formats
- Credit Cards: All major providers
- Digital Banks: Monzo, Starling, Revolut, N26, Wise, etc.

Key Features:
1. Intelligent format detection
2. OCR for images and scanned documents
3. Flexible pattern matching for any date/amount format
4. AI-powered transaction extraction
5. Multi-currency support
6. Automatic deduplication
"""

import re
import io
import csv
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

# PDF processing
import pdfplumber
import fitz  # PyMuPDF

# Image processing and OCR
from PIL import Image
import pytesseract

# Try to import pdf2image for scanned PDFs
try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False


class UniversalFinancialParser:
    """
    Universal parser for any financial document format.
    
    Automatically detects document type and extracts transactions
    using the most appropriate method.
    """
    
    def __init__(self):
        # Comprehensive date patterns (international formats)
        self.date_patterns = [
            # UK formats
            (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:uary|ruary|ch|il|e|y|ust|tember|ober|ember)?\s*(\d{2,4})?', 'uk_text'),
            (r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})', 'dmy_or_mdy'),
            # ISO format
            (r'(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})', 'iso'),
            # US format with month name
            (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:uary|ruary|ch|il|e|y|ust|tember|ober|ember)?\s+(\d{1,2}),?\s*(\d{2,4})?', 'us_text'),
            # Compact formats
            (r'(\d{8})', 'compact'),  # YYYYMMDD or DDMMYYYY
        ]
        
        # Amount patterns (multi-currency)
        self.amount_patterns = [
            # With currency symbols
            r'([£$€¥₹฿R])\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*([£$€¥₹฿])',
            # With currency codes
            r'(GBP|USD|EUR|JPY|INR|AUD|CAD|CHF|CNY)\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*(GBP|USD|EUR|JPY|INR|AUD|CAD|CHF|CNY)',
            # Plain amounts
            r'([\d,]+\.\d{2})',
            r'([\d,]+\.\d{1,2})',
        ]
        
        # Currency mappings
        self.currency_symbols = {
            '£': 'GBP', '$': 'USD', '€': 'EUR', '¥': 'JPY', 
            '₹': 'INR', '฿': 'THB', 'R': 'ZAR'
        }
        
        # Month mappings
        self.month_map = {
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
            'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
            'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
            'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9,
            'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
            'dec': 12, 'december': 12
        }
        
        # Bank identifiers (expanded)
        self.bank_identifiers = {
            # UK Traditional
            'natwest': ['natwest', 'national westminster'],
            'hsbc': ['hsbc'],
            'barclays': ['barclays'],
            'lloyds': ['lloyds', 'lloyds bank'],
            'santander': ['santander'],
            'nationwide': ['nationwide'],
            'halifax': ['halifax'],
            'rbs': ['royal bank of scotland', 'rbs'],
            'tsb': ['tsb bank', 'tsb'],
            # UK Digital
            'monzo': ['monzo'],
            'starling': ['starling', 'starling bank'],
            'revolut': ['revolut'],
            'chase_uk': ['chase uk', 'jpmorgan chase uk'],
            # US Banks
            'chase': ['chase', 'jpmorgan chase'],
            'boa': ['bank of america', 'bofa'],
            'wells_fargo': ['wells fargo'],
            'citi': ['citibank', 'citi'],
            'capital_one': ['capital one'],
            # International
            'wise': ['wise', 'transferwise'],
            'n26': ['n26'],
            'ing': ['ing bank', 'ing direct'],
            # Credit Cards
            'amex': ['american express', 'amex'],
            'visa': ['visa'],
            'mastercard': ['mastercard'],
            'discover': ['discover'],
        }
        
        # Bank-specific parsing configurations
        # Each config specifies: column order, date format, amount format, special rules
        self.bank_configs = {
            'natwest': {
                'date_format': 'dmy',  # DD/MM/YYYY
                'columns': ['date', 'type', 'description', 'paid_out', 'paid_in', 'balance'],
                'has_transaction_type': True,
                'multiline_descriptions': True,
                'balance_column': 'last',
                'debit_column': 'paid_out',
                'credit_column': 'paid_in',
                'header_keywords': ['date', 'type', 'description', 'paid out', 'paid in', 'balance'],
                'skip_rows_containing': ['balance brought forward', 'balance carried forward', 'statement', 'page'],
            },
            'hsbc': {
                'date_format': 'dmy',
                'columns': ['date', 'description', 'paid_out', 'paid_in', 'balance'],
                'has_transaction_type': False,
                'multiline_descriptions': True,
                'balance_column': 'last',
                'debit_column': 'paid_out',
                'credit_column': 'paid_in',
                'header_keywords': ['date', 'payment type', 'details', 'paid out', 'paid in', 'balance'],
                'skip_rows_containing': ['brought forward', 'carried forward', 'opening balance'],
            },
            'barclays': {
                'date_format': 'dmy',
                'columns': ['date', 'description', 'amount', 'balance'],
                'has_transaction_type': False,
                'multiline_descriptions': False,
                'balance_column': 'last',
                'amount_column': 'amount',  # Single column, negative for debits
                'header_keywords': ['date', 'description', 'amount', 'balance'],
                'skip_rows_containing': ['opening balance', 'closing balance'],
            },
            'lloyds': {
                'date_format': 'dmy',
                'columns': ['date', 'description', 'type', 'money_in', 'money_out', 'balance'],
                'has_transaction_type': True,
                'multiline_descriptions': True,
                'balance_column': 'last',
                'debit_column': 'money_out',
                'credit_column': 'money_in',
                'header_keywords': ['date', 'description', 'type', 'in', 'out', 'balance'],
                'skip_rows_containing': ['balance brought', 'balance carried'],
            },
            'santander': {
                'date_format': 'dmy',
                'columns': ['date', 'description', 'withdrawals', 'deposits', 'balance'],
                'has_transaction_type': False,
                'multiline_descriptions': False,
                'balance_column': 'last',
                'debit_column': 'withdrawals',
                'credit_column': 'deposits',
                'header_keywords': ['date', 'description', 'withdrawal', 'deposit', 'balance'],
                'skip_rows_containing': ['statement period', 'account number', 'sort code'],
                'single_cell_likely': True,  # Often produces merged cells
            },
            'nationwide': {
                'date_format': 'dmy',
                'columns': ['date', 'description', 'payments', 'receipts', 'balance'],
                'has_transaction_type': False,
                'multiline_descriptions': False,
                'balance_column': 'last',
                'debit_column': 'payments',
                'credit_column': 'receipts',
                'header_keywords': ['date', 'details', 'payments', 'receipts', 'balance'],
                'skip_rows_containing': ['opening balance', 'closing balance'],
            },
            'monzo': {
                'date_format': 'iso',  # YYYY-MM-DD
                'columns': ['date', 'time', 'type', 'name', 'emoji', 'category', 'amount', 'currency', 'notes', 'address', 'receipt', 'description', 'category_split'],
                'has_transaction_type': True,
                'multiline_descriptions': False,
                'amount_column': 'amount',  # Negative for debits
                'csv_preferred': True,  # Monzo exports are usually CSV
                'header_keywords': ['date', 'type', 'name', 'amount'],
            },
            'starling': {
                'date_format': 'dmy',
                'columns': ['date', 'counter_party', 'reference', 'type', 'amount', 'balance'],
                'has_transaction_type': True,
                'multiline_descriptions': False,
                'amount_column': 'amount',
                'balance_column': 'balance',
                'csv_preferred': True,
                'header_keywords': ['date', 'counter party', 'type', 'amount', 'balance'],
            },
            'revolut': {
                'date_format': 'iso',
                'columns': ['type', 'product', 'started_date', 'completed_date', 'description', 'amount', 'fee', 'currency', 'state', 'balance'],
                'has_transaction_type': True,
                'multiline_descriptions': False,
                'amount_column': 'amount',
                'balance_column': 'balance',
                'csv_preferred': True,
                'multi_currency': True,
                'header_keywords': ['type', 'started date', 'completed date', 'amount', 'balance'],
            },
            'wise': {
                'date_format': 'iso',
                'columns': ['id', 'date', 'amount', 'currency', 'description', 'payment_reference', 'running_balance', 'exchange_from', 'exchange_to', 'exchange_rate'],
                'has_transaction_type': False,
                'multiline_descriptions': False,
                'amount_column': 'amount',
                'balance_column': 'running_balance',
                'csv_preferred': True,
                'multi_currency': True,
                'header_keywords': ['date', 'amount', 'currency', 'description', 'running balance'],
            },
            # US Banks
            'chase': {
                'date_format': 'mdy',  # MM/DD/YYYY
                'columns': ['date', 'description', 'amount', 'balance'],
                'has_transaction_type': False,
                'amount_column': 'amount',
                'balance_column': 'balance',
                'header_keywords': ['date', 'description', 'amount', 'balance'],
            },
            'boa': {
                'date_format': 'mdy',
                'columns': ['date', 'description', 'amount', 'running_balance'],
                'has_transaction_type': False,
                'amount_column': 'amount',
                'balance_column': 'running_balance',
                'header_keywords': ['date', 'description', 'amount', 'balance'],
            },
            # Default fallback
            'default': {
                'date_format': 'dmy',
                'columns': ['date', 'description', 'debit', 'credit', 'balance'],
                'has_transaction_type': False,
                'multiline_descriptions': False,
                'balance_column': 'last',
                'debit_column': 'debit',
                'credit_column': 'credit',
                'header_keywords': ['date', 'description', 'debit', 'credit', 'balance'],
            }
        }
        
        # Transaction type keywords (expanded for all banks)
        # IMPORTANT: Include directional variants (to/from) for accurate detection
        self.debit_keywords = [
            # Generic
            'debit', 'dr', 'withdrawal', 'payment', 'purchase', 'bought',
            'paid', 'sent', 'transfer out', 'outgoing', 'expense',
            # UK specific - with directional indicators
            'direct debit', 'dd', 'standing order to', 'so to', 
            'faster payment to', 'fp to', 'card payment', 'contactless', 'chip and pin',
            'chaps to', 'bacs to', 'payment to', 'transfer to',
            # Digital banks
            'pot transfer', 'to pot', 'declined',
            # Credit cards  
            'charge', 'transaction', 'spend',
            # US specific
            'check', 'cheque', 'ach debit', 'wire out',
            # Money out indicators
            'money out', 'paid out',
        ]
        
        self.credit_keywords = [
            # Generic
            'credit', 'cr', 'deposit', 'received', 'income', 'refund',
            'transfer in', 'incoming', 'receipt',
            # UK specific - with directional indicators
            'faster payment from', 'fp from', 'standing order from', 'so from',
            'bacs from', 'chaps from', 'payment from', 'transfer from',
            'salary', 'wages', 'pension', 'interest',
            # Digital banks
            'from pot', 'cashback', 'reward', 'interest earned',
            # US specific
            'ach credit', 'wire in', 'direct deposit',
            # Money in indicators
            'money in', 'paid in',
        ]
        
        # Column name variations for CSV detection
        self.date_column_names = [
            'date', 'transaction date', 'trans date', 'posting date', 'posted',
            'value date', 'transaction_date', 'txn_date', 'created', 'time',
            'completed date', 'settled date'
        ]
        
        self.amount_column_names = [
            'amount', 'value', 'sum', 'total', 'money', 'transaction amount',
            'debit', 'credit', 'paid out', 'paid in', 'money out', 'money in',
            'withdrawal', 'deposit', 'in', 'out', 'dr', 'cr', 'balance change'
        ]
        
        self.description_column_names = [
            'description', 'details', 'narrative', 'particulars', 'reference',
            'memo', 'notes', 'transaction', 'type', 'merchant', 'payee', 'name',
            'transaction description', 'payment details', 'transaction type'
        ]
    
    def parse(self, file_content: bytes, filename: str = '', content_type: str = '') -> Dict[str, Any]:
        """
        Universal entry point - automatically detects format and parses.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename (helps with format detection)
            content_type: MIME type if known
            
        Returns:
            {
                'success': bool,
                'transactions': List[Dict],
                'metadata': Dict,
                'error': Optional[str]
            }
        """
        try:
            # Detect file type
            file_type = self._detect_file_type(file_content, filename, content_type)
            print(f"📁 Detected file type: {file_type}")
            
            # Route to appropriate parser
            if file_type == 'pdf':
                return self._parse_pdf(file_content)
            elif file_type == 'image':
                return self._parse_image(file_content)
            elif file_type == 'csv':
                return self._parse_csv(file_content)
            elif file_type == 'excel':
                return self._parse_excel(file_content)
            else:
                # Try as text/CSV first, then as image
                result = self._parse_csv(file_content)
                if not result['success'] or not result['transactions']:
                    result = self._parse_image(file_content)
                return result
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'transactions': [],
                'metadata': {'error_type': type(e).__name__},
                'error': str(e)
            }
    
    def _detect_file_type(self, content: bytes, filename: str, content_type: str) -> str:
        """Detect file type from content, filename, or MIME type."""
        filename_lower = filename.lower()
        
        # Check by extension
        if filename_lower.endswith('.pdf'):
            return 'pdf'
        elif filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp')):
            return 'image'
        elif filename_lower.endswith('.csv'):
            return 'csv'
        elif filename_lower.endswith(('.xlsx', '.xls')):
            return 'excel'
        
        # Check by MIME type
        if content_type:
            if 'pdf' in content_type:
                return 'pdf'
            elif 'image' in content_type:
                return 'image'
            elif 'csv' in content_type or 'text' in content_type:
                return 'csv'
            elif 'spreadsheet' in content_type or 'excel' in content_type:
                return 'excel'
        
        # Check by magic bytes
        if content[:4] == b'%PDF':
            return 'pdf'
        elif content[:8] == b'\x89PNG\r\n\x1a\n':
            return 'image'
        elif content[:2] == b'\xff\xd8':  # JPEG
            return 'image'
        elif content[:4] == b'PK\x03\x04':  # ZIP (could be XLSX)
            return 'excel'
        
        # Try to decode as text (CSV)
        try:
            text = content.decode('utf-8')
            if ',' in text or '\t' in text:
                return 'csv'
        except:
            pass
        
        return 'unknown'
    
    def _parse_pdf(self, content: bytes) -> Dict[str, Any]:
        """Parse PDF document (native text or scanned)."""
        transactions = []
        metadata = {
            'source': 'pdf',
            'pages': 0,
            'extraction_method': None,
            'bank': None,
            'bank_config': None,
            'ocr_used': False,
            'account_info': {},
            'validation': {
                'balance_checks_passed': 0,
                'balance_checks_failed': 0,
                'balance_validated': False
            }
        }
        
        # Detect bank from PDF
        bank = self._detect_bank_from_pdf(content)
        metadata['bank'] = bank
        
        # Extract account information from PDF header
        account_info = self._extract_account_info(content)
        metadata['account_info'] = account_info
        if account_info:
            print(f"   📋 Account: {account_info.get('account_number', 'Unknown')} ({account_info.get('account_type', 'Unknown')}) at {account_info.get('bank_name', bank or 'Unknown')}")
        
        # Get bank-specific configuration
        bank_config = self.bank_configs.get(bank, self.bank_configs['default'])
        metadata['bank_config'] = bank
        print(f"🏦 Detected bank: {bank or 'Unknown'} (using {'specific' if bank in self.bank_configs else 'default'} config)")
        
        # Strategy 1: Native text extraction with tables (using bank config)
        print("\n📊 Trying native PDF extraction...")
        native_txns = self._extract_pdf_native(content, metadata, bank_config)
        
        if native_txns and len(native_txns) >= 3:
            print(f"   ✅ Native extraction: {len(native_txns)} transactions")
            transactions = native_txns
            metadata['extraction_method'] = 'native'
        else:
            print(f"   ⚠️ Native extraction found only {len(native_txns) if native_txns else 0} transactions")
        
        # Strategy 2: Bank-specific text parsing if native failed
        if len(transactions) < 5:
            print("\n📝 Trying bank-specific text parsing...")
            text_txns = self._extract_pdf_text_with_bank_config(content, metadata, bank_config)
            if text_txns and len(text_txns) > len(transactions):
                print(f"   ✅ Text extraction: {len(text_txns)} transactions")
                transactions = text_txns
                metadata['extraction_method'] = 'text_bank_specific'
        
        # Strategy 3: OCR if native extraction failed or got few results
        if len(transactions) < 5 and PDF2IMAGE_AVAILABLE:
            print("\n🔍 Trying OCR extraction...")
            ocr_txns = self._extract_pdf_ocr_enhanced(content, metadata, bank_config)
            
            if ocr_txns and len(ocr_txns) > len(transactions):
                print(f"   ✅ OCR extraction: {len(ocr_txns)} transactions")
                transactions = ocr_txns
                metadata['extraction_method'] = 'ocr'
                metadata['ocr_used'] = True
        
        # Apply correct account_id to all transactions
        if account_info and account_info.get('account_number'):
            for txn in transactions:
                txn['account_id'] = account_info['account_number']
                txn['account_type'] = account_info.get('account_type', 'Unknown')
                txn['bank_name'] = account_info.get('bank_name', bank or 'Unknown')
                txn['sort_code'] = account_info.get('sort_code', '')
        
        # Deduplicate
        transactions = self._deduplicate(transactions)
        
        # Validate balances if we have balance data
        if transactions:
            transactions, validation_result = self._validate_balances(transactions)
            metadata['validation'] = validation_result
            if validation_result['balance_validated']:
                print(f"   ✅ Balance validation: {validation_result['balance_checks_passed']} passed, {validation_result['balance_checks_failed']} failed")
        
        return {
            'success': len(transactions) > 0,
            'transactions': transactions,
            'metadata': metadata,
            'error': None if transactions else 'No transactions could be extracted from PDF'
        }
    
    def _extract_account_info(self, content: bytes) -> Dict[str, Any]:
        """Extract account information from PDF header (account number, sort code, type, bank)."""
        account_info = {}
        
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                if not pdf.pages:
                    return account_info
                
                # Get text from first page
                first_page = pdf.pages[0]
                full_text = first_page.extract_text() or ''
                
                # Split into lines and take header portion (before transaction data starts)
                lines = full_text.split('\n')
                header_lines = []
                for line in lines:
                    # Stop when we hit actual transaction data
                    # Transaction lines START with a date (DD/MM/YYYY at beginning of line)
                    # Not "Statement Period: DD/MM/YYYY" which is part of header
                    stripped = line.strip()
                    if re.match(r'^\d{2}/\d{2}/\d{4}\s', stripped):
                        break
                    header_lines.append(line)
                
                header_text = '\n'.join(header_lines)
                header_lower = header_text.lower()
                
                # Extract account number from header
                account_patterns = [
                    r'Account\s*No[:\.]?\s*(\*{4}\d{4})',
                    r'Account\s*Number[:\.]?\s*(\*{4}\d{4})',
                    r'A/C\s*No[:\.]?\s*(\*{4}\d{4})',
                    r'Account\s*No[:\.]?\s*(\d{4,8})',
                ]
                for pattern in account_patterns:
                    match = re.search(pattern, header_text, re.IGNORECASE)
                    if match:
                        acc_num = match.group(1)
                        # Normalize to ****XXXX format
                        if not acc_num.startswith('*'):
                            acc_num = '****' + acc_num[-4:]
                        account_info['account_number'] = acc_num
                        break
                
                # Extract sort code from header
                sort_code_patterns = [
                    r'Sort\s*Code[:\.]?\s*(\d{2}[-\s]?\d{2}[-\s]?\d{2})',
                    r'Sort[:\.]?\s*(\d{2}[-\s]?\d{2}[-\s]?\d{2})',
                ]
                for pattern in sort_code_patterns:
                    match = re.search(pattern, header_text, re.IGNORECASE)
                    if match:
                        account_info['sort_code'] = match.group(1).replace(' ', '-')
                        break
                
                # Detect bank name FIRST from header (prioritize first occurrence)
                bank_names = {
                    'santander': 'Santander',
                    'hsbc': 'HSBC',
                    'natwest': 'NatWest',
                    'barclays': 'Barclays',
                    'lloyds': 'Lloyds',
                    'nationwide': 'Nationwide',
                    'monzo': 'Monzo',
                    'starling': 'Starling',
                    'revolut': 'Revolut',
                    'chase': 'Chase',
                }
                first_bank_pos = len(header_lower) + 1
                detected_bank = None
                for key, name in bank_names.items():
                    pos = header_lower.find(key)
                    if pos != -1 and pos < first_bank_pos:
                        first_bank_pos = pos
                        detected_bank = name
                if detected_bank:
                    account_info['bank_name'] = detected_bank
                
                # Detect account type from header only
                account_type = 'Current Account'  # Default
                if 'savings' in header_lower or 'saver' in header_lower or 'isa' in header_lower:
                    account_type = 'Savings Account'
                elif 'current' in header_lower or 'checking' in header_lower:
                    account_type = 'Current Account'
                elif 'business' in header_lower:
                    account_type = 'Business Account'
                elif 'joint' in header_lower:
                    account_type = 'Joint Account'
                account_info['account_type'] = account_type
                
        except Exception as e:
            print(f"   ⚠️ Account info extraction error: {e}")
        
        return account_info
    
    def _extract_pdf_native(self, content: bytes, metadata: Dict, bank_config: Dict) -> List[Dict]:
        """Extract transactions from native PDF text using bank-specific rules."""
        transactions = []
        
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            metadata['pages'] = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages, 1):
                page_transactions = []
                
                # Try table extraction first
                tables = page.extract_tables()
                
                print(f"   📄 Page {page_num}: Found {len(tables) if tables else 0} tables")
                
                for table_idx, table in enumerate(tables or []):
                    if table and len(table) >= 2:
                        # Debug: show table structure
                        if table_idx == 0 and len(table) > 0:
                            print(f"      Table {table_idx}: {len(table)} rows, first row cols: {len(table[0]) if table[0] else 0}")
                        
                        table_txns = self._parse_table_with_bank_config(table, page_num, bank_config)
                        page_transactions.extend(table_txns)
                
                # If table parsing returned nothing (e.g., single-cell with withdrawals/deposits), 
                # try position-based extraction
                if not page_transactions:
                    print(f"   📝 Trying position-based extraction for page {page_num}...")
                    position_txns = self._extract_with_column_positions(page, page_num, bank_config)
                    if position_txns:
                        print(f"      ✅ Position-based: {len(position_txns)} transactions")
                        page_transactions.extend(position_txns)
                    else:
                        # Fallback to text extraction
                        text = page.extract_text()
                        if text:
                            text_txns = self._parse_text_with_bank_config(text, page_num, bank_config)
                            page_transactions.extend(text_txns)
                
                transactions.extend(page_transactions)
                print(f"      Page {page_num} total: {len(page_transactions)} transactions")
        
        return transactions
    
    def _extract_with_column_positions(self, page, page_num: int, bank_config: Dict) -> List[Dict]:
        """Extract transactions using word positions to determine columns."""
        transactions = []
        
        try:
            words = page.extract_words()
            if not words:
                return []
            
            # Find header row to determine column positions
            # Look for "Withdrawals" and "Deposits" or similar
            withdrawal_x = None
            deposit_x = None
            balance_x = None
            
            for word in words:
                text = word['text'].lower()
                if 'withdrawal' in text:
                    withdrawal_x = word['x0']
                    print(f"      Found 'Withdrawals' column at x={withdrawal_x:.0f}")
                elif 'deposit' in text:
                    deposit_x = word['x0']
                    print(f"      Found 'Deposits' column at x={deposit_x:.0f}")
                elif text == 'balance':
                    balance_x = word['x0']
                    print(f"      Found 'Balance' column at x={balance_x:.0f}")
            
            if not (withdrawal_x or deposit_x):
                # Try alternative column names
                for word in words:
                    text = word['text'].lower()
                    if text in ['out', 'paid', 'debit', 'dr']:
                        withdrawal_x = word['x0']
                    elif text in ['in', 'credit', 'cr']:
                        deposit_x = word['x0']
            
            if not (withdrawal_x or deposit_x):
                return []  # Can't determine columns
            
            # Group words by line (y-position)
            lines = {}
            for word in words:
                y_key = round(word['top'], 0)  # Round to group nearby words
                if y_key not in lines:
                    lines[y_key] = []
                lines[y_key].append(word)
            
            # Process each line
            for y_pos in sorted(lines.keys()):
                line_words = sorted(lines[y_pos], key=lambda w: w['x0'])
                
                # Check if line starts with a date
                if not line_words:
                    continue
                
                first_text = line_words[0]['text']
                date_match = re.match(r'^(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})$', first_text)
                if not date_match:
                    continue
                
                parsed_date = self._parse_date_universal(first_text)
                if not parsed_date:
                    continue
                
                # Find amounts and their positions
                amounts_with_pos = []
                description_parts = []
                
                for word in line_words[1:]:  # Skip date
                    text = word['text'].replace('£', '').replace(',', '')
                    x_pos = word['x0']
                    
                    # Check if it's an amount
                    try:
                        if '.' in text and text.replace('.', '').isdigit():
                            amount = float(text)
                            amounts_with_pos.append((amount, x_pos))
                        else:
                            description_parts.append(word['text'])
                    except:
                        description_parts.append(word['text'])
                
                if not amounts_with_pos:
                    continue
                
                # Determine direction based on amount position
                description = ' '.join(description_parts)
                amount = amounts_with_pos[0][0]
                amount_x = amounts_with_pos[0][1]
                balance = amounts_with_pos[-1][0] if len(amounts_with_pos) > 1 else None
                
                # Determine direction: if amount is closer to withdrawal_x, it's debit
                direction = 'credit'  # Default
                
                if withdrawal_x and deposit_x:
                    # Both columns detected - use position
                    dist_to_withdrawal = abs(amount_x - withdrawal_x) if withdrawal_x else float('inf')
                    dist_to_deposit = abs(amount_x - deposit_x) if deposit_x else float('inf')
                    
                    if dist_to_withdrawal < dist_to_deposit:
                        direction = 'debit'
                        print(f"      📤 DEBIT (position x={amount_x:.0f} near withdrawal): £{amount:,.2f}")
                    else:
                        direction = 'credit'
                        print(f"      📥 CREDIT (position x={amount_x:.0f} near deposit): £{amount:,.2f}")
                elif withdrawal_x:
                    # Only withdrawal column detected
                    if abs(amount_x - withdrawal_x) < 50:  # Within 50 pixels
                        direction = 'debit'
                
                txn = {
                    'account_id': f'PDF_P{page_num}',
                    'date': parsed_date,
                    'amount': float(amount),
                    'currency': 'GBP',
                    'direction': direction,
                    'description': description[:500] if description else 'Transaction',
                    'counterparty_name': '',
                    'balance': float(balance) if balance else None,
                    'source': f'position_page{page_num}_y{int(y_pos)}'
                }
                transactions.append(txn)
        
        except Exception as e:
            print(f"      ⚠️ Position extraction error: {e}")
        
        return transactions
    
    def _extract_pdf_text_with_bank_config(self, content: bytes, metadata: Dict, bank_config: Dict) -> List[Dict]:
        """Extract using pure text parsing with bank-specific rules."""
        transactions = []
        
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    text_txns = self._parse_text_with_bank_config(text, page_num, bank_config)
                    transactions.extend(text_txns)
        
        return transactions
    
    def _extract_pdf_ocr_enhanced(self, content: bytes, metadata: Dict, bank_config: Dict) -> List[Dict]:
        """Extract transactions from scanned PDF using enhanced OCR."""
        transactions = []
        
        try:
            # Convert PDF to images with higher DPI for better OCR
            images = convert_from_bytes(content, dpi=400)  # Increased from 300
            
            for page_num, image in enumerate(images, 1):
                # Preprocess image for better OCR
                processed_image = self._preprocess_image_for_ocr(image)
                
                # Try different OCR configurations
                ocr_configs = [
                    '--psm 6',  # Assume uniform block of text
                    '--psm 4',  # Assume single column of text
                    '--psm 3',  # Fully automatic page segmentation
                ]
                
                best_txns = []
                for config in ocr_configs:
                    text = pytesseract.image_to_string(processed_image, config=config)
                    if text:
                        text_txns = self._parse_text_with_bank_config(text, page_num, bank_config)
                        if len(text_txns) > len(best_txns):
                            best_txns = text_txns
                
                transactions.extend(best_txns)
                    
        except Exception as e:
            print(f"   ⚠️ OCR error: {e}")
        
        return transactions
    
    def _preprocess_image_for_ocr(self, image) -> Image.Image:
        """Preprocess image to improve OCR accuracy."""
        import numpy as np
        
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to numpy array
        img_array = np.array(image)
        
        # Convert to grayscale
        gray = np.mean(img_array, axis=2).astype(np.uint8)
        
        # Apply threshold to make text clearer (binarization)
        threshold = 180
        binary = np.where(gray > threshold, 255, 0).astype(np.uint8)
        
        # Convert back to PIL Image
        return Image.fromarray(binary)
    
    def _parse_table_with_bank_config(self, table: List[List], page_num: int, bank_config: Dict) -> List[Dict]:
        """Parse a table using bank-specific configuration."""
        if not table or len(table) < 2:
            return []
        
        transactions = []
        skip_keywords = bank_config.get('skip_rows_containing', [])
        
        # DEBUG: Show table structure
        print(f"\n   🔍 TABLE DEBUG (Page {page_num}):")
        print(f"      Total rows: {len(table)}")
        if table[0]:
            print(f"      First row ({len(table[0])} cols): {table[0]}")
        if len(table) > 1 and table[1]:
            print(f"      Second row ({len(table[1])} cols): {table[1]}")
        
        # Check if this is a "single-cell" table (columns merged into one cell)
        is_single_cell = all(len(row) == 1 for row in table if row)
        
        if is_single_cell:
            print(f"      ⚠️ SINGLE-CELL TABLE - using position-based extraction")
        
        if is_single_cell or bank_config.get('single_cell_likely', False):
            # For single-cell tables, we need to use word positions to determine columns
            # First, extract the header to find column positions
            header_text = str(table[0][0]).lower() if table[0] else ''
            
            # Check if header contains column indicators
            has_withdrawal_col = 'withdrawal' in header_text
            has_deposit_col = 'deposit' in header_text
            
            if has_withdrawal_col or has_deposit_col:
                print(f"      📊 Detected Withdrawals/Deposits columns in header")
                # Return empty - let position-based extraction handle it
                # This will fall through to _extract_with_column_positions in the caller
                return []
            
            # Fall back to text-based parsing only if no clear column structure
            print(f"   📋 Page {page_num}: No clear columns, using text parsing")
            for row_idx, row in enumerate(table):
                if not row or not row[0]:
                    continue
                line = str(row[0]).strip()
                
                # Skip header rows and unwanted lines
                line_lower = line.lower()
                if any(skip in line_lower for skip in skip_keywords):
                    continue
                if 'date' in line_lower and 'description' in line_lower:
                    continue
                
                # Try to parse this line as a transaction
                txn = self._parse_single_cell_row(line, page_num, row_idx)
                if txn:
                    transactions.append(txn)
            
            return transactions
        
        # Standard multi-column parsing with bank config
        header_idx = None
        header = None
        header_keywords = bank_config.get('header_keywords', ['date', 'description', 'amount', 'balance'])
        
        for idx in range(min(5, len(table))):
            row = table[idx]
            if not row:
                continue
            row_text = ' '.join([str(cell).lower() for cell in row if cell])
            
            matches = sum(1 for kw in header_keywords if kw in row_text)
            if matches >= 2:
                header_idx = idx
                header = [str(cell).lower().strip() if cell else '' for cell in row]
                break
        
        if header_idx is not None:
            col_map = self._map_columns_with_bank_config(header, bank_config)
            start_row = header_idx + 1
            print(f"      ✅ Header found at row {header_idx}: {header}")
            print(f"      📊 Column mapping: date={col_map['date']}, desc={col_map['description']}, debit={col_map['debit']}, credit={col_map['credit']}, balance={col_map['balance']}")
        else:
            col_map = self._create_default_col_map(bank_config)
            start_row = 0
            print(f"      ⚠️ No header found, using default column mapping")
        
        for row_idx in range(start_row, len(table)):
            row = [str(cell).strip() if cell else '' for cell in table[row_idx]]
            
            # Skip rows containing unwanted content
            row_text = ' '.join(row).lower()
            if any(skip in row_text for skip in skip_keywords):
                continue
            
            txn = self._parse_row_with_bank_config(row, col_map, row_idx, bank_config)
            if txn:
                txn['source'] = f'pdf_page{page_num}_row{row_idx}'
                transactions.append(txn)
        
        return transactions
    
    def _parse_text_with_bank_config(self, text: str, page_num: int, bank_config: Dict) -> List[Dict]:
        """Parse transactions from text using bank-specific rules."""
        transactions = []
        lines = text.split('\n')
        skip_keywords = bank_config.get('skip_rows_containing', [])
        
        current_txn = None
        multiline = bank_config.get('multiline_descriptions', False)
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 8:
                continue
            
            # Skip obvious non-transaction lines
            line_lower = line.lower()
            if any(skip in line_lower for skip in skip_keywords):
                continue
            if any(skip in line_lower for skip in ['page', 'statement', 'account number', 'sort code']):
                continue
            
            # Try to find a date at the start of the line
            date_match = self._extract_date_from_text(line)
            
            if date_match:
                # Save previous transaction
                if current_txn and current_txn.get('amount'):
                    transactions.append(current_txn)
                
                parsed_date = self._parse_date_with_format(date_match, bank_config.get('date_format', 'dmy'))
                if parsed_date:
                    # Extract amounts from line
                    amounts = self._extract_amounts_from_text(line)
                    
                    # Build description
                    description = line.replace(date_match, '').strip()
                    for amt in amounts:
                        description = re.sub(r'[£$€]?\s*' + re.escape(f"{amt:,.2f}".replace(',', ',?')), '', description)
                    description = ' '.join(description.split())
                    
                    # Determine direction using bank config
                    direction = self._determine_direction(description, amounts, bank_config)
                    
                    current_txn = {
                        'account_id': f'PDF_P{page_num}',
                        'date': parsed_date,
                        'amount': amounts[0] if amounts else None,
                        'currency': 'GBP',
                        'direction': direction,
                        'description': description[:500],
                        'counterparty_name': '',
                        'balance': amounts[-1] if len(amounts) > 1 else None,
                        'source': f'text_page{page_num}_line{line_idx}'
                    }
            elif current_txn and multiline:
                # Continuation line - add to description
                if not self._extract_amounts_from_text(line):
                    current_txn['description'] = (current_txn['description'] + ' ' + line)[:500]
        
        # Don't forget the last transaction
        if current_txn and current_txn.get('amount'):
            transactions.append(current_txn)
        
        return transactions
    
    def _map_columns_with_bank_config(self, header: List[str], bank_config: Dict) -> Dict[str, int]:
        """Map columns using bank-specific configuration."""
        col_map = {
            'date': None,
            'description': None,
            'amount': None,
            'debit': None,
            'credit': None,
            'balance': None,
            'currency': None,
            'type': None
        }
        
        for idx, col_name in enumerate(header):
            col_lower = col_name.lower().strip()
            
            # Date columns
            if any(kw in col_lower for kw in ['date', 'posted', 'value']):
                if col_map['date'] is None:
                    col_map['date'] = idx
            
            # Description columns
            elif any(kw in col_lower for kw in ['description', 'details', 'narrative', 'particulars', 'memo', 'reference']):
                col_map['description'] = idx
            
            # Debit column (bank-specific) - includes singular and plural forms
            elif any(kw in col_lower for kw in ['paid out', 'money out', 'withdrawal', 'withdrawals', 'debit', 'debits', 'dr', 'out', 'payment', 'payments']):
                col_map['debit'] = idx
                print(f"         → Column {idx} '{col_name}' mapped to DEBIT")
            
            # Credit column (bank-specific) - includes singular and plural forms
            elif any(kw in col_lower for kw in ['paid in', 'money in', 'deposit', 'deposits', 'credit', 'credits', 'cr', 'receipt', 'receipts', 'in']):
                col_map['credit'] = idx
                print(f"         → Column {idx} '{col_name}' mapped to CREDIT")
            
            # Single amount column
            elif col_lower == 'amount' or col_lower == 'value':
                col_map['amount'] = idx
            
            # Balance column
            elif 'balance' in col_lower:
                col_map['balance'] = idx
            
            # Transaction type
            elif col_lower == 'type' or col_lower == 'transaction type':
                col_map['type'] = idx
        
        return col_map
    
    def _create_default_col_map(self, bank_config: Dict) -> Dict[str, int]:
        """Create default column map based on bank config."""
        expected_columns = bank_config.get('columns', ['date', 'description', 'debit', 'credit', 'balance'])
        col_map = {
            'date': None,
            'description': None,
            'amount': None,
            'debit': None,
            'credit': None,
            'balance': None,
            'currency': None,
            'type': None
        }
        
        for idx, col in enumerate(expected_columns):
            if col in col_map:
                col_map[col] = idx
            elif col in ['paid_out', 'money_out', 'withdrawals', 'payments']:
                col_map['debit'] = idx
            elif col in ['paid_in', 'money_in', 'deposits', 'receipts']:
                col_map['credit'] = idx
        
        return col_map
    
    def _parse_row_with_bank_config(self, row: List[str], col_map: Dict[str, int], row_idx: int, bank_config: Dict) -> Optional[Dict]:
        """Parse a single row using bank-specific configuration."""
        try:
            # Get date
            date_str = None
            if col_map['date'] is not None and col_map['date'] < len(row):
                date_str = row[col_map['date']].strip()
            
            if not date_str:
                return None
            
            parsed_date = self._parse_date_with_format(date_str, bank_config.get('date_format', 'dmy'))
            if not parsed_date:
                return None
            
            # Get amount and direction
            amount = None
            direction = 'credit'
            
            # Try single amount column first
            if col_map['amount'] is not None and col_map['amount'] < len(row):
                amt_str = row[col_map['amount']].strip()
                amount = self._parse_amount_universal(amt_str)
                if amount:
                    if '-' in amt_str or '(' in amt_str:
                        direction = 'debit'
                        amount = abs(amount)
            
            # Try split debit/credit columns
            if amount is None:
                if col_map['debit'] is not None and col_map['debit'] < len(row):
                    debit_str = row[col_map['debit']].strip()
                    if debit_str and debit_str not in ['-', '', '0', '0.00']:
                        amount = self._parse_amount_universal(debit_str)
                        if amount:
                            direction = 'debit'
                
                if amount is None and col_map['credit'] is not None and col_map['credit'] < len(row):
                    credit_str = row[col_map['credit']].strip()
                    if credit_str and credit_str not in ['-', '', '0', '0.00']:
                        amount = self._parse_amount_universal(credit_str)
                        if amount:
                            direction = 'credit'
            
            if amount is None or amount == 0:
                return None
            
            # Get description
            description = ''
            if col_map['description'] is not None and col_map['description'] < len(row):
                description = row[col_map['description']].strip()
            
            if not description:
                for idx, cell in enumerate(row):
                    if idx not in [col_map['date'], col_map['amount'], col_map['debit'], 
                                   col_map['credit'], col_map['balance']]:
                        cell_str = cell.strip()
                        if cell_str and not self._is_amount(cell_str) and len(cell_str) > 2:
                            description += ' ' + cell_str
                description = description.strip()
            
            # Get balance
            balance = None
            if col_map['balance'] is not None and col_map['balance'] < len(row):
                balance = self._parse_amount_universal(row[col_map['balance']])
            
            return {
                'account_id': 'PDF_IMPORT',
                'date': parsed_date,
                'amount': float(amount),
                'currency': 'GBP',
                'direction': direction,
                'description': description[:500] if description else 'Transaction',
                'counterparty_name': '',
                'balance': float(balance) if balance else None,
                'source': f'pdf_row_{row_idx}'
            }
            
        except Exception as e:
            return None
    
    def _parse_date_with_format(self, date_str: str, format_hint: str = 'dmy') -> Optional[str]:
        """Parse date string with format hint from bank config."""
        # First try the universal parser
        result = self._parse_date_universal(date_str)
        if result:
            return result
        
        # If that fails, try with format hint
        date_str = date_str.strip()
        
        # Try common patterns based on format hint
        patterns = []
        if format_hint == 'dmy':
            patterns = [
                (r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})', 'dmy'),
                (r'(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{2,4})', 'dmy_text'),
            ]
        elif format_hint == 'mdy':
            patterns = [
                (r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})', 'mdy'),
                (r'([A-Za-z]{3,})\s+(\d{1,2}),?\s+(\d{2,4})', 'mdy_text'),
            ]
        elif format_hint == 'iso':
            patterns = [
                (r'(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})', 'iso'),
            ]
        
        for pattern, fmt in patterns:
            match = re.match(pattern, date_str, re.IGNORECASE)
            if match:
                try:
                    if fmt == 'dmy':
                        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    elif fmt == 'mdy':
                        month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    elif fmt == 'iso':
                        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    elif fmt == 'dmy_text':
                        day = int(match.group(1))
                        month = self.month_map.get(match.group(2).lower()[:3], 0)
                        year = int(match.group(3))
                    elif fmt == 'mdy_text':
                        month = self.month_map.get(match.group(1).lower()[:3], 0)
                        day = int(match.group(2))
                        year = int(match.group(3))
                    else:
                        continue
                    
                    if year < 100:
                        year += 2000 if year < 50 else 1900
                    
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        return f"{year:04d}-{month:02d}-{day:02d}"
                except:
                    continue
        
        return None
    
    def _determine_direction(self, description: str, amounts: List[float], bank_config: Dict) -> str:
        """Determine transaction direction using bank-specific rules.
        
        IMPORTANT: Check DEBIT keywords FIRST because they contain clearer directional
        indicators ('to', 'out') that take precedence over generic credit keywords.
        """
        desc_lower = description.lower()
        
        # Check DEBIT keywords FIRST - these have clear directional indicators
        debit_keywords = ['card payment', 'withdrawal', 'transfer out', 'purchase', 
                         'faster payment to', 'fp to', 'direct debit', 'standing order to', 
                         'bill payment', 'atm', 'cash', 'payment to', 'chaps to', 'bacs to',
                         'transfer to', 'money out', 'paid out']
        
        if any(kw in desc_lower for kw in debit_keywords):
            print(f"      📤 Direction=DEBIT (keyword): {description[:50]}...")
            return 'debit'
        
        # Then check CREDIT keywords
        credit_keywords = ['interest', 'deposit', 'transfer in', 'salary', 'refund', 
                          'faster payment from', 'fp from', 'standing order from', 
                          'dividend', 'bonus', 'credit', 'incoming', 'wages', 'pension',
                          'transfer from', 'payment from', 'received', 'money in', 'paid in']
        
        if any(kw in desc_lower for kw in credit_keywords):
            print(f"      📥 Direction=CREDIT (keyword): {description[:50]}...")
            return 'credit'
        
        # For BACS - check context (BACS alone is usually salary/credit, but BACS TO is debit)
        if 'bacs' in desc_lower:
            if ' to ' in desc_lower:
                print(f"      📤 Direction=DEBIT (bacs to): {description[:50]}...")
                return 'debit'
            else:
                print(f"      📥 Direction=CREDIT (bacs): {description[:50]}...")
                return 'credit'
        
        # Default to credit (most unspecified transactions are deposits)
        print(f"      ❓ Direction=CREDIT (default): {description[:50]}...")
        return 'credit'
    
    def _validate_balances(self, transactions: List[Dict]) -> Tuple[List[Dict], Dict]:
        """Validate transaction balances and flag discrepancies."""
        validation_result = {
            'balance_checks_passed': 0,
            'balance_checks_failed': 0,
            'balance_validated': False,
            'discrepancies': []
        }
        
        # Sort by date AND by source line number for same-date transactions
        def sort_key(t):
            date = t.get('date', '')
            source = t.get('source', '')
            # Extract line/row number from source like 'pdf_page1_row5'
            line_num = 0
            if source:
                match = re.search(r'(\d+)$', source)
                if match:
                    line_num = int(match.group(1))
            return (date, line_num)
        
        sorted_txns = sorted(transactions, key=sort_key)
        
        # Check if we have balance data
        txns_with_balance = [t for t in sorted_txns if t.get('balance') is not None]
        
        if len(txns_with_balance) < 2:
            return sorted_txns, validation_result
        
        validation_result['balance_validated'] = True
        
        # Validate consecutive balances
        for i in range(1, len(txns_with_balance)):
            prev_txn = txns_with_balance[i - 1]
            curr_txn = txns_with_balance[i]
            
            prev_balance = prev_txn.get('balance', 0)
            curr_balance = curr_txn.get('balance', 0)
            amount = curr_txn.get('amount', 0)
            direction = curr_txn.get('direction', 'credit')
            
            # Calculate expected balance
            if direction == 'credit':
                expected_balance = prev_balance + amount
            else:
                expected_balance = prev_balance - amount
            
            # Allow small tolerance for rounding
            tolerance = 0.05
            
            balance_diff = abs(curr_balance - expected_balance)
            
            # Debug logging for large transactions
            if amount >= 10000:
                print(f"   💰 BALANCE CHECK: {curr_txn.get('description', '')[:40]}...")
                print(f"      Amount: £{amount:,.2f}, Direction: {direction}")
                print(f"      Prev balance: £{prev_balance:,.2f}")
                print(f"      Expected: £{expected_balance:,.2f}, Actual: £{curr_balance:,.2f}")
                print(f"      Diff: £{balance_diff:,.2f}")
            
            if balance_diff <= tolerance:
                validation_result['balance_checks_passed'] += 1
                curr_txn['balance_validated'] = True
                if amount >= 10000:
                    print(f"      ✅ BALANCE MATCHES")
            else:
                # Check if direction was wrong (discrepancy = 2 * amount)
                direction_error_amount = 2 * amount
                actual_diff = curr_balance - expected_balance
                
                if amount >= 10000:
                    print(f"      ❌ BALANCE MISMATCH - checking direction...")
                    print(f"      Direction error would be: £{direction_error_amount:,.2f}")
                    print(f"      Actual diff: £{abs(actual_diff):,.2f}")
                
                # Only auto-correct if we're VERY confident (exact match within tolerance)
                if abs(abs(actual_diff) - direction_error_amount) <= tolerance:
                    # Direction was definitely wrong, flip it
                    old_direction = curr_txn['direction']
                    curr_txn['direction'] = 'debit' if direction == 'credit' else 'credit'
                    curr_txn['direction_corrected'] = True
                    
                    # Re-validate with corrected direction
                    if curr_txn['direction'] == 'credit':
                        new_expected = prev_balance + amount
                    else:
                        new_expected = prev_balance - amount
                    
                    if abs(curr_balance - new_expected) <= tolerance:
                        validation_result['balance_checks_passed'] += 1
                        curr_txn['balance_validated'] = True
                        print(f"   ✅ CORRECTED direction: {curr_txn.get('description', '')[:40]} ({old_direction} → {curr_txn['direction']})")
                    else:
                        # Correction didn't help, revert
                        curr_txn['direction'] = old_direction
                        del curr_txn['direction_corrected']
                        validation_result['balance_checks_failed'] += 1
                        curr_txn['balance_validated'] = False
                        if amount >= 10000:
                            print(f"      ⚠️ Correction didn't help, reverting")
                else:
                    # Just flag as discrepancy, don't try to correct
                    validation_result['balance_checks_failed'] += 1
                    curr_txn['balance_validated'] = False
                    curr_txn['balance_discrepancy'] = {
                        'expected': expected_balance,
                        'actual': curr_balance,
                        'difference': actual_diff
                    }
                    validation_result['discrepancies'].append({
                        'date': curr_txn.get('date'),
                        'description': curr_txn.get('description', '')[:50],
                        'expected': expected_balance,
                        'actual': curr_balance,
                        'difference': actual_diff
                    })
                    if amount >= 10000:
                        print(f"      ⚠️ Balance discrepancy - not a simple direction error")
        
        return sorted_txns, validation_result
    
    def _extract_pdf_ocr(self, content: bytes, metadata: Dict) -> List[Dict]:
        """Extract transactions from scanned PDF using OCR."""
        transactions = []
        
        try:
            # Convert PDF to images
            images = convert_from_bytes(content, dpi=300)
            
            for page_num, image in enumerate(images, 1):
                # Run OCR
                text = pytesseract.image_to_string(image, config='--psm 6')
                
                if text:
                    text_txns = self._parse_text_universal(text, page_num)
                    transactions.extend(text_txns)
                    
        except Exception as e:
            print(f"   ⚠️ OCR error: {e}")
        
        return transactions
    
    def _parse_image(self, content: bytes) -> Dict[str, Any]:
        """Parse image file (screenshot) using OCR."""
        metadata = {
            'source': 'image',
            'extraction_method': 'ocr',
            'ocr_used': True,
            'bank': None
        }
        
        try:
            # Open image
            image = Image.open(io.BytesIO(content))
            
            # Preprocess for better OCR
            image = self._preprocess_image(image)
            
            # Run OCR
            print("🔍 Running OCR on image...")
            text = pytesseract.image_to_string(image, config='--psm 6')
            
            if not text or len(text.strip()) < 20:
                return {
                    'success': False,
                    'transactions': [],
                    'metadata': metadata,
                    'error': 'Could not extract text from image'
                }
            
            # Detect bank from text
            metadata['bank'] = self._detect_bank_from_text(text)
            print(f"🏦 Detected bank: {metadata['bank'] or 'Unknown'}")
            
            # Parse transactions from OCR text
            transactions = self._parse_text_universal(text, 1)
            transactions = self._deduplicate(transactions)
            
            print(f"✅ Extracted {len(transactions)} transactions from image")
            
            return {
                'success': len(transactions) > 0,
                'transactions': transactions,
                'metadata': metadata,
                'error': None if transactions else 'No transactions found in image'
            }
            
        except Exception as e:
            return {
                'success': False,
                'transactions': [],
                'metadata': metadata,
                'error': f'Image processing error: {str(e)}'
            }
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocess image for better OCR results."""
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to grayscale
        image = image.convert('L')
        
        # Increase size if small
        width, height = image.size
        if width < 1000:
            ratio = 1000 / width
            image = image.resize((int(width * ratio), int(height * ratio)), Image.Resampling.LANCZOS)
        
        # Increase contrast
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        # Sharpen
        from PIL import ImageFilter
        image = image.filter(ImageFilter.SHARPEN)
        
        return image
    
    def _parse_csv(self, content: bytes) -> Dict[str, Any]:
        """Parse CSV file with intelligent column detection."""
        metadata = {
            'source': 'csv',
            'extraction_method': 'csv_parse',
            'columns_detected': {},
            'bank': None
        }
        
        try:
            # Try different encodings
            text = None
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    text = content.decode(encoding)
                    break
                except:
                    continue
            
            if not text:
                return {
                    'success': False,
                    'transactions': [],
                    'metadata': metadata,
                    'error': 'Could not decode CSV file'
                }
            
            # Detect delimiter
            delimiter = self._detect_csv_delimiter(text)
            
            # Parse CSV
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = list(reader)
            
            if len(rows) < 2:
                return {
                    'success': False,
                    'transactions': [],
                    'metadata': metadata,
                    'error': 'CSV file too short'
                }
            
            # Find header row
            header_idx, header = self._find_csv_header(rows)
            metadata['columns_detected']['header_row'] = header_idx
            
            # Map columns
            col_map = self._map_csv_columns(header)
            metadata['columns_detected'].update(col_map)
            
            # Parse transactions
            transactions = []
            for row_idx in range(header_idx + 1, len(rows)):
                row = rows[row_idx]
                if not row or all(not cell.strip() for cell in row):
                    continue
                
                txn = self._parse_csv_row(row, col_map, row_idx)
                if txn:
                    transactions.append(txn)
            
            transactions = self._deduplicate(transactions)
            
            print(f"✅ Extracted {len(transactions)} transactions from CSV")
            
            return {
                'success': len(transactions) > 0,
                'transactions': transactions,
                'metadata': metadata,
                'error': None if transactions else 'No valid transactions in CSV'
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'transactions': [],
                'metadata': metadata,
                'error': f'CSV parsing error: {str(e)}'
            }
    
    def _detect_csv_delimiter(self, text: str) -> str:
        """Detect CSV delimiter."""
        first_lines = text[:2000]
        
        comma_count = first_lines.count(',')
        tab_count = first_lines.count('\t')
        semicolon_count = first_lines.count(';')
        pipe_count = first_lines.count('|')
        
        counts = {',': comma_count, '\t': tab_count, ';': semicolon_count, '|': pipe_count}
        return max(counts, key=counts.get)
    
    def _find_csv_header(self, rows: List[List[str]]) -> Tuple[int, List[str]]:
        """Find the header row in CSV."""
        for idx in range(min(10, len(rows))):
            row = rows[idx]
            row_lower = [str(cell).lower().strip() for cell in row]
            row_text = ' '.join(row_lower)
            
            # Check for common header keywords
            matches = sum(1 for kw in self.date_column_names + self.amount_column_names 
                         if any(kw in cell for cell in row_lower))
            
            if matches >= 2:
                return idx, row
        
        # Default to first row
        return 0, rows[0] if rows else []
    
    def _map_csv_columns(self, header: List[str]) -> Dict[str, int]:
        """Map CSV columns to their indices."""
        col_map = {
            'date': None,
            'amount': None,
            'debit': None,
            'credit': None,
            'description': None,
            'balance': None,
            'direction': None,
            'currency': None
        }
        
        header_lower = [str(h).lower().strip() for h in header]
        
        for idx, col in enumerate(header_lower):
            # Clean column name - remove currency indicators in parentheses
            col_clean = re.sub(r'\s*\([^)]*\)\s*', '', col).strip()
            
            # Date columns
            if any(kw in col for kw in self.date_column_names):
                if col_map['date'] is None:
                    col_map['date'] = idx
            
            # Amount columns - check both original and cleaned
            # Single amount column (signed or absolute)
            if col_clean in ['amount', 'value', 'sum', 'total', 'transaction amount'] or \
               col.startswith('amount') or 'amount' in col_clean:
                if col_map['amount'] is None:
                    col_map['amount'] = idx
            
            # Debit/Out columns
            if any(kw in col for kw in ['paid out', 'debit', 'withdrawal', 'money out', 'out', 'expense']):
                col_map['debit'] = idx
            
            # Credit/In columns  
            if any(kw in col for kw in ['paid in', 'credit', 'deposit', 'money in', 'income']):
                col_map['credit'] = idx
            
            # Description columns - be more flexible
            if any(kw in col for kw in self.description_column_names):
                if col_map['description'] is None:
                    col_map['description'] = idx
            # Also check for 'counter party', 'counterparty', 'name'
            if col_map['description'] is None:
                if any(kw in col for kw in ['counter party', 'counterparty', 'name', 'merchant', 'payee']):
                    col_map['description'] = idx
            
            # Balance - be more flexible
            if 'balance' in col:
                col_map['balance'] = idx
            
            # Direction/Type
            if col in ['direction', 'type', 'transaction type', 'category']:
                col_map['direction'] = idx
            
            # Currency
            if col in ['currency', 'ccy']:
                col_map['currency'] = idx
        
        return col_map
    
    def _parse_csv_row(self, row: List[str], col_map: Dict[str, int], row_idx: int) -> Optional[Dict]:
        """Parse a single CSV row into a transaction."""
        try:
            # Get date
            date_str = None
            if col_map['date'] is not None and col_map['date'] < len(row):
                date_str = row[col_map['date']].strip()
            
            if not date_str:
                return None
            
            parsed_date = self._parse_date_universal(date_str)
            if not parsed_date:
                return None
            
            # Get amount and direction
            amount = None
            direction = 'credit'
            
            # Try single amount column first
            if col_map['amount'] is not None and col_map['amount'] < len(row):
                amt_str = row[col_map['amount']].strip()
                amount = self._parse_amount_universal(amt_str)
                if amount:
                    # Determine direction from sign
                    if '-' in amt_str or '(' in amt_str:
                        direction = 'debit'
                        amount = abs(amount)
            
            # Try split debit/credit columns
            if amount is None:
                if col_map['debit'] is not None and col_map['debit'] < len(row):
                    debit_str = row[col_map['debit']].strip()
                    if debit_str and debit_str not in ['-', '', '0', '0.00']:
                        amount = self._parse_amount_universal(debit_str)
                        if amount:
                            direction = 'debit'
                
                if amount is None and col_map['credit'] is not None and col_map['credit'] < len(row):
                    credit_str = row[col_map['credit']].strip()
                    if credit_str and credit_str not in ['-', '', '0', '0.00']:
                        amount = self._parse_amount_universal(credit_str)
                        if amount:
                            direction = 'credit'
            
            if amount is None or amount == 0:
                return None
            
            # Get description
            description = ''
            if col_map['description'] is not None and col_map['description'] < len(row):
                description = row[col_map['description']].strip()
            
            # If no description column, concatenate other text columns
            if not description:
                for idx, cell in enumerate(row):
                    if idx not in [col_map['date'], col_map['amount'], col_map['debit'], 
                                   col_map['credit'], col_map['balance']]:
                        cell_str = cell.strip()
                        if cell_str and not self._is_amount(cell_str) and len(cell_str) > 2:
                            description += ' ' + cell_str
                description = description.strip()
            
            # Infer direction from description if we have a single amount column
            if col_map['amount'] is not None and col_map['debit'] is None:
                desc_lower = description.lower()
                if any(kw in desc_lower for kw in self.debit_keywords):
                    direction = 'debit'
                elif any(kw in desc_lower for kw in self.credit_keywords):
                    direction = 'credit'
            
            # Get balance
            balance = None
            if col_map['balance'] is not None and col_map['balance'] < len(row):
                balance = self._parse_amount_universal(row[col_map['balance']])
            
            # Get currency
            currency = 'GBP'  # Default
            if col_map['currency'] is not None and col_map['currency'] < len(row):
                currency = row[col_map['currency']].strip().upper()
            
            return {
                'account_id': 'CSV_IMPORT',
                'date': parsed_date,
                'amount': float(amount),
                'currency': currency,
                'direction': direction,
                'description': description[:500] if description else 'Transaction',
                'counterparty_name': '',
                'balance': float(balance) if balance else None,
                'source': f'csv_row_{row_idx}'
            }
            
        except Exception as e:
            return None
    
    def _parse_excel(self, content: bytes) -> Dict[str, Any]:
        """Parse Excel file."""
        metadata = {'source': 'excel', 'extraction_method': 'excel_parse'}
        
        try:
            import openpyxl
            
            workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            sheet = workbook.active
            
            # Convert to list of rows
            rows = []
            for row in sheet.iter_rows(values_only=True):
                rows.append([str(cell) if cell is not None else '' for cell in row])
            
            if not rows:
                return {
                    'success': False,
                    'transactions': [],
                    'metadata': metadata,
                    'error': 'Empty Excel file'
                }
            
            # Use CSV parsing logic
            header_idx, header = self._find_csv_header(rows)
            col_map = self._map_csv_columns(header)
            
            transactions = []
            for row_idx in range(header_idx + 1, len(rows)):
                row = rows[row_idx]
                if not row or all(not str(cell).strip() for cell in row):
                    continue
                
                txn = self._parse_csv_row(row, col_map, row_idx)
                if txn:
                    transactions.append(txn)
            
            transactions = self._deduplicate(transactions)
            
            return {
                'success': len(transactions) > 0,
                'transactions': transactions,
                'metadata': metadata,
                'error': None if transactions else 'No valid transactions in Excel'
            }
            
        except ImportError:
            return {
                'success': False,
                'transactions': [],
                'metadata': metadata,
                'error': 'Excel support not available (openpyxl not installed)'
            }
        except Exception as e:
            return {
                'success': False,
                'transactions': [],
                'metadata': metadata,
                'error': f'Excel parsing error: {str(e)}'
            }
    
    def _parse_table_universal(self, table: List[List], page_num: int) -> List[Dict]:
        """Parse a table with universal column detection."""
        if not table or len(table) < 2:
            return []
        
        transactions = []
        
        # Check if this is a "single-cell" table (columns merged into one cell)
        # This happens when pdfplumber can't detect column boundaries
        is_single_cell = all(len(row) == 1 for row in table if row)
        
        if is_single_cell:
            # Parse as text lines instead
            print(f"   📋 Page {page_num}: Single-cell table detected, parsing as text lines")
            for row_idx, row in enumerate(table):
                if not row or not row[0]:
                    continue
                line = str(row[0]).strip()
                
                # Skip header rows
                if 'date' in line.lower() and 'description' in line.lower():
                    continue
                
                # Try to parse this line as a transaction
                txn = self._parse_single_cell_row(line, page_num, row_idx)
                if txn:
                    transactions.append(txn)
            
            return transactions
        
        # Standard multi-column parsing
        # Find header row
        header_idx = None
        header = None
        
        for idx in range(min(5, len(table))):
            row = table[idx]
            if not row:
                continue
            row_text = ' '.join([str(cell).lower() for cell in row if cell])
            
            matches = sum(1 for kw in ['date', 'amount', 'description', 'balance', 'debit', 'credit', 'paid']
                         if kw in row_text)
            if matches >= 2:
                header_idx = idx
                header = [str(cell).lower().strip() if cell else '' for cell in row]
                break
        
        if header_idx is not None:
            # Map columns
            col_map = self._map_csv_columns(header)
            start_row = header_idx + 1
        else:
            # Positional parsing: assume Date | Description | Out | In | Balance
            col_map = {'date': 0, 'description': 1, 'debit': 2, 'credit': 3, 'balance': 4, 'amount': None}
            start_row = 0
        
        for row_idx in range(start_row, len(table)):
            row = [str(cell).strip() if cell else '' for cell in table[row_idx]]
            
            txn = self._parse_csv_row(row, col_map, row_idx)
            if txn:
                txn['source'] = f'pdf_page{page_num}_row{row_idx}'
                transactions.append(txn)
        
        return transactions
    
    def _parse_single_cell_row(self, line: str, page_num: int, row_idx: int) -> Optional[Dict]:
        """Parse a single-cell row where all columns are merged into one text string."""
        import re
        
        if not line or len(line) < 10:
            return None
        
        # Pattern: Date at start, then description, then amounts
        # Example: "15/01/2020 STANDING ORDER FROM HSBC ****5678 £2,500.00 £15,000.00"
        
        # Extract date from beginning
        date_match = re.match(r'^(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', line)
        if not date_match:
            return None
        
        date_str = date_match.group(1)
        parsed_date = self._parse_date_universal(date_str)
        if not parsed_date:
            return None
        
        # Extract all amounts from the line (with or without £ symbol)
        amounts = re.findall(r'£?([\d,]+\.\d{2})', line)
        if not amounts:
            return None
        
        # Parse amounts
        parsed_amounts = []
        for amt in amounts:
            try:
                parsed_amounts.append(float(amt.replace(',', '')))
            except:
                pass
        
        if not parsed_amounts:
            return None
        
        # Get description - everything between date and first amount
        rest_of_line = line[date_match.end():].strip()
        
        # Find where the first amount starts
        first_amt_match = re.search(r'£?[\d,]+\.\d{2}', rest_of_line)
        if first_amt_match:
            description = rest_of_line[:first_amt_match.start()].strip()
        else:
            description = rest_of_line
        
        # Determine direction based on position and description
        # For statements with Withdrawals | Deposits | Balance columns:
        # - Withdrawal column comes before Deposit column
        # - If there are 2 amounts: first is debit/credit, second is balance
        # - If there are 3 amounts: first is withdrawal, second is deposit, third is balance
        
        direction = 'credit'  # Default
        amount = parsed_amounts[0]
        balance = parsed_amounts[-1] if len(parsed_amounts) > 1 else None
        
        # Check direction based on description keywords
        desc_lower = description.lower()
        
        # DEBIT keywords - check these FIRST (outgoing money)
        # These indicate money leaving the account
        if any(kw in desc_lower for kw in ['card payment', 'withdrawal', 'transfer out', 
                                            'purchase', 'faster payment to', 'fp to',
                                            'direct debit', 'standing order to', 'bill payment',
                                            'atm', 'cash', 'payment to', 'chaps to', 'bacs to']):
            direction = 'debit'
            print(f"      📤 DEBIT (keyword match): {description[:50]}...")
        # CREDIT keywords - incoming money
        elif any(kw in desc_lower for kw in ['interest', 'deposit', 'transfer in', 'salary', 
                                              'refund', 'faster payment from', 'fp from',
                                              'standing order from', 'dividend', 'bonus',
                                              'credit', 'incoming', 'payment from', 'received']):
            direction = 'credit'
            print(f"      📥 CREDIT (keyword match): {description[:50]}...")
        else:
            print(f"      ❓ DEFAULT credit (no keyword): {description[:50]}...")
        
        # For statements where balance grows with deposits:
        # We can sometimes infer direction from balance changes, but that requires previous balance
        
        return {
            'account_id': '',  # Will be populated from PDF header extraction in _parse_pdf()
            'date': parsed_date,
            'amount': float(amount),
            'currency': 'GBP',
            'direction': direction,
            'description': description[:500] if description else 'Transaction',
            'counterparty_name': '',
            'balance': float(balance) if balance else None,
            'source': f'pdf_page{page_num}_row{row_idx}'
        }
    
    def _parse_text_universal(self, text: str, page_num: int) -> List[Dict]:
        """Parse transactions from text using universal pattern matching."""
        transactions = []
        lines = text.split('\n')
        
        current_txn = None
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 8:
                continue
            
            # Skip obvious non-transaction lines
            line_lower = line.lower()
            if any(skip in line_lower for skip in ['page', 'statement', 'account number', 'sort code', 
                                                     'balance brought', 'balance carried', 'opening balance',
                                                     'closing balance', 'total']):
                continue
            
            # Try to find a date at the start of the line
            date_match = self._extract_date_from_text(line)
            
            if date_match:
                # Save previous transaction
                if current_txn and current_txn.get('amount'):
                    transactions.append(current_txn)
                
                parsed_date = self._parse_date_universal(date_match)
                if parsed_date:
                    # Extract amounts from line
                    amounts = self._extract_amounts_from_text(line)
                    
                    # Build description
                    description = line
                    # Remove date from description
                    description = description.replace(date_match, '').strip()
                    # Remove amounts from description
                    for amt in amounts:
                        description = re.sub(r'[£$€]?\s*' + re.escape(f"{amt:,.2f}".replace(',', ',?')), '', description)
                    description = ' '.join(description.split())
                    
                    # Determine direction
                    direction = 'credit'
                    if any(kw in description.lower() for kw in self.debit_keywords):
                        direction = 'debit'
                    
                    current_txn = {
                        'account_id': f'PDF_P{page_num}',
                        'date': parsed_date,
                        'amount': amounts[0] if amounts else None,
                        'currency': 'GBP',
                        'direction': direction,
                        'description': description[:500],
                        'counterparty_name': '',
                        'balance': amounts[-1] if len(amounts) > 1 else None,
                        'source': f'text_page{page_num}_line{line_idx}'
                    }
            elif current_txn:
                # Continuation line - add to description
                if not self._extract_amounts_from_text(line):
                    current_txn['description'] += ' ' + line
                else:
                    # Line has amounts - might be the amount line for this transaction
                    amounts = self._extract_amounts_from_text(line)
                    if not current_txn.get('amount') and amounts:
                        current_txn['amount'] = amounts[0]
                        if len(amounts) > 1:
                            current_txn['balance'] = amounts[-1]
        
        # Don't forget last transaction
        if current_txn and current_txn.get('amount'):
            transactions.append(current_txn)
        
        return transactions
    
    def _extract_date_from_text(self, text: str) -> Optional[str]:
        """Extract date string from text."""
        for pattern, _ in self.date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group()
        return None
    
    def _parse_date_universal(self, date_str: str) -> Optional[str]:
        """Parse any date format to YYYY-MM-DD."""
        if not date_str:
            return None
        
        date_str = date_str.strip()
        current_year = datetime.now().year
        
        for pattern, fmt_type in self.date_patterns:
            match = re.match(pattern, date_str, re.IGNORECASE)
            if not match:
                continue
            
            try:
                if fmt_type == 'uk_text':
                    day = int(match.group(1))
                    month_str = match.group(2).lower()
                    month = self.month_map.get(month_str[:3])
                    year = int(match.group(3)) if match.group(3) else current_year
                    if year < 100:
                        year += 2000 if year < 50 else 1900
                
                elif fmt_type == 'us_text':
                    month_str = match.group(1).lower()
                    month = self.month_map.get(month_str[:3])
                    day = int(match.group(2))
                    year = int(match.group(3)) if match.group(3) else current_year
                    if year < 100:
                        year += 2000 if year < 50 else 1900
                
                elif fmt_type == 'dmy_or_mdy':
                    part1 = int(match.group(1))
                    part2 = int(match.group(2))
                    year = int(match.group(3))
                    if year < 100:
                        year += 2000 if year < 50 else 1900
                    
                    # Determine if DMY or MDY
                    if part1 > 12:  # Must be day
                        day, month = part1, part2
                    elif part2 > 12:  # Must be day
                        month, day = part1, part2
                    else:
                        # Assume DMY for non-US
                        day, month = part1, part2
                
                elif fmt_type == 'iso':
                    year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))
                
                elif fmt_type == 'compact':
                    compact = match.group(1)
                    # Try YYYYMMDD first
                    if int(compact[:4]) > 1900:
                        year = int(compact[:4])
                        month = int(compact[4:6])
                        day = int(compact[6:8])
                    else:
                        # Try DDMMYYYY
                        day = int(compact[:2])
                        month = int(compact[2:4])
                        year = int(compact[4:8])
                
                if month and 1 <= day <= 31 and 1 <= month <= 12:
                    return f"{year:04d}-{month:02d}-{day:02d}"
                    
            except Exception:
                continue
        
        return None
    
    def _extract_amounts_from_text(self, text: str) -> List[float]:
        """Extract all amounts from text."""
        amounts = []
        
        for pattern in self.amount_patterns:
            for match in re.finditer(pattern, text):
                try:
                    # Get the numeric part
                    groups = match.groups()
                    for g in groups:
                        if g and re.match(r'[\d,]+\.?\d*', g):
                            amt_str = g.replace(',', '')
                            amount = float(amt_str)
                            if amount > 0:
                                amounts.append(amount)
                                break
                except:
                    continue
        
        return amounts
    
    def _parse_amount_universal(self, text: str) -> Optional[float]:
        """Parse amount from text, handling various formats."""
        if not text:
            return None
        
        text = text.strip()
        
        # Remove currency symbols and codes
        text = re.sub(r'[£$€¥₹฿]', '', text)
        text = re.sub(r'(GBP|USD|EUR|JPY|INR|AUD|CAD|CHF|CNY)\s*', '', text, flags=re.IGNORECASE)
        
        # Handle negative formats
        is_negative = False
        if text.startswith('(') and text.endswith(')'):
            is_negative = True
            text = text[1:-1]
        elif text.startswith('-') or text.endswith('-'):
            is_negative = True
            text = text.replace('-', '')
        elif text.endswith('DR') or text.endswith('D'):
            is_negative = True
            text = re.sub(r'DR?$', '', text)
        
        # Clean and parse
        text = text.replace(',', '').replace(' ', '').strip()
        
        try:
            amount = float(text)
            return -amount if is_negative else amount
        except:
            return None
    
    def _is_amount(self, text: str) -> bool:
        """Check if text looks like an amount."""
        text = text.strip()
        return bool(re.match(r'^[£$€]?\s*[\d,]+\.?\d*$', text))
    
    def _detect_bank_from_pdf(self, content: bytes) -> Optional[str]:
        """Detect bank from PDF content - prioritizes earliest appearance in header."""
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                if pdf.pages:
                    # Get first page text
                    text = pdf.pages[0].extract_text() or ''
                    text_lower = text.lower()
                    
                    # Find all matching banks and their positions
                    bank_positions = []
                    
                    for bank, keywords in self.bank_identifiers.items():
                        for kw in keywords:
                            pos = text_lower.find(kw)
                            if pos != -1:
                                # Check if this appears in a transaction description (after common patterns)
                                # vs appearing as the bank name/letterhead
                                context_before = text_lower[max(0, pos-30):pos]
                                
                                # If preceded by "from", "to", "at", "via" - it's likely in a transaction
                                is_in_transaction = any(word in context_before for word in 
                                    ['from ', 'to ', 'at ', 'via ', 'payment ', 'transfer '])
                                
                                # Give priority (lower position) to non-transaction occurrences
                                adjusted_pos = pos + (10000 if is_in_transaction else 0)
                                
                                bank_positions.append((adjusted_pos, bank, kw))
                                break  # Only need first occurrence of this bank
                    
                    if bank_positions:
                        # Return the bank that appears earliest (lowest position)
                        bank_positions.sort(key=lambda x: x[0])
                        detected_bank = bank_positions[0][1]
                        print(f"   Bank detection: Found {[b[1] for b in bank_positions[:3]]}, selected '{detected_bank}' (earliest)")
                        return detected_bank
                    
        except Exception as e:
            print(f"   ⚠️ Bank detection error: {e}")
        return None
    
    def _detect_bank_from_text(self, text: str) -> Optional[str]:
        """Detect bank from text content."""
        text_lower = text.lower()
        
        for bank, keywords in self.bank_identifiers.items():
            if any(kw in text_lower for kw in keywords):
                return bank
        
        return None
    
    def _deduplicate(self, transactions: List[Dict]) -> List[Dict]:
        """Remove duplicate transactions."""
        seen = set()
        unique = []
        
        for txn in transactions:
            key = (
                txn.get('date'),
                round(txn.get('amount', 0), 2),
                txn.get('description', '')[:50]
            )
            
            if key not in seen:
                seen.add(key)
                unique.append(txn)
        
        return unique


# Singleton instance
universal_parser = UniversalFinancialParser()
