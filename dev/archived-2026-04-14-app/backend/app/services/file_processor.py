"""
File Processing Service for SoF Assessment
Handles JSON, CSV, and PDF uploads

100% LOCAL - No external API calls
"""
from typing import Dict, List, Any, Optional, Tuple
import asyncio
import json
import csv
import io
import re
import hashlib
import uuid
from datetime import datetime
from decimal import Decimal
import pdfplumber
import fitz  # PyMuPDF
from fastapi import UploadFile


class FileProcessor:
    """
    Process uploaded files for SoF assessment
    Supports: JSON (client info), CSV (bank statements), PDF (statements + docs),
              Images/Screenshots (PNG, JPG, etc.)
    """
    
    def __init__(self):
        self.supported_types = {
            'json': ['application/json', 'text/json'],
            'csv': ['text/csv', 'application/csv', 'text/plain'],
            'pdf': ['application/pdf'],
            'image': ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/bmp', 'image/webp', 'image/tiff'],
            'excel': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                      'application/vnd.ms-excel']
        }

    def _generate_transaction_id(self, account_id: str = "", date: str = "", amount: float = 0, file_hash: str = None) -> str:
        """
        Generate a unique, stateless transaction ID using UUID.
        Format: TXN-{uuid_hex_short}

        Thread-safe: no mutable instance state is used.
        """
        return f"TXN-{uuid.uuid4().hex[:12].upper()}"
    
    def _get_file_hash(self, content: bytes) -> str:
        """Generate a short hash of file content for ID generation"""
        return hashlib.md5(content).hexdigest()[:8]
    
    def _process_sync(self, content: bytes, file_type: str, filename: str = '', content_type: str = '') -> Dict[str, Any]:
        """
        Synchronous dispatcher — runs in a thread via run_in_executor
        so that blocking PDF/OCR work does not stall the event loop.
        """
        if file_type == 'json':
            return self.process_json(content)
        elif file_type == 'csv':
            return self.process_csv_bank_statement(content)
        elif file_type == 'pdf':
            # Try as bank statement first, fall back to document
            result = self.process_pdf_bank_statement(content)
            if not result['success']:
                result = self.process_pdf_document(content)
            return result
        elif file_type == 'pdf_document':
            print(f"📄 Processing as supporting document: {filename}")
            return self.process_pdf_document(content)
        elif file_type == 'image':
            return self.process_image_bank_statement(content, filename)
        elif file_type == 'excel':
            return self.process_excel_bank_statement(content)
        elif file_type == 'auto':
            return self.process_auto(content, filename, content_type)
        else:
            return self.process_auto(content, filename, content_type)

    async def process_upload(
        self,
        file: UploadFile,
        file_type: str
    ) -> Dict[str, Any]:
        """
        Main entry point for file processing.
        Returns: {"success": bool, "data": Any, "error": str}

        Validates file size and MIME type against application settings
        before processing.  Blocking work (PDF parsing, OCR, CSV parsing)
        is offloaded to a thread via asyncio.run_in_executor so the event
        loop stays free.
        """
        from app.core.config import settings

        try:
            content = await file.read()
            filename = file.filename or ''
            content_type = file.content_type or ''

            # ---- File size validation ----
            max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
            if len(content) > max_bytes:
                return {
                    "success": False,
                    "error": (
                        f"File too large: {len(content) / (1024 * 1024):.1f} MB. "
                        f"Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB."
                    ),
                }

            # ---- MIME type validation ----
            # Build the full set of allowed MIME types from settings + processor
            allowed_mime_types: set = set(settings.ALLOWED_DOCUMENT_TYPES)
            for type_list in self.supported_types.values():
                allowed_mime_types.update(type_list)

            if content_type and content_type not in allowed_mime_types:
                return {
                    "success": False,
                    "error": (
                        f"File type '{content_type}' is not allowed. "
                        f"Accepted types: PDF, CSV, JSON, PNG, JPEG, Excel."
                    ),
                }

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,  # default ThreadPoolExecutor
                self._process_sync,
                content,
                file_type,
                filename,
                content_type,
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"File processing error: {str(e)}"
            }
    
    def process_auto(self, content: bytes, filename: str, content_type: str) -> Dict[str, Any]:
        """
        Auto-detect file type and process accordingly using enhanced parser.
        Now generates unique transaction IDs.
        """
        try:
            from app.services.enhanced_universal_parser import enhanced_universal_parser
            
            # Generate file hash for unique transaction IDs
            file_hash = self._get_file_hash(content)
            # file_hash used for dedup, no mutable counter state needed
            
            print(f"\n🔄 Auto-detecting file type for: {filename}")
            result = enhanced_universal_parser.parse(content, filename=filename, content_type=content_type)
            
            if result['success'] and result['transactions']:
                # Add transaction IDs
                for txn in result['transactions']:
                    if not txn.get('id'):
                        txn['id'] = self._generate_transaction_id(
                            txn.get('account_id', 'Unknown'),
                            txn.get('date', ''),
                            txn.get('amount', 0),
                            file_hash
                        )
                        txn['transaction_id'] = txn['id']
                
                print(f"✅ Auto-detection succeeded: {len(result['transactions'])} transactions with unique IDs")
                return {
                    "success": True,
                    "data": {
                        "bank_statements": result['transactions'],
                        "transaction_count": len(result['transactions'])
                    },
                    "file_type": result['metadata'].get('source', 'auto'),
                    "metadata": result['metadata']
                }
            else:
                return {
                    "success": False,
                    "error": result.get('error', 'Could not extract transactions from file')
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Auto-processing error: {str(e)}"
            }
    
    def process_image_bank_statement(self, content: bytes, filename: str = '') -> Dict[str, Any]:
        """
        Process image file (screenshot of bank statement) using enhanced OCR.
        Uses multiple preprocessing techniques for poor quality images.
        Now generates unique transaction IDs.
        """
        try:
            from app.services.enhanced_universal_parser import enhanced_universal_parser
            
            # Generate file hash for unique transaction IDs
            file_hash = self._get_file_hash(content)
            # file_hash used for dedup, no mutable counter state needed
            
            print(f"\n🖼️ Processing image: {filename}")
            result = enhanced_universal_parser.parse(content, filename=filename, content_type='image/png')
            
            if result['success'] and result['transactions']:
                # Add transaction IDs
                for txn in result['transactions']:
                    if not txn.get('id'):
                        txn['id'] = self._generate_transaction_id(
                            txn.get('account_id', 'Image_Statement'),
                            txn.get('date', ''),
                            txn.get('amount', 0),
                            file_hash
                        )
                        txn['transaction_id'] = txn['id']
                
                print(f"✅ Image OCR extracted {len(result['transactions'])} transactions with unique IDs")
                print(f"   Preprocessing variants tried: {result['metadata'].get('preprocessing_variants_tried', 0)}")
                return {
                    "success": True,
                    "data": {
                        "bank_statements": result['transactions'],
                        "transaction_count": len(result['transactions'])
                    },
                    "file_type": "image_statement",
                    "metadata": result['metadata']
                }
            else:
                return {
                    "success": False,
                    "error": result.get('error', 'Could not extract transactions from image')
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Image processing error: {str(e)}"
            }
    
    def process_excel_bank_statement(self, content: bytes) -> Dict[str, Any]:
        """
        Process Excel file (bank statement export).
        Now generates unique transaction IDs.
        """
        try:
            from app.services.enhanced_universal_parser import enhanced_universal_parser
            
            # Generate file hash for unique transaction IDs
            file_hash = self._get_file_hash(content)
            # file_hash used for dedup, no mutable counter state needed
            
            print("\n📊 Processing Excel file")
            result = enhanced_universal_parser.parse(content, filename='statement.xlsx', content_type='application/vnd.ms-excel')
            
            if result['success'] and result['transactions']:
                # Add transaction IDs
                for txn in result['transactions']:
                    if not txn.get('id'):
                        txn['id'] = self._generate_transaction_id(
                            txn.get('account_id', 'Excel_Statement'),
                            txn.get('date', ''),
                            txn.get('amount', 0),
                            file_hash
                        )
                        txn['transaction_id'] = txn['id']
                
                print(f"✅ Excel parser extracted {len(result['transactions'])} transactions with unique IDs")
                return {
                    "success": True,
                    "data": {
                        "bank_statements": result['transactions'],
                        "transaction_count": len(result['transactions'])
                    },
                    "file_type": "excel_statement",
                    "metadata": result['metadata']
                }
            else:
                return {
                    "success": False,
                    "error": result.get('error', 'Could not extract transactions from Excel')
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Excel processing error: {str(e)}"
            }
    
    def process_json(self, content: bytes) -> Dict[str, Any]:
        """
        Process JSON file (client info, purchase details, SoF explanation)
        Expected structure:
        {
            "client_info": {...},
            "purchase": {...},
            "sof_explanation": "...",
            "flags": {...}
        }
        """
        try:
            data = json.loads(content.decode('utf-8'))
            
            # Validate required fields
            required = ['client_info', 'purchase', 'sof_explanation']
            missing = [f for f in required if f not in data]
            
            if missing:
                return {
                    "success": False,
                    "error": f"Missing required fields: {', '.join(missing)}"
                }
            
            # Validate client_info
            if 'client_risk_rating' not in data['client_info']:
                data['client_info']['client_risk_rating'] = 'medium'
            
            # Validate purchase
            purchase = data['purchase']
            if 'amount' not in purchase or 'currency' not in purchase:
                return {
                    "success": False,
                    "error": "Purchase must include 'amount' and 'currency'"
                }
            
            return {
                "success": True,
                "data": {
                    "client_info": data['client_info'],
                    "purchase": data['purchase'],
                    "sof_explanation": data['sof_explanation'],
                    "known_documents": data.get('known_documents', []),
                    "flags": data.get('flags', {}),
                    "constraints": data.get('constraints', {}),
                    "claims": data.get('claims', [])  # Support explicit claims array
                },
                "file_type": "json"
            }
        
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"JSON processing error: {str(e)}"
            }
    
    def process_csv_bank_statement(self, content: bytes) -> Dict[str, Any]:
        """
        Process CSV bank statement.
        First tries legacy parsing which reads columns directly (date, description, direction, amount, account_id).
        Falls back to enhanced universal parser for non-standard formats.
        """
        try:
            # Generate file hash for unique transaction IDs
            file_hash = self._get_file_hash(content)
            
            # First try legacy parsing which respects column names directly
            print("\n📋 Processing CSV - trying direct column parsing first...")
            legacy_result = self._legacy_csv_parse(content, file_hash)
            
            if legacy_result['success']:
                txn_count = len(legacy_result.get('data', {}).get('bank_statements', []))
                print(f"✅ Legacy CSV parser extracted {txn_count} transactions with direct column mapping")
                
                # Log first transaction to verify direction is being read
                if txn_count > 0:
                    first_txn = legacy_result['data']['bank_statements'][0]
                    print(f"   First transaction: {first_txn.get('id')} | {first_txn.get('date')} | {first_txn.get('direction')} | £{first_txn.get('amount')} | {first_txn.get('account_id')}")
                
                return legacy_result
            
            # If legacy parsing fails, try enhanced universal parser
            print("⚠️ Legacy parser failed, trying enhanced universal parser...")
            from app.services.enhanced_universal_parser import enhanced_universal_parser
            
            result = enhanced_universal_parser.parse(content, filename='statement.csv', content_type='text/csv')
            
            if result['success'] and result['transactions']:
                # Add transaction IDs to enhanced parser results
                for txn in result['transactions']:
                    if not txn.get('id'):
                        txn['id'] = self._generate_transaction_id(
                            txn.get('account_id', 'Unknown'),
                            txn.get('date', ''),
                            txn.get('amount', 0),
                            file_hash
                        )
                
                print(f"✅ Enhanced CSV parser extracted {len(result['transactions'])} transactions")
                print(f"   Columns detected: {result['metadata'].get('columns_detected', {})}")
                return {
                    "success": True,
                    "data": {
                        "bank_statements": result['transactions'],
                        "transaction_count": len(result['transactions'])
                    },
                    "file_type": "csv",
                    "metadata": result['metadata']
                }
            
            return {
                "success": False,
                "error": "Could not parse CSV file with either parser"
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"CSV processing error: {str(e)}"
            }
    
    def _legacy_csv_parse(self, content: bytes, file_hash: str = None) -> Dict[str, Any]:
        """
        Legacy CSV parsing for backwards compatibility.
        Expected columns: account_id, date, amount, currency, direction, description
        Optional: counterparty_name, balance
        
        Now generates unique transaction IDs for each row.
        """
        try:
            decoded = content.decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded))
            
            # Generate file hash if not provided
            if not file_hash:
                file_hash = self._get_file_hash(content)
            
            # Reset counter for this file
            # file_hash used for dedup, no mutable counter state needed
            
            # Check required columns
            required_cols = ['date', 'amount', 'direction', 'description']
            if not reader.fieldnames:
                print("❌ Legacy CSV parser: CSV file appears to be empty")
                return {
                    "success": False,
                    "error": "CSV file appears to be empty"
                }
            
            print(f"📋 Legacy CSV parser: Found columns: {reader.fieldnames}")
            
            missing_cols = [c for c in required_cols if c not in reader.fieldnames]
            if missing_cols:
                print(f"❌ Legacy CSV parser: Missing required columns: {missing_cols}")
                return {
                    "success": False,
                    "error": f"Missing required columns: {', '.join(missing_cols)}"
                }
            
            # Parse transactions
            transactions = []
            for row_num, row in enumerate(reader, start=2):
                try:
                    # Parse amount
                    amount_str = row['amount'].replace('£', '').replace(',', '').replace('$', '').strip()
                    amount = float(amount_str)
                    
                    # Parse date (try multiple formats)
                    date_str = row['date'].strip()
                    parsed_date = self._parse_date(date_str)
                    
                    # Direction (credit/debit) - READ DIRECTLY FROM COLUMN
                    direction = row['direction'].lower().strip()
                    if direction not in ['credit', 'debit']:
                        # Try to infer from amount
                        if amount > 0:
                            direction = 'credit'
                        else:
                            direction = 'debit'
                            amount = abs(amount)
                    
                    # Get account_id - READ DIRECTLY FROM COLUMN
                    account_id = row.get('account_id', 'Unknown')
                    
                    # Get country - check multiple possible column names (case-insensitive)
                    country_iso2 = None
                    for col_name in ['country', 'COUNTRY', 'Country', 'country_iso2', 'country_code']:
                        if col_name in row and row[col_name]:
                            country_val = row[col_name].strip().upper()
                            # Normalize common country codes
                            country_map = {
                                'UK': 'GB', 'UNITED KINGDOM': 'GB', 'ENGLAND': 'GB',
                                'USA': 'US', 'UNITED STATES': 'US', 'AMERICA': 'US',
                                'UAE': 'AE', 'UNITED ARAB EMIRATES': 'AE',
                                'IRAN': 'IR', 'ISLAMIC REPUBLIC OF IRAN': 'IR',
                            }
                            country_iso2 = country_map.get(country_val, country_val[:2] if len(country_val) >= 2 else country_val)
                            break
                    
                    # Get channel - check multiple possible column names
                    channel = None
                    for col_name in ['channel', 'CHANNEL', 'Channel', 'method', 'payment_method', 'type']:
                        if col_name in row and row[col_name]:
                            channel = row[col_name].strip()
                            break
                    
                    # Generate unique transaction ID
                    txn_id = self._generate_transaction_id(account_id, parsed_date, amount, file_hash)
                    
                    transactions.append({
                        "id": txn_id,
                        "transaction_id": txn_id,  # Duplicate for compatibility
                        "account_id": account_id,
                        "date": parsed_date,
                        "amount": amount,
                        "currency": row.get('currency', 'GBP'),
                        "direction": direction,
                        "description": row['description'].strip(),
                        "counterparty_name": row.get('counterparty_name', ''),
                        "balance": float(row['balance'].replace(',', '')) if row.get('balance') else None,
                        "country_iso2": country_iso2,
                        "channel": channel
                    })
                    
                    # Log first few transactions for debugging
                    if row_num <= 4:
                        print(f"   Row {row_num}: {txn_id} | {parsed_date} | {direction} | £{amount} | {account_id[:30]}... | Country: {country_iso2 or 'N/A'}")
                
                except Exception as e:
                    # Skip malformed rows but log warning
                    print(f"⚠️ Legacy CSV parser: Skipped row {row_num} due to error: {str(e)}")
                    continue
            
            if not transactions:
                print("❌ Legacy CSV parser: No valid transactions found in CSV")
                return {
                    "success": False,
                    "error": "No valid transactions found in CSV"
                }
            
            print(f"✅ Legacy CSV parser: Successfully parsed {len(transactions)} transactions with unique IDs")
            
            # Log unique account IDs found
            unique_accounts = set(t['account_id'] for t in transactions)
            print(f"   Unique accounts found: {unique_accounts}")
            
            # Log direction breakdown
            credits = sum(1 for t in transactions if t['direction'] == 'credit')
            debits = sum(1 for t in transactions if t['direction'] == 'debit')
            print(f"   Direction breakdown: {credits} credits, {debits} debits")
            
            return {
                "success": True,
                "data": {
                    "bank_statements": transactions,
                    "transaction_count": len(transactions)
                },
                "file_type": "csv"
            }
        
        except Exception as e:
            print(f"❌ Legacy CSV parser error: {str(e)}")
            return {
                "success": False,
                "error": f"CSV processing error: {str(e)}"
            }
    
    def process_pdf_bank_statement(self, content: bytes) -> Dict[str, Any]:
        """
        Process PDF bank statement
        Uses the enhanced universal parser that handles ANY format including:
        - Poor quality scans (with advanced OCR preprocessing)
        - Unusual table layouts
        - International formats (multi-language, multi-currency)
        - Encrypted PDFs (with detection)
        - AI fallback for really difficult documents
        
        Now generates unique transaction IDs for each transaction.
        """
        # Generate file hash for unique transaction IDs
        file_hash = self._get_file_hash(content)

        # Use the enhanced universal parser
        try:
            from app.services.enhanced_universal_parser import enhanced_universal_parser
            
            print("\n🌐 Using Enhanced Universal Financial Parser")
            result = enhanced_universal_parser.parse(content, filename='statement.pdf', content_type='application/pdf')
            
            if result['success'] and result['transactions']:
                # Debug: Show account info from first transaction
                first_txn = result['transactions'][0]
                print(f"   🏦 Account detected: {first_txn.get('account_id', 'N/A')} ({first_txn.get('account_type', 'N/A')}) at {first_txn.get('bank_name', 'N/A')}")
                print(f"   📋 Account info in metadata: {result['metadata'].get('account_info', {})}")
                
                # Add transaction IDs to each transaction
                for txn in result['transactions']:
                    if not txn.get('id'):
                        txn['id'] = self._generate_transaction_id(
                            txn.get('account_id', 'PDF_Statement'),
                            txn.get('date', ''),
                            txn.get('amount', 0),
                            file_hash
                        )
                        txn['transaction_id'] = txn['id']  # Duplicate for compatibility
                
                print(f"✅ Enhanced parser extracted {len(result['transactions'])} transactions with unique IDs")
                print(f"   Extraction method: {result['metadata'].get('extraction_method', 'Unknown')}")
                print(f"   Strategies tried: {result['metadata'].get('strategies_tried', [])}")
                print(f"   OCR used: {result['metadata'].get('ocr_used', False)}")
                return {
                    "success": True,
                    "data": {
                        "bank_statements": result['transactions'],
                        "transaction_count": len(result['transactions']),
                        "account_info": result['metadata'].get('account_info', {})
                    },
                    "file_type": "pdf_statement",
                    "metadata": result['metadata']
                }
            else:
                error_msg = result.get('error', 'No transactions found')
                print(f"⚠️ Enhanced parser: {error_msg}")
                
                # Check if it's an encryption issue
                if result['metadata'].get('encrypted'):
                    return {
                        "success": False,
                        "error": "PDF is password-protected. Please provide an unencrypted version."
                    }
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"⚠️ Enhanced parser error: {e}")
        
        # Fallback to original parser
        print("📄 Using legacy PDF parser")
        try:
            transactions = []
            debug_info = {
                "pages_processed": 0,
                "tables_found": 0,
                "text_lines_checked": 0,
                "transactions_extracted": 0
            }
            
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    debug_info["pages_processed"] += 1
                    
                    # METHOD 1: Try table extraction first
                    tables = page.extract_tables()
                    debug_info["tables_found"] += len(tables)
                    
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        
                        # Try to identify header row (case-insensitive)
                        header = [str(cell).lower() if cell else '' for cell in table[0]]
                        
                        # Find column indices (more flexible matching)
                        date_idx = self._find_column_index(header, ['date', 'transaction date', 'trans date', 'posted date', 'posted'])
                        amount_idx = self._find_column_index(header, ['amount', 'debit', 'credit', 'value', 'paid in', 'paid out', 'money in', 'money out'])
                        desc_idx = self._find_column_index(header, ['description', 'details', 'narrative', 'transaction', 'particulars', 'type'])
                        balance_idx = self._find_column_index(header, ['balance', 'running balance'])
                        
                        # Parse rows even if not all columns found
                        for row_idx, row in enumerate(table[1:]):
                            if not row:
                                continue
                            
                            try:
                                # Try to find date and amount in ANY cell
                                date_str = None
                                amount_str = None
                                description = ""
                                balance = None
                                
                                # If we know column indices, use them
                                if date_idx is not None and date_idx < len(row):
                                    date_str = str(row[date_idx]).strip()
                                if amount_idx is not None and amount_idx < len(row):
                                    amount_str = str(row[amount_idx]).strip()
                                if desc_idx is not None and desc_idx < len(row):
                                    description = str(row[desc_idx]).strip()
                                if balance_idx is not None and balance_idx < len(row):
                                    balance_str = str(row[balance_idx]).replace('£', '').replace(',', '').strip()
                                    try:
                                        balance = float(balance_str)
                                    except:
                                        pass
                                
                                # FALLBACK: Scan all cells for date and amount patterns
                                if not date_str or not amount_str:
                                    for cell in row:
                                        if cell:
                                            cell_str = str(cell).strip()
                                            # Check for date pattern
                                            if not date_str and re.search(r'\d{2}[-/]\d{2}[-/]\d{2,4}', cell_str):
                                                date_str = cell_str
                                            # Check for amount pattern
                                            if not amount_str and re.search(r'[£$€]?[\d,]+\.\d{2}', cell_str):
                                                amount_str = cell_str
                                            # Collect description if not a date or amount
                                            if not re.search(r'\d{2}[-/]\d{2}[-/]\d{2,4}', cell_str) and not re.search(r'[£$€]?[\d,]+\.\d{2}', cell_str):
                                                if len(cell_str) > 3:
                                                    description = description + " " + cell_str if description else cell_str
                                
                                if not date_str or not amount_str:
                                    continue
                                
                                if date_str.lower() in ['none', 'null', ''] or amount_str.lower() in ['none', 'null', '']:
                                    continue
                                
                                # Parse date
                                parsed_date = self._parse_date(date_str)
                                if not parsed_date:
                                    continue
                                
                                # Parse amount
                                clean_amount = amount_str.replace('£', '').replace('$', '').replace('€', '').replace(',', '').strip()
                                
                                # Handle negative/debit indicators
                                direction = 'credit'
                                if '-' in clean_amount or '(' in clean_amount or 'DR' in amount_str.upper():
                                    direction = 'debit'
                                    clean_amount = clean_amount.replace('-', '').replace('(', '').replace(')', '').strip()
                                
                                try:
                                    amount = abs(float(clean_amount))
                                except:
                                    continue
                                
                                # Generate unique transaction ID
                                txn_id = self._generate_transaction_id("PDF_Statement", parsed_date, amount, file_hash)
                                
                                transactions.append({
                                    "id": txn_id,
                                    "transaction_id": txn_id,
                                    "account_id": "PDF_Statement",
                                    "date": parsed_date,
                                    "amount": amount,
                                    "currency": "GBP",
                                    "direction": direction,
                                    "description": description[:500] if description else "N/A",
                                    "counterparty_name": "",
                                    "balance": balance
                                })
                                debug_info["transactions_extracted"] += 1
                            
                            except Exception as e:
                                # Skip malformed rows silently
                                continue
                    
                    # METHOD 2: If no tables or few transactions, try text extraction
                    if len(transactions) < 3:  # Threshold: try text extraction if < 3 transactions found
                        text = page.extract_text()
                        if text:
                            lines = text.split('\n')
                            debug_info["text_lines_checked"] += len(lines)
                            
                            for line in lines:
                                line = line.strip()
                                if not line or len(line) < 10:
                                    continue
                                
                                # Look for lines with date pattern AND amount pattern
                                date_match = re.search(r'\d{2}[-/]\d{2}[-/]\d{2,4}', line)
                                amount_match = re.search(r'[£$€]?[\d,]+\.\d{2}', line)
                                
                                if date_match and amount_match:
                                    try:
                                        date_str = date_match.group()
                                        amount_str = amount_match.group()
                                        
                                        # Extract description (text between date and amount)
                                        desc_start = date_match.end()
                                        desc_end = amount_match.start()
                                        description = line[desc_start:desc_end].strip()
                                        
                                        parsed_date = self._parse_date(date_str)
                                        if not parsed_date:
                                            continue
                                        
                                        clean_amount = amount_str.replace('£', '').replace('$', '').replace('€', '').replace(',', '').strip()
                                        direction = 'debit' if '-' in line[:amount_match.start()] or 'DR' in line else 'credit'
                                        clean_amount = clean_amount.replace('-', '').replace('(', '').replace(')', '')
                                        
                                        amount = abs(float(clean_amount))
                                        
                                        # Check if this transaction already exists (avoid duplicates)
                                        duplicate = any(
                                            t['date'] == parsed_date and abs(t['amount'] - amount) < 0.01 
                                            for t in transactions
                                        )
                                        
                                        if not duplicate:
                                            # Generate unique transaction ID
                                            txn_id = self._generate_transaction_id("PDF_Statement", parsed_date, amount, file_hash)
                                            
                                            transactions.append({
                                                "id": txn_id,
                                                "transaction_id": txn_id,
                                                "account_id": "PDF_Statement",
                                                "date": parsed_date,
                                                "amount": amount,
                                                "currency": "GBP",
                                                "direction": direction,
                                                "description": description[:500] if description else "Transaction",
                                                "counterparty_name": "",
                                                "balance": None
                                            })
                                            debug_info["transactions_extracted"] += 1
                                    
                                    except Exception:
                                        continue
            
            if not transactions:
                return {
                    "success": False,
                    "error": f"No transaction data could be extracted from PDF. Debug: {debug_info}"
                }
            
            print(f"✅ Legacy PDF parser: Extracted {len(transactions)} transactions with unique IDs")
            
            return {
                "success": True,
                "data": {
                    "bank_statements": transactions,
                    "transaction_count": len(transactions)
                },
                "file_type": "pdf_statement"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"PDF bank statement processing error: {str(e)}"
            }
    
    def process_pdf_document(self, content: bytes) -> Dict[str, Any]:
        """
        Process PDF supporting document (not a bank statement)
        Extracts text for document type identification AND structured data
        """
        try:
            from app.services.pdf_extractor import pdf_extractor
            
            text_content = []
            
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
            
            full_text = "\n".join(text_content).lower()
            
            # Identify document type
            doc_type = self._identify_document_type(full_text)
            
            # Extract structured data from the PDF
            extraction_result = pdf_extractor.extract_document_data(content, doc_type)
            
            return {
                "success": True,
                "data": {
                    "document_type": doc_type,
                    "extracted_data": extraction_result['extracted_data'],
                    "extraction_confidence": extraction_result['confidence'],
                    "text_preview": extraction_result['raw_text'][:500],
                    "page_count": len(text_content)
                },
                "file_type": "pdf_document"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"PDF document processing error: {str(e)}"
            }
    
    def _parse_date(self, date_str: str) -> str:
        """
        Parse date string to ISO format (YYYY-MM-DD)
        Handles multiple common formats
        """
        date_str = date_str.strip()
        
        # Common formats
        formats = [
            '%Y-%m-%d',      # 2024-01-15
            '%d/%m/%Y',      # 15/01/2024
            '%d-%m-%Y',      # 15-01-2024
            '%m/%d/%Y',      # 01/15/2024
            '%d %b %Y',      # 15 Jan 2024
            '%d %B %Y',      # 15 January 2024
            '%Y%m%d',        # 20240115
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%d/%m/%Y')  # UK format
            except ValueError:
                continue
        
        # If all fail, return original (will be caught upstream)
        return date_str
    
    def _find_column_index(self, header: List[str], keywords: List[str]) -> Optional[int]:
        """
        Find column index by matching keywords
        """
        for i, col in enumerate(header):
            for keyword in keywords:
                if keyword in col:
                    return i
        return None
    
    def _identify_document_type(self, text: str) -> str:
        """
        Identify document type from text content
        Returns document names that match assessment engine expectations
        
        IMPORTANT: Check more specific types first to avoid false positives
        Order matters! 'estate' in probate can match property docs mentioning 'real estate'
        """
        text_lower = text.lower()
        
        # Check in order of specificity (most specific first)
        # Share Purchase Agreement - check FIRST (very specific)
        if any(kw in text_lower for kw in ['share purchase agreement', 'spa', 'business sale', 'acquisition agreement', 'share transfer', 'sale of shares']):
            return 'Share Purchase Agreement'
        
        # Property completion - check AFTER share purchase (can have similar keywords)
        completion_keywords = ['completion statement', 'completion date', 'contract price', 'net proceeds', 'property sale proceeds', 'vendor', 'purchaser', 'title number', 'land registry', 'completion accounts', 'property purchase']
        if any(kw in text_lower for kw in completion_keywords):
            return 'completion statement'
        
        # Probate - check AFTER completion (be more specific with keywords)
        probate_keywords = ['grant of probate', 'letters of administration', 'probate registry', 'grant in respect of', 'deceased estate', 'estate of the late', 'executor', 'beneficiary distribution', 'probate reference', 'date of death']
        if any(kw in text_lower for kw in probate_keywords):
            return 'Probate grant'
        
        # Other document types
        if any(kw in text_lower for kw in ['loan agreement', 'loan offer', 'facility letter', 'lender', 'borrower', 'credit agreement']):
            return 'Loan'
        
        if any(kw in text_lower for kw in ['client account statement', 'solicitor client account', 'statement of account']):
            return "Solicitor's statement"
        
        if any(kw in text_lower for kw in ['bank confirmation letter', 'account confirmation', 'balance confirmation']):
            return 'Bank confirmation'
        
        if any(kw in text_lower for kw in ['passport', 'driving licence', 'identity document', 'proof of address']):
            return 'ID verification'
        
        if any(kw in text_lower for kw in ['financial statements', 'balance sheet', 'profit and loss', 'company accounts', 'directors report']):
            return 'Company accounts'
        
        return 'unknown'
    
    def validate_file_type(self, file: UploadFile, expected_type: str) -> Tuple[bool, str]:
        """
        Validate file MIME type
        """
        if expected_type not in self.supported_types:
            return False, f"Unsupported file type category: {expected_type}"
        
        allowed_mimes = self.supported_types[expected_type]
        
        if file.content_type not in allowed_mimes:
            return False, f"Expected {'/'.join(allowed_mimes)}, got {file.content_type}"
        
        return True, "Valid"


# Singleton instance
file_processor = FileProcessor()
