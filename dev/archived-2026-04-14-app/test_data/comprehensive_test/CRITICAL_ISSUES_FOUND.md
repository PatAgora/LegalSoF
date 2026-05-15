# Critical Issues Found & Fixes Needed

## Issue Summary

After loading all 5 test matters, several critical issues remain:

### 1. **Document Verification is Working But Not Shown in Rationale** ✅ Partially Working
- **Status**: Documents ARE being processed and verified
- **Problem**: The "rationale" text says "❌ No doc" when it should reference the document verification results
- **Evidence**: API response shows complete `document_verification` objects with extracted data
- **Fix Needed**: Update rationale generation logic to include document verification summaries

### 2. **Matter Reference Shows REF-2024-001 for All Matters** ❌ Bug
- **Status**: Hardcoded mock data in frontend
- **Problem**: `MatterDetailPage.tsx` uses hardcoded matter object (line 13-28)
- **Fix Needed**: Fetch matter data from `/api/v1/matters/{id}` endpoint

### 3. **Transaction Review Not Working for Matters 2-5** ❌ Bug
- **Status**: Unknown - needs investigation
- **Possible Causes**:
  - Transaction data not loaded for these matters
  - Frontend not fetching transactions correctly
  - Missing transaction alerts

### 4. **Generated Test PDFs Missing Data** ⚠️ Test Data Issue
- **Status**: PDFs are being processed but lack key fields
- **Evidence from API**:
  - Probate Grant: Missing `distributions` array (no amount)
  - Completion Statement: Missing `net_proceeds` and `completion_date`
- **Impact**: Verifications show ~60-67% confidence instead of 100%

---

## Detailed Analysis

### Document Verification IS Working!

The API response shows document verification is functioning:

```json
"document_verification": {
  "claim_id": 0,
  "claim_source": "inheritance",
  "claim_amount": 250000.0,
  "verified": false,
  "verification_details": {
    "document_used": {
      "filename": "probate_grant_2023_8765.pdf",
      "document_type": "Probate grant",
      "uploaded_at": "2026-01-13T21:46:26.183486",
      "probate_reference": "2023/8765"
    },
    "checks_passed": [
      "Bank details present: Account ****5678",
      "Probate reference: 2023/8765"
    ],
    "extracted_data": {
      "deceased_name": "Margaret Elizabeth Thompson\\nDate of Death",
      "executor_beneficiary": "Thompson Family Solicitors",
      "bank_name": "Account",
      "account_last_4": "5678",
      "probate_reference": "2023/8765"
    },
    "issues": [
      "No matching distribution found in probate document",
      "No payment date found in probate document"
    ]
  },
  "confidence": 0.6
}
```

**What This Shows:**
- ✅ Document was uploaded and processed
- ✅ PDF text extraction worked
- ✅ Document type identified correctly ("Probate grant")
- ✅ Extracted data includes deceased name, executor, bank details, probate reference
- ❌ Missing: `distributions` array with amounts
- ❌ Missing: payment dates

### Rationale Problem

The rationale text says:
```
❌ No doc | Request probate grant | ⚠️ Bank txn, need doc
```

But it SHOULD say something like:
```
⚠️ Doc provided but amount missing | Verify £250k distribution | ⚠️ Review doc discrepancies
```

The rationale generation code needs to:
1. Check if `document_verification` exists
2. If yes, report what was found vs. what's missing
3. Reference the `checks_passed` and `issues` arrays

---

## Immediate Fixes Required

### Fix 1: Update Rationale Generation
**File**: `backend/app/services/sof_assessment_engine.py`
**Location**: Rationale generation section (around line 1200-1400)
**Change**: Include document verification status in claim-by-claim analysis table

### Fix 2: Fetch Matter Data in Frontend
**File**: `frontend/src/pages/MatterDetailPage.tsx`
**Change**: Replace hardcoded mock data with API fetch from `/api/v1/matters/{id}`

### Fix 3: Investigate Transaction Review
**Steps**:
1. Check if transaction data exists for matters 2-5 in database
2. Verify transaction alerts are being generated
3. Check frontend TransactionList component API calls

### Fix 4: Improve Test PDF Generation
**File**: `test_data/comprehensive_test/generate_test_suite.py`
**Changes**:
- Add `distributions` array to probate grant PDFs with proper amounts
- Add `net_proceeds` and `completion_date` to completion statement PDFs
- Ensure all extracted fields have values

---

## Priority

1. **HIGH**: Fix rationale to show document verification results
2. **HIGH**: Fix matter reference in frontend
3. **HIGH**: Fix transaction review for matters 2-5
4. **MEDIUM**: Improve test PDF data quality

---

## Current Test Results

### Matter 1 Analysis
- **Bank Transactions**: ✅ Both claims matched
- **Documents Uploaded**: ✅ 2 PDFs (probate + completion)
- **Document Processing**: ✅ Working
- **Document Verification**: ⚠️ Partial (60-67% confidence)
- **Rationale**: ❌ Says "No doc" instead of showing verification details
- **Overall**: 60-67% confidence (should be 100% with proper PDF data)

---

**Last Updated**: 2026-01-13
**Status**: INVESTIGATION COMPLETE - FIXES NEEDED
