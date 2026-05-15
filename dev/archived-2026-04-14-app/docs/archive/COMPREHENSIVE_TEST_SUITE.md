# Comprehensive Test Suite - READY FOR TESTING ✅

## Overview

This test suite provides **6 different scenarios** covering:
- ✅ Perfect matches (100% confidence)
- ⚠️ Missing fields (solicitor, title)
- 🔴 Amount mismatches (£150k vs £155k)
- ⚠️ Date discrepancies (January vs March)
- ❌ Wrong document types
- 🔀 Mixed success/failure scenarios

## Location

All test files are in: `/home/user/webapp/test_data/comprehensive_test/`

## Test Files Created

### 1. Client Information
**File:** `client_info.json`
- Client: TestCo Acquisition Ltd
- Purchase Amount: £1,050,000
- 6 SoF Claims:
  1. Inheritance: £250,000
  2. Property Sale: £300,000
  3. Business Loan: £150,000 (⚠️ document will show £155,000)
  4. Business Sale: £200,000 (⚠️ date mismatch)
  5. Savings: £50,000 (❌ wrong doc type provided)
  6. Gift: £100,000

### 2. Bank Statements
**File:** `bank_statements_clean.csv`
- Clean transactions (no suspicious activity)
- All 6 claims have matching bank transactions
- Dates: June 2023 - March 2024
- Note: Loan shows £155,000 (not £150,000)

### 3. Supporting Documents (TO BE CREATED AS PDFs)

See `DOCUMENTS_TO_CREATE.md` for detailed content.

**Documents needed:**
1. `probate_grant_johnson.pdf` - ✅ PERFECT MATCH (100%)
2. `property_completion_123_high_street.pdf` - ⚠️ MISSING SOLICITOR (85%)
3. `natwest_business_loan_agreement.pdf` - 🔴 AMOUNT MISMATCH (83%)
4. `business_sale_digital_solutions.pdf` - ⚠️ DATE WRONG (85%)
5. `santander_credit_card_statement.pdf` - ❌ WRONG TYPE (0%)
6. `gift_letter_thompson_parents.pdf` - ✅ PERFECT MATCH (100%)

## Expected Test Results

| Claim | Amount | Bank Match | Doc Match | Confidence | Status | Differences |
|-------|--------|-----------|-----------|-----------|--------|-------------|
| 1. Inheritance | £250,000 | ✅ Yes | ✅ Perfect | 100% | ✅ FULLY VERIFIED | None |
| 2. Property | £300,000 | ✅ Yes | ⚠️ Missing | 85% | ⚠️ REQUIRES REVIEW | Missing: Solicitor Firm |
| 3. Loan | £150,000 | ✅ Yes | 🔴 Mismatch | 83% | ⚠️ REQUIRES REVIEW | Amount: £155k vs £150k |
| 4. Business | £200,000 | ✅ Yes | ⚠️ Wrong Date | 85% | ⚠️ REQUIRES REVIEW | Date: March vs January |
| 5. Savings | £50,000 | ✅ Yes | ❌ Wrong Doc | 0% | ❌ MISSING DOCS | Credit card not savings |
| 6. Gift | £100,000 | ✅ Yes | ✅ Perfect | 100% | ✅ FULLY VERIFIED | None |

**Summary:**
- Fully Verified: 2/6 claims (33%)
- Requires Review: 3/6 claims (50%)
- Missing Documents: 1/6 claims (17%)

## Testing Workflow

### Step 1: Reset and Upload
```bash
# Reset matter 1
curl -X DELETE http://localhost:8001/api/v1/matters/1/sof-assessment/reset

# Upload client info
cd /home/user/webapp/test_data/comprehensive_test
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@client_info.json" \
  -F "file_category=client_info"

# Upload bank statements
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@bank_statements_clean.csv" \
  -F "file_category=bank_statement"
```

### Step 2: Initial Assessment (Bank Only)
```bash
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/run
```

**Expected:** All 6 claims show "⚠️ Payment found, docs req'd"

### Step 3: Upload Supporting Documents
```bash
# Upload all 6 PDFs (once created)
for doc in probate_grant_johnson.pdf \
           property_completion_123_high_street.pdf \
           natwest_business_loan_agreement.pdf \
           business_sale_digital_solutions.pdf \
           santander_credit_card_statement.pdf \
           gift_letter_thompson_parents.pdf
do
    curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
      -F "file=@${doc}" \
      -F "file_category=supporting_doc"
done
```

### Step 4: Final Assessment (With Documents)
```bash
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/run
```

**Expected:**
- Claims 1 & 6: ✅ FULLY VERIFIED (100%)
- Claims 2, 3, 4: ⚠️ REQUIRES REVIEW with specific differences
- Claim 5: ❌ MISSING DOCS

### Step 5: View Results
```bash
curl -s http://localhost:8001/api/v1/matters/1/sof-assessment/results | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
evidence = data['assessment']['evidence_matches']

for i, ev in enumerate(evidence):
    doc_ver = ev.get('document_verification', {})
    print(f'Claim {i+1}: {ev.get(\"claim_source\")} - {doc_ver.get(\"confidence\", 0)*100:.0f}%')
    if doc_ver.get('differences'):
        for diff in doc_ver['differences']:
            print(f'  ❌ {diff[\"field\"]}: {diff[\"issue\"]}')
"
```

### Step 6: Test "Accept Differences"
```bash
# Accept difference for Claim 2 (Property - Missing Solicitor)
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/accept-differences \
  -H "Content-Type: application/json" \
  -d '{
    "claim_index": 1,
    "accepted_by": "Test Reviewer",
    "reason": "Title number verified, solicitor detail not material to AML assessment"
  }'

# Accept difference for Claim 3 (Loan - Amount Mismatch)
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/accept-differences \
  -H "Content-Type: application/json" \
  -d '{
    "claim_index": 2,
    "accepted_by": "Test Reviewer",
    "reason": "Customer understated by £5k, actual loan £155k, verified with bank"
  }'
```

## Features Being Tested

### ✅ Document Verification
- [x] Perfect match (100%) - Claims 1 & 6
- [x] Missing fields detection - Claim 2
- [x] Amount mismatch detection - Claim 3
- [x] Date discrepancy detection - Claim 4
- [x] Wrong document type - Claim 5

### ✅ Difference Tracking
- [x] Field-level difference identification
- [x] Severity classification (missing vs mismatch)
- [x] Clear issue descriptions
- [x] Customer vs document comparison

### ✅ Manual Acceptance
- [x] "Accept Differences" button display
- [x] Reason prompt
- [x] Audit trail recording
- [x] Status update (pending → accepted)
- [x] Visual indicators in UI

### ✅ Confidence Scoring
- [x] 100% when all fields match
- [x] Proportional reduction for issues
- [x] Clear confidence % display
- [x] Requires review flag when < 100%

### ✅ UI Badges
- [x] ✅ FULLY VERIFIED (100%) - Green
- [x] ⚠️ REQUIRES REVIEW (X%) - Amber
- [x] ⚠️ Payment found, docs req'd - Beige
- [x] ❌ MISSING - Red

## Document Creation Needed

The PDFs need to be created based on the text in `DOCUMENTS_TO_CREATE.md`.

**Options:**
1. Use a PDF generation tool (e.g., LibreOffice, Word → PDF)
2. Use Python reportlab library
3. Use online PDF creators
4. Use existing sample PDFs and manually add/remove fields

**Key Points:**
- Document 1 & 6: Include ALL fields perfectly
- Document 2: Omit solicitor firm intentionally
- Document 3: Show £155,000 (not £150,000)
- Document 4: Show March 2023 dates (not January)
- Document 5: Must be clearly a credit card statement

## Transaction Review Note

The current test data has **CLEAN** bank statements with **NO** suspicious activity.

If you want to test transaction review:
- Add large cash deposits
- Add transfers to high-risk jurisdictions
- Add unusual transaction patterns
- Add sanctioned entity names

But for testing document verification and difference tracking, clean data is better.

## Next Steps

1. ✅ Test files created
2. ⏳ Create PDFs based on DOCUMENTS_TO_CREATE.md
3. ⏳ Upload all files and run assessment
4. ⏳ Verify difference tracking shows correctly
5. ⏳ Test "Accept Differences" workflow
6. ⏳ Confirm audit trail captures acceptances

---

**Status:** Test suite design COMPLETE. Ready for PDF creation and testing.
