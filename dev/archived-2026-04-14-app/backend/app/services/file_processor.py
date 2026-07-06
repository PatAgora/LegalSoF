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
from datetime import datetime
from decimal import Decimal
import pdfplumber
import fitz  # PyMuPDF
from fastapi import UploadFile

from app.services.amount_parser import parse_amount, parse_date, detect_currency


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

    def _generate_transaction_id(self, account_id: str = "", date: str = "", amount: float = 0,
                                 description: str = "", balance: Optional[float] = None,
                                 occurrence_index: int = 0) -> str:
        """
        Generate a CONTENT-DERIVED transaction ID (A14).

        sha256 over (account_id, date, amount, normalised description,
        balance, occurrence_index), truncated. Re-uploading the same
        statement therefore yields the SAME IDs (stable, idempotent), while
        legitimate identical rows on the same statement get distinct IDs via
        occurrence_index (their position among identical tuples).

        Format: TXN-{sha256_hex[:16].upper()}
        """
        norm_desc = ' '.join(str(description or '').split()).lower()[:100]
        try:
            amount_part = f"{float(amount):.2f}"
        except (TypeError, ValueError):
            amount_part = str(amount)
        balance_part = '' if balance is None else f"{float(balance):.2f}"
        payload = f"{account_id}|{date}|{amount_part}|{norm_desc}|{balance_part}|{occurrence_index}"
        digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        return f"TXN-{digest[:16].upper()}"

    def _assign_transaction_ids(self, transactions: List[Dict], account_fallback: str = 'Unknown') -> None:
        """Assign stable content-derived IDs to transactions lacking one.

        occurrence_index counts identical (account, date, amount, desc,
        balance) tuples so genuine same-day duplicates still get distinct,
        stable IDs.
        """
        occurrence_counter: Dict[tuple, int] = {}
        for txn in transactions:
            if txn.get('id'):
                continue
            account_id = txn.get('account_id') or account_fallback
            date_val = txn.get('date', '')
            amount_val = txn.get('amount', 0)
            desc_val = txn.get('description', '')
            balance_val = txn.get('balance')
            key = (account_id, date_val, amount_val,
                   ' '.join(str(desc_val or '').split()).lower()[:100],
                   balance_val)
            idx = occurrence_counter.get(key, 0)
            occurrence_counter[key] = idx + 1
            txn['id'] = self._generate_transaction_id(
                account_id, date_val, amount_val, desc_val, balance_val, idx
            )
            txn['transaction_id'] = txn['id']
    
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
                statement_error = result.get('error', 'unknown parsing error')
                result = self.process_pdf_document(content)
                # A16: don't silently retry as a supporting document — record
                # a warning that flows back so the UI/report can surface it.
                if result.get('success'):
                    warning = ("Bank statement could not be parsed as transactions; "
                               f"treated as supporting document (reason: {statement_error})")
                    result.setdefault('metadata', {})
                    result['metadata'].setdefault('parse_warnings', []).append(warning)
                    if isinstance(result.get('data'), dict):
                        result['data'].setdefault('parse_warnings', []).append(warning)
                    print(f"⚠️ {warning}")
            return result
        elif file_type == 'pdf_document':
            print(f"📄 Processing as supporting document: {filename}")
            return self.process_pdf_document(content)
        elif file_type == 'client_info_document':
            # Free-text client-info file (PDF / Word / CSV / TXT) —
            # extract text then regex out the structured fields.
            print(f"📄 Processing as client_info document: {filename}")
            return self.process_client_info_document(content, filename)
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

            # ---- Content validation (A18) ----
            # An empty content_type must NOT bypass validation: check the
            # extension AND the magic bytes, and reject when the claimed
            # type contradicts what the bytes actually are.
            valid, validation_error = self._validate_content_signature(content, filename, content_type)
            if not valid:
                return {"success": False, "error": validation_error}

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
    
    # ------------------------------------------------------------------
    # Content signature validation (A18)
    # ------------------------------------------------------------------
    @staticmethod
    def _detect_magic_category(content: bytes) -> Optional[str]:
        """Classify content by magic bytes: pdf / zip / ole / image / text / None."""
        if not content:
            return None
        if content[:4] == b'%PDF':
            return 'pdf'
        if content[:4] == b'PK\x03\x04':
            return 'zip'  # XLSX / ODS / DOCX containers
        if content[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            return 'ole'  # legacy .xls / .doc
        if (content[:8] == b'\x89PNG\r\n\x1a\n' or content[:2] == b'\xff\xd8'
                or content[:4] == b'GIF8' or content[:2] == b'BM'
                or content[:4] in (b'II*\x00', b'MM\x00*')
                or (content[:4] == b'RIFF' and content[8:12] == b'WEBP')):
            return 'image'
        # Text detection on the first 1KB: try utf-8, then latin-1 with a
        # printable-character sanity check (latin-1 decodes any bytes).
        head = content[:1024]
        for encoding in ('utf-8', 'latin-1'):
            try:
                decoded = head.decode(encoding)
            except UnicodeDecodeError:
                continue
            printable = sum(1 for ch in decoded if ch.isprintable() or ch in '\r\n\t')
            if decoded and printable / len(decoded) >= 0.9:
                return 'text'
            break
        return None

    def _validate_content_signature(self, content: bytes, filename: str, content_type: str) -> Tuple[bool, str]:
        """Validate that the claimed file type (extension / MIME) matches the
        actual magic bytes. Rejects contradictions (A18)."""
        magic = self._detect_magic_category(content)

        # What does the caller claim this file is?
        ext = (filename.rsplit('.', 1)[-1].lower() if '.' in (filename or '') else '')
        claimed = None
        if ext == 'pdf' or 'pdf' in (content_type or ''):
            claimed = 'pdf'
        elif ext in ('xlsx', 'ods') or 'spreadsheetml' in (content_type or ''):
            claimed = 'zip'
        elif ext == 'xls' or (content_type or '') == 'application/vnd.ms-excel':
            claimed = 'ole_or_zip'
        elif ext in ('png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff') or 'image' in (content_type or ''):
            claimed = 'image'
        elif ext in ('csv', 'txt', 'json', 'tsv') or any(
                t in (content_type or '') for t in ('csv', 'json', 'text')):
            claimed = 'text'

        if claimed is None or magic is None:
            # Nothing verifiable to contradict — allow (parser will re-detect).
            return True, ''

        allowed = {
            'pdf': {'pdf'},
            'zip': {'zip'},
            'ole_or_zip': {'ole', 'zip'},
            'image': {'image'},
            'text': {'text'},
        }[claimed]

        if magic not in allowed:
            return False, (
                f"File content does not match its declared type: claimed "
                f"'{ext or content_type or 'unknown'}' but the file signature "
                f"is '{magic}'. Upload rejected."
            )
        return True, ''

    def process_auto(self, content: bytes, filename: str, content_type: str) -> Dict[str, Any]:
        """
        Auto-detect file type and process accordingly using enhanced parser.
        Now generates unique transaction IDs.
        """
        try:
            from app.services.enhanced_universal_parser import enhanced_universal_parser

            print(f"\n🔄 Auto-detecting file type for: {filename}")
            result = enhanced_universal_parser.parse(content, filename=filename, content_type=content_type)

            if result['success'] and result['transactions']:
                # Add stable, content-derived transaction IDs (A14)
                self._assign_transaction_ids(result['transactions'], 'Unknown')

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

            print(f"\n🖼️ Processing image: {filename}")
            result = enhanced_universal_parser.parse(content, filename=filename, content_type='image/png')

            if result['success'] and result['transactions']:
                # Add stable, content-derived transaction IDs (A14)
                self._assign_transaction_ids(result['transactions'], 'Image_Statement')

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

            print("\n📊 Processing Excel file")
            result = enhanced_universal_parser.parse(content, filename='statement.xlsx', content_type='application/vnd.ms-excel')

            if result['success'] and result['transactions']:
                # Add stable, content-derived transaction IDs (A14)
                self._assign_transaction_ids(result['transactions'], 'Excel_Statement')

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
            
            # Resolve an explicit claims array. Client info JSON comes in
            # two shapes:
            #   (a) a top-level "claims" array, or
            #   (b) a structured "sof_explanation" object carrying a
            #       "sources" array (property_sale / savings / etc.).
            # Either way we surface a single canonical "claims" list so
            # downstream code never has to dig the sources out of
            # sof_explanation — and so the structured data survives even
            # if sof_explanation later gets flattened to prose text.
            claims = data.get('claims') or []
            if not claims:
                sof = data.get('sof_explanation')
                if isinstance(sof, dict) and isinstance(sof.get('sources'), list):
                    claims = sof['sources']

            return {
                "success": True,
                "data": {
                    "client_info": data['client_info'],
                    "purchase": data['purchase'],
                    "sof_explanation": data['sof_explanation'],
                    "known_documents": data.get('known_documents', []),
                    "flags": data.get('flags', {}),
                    "constraints": data.get('constraints', {}),
                    "claims": claims  # canonical claims list (see above)
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
            # First try legacy parsing which respects column names directly
            print("\n📋 Processing CSV - trying direct column parsing first...")
            legacy_result = self._legacy_csv_parse(content)
            
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
                # Add stable, content-derived transaction IDs (A14)
                self._assign_transaction_ids(result['transactions'], 'Unknown')

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
    
    def _legacy_csv_parse(self, content: bytes) -> Dict[str, Any]:
        """
        Legacy CSV parsing for backwards compatibility.
        Expected columns: account_id, date, amount, currency, direction, description
        Optional: counterparty_name, balance

        Transaction IDs are content-derived (A14): stable across re-uploads.
        """
        try:
            decoded = content.decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded))

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
            rejected_rows = 0
            rejected_samples: List[str] = []

            def _reject(row_num, row, reason):
                nonlocal rejected_rows
                rejected_rows += 1
                if len(rejected_samples) < 5:
                    rejected_samples.append(f"row {row_num} ({reason}): " +
                                            ' | '.join(str(v) for v in row.values())[:200])
                print(f"⚠️ Legacy CSV parser: Skipped row {row_num}: {reason}")

            for row_num, row in enumerate(reader, start=2):
                try:
                    # Parse amount via the shared helper (handles £/,/CR/DR/parens)
                    amount_raw = row['amount']
                    amount = parse_amount(amount_raw)
                    if amount is None:
                        _reject(row_num, row, f"unparseable amount '{amount_raw}'")
                        continue

                    # Parse date (A6: None on failure — skip AND count the row)
                    date_str = row['date'].strip()
                    parsed_date = self._parse_date(date_str)
                    if not parsed_date:
                        _reject(row_num, row, f"unparseable date '{date_str}'")
                        continue

                    # Direction (credit/debit) - READ DIRECTLY FROM COLUMN
                    direction = row['direction'].lower().strip()
                    if direction not in ['credit', 'debit']:
                        # Try to infer from amount sign
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
                    
                    # A4: balance parsed via shared helper (strips £ etc.
                    # instead of raising ValueError and killing the row)
                    balance = parse_amount(row['balance']) if row.get('balance') else None

                    transactions.append({
                        "account_id": account_id,
                        "date": parsed_date,
                        "amount": amount,
                        # A17: fall back to the symbol in the amount cell
                        "currency": row.get('currency') or detect_currency(amount_raw, 'GBP'),
                        "direction": direction,
                        "description": row['description'].strip(),
                        "counterparty_name": row.get('counterparty_name', ''),
                        "balance": float(balance) if balance is not None else None,
                        "country_iso2": country_iso2,
                        "channel": channel
                    })

                    # Log first few transactions for debugging
                    if row_num <= 4:
                        print(f"   Row {row_num}: {parsed_date} | {direction} | £{amount} | {account_id[:30]}... | Country: {country_iso2 or 'N/A'}")

                except Exception as e:
                    # Skip malformed rows, but COUNT them (silent-row-loss fix)
                    _reject(row_num, row, str(e))
                    continue

            # Assign stable, content-derived transaction IDs (A14)
            self._assign_transaction_ids(transactions, 'Unknown')
            
            if not transactions:
                print("❌ Legacy CSV parser: No valid transactions found in CSV")
                return {
                    "success": False,
                    "error": "No valid transactions found in CSV"
                }
            
            print(f"✅ Legacy CSV parser: Successfully parsed {len(transactions)} transactions with unique IDs")
            if rejected_rows:
                print(f"   ⚠️ Parsed {len(transactions)} of {len(transactions) + rejected_rows} rows "
                      f"({rejected_rows} rejected)")

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
                "file_type": "csv",
                "metadata": {
                    "rejected_row_count": rejected_rows,
                    "rejected_row_samples": rejected_samples,
                }
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
        
        Transaction IDs are content-derived (A14): stable across re-uploads.
        """
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

                # Add stable, content-derived transaction IDs (A14)
                self._assign_transaction_ids(result['transactions'], 'PDF_Statement')

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
                "transactions_extracted": 0,
                "rejected_row_count": 0,
                "rejected_row_samples": [],
            }

            def _reject_pdf_row(raw, reason):
                debug_info["rejected_row_count"] += 1
                if len(debug_info["rejected_row_samples"]) < 5:
                    debug_info["rejected_row_samples"].append(f"({reason}) {str(raw)[:200]}")
            
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
                                    # A4: shared parser strips £ etc. instead of
                                    # raising ValueError and killing the row
                                    balance = parse_amount(str(row[balance_idx]))
                                
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
                                
                                # Parse date (A6: shared parser, ISO output, None on failure)
                                parsed_date = self._parse_date(date_str)
                                if not parsed_date:
                                    _reject_pdf_row(row, f"unparseable date '{date_str}'")
                                    continue

                                # Parse amount via the shared helper (A9: sign
                                # comes from the amount cell itself; DR/CR only
                                # as whole suffix tokens, so 'DR SMITH' in the
                                # description can no longer flip a row)
                                amount_val = parse_amount(amount_str)
                                if amount_val is None:
                                    _reject_pdf_row(row, f"unparseable amount '{amount_str}'")
                                    continue

                                if amount_val < 0 or '(' in amount_str:
                                    direction = 'debit'
                                elif re.search(r'\bCR\b', amount_str, re.IGNORECASE):
                                    direction = 'credit'
                                elif re.search(r'\bDR\b', amount_str, re.IGNORECASE):
                                    direction = 'debit'
                                else:
                                    # A10: no evidence — needs review, never
                                    # a fabricated credit
                                    direction = 'unknown'
                                amount = abs(amount_val)

                                transactions.append({
                                    "account_id": "PDF_Statement",
                                    "date": parsed_date,
                                    "amount": amount,
                                    "currency": detect_currency(amount_str, 'GBP'),  # A17
                                    "direction": direction,
                                    "description": description[:500] if description else "N/A",
                                    "counterparty_name": "",
                                    "balance": balance
                                })
                                debug_info["transactions_extracted"] += 1

                            except Exception as e:
                                # Skip malformed rows, but COUNT them
                                _reject_pdf_row(row, str(e))
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
                                            _reject_pdf_row(line, f"unparseable date '{date_str}'")
                                            continue

                                        amount_val = parse_amount(amount_str)
                                        if amount_val is None:
                                            _reject_pdf_row(line, f"unparseable amount '{amount_str}'")
                                            continue
                                        amount = abs(amount_val)

                                        # A9: a minus only counts when IMMEDIATELY
                                        # adjacent to the amount (hyphenated dates/
                                        # descriptions used to make everything a
                                        # debit); DR/CR only as whole tokens NEAR
                                        # the amount (so 'DR SMITH' elsewhere in
                                        # the line no longer flips direction).
                                        near_amount = line[max(0, amount_match.start() - 12):
                                                           min(len(line), amount_match.end() + 12)]
                                        char_before = line[amount_match.start() - 1] if amount_match.start() > 0 else ''
                                        if amount_val < 0 or char_before == '-' or amount_str.startswith('-'):
                                            direction = 'debit'
                                        elif re.search(r'\bDR\b', near_amount):
                                            direction = 'debit'
                                        elif re.search(r'\bCR\b', near_amount):
                                            direction = 'credit'
                                        else:
                                            # A10: no evidence — needs review
                                            direction = 'unknown'

                                        # A13: dedup must also compare description
                                        # (and balance) so legitimate same-day,
                                        # same-amount transactions survive.
                                        duplicate = any(
                                            t['date'] == parsed_date
                                            and abs(t['amount'] - amount) < 0.01
                                            and (t.get('description') or '')[:50] == (description or '')[:50]
                                            for t in transactions
                                        )

                                        if not duplicate:
                                            transactions.append({
                                                "account_id": "PDF_Statement",
                                                "date": parsed_date,
                                                "amount": amount,
                                                "currency": detect_currency(amount_str, 'GBP'),  # A17
                                                "direction": direction,
                                                "description": description[:500] if description else "Transaction",
                                                "counterparty_name": "",
                                                "balance": None
                                            })
                                            debug_info["transactions_extracted"] += 1

                                    except Exception as e:
                                        _reject_pdf_row(line, str(e))
                                        continue
            
            if not transactions:
                return {
                    "success": False,
                    "error": f"No transaction data could be extracted from PDF. Debug: {debug_info}"
                }

            # Assign stable, content-derived transaction IDs (A14)
            self._assign_transaction_ids(transactions, 'PDF_Statement')

            print(f"✅ Legacy PDF parser: Extracted {len(transactions)} transactions with unique IDs")
            if debug_info["rejected_row_count"]:
                total = len(transactions) + debug_info["rejected_row_count"]
                print(f"   ⚠️ Parsed {len(transactions)} of {total} candidate rows "
                      f"({debug_info['rejected_row_count']} rejected)")

            return {
                "success": True,
                "data": {
                    "bank_statements": transactions,
                    "transaction_count": len(transactions)
                },
                "file_type": "pdf_statement",
                "metadata": {
                    "rejected_row_count": debug_info["rejected_row_count"],
                    "rejected_row_samples": debug_info["rejected_row_samples"],
                    "unknown_direction_count": sum(
                        1 for t in transactions if t.get('direction') == 'unknown'),
                }
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
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """
        Parse date string to ISO format (YYYY-MM-DD) via the shared helper.

        A6: returns None on failure — NEVER the input string — so callers'
        `if not parsed_date` checks actually fire and the row is skipped
        (and counted). Output is standardised to ISO YYYY-MM-DD everywhere
        (the assessment engine expects ISO).
        A8: two-digit years supported (pivot: <70 -> 2000s).
        """
        return parse_date(date_str)
    
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
        # A15: completion-statement keywords are checked BEFORE the SPA
        # shortlist, and 'spa' must be a whole word (r'\bspa\b') so that
        # "spacious"/"Spain" no longer classify a document as an SPA.
        completion_keywords = ['completion statement', 'completion date', 'contract price', 'net proceeds', 'property sale proceeds', 'vendor', 'purchaser', 'title number', 'land registry', 'completion accounts', 'property purchase']
        if any(kw in text_lower for kw in completion_keywords):
            return 'completion statement'

        # Share Purchase Agreement
        if any(kw in text_lower for kw in ['share purchase agreement', 'business sale', 'acquisition agreement', 'share transfer', 'sale of shares']) \
                or re.search(r'\bspa\b', text_lower):
            return 'Share Purchase Agreement'
        
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


    # ------------------------------------------------------------------
    # Client-info document parser
    # ------------------------------------------------------------------
    # Extracts the SAME structured shape that process_json produces
    # (client_info / purchase / sof_explanation) — but from a free-text
    # PDF, Word doc, CSV or TXT. Regex-driven, never throws; missing
    # fields stay null so the frontend pre-fill logic just leaves them
    # blank and the user enters them manually.
    def process_client_info_document(self, content: bytes, filename: str = '') -> Dict[str, Any]:
        text = self._extract_text_for_client_info(content, filename)
        if not text or not text.strip():
            return {
                "success": False,
                "error": "Could not read any text from the file.",
            }

        client_info, purchase, sof_explanation = self._regex_client_info(text)

        # Always return a populated structure even when some fields are
        # missing — the upload pipeline downstream calls
        # `data['client_info']` etc unconditionally, so we mustn't drop
        # the keys.
        return {
            "success": True,
            "file_type": filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'text',
            "data": {
                "client_info": client_info,
                "purchase": purchase,
                "sof_explanation": sof_explanation,
                "known_documents": [],
                "flags": {"pep": client_info.get('pep_status', False)},
                "constraints": {},
                "claims": [],
            },
        }

    def _extract_text_for_client_info(self, content: bytes, filename: str) -> str:
        """Pull plain text from whatever format the user uploaded."""
        ext = (filename.rsplit('.', 1)[-1] or '').lower() if '.' in filename else ''
        try:
            if ext == 'pdf' or content[:4] == b'%PDF':
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(stream=content, filetype='pdf')
                    try:
                        return "\n".join((p.get_text() or '') for p in doc)
                    finally:
                        doc.close()
                except Exception:
                    return ''
            if ext in ('docx', 'doc'):
                try:
                    from docx import Document
                    import io as _io
                    doc = Document(_io.BytesIO(content))
                    return "\n".join(p.text for p in doc.paragraphs)
                except Exception:
                    return content.decode('utf-8', errors='ignore')
            # CSV / TXT / fallback — just decode bytes.
            return content.decode('utf-8', errors='ignore')
        except Exception:
            return ''

    @staticmethod
    def _regex_client_info(text: str) -> tuple:
        """Run the actual extraction. Returns (client_info dict,
        purchase dict, sof_explanation str)."""
        import re

        # ---------- helpers --------------------------------------------
        def _find_first(patterns, flags=re.IGNORECASE):
            for pat in patterns:
                m = re.search(pat, text, flags)
                if m:
                    return m.group(1).strip()
            return None

        def _clean(s):
            if not s:
                return None
            # Strip surrounding quotes and trailing punctuation /
            # whitespace.
            s = s.strip().strip('"\'')
            return s or None

        # ---------- client name ----------------------------------------
        client_name = _find_first([
            r'(?:client(?:\'s)?\s+name|full\s+name|customer\s+name|name\s+of\s+client)\s*[:\-]\s*([^\n\r]+?)(?:\n|$|,|;)',
            r'(?:client|customer)\s*[:\-]\s*((?:Mr|Mrs|Ms|Miss|Dr|Mr\.|Mrs\.|Ms\.|Dr\.)\s+[A-Z][^\n\r]{1,80})',
        ])
        client_name = _clean(client_name)

        # ---------- business sector ------------------------------------
        business_sector = _clean(_find_first([
            r'(?:business\s+sector|industry|sector|occupation|profession)\s*[:\-]\s*([^\n\r]+?)(?:\n|$|,|;)',
        ]))

        # ---------- risk rating ----------------------------------------
        risk_raw = _find_first([
            r'(?:client\s+)?risk\s*(?:rating)?\s*[:\-]\s*(low|medium|high|standard|elevated|enhanced)',
        ])
        risk = None
        if risk_raw:
            r = risk_raw.lower()
            if r in ('low', 'standard'):
                risk = 'low'
            elif r in ('medium',):
                risk = 'medium'
            elif r in ('high', 'elevated', 'enhanced'):
                risk = 'high'

        # ---------- PEP status -----------------------------------------
        pep_status = False
        pep_match = re.search(
            r'(?:pep|politically\s+exposed\s+person|political(?:ly)?\s+exposed)\s*[:\-]\s*(yes|no|true|false|n/a|none)',
            text, re.IGNORECASE,
        )
        if pep_match:
            pep_status = pep_match.group(1).lower() in ('yes', 'true')
        elif re.search(r'\bPEP\s*[:\-]?\s*(?:yes|y|true)\b', text, re.IGNORECASE):
            pep_status = True
        elif re.search(r'is\s+a\s+politically\s+exposed\s+person', text, re.IGNORECASE):
            pep_status = True

        # ---------- amount + currency ----------------------------------
        amount = None
        currency = None
        # Try labelled amount first: "purchase price: £500,000",
        # "transaction amount: 250000 GBP", "amount: $1,200,000".
        labelled = re.search(
            r'(?:purchase\s+(?:price|amount)|transaction\s+amount|amount|sum\s+of)\s*[:\-]?\s*'
            r'(?P<sym>[£$€])?\s*(?P<value>[\d][\d,]*(?:\.\d+)?)\s*(?P<cur>GBP|USD|EUR|AUD|CAD|NZD|CHF|JPY|SGD)?',
            text, re.IGNORECASE,
        )
        if labelled:
            try:
                amount = float(labelled.group('value').replace(',', ''))
                sym = labelled.group('sym') or ''
                cur = (labelled.group('cur') or '').upper()
                if cur:
                    currency = cur
                elif sym == '£':
                    currency = 'GBP'
                elif sym == '$':
                    currency = 'USD'
                elif sym == '€':
                    currency = 'EUR'
            except (TypeError, ValueError):
                amount = None
        # Fallback — any £-prefixed number anywhere in the doc.
        if amount is None:
            free = re.search(r'£\s*([\d][\d,]*(?:\.\d+)?)', text)
            if free:
                try:
                    amount = float(free.group(1).replace(',', ''))
                    currency = 'GBP'
                except (TypeError, ValueError):
                    amount = None

        # ---------- expected payment date -------------------------------
        # Accept "expected payment date: 12/06/2026" / "completion
        # date: 12 June 2026" / ISO. Best-effort parse to YYYY-MM-DD.
        date_iso = None
        date_raw = _find_first([
            r'(?:expected\s+(?:payment|completion)\s+date|completion\s+date|payment\s+date|date\s+expected)\s*[:\-]\s*([^\n\r,;]+?)(?:\n|$|,|;)',
        ])
        if date_raw:
            from datetime import datetime as _dt
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d %B %Y', '%d %b %Y', '%d.%m.%Y'):
                try:
                    date_iso = _dt.strptime(date_raw.strip(), fmt).date().isoformat()
                    break
                except (ValueError, TypeError):
                    continue

        # ---------- purchase description --------------------------------
        description = _clean(_find_first([
            r'(?:purchase\s+description|transaction\s+description|purpose|description\s+of\s+purchase)\s*[:\-]\s*([^\n\r]+?)(?:\n|$)',
        ]))

        # ---------- source-of-funds explanation -------------------------
        # Try a labelled block first: capture lines following the label
        # until a blank line or the next "FieldName:" header.
        sof = None
        block_match = re.search(
            r'(?:source\s+of\s+funds(?:\s+explanation)?|funds\s+explanation|sof\s+explanation)\s*[:\-]\s*'
            r'(.+?)(?:\n\s*\n|\n[A-Z][A-Za-z ]{1,40}:|\Z)',
            text, re.IGNORECASE | re.DOTALL,
        )
        if block_match:
            sof = block_match.group(1).strip()
            # Collapse extra whitespace.
            sof = re.sub(r'\s+', ' ', sof).strip()
            if len(sof) < 4:
                sof = None

        # Build outputs.
        client_info = {
            'client_name':        client_name,
            'client_risk_rating': risk or 'medium',
            'business_sector':    business_sector,
            'pep_status':         pep_status,
        }
        purchase = {
            'amount':                amount,
            'currency':              currency or 'GBP',
            'expected_payment_date': date_iso,
            'description':           description,
        }
        return client_info, purchase, (sof or '')


# Singleton instance
file_processor = FileProcessor()
