"""
CSV parser for bank statement transaction data.
Supports multiple CSV formats and validates data.
"""
import csv
import io
from datetime import datetime
from typing import List, Dict
from decimal import Decimal


class TransactionCSVParser:
    """Parser for transaction CSV files"""
    
    # Common column name variations
    COLUMN_MAPPINGS = {
        'id': ['id', 'transaction_id', 'txn_id', 'reference', 'ref'],
        'date': ['date', 'txn_date', 'transaction_date', 'value_date', 'posting_date'],
        'amount': ['amount', 'value', 'debit', 'credit', 'transaction_amount'],
        'currency': ['currency', 'ccy', 'curr'],
        'direction': ['direction', 'type', 'transaction_type', 'dr_cr'],
        'narrative': ['narrative', 'description', 'details', 'memo', 'reference'],
        'country': ['country', 'country_code', 'country_iso2', 'iso2'],
        'channel': ['channel', 'method', 'payment_method', 'type'],
        'payer_sort_code': ['payer_sort_code', 'from_sort_code', 'debit_sort_code'],
        'payee_sort_code': ['payee_sort_code', 'to_sort_code', 'credit_sort_code'],
    }
    
    def parse_csv(self, csv_content: str, customer_id: str) -> List[Dict]:
        """Parse CSV content and return list of transaction dicts"""
        # Read CSV
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no headers")
        
        # Map columns
        column_map = self._detect_columns(reader.fieldnames)
        
        transactions = []
        row_num = 1
        
        for row in reader:
            row_num += 1
            try:
                txn = self._parse_row(row, column_map, customer_id)
                if txn:
                    transactions.append(txn)
            except Exception as e:
                raise ValueError(f"Error parsing row {row_num}: {str(e)}")
        
        if not transactions:
            raise ValueError("No valid transactions found in CSV")
        
        return transactions
    
    def _detect_columns(self, headers: List[str]) -> Dict[str, str]:
        """Detect which columns map to our fields"""
        headers_lower = [h.strip().lower() for h in headers]
        column_map = {}
        
        for field, variations in self.COLUMN_MAPPINGS.items():
            for var in variations:
                if var in headers_lower:
                    # Find original header name
                    idx = headers_lower.index(var)
                    column_map[field] = headers[idx]
                    break
        
        # Validate required fields
        required = ['id', 'date', 'amount']
        missing = [f for f in required if f not in column_map]
        
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(missing)}. Headers found: {', '.join(headers)}")
        
        return column_map
    
    def _parse_row(self, row: Dict[str, str], column_map: Dict[str, str], customer_id: str) -> Dict:
        """Parse a single CSV row"""
        # Extract values using column map
        txn_id = self._get_value(row, column_map, 'id')
        date_str = self._get_value(row, column_map, 'date')
        amount_str = self._get_value(row, column_map, 'amount')
        
        if not txn_id or not date_str or not amount_str:
            return None  # Skip incomplete rows
        
        # Parse date
        txn_date = self._parse_date(date_str)
        
        # Parse amount and determine direction
        amount_str = amount_str.strip().replace(',', '').replace('£', '').replace('$', '')
        
        # Handle negative amounts (withdrawals/debits)
        if amount_str.startswith('-') or amount_str.startswith('('):
            direction = 'out'
            amount = abs(float(amount_str.replace('(', '').replace(')', '')))
        else:
            # Check direction column if exists
            direction_val = self._get_value(row, column_map, 'direction', '')
            if direction_val:
                direction_val = direction_val.strip().lower()
                if direction_val in ('out', 'debit', 'dr', 'withdrawal', 'payment'):
                    direction = 'out'
                else:
                    direction = 'in'
            else:
                direction = 'in'  # Default to incoming
            
            amount = float(amount_str)
        
        # Currency (default GBP)
        currency = self._get_value(row, column_map, 'currency', 'GBP').strip().upper()
        
        # Optional fields
        narrative = self._get_value(row, column_map, 'narrative', '')
        country = self._get_value(row, column_map, 'country', '')
        channel = self._get_value(row, column_map, 'channel', '')
        payer_sort_code = self._get_value(row, column_map, 'payer_sort_code', '')
        payee_sort_code = self._get_value(row, column_map, 'payee_sort_code', '')
        
        # Normalize country code (GB -> GB, United Kingdom -> GB, etc.)
        if country:
            country = self._normalize_country_code(country)
        
        return {
            'id': txn_id.strip(),
            'txn_date': txn_date,
            'customer_id': customer_id,
            'direction': direction,
            'amount': amount,
            'currency': currency,
            'base_amount': amount,  # Will be converted by API if needed
            'country_iso2': country,
            'narrative': narrative.strip() if narrative else None,
            'channel': channel.strip() if channel else None,
            'payer_sort_code': payer_sort_code.strip() if payer_sort_code else None,
            'payee_sort_code': payee_sort_code.strip() if payee_sort_code else None,
        }
    
    def _get_value(self, row: Dict[str, str], column_map: Dict[str, str], field: str, default: str = None) -> str:
        """Get value from row using column map"""
        if field not in column_map:
            return default
        
        col_name = column_map[field]
        return row.get(col_name, default) or default
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string in various formats"""
        date_str = date_str.strip()
        
        # Try common formats
        formats = [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%d-%m-%Y',
            '%Y/%m/%d',
            '%d %b %Y',
            '%d %B %Y',
            '%Y-%m-%d %H:%M:%S',
            '%d/%m/%Y %H:%M:%S',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse date: {date_str}")
    
    def _normalize_country_code(self, country: str) -> str:
        """Normalize country name/code to ISO 3166-1 alpha-2"""
        country = country.strip().upper()
        
        # Common mappings
        country_map = {
            'UK': 'GB',
            'UNITED KINGDOM': 'GB',
            'ENGLAND': 'GB',
            'SCOTLAND': 'GB',
            'WALES': 'GB',
            'NORTHERN IRELAND': 'GB',
            'USA': 'US',
            'UNITED STATES': 'US',
            'AMERICA': 'US',
            'UAE': 'AE',
            'UNITED ARAB EMIRATES': 'AE',
        }
        
        # Return mapped or original
        return country_map.get(country, country[:2] if len(country) >= 2 else country)
