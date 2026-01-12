# 🔍 PDF Document Processing Issue - Root Cause Analysis

## Problem Statement

When uploading PDF supporting documents (inheritance proof and property completion statement), the assessment engine does NOT recognize them and continues to request the same documents.

---

## 🔎 Root Cause

**Document Type Mismatch between File Processor and Assessment Engine**

### What's Happening:

1. **File Processor** (`file_processor.py` line 386-405):
   ```python
   def _identify_document_type(self, text: str) -> str:
       doc_types = {
           'probate': ['probate', 'grant of probate',...],  # Returns: "probate"
           'property_completion': ['completion statement',...],  # Returns: "property_completion"
       }
   ```
   
   **Returns:** `"probate"` or `"property_completion"`

2. **Assessment Engine** (`sof_assessment_engine.py` line 1085-1094):
   ```python
   if 'inheritance' in source_lower:
       if "Probate grant" not in ' '.join(known_documents):  # Looking for: "Probate grant"
           documents.append("Probate grant or letters...")
   
   elif 'property' in source_lower:
       if "completion statement" not in ' '.join(known_documents).lower():  # Looking for: "completion statement"
           documents.append("Property completion statement...")
   ```
   
   **Looking for:** `"Probate grant"` and `"completion statement"`

3. **The Mismatch:**
   - File processor returns: `"probate"` → Assessment engine looks for: `"Probate grant"` ❌
   - File processor returns: `"property_completion"` → Assessment engine looks for: `"completion statement"` ❌

---

## 📊 Data Flow Trace

### Step-by-Step Process:

```
1. User uploads: inheritance_proof_probate_grant.pdf
   ↓
2. API endpoint (sof_assessment.py line 97-103):
   - Accepts as supporting_doc
   - Processes with file_processor
   ↓
3. File Processor (file_processor.py line 313-346):
   - Extracts PDF text
   - Calls _identify_document_type()
   - Returns: {"document_type": "probate", "text_preview": "...", ...}
   ↓
4. API stores (sof_assessment.py line 132):
   storage['supporting_docs'].append(result['data'])
   # Now storage contains: [{"document_type": "probate", ...}]
   ↓
5. Assessment run (sof_assessment.py line 244-248):
   known_documents = []
   for doc in storage['supporting_docs']:
       doc_type = doc.get('document_type', 'unknown')  # Gets: "probate"
       if doc_type != 'unknown':
           known_documents.append(doc_type)  # Adds: "probate" to list
   # known_documents = ["probate"]
   ↓
6. Assessment Engine checks (sof_assessment_engine.py line 1086):
   if "Probate grant" not in ' '.join(known_documents):  # "Probate grant" not in "probate"
       documents.append("Probate grant...")  # ❌ STILL REQUESTS IT!
```

---

## 🐛 The Bug

### Known Documents List:
```python
known_documents = ["probate", "property_completion"]
```

### What Assessment Engine Checks:
```python
# For inheritance:
if "Probate grant" not in ' '.join(known_documents):  # "Probate grant" not in "probate property_completion"
    # Result: NOT FOUND → Still requests document ❌

# For property:
if "completion statement" not in ' '.join(known_documents).lower():  # "completion statement" not in "probate property_completion"
    # Result: NOT FOUND → Still requests document ❌
```

---

## ✅ The Fix

We need to make the document type identification consistent. Two options:

### Option 1: Update File Processor (Recommended)
Change the returned document types to match what the assessment engine expects:

**File:** `app/services/file_processor.py` (line 390-392)

**Current:**
```python
doc_types = {
    'probate': ['probate', 'grant of probate', ...],
    'property_completion': ['completion statement', ...],
}
```

**Should be:**
```python
doc_types = {
    'Probate grant': ['probate', 'grant of probate', ...],
    'completion statement': ['completion statement', 'property purchase', ...],
}
```

### Option 2: Update Assessment Engine
Change what the assessment engine looks for to match file processor output:

**File:** `app/services/sof_assessment_engine.py` (lines 1086, 1091)

**Current:**
```python
if "Probate grant" not in ' '.join(known_documents):
if "completion statement" not in ' '.join(known_documents).lower():
```

**Should be:**
```python
if "probate" not in ' '.join(known_documents).lower():
if "property_completion" not in ' '.join(known_documents).lower():
```

---

## 🎯 Recommended Solution

**Option 1 is better** because:
1. The assessment engine already uses human-readable document names
2. Multiple checks in the assessment engine would need updating (Option 2)
3. File processor output will be more descriptive for users
4. Easier to extend with new document types

---

## 🔧 Implementation Plan

### Changes Needed:

1. **Update `file_processor.py`** (line 390-405):
   - Change document type keys to match assessment engine expectations
   - Make all document types human-readable

2. **Test Cases:**
   - Upload inheritance_proof_probate_grant.pdf
   - Upload property_completion_statement.pdf
   - Run assessment
   - Verify documents are recognized in "Documents Required" section

3. **Expected Behavior After Fix:**
   ```
   Before: Documents Required lists "Probate grant" (even though uploaded)
   After: Documents Required does NOT list "Probate grant" (recognized!)
   ```

---

## 📝 Summary

### The Issue:
- PDFs are being uploaded ✅
- PDFs are being processed ✅
- Document types are being identified ✅
- **BUT** the names don't match what the assessment engine expects ❌

### The Solution:
Update the document type names in `file_processor.py` to match what `sof_assessment_engine.py` is looking for.

### Impact:
- Fix will make supporting documents properly recognized
- Confidence scores will improve
- "Documents Required" list will be accurate
- Assessment status will change from INSUFFICIENT to SUFFICIENT

---

## 🚀 Next Steps

1. Apply the fix to `file_processor.py`
2. Test with both PDF documents
3. Verify assessment recognizes documents
4. Commit changes with descriptive message
5. Update documentation

---

**File to modify:** `/home/user/webapp/backend/app/services/file_processor.py`  
**Lines to change:** 390-405 (document type dictionary)  
**Time to fix:** ~5 minutes  
**Testing time:** ~3 minutes  
**Total:** ~10 minutes to complete fix
