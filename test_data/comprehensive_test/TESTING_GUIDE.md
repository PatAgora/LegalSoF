# Comprehensive Testing Guide

## Overview
This test suite includes 6 scenarios designed to test all aspects of the SoF verification system, including intentional mismatches to verify the difference tracking and manual acceptance features.

## Test Data Summary

### Claims in client_info.json
1. **Inheritance** - £250,000 (Perfect match expected)
2. **Property Sale** - £300,000 (Missing solicitor field)
3. **Business Loan** - £150,000 (Amount mismatch: doc shows £155k)
4. **Business Sale** - £200,000 (Date discrepancy: claimed Jan, doc shows Mar)
5. **Savings** - £50,000 (Wrong document type provided)
6. **Gift** - £100,000 (Perfect match expected)

### Bank Statement Transactions
- All 6 claims have matching bank transactions
- Note: Loan shows £155,000 in bank (matches document, not customer claim)
- Business sale dated 10 March 2023 in bank (matches document date)

### Supporting Documents with Intentional Issues

| Doc | Claim | Issue | Expected Result |
|-----|-------|-------|-----------------|
| 1 | Inheritance | None - perfect | ✅ 100% confidence |
| 2 | Property | Missing solicitor | ⚠️ 85% confidence |
| 3 | Loan | Amount: £155k vs £150k | ⚠️ Mismatch detected |
| 4 | Business | Date: Mar vs Jan | ⚠️ Date discrepancy |
| 5 | Savings | Credit card != savings | ❌ Wrong doc type |
| 6 | Gift | None - perfect | ✅ 100% confidence |

## Step-by-Step Testing

### Step 1: Reset and Upload Client Info
```bash
# Reset matter 1
curl -X DELETE http://localhost:8001/api/v1/matters/1/sof-assessment/reset

# Upload client info
cd /home/user/webapp/test_data/comprehensive_test
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@client_info.json" \
  -F "file_category=client_info"
```

### Step 2: Upload Bank Statements
```bash
# Upload clean bank statements (CSV for now)
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@bank_statements_clean.csv" \
  -F "file_category=bank_statement"
```

### Step 3: Run Initial Assessment
```bash
# Should show: bank transactions verified, documents needed
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/run
```

**Expected Result:**
- 6 claims extracted
- 5-6 bank transactions matched (depending on matching logic)
- All claims show "⚠️ Payment found, docs req'd"
- Status: INSUFFICIENT - documents needed

### Step 4: Upload Supporting Documents
```bash
# Upload all 6 documents
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@1_probate_grant_perfect.txt" \
  -F "file_category=supporting_doc"

curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@2_property_completion_missing_solicitor.txt" \
  -F "file_category=supporting_doc"

curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@3_loan_agreement_amount_mismatch.txt" \
  -F "file_category=supporting_doc"

curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@4_business_sale_date_discrepancy.txt" \
  -F "file_category=supporting_doc"

curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@5_wrong_document_credit_card.txt" \
  -F "file_category=supporting_doc"

curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@6_gift_letter_perfect.txt" \
  -F "file_category=supporting_doc"
```

### Step 5: Run Final Assessment
```bash
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/run
```

**Expected Results:**

#### Claim 1: Inheritance (✅ FULLY VERIFIED 100%)
- Bank: £250,000 on 2023-06-15 ✅
- Document: Probate grant with all fields ✅
- Confidence: 100%
- Status: ✅ FULLY VERIFIED (100%)
- Differences: None

#### Claim 2: Property Sale (⚠️ REQUIRES REVIEW 85%)
- Bank: £300,000 on 2023-07-20 ✅
- Document: Completion statement ⚠️
- Confidence: ~85%
- Status: ⚠️ REQUIRES REVIEW (85%)
- Differences:
  - 🔴 Missing: Solicitor Firm
  - Issue: "No solicitor details found"
- Button: ✓ Accept Differences

#### Claim 3: Loan (⚠️ REQUIRES REVIEW - Amount Mismatch)
- Bank: £155,000 on 2024-01-15 ✅
- Document: Loan agreement showing £155,000 ⚠️
- Customer Claim: £150,000 ❌
- Confidence: <100%
- Status: ⚠️ REQUIRES REVIEW
- Differences:
  - ⚠️ Mismatch: Amount
  - Customer: £150,000
  - Document: £155,000
  - Bank: £155,000
  - Issue: "Amount mismatch: document shows £155,000, claim is £150,000"
- Button: ✓ Accept Differences

#### Claim 4: Business Sale (⚠️ REQUIRES REVIEW - Date Discrepancy)
- Bank: £200,000 on 2023-03-10 ✅
- Document: Sale agreement dated 10 March 2023 ⚠️
- Customer Claim: January 2023 ❌
- Confidence: <100%
- Status: ⚠️ REQUIRES REVIEW
- Differences:
  - ⚠️ Mismatch: Date
  - Customer: "January 2023"
  - Document: "10th March 2023"
  - Issue: Could show date-related issue
- Button: ✓ Accept Differences

#### Claim 5: Savings (❌ MISSING - Wrong Document)
- Bank: £50,000 transactions (8 x £5k salary) ✅
- Document: Credit card statement ❌
- Expected: Savings account statements
- Confidence: 0%
- Status: ❌ MISSING
- Differences:
  - 🔴 Missing: Savings statements
  - Issue: "Wrong document type - credit card statement provided"

#### Claim 6: Gift (✅ FULLY VERIFIED 100%)
- Bank: £100,000 on 2024-02-10 ✅
- Document: Gift letter with all fields ✅
- Confidence: 100%
- Status: ✅ FULLY VERIFIED (100%)
- Differences: None

### Step 6: Test Manual Acceptance

#### Accept Property Sale (Claim 2)
```bash
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/accept-differences \
  -H "Content-Type: application/json" \
  -d '{
    "claim_index": 1,
    "accepted_by": "Test Reviewer",
    "reason": "Title number LN123456 verified, solicitor detail not material to verification"
  }'
```

**Expected:**
- Manual review status: "accepted"
- UI shows: ✅ Differences Accepted
- Audit trail: Test Reviewer, timestamp, reason recorded

#### Accept Loan Amount Mismatch (Claim 3)
```bash
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/accept-differences \
  -H "Content-Type: application/json" \
  -d '{
    "claim_index": 2,
    "accepted_by": "Test Reviewer",
    "reason": "Customer understated by £5k. Actual loan £155k verified in both document and bank statement. Customer explanation updated."
  }'
```

#### Accept Business Sale Date (Claim 4)
```bash
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/accept-differences \
  -H "Content-Type: application/json" \
  -d '{
    "claim_index": 3,
    "accepted_by": "Test Reviewer",
    "reason": "Sale completed March 2023 per agreement and bank statement. Customer approximated as January. Acceptable variance."
  }'
```

### Step 7: Verify Results
```bash
# Check all claims
curl -s http://localhost:8001/api/v1/matters/1/sof-assessment/results | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
for i, ev in enumerate(data['assessment']['evidence_matches']):
    doc = ev.get('document_verification', {})
    print(f'Claim {i+1}: {ev.get(\"claim_source\")}')
    print(f'  Confidence: {doc.get(\"confidence\", 0)*100:.0f}%')
    print(f'  Manual Status: {doc.get(\"manual_review_status\", \"N/A\")}')
    print()
"
```

## Expected Final Summary

### Overall Assessment
- Total Claims: 6
- Fully Verified (100% + no manual review): 2/6
- Requires Review (accepted): 3/6
- Missing/Failed: 1/6

### Breakdown
✅ Claim 1 (Inheritance): 100% - Fully Verified
✅ Claim 2 (Property): 85% - Accepted (solicitor missing)
✅ Claim 3 (Loan): ~90% - Accepted (amount mismatch £5k)
✅ Claim 4 (Business): ~90% - Accepted (date discrepancy)
❌ Claim 5 (Savings): 0% - Failed (wrong document)
✅ Claim 6 (Gift): 100% - Fully Verified

### Differences Identified and Tracked
1. Property: Missing solicitor firm ✅ Accepted
2. Loan: Amount mismatch (£150k vs £155k) ✅ Accepted
3. Business: Date discrepancy (Jan vs Mar) ✅ Accepted
4. Savings: Wrong document type ❌ Cannot accept

## Key Testing Points

### ✅ Automated Verification
- [x] Perfect documents get 100% confidence
- [x] Missing fields reduce confidence proportionally
- [x] Amount mismatches detected
- [x] Date discrepancies identified
- [x] Wrong document types rejected

### ✅ Difference Tracking
- [x] Specific fields identified (e.g., "solicitor_firm")
- [x] Severity classified (missing vs mismatch)
- [x] Customer vs document values captured
- [x] Clear issue descriptions provided

### ✅ Manual Acceptance
- [x] "Accept Differences" button appears for review-required claims
- [x] User prompted for acceptance reason
- [x] Audit trail recorded (who, when, why)
- [x] Status updates to "accepted"
- [x] Differences marked as accepted individually

### ✅ UI Display
- [x] 100% confidence: Green "FULLY VERIFIED"
- [x] <100% confidence: Amber "REQUIRES REVIEW (X%)"
- [x] Accepted differences: Shows acceptance details
- [x] Missing docs: Red "MISSING" or specific guidance

## Next Steps After Testing

1. **Convert text files to PDFs** for realistic testing
2. **Create PDF bank statements** with proper formatting
3. **Implement PDF processing** if not already handling text extraction
4. **Test transaction review** with PDF statements
5. **Add more edge cases** as needed
6. **Test with real-world documents** (sanitized)

## Notes on Intentional Issues

These test documents contain intentional issues to verify the system handles:
- **Missing fields** (solicitor in property doc)
- **Amount discrepancies** (£5k difference in loan)
- **Date mismatches** (2-month difference in business sale)
- **Wrong document types** (credit card vs savings)

This ensures the difference tracking, manual review, and acceptance workflow function correctly under real-world conditions where documents may not be perfect.
