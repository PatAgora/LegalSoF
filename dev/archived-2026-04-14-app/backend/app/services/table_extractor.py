"""
Table extraction from PDFs
Handles structured beneficiary schedules, distribution tables, property details, etc.
"""
import pdfplumber
import io
from typing import List, Dict, Any, Optional
import re


class TableExtractor:
    """Extract structured data from PDF tables"""
    
    def extract_tables(self, pdf_content: bytes) -> List[List[List[str]]]:
        """Extract all tables from PDF"""
        tables = []
        
        try:
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
        except Exception as e:
            print(f"Table extraction error: {str(e)}")
        
        return tables
    
    def extract_beneficiary_distributions(self, tables: List[List[List[str]]]) -> List[Dict[str, Any]]:
        """
        Extract beneficiary distributions from tables
        Returns: [{'beneficiary': 'Name', 'amount': 250000.0, 'date': '15/05/2023'}, ...]
        """
        distributions = []
        
        for table in tables:
            if not table or len(table) < 2:
                continue
            
            # Get headers (first row)
            headers = [str(h).lower().strip() if h else '' for h in table[0]]
            
            # Find relevant columns
            name_col = self._find_column_index(headers, ['name', 'beneficiary', 'recipient', 'payee', 'person'])
            amount_col = self._find_column_index(headers, ['amount', 'sum', 'payment', '£', 'gbp', 'value', 'total'])
            date_col = self._find_column_index(headers, ['date', 'paid', 'transfer', 'payment date', 'distribution date'])
            
            if name_col is None or amount_col is None:
                continue
            
            # Extract data rows
            for row in table[1:]:  # Skip header
                if not row or len(row) <= max(name_col, amount_col):
                    continue
                
                name = str(row[name_col]).strip() if row[name_col] else None
                amount_str = str(row[amount_col]).strip() if row[amount_col] else None
                date_str = str(row[date_col]).strip() if date_col is not None and len(row) > date_col and row[date_col] else None
                
                if not name or not amount_str:
                    continue
                
                # Skip if name is empty or just whitespace
                if not name or name == 'None':
                    continue
                
                # Parse amount
                amount = self._parse_amount(amount_str)
                if amount == 0:
                    continue
                
                distributions.append({
                    'beneficiary': name,
                    'amount': amount,
                    'date': date_str
                })
        
        return distributions
    
    def extract_property_details(self, tables: List[List[List[str]]]) -> Dict[str, Any]:
        """Extract property transaction details from tables"""
        details = {}
        
        # Look for key-value tables (common in completion statements)
        for table in tables:
            if not table:
                continue
            
            for row in table:
                if not row or len(row) < 2:
                    continue
                
                key = str(row[0]).lower().strip() if row[0] else ''
                value = str(row[1]).strip() if row[1] else ''
                
                if not key or not value or value == 'None':
                    continue
                
                # Match common fields
                if 'address' in key or 'property' in key:
                    details['property_address'] = value
                elif 'vendor' in key or 'seller' in key:
                    details['vendor_name'] = value
                elif 'purchaser' in key or 'buyer' in key:
                    details['purchaser_name'] = value
                elif 'completion' in key and 'date' in key:
                    details['completion_date'] = value
                elif 'contract' in key and 'price' in key:
                    details['contract_price'] = self._parse_amount(value)
                elif 'net' in key and 'proceed' in key:
                    details['net_proceeds'] = self._parse_amount(value)
                elif 'title' in key and 'number' in key:
                    details['title_number'] = value
        
        return details
    
    def _find_column_index(self, headers: List[str], keywords: List[str]) -> Optional[int]:
        """Find column index by matching keywords (fuzzy)"""
        for i, header in enumerate(headers):
            if not header:
                continue
            for keyword in keywords:
                if keyword in header or header in keyword:
                    return i
                # Fuzzy match
                if self._fuzzy_match(header, keyword):
                    return i
        return None
    
    def _fuzzy_match(self, text1: str, text2: str, threshold: float = 0.8) -> bool:
        """Simple fuzzy matching"""
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
        return ratio >= threshold
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float"""
        if not amount_str or amount_str == 'None':
            return 0.0
        
        try:
            # Remove currency symbols, commas, and spaces
            cleaned = re.sub(r'[£$€,\s]', '', str(amount_str))
            # Remove GBP, USD, etc.
            cleaned = re.sub(r'[A-Z]{3}', '', cleaned)
            # Remove any non-numeric except decimal point
            cleaned = re.sub(r'[^\d.]', '', cleaned)
            if cleaned:
                return float(cleaned)
            return 0.0
        except:
            return 0.0


# Singleton
table_extractor = TableExtractor()
