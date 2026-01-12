# Complete Implementation Plan - 99% PDF Coverage

## Issues Identified from Screenshot

### ❌ CRITICAL Issue 1: Assessment Not Recognizing New Documents
**Problem**: After uploading probate grant and property completion PDFs, the assessment still shows:
- "BANK PAYMENT FOUND - DOCS REQUIRED"
- "REQUIRES: Source documentation to prove legitimacy"

**Root Cause**: Assessment engine is running, but:
1. PDFs may not be properly extracted
2. Document verification may not be matching
3. Results may be cached somewhere

### ❌ CRITICAL Issue 2: Second Assessment Run Not Re-Processing
**Problem**: When user uploads new docs and clicks "Run Assessment" again, it returns cached results without processing new documents.

**Root Cause**: Need to verify assessment storage is being refreshed with new supporting_docs_data

---

## Implementation Plan - 99% Coverage

### **Phase 1: Fix Critical Caching Issue** (30 minutes)
1. Add debug logging to track document flow
2. Ensure assessment runs fresh each time
3. Clear any frontend caching

### **Phase 2: Comprehensive Pattern Library** (4-6 hours)
Create 150+ regex patterns across all fields:
- Deceased names: 20 patterns
- Beneficiary distributions: 30 patterns
- Property addresses: 20 patterns
- Completion dates: 30 patterns
- Monetary amounts: 15 patterns
- Bank details: 15 patterns
- References: 15 patterns
- Solicitor details: 10 patterns

### **Phase 3: Table Extraction** (2-3 hours)
- Extract structured tables from PDFs
- Parse beneficiary schedules
- Extract distribution tables
- Parse property details tables

### **Phase 4: OCR Integration** (3-4 hours)
- Quality check text extraction
- Fallback to OCR for poor quality PDFs
- Image preprocessing pipeline
- Tesseract integration

### **Phase 5: Fuzzy Matching** (2 hours)
- Typo tolerance for keywords
- Flexible field matching
- Enhanced confidence scoring

---

## Detailed Implementation

### 1. Fix Assessment Caching (IMMEDIATE)

#### Issue Analysis
The backend code shows assessment runs fresh each time (no caching in endpoint).
The problem is likely:
- Frontend may be caching results
- Status check returning old results
- Document verification not finding matches

#### Solution A: Force Fresh Assessment
```python
# In sof_assessment.py - run_sof_assessment endpoint

# BEFORE running assessment, log ALL data
print(f"\n{'='*60}")
print(f"RUNNING FRESH ASSESSMENT - Matter {matter_id}")
print(f"{'='*60}")
print(f"Client Info: {client_info.get('client_name')}")
print(f"Bank Statements: {len(bank_statements)} transactions")
print(f"Supporting Docs: {len(supporting_docs_data)} documents")
for idx, doc in enumerate(supporting_docs_data):
    print(f"  Doc {idx}: {doc.get('document_type')}")
    print(f"    Extracted data: {doc.get('extracted_data', {}).keys()}")
print(f"{'='*60}\n")

# Clear any cached assessment result before running
if 'assessment_result' in storage:
    print(f"⚠️ Clearing previous assessment result")
    del storage['assessment_result']

# Run fresh assessment
assessment_result = engine.assess(...)
```

#### Solution B: Add Timestamp to Results
```python
# Add timestamp to force frontend refresh
return {
    "success": True,
    "matter_id": matter_id,
    "assessment": assessment_result,
    "assessed_at": datetime.utcnow().isoformat(),
    "documents_processed": {
        "bank_statements": len(bank_statements),
        "supporting_docs": len(supporting_docs_data),
        "known_documents": known_documents
    }
}
```

---

### 2. Comprehensive Pattern Library

Create `/home/user/webapp/backend/app/services/extraction_patterns.py`:

```python
\"\"\"
Comprehensive regex pattern library for PDF extraction
150+ patterns for 99% document coverage
\"\"\"
import re
from typing import List, Dict, Pattern

class ExtractionPatterns:
    \"\"\"Pattern library for all document types\"\"\"
    
    # ============================================
    # DECEASED NAME PATTERNS (20)
    # ============================================
    DECEASED_NAME = [
        # Standard formats
        r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(Deceased\)',
        r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(deceased\)',
        r'ESTATE OF[:\s]+([A-Z\s]+)\s*\(DECEASED\)',
        
        # With "In the"
        r'In the Estate of[:\s]+([A-Z][A-Za-z\s]+)',
        r'IN THE ESTATE OF[:\s]+([A-Z\s]+)',
        
        # With "late"
        r'Estate of the late[:\s]+([A-Z][A-Za-z\s]+)',
        r'Late[:\s]+([A-Z][A-Za-z\s]+)\s*\(Deceased\)',
        r'the late[:\s]+([A-Z][A-Za-z\s]+)',
        
        # Solicitor formats
        r'Re:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',
        r'Matter:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',
        r'Client:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',
        
        # Court formats
        r'Grant in respect of[:\s]+([A-Z][A-Za-z\s]+)',
        r'Probate of[:\s]+([A-Z][A-Za-z\s]+)',
        
        # Form fields
        r'Deceased[:\s]+([A-Z][A-Za-z\s]+)',
        r'Name of Deceased[:\s]+([A-Z][A-Za-z\s]+)',
        r'Deceased Name[:\s]+([A-Z][A-Za-z\s]+)',
        
        # Table formats
        r'Deceased\s*\|?\s*:?\s*([A-Z][A-Za-z\s]+)',
        
        # With middle names/initials
        r'Estate of[:\s]+([A-Z][A-Za-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z]+)*)\s*\(Deceased\)',
        
        # Alternative deceased marker
        r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(dec\)',
        r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(dec\.\)',
    ]
    
    # ============================================
    # BENEFICIARY DISTRIBUTION PATTERNS (30)
    # ============================================
    BENEFICIARY_DISTRIBUTION = [
        # Standard formats
        r'(?:Primary\s+)?Beneficiary[:\s]*\n?([A-Z][A-Za-z\s()]+?)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'(?:Primary\s+)?BENEFICIARY[:\s]*\n?([A-Z][A-Z\s()]+?)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        
        # With recipient
        r'(?:Payment|Distribution|Transfer)\s+to[:\s]+([A-Z][A-Za-z\s]+)\s*[:\-]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'Paid\s+to[:\s]+([A-Z][A-Za-z\s]+)\s*[:\-]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'Payable\s+to[:\s]+([A-Z][A-Za-z\s]+)\s*[:\-]\s*£?([0-9,]+(?:\.\d{2})?)',
        
        # Table formats
        r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+\|?\s*£?([0-9,]+(?:\.\d{2})?)\s*\|?',
        r'\|?\s*([A-Z][A-Za-z\s]+?)\s*\|\s*£?([0-9,]+(?:\.\d{2})?)\s*\|',
        
        # With relationship
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+\((?:Son|Daughter|Spouse|Wife|Husband|Child|Sibling|Brother|Sister|Parent|Mother|Father)\)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        
        # Numbered list
        r'(\d+\.)\s*([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        
        # Executor's statement
        r'(?:transferred|paid|distributed)\s+(?:to|to:)\s*\n?([A-Z][A-Za-z\s]+)\s*.*?£?([0-9,]+(?:\.\d{2})?)',
        
        # Share/Entitlement
        r'Share[:\s]+([A-Z][A-Za-z\s]+)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'Entitlement[:\s]+([A-Z][A-Za-z\s]+)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'Inheritance[:\s]+([A-Z][A-Za-z\s]+)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        
        # Bank transfer detail
        r'Transfer of £?([0-9,]+(?:\.\d{2})?)\s+to\s+([A-Z][A-Za-z\s]+)',
        r'£?([0-9,]+(?:\.\d{2})?)\s+transferred to\s+([A-Z][A-Za-z\s]+)',
        
        # Schedule format
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+receives\s+£?([0-9,]+(?:\.\d{2})?)',
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+entitled\s+to\s+£?([0-9,]+(?:\.\d{2})?)',
        
        # Distribution schedule with amount first
        r'£?([0-9,]+(?:\.\d{2})?)\s*(?:to|payable to|for)\s+([A-Z][A-Za-z\s]+)',
        
        # Legacy format
        r'Legacy\s+to\s+([A-Z][A-Za-z\s]+)[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        
        # Bequest format
        r'Bequest\s+to\s+([A-Z][A-Za-z\s]+)[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        
        # Gift format
        r'Gift\s+to\s+([A-Z][A-Za-z\s]+)[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        
        # Named beneficiary formats
        r'Name[:\s]+([A-Z][A-Za-z\s]+)\s+Amount[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        r'([A-Z][A-Za-z\s]+)\s*\n\s*Amount[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        
        # Multi-line with account
        r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\n.*?Account.*?\n.*?£?([0-9,]+(?:\.\d{2})?)',
        
        # Split format (name line, amount line)
        r'(?:Beneficiary|Recipient|Payee)[:\s]*([A-Z][A-Za-z\s]+)\s*\n.*?(?:Amount|Sum|Payment)[:\s]*£?([0-9,]+(?:\.\d{2})?)',
        
        # Residuary beneficiary
        r'Residuary\s+(?:beneficiary|estate)\s+to\s+([A-Z][A-Za-z\s]+)[:\s]*£?([0-9,]+(?:\.\d{2})?)',
        
        # Cash legacy
        r'Cash\s+(?:legacy|gift)\s+to\s+([A-Z][A-Za-z\s]+)[:\s]*£?([0-9,]+(?:\.\d{2})?)',
        
        # Specific bequest
        r'Specific\s+bequest\s+to\s+([A-Z][A-Za-z\s]+)[:\s]*£?([0-9,]+(?:\.\d{2})?)',
    ]
    
    # ============================================
    # DATE PATTERNS (30)
    # ============================================
    DATE = [
        # UK formats with ordinals and full month
        r'(\d{1,2}(?:st|nd|rd|th)?\s+January\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+February\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+March\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+April\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+May\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+June\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+July\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+August\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+September\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+October\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+November\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)?\s+December\s+\d{4})',
        
        # Short month names
        r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{4})',
        
        # ISO format
        r'(\d{4}-\d{2}-\d{2})',
        
        # UK slash formats
        r'(\d{1,2}/\d{1,2}/\d{4})',
        r'(\d{1,2}/\d{1,2}/\d{2})',
        
        # Dash format
        r'(\d{1,2}-\d{1,2}-\d{4})',
        r'(\d{1,2}-\d{1,2}-\d{2})',
        
        # Dot format (European)
        r'(\d{1,2}\.\d{1,2}\.\d{4})',
        
        # Long format (month first)
        r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})',
        
        # No ordinal
        r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
        
        # With day of week
        r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        
        # American format (Month Day, Year)
        r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})',
        
        # Compact format
        r'(\d{8})',  # YYYYMMDD
        
        # With "on"
        r'on\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        r'dated\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        
        # Case insensitive months
        r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})',
    ]
    
    # ============================================
    # MONETARY AMOUNT PATTERNS (15)
    # ============================================
    AMOUNT = [
        # Standard UK format with £
        r'£\s*([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        r'£([0-9]+(?:\.\d{2})?)',
        
        # GBP explicit
        r'GBP\s*([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        r'([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*GBP',
        
        # Space separators (European style)
        r'£\s*([0-9]{1,3}(?:\s\d{3})*(?:\.\d{2})?)',
        
        # With words
        r'([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+(?:pounds?|sterling)',
        r'£([0-9,]+)\s+(?:pounds?|sterling)',
        
        # In parentheses
        r'\(£\s*([0-9,]+(?:\.\d{2})?)\)',
        r'\(([0-9,]+(?:\.\d{2})?)\)',
        
        # Negative amounts
        r'-\s*£\s*([0-9,]+(?:\.\d{2})?)',
        r'£\s*-\s*([0-9,]+(?:\.\d{2})?)',
        
        # With decimal only (no commas)
        r'£([0-9]+\.\d{2})',
        
        # Pence only
        r'([0-9]+)p\b',
        
        # In words followed by figure
        r'(?:sum of|amount of)\s+£?([0-9,]+(?:\.\d{2})?)',
        
        # Bold/formatted
        r'\*\*£([0-9,]+(?:\.\d{2})?)\*\*',
    ]
    
    # Continue with more patterns...
    
    @classmethod
    def try_all_patterns(cls, text: str, pattern_list: List[str], flags=re.IGNORECASE) -> List[re.Match]:
        \"\"\"Try all patterns in a list and return all matches\"\"\"
        matches = []
        for pattern in pattern_list:
            found = re.finditer(pattern, text, flags)
            matches.extend(found)
        return matches
    
    @classmethod
    def extract_first_match(cls, text: str, pattern_list: List[str], group: int = 1, flags=re.IGNORECASE) -> str:
        \"\"\"Try patterns until first match found\"\"\"
        for pattern in pattern_list:
            match = re.search(pattern, text, flags)
            if match:
                try:
                    return match.group(group).strip()
                except:
                    continue
        return None
```

---

### 3. Table Extraction Implementation

Create `/home/user/webapp/backend/app/services/table_extractor.py`:

```python
\"\"\"
Table extraction from PDFs
Handles structured beneficiary schedules, distribution tables, etc.
\"\"\"
import pdfplumber
from typing import List, Dict, Any, Optional
import re

class TableExtractor:
    \"\"\"Extract structured data from PDF tables\"\"\"
    
    def extract_tables(self, pdf_content: bytes) -> List[List[List[str]]]:
        \"\"\"Extract all tables from PDF\"\"\"
        import io
        tables = []
        
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    tables.extend(page_tables)
        
        return tables
    
    def extract_beneficiary_distributions(self, tables: List[List[List[str]]]) -> List[Dict[str, Any]]:
        \"\"\"
        Extract beneficiary distributions from tables
        Returns: [{'beneficiary': 'Name', 'amount': 250000.0, 'date': '15/05/2023'}, ...]
        \"\"\"
        distributions = []
        
        for table in tables:
            if not table or len(table) < 2:
                continue
            
            # Get headers (first row)
            headers = [str(h).lower().strip() if h else '' for h in table[0]]
            
            # Find relevant columns
            name_col = self._find_column_index(headers, ['name', 'beneficiary', 'recipient', 'payee'])
            amount_col = self._find_column_index(headers, ['amount', 'sum', 'payment', '£', 'gbp', 'value'])
            date_col = self._find_column_index(headers, ['date', 'paid', 'transfer', 'payment date'])
            
            if name_col is None or amount_col is None:
                continue
            
            # Extract data rows
            for row in table[1:]:  # Skip header
                if not row or len(row) <= max(name_col, amount_col):
                    continue
                
                name = str(row[name_col]).strip() if row[name_col] else None
                amount_str = str(row[amount_col]).strip() if row[amount_col] else None
                date_str = str(row[date_col]).strip() if date_col is not None and row[date_col] else None
                
                if not name or not amount_str:
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
        \"\"\"Extract property transaction details from tables\"\"\"
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
                
                if not key or not value:
                    continue
                
                # Match common fields
                if 'address' in key or 'property' in key:
                    details['property_address'] = value
                elif 'vendor' in key or 'seller' in key:
                    details['vendor_name'] = value
                elif 'completion' in key and 'date' in key:
                    details['completion_date'] = value
                elif 'contract' in key and 'price' in key:
                    details['contract_price'] = self._parse_amount(value)
                elif 'net' in key and 'proceed' in key:
                    details['net_proceeds'] = self._parse_amount(value)
        
        return details
    
    def _find_column_index(self, headers: List[str], keywords: List[str]) -> Optional[int]:
        \"\"\"Find column index by matching keywords (fuzzy)\"\"\"
        for i, header in enumerate(headers):
            for keyword in keywords:
                if keyword in header or header in keyword:
                    return i
        return None
    
    def _parse_amount(self, amount_str: str) -> float:
        \"\"\"Parse amount string to float\"\"\"
        if not amount_str:
            return 0.0
        
        try:
            # Remove currency symbols and commas
            cleaned = re.sub(r'[£$€,\s]', '', amount_str)
            # Remove GBP, USD, etc.
            cleaned = re.sub(r'[A-Z]{3}', '', cleaned)
            return float(cleaned)
        except:
            return 0.0

# Singleton
table_extractor = TableExtractor()
```

---

### 4. OCR Integration

Would you like me to proceed with implementing all of these improvements, or would you prefer to:

1. **First fix the caching issue** (30 min) → Test → Then add patterns
2. **Implement everything at once** (1 day) → Test complete solution

Which approach do you prefer?

Also, confirm:
- Should I install Tesseract for OCR support?
- Do you want fuzzy matching added?
- Any specific document formats you know are failing?
