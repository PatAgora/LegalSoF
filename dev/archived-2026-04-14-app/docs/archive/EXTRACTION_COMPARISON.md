# PDF Extraction Approach Comparison

## Quick Summary

| Approach | Coverage | Speed | Complexity | Risk | Recommendation |
|----------|----------|-------|------------|------|----------------|
| **Current (pdfplumber + basic regex)** | 60-70% | ⚡⚡⚡ Fast | ✅ Simple | ✅ Very Low | ❌ Insufficient |
| **Enhanced Patterns** | 85-95% | ⚡⚡⚡ Fast | ✅ Simple | ✅ Very Low | ✅ **Do First** |
| **+ Table Extraction** | 90-95% | ⚡⚡ Fast | ✅ Simple | ✅ Low | ✅ **Do Second** |
| **+ OCR Fallback** | 95-99% | ⚡ Slower | ⚠️ Medium | ⚠️ Medium | ⚠️ If Needed |
| **NLP/ML Approach** | 98-99% | ⚡ Slow | ❌ Complex | ❌ High | ❌ Not Now |

---

## Current System Analysis

### What You Have Now
```
PDF → pdfplumber text extraction → Basic regex (2-3 patterns per field) → Done
```

### Current Regex Pattern Count
- **Deceased name**: 1 pattern
- **Distribution amounts**: 2 patterns (just fixed)
- **Dates**: 2 patterns
- **Property address**: 2 patterns
- **Bank details**: 1 pattern each
- **Total**: ~15 patterns across all fields

### Problems with Current Approach
1. **Too Few Patterns**: Each field has 1-2 patterns, real documents have 10-20 variations
2. **Case Sensitive**: "VENDOR" ≠ "Vendor" ≠ "vendor"
3. **Exact Whitespace**: "Estate of: Name" ≠ "Estate of:Name"
4. **No Table Support**: Tables treated as unstructured text
5. **No OCR**: Scanned documents return empty
6. **No Fuzzy Match**: "Beneficiary" ≠ "Beneficary" (typo)

### Current Success Rate (Estimated)
- ✅ **60-70%** of PDFs fully extracted
- ⚠️ **20-25%** partially extracted (missing some fields)
- ❌ **10-15%** failed extraction (scanned docs, unusual formats)

---

## Approach 1: Enhanced Patterns (Recommended - Do First)

### What Changes
```
PDF → pdfplumber text extraction → COMPREHENSIVE regex (15-25 patterns per field) → Done
```

### Pattern Expansion Example

**Before (Deceased Name)**:
```python
# 1 pattern
r'Estate of[:\s]+([A-Z\s]+)\s*\(Deceased\)'
```
Matches: "Estate of JOHN SMITH (Deceased)"
Misses:
- "Estate of: John Smith (deceased)" ← lowercase
- "In the Estate of John Smith" ← different wording
- "Estate of the late John Smith" ← "late" variant
- "Re: Estate of John Smith" ← solicitor format

**After (Deceased Name)**:
```python
# 15 patterns
deceased_patterns = [
    r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(Deceased\)',  # Original
    r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(deceased\)',  # Lowercase
    r'In the Estate of[:\s]+([A-Z][A-Za-z\s]+)',          # "In the" variant
    r'Estate of the late[:\s]+([A-Z][A-Za-z\s]+)',        # "late" variant
    r'Estate:\s*([A-Z][A-Za-z\s]+)\s*\(Deceased\)',       # Colon format
    r'Re:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',           # Solicitor format
    r'Matter:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',       # Matter ref
    r'Grant in respect of[:\s]+([A-Z][A-Za-z\s]+)',       # Court format
    r'Deceased[:\s]+([A-Z][A-Za-z\s]+)',                  # Simple format
    r'Name of Deceased[:\s]+([A-Z][A-Za-z\s]+)',          # Form field
    r'ESTATE OF[:\s]+([A-Z\s]+)',                         # All caps
    # ... more patterns ...
]
```
Matches: All of the above plus many more variations!

### Coverage Improvement
- **Before**: 60-70% of documents
- **After**: 85-95% of documents
- **Improvement**: +25-30 percentage points

### Benefits
✅ **No new dependencies** - uses existing libraries
✅ **Fast** - regex is very fast
✅ **Low risk** - just better patterns
✅ **Easy to test** - run existing test script
✅ **Immediate improvement** - works on next PDF upload
✅ **Easy to maintain** - add patterns as needed

### Drawbacks
❌ Still won't handle scanned documents (OCR needed)
❌ Needs comprehensive testing with real documents
❌ Pattern library becomes larger

### Implementation Effort
- **Time**: 1-2 days
- **Complexity**: Low
- **Code changes**: Expand pattern arrays in `pdf_extractor.py`
- **Testing**: Use existing test script

---

## Approach 2: Add Table Extraction

### What Changes
```
PDF → pdfplumber text + TABLE extraction → Parse both → Merge results → Done
```

### Why Tables Matter

Many legal documents use structured tables:

**Probate Grant - Beneficiary Schedule**:
```
+-------------------------+--------------+-------------+
| Beneficiary Name        | Amount       | Date        |
+-------------------------+--------------+-------------+
| John David Smith        | £250,000.00  | 15/05/2023  |
| Sarah Jane Thompson     | £250,000.00  | 15/05/2023  |
| Emily Rose Smith        | £80,000.00   | 15/05/2023  |
+-------------------------+--------------+-------------+
```

**Current Approach**: Tries to parse this with regex on flat text
**With Table Extraction**: Parses as structured data (columns + rows)

### Table Extraction Process
```python
# Extract tables
tables = page.extract_tables()

# Identify columns
headers = table[0]
name_col = find_column(headers, ['name', 'beneficiary'])
amount_col = find_column(headers, ['amount', '£', 'sum'])
date_col = find_column(headers, ['date', 'paid'])

# Extract rows
for row in table[1:]:
    beneficiary = row[name_col]
    amount = parse_amount(row[amount_col])
    date = row[date_col]
```

### Coverage Improvement
- **Before** (patterns only): 85-95%
- **After** (patterns + tables): 90-95%
- **Improvement**: +5-10 percentage points (for table-heavy docs)

### Benefits
✅ **More accurate** - structured data is cleaner than regex
✅ **Handles multi-row data** - easy to extract all beneficiaries
✅ **No new dependencies** - pdfplumber already does this
✅ **Fast** - table extraction is fast
✅ **Robust** - less brittle than regex

### Drawbacks
❌ Not all documents use tables
❌ Table formats vary (need column detection)
❌ Some PDFs have malformed tables

### Implementation Effort
- **Time**: 1-2 days
- **Complexity**: Low-Medium
- **Code changes**: Add table extraction methods
- **Testing**: Create test docs with tables

---

## Approach 3: OCR Fallback (For Scanned Documents)

### What Changes
```
PDF → Try pdfplumber text extraction
      ↓ (if quality < threshold)
      Convert to images → Preprocess → Tesseract OCR → Continue as normal
```

### When OCR Triggers
1. **Empty text extraction** → Likely scanned document
2. **Low quality score** → Gibberish text extracted
3. **Missing all critical fields** → Format not recognized

### OCR Pipeline
```
PDF → pypdfium2 (render page to image)
    → PIL preprocessing (contrast, sharpen, threshold)
    → Tesseract OCR (extract text from image)
    → Continue with pattern matching
```

### Example Quality Check
```python
def check_text_quality(text):
    if len(text) < 100:
        return 0.0  # Too short
    
    # Check for common legal words
    words = ['estate', 'property', 'amount', 'beneficiary', 'date']
    found = sum(1 for w in words if w.lower() in text.lower())
    
    if found < 2:
        return 0.0  # Probably gibberish
    
    # Check word:char ratio
    word_count = len(text.split())
    char_count = len(text)
    ratio = word_count / max(char_count, 1)
    
    if ratio < 0.08:  # Less than 8% is unusual
        return 0.5  # Suspicious
    
    return 1.0  # Good quality
```

### Coverage Improvement
- **Before** (patterns + tables): 90-95%
- **After** (+ OCR): 95-99%
- **Improvement**: +5-10 percentage points (for scanned docs)

### Benefits
✅ **Handles scanned documents** - main benefit
✅ **Handles poor quality PDFs**
✅ **Fallback mechanism** - only used when needed
✅ **Preprocessing improves accuracy**

### Drawbacks
❌ **Requires Tesseract binary** - system dependency
❌ **Slower** - OCR takes 2-5 seconds per page
❌ **Less accurate** - OCR has ~95% accuracy vs 99.9% for native text
❌ **More complex** - image processing, error handling

### System Requirements
**Tesseract Installation**:
- Ubuntu/Debian: `apt-get install tesseract-ocr`
- MacOS: `brew install tesseract`
- Already have `pytesseract` Python library installed
- **Current Status**: ❌ Tesseract binary NOT installed

### Implementation Effort
- **Time**: 2-3 days
- **Complexity**: Medium
- **Code changes**: Add OCR layer, image preprocessing, quality checking
- **System**: Need Tesseract installed (requires admin/DevOps)
- **Testing**: Need scanned document samples

---

## Approach 4: NLP/ML Entity Extraction (Not Recommended)

### What It Is
Use machine learning to identify entities:
- spaCy NER (Named Entity Recognition)
- Custom trained models
- Or commercial APIs (AWS Textract, Azure Form Recognizer)

### Example
```python
import spacy
nlp = spacy.load("en_core_web_sm")

doc = nlp(text)
for ent in doc.ents:
    if ent.label_ == "PERSON":
        # Potential beneficiary name
    elif ent.label_ == "MONEY":
        # Potential amount
    elif ent.label_ == "DATE":
        # Potential date
```

### Benefits
✅ **Handles any format** - learns patterns
✅ **Typo tolerant** - ML is fuzzy by nature
✅ **Can improve over time** - with training data

### Drawbacks
❌ **Complex** - need ML expertise
❌ **Slow** - model inference takes time
❌ **Large dependencies** - spaCy models are 100+ MB
❌ **Training required** - for legal documents
❌ **Overkill** - legal docs are structured, not free-text
❌ **Hard to debug** - black box decisions
❌ **Privacy concerns** - if using commercial APIs

### Why Not Recommended
- Legal documents are **structured** → Pattern matching works well
- ML is for **unstructured text** → Not needed here
- Pattern matching is **faster, simpler, more explainable**
- Can always add ML later if patterns fail

### Implementation Effort
- **Time**: 1-2 weeks (if using pre-trained) or 1-2 months (if training custom)
- **Complexity**: High
- **Code changes**: Major refactor
- **Infrastructure**: GPU for training (if custom model)

---

## Recommended Implementation Plan

### **Phase 1: Enhanced Patterns** ✅ DO THIS FIRST
**Timeline**: 1-2 days
**Effort**: Low
**Impact**: High (+25-30% coverage)

**What to do**:
1. Create pattern library file (`patterns.py`)
2. Add 15-25 patterns per critical field:
   - Deceased name: 15 patterns
   - Distributions: 20 patterns
   - Property address: 15 patterns
   - Dates: 25 patterns
   - Amounts: 10 patterns
   - Bank details: 10 patterns
3. Update `_extract_probate_data()` to try all patterns
4. Update `_extract_property_completion_data()` to try all patterns
5. Add case-insensitive matching everywhere
6. Test with existing test script

**Expected Result**: 85-95% of documents fully extracted

---

### **Phase 2: Table Extraction** ✅ DO THIS SECOND
**Timeline**: 1-2 days
**Effort**: Low-Medium
**Impact**: Medium (+5-10% coverage for table-heavy docs)

**What to do**:
1. Add `_extract_tables()` method using pdfplumber
2. Add `_extract_from_tables()` for each document type
3. Create column detection logic (fuzzy match headers)
4. Parse table rows into structured data
5. Prefer table data over regex when both available
6. Test with documents that have tables

**Expected Result**: 90-95% of documents fully extracted

---

### **Phase 3: OCR Fallback** ⚠️ OPTIONAL - ONLY IF NEEDED
**Timeline**: 2-3 days
**Effort**: Medium
**Impact**: Medium (+5-10% for scanned docs)

**Prerequisites**:
- ❌ Tesseract binary must be installed
- Need DevOps/admin to install system package
- Test on server environment first

**What to do**:
1. Add quality checking for extracted text
2. Add PDF-to-image conversion (pypdfium2)
3. Add image preprocessing (PIL)
4. Add OCR extraction (pytesseract)
5. Add fallback logic (if quality < threshold → OCR)
6. Test with scanned documents

**Expected Result**: 95-99% of documents extracted

**When to skip**:
- If you rarely receive scanned documents
- If server can't install Tesseract
- If Phase 1+2 already covers your needs

---

## Testing Approach

### **After Phase 1 (Enhanced Patterns)**
Run test script:
```bash
cd backend
python3 test_pdf_extraction.py
```

Expected output:
```
Overall Verification Rate: 100%
Claim 0: ✅ YES (Confidence: 90%)
Claim 1: ✅ YES (Confidence: 92%)
```

### **Real-World Testing**
Test with actual documents:
1. Upload 20 different probate grants
2. Upload 20 different completion statements
3. Check extraction success rate
4. Identify patterns that still fail
5. Add those patterns to library

### **Pattern Testing Matrix**
| Document Type | Format Variations | Current Success | Target Success |
|---------------|-------------------|-----------------|----------------|
| Probate Grants | 10+ variations | ~60% | 90%+ |
| Completion Statements | 8+ variations | ~70% | 90%+ |
| Loan Agreements | 5+ variations | ~50% | 85%+ |
| Solicitor Statements | 6+ variations | ~60% | 85%+ |

---

## Cost-Benefit Analysis

### Phase 1: Enhanced Patterns
**Cost**:
- ⏱️ 1-2 days development time
- 💻 No new dependencies
- 🔧 No infrastructure changes

**Benefit**:
- 📈 +25-30% coverage (60% → 85-95%)
- ⚡ Still very fast
- ✅ Low risk
- 💰 High ROI

**ROI**: ⭐⭐⭐⭐⭐ (5/5) - Best value

### Phase 2: Table Extraction
**Cost**:
- ⏱️ 1-2 days development time
- 💻 No new dependencies
- 🔧 No infrastructure changes

**Benefit**:
- 📈 +5-10% coverage (85% → 90-95%)
- ⚡ Still fast
- ✅ Better data quality
- 💰 Good ROI

**ROI**: ⭐⭐⭐⭐ (4/5) - Good value

### Phase 3: OCR Fallback
**Cost**:
- ⏱️ 2-3 days development time
- 💻 No new dependencies (pytesseract installed)
- 🔧 **Requires Tesseract installation** (system admin needed)
- 🐌 Slower performance for scanned docs

**Benefit**:
- 📈 +5-10% coverage (90% → 95-99%)
- 📄 Handles scanned documents
- ⚠️ Medium risk (system dependencies)
- 💰 Depends on % of scanned docs

**ROI**: ⭐⭐⭐ (3/5) - If needed, good; if not needed, unnecessary

---

## Decision Framework

### **Start with Phase 1+2** if:
✅ Most documents are digital (not scanned)
✅ Want quick improvement with low risk
✅ Don't want infrastructure changes
✅ Need results in 2-4 days

### **Add Phase 3 (OCR)** if:
⚠️ Receive many scanned documents (>10%)
⚠️ Phase 1+2 success rate is insufficient
⚠️ Can install Tesseract on server
⚠️ Acceptable for processing to be slower

### **Skip OCR** if:
❌ Rarely receive scanned documents (<5%)
❌ Cannot install Tesseract
❌ Phase 1+2 already achieves 90%+ success
❌ Performance is critical

---

## Sample Pattern Library Structure

```python
# patterns.py

# ======================
# PROBATE PATTERNS
# ======================

DECEASED_NAME_PATTERNS = [
    r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(Deceased\)',
    r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(deceased\)',
    r'In the Estate of[:\s]+([A-Z][A-Za-z\s]+)',
    r'Estate of the late[:\s]+([A-Z][A-Za-z\s]+)',
    r'Estate:\s*([A-Z][A-Za-z\s]+)\s*\(Deceased\)',
    r'Re:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',
    r'Matter:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',
    r'Grant in respect of[:\s]+([A-Z][A-Za-z\s]+)',
    r'Deceased[:\s]+([A-Z][A-Za-z\s]+)',
    r'Name of Deceased[:\s]+([A-Z][A-Za-z\s]+)',
    r'ESTATE OF[:\s]+([A-Z\s]+)',
    r'Probate of[:\s]+([A-Z][A-Za-z\s]+)',
    # ... 3 more patterns ...
]

DISTRIBUTION_PATTERNS = [
    # Standard formats
    r'(?:Primary\s+)?Beneficiary[:\s]*\n?([A-Z][A-Za-z\s()]+?)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
    
    # Payment to...
    r'(?:Payment|Distribution)\s+to[:\s]+([A-Z][A-Za-z\s]+)\s*[:\-]\s*£?([0-9,]+(?:\.\d{2})?)',
    
    # Table format
    r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+\|?\s*£?([0-9,]+(?:\.\d{2})?)',
    
    # With relationship
    r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+\((?:Son|Daughter|Spouse|Child)\)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
    
    # ... 16 more patterns ...
]

# ======================
# PROPERTY PATTERNS
# ======================

PROPERTY_ADDRESS_PATTERNS = [
    # Full UK address with postcode
    r'(?:Property|Address)[:\s]*\n?([0-9]+[A-Za-z]?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z\s]+,\s*[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
    
    # Flat format
    r'(?:Flat|Apartment|Unit)\s+([0-9A-Za-z]+),?\s+([0-9]+\s+[A-Z][a-z\s,]+[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
    
    # Multi-line
    r'(?:Property|Address)[:\s]*\n([^\n]+)\n([^\n]+)\n([A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
    
    # ... 12 more patterns ...
]

# ======================
# COMMON PATTERNS
# ======================

DATE_PATTERNS = [
    # UK with ordinals
    r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4})',
    
    # ISO format
    r'(\d{4}-\d{2}-\d{2})',
    
    # Slash formats
    r'(\d{1,2}/\d{1,2}/\d{4})',
    r'(\d{1,2}/\d{1,2}/\d{2})',
    
    # ... 21 more patterns ...
]

AMOUNT_PATTERNS = [
    r'£\s*([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    r'GBP\s*([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    r'([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*GBP',
    # ... 7 more patterns ...
]
```

---

## Conclusion & Recommendation

### **Do This (Recommended)**
✅ **Phase 1**: Enhanced patterns (1-2 days, high impact)
✅ **Phase 2**: Table extraction (1-2 days, good impact)

**Total**: 2-4 days for 90-95% coverage

### **Consider Later**
⚠️ **Phase 3**: OCR fallback (2-3 days) - Only if you have scanned documents

### **Don't Do (Yet)**
❌ NLP/ML approach - Overkill for structured legal documents

### **Next Steps**
1. Answer the questions below
2. I'll create the enhanced pattern library
3. We'll test with your real documents
4. Iterate based on results

---

## Questions for You

### 1. Document Types & Volumes
- What % of documents are **scanned** vs **digital PDFs**?
- How many different solicitor firms' templates do you see?
- Which document types are most common?

### 2. Current Pain Points
- Do you have specific documents that are failing now?
- Can you share 5-10 real PDFs (anonymized) for testing?
- What fields are most often missing from extraction?

### 3. Infrastructure
- Can we install Tesseract on the server? (For Phase 3 if needed)
- Is there a test/staging environment we can try OCR on?
- Any restrictions on system dependencies?

### 4. Timeline & Priority
- How urgent is improving extraction coverage?
- Is 90-95% coverage acceptable, or do you need 99%?
- Acceptable for Phase 1+2 (patterns + tables) to go live first?

### 5. Testing
- Can you provide varied sample documents for testing?
- Who will test the improvements before production deployment?
- What's the acceptance criteria (X% success rate)?

---

**Bottom Line**: Start with enhanced patterns + table extraction. This gives you 90-95% coverage in 2-4 days with low risk. Add OCR later only if you have many scanned documents.
