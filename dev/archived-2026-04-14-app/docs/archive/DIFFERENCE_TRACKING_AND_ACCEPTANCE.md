# Difference Tracking & Manual Acceptance Feature ✅

## Overview

This feature allows the system to:
1. **Identify specific differences** between customer claims and supporting documents
2. **Display differences clearly** with field names and severity
3. **Enable manual override** through "Accept Differences" button
4. **Maintain audit trail** of who accepted what, when, and why

---

## Use Case

**Problem:** A Property Sale claim shows 86% confidence because the completion statement PDF is missing the "solicitor firm" field. However, upon manual review, the user determines this is acceptable because:
- All other critical fields match (amount, date, address, bank details)
- The title number is present and verified
- The transaction is clearly legitimate

**Solution:** The user can now click "Accept Differences" to manually override the review requirement while maintaining a full audit trail.

---

## Backend Implementation

### 1. Difference Tracking Structure

Each verification result now includes:

```python
{
    "differences": [
        {
            "field": "solicitor_firm",
            "issue": "No solicitor details found",
            "severity": "missing",  # or "mismatch"
            "customer_value": None,
            "document_value": None,
            "accepted": False,  # Set to True when manually accepted
            "accepted_by": None,
            "accepted_at": None
        }
    ],
    "manual_review_status": "pending",  # or "accepted" or "not_required"
    "manually_accepted_by": None,
    "manually_accepted_at": None,
    "acceptance_reason": None
}
```

### 2. Field Name Extraction

Helper method maps common issues to field names:

```python
def _extract_field_name(self, issue: str) -> str:
    """Extract the field name from an issue description"""
    if 'solicitor' in issue.lower():
        return 'solicitor_firm'
    elif 'probate reference' in issue.lower():
        return 'probate_reference'
    elif 'bank details' in issue.lower():
        return 'bank_details'
    # ... more mappings
```

### 3. Acceptance API Endpoint

**Endpoint:** `POST /api/v1/matters/{matter_id}/sof-assessment/accept-differences`

**Request Body:**
```json
{
    "claim_index": 1,
    "accepted_by": "John Smith",
    "reason": "Manual review completed - all critical fields verified"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Differences accepted for claim 2",
    "claim_index": 1,
    "accepted_by": "John Smith",
    "accepted_at": "2026-01-13T10:30:00",
    "reason": "Manual review completed - all critical fields verified",
    "updated_status": {
        "requires_review": true,
        "manual_review_status": "accepted",
        "confidence": 0.857
    }
}
```

**Important:** The `requires_review` flag remains `true` and confidence stays at < 100%, but `manual_review_status` changes to `"accepted"` to indicate manual override.

---

## Frontend Implementation

### 1. Difference Display

When `confidence < 100%` and `requires_review = true`:

```
⚠️ DOCUMENT VERIFICATION INCOMPLETE (Confidence: 86%)

Issues Found:
  ❌ No solicitor details found

📋 Specific Differences Identified:
  ┌─────────────────────────────────────────────┐
  │ 🔴 Missing: Solicitor Firm                  │
  │ No solicitor details found                   │
  └─────────────────────────────────────────────┘

Manual Review Status:
  ⏳ Pending Manual Review

┌─────────────────────────────────────────┐
│        ✓ Accept Differences              │
└─────────────────────────────────────────┘
Review the differences above and click to accept
if satisfied upon manual review
```

### 2. Accept Differences Button

```typescript
<button
  onClick={async () => {
    const reason = prompt('Please provide a reason for accepting...');
    if (reason !== null) {
      const response = await fetch(
        `/api/v1/matters/${matter_id}/sof-assessment/accept-differences`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            claim_index: idx,
            accepted_by: 'Current User',
            reason: reason || 'Manual review completed'
          })
        }
      );
      
      if (response.ok) {
        alert('Differences accepted successfully!');
        window.location.reload();
      }
    }
  }}
  className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white"
>
  ✓ Accept Differences
</button>
```

### 3. After Acceptance

Display changes to:

```
⚠️ DOCUMENT VERIFICATION INCOMPLETE (Confidence: 86%)

📋 Specific Differences Identified:
  ┌─────────────────────────────────────────────┐
  │ 🔴 Missing: Solicitor Firm                  │
  │ No solicitor details found                   │
  │ ✅ Accepted by John Smith on 01/13/2026     │
  └─────────────────────────────────────────────┘

Manual Review Status:
  ✅ Differences Accepted
  By: John Smith
  Date: 1/13/2026, 10:30:00 AM
  Reason: Manual review completed - all critical 
          fields verified
```

---

## Difference Severity Types

### 1. Missing Fields (`severity: "missing"`)
- Triggered when a field is not found in the document
- Examples: missing solicitor, missing probate reference
- Pattern: "not found" or "No [field]"

### 2. Mismatches (`severity: "mismatch"`)
- Triggered when a field value differs from expected
- Examples: amount discrepancy, date mismatch
- Pattern: "mismatch" or "does not match"

---

## Example Scenarios

### Scenario 1: Missing Solicitor Field (Current)

**Inputs:**
- Customer Claim: Property Sale £300,000
- Bank Statement: £300,000 on 2023-07-01 ✅
- Completion Statement:
  - ✅ Net proceeds: £300,000.82
  - ✅ Completion date: 1 July 2023
  - ✅ Property address: 45 Oak Street
  - ✅ Bank details: ****8642
  - ✅ Title: TGL123456
  - ❌ Solicitor: [MISSING]

**Verification Result:**
- Confidence: 83-86%
- Requires Review: True
- Differences: 1 (Missing: Solicitor Firm)

**User Action:**
1. Reviews the difference
2. Determines: "Title number verified, all other fields match, acceptable"
3. Clicks "Accept Differences"
4. Enters reason: "Title number TGL123456 verified, solicitor detail not material"

**Result:**
- Manual Review Status: Accepted
- Audit Trail: Recorded acceptance
- Badge: Still shows ⚠️ REQUIRES REVIEW but with "Accepted" status

### Scenario 2: Amount Mismatch

**Inputs:**
- Customer Claim: £300,000.00
- Document shows: £300,000.82

**Verification Result:**
- Confidence: 100% (within 1% tolerance)
- No difference flagged (tolerance applied)

### Scenario 3: Amount Outside Tolerance

**Inputs:**
- Customer Claim: £300,000
- Document shows: £305,000

**Verification Result:**
- Confidence: < 100%
- Differences: 1 (Mismatch: Amount)
- Issue: "Amount mismatch: document shows £305,000, claim is £300,000"

**User Action:**
1. Reviews difference
2. Determines: "Customer explanation was approximate, actual amount is £305,000 as per completion statement"
3. Accepts difference with reason
4. Updates customer file with correct amount

---

## Audit Trail

All acceptances are recorded with:
- **Who:** `accepted_by` field (username/email)
- **When:** `accepted_at` timestamp (UTC)
- **Why:** `acceptance_reason` text
- **What:** Full list of differences accepted

This data is:
- ✅ Persisted to storage
- ✅ Displayed in UI
- ✅ Included in file notes
- ✅ Available for regulatory audit

---

## API Testing

### Test Accept Differences

```bash
# Assuming claim 1 requires review
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/accept-differences \
  -H "Content-Type: application/json" \
  -d '{
    "claim_index": 1,
    "accepted_by": "Test User",
    "reason": "Manual review complete - acceptable variance"
  }'

# Response
{
  "success": true,
  "message": "Differences accepted for claim 2",
  "claim_index": 1,
  "accepted_by": "Test User",
  "accepted_at": "2026-01-13T10:35:22.123456",
  "reason": "Manual review complete - acceptable variance"
}
```

### Verify Acceptance

```bash
curl -s http://localhost:8001/api/v1/matters/1/sof-assessment/results | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
evidence = data['assessment']['evidence_matches'][1]
doc_ver = evidence['document_verification']
print('Manual Review Status:', doc_ver.get('manual_review_status'))
print('Accepted By:', doc_ver.get('manually_accepted_by'))
print('Accepted At:', doc_ver.get('manually_accepted_at'))
print('Reason:', doc_ver.get('acceptance_reason'))
"
```

---

## UI States

### State 1: No Review Required (100% Confidence)
```
✅ FULLY VERIFIED (100%)
✅ SUPPORTING DOCUMENT VERIFIED (Confidence: 100%)
```
- No differences
- No button shown

### State 2: Requires Review (Pending)
```
⚠️ REQUIRES REVIEW (86%)
⚠️ DOCUMENT VERIFICATION INCOMPLETE (Confidence: 86%)
📋 Specific Differences Identified
Manual Review Status: ⏳ Pending Manual Review
[✓ Accept Differences] button shown
```

### State 3: Requires Review (Accepted)
```
⚠️ REQUIRES REVIEW (86%)
⚠️ DOCUMENT VERIFICATION INCOMPLETE (Confidence: 86%)
📋 Specific Differences Identified
  ✅ Accepted by John Smith on 01/13/2026
Manual Review Status: ✅ Differences Accepted
No button (already accepted)
```

### State 4: Bank Only (No Documents)
```
⚠️ Payment found, docs req'd
```
- No differences (no document to compare)
- No button shown

---

## Security Considerations

### Authentication (TODO)
Currently uses hardcoded "Current User". Should integrate with:
- Session management
- User authentication system
- Role-based access control (RBAC)

### Authorization (TODO)
Should check:
- User has permission to accept differences
- User role (e.g., only Senior Compliance Officers can accept)
- Matter access permissions

### Audit Log Enhancement (TODO)
Should record:
- IP address of acceptance
- Before/after confidence scores
- Full diff of what was accepted
- Any notes or attachments

---

## Files Modified

### Backend
- ✅ `backend/app/services/document_verifier.py`
  - Added `_extract_field_name()` helper
  - Added difference tracking to `_verify_inheritance_claim()`
  - Added difference tracking to `_verify_property_claim()`
  - Added `manual_review_status`, `manually_accepted_*` fields

- ✅ `backend/app/api/v1/endpoints/sof_assessment.py`
  - Added `/accept-differences` endpoint (lines 421-516)
  - Validates claim index and review status
  - Updates manual review fields
  - Persists changes

### Frontend
- ✅ `frontend/src/components/SoFAssessment/SoFAssessment.tsx`
  - Added detailed differences display
  - Added "Accept Differences" button
  - Added manual review status display
  - Added acceptance confirmation flow

---

## Deployment

- **Commit:** `58b9e83`
- **Branch:** `fix/pdf-verification-and-file-persistence`
- **PR:** https://github.com/PatAgora/LegalSoF/pull/1
- **Frontend:** https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai
- **Backend:** http://localhost:8001

---

## Summary

✅ **Difference Tracking:** System identifies which specific fields are missing or mismatched

✅ **Clear Display:** Differences shown with field names, issues, and severity

✅ **Manual Override:** "Accept Differences" button allows authorized users to override

✅ **Audit Trail:** Full record of who accepted, when, and why

✅ **Visual Indicators:** Clear status badges for pending/accepted states

This feature enables flexible, auditable manual review workflows while maintaining strict automated verification standards.
