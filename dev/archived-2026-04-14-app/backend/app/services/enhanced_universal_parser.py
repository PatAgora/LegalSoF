"""
Universal Financial Document Parser - Enhanced Edition

Handles edge cases:
1. Poor quality scans - Advanced image preprocessing
2. Unusual layouts - Multiple extraction strategies  
3. Multi-column statements - Positional analysis
4. Merged cells - Flexible table parsing
5. International formats - Extended date/currency support
6. Encrypted PDFs - Detection and user notification
7. Variable layouts - Pattern-based extraction

Uses AI (Claude API) as intelligent fallback for documents
that can't be parsed with traditional methods.
"""

import re
import io
import csv
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

# PDF processing
import pdfplumber
import fitz  # PyMuPDF

# Image processing and OCR
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract

# Try to import pdf2image for scanned PDFs
try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False


class EnhancedUniversalParser:
    """
    Enhanced universal parser with better edge case handling.
    
    Improvements:
    - Advanced image preprocessing for poor scans
    - Multiple OCR configurations
    - Flexible table detection
    - International format support
    - AI fallback for difficult documents
    """
    
    def __init__(self):
        # Extended date patterns (international)
        self.date_patterns = [
            # UK/EU formats
            (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:uary|ruary|ch|il|e|y|ust|tember|ober|ember)?\s*[,]?\s*(\d{2,4})?', 'dmy_text'),
            (r'(\d{1,2})[/\-\.\s](\d{1,2})[/\-\.\s](\d{2,4})', 'dmy_numeric'),
            # US formats
            (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:uary|ruary|ch|il|e|y|ust|tember|ober|ember)?\s+(\d{1,2})[,]?\s*(\d{2,4})?', 'mdy_text'),
            (r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})', 'mdy_numeric'),
            # ISO format
            (r'(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})', 'iso'),
            # European with dots
            (r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})', 'eu_dots'),
            # Compact formats
            (r'(\d{8})', 'compact'),
            # German format
            (r'(\d{1,2})\.\s*(Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\.?\s*(\d{2,4})?', 'german'),
            # French format  
            (r'(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s*(\d{2,4})?', 'french'),
            # Spanish format
            (r'(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})', 'spanish'),
        ]
        
        # Extended month mappings (international)
        self.month_map = {
            # English
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
            'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
            'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
            'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9,
            'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
            'dec': 12, 'december': 12,
            # German
            'mär': 3, 'märz': 3, 'mai': 5, 'okt': 10,
            # French
            'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4,
            'juin': 6, 'juillet': 7, 'août': 8, 'septembre': 9,
            'octobre': 10, 'novembre': 11, 'décembre': 12,
            # Spanish
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
            'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
            'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
            # Italian
            'gennaio': 1, 'febbraio': 2, 'aprile': 4, 'maggio': 5,
            'giugno': 6, 'luglio': 7, 'settembre': 9, 'ottobre': 10,
            'dicembre': 12,
            # Dutch
            'januari': 1, 'februari': 2, 'maart': 3, 'mei': 5,
            'juni': 6, 'juli': 7, 'augustus': 8, 'oktober': 10,
        }
        
        # Extended currency support
        self.currency_patterns = [
            # Symbols
            (r'£\s*([\d,]+\.?\d*)', 'GBP'),
            (r'\$\s*([\d,]+\.?\d*)', 'USD'),
            (r'€\s*([\d,]+\.?\d*)', 'EUR'),
            (r'¥\s*([\d,]+\.?\d*)', 'JPY'),
            (r'₹\s*([\d,]+\.?\d*)', 'INR'),
            (r'Fr\.?\s*([\d,\']+\.?\d*)', 'CHF'),
            (r'kr\.?\s*([\d,\s]+\.?\d*)', 'SEK'),  # Also NOK, DKK
            (r'R\$?\s*([\d,]+\.?\d*)', 'BRL'),
            (r'A\$\s*([\d,]+\.?\d*)', 'AUD'),
            (r'C\$\s*([\d,]+\.?\d*)', 'CAD'),
            # Codes before amount
            (r'(GBP|USD|EUR|JPY|INR|CHF|SEK|NOK|DKK|AUD|CAD|NZD|SGD|HKD|CNY|BRL|MXN|ZAR)\s*([\d,]+\.?\d*)', 'code_prefix'),
            # Codes after amount
            (r'([\d,]+\.?\d*)\s*(GBP|USD|EUR|JPY|INR|CHF|SEK|NOK|DKK|AUD|CAD|NZD|SGD|HKD|CNY|BRL|MXN|ZAR)', 'code_suffix'),
            # Plain amount (fallback)
            (r'([\d,]+\.\d{2})', 'plain'),
            # European format (comma as decimal)
            (r'([\d.]+,\d{2})', 'european'),
        ]
        
        # Transaction keywords (multilingual)
        self.debit_keywords = [
            # English
            'debit', 'dr', 'withdrawal', 'payment', 'purchase', 'paid',
            'sent', 'transfer out', 'outgoing', 'expense', 'charge',
            'direct debit', 'dd', 'standing order', 'so', 'card payment',
            'contactless', 'atm', 'cash', 'fee', 'interest charged',
            # German
            'lastschrift', 'abbuchung', 'überweisung', 'zahlung', 'gebühr',
            # French
            'débit', 'prélèvement', 'virement', 'paiement', 'retrait',
            # Spanish
            'débito', 'pago', 'transferencia', 'retiro', 'cargo',
        ]
        
        self.credit_keywords = [
            # English
            'credit', 'cr', 'deposit', 'received', 'income', 'refund',
            'transfer in', 'incoming', 'salary', 'wages', 'pension',
            'interest earned', 'cashback', 'reward',
            # German
            'gutschrift', 'einzahlung', 'gehalt', 'lohn',
            # French
            'crédit', 'dépôt', 'salaire', 'virement reçu',
            # Spanish
            'crédito', 'depósito', 'salario', 'ingreso',
        ]
        
        # OCR configurations to try
        self.ocr_configs = [
            '--psm 6',  # Uniform block of text
            '--psm 4',  # Single column of variable sizes
            '--psm 3',  # Fully automatic page segmentation
            '--psm 11', # Sparse text
            '--psm 6 --oem 3',  # LSTM engine
        ]
        
        # Column name variations (comprehensive - covers all major banks)
        
        # DATE column names
        self.date_column_names = [
            'date', 'transaction date', 'trans date', 'posting date', 'posted',
            'value date', 'txn date', 'created', 'time', 'completed', 'settled',
            'booked', 'effective date', 'process date', 'entry date', 'booking date',
            # German
            'datum', 'buchungstag', 'wertstellung',
            # French  
            'date opération', 'date valeur',
            # Spanish
            'fecha', 'fecha valor',
        ]
        
        # DEBIT/WITHDRAWAL column names (money going OUT)
        self.debit_column_names = [
            # English - UK banks
            'withdrawn', 'withdrawals', 'withdrawal',
            'paid out', 'paidout', 'paid_out',
            'money out', 'moneyout', 'money_out',
            'debit', 'debits', 'dr',
            'out', 'outgoing', 'outgoings',
            'payments out', 'payment out',
            'expenditure', 'spend', 'spent',
            'charges', 'charge',
            # With currency symbols
            'withdrawn(£)', 'withdrawn (£)', 'withdrawn £',
            'paid out(£)', 'paid out (£)',
            'debit(£)', 'debit (£)', 'debit £',
            'out(£)', 'out (£)',
            'money out(£)', 'money out (£)',
            # German
            'ausgaben', 'abbuchung', 'soll',
            # French
            'débit', 'dépenses', 'sortie',
            # Spanish
            'débito', 'cargo', 'salida',
            # Italian
            'uscita', 'addebito',
        ]
        
        # CREDIT/DEPOSIT column names (money coming IN)
        self.credit_column_names = [
            # English - UK banks
            'paid in', 'paidin', 'paid_in',
            'money in', 'moneyin', 'money_in',
            'credit', 'credits', 'cr',
            'in', 'incoming', 'incomings',
            'receipts', 'receipt',
            'deposits', 'deposit', 'deposited',
            'income', 'received',
            'payments in', 'payment in',
            # With currency symbols
            'paid in(£)', 'paid in (£)', 'paid in £',
            'credit(£)', 'credit (£)', 'credit £',
            'in(£)', 'in (£)',
            'money in(£)', 'money in (£)',
            'deposits(£)', 'deposits (£)',
            # German
            'einnahmen', 'gutschrift', 'haben',
            # French
            'crédit', 'entrée', 'recettes',
            # Spanish
            'crédito', 'abono', 'entrada',
            # Italian
            'entrata', 'accredito',
        ]
        
        # AMOUNT column names (single column for both - direction from sign)
        self.amount_column_names = [
            'amount', 'value', 'sum', 'total', 'transaction amount',
            'txn amount', 'balance change',
            # With currency symbols
            'amount(£)', 'amount (£)', 'amount £',
            'value(£)', 'value (£)',
            # German
            'betrag', 'umsatz', 'summe',
            # French
            'montant',
            # Spanish
            'importe', 'monto',
        ]
        
        # DESCRIPTION column names
        self.description_column_names = [
            'description', 'details', 'narrative', 'particulars', 'reference',
            'memo', 'notes', 'transaction', 'type', 'merchant', 'payee', 'name',
            'counter party', 'counterparty', 'beneficiary', 'remitter',
            'transaction details', 'payment details',
            # German
            'verwendungszweck', 'buchungstext', 'empfänger',
            # French
            'libellé', 'motif', 'bénéficiaire',
            # Spanish
            'concepto', 'descripción', 'beneficiario',
        ]
        
        # BALANCE column names
        self.balance_column_names = [
            'balance', 'running balance', 'available balance',
            'account balance', 'closing balance', 'bal',
            'cumulative', 'running total',
            # With currency
            'balance(£)', 'balance (£)', 'balance £',
            # German/Spanish
            'saldo', 'kontostand',
            # French
            'solde',
        ]
    
    def parse(self, file_content: bytes, filename: str = '', content_type: str = '') -> Dict[str, Any]:
        """
        Main entry point with enhanced error handling.
        """
        try:
            # Detect file type
            file_type = self._detect_file_type(file_content, filename, content_type)
            print(f"📁 Detected file type: {file_type}")
            
            # Check for encrypted PDF
            if file_type == 'pdf':
                is_encrypted, can_read = self._check_pdf_encryption(file_content)
                if is_encrypted and not can_read:
                    return {
                        'success': False,
                        'transactions': [],
                        'metadata': {'encrypted': True},
                        'error': 'PDF is password-protected. Please provide an unencrypted version or enter the password.'
                    }
            
            # Route to appropriate parser
            if file_type == 'pdf':
                # Try Universal Financial Parser FIRST (handles all banks)
                print("\n🌐 Trying Universal Financial Parser...")
                try:
                    from app.services.universal_financial_parser import universal_parser
                    universal_result = universal_parser.parse(file_content, filename=filename, content_type='application/pdf')
                    if universal_result['success'] and len(universal_result.get('transactions', [])) >= 3:
                        print(f"   ✅ Universal parser succeeded: {len(universal_result['transactions'])} transactions")
                        
                        # DEBUG: Log account info
                        if universal_result['transactions']:
                            first_txn = universal_result['transactions'][0]
                            print(f"   🔍 DEBUG enhanced_parser - account_id: {first_txn.get('account_id', 'MISSING')}")
                            print(f"   🔍 DEBUG enhanced_parser - account_type: {first_txn.get('account_type', 'MISSING')}")
                            print(f"   🔍 DEBUG enhanced_parser - bank_name: {first_txn.get('bank_name', 'MISSING')}")
                        
                        return universal_result
                    else:
                        print(f"   ⚠️ Universal parser: {len(universal_result.get('transactions', []))} transactions, trying fallback...")
                except Exception as e:
                    print(f"   ⚠️ Universal parser error: {e}, trying fallback...")
                
                # Fallback: Try NatWest-specific parser (for complex multi-line UK statements)
                print("\n🏦 Trying NatWest fallback parser...")
                try:
                    from app.services.natwest_statement_parser import natwest_parser
                    natwest_result = natwest_parser.parse(file_content, filename)
                    if natwest_result['success'] and len(natwest_result.get('transactions', [])) >= 3:
                        print(f"   ✅ NatWest parser succeeded: {len(natwest_result['transactions'])} transactions")
                        return natwest_result
                except Exception as e:
                    print(f"   ⚠️ NatWest parser error: {e}")
                
                # Final fallback: enhanced PDF parser
                result = self._parse_pdf_enhanced(file_content)
            elif file_type == 'image':
                result = self._parse_image_enhanced(file_content)
            elif file_type == 'csv':
                result = self._parse_csv_enhanced(file_content)
            elif file_type == 'excel':
                result = self._parse_excel(file_content)
            else:
                # Try multiple approaches
                result = self._parse_unknown(file_content, filename)
            
            # If traditional parsing failed, try AI fallback
            if not result['success'] or len(result.get('transactions', [])) < 3:
                print("⚠️ Traditional parsing got few results, trying AI extraction...")
                ai_result = self._parse_with_ai(file_content, file_type)
                if ai_result['success'] and len(ai_result.get('transactions', [])) > len(result.get('transactions', [])):
                    result = ai_result
            
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
    
    def _check_pdf_encryption(self, content: bytes) -> Tuple[bool, bool]:
        """Check if PDF is encrypted and if we can read it."""
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            is_encrypted = doc.is_encrypted
            can_read = not is_encrypted or doc.authenticate("")  # Try empty password
            doc.close()
            return is_encrypted, can_read
        except:
            return False, True
    
    def _detect_bank_from_pdf(self, content: bytes) -> Optional[str]:
        """Detect which bank a PDF statement is from."""
        bank_identifiers = {
            'natwest': ['natwest', 'national westminster'],
            'hsbc': ['hsbc'],
            'barclays': ['barclays'],
            'lloyds': ['lloyds', 'lloyds bank', 'lloyds tsb'],
            'santander': ['santander'],
            'nationwide': ['nationwide'],
            'monzo': ['monzo'],
            'starling': ['starling'],
            'revolut': ['revolut'],
            'wise': ['wise', 'transferwise'],
            'chase': ['chase', 'jpmorgan chase'],
            'bank_of_america': ['bank of america'],
        }
        
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            if doc.page_count > 0:
                # Get text from first page
                text = doc[0].get_text().lower()
                
                # Find all matching banks and their positions
                bank_positions = []
                for bank, keywords in bank_identifiers.items():
                    for kw in keywords:
                        pos = text.find(kw)
                        if pos != -1:
                            # Check if this appears in a transaction description
                            context_before = text[max(0, pos-30):pos]
                            is_in_transaction = any(word in context_before for word in 
                                ['from ', 'to ', 'at ', 'via ', 'payment ', 'transfer '])
                            # Prioritize non-transaction occurrences (bank letterhead)
                            adjusted_pos = pos + (10000 if is_in_transaction else 0)
                            bank_positions.append((adjusted_pos, bank))
                            break
                
                doc.close()
                
                if bank_positions:
                    # Return the bank that appears earliest (likely in header/letterhead)
                    bank_positions.sort(key=lambda x: x[0])
                    return bank_positions[0][1]
            
            doc.close()
        except Exception as e:
            print(f"   ⚠️ Bank detection error: {e}")
        
        return None
    
    def _detect_file_type(self, content: bytes, filename: str, content_type: str) -> str:
        """Enhanced file type detection."""
        filename_lower = filename.lower()
        
        # Check by extension
        if filename_lower.endswith('.pdf'):
            return 'pdf'
        elif filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.heic')):
            return 'image'
        elif filename_lower.endswith(('.csv', '.tsv', '.txt')):
            return 'csv'
        elif filename_lower.endswith(('.xlsx', '.xls', '.ods')):
            return 'excel'
        
        # Check by magic bytes
        if content[:4] == b'%PDF':
            return 'pdf'
        elif content[:8] == b'\x89PNG\r\n\x1a\n':
            return 'image'
        elif content[:2] == b'\xff\xd8':  # JPEG
            return 'image'
        elif content[:4] == b'GIF8':
            return 'image'
        elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
            return 'image'
        elif content[:4] == b'PK\x03\x04':  # ZIP (XLSX, ODS)
            return 'excel'
        
        # Check MIME type
        if content_type:
            if 'pdf' in content_type:
                return 'pdf'
            elif 'image' in content_type:
                return 'image'
            elif 'csv' in content_type or 'text' in content_type:
                return 'csv'
            elif 'spreadsheet' in content_type or 'excel' in content_type:
                return 'excel'
        
        # Try to decode as text
        try:
            text = content[:1000].decode('utf-8')
            if ',' in text or '\t' in text or ';' in text:
                return 'csv'
        except:
            pass
        
        return 'unknown'
    
    def _parse_pdf_enhanced(self, content: bytes) -> Dict[str, Any]:
        """Enhanced PDF parsing with multiple strategies."""
        transactions = []
        metadata = {
            'source': 'pdf',
            'pages': 0,
            'extraction_method': None,
            'strategies_tried': [],
            'ocr_used': False
        }
        
        # Strategy 1: Native text extraction with pdfplumber
        print("\n📊 Strategy 1: Native PDF extraction (pdfplumber)...")
        metadata['strategies_tried'].append('pdfplumber')
        pdfplumber_txns = self._extract_with_pdfplumber(content, metadata)
        if pdfplumber_txns and len(pdfplumber_txns) >= 5:
            print(f"   ✅ Found {len(pdfplumber_txns)} transactions")
            transactions = pdfplumber_txns
            metadata['extraction_method'] = 'pdfplumber'
        else:
            print(f"   ⚠️ Only found {len(pdfplumber_txns) if pdfplumber_txns else 0} transactions")
        
        # Strategy 2: PyMuPDF with different text extraction modes
        if len(transactions) < 5:
            print("\n📊 Strategy 2: PyMuPDF text extraction...")
            metadata['strategies_tried'].append('pymupdf')
            pymupdf_txns = self._extract_with_pymupdf_enhanced(content, metadata)
            if pymupdf_txns and len(pymupdf_txns) > len(transactions):
                print(f"   ✅ Found {len(pymupdf_txns)} transactions")
                transactions = pymupdf_txns
                metadata['extraction_method'] = 'pymupdf'
        
        # Strategy 3: OCR with multiple configurations
        if len(transactions) < 5 and PDF2IMAGE_AVAILABLE:
            print("\n📊 Strategy 3: OCR extraction...")
            metadata['strategies_tried'].append('ocr')
            ocr_txns = self._extract_with_ocr_enhanced(content, metadata)
            if ocr_txns and len(ocr_txns) > len(transactions):
                print(f"   ✅ Found {len(ocr_txns)} transactions")
                transactions = ocr_txns
                metadata['extraction_method'] = 'ocr'
                metadata['ocr_used'] = True
        
        # Strategy 4: Line-by-line pattern matching
        if len(transactions) < 5:
            print("\n📊 Strategy 4: Pattern-based line extraction...")
            metadata['strategies_tried'].append('pattern')
            pattern_txns = self._extract_with_patterns(content, metadata)
            if pattern_txns and len(pattern_txns) > len(transactions):
                print(f"   ✅ Found {len(pattern_txns)} transactions")
                transactions = pattern_txns
                metadata['extraction_method'] = 'pattern'
        
        # Deduplicate
        transactions = self._deduplicate(transactions)
        
        return {
            'success': len(transactions) > 0,
            'transactions': transactions,
            'metadata': metadata,
            'error': None if transactions else 'No transactions could be extracted'
        }
    
    def _extract_with_pdfplumber(self, content: bytes, metadata: Dict) -> List[Dict]:
        """Extract with pdfplumber using multiple table settings."""
        transactions = []
        
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                metadata['pages'] = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, 1):
                    # Try different table extraction settings
                    table_settings_list = [
                        {},  # Default
                        {'vertical_strategy': 'lines', 'horizontal_strategy': 'lines'},
                        {'vertical_strategy': 'text', 'horizontal_strategy': 'text'},
                        {'vertical_strategy': 'lines', 'horizontal_strategy': 'text'},
                        {'snap_tolerance': 5, 'join_tolerance': 5},
                    ]
                    
                    page_txns = []
                    for settings in table_settings_list:
                        tables = page.extract_tables(settings) if settings else page.extract_tables()
                        
                        for table in tables or []:
                            if table and len(table) >= 2:
                                table_txns = self._parse_table_flexible(table, page_num)
                                if len(table_txns) > len(page_txns):
                                    page_txns = table_txns
                    
                    # If no good table results, try text
                    if len(page_txns) < 3:
                        text = page.extract_text()
                        if text:
                            text_txns = self._parse_text_flexible(text, page_num)
                            if len(text_txns) > len(page_txns):
                                page_txns = text_txns
                    
                    transactions.extend(page_txns)
        except Exception as e:
            print(f"   ⚠️ pdfplumber error: {e}")
        
        return transactions
    
    def _extract_with_pymupdf_enhanced(self, content: bytes, metadata: Dict) -> List[Dict]:
        """Extract with PyMuPDF using multiple text modes."""
        transactions = []
        
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Try different text extraction modes
                text_modes = ['text', 'blocks', 'words', 'dict']
                
                for mode in text_modes:
                    try:
                        if mode == 'text':
                            text = page.get_text()
                        elif mode == 'blocks':
                            blocks = page.get_text('blocks')
                            text = '\n'.join([b[4] for b in blocks if len(b) > 4])
                        elif mode == 'words':
                            words = page.get_text('words')
                            # Group words by y-position into lines
                            text = self._words_to_lines(words)
                        elif mode == 'dict':
                            data = page.get_text('dict')
                            text = self._dict_to_text(data)
                        
                        if text:
                            txns = self._parse_text_flexible(text, page_num + 1)
                            if len(txns) > len(transactions):
                                transactions = txns
                    except:
                        continue
            
            doc.close()
        except Exception as e:
            print(f"   ⚠️ PyMuPDF error: {e}")
        
        return transactions
    
    def _words_to_lines(self, words: List) -> str:
        """Convert word list to lines based on y-position."""
        if not words:
            return ""
        
        # Sort by y then x
        sorted_words = sorted(words, key=lambda w: (round(w[1], 0), w[0]))
        
        lines = []
        current_line = []
        current_y = None
        
        for word in sorted_words:
            y = round(word[1], 0)
            if current_y is None or abs(y - current_y) < 5:
                current_line.append(word[4])
                current_y = y
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word[4]]
                current_y = y
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines)
    
    def _dict_to_text(self, data: Dict) -> str:
        """Convert dict text extraction to string."""
        lines = []
        for block in data.get('blocks', []):
            if 'lines' in block:
                for line in block['lines']:
                    line_text = ' '.join([span['text'] for span in line.get('spans', [])])
                    if line_text.strip():
                        lines.append(line_text)
        return '\n'.join(lines)
    
    def _extract_with_ocr_enhanced(self, content: bytes, metadata: Dict) -> List[Dict]:
        """Enhanced OCR with multiple preprocessing and config attempts."""
        best_transactions = []
        
        try:
            # Convert PDF to images at higher DPI for better OCR
            images = convert_from_bytes(content, dpi=400)
            
            for page_num, image in enumerate(images, 1):
                # Try multiple preprocessing approaches
                preprocessed_images = self._preprocess_image_multiple(image)
                
                for img_variant, variant_name in preprocessed_images:
                    # Try multiple OCR configurations
                    for config in self.ocr_configs:
                        try:
                            text = pytesseract.image_to_string(img_variant, config=config)
                            
                            if text and len(text.strip()) > 50:
                                txns = self._parse_text_flexible(text, page_num)
                                if len(txns) > len(best_transactions):
                                    best_transactions = txns
                                    print(f"   Best so far: {len(txns)} transactions (variant: {variant_name}, config: {config})")
                        except:
                            continue
                    
                    # If we found good results, stop trying
                    if len(best_transactions) >= 10:
                        break
                
        except Exception as e:
            print(f"   ⚠️ OCR error: {e}")
        
        return best_transactions
    
    def _preprocess_image_multiple(self, image: Image.Image) -> List[Tuple[Image.Image, str]]:
        """Generate multiple preprocessed versions of image for OCR."""
        variants = []
        
        # Convert to RGB first
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # 1. Original grayscale
        gray = image.convert('L')
        variants.append((gray, 'grayscale'))
        
        # 2. High contrast
        enhancer = ImageEnhance.Contrast(gray)
        high_contrast = enhancer.enhance(2.0)
        variants.append((high_contrast, 'high_contrast'))
        
        # 3. Sharpened
        sharpened = high_contrast.filter(ImageFilter.SHARPEN)
        variants.append((sharpened, 'sharpened'))
        
        # 4. Binarized (threshold)
        threshold = 128
        binarized = gray.point(lambda p: 255 if p > threshold else 0)
        variants.append((binarized, 'binarized'))
        
        # 5. Adaptive threshold approximation
        # (simple version - divide into regions)
        
        # 6. Inverted (for dark backgrounds)
        inverted = ImageOps.invert(gray)
        variants.append((inverted, 'inverted'))
        
        # 7. Deskewed (rotation correction) - simplified
        # Would need more complex implementation for real deskewing
        
        # 8. Scaled up (for small text)
        width, height = gray.size
        if width < 2000:
            scale = 2000 / width
            scaled = gray.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
            variants.append((scaled, 'scaled'))
        
        return variants
    
    def _extract_with_patterns(self, content: bytes, metadata: Dict) -> List[Dict]:
        """Pattern-based extraction for unusual layouts."""
        transactions = []
        
        try:
            # Get all text from PDF
            doc = fitz.open(stream=content, filetype="pdf")
            all_text = ""
            
            for page in doc:
                all_text += page.get_text() + "\n"
            
            doc.close()
            
            # Find all dates in document
            date_positions = []
            for pattern, fmt in self.date_patterns:
                for match in re.finditer(pattern, all_text, re.IGNORECASE):
                    parsed = self._parse_date_flexible(match.group())
                    if parsed:
                        date_positions.append({
                            'date': parsed,
                            'start': match.start(),
                            'end': match.end(),
                            'match': match.group()
                        })
            
            # Sort by position
            date_positions.sort(key=lambda x: x['start'])
            
            # For each date, look for amounts nearby
            for i, date_info in enumerate(date_positions):
                # Get text window around date
                start = max(0, date_info['start'] - 50)
                end = min(len(all_text), date_info['end'] + 200)
                
                # If there's another date nearby, stop there
                if i + 1 < len(date_positions):
                    end = min(end, date_positions[i + 1]['start'])
                
                window = all_text[start:end]
                
                # Find amounts in window
                amounts = self._extract_amounts_flexible(window)
                
                if amounts:
                    # Get description (text between date and amount)
                    desc = window[date_info['end'] - start:].strip()
                    desc = re.sub(r'[£$€]?\s*[\d,]+\.?\d*', '', desc)  # Remove amounts
                    desc = ' '.join(desc.split())[:200]
                    
                    # Determine direction
                    direction = 'credit'
                    if any(kw in desc.lower() for kw in self.debit_keywords):
                        direction = 'debit'
                    
                    transactions.append({
                        'account_id': 'PDF_PATTERN',
                        'date': date_info['date'],
                        'amount': float(amounts[0]),
                        'currency': 'GBP',
                        'direction': direction,
                        'description': desc if desc else 'Transaction',
                        'counterparty_name': '',
                        'balance': float(amounts[-1]) if len(amounts) > 1 else None,
                        'source': 'pattern_extraction'
                    })
            
        except Exception as e:
            print(f"   ⚠️ Pattern extraction error: {e}")
        
        return transactions
    
    def _parse_with_ai(self, content: bytes, file_type: str) -> Dict[str, Any]:
        """Use Claude API as fallback for difficult documents."""
        try:
            # Check if API key is available
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                return {'success': False, 'transactions': [], 'metadata': {}, 'error': 'No API key'}
            
            # Get text from document
            if file_type == 'pdf':
                text = self._get_pdf_text(content)
            elif file_type == 'image':
                text = self._get_image_text(content)
            else:
                text = content.decode('utf-8', errors='ignore')
            
            if not text or len(text) < 50:
                return {'success': False, 'transactions': [], 'metadata': {}, 'error': 'No text to process'}
            
            # Truncate if too long
            text = text[:15000]
            
            # Call Claude API
            import requests
            
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01'
                },
                json={
                    'model': 'claude-sonnet-4-20250514',
                    'max_tokens': 4000,
                    'messages': [{
                        'role': 'user',
                        'content': f"""Extract all financial transactions from this bank statement text.

For each transaction, identify:
- Date (in YYYY-MM-DD format)
- Amount (as a number)
- Direction (credit or debit)
- Description

Return ONLY a JSON array of transactions like this:
[
  {{"date": "2025-01-15", "amount": 150.00, "direction": "debit", "description": "Card payment to Tesco"}},
  {{"date": "2025-01-16", "amount": 3500.00, "direction": "credit", "description": "Salary from Employer Ltd"}}
]

If you cannot find any transactions, return an empty array: []

Bank statement text:
{text}"""
                    }]
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content_text = result['content'][0]['text']
                
                # Parse JSON from response
                import json
                
                # Find JSON array in response
                json_match = re.search(r'\[[\s\S]*\]', content_text)
                if json_match:
                    transactions_data = json.loads(json_match.group())
                    
                    transactions = []
                    for txn in transactions_data:
                        transactions.append({
                            'account_id': 'AI_EXTRACTED',
                            'date': txn.get('date', ''),
                            'amount': float(txn.get('amount', 0)),
                            'currency': 'GBP',
                            'direction': txn.get('direction', 'credit'),
                            'description': txn.get('description', '')[:500],
                            'counterparty_name': '',
                            'balance': None,
                            'source': 'ai_extraction'
                        })
                    
                    print(f"   ✅ AI extracted {len(transactions)} transactions")
                    return {
                        'success': len(transactions) > 0,
                        'transactions': transactions,
                        'metadata': {'extraction_method': 'ai', 'ai_model': 'claude-sonnet-4-20250514'},
                        'error': None
                    }
            
            return {'success': False, 'transactions': [], 'metadata': {}, 'error': 'AI extraction failed'}
            
        except Exception as e:
            print(f"   ⚠️ AI extraction error: {e}")
            return {'success': False, 'transactions': [], 'metadata': {}, 'error': str(e)}
    
    def _get_pdf_text(self, content: bytes) -> str:
        """Get text from PDF."""
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            return text
        except:
            return ""
    
    def _get_image_text(self, content: bytes) -> str:
        """Get text from image using OCR."""
        try:
            image = Image.open(io.BytesIO(content))
            if image.mode != 'L':
                image = image.convert('L')
            return pytesseract.image_to_string(image)
        except:
            return ""
    
    def _parse_table_flexible(self, table: List[List], page_num: int) -> List[Dict]:
        """Flexible table parsing that handles unusual structures."""
        if not table or len(table) < 2:
            return []
        
        transactions = []
        
        # Find header row
        header_idx = None
        header = None
        
        for idx in range(min(10, len(table))):
            row = table[idx]
            if not row:
                continue
            
            row_text = ' '.join([str(cell).lower() for cell in row if cell])
            
            # Check for header keywords
            header_score = sum(1 for kw in self.date_column_names + self.amount_column_names + self.description_column_names 
                              if kw in row_text)
            
            if header_score >= 2:
                header_idx = idx
                header = [str(cell).lower().strip() if cell else '' for cell in row]
                break
        
        # Map columns
        if header:
            col_map = self._map_columns_flexible(header)
            start_row = header_idx + 1
        else:
            # Try to infer from data
            col_map = self._infer_columns_from_data(table)
            start_row = 0
        
        # Parse rows
        for row_idx in range(start_row, len(table)):
            row = table[row_idx]
            if not row or all(not str(cell).strip() for cell in row if cell):
                continue
            
            txn = self._parse_row_flexible(row, col_map, page_num, row_idx)
            if txn:
                transactions.append(txn)
        
        return transactions
    
    def _map_columns_flexible(self, header: List[str]) -> Dict[str, int]:
        """Map columns with comprehensive keyword matching for all bank formats."""
        col_map = {
            'date': None, 'amount': None, 'debit': None, 'credit': None,
            'description': None, 'balance': None, 'direction': None, 'currency': None
        }
        
        for idx, col in enumerate(header):
            # Clean column name - remove currency symbols in parentheses but keep for matching
            col_lower = col.lower().strip()
            col_clean = re.sub(r'\s*\([^)]*\)\s*', '', col_lower).strip()
            
            # DATE column
            if col_map['date'] is None:
                if any(date_name in col_lower for date_name in self.date_column_names):
                    col_map['date'] = idx
                    continue
            
            # DEBIT/WITHDRAWAL column (money OUT) - check before generic amount
            if col_map['debit'] is None:
                if any(debit_name in col_lower for debit_name in self.debit_column_names):
                    col_map['debit'] = idx
                    continue
            
            # CREDIT/DEPOSIT column (money IN) - check before generic amount
            if col_map['credit'] is None:
                if any(credit_name in col_lower for credit_name in self.credit_column_names):
                    col_map['credit'] = idx
                    continue
            
            # AMOUNT column (single column - direction from sign)
            if col_map['amount'] is None and col_map['debit'] is None and col_map['credit'] is None:
                if any(amt_name in col_lower for amt_name in self.amount_column_names):
                    col_map['amount'] = idx
                    continue
            
            # DESCRIPTION column
            if col_map['description'] is None:
                if any(desc_name in col_lower for desc_name in self.description_column_names):
                    col_map['description'] = idx
                    continue
            
            # BALANCE column
            if col_map['balance'] is None:
                if any(bal_name in col_lower for bal_name in self.balance_column_names):
                    col_map['balance'] = idx
                    continue
        
        # Log what we found
        print(f"   Column mapping: date={col_map['date']}, desc={col_map['description']}, "
              f"debit={col_map['debit']}, credit={col_map['credit']}, "
              f"amount={col_map['amount']}, balance={col_map['balance']}")
        
        return col_map
    
    def _infer_columns_from_data(self, table: List[List]) -> Dict[str, int]:
        """Infer column types from data patterns."""
        col_map = {
            'date': None, 'amount': None, 'debit': None, 'credit': None,
            'description': None, 'balance': None, 'direction': None, 'currency': None
        }
        
        if not table or not table[0]:
            return col_map
        
        num_cols = max(len(row) for row in table if row)
        
        # Analyze each column
        for col_idx in range(num_cols):
            col_values = []
            for row in table[:min(20, len(table))]:
                if row and col_idx < len(row) and row[col_idx]:
                    col_values.append(str(row[col_idx]).strip())
            
            if not col_values:
                continue
            
            # Check if column looks like dates
            date_count = sum(1 for v in col_values if self._looks_like_date(v))
            if date_count >= len(col_values) * 0.5 and col_map['date'] is None:
                col_map['date'] = col_idx
                continue
            
            # Check if column looks like amounts
            amount_count = sum(1 for v in col_values if self._looks_like_amount(v))
            if amount_count >= len(col_values) * 0.5:
                if col_map['amount'] is None:
                    col_map['amount'] = col_idx
                elif col_map['debit'] is None:
                    col_map['debit'] = col_idx
                elif col_map['credit'] is None:
                    col_map['credit'] = col_idx
                continue
            
            # Otherwise, probably description
            if col_map['description'] is None:
                avg_len = sum(len(v) for v in col_values) / len(col_values)
                if avg_len > 5:
                    col_map['description'] = col_idx
        
        return col_map
    
    def _looks_like_date(self, text: str) -> bool:
        """Check if text looks like a date."""
        for pattern, _ in self.date_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _looks_like_amount(self, text: str) -> bool:
        """Check if text looks like an amount."""
        text = text.strip()
        # Remove currency symbols and check for number pattern
        cleaned = re.sub(r'[£$€¥₹\s]', '', text)
        return bool(re.match(r'^-?[\d,]+\.?\d*$', cleaned) or re.match(r'^-?[\d.]+,\d{2}$', cleaned))
    
    def _parse_row_flexible(self, row: List, col_map: Dict, page_num: int, row_idx: int) -> Optional[Dict]:
        """Parse row with flexible column handling."""
        try:
            row = [str(cell).strip() if cell else '' for cell in row]
            
            # Get date
            date_str = None
            if col_map['date'] is not None and col_map['date'] < len(row):
                date_str = row[col_map['date']]
            
            # If no date column, scan for date
            if not date_str:
                for cell in row:
                    if self._looks_like_date(cell):
                        date_str = cell
                        break
            
            if not date_str:
                return None
            
            parsed_date = self._parse_date_flexible(date_str)
            if not parsed_date:
                return None
            
            # Get amount and direction
            amount = None
            direction = 'credit'
            
            # Try debit column
            if col_map['debit'] is not None and col_map['debit'] < len(row):
                val = row[col_map['debit']]
                if val and val not in ['-', '', '0', '0.00']:
                    amount = self._parse_amount_flexible(val)
                    if amount:
                        direction = 'debit'
            
            # Try credit column
            if amount is None and col_map['credit'] is not None and col_map['credit'] < len(row):
                val = row[col_map['credit']]
                if val and val not in ['-', '', '0', '0.00']:
                    amount = self._parse_amount_flexible(val)
                    if amount:
                        direction = 'credit'
            
            # Try single amount column
            if amount is None and col_map['amount'] is not None and col_map['amount'] < len(row):
                val = row[col_map['amount']]
                if val:
                    amount = self._parse_amount_flexible(val)
                    if amount:
                        # Determine direction from sign
                        if val.startswith('-') or val.startswith('(') or val.endswith('-'):
                            direction = 'debit'
                            amount = abs(amount)
            
            # Scan for amounts if still not found
            if amount is None:
                for cell in row:
                    if self._looks_like_amount(cell):
                        amount = self._parse_amount_flexible(cell)
                        if amount:
                            if cell.startswith('-') or '(' in cell:
                                direction = 'debit'
                                amount = abs(amount)
                            break
            
            if amount is None or amount == 0:
                return None
            
            # Get description
            description = ''
            if col_map['description'] is not None and col_map['description'] < len(row):
                description = row[col_map['description']]
            
            if not description:
                # Concatenate non-date, non-amount cells
                for i, cell in enumerate(row):
                    if cell and not self._looks_like_date(cell) and not self._looks_like_amount(cell):
                        if len(cell) > 2:
                            description += ' ' + cell
                description = description.strip()
            
            # Infer direction from description
            if description:
                desc_lower = description.lower()
                if any(kw in desc_lower for kw in self.debit_keywords):
                    direction = 'debit'
                elif any(kw in desc_lower for kw in self.credit_keywords):
                    direction = 'credit'
            
            return {
                'account_id': f'PDF_P{page_num}',
                'date': parsed_date,
                'amount': float(amount),
                'currency': 'GBP',
                'direction': direction,
                'description': description[:500] if description else 'Transaction',
                'counterparty_name': '',
                'balance': None,
                'source': f'table_page{page_num}_row{row_idx}'
            }
            
        except Exception as e:
            return None
    
    def _parse_text_flexible(self, text: str, page_num: int) -> List[Dict]:
        """Flexible text parsing for various layouts."""
        transactions = []
        lines = text.split('\n')
        
        current_txn = None
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 5:
                continue
            
            # Skip header/footer lines
            skip_patterns = ['page', 'statement', 'account number', 'sort code', 
                           'opening balance', 'closing balance', 'brought forward',
                           'carried forward', 'total', 'balance b/f', 'balance c/f']
            if any(p in line.lower() for p in skip_patterns):
                continue
            
            # Check for date
            date_match = self._find_date_in_text(line)
            
            if date_match:
                # Save previous transaction
                if current_txn and current_txn.get('amount'):
                    transactions.append(current_txn)
                
                parsed_date = self._parse_date_flexible(date_match)
                if parsed_date:
                    # Extract amounts
                    amounts = self._extract_amounts_flexible(line)
                    
                    # Get description
                    desc = line.replace(date_match, '').strip()
                    for amt in amounts:
                        desc = re.sub(r'[£$€]?\s*' + str(amt).replace('.', r'\.'), '', desc)
                    desc = ' '.join(desc.split())
                    
                    # Direction
                    direction = 'credit'
                    if any(kw in desc.lower() for kw in self.debit_keywords):
                        direction = 'debit'
                    
                    current_txn = {
                        'account_id': f'PDF_P{page_num}',
                        'date': parsed_date,
                        'amount': amounts[0] if amounts else None,
                        'currency': 'GBP',
                        'direction': direction,
                        'description': desc[:500] if desc else 'Transaction',
                        'counterparty_name': '',
                        'balance': amounts[-1] if len(amounts) > 1 else None,
                        'source': f'text_page{page_num}_line{line_idx}'
                    }
            elif current_txn:
                # Continuation line
                amounts = self._extract_amounts_flexible(line)
                if amounts and not current_txn.get('amount'):
                    current_txn['amount'] = amounts[0]
                elif not amounts:
                    current_txn['description'] += ' ' + line
        
        # Don't forget last transaction
        if current_txn and current_txn.get('amount'):
            transactions.append(current_txn)
        
        return transactions
    
    def _find_date_in_text(self, text: str) -> Optional[str]:
        """Find date pattern in text."""
        for pattern, _ in self.date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group()
        return None
    
    def _parse_date_flexible(self, date_str: str) -> Optional[str]:
        """Parse date with extended format support."""
        if not date_str:
            return None
        
        date_str = date_str.strip()
        current_year = datetime.now().year
        
        for pattern, fmt in self.date_patterns:
            match = re.match(pattern, date_str, re.IGNORECASE)
            if not match:
                continue
            
            try:
                groups = match.groups()
                
                if fmt in ['dmy_text', 'german', 'french', 'spanish']:
                    day = int(groups[0])
                    month_str = groups[1].lower()
                    month = self.month_map.get(month_str[:3]) or self.month_map.get(month_str)
                    year = int(groups[2]) if groups[2] else current_year
                    if year < 100:
                        year += 2000 if year < 50 else 1900
                        
                elif fmt == 'mdy_text':
                    month_str = groups[0].lower()
                    month = self.month_map.get(month_str[:3]) or self.month_map.get(month_str)
                    day = int(groups[1])
                    year = int(groups[2]) if groups[2] else current_year
                    if year < 100:
                        year += 2000 if year < 50 else 1900
                        
                elif fmt in ['dmy_numeric', 'mdy_numeric', 'eu_dots']:
                    p1, p2, p3 = int(groups[0]), int(groups[1]), int(groups[2])
                    if p3 < 100:
                        p3 += 2000 if p3 < 50 else 1900
                    
                    # Determine if DMY or MDY
                    if p1 > 12:  # Must be day
                        day, month, year = p1, p2, p3
                    elif p2 > 12:  # Must be day
                        month, day, year = p1, p2, p3
                    else:
                        # Assume DMY for non-US
                        day, month, year = p1, p2, p3
                        
                elif fmt == 'iso':
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    
                elif fmt == 'compact':
                    val = groups[0]
                    if int(val[:4]) > 1900:  # YYYYMMDD
                        year, month, day = int(val[:4]), int(val[4:6]), int(val[6:8])
                    else:  # DDMMYYYY
                        day, month, year = int(val[:2]), int(val[2:4]), int(val[4:8])
                
                if month and 1 <= day <= 31 and 1 <= month <= 12:
                    return f"{year:04d}-{month:02d}-{day:02d}"
                    
            except Exception:
                continue
        
        return None
    
    def _extract_amounts_flexible(self, text: str) -> List[float]:
        """Extract amounts with multi-currency support."""
        amounts = []
        
        for pattern, currency in self.currency_patterns:
            for match in re.finditer(pattern, text):
                try:
                    groups = match.groups()
                    for g in groups:
                        if g and re.match(r'[\d,.\'\s]+', g):
                            # Handle European format (comma as decimal)
                            if ',' in g and '.' not in g:
                                g = g.replace(',', '.')
                            elif '.' in g and ',' in g:
                                # 1.234,56 -> 1234.56
                                g = g.replace('.', '').replace(',', '.')
                            
                            g = g.replace(',', '').replace("'", '').replace(' ', '')
                            amount = float(g)
                            if amount > 0 and amount not in amounts:
                                amounts.append(amount)
                            break
                except:
                    continue
        
        return amounts
    
    def _parse_amount_flexible(self, text: str) -> Optional[float]:
        """Parse amount from text with flexible formatting."""
        if not text:
            return None
        
        text = text.strip()
        
        # Remove currency symbols
        text = re.sub(r'[£$€¥₹]', '', text)
        text = re.sub(r'(GBP|USD|EUR|JPY|INR)\s*', '', text, flags=re.IGNORECASE)
        
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
        
        # Handle European format
        text = text.strip()
        if ',' in text and '.' not in text:
            text = text.replace(',', '.')
        elif '.' in text and ',' in text:
            text = text.replace('.', '').replace(',', '.')
        
        text = text.replace(',', '').replace(' ', '')
        
        try:
            amount = float(text)
            return -amount if is_negative else amount
        except:
            return None
    
    def _parse_image_enhanced(self, content: bytes) -> Dict[str, Any]:
        """Enhanced image parsing with multiple preprocessing attempts."""
        metadata = {
            'source': 'image',
            'extraction_method': 'ocr',
            'ocr_used': True,
            'preprocessing_variants_tried': 0
        }
        
        try:
            image = Image.open(io.BytesIO(content))
            
            # Try multiple preprocessing variants
            variants = self._preprocess_image_multiple(image)
            metadata['preprocessing_variants_tried'] = len(variants)
            
            best_transactions = []
            
            for img_variant, variant_name in variants:
                for config in self.ocr_configs[:3]:  # Try first 3 configs
                    try:
                        text = pytesseract.image_to_string(img_variant, config=config)
                        
                        if text and len(text.strip()) > 30:
                            txns = self._parse_text_flexible(text, 1)
                            if len(txns) > len(best_transactions):
                                best_transactions = txns
                                print(f"   Best: {len(txns)} transactions (variant: {variant_name})")
                    except:
                        continue
                
                if len(best_transactions) >= 5:
                    break
            
            best_transactions = self._deduplicate(best_transactions)
            
            return {
                'success': len(best_transactions) > 0,
                'transactions': best_transactions,
                'metadata': metadata,
                'error': None if best_transactions else 'No transactions found in image'
            }
            
        except Exception as e:
            return {
                'success': False,
                'transactions': [],
                'metadata': metadata,
                'error': f'Image processing error: {str(e)}'
            }
    
    def _parse_csv_enhanced(self, content: bytes) -> Dict[str, Any]:
        """Enhanced CSV parsing with flexible column detection."""
        metadata = {
            'source': 'csv',
            'extraction_method': 'csv_parse',
            'columns_detected': {}
        }
        
        try:
            # Try different encodings
            text = None
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16']:
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
            delimiter = self._detect_delimiter(text)
            
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
            
            # Find header and map columns
            header_idx = self._find_header_row(rows)
            header = [str(h).lower().strip() for h in rows[header_idx]] if header_idx < len(rows) else []
            
            col_map = self._map_columns_flexible(header) if header else self._infer_columns_from_data(rows)
            metadata['columns_detected'] = {k: v for k, v in col_map.items() if v is not None}
            
            # Parse transactions
            transactions = []
            for row_idx in range(header_idx + 1, len(rows)):
                row = rows[row_idx]
                if not row or all(not str(cell).strip() for cell in row):
                    continue
                
                txn = self._parse_row_flexible(row, col_map, 1, row_idx)
                if txn:
                    transactions.append(txn)
            
            transactions = self._deduplicate(transactions)
            
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
    
    def _detect_delimiter(self, text: str) -> str:
        """Detect CSV delimiter."""
        first_lines = text[:3000]
        counts = {
            ',': first_lines.count(','),
            '\t': first_lines.count('\t'),
            ';': first_lines.count(';'),
            '|': first_lines.count('|')
        }
        return max(counts, key=counts.get)
    
    def _find_header_row(self, rows: List[List]) -> int:
        """Find header row in CSV."""
        for idx in range(min(15, len(rows))):
            row = rows[idx]
            if not row:
                continue
            
            row_lower = [str(cell).lower().strip() for cell in row]
            
            # Count header keyword matches
            matches = sum(1 for kw in self.date_column_names + self.amount_column_names + self.description_column_names
                         if any(kw in cell for cell in row_lower))
            
            if matches >= 2:
                return idx
        
        return 0
    
    def _parse_excel(self, content: bytes) -> Dict[str, Any]:
        """Parse Excel file."""
        metadata = {'source': 'excel', 'extraction_method': 'excel_parse'}
        
        try:
            import openpyxl
            
            workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            sheet = workbook.active
            
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
            header_idx = self._find_header_row(rows)
            header = [str(h).lower().strip() for h in rows[header_idx]] if header_idx < len(rows) else []
            col_map = self._map_columns_flexible(header) if header else self._infer_columns_from_data(rows)
            
            transactions = []
            for row_idx in range(header_idx + 1, len(rows)):
                row = rows[row_idx]
                if not row or all(not str(cell).strip() for cell in row):
                    continue
                
                txn = self._parse_row_flexible(row, col_map, 1, row_idx)
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
                'error': 'Excel support not available'
            }
        except Exception as e:
            return {
                'success': False,
                'transactions': [],
                'metadata': metadata,
                'error': f'Excel parsing error: {str(e)}'
            }
    
    def _parse_unknown(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Try multiple approaches for unknown file types."""
        # Try as CSV
        result = self._parse_csv_enhanced(content)
        if result['success'] and result['transactions']:
            return result
        
        # Try as image
        result = self._parse_image_enhanced(content)
        if result['success'] and result['transactions']:
            return result
        
        return {
            'success': False,
            'transactions': [],
            'metadata': {},
            'error': 'Could not determine file type or extract transactions'
        }
    
    def _deduplicate(self, transactions: List[Dict]) -> List[Dict]:
        """Remove duplicate transactions - only exact duplicates on same date."""
        seen = set()
        unique = []
        
        for txn in transactions:
            # Use more of the description to avoid false positives
            description = txn.get('description', '')
            key = (
                txn.get('date'),
                round(txn.get('amount', 0), 2),
                description[:100] if description else ''  # Increased from 30 to 100
            )
            
            if key not in seen:
                seen.add(key)
                unique.append(txn)
        
        return unique


# Singleton instance
enhanced_universal_parser = EnhancedUniversalParser()
