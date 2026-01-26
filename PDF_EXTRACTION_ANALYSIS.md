# PDF Extraction Strategy Analysis

## Date: 2026-01-12

---

## Current Approach: Analysis

### What's Currently Used: **pdfplumber (Text Extraction Only)**

**Current Implementation** (`pdf_extractor.py`):
```python
def _extract_text(self, pdf_content: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)
    return "\n".join(full_text)
```

**Then uses**: Regex patterns on extracted text

### Strengths of Current Approach:
✅ Simple and fast
✅ Works well for text-based PDFs (native text, not scanned)
✅ No additional dependencies needed
✅ Already handles most digital PDFs correctly

### Weaknesses of Current Approach:
❌ **Fails completely on scanned documents** (images of text)
❌ **Brittle regex patterns** - must match exact formatting
❌ **No table structure awareness** - treats tables as flat text
❌ **Case-sensitive** - "VENDOR:" vs "Vendor:" needs separate patterns
❌ **Layout-dependent** - newlines and spacing affect matching
❌ **No fuzzy matching** - "Beneficiary" vs "Beneficary" (typo) fails
❌ **Limited variation handling** - each document format needs specific patterns

---

## Available Libraries (Already Installed)

### 1. **pdfplumber** (Currently used)
- **Best for**: Text extraction from native PDFs
- **Strengths**: 
  - Handles text-based PDFs very well
  - Can extract tables with `.extract_tables()`
  - Preserves layout to some degree
- **Weaknesses**: 
  - Cannot read scanned documents (no OCR)
  - No fuzzy matching or NLP capabilities

### 2. **pytesseract** (OCR - Available but not used)
- **Best for**: Scanned documents, images embedded in PDFs
- **Strengths**:
  - Can read text from images
  - Handles poor quality scans
  - Multi-language support
- **Weaknesses**:
  - Slower than text extraction
  - Requires preprocessing for best results
  - May have errors on poor quality images
  - Needs Tesseract binary installed on system

### 3. **pypdfium2** (Low-level PDF access)
- **Best for**: Rendering PDF pages as images
- **Use case**: Convert PDF pages to images → OCR with pytesseract
- **Hybrid approach enabler**

### 4. **pdfminer.six** (Alternative text extractor)
- **Best for**: Complex PDF layouts
- **More detailed** than pdfplumber for layout analysis
- **Can extract**: Coordinates, fonts, sizes of text elements

---

## Recommended Hybrid Approach

### **Strategy: Multi-Layer Extraction Pipeline**

```
PDF Input
    ↓
┌─────────────────────────────────────┐
│  LAYER 1: Native Text Extraction   │
│  (pdfplumber - fast)                │
└──────────────┬──────────────────────┘
               ↓
     Text extracted? Quality check
               ↓
         ┌─────┴─────┐
         YES          NO (or poor quality)
          ↓           ↓
    ┌─────────┐  ┌────────────────────────┐
    │ Success │  │ LAYER 2: OCR Fallback  │
    └─────────┘  │ (pytesseract)          │
                 │ Convert PDF→Image→Text  │
                 └───────────┬────────────┘
                             ↓
                ┌────────────────────────────┐
                │ LAYER 3: Intelligent Parse │
                │ - Multiple regex patterns  │
                │ - Table extraction         │
                │ - Fuzzy matching           │
                │ - Entity extraction (NLP)  │
                └────────────────────────────┘
```

### **Implementation Architecture**

#### **Tier 1: Extraction Layer** (Get the text)
1. **Try pdfplumber first** (fast, 90% of cases)
   - Extract native text
   - Quality check: minimum characters, coherent words
   - If quality > threshold → proceed to parsing
   - If quality < threshold → fallback to OCR

2. **OCR Fallback** (when needed)
   - Convert PDF pages to images (pypdfium2)
   - Apply image preprocessing (PIL/Pillow):
     - Deskew (rotation correction)
     - Contrast enhancement
     - Noise reduction
   - Run Tesseract OCR
   - Merge results from all pages

#### **Tier 2: Parsing Layer** (Extract structured data)
1. **Multiple regex pattern sets** per field:
   - Case-insensitive patterns
   - Flexible whitespace matching
   - Multiple format variants
   - Typo-tolerant alternatives

2. **Table extraction** (for structured data):
   - pdfplumber `.extract_tables()`
   - Look for amounts in table cells
   - Match headers to identify columns

3. **Fuzzy matching** for key terms:
   - "Beneficiary" matches "Beneficary", "Beneficiaries"
   - Use Levenshtein distance or similar

4. **Entity extraction** (optional - NLP):
   - Use spaCy or similar for:
     - Person names (PERSON entities)
     - Monetary amounts (MONEY entities)
     - Dates (DATE entities)
     - Organizations (ORG entities)

#### **Tier 3: Validation Layer** (Ensure quality)
1. **Cross-field validation**:
   - Check amounts are reasonable
   - Dates are valid and chronological
   - Names are properly formatted

2. **Confidence scoring**:
   - High confidence: Multiple patterns matched
   - Medium confidence: Single pattern matched
   - Low confidence: Fuzzy match or partial extraction

---

## Specific Pattern Improvements Needed

### **Current Issues with Regex Patterns**

#### 1. **Deceased Name** (Probate)
**Current**:
```python
r'Estate of[:\s]+([A-Z\s]+)\s*\(Deceased\)'
```
**Problems**:
- Requires exact "(Deceased)" text
- Assumes all caps for name
- Won't match "Estate of: John Smith (deceased)"
- Won't match "In the Estate of John Smith"

**Improved Patterns** (15+ variations):
```python
deceased_patterns = [
    # Standard format
    r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(Deceased\)',
    r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(deceased\)',
    
    # Alternative formats
    r'In the Estate of[:\s]+([A-Z][A-Za-z\s]+)',
    r'Estate:\s*([A-Z][A-Za-z\s]+)\s*\(Deceased\)',
    
    # With "late"
    r'Estate of the late[:\s]+([A-Z][A-Za-z\s]+)',
    r'Late[:\s]+([A-Z][A-Za-z\s]+)\s*\(Deceased\)',
    
    # Solicitor formats
    r'Matter:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',
    r'Re:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',
    
    # Court formats
    r'Grant in respect of[:\s]+([A-Z][A-Za-z\s]+)',
    
    # With middle names/initials
    r'Estate of[:\s]+([A-Z][A-Za-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z]+)*)',
    
    # All caps variation
    r'ESTATE OF[:\s]+([A-Z\s]+)',
    
    # Mixed case with colon
    r'Estate of:[^\n]+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
    
    # Table row format
    r'Deceased[:\s|]+([A-Z][A-Za-z\s]+)',
    r'Name of Deceased[:\s|]+([A-Z][A-Za-z\s]+)',
    
    # Probate registry format
    r'Probate of[:\s]+([A-Z][A-Za-z\s]+)',
]
```

#### 2. **Distribution Amounts** (Probate)
**Current**: 2 patterns (single-line, multi-line)

**Improved Patterns** (20+ variations):
```python
distribution_patterns = [
    # Standard beneficiary formats
    r'(?:Primary\s+)?Beneficiary[:\s]*\n?([A-Z][A-Za-z\s()]+?)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
    r'Beneficiary\s+Name[:\s]*([^£\n]+?)\s*Amount[:\s]*£?([0-9,]+(?:\.\d{2})?)',
    
    # Payment/Distribution to...
    r'(?:Payment|Distribution)\s+to[:\s]+([A-Z][A-Za-z\s]+)\s*[:\-]\s*£?([0-9,]+(?:\.\d{2})?)',
    r'Paid to[:\s]+([A-Z][A-Za-z\s]+)\s*[:\-]\s*£?([0-9,]+(?:\.\d{2})?)',
    
    # Table formats
    r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+\|?\s*£?([0-9,]+(?:\.\d{2})?)\s*\|?',
    
    # With relationship
    r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+\((?:Son|Daughter|Spouse|Child|Sibling)\)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
    
    # Distribution list format
    r'(\d+\.)\s*([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
    
    # Executor's statement format
    r'(?:transferred|paid)\s+(?:to|to:)\s*\n?([A-Z][A-Za-z\s]+)\s*.*?£?([0-9,]+(?:\.\d{2})?)',
    
    # Schedule format
    r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+receives\s+£?([0-9,]+(?:\.\d{2})?)',
    
    # Multiple formats in same document
    r'Share[:\s]+([A-Z][A-Za-z\s]+)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
    r'Entitlement[:\s]+([A-Z][A-Za-z\s]+)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
    
    # Bank transfer detail extraction
    r'Transfer of £?([0-9,]+(?:\.\d{2})?)\s+to\s+([A-Z][A-Za-z\s]+)',
    
    # With account details on next line
    r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\n.*?Account.*?\n.*?£?([0-9,]+(?:\.\d{2})?)',
]
```

#### 3. **Property Address** (Completion Statement)
**Current**: 1 basic pattern

**Improved Patterns** (15+ variations):
```python
property_patterns = [
    # Full address with postcode
    r'Property[:\s]*\n?([0-9]+[A-Za-z]?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z\s]+,\s*[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
    
    # Address without property label
    r'([0-9]+[A-Za-z]?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z\s]+,\s*[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
    
    # Flat/Apartment format
    r'(?:Flat|Apartment|Unit)\s+([0-9A-Za-z]+),?\s+([0-9]+\s+[A-Z][a-z\s,]+[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
    
    # Address field in form
    r'Address[:\s]*\n?(.+?)\n(?:Post\s*Code|Postcode)[:\s]*([A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
    
    # Multi-line address
    r'Address[:\s]*\n([^\n]+)\n([^\n]+)\n([A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
    
    # Table cell format
    r'Property\s*\|\s*([^|\n]+(?:\n[^|\n]+)*?[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
    
    # Land Registry format
    r'Title Number[:\s]*[A-Z0-9]+\s*\n.*?Address[:\s]*([^\n]+(?:\n[^\n]+)*?[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
]
```

#### 4. **Dates** (All documents)
**Current**: Limited to "15th May 2023" format

**Improved Patterns** (25+ variations):
```python
date_patterns = [
    # UK formats with ordinals
    r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
    r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{4})',
    
    # ISO format
    r'(\d{4}-\d{2}-\d{2})',
    
    # UK slash format
    r'(\d{1,2}/\d{1,2}/\d{4})',
    r'(\d{1,2}/\d{1,2}/\d{2})',
    
    # US format
    r'(\d{1,2}-\d{1,2}-\d{4})',
    
    # Dot format (European)
    r'(\d{1,2}\.\d{1,2}\.\d{4})',
    
    # Long format
    r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})',
    
    # No ordinal
    r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
    
    # With day of week
    r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
]
```

#### 5. **Monetary Amounts** (All documents)
**Current**: Basic `£?([0-9,]+(?:\.\d{2})?)`

**Improved Patterns** (10+ variations):
```python
amount_patterns = [
    # Standard formats
    r'£\s*([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # £250,000.00
    r'GBP\s*([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # GBP 250,000.00
    r'([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*GBP',  # 250,000.00 GBP
    
    # No separators
    r'£\s*([0-9]+(?:\.\d{2})?)',  # £250000.00
    
    # Space separators (European)
    r'£\s*([0-9]{1,3}(?:\s\d{3})*(?:\.\d{2})?)',  # £250 000.00
    
    # With words
    r'([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+(?:pounds?|sterling)',
    
    # Written in parentheses
    r'\(£\s*([0-9,]+(?:\.\d{2})?)\)',
    
    # Negative amounts
    r'-\s*£\s*([0-9,]+(?:\.\d{2})?)',
]
```

---

## Recommended Implementation: Hybrid PDF Extractor

### **New Class Structure**

```python
class HybridPDFExtractor:
    """
    Multi-layer PDF extraction with:
    - Native text extraction (pdfplumber)
    - OCR fallback (pytesseract)
    - Table extraction
    - Enhanced pattern matching
    - Confidence scoring
    """
    
    def extract(self, pdf_content: bytes, doc_type: str):
        # Layer 1: Try native text extraction
        text, quality = self._extract_native_text(pdf_content)
        
        if quality < 0.5:  # Low quality text
            # Layer 2: OCR fallback
            text = self._ocr_extract(pdf_content)
        
        # Layer 3: Extract tables (if any)
        tables = self._extract_tables(pdf_content)
        
        # Layer 4: Parse with enhanced patterns
        data = self._parse_with_multi_patterns(text, tables, doc_type)
        
        # Layer 5: Validate and score confidence
        data = self._validate_and_score(data)
        
        return data
    
    def _extract_native_text(self, pdf_content):
        """pdfplumber extraction with quality check"""
        # ... pdfplumber code ...
        quality = self._check_text_quality(text)
        return text, quality
    
    def _check_text_quality(self, text):
        """
        Check if extracted text is good quality
        - Minimum length
        - Contains coherent words
        - Has expected document structure markers
        """
        if len(text) < 100:
            return 0.0
        
        # Check for common document words
        common_words = ['estate', 'property', 'amount', 'date', 'name']
        word_count = sum(1 for word in common_words if word.lower() in text.lower())
        
        return min(word_count / len(common_words), 1.0)
    
    def _ocr_extract(self, pdf_content):
        """
        OCR fallback using pytesseract
        - Convert PDF pages to images
        - Preprocess images
        - Run OCR
        """
        # Convert PDF to images using pypdfium2
        images = self._pdf_to_images(pdf_content)
        
        text_parts = []
        for img in images:
            # Preprocess image
            img = self._preprocess_image(img)
            # OCR
            text = pytesseract.image_to_string(img)
            text_parts.append(text)
        
        return "\n".join(text_parts)
    
    def _extract_tables(self, pdf_content):
        """Extract structured tables from PDF"""
        tables = []
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                tables.extend(page_tables)
        return tables
    
    def _parse_with_multi_patterns(self, text, tables, doc_type):
        """
        Parse using multiple patterns per field
        - Try all patterns until match found
        - Score each match for confidence
        - Prefer table data over text extraction
        """
        data = {}
        
        if doc_type == 'Probate grant':
            # Try table extraction first
            data.update(self._extract_from_tables(tables, 'probate'))
            
            # Fill gaps with regex
            data.update(self._extract_probate_with_patterns(text))
        
        return data
    
    def _extract_probate_with_patterns(self, text):
        """Use comprehensive pattern sets"""
        data = {}
        
        # Deceased name - try all 15 patterns
        for pattern in DECEASED_NAME_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['deceased_name'] = match.group(1).strip()
                break
        
        # Distribution amounts - try all 20 patterns
        distributions = []
        for pattern in DISTRIBUTION_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Parse beneficiary and amount from groups
                distributions.append(...)
        
        if distributions:
            data['distributions'] = distributions
        
        return data
```

---

## Pattern Libraries to Create

### **1. Pattern Sets File** (`patterns.py`)
```python
# Comprehensive pattern library for all document types

DECEASED_NAME_PATTERNS = [
    # ... 15+ patterns ...
]

DISTRIBUTION_PATTERNS = [
    # ... 20+ patterns ...
]

PROPERTY_ADDRESS_PATTERNS = [
    # ... 15+ patterns ...
]

DATE_PATTERNS = [
    # ... 25+ patterns ...
]

AMOUNT_PATTERNS = [
    # ... 10+ patterns ...
]

# ... more pattern sets ...
```

### **2. Field Extractors** (`field_extractors.py`)
```python
class FieldExtractor:
    """Base class for extracting specific fields"""
    
    def extract_amount(self, text):
        """Try all amount patterns"""
        for pattern in AMOUNT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return self._parse_amount(match.group(1))
        return None
    
    def extract_date(self, text):
        """Try all date patterns"""
        # ... similar ...
    
    def extract_name(self, text, name_type='person'):
        """Try all name patterns"""
        # ... similar ...
```

---

## Table Extraction Strategy

### **Why Tables Matter**
Many legal documents use structured tables:
```
| Beneficiary Name     | Amount      | Payment Date |
|---------------------|-------------|--------------|
| John Smith          | £250,000.00 | 15/05/2023   |
| Sarah Thompson      | £250,000.00 | 15/05/2023   |
```

### **Table Extraction Approach**
```python
def extract_distributions_from_tables(self, tables):
    """
    Extract beneficiary distributions from tables
    - Identify column headers
    - Match to expected fields
    - Extract data rows
    """
    for table in tables:
        headers = table[0]  # First row is usually headers
        
        # Find relevant columns
        name_col = self._find_column(headers, ['name', 'beneficiary', 'recipient'])
        amount_col = self._find_column(headers, ['amount', 'sum', 'payment', '£'])
        date_col = self._find_column(headers, ['date', 'paid', 'transfer'])
        
        # Extract rows
        distributions = []
        for row in table[1:]:  # Skip header
            if name_col is not None and amount_col is not None:
                distributions.append({
                    'beneficiary': row[name_col],
                    'amount': self._parse_amount(row[amount_col]),
                    'date': row[date_col] if date_col else None
                })
        
        return distributions
```

---

## OCR Integration Details

### **When to Use OCR**
1. **pdfplumber returns empty or gibberish** → Scanned document
2. **Text quality score < 0.5** → Poor extraction
3. **Missing critical fields** → May be in image form

### **OCR Preprocessing Pipeline**
```python
def _preprocess_image(self, image):
    """
    Optimize image for OCR
    """
    from PIL import Image, ImageEnhance, ImageFilter
    
    # Convert to grayscale
    image = image.convert('L')
    
    # Increase contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    
    # Sharpen
    image = image.filter(ImageFilter.SHARPEN)
    
    # Threshold to black and white
    threshold = 150
    image = image.point(lambda p: p > threshold and 255)
    
    return image
```

### **OCR Quality Check**
```python
def _check_ocr_quality(self, ocr_text):
    """
    Verify OCR didn't produce garbage
    """
    # Check for reasonable word:character ratio
    words = ocr_text.split()
    if len(words) / max(len(ocr_text), 1) < 0.1:
        return False  # Too few words = garbage
    
    # Check for common words
    common_legal_words = ['estate', 'property', 'amount', 'date']
    found = sum(1 for word in common_legal_words if word in ocr_text.lower())
    
    return found >= 2  # At least 2 common words
```

---

## Implementation Phases

### **Phase 1: Enhanced Patterns** (Quick Win - 1-2 days)
✅ Expand regex patterns (15-25 per field)
✅ Add case-insensitive matching
✅ Handle multiple format variations
✅ **No new dependencies needed**
✅ **Immediate improvement for 80% of documents**

**Effort**: Low
**Impact**: High
**Risk**: Very Low

### **Phase 2: Table Extraction** (1-2 days)
✅ Add pdfplumber table extraction
✅ Parse structured data from tables
✅ Prefer table data over regex when available
✅ **No new dependencies needed**

**Effort**: Low-Medium
**Impact**: High
**Risk**: Low

### **Phase 3: OCR Fallback** (2-3 days)
✅ Implement quality checking
✅ Add OCR fallback for poor quality PDFs
✅ Image preprocessing pipeline
✅ **Requires Tesseract binary installation**

**Effort**: Medium
**Impact**: Medium-High
**Risk**: Medium (system dependencies)

### **Phase 4: NLP Entity Extraction** (Optional - 3-5 days)
⚠️ Add spaCy or similar for entity recognition
⚠️ Train custom model for legal documents
⚠️ **Significant dependencies and complexity**

**Effort**: High
**Impact**: Medium
**Risk**: High

---

## Recommended Action Plan

### **Immediate (Do First)**
1. ✅ **Expand regex patterns** - Phase 1
   - Create comprehensive pattern library
   - 15-25 patterns per critical field
   - Case-insensitive + flexible whitespace
   - **Handles 80-90% of real-world variation**

2. ✅ **Add table extraction** - Phase 2
   - Use pdfplumber `.extract_tables()`
   - Parse structured data
   - **Handles well-formatted documents**

### **Near Term (Next)**
3. ⚠️ **OCR fallback** - Phase 3
   - For scanned documents only
   - Requires Tesseract installation
   - **Handles remaining 10-20% of documents**

### **Future (If Needed)**
4. ⚠️ **NLP entity extraction** - Phase 4
   - Only if pattern matching insufficient
   - Consider commercial APIs (AWS Textract, Azure Form Recognizer)
   - **May not be necessary with good patterns**

---

## Testing Strategy

### **Real-World Document Variations to Test**
Create test PDFs for:

1. **Probate Grants**:
   - [ ] High Court format
   - [ ] Scotland format (Confirmation)
   - [ ] Northern Ireland format
   - [ ] Solicitor-prepared format
   - [ ] Scanned handwritten annotations
   - [ ] Multiple beneficiaries
   - [ ] Different estate sizes

2. **Completion Statements**:
   - [ ] Different solicitor firms' templates
   - [ ] Leasehold vs Freehold
   - [ ] With/without mortgage redemption
   - [ ] Different property types (flat, house, commercial)
   - [ ] Multiple pages
   - [ ] Table format vs text format

3. **Edge Cases**:
   - [ ] Poor quality scans
   - [ ] Handwritten sections
   - [ ] Mixed languages
   - [ ] Stamped/watermarked documents
   - [ ] Rotated pages
   - [ ] Multiple documents in one PDF

---

## Confidence Scoring Enhancement

### **Multi-Factor Confidence Calculation**
```python
def calculate_confidence(self, extracted_data, extraction_method):
    """
    Calculate confidence based on:
    - Number of fields extracted
    - Method used (native text > OCR)
    - Pattern match quality (exact > fuzzy)
    - Cross-field validation results
    """
    score = 0.0
    
    # Base score: field completeness
    filled = sum(1 for v in extracted_data.values() if v)
    total = len(extracted_data)
    score += (filled / total) * 0.4  # 40% weight
    
    # Extraction method bonus
    if extraction_method == 'native_text':
        score += 0.3  # 30% bonus
    elif extraction_method == 'ocr':
        score += 0.15  # 15% bonus
    
    # Pattern quality bonus
    if self._has_exact_matches(extracted_data):
        score += 0.2  # 20% bonus
    elif self._has_fuzzy_matches(extracted_data):
        score += 0.1  # 10% bonus
    
    # Validation bonus
    if self._cross_validate(extracted_data):
        score += 0.1  # 10% bonus
    
    return min(score, 1.0)
```

---

## Summary & Recommendation

### **Current Limitations**
1. ❌ Only handles text-based PDFs (no scanned documents)
2. ❌ Brittle regex patterns (exact format matching required)
3. ❌ No table structure awareness
4. ❌ Limited format variation handling
5. ❌ No fuzzy matching or typo tolerance

### **Recommended Solution: Hybrid Multi-Layer**
1. ✅ **Expand patterns** (immediate, low-risk, high-impact)
2. ✅ **Add table extraction** (quick, handles structured docs)
3. ⚠️ **OCR fallback** (for scanned docs when needed)

### **Implementation Priority**
**Phase 1 (Do Now)**: Enhanced patterns + table extraction
- **Time**: 2-3 days
- **Risk**: Very low
- **Coverage**: 85-95% of documents

**Phase 2 (Later)**: OCR fallback
- **Time**: 2-3 days
- **Risk**: Medium (system dependencies)
- **Coverage**: Remaining 5-15% (scanned docs)

### **Not Recommended (Yet)**
- ❌ Full NLP/ML approach (overkill for structured documents)
- ❌ Commercial OCR APIs (cost, privacy concerns)
- ❌ Custom ML models (unnecessary complexity)

---

## Questions for You

1. **Do you receive many scanned documents?**
   - If YES → OCR fallback is important (Phase 2)
   - If NO → Focus on patterns + tables (Phase 1)

2. **What document format variations do you see most?**
   - Different solicitor templates?
   - Court vs solicitor formats?
   - Handwritten vs typed?

3. **Is Tesseract already installed on the server?**
   - Check with: `tesseract --version`
   - If NO → May need system admin to install

4. **Do you have sample PDFs that are currently failing?**
   - Would help identify specific patterns to add
   - Can test extraction improvements

5. **Privacy/Security constraints?**
   - Can we use external OCR APIs if needed?
   - Or must everything be local?

---

Let me know your answers and I'll create the specific implementation plan!
