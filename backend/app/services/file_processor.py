"""
File Processing Service for SoF Assessment
Handles JSON, CSV, and PDF uploads

100% LOCAL - No external API calls
"""
from typing import Dict, List, Any, Optional, Tuple
import json
import csv
import io
import re
from datetime import datetime
from decimal import Decimal
import pdfplumber
import PyMuPDF  # fitz
from fastapi import UploadFile


class FileProcessor:
    """
    Process uploaded files for SoF assessment
    Supports: JSON (client info), CSV (bank statements), PDF (statements + docs)
    """
    
    def __init__(self):
        self.supported_types = {
            'json': ['application/json', 'text/json'],
            'csv': ['text/csv', 'application/csv'],
            'pdf': ['application/pdf']
        }
    
    async def process_upload(
        self, 
        file: UploadFile, 
        file_type: str
    ) -> Dict[str, Any]:
        """
        Main entry point for file processing
        Returns: {"success": bool, "data": Any, "error": str}
        """
        try:
            content = await file.read()
            
            if file_type == 'json':
                return await self.process_json(content)
            elif file_type == 'csv':
                return await self.process_csv_bank_statement(content)
            elif file_type == 'pdf':
                # Try as bank statement first, fall back to document
                result = await self.process_pdf_bank_statement(content)
                if not result['success']:
                    result = await self.process_pdf_document(content)
                return result
            else:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {file_type}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"File processing error: {str(e)}"
            }
    
    async def process_json(self, content: bytes) -> Dict[str, Any]:
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
                    "constraints": data.get('constraints', {})
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
    
    async def process_csv_bank_statement(self, content: bytes) -> Dict[str, Any]:
        """
        Process CSV bank statement
        Expected columns: account_id, date, amount, currency, direction, description
        Optional: counterparty_name, balance
        """
        try:
            decoded = content.decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded))
            
            # Check required columns
            required_cols = ['date', 'amount', 'direction', 'description']
            if not reader.fieldnames:
                return {
                    "success": False,
                    "error": "CSV file appears to be empty"
                }
            
            missing_cols = [c for c in required_cols if c not in reader.fieldnames]
            if missing_cols:
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
                    
                    # Direction (credit/debit)
                    direction = row['direction'].lower().strip()
                    if direction not in ['credit', 'debit']:
                        # Try to infer from amount
                        if amount > 0:
                            direction = 'credit'
                        else:
                            direction = 'debit'
                            amount = abs(amount)
                    
                    transactions.append({
                        "account_id": row.get('account_id', 'Unknown'),
                        "date": parsed_date,
                        "amount": amount,
                        "currency": row.get('currency', 'GBP'),
                        "direction": direction,
                        "description": row['description'].strip(),
                        "counterparty_name": row.get('counterparty_name', ''),
                        "balance": float(row['balance'].replace(',', '')) if row.get('balance') else None
                    })
                
                except Exception as e:
                    # Skip malformed rows but log warning
                    print(f"Warning: Skipped row {row_num} due to error: {str(e)}")
                    continue
            
            if not transactions:
                return {
                    "success": False,
                    "error": "No valid transactions found in CSV"
                }
            
            return {
                "success": True,
                "data": {
                    "bank_statements": transactions,
                    "transaction_count": len(transactions)
                },
                "file_type": "csv"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"CSV processing error: {str(e)}"
            }
    
    async def process_pdf_bank_statement(self, content: bytes) -> Dict[str, Any]:
        """
        Process PDF bank statement
        Attempts to extract transaction data using pdfplumber
        """
        try:
            transactions = []
            
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    # Extract tables
                    tables = page.extract_tables()
                    
                    for table in tables:
                        # Try to identify header row
                        if not table or len(table) < 2:
                            continue
                        
                        # Simple heuristic: look for date, amount, description columns
                        header = [str(cell).lower() if cell else '' for cell in table[0]]
                        
                        # Find column indices
                        date_idx = self._find_column_index(header, ['date', 'transaction date'])
                        amount_idx = self._find_column_index(header, ['amount', 'debit', 'credit', 'value'])
                        desc_idx = self._find_column_index(header, ['description', 'details', 'narrative'])
                        balance_idx = self._find_column_index(header, ['balance'])
                        
                        if date_idx is None or amount_idx is None:
                            continue
                        
                        # Parse rows
                        for row in table[1:]:
                            if not row or len(row) <= max(date_idx, amount_idx):
                                continue
                            
                            try:
                                # Parse date
                                date_str = str(row[date_idx]).strip()
                                if not date_str or date_str.lower() in ['none', 'null', '']:
                                    continue
                                
                                parsed_date = self._parse_date(date_str)
                                
                                # Parse amount
                                amount_str = str(row[amount_idx]).replace('£', '').replace(',', '').replace('$', '').strip()
                                if not amount_str or amount_str.lower() in ['none', 'null', '']:
                                    continue
                                
                                amount = abs(float(amount_str))
                                
                                # Infer direction (look for minus sign or separate debit/credit columns)
                                direction = 'credit'
                                if '-' in str(row[amount_idx]) or amount_str.startswith('-'):
                                    direction = 'debit'
                                
                                # Description
                                description = str(row[desc_idx]).strip() if desc_idx is not None and desc_idx < len(row) else 'N/A'
                                
                                # Balance
                                balance = None
                                if balance_idx is not None and balance_idx < len(row):
                                    try:
                                        balance_str = str(row[balance_idx]).replace('£', '').replace(',', '').strip()
                                        balance = float(balance_str)
                                    except:
                                        pass
                                
                                transactions.append({
                                    "account_id": "PDF_Statement",
                                    "date": parsed_date,
                                    "amount": amount,
                                    "currency": "GBP",  # Default assumption
                                    "direction": direction,
                                    "description": description,
                                    "counterparty_name": "",
                                    "balance": balance
                                })
                            
                            except Exception as e:
                                # Skip malformed rows
                                continue
            
            if not transactions:
                return {
                    "success": False,
                    "error": "No transaction data could be extracted from PDF"
                }
            
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
    
    async def process_pdf_document(self, content: bytes) -> Dict[str, Any]:
        """
        Process PDF supporting document (not a bank statement)
        Extracts text for document type identification
        """
        try:
            text_content = []
            
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
            
            full_text = "\n".join(text_content).lower()
            
            # Identify document type
            doc_type = self._identify_document_type(full_text)
            
            return {
                "success": True,
                "data": {
                    "document_type": doc_type,
                    "text_preview": full_text[:500],  # First 500 chars
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
                return dt.strftime('%Y-%m-%d')
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
        """
        doc_types = {
            'probate': ['probate', 'grant of probate', 'letters of administration', 'estate'],
            'property_completion': ['completion statement', 'property purchase', 'land registry'],
            'loan_agreement': ['loan agreement', 'loan offer', 'facility letter', 'lender'],
            'share_purchase': ['share purchase', 'spa', 'business sale', 'acquisition'],
            'solicitor_statement': ['solicitor', 'client account', 'statement of account'],
            'bank_confirmation': ['bank confirmation', 'account confirmation'],
            'id_verification': ['passport', 'driving licence', 'identity', 'proof of address'],
            'company_accounts': ['financial statements', 'balance sheet', 'profit and loss', 'company accounts']
        }
        
        for doc_type, keywords in doc_types.items():
            if any(kw in text for kw in keywords):
                return doc_type
        
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
