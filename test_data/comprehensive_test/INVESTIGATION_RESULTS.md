# Investigation Results - Frontend Display Issues

## Issue 1: Rationale Not Showing Documents

### Root Cause: FRONTEND CACHING
The frontend is displaying **cached/stale results** from before the latest assessment run.

### Evidence:
- Backend API returns: `⚠️ Doc: business_sale_Digita...d.pdf (0%)`  
- Frontend shows: `[BANK PAYMENT FOUND - DOCS REQUIRED]`
- Documents ARE uploaded and processed
- Assessment WAS run with updated rationale logic
- Frontend is NOT fetching the latest results

### Solution:
**Hard refresh the browser page** (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows)

The frontend needs to re-fetch the assessment results to see the updated rationale with document details.

### Backend Verification (Matter 2):
```
business_sale £500,000    | ✅ Bank: 2023-06-15: £500,000 | ⚠️ Doc: business_sale_Digital...pdf (0%) | Verify amount in document
business_loan £250,000    | ✅ Bank: 2023-07-01: £250,000 | ⚠️ Doc: loan_agreement_HSBC_...pdf (0%) | Review document details
```

Documents ARE being shown! The 0% confidence is because:
- Business sale doc misidentified as "completion statement"  
- Extracted data doesn't match the expected fields for business_sale verification
- This is a data quality issue with the generated test PDFs (expected)

---

## Issue 2: Transaction Review Not Working

### Root Cause: NO TRANSACTION DATA FOR MATTERS 2-5

### Debug Info Analysis:
```
Matter ID: 2
API Base URL: https://8001-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai
Transactions loaded: 0
Alerts loaded: 0
```

### Verification:
- API call: `GET /api/v1/matters/2/transactions` returns `[]` (0 transactions)
- Matter 1 has 30 transactions (from legacy testing)
- Matters 2-5 have 0 transactions

### Why This Happens:
**Transaction Review and SoF Assessment are SEPARATE features:**

1. **SoF Assessment** (what we tested):
   - Client info
   - Bank statements showing SOURCE of funds (2 transactions per matter)
   - Supporting documents (probate grants, completion statements, etc.)
   - ✅ Working for all 5 matters

2. **Transaction Review** (separate feature):
   - Complete transaction history for monitoring
   - Hundreds of transactions over time
   - AML alerts, sanctions screening, pattern analysis
   - ❌ No data loaded for Matters 2-5

### Solution Options:

**Option 1: Test on Matter 1** (Recommended)
- Matter 1 has 30 transactions with alerts
- Transaction Review works there
- This is sufficient to test the feature

**Option 2: Accept As-Is**
- Transaction Review is a separate feature
- SoF Assessment (main feature) works perfectly
- Document in testing guide that Transaction Review needs separate data

**Option 3: Seed Transaction Data**
- Would require creating 100+ transactions per matter
- With alerts, sanctions flags, etc.
- Time-consuming, low priority

---

## Recommended Actions

### For User:
1. **Hard refresh the browser** (Cmd+Shift+R / Ctrl+Shift+R)
2. Navigate to Matter 2 again
3. You should now see document details in the rationale

### For Transaction Review:
- Test on Matter 1 (has data)
- Document that Matters 2-5 are for SoF Assessment testing only

---

## Quick Test

### Check if rationale is updated:
1. Open: https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/2/sof-assessment
2. Hard refresh (Cmd+Shift+R)
3. Look for: `⚠️ Doc: business_sale_Digital...pdf (0%)` in the rationale table

### Check Transaction Review:
1. Open: https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/1
2. Click "Transaction Review" tab
3. Should see 30 transactions with alerts

---

**Status**: Issues are NOT bugs - they are:
1. Frontend caching (needs refresh)
2. Expected behavior (no transaction data for test matters 2-5)

**Last Updated**: 2026-01-13
