# Comprehensive SoF Assessment Test Suite

## Overview

This test suite contains 5 complete test scenarios with realistic PDF documents to test all aspects of the SoF Assessment system.

## Test Scenarios

### Scenario 1: Perfect Match ✅
- **Client**: Residential Property Ltd
- **Sources**: Inheritance (£250k) + Property Sale (£200k)
- **Expected Result**: Both claims FULLY VERIFIED (100% confidence)
- **Files**:
  - `client_info.json`
  - `bank_statement_matching.pdf` ✓
  - `probate_grant_2023_8765.pdf` ✓
  - `completion_statement_*.pdf` ✓

### Scenario 2: Missing Solicitor ⚠️
- **Client**: Commercial Ventures PLC
- **Sources**: Business Sale (£500k) + Business Loan (£250k)
- **Expected Result**: 
  - Business Sale: REQUIRES REVIEW (~83% confidence) - Missing solicitor field
  - Business Loan: FULLY VERIFIED (100%)
- **Files**:
  - `client_info.json`
  - `bank_statement_matching.pdf` ✓
  - `business_sale_*.pdf` (missing solicitor) ⚠️
  - `loan_agreement_*.pdf` ✓

### Scenario 3: Amount Mismatch ❌
- **Client**: Property Investors Group
- **Sources**: Property Sale (£400k claimed) + Savings (£220k claimed)
- **Expected Result**:
  - Property Sale: REQUIRES REVIEW - Document shows £385k (£15k difference)
  - Savings: REQUIRES REVIEW - Statements show £215k (£5k difference)
- **Files**:
  - `client_info.json`
  - `bank_statement_non_matching.pdf` (lower amounts) ❌
  - `completion_statement_*.pdf` (shows £385k) ❌

### Scenario 4: Date Discrepancy ⚠️
- **Client**: Tech Acquisitions Ltd
- **Sources**: Inheritance (£350k) + Business Sale (£540k)
- **Expected Result**:
  - Inheritance: REQUIRES REVIEW - Distribution date differs by 2 months
  - Business Sale: REQUIRES REVIEW - Completion date differs by 1 month
- **Files**:
  - `client_info.json`
  - `bank_statement_non_matching.pdf` (dates don't match) ⚠️
  - `probate_grant_*.pdf` (August vs June) ⚠️
  - `business_sale_*.pdf` (October vs September) ⚠️

### Scenario 5: Wrong Document Type ❌
- **Client**: Startup Ventures Ltd
- **Sources**: Gift (£100k) + Savings (£220k)
- **Expected Result**:
  - Gift: FULLY VERIFIED (100%)
  - Savings: REQUIRES REVIEW - Credit card statement provided instead of bank statement
- **Files**:
  - `client_info.json`
  - `bank_statement_matching.pdf` ✓
  - `gift_letter.pdf` ✓
  - `credit_card_statement.pdf` (wrong document type) ❌

## Running Tests

### Quick Test All Scenarios

```bash
cd /home/user/webapp/test_data/comprehensive_test
python run_all_tests.py
```

### Test Individual Scenario

```bash
# Example: Test Scenario 1
cd scenario_1_perfect_match

# 1. Reset assessment
curl -X DELETE http://localhost:8001/api/v1/matters/1/sof-assessment/reset

# 2. Upload client info
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@client_info.json" \
  -F "file_category=client_info"

# 3. Upload bank statement
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@bank_statement_matching.pdf" \
  -F "file_category=bank_statement"

# 4. Upload supporting documents
for doc in *.pdf; do
  if [[ $doc != bank_statement* ]]; then
    curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
      -F "file=@$doc" \
      -F "file_category=supporting_doc"
  fi
done

# 5. Run assessment
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/run

# 6. View results
curl http://localhost:8001/api/v1/matters/1/sof-assessment/results
```

## Expected Outcomes Summary

| Scenario | Claim 1 | Claim 2 | Overall |
|----------|---------|---------|---------|
| 1 - Perfect Match | ✅ 100% | ✅ 100% | All verified |
| 2 - Missing Solicitor | ⚠️ ~83% | ✅ 100% | Requires review |
| 3 - Amount Mismatch | ❌ Amount diff | ❌ Amount diff | Requires review |
| 4 - Date Discrepancy | ⚠️ Date diff | ⚠️ Date diff | Requires review |
| 5 - Wrong Docs | ✅ 100% | ❌ Wrong type | Requires review |

## Manual Acceptance Testing

For scenarios requiring review, test the manual acceptance workflow:

```bash
# Accept differences for a claim
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/accept-differences \
  -H "Content-Type: application/json" \
  -d '{
    "claim_index": 0,
    "accepted_by": "Test User",
    "reason": "Verified through alternative means"
  }'
```

## What to Test

1. **PDF Extraction**: Verify system can extract data from all PDF files
2. **Transaction Matching**: Confirm bank transactions are correctly matched to claims
3. **Confidence Scoring**: Validate confidence percentages match expected values
4. **Difference Detection**: Check specific differences are identified (field, amount, date)
5. **Review Badges**: Verify REQUIRES REVIEW badges appear correctly
6. **Manual Acceptance**: Test acceptance workflow and audit trail
7. **UI Display**: Confirm all data displays correctly in frontend

## File Structure

```
comprehensive_test/
├── scenario_1_perfect_match/
│   ├── client_info.json
│   ├── bank_statement_matching.pdf
│   ├── probate_grant_2023_8765.pdf
│   └── completion_statement_*.pdf
├── scenario_2_missing_solicitor/
│   ├── client_info.json
│   ├── bank_statement_matching.pdf
│   ├── business_sale_*.pdf
│   └── loan_agreement_*.pdf
├── scenario_3_amount_mismatch/
│   ├── client_info.json
│   ├── bank_statement_non_matching.pdf
│   └── completion_statement_*.pdf
├── scenario_4_date_discrepancy/
│   ├── client_info.json
│   ├── bank_statement_non_matching.pdf
│   ├── probate_grant_*.pdf
│   └── business_sale_*.pdf
└── scenario_5_wrong_documents/
    ├── client_info.json
    ├── bank_statement_matching.pdf
    ├── gift_letter.pdf
    └── credit_card_statement.pdf
```

## Notes

- All bank statements are PDF files that must be parsed by the system
- Transaction review data comes exclusively from uploaded PDF bank statements
- Supporting documents have intentional discrepancies to test verification logic
- Test both the automated verification and manual acceptance workflows
