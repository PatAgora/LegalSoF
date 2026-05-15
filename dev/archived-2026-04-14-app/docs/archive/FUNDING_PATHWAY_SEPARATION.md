# Funding Pathway Separation

## What Changed

The **Funding Analysis** section now clearly separates funding sources that the client explained from other credits found in the bank statements.

---

## NEW Format

### Split into Two Sections

#### **1. Funding pathway (from client explanation)**
Shows only the transactions that match the client's stated sources (verified claims):

```
Funding pathway (from client explanation):
  • £250,000.00 received into Barclays_****1234 on 2023-05-15
    (Matches: Inheritance claim)
  • £300,000.00 received into HSBC_****5678 on 2023-07-01
    (Matches: Property Sale claim)
```

**Criteria:**
- Transaction must match a **verified claim**
- Date and amount must correspond to evidence_matches
- These are the sources the client **explained**

#### **2. Other potential funding pathway**
Shows additional credits found in statements that were NOT explained by the client:

```
Other potential funding pathway:
  • £200,000.00 transferred from Barclays_****1234 on 2023-06-15
  • £50,000.00 received into HSBC_****5678 on 2023-08-01
  • £25,000.00 dividend payment on 2023-09-10
```

**Criteria:**
- Transactions found in statements
- NOT matched to any client claim
- **Alternative funding sources** that need explanation

---

## Example Scenarios

### Scenario 1: All Verified Claims
**Client Explanation:**
- Inheritance £250,000
- Property Sale £300,000

**Bank Statements Show:**
- £250,000 inheritance (verified) ✅
- £300,000 property sale (verified) ✅

**Output:**
```
Funding pathway (from client explanation):
  • £250,000.00 received into Barclays_****1234 on 2023-05-15
  • £300,000.00 received into HSBC_****5678 on 2023-07-01

(No "Other potential funding pathway" section - everything explained)
```

### Scenario 2: Partial Verification
**Client Explanation:**
- Inheritance £250,000
- Property Sale £300,000

**Bank Statements Show:**
- £250,000 inheritance (verified) ✅
- £200,000 transfer (not explained) ⚠️
- £50,000 dividend (not explained) ⚠️

**Output:**
```
Funding pathway (from client explanation):
  • £250,000.00 received into Barclays_****1234 on 2023-05-15

Other potential funding pathway:
  • £200,000.00 transferred from HSBC_****5678 on 2023-06-15
  • £50,000.00 dividend payment on 2023-09-10
```

### Scenario 3: No Verified Claims (All Alternative)
**Client Explanation:**
- Inheritance £250,000
- Property Sale £300,000

**Bank Statements Show:**
- NO inheritance found ❌
- NO property sale found ❌
- £200,000 transfer (unexplained) ⚠️
- £150,000 loan (unexplained) ⚠️
- £100,000 dividend (unexplained) ⚠️

**Output:**
```
(No "Funding pathway (from client explanation)" section - nothing verified)

Other potential funding pathway:
  • £200,000.00 transferred from HSBC_****5678 on 2023-06-15
  • £150,000.00 loan drawdown on 2023-07-01
  • £100,000.00 dividend payment on 2023-08-10
```

---

## Benefits

### ✅ For Solicitors
- **Clear distinction** between explained and unexplained funding
- **Easy to see** what client disclosed vs what we found
- **Immediate red flags** - unexplained sources stand out
- **Better questions** for client follow-up
- **Transparent** for regulatory review

### ✅ For Compliance
- **Disclosed sources** clearly identified
- **Undisclosed sources** highlighted
- **Risk assessment** easier with separation
- **Audit trail** shows what was explained
- **Regulatory defense** - we identified all sources

### ✅ For Client Communication
- **Specific** about what was verified
- **Clear** about additional sources found
- **Actionable** - client knows what to explain
- **Educational** - shows importance of full disclosure

---

## Technical Implementation

### Matching Logic

```typescript
// For each funding step, check if it matches a verified claim
const isClaimedSource = result.evidence_matches.some(evidence => {
  if (!evidence.verified) return false;
  return evidence.transactions.some(txn => {
    // Match by date and amount
    return step.includes(txn.date) && step.includes(txn.amount.toString());
  });
});

if (isClaimedSource) {
  claimedSteps.push(step);  // From client explanation
} else {
  otherSteps.push(step);    // Other potential funding
}
```

### Data Flow

1. **Get verified claims** from `result.evidence_matches`
2. **Extract transactions** from verified claims
3. **Loop through funding steps** from `best_path.steps`
4. **Match each step** against verified claim transactions
5. **Separate** into claimedSteps and otherSteps
6. **Render** two sections conditionally

---

## Example Output in Decision Box

```
┌──────────────────────────────────────────────────────────────┐
│ ❌ INSUFFICIENT                                        ❌    │
│ Confidence: 40%                                               │
├──────────────────────────────────────────────────────────────┤
│ Assessment Summary                                           │
│                                                              │
│ [Client's SoF Explanation]                                   │
│ [Evidence Review]                                            │
│                                                              │
│ Funding Analysis:                                            │
│ Total funding traced: 100% of purchase amount.              │
│                                                              │
│ INTERPRETATION: [...]                                        │
│                                                              │
│ Funding pathway (from client explanation):                   │
│   • £250,000.00 received into Barclays_****1234 on         │
│     2023-05-15                                              │
│   • £300,000.00 received into HSBC_****5678 on             │
│     2023-07-01                                              │
│                                                              │
│ Other potential funding pathway:                             │
│   • £200,000.00 transferred from Barclays_****1234 on      │
│     2023-06-15                                              │
│   • £50,000.00 received into HSBC_****5678 on              │
│     2023-08-01                                              │
│                                                              │
│ [Transaction Review]                                         │
│ [Red Flags]                                                  │
│ [Regulatory Statement]                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## Regulatory Implications

### Client Disclosed (From Explanation)
- Shows **full disclosure** by client
- **Positive factor** in risk assessment
- **Matches stated sources** to bank evidence
- **Complete audit trail**

### Other Sources (Not Explained)
- **Red flag** - undisclosed sources
- **Risk factor** - why not mentioned?
- **Follow-up required** - get explanation
- **Potential issue** - incomplete disclosure

### Decision Impact

**Scenario A: All from Explanation**
```
✅ Client fully disclosed all sources
✅ Everything explained and verified
✅ Low risk - complete transparency
→ More likely SUFFICIENT
```

**Scenario B: Mix of Sources**
```
⚠️ Some sources disclosed
⚠️ Other sources found not mentioned
⚠️ Medium risk - incomplete disclosure
→ More likely BORDERLINE (need explanations)
```

**Scenario C: Mostly Other Sources**
```
❌ Few disclosed sources verified
❌ Most funding from unexplained sources
❌ High risk - poor disclosure
→ More likely INSUFFICIENT
```

---

## Comparison

### OLD (All Mixed Together)
```
Funding path analysis:
  • £250,000.00 received into Barclays_****1234 on 2023-05-15
  • £200,000.00 transferred from Barclays_****1234 on 2023-06-15
  • £300,000.00 received into HSBC_****5678 on 2023-07-01
  • £50,000.00 received into HSBC_****5678 on 2023-08-01
```

❌ Can't tell what client explained  
❌ Can't identify undisclosed sources  
❌ Hard to assess disclosure quality  
❌ Difficult to target follow-up questions

### NEW (Separated)
```
Funding pathway (from client explanation):
  • £250,000.00 received into Barclays_****1234 on 2023-05-15
  • £300,000.00 received into HSBC_****5678 on 2023-07-01

Other potential funding pathway:
  • £200,000.00 transferred from Barclays_****1234 on 2023-06-15
  • £50,000.00 received into HSBC_****5678 on 2023-08-01
```

✅ Clear what client explained  
✅ Obvious undisclosed sources  
✅ Easy risk assessment  
✅ Specific follow-up targets

---

## Next Actions Impact

### Questions Generated

**For "Other potential funding pathway" entries:**
```
Questions for Client:
1. We identified a £200,000 transfer on 2023-06-15 that was not mentioned 
   in your SoF explanation. Please explain the source of these funds.
   
2. A £50,000 credit on 2023-08-01 was found in your statements. What is 
   the source of this payment?
```

**For "Funding pathway (from client explanation)" entries:**
```
(No questions needed - these are explained and verified)
```

---

## Testing

**URL:** https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai

**Steps:**
1. Navigate: Matters → REF-2024-001 → SoF Assessment
2. Upload: Client info + Comprehensive bank statement
3. Run Assessment
4. **Check Funding Analysis section**

**Expected:**
```
Funding Analysis:
Total funding traced: 100%

[INTERPRETATION if needed]

Funding pathway (from client explanation):
  • [Verified claim transactions only]

Other potential funding pathway:
  • [Alternative sources found in statements]
```

**Look For:**
- Clear separation between sections
- Verified claims in first section
- Unexplained credits in second section
- Both sections may be present depending on data

---

## Summary

**Change:** Split funding pathway into explained vs unexplained sources  
**Benefit:** Clear distinction for regulatory review  
**Impact:** Better risk assessment and client follow-up

**Sections:**
1. **Funding pathway (from client explanation)** - Verified claimed sources
2. **Other potential funding pathway** - Alternative credits requiring explanation

**Status:**
- ✅ Implemented and committed (`b692ab3`)
- ✅ Matches verified claims to funding steps
- ✅ Separates explained from unexplained
- ✅ Ready to test

This separation makes it **immediately clear** to solicitors which sources the client disclosed vs what we found independently - critical for regulatory compliance! 🎯
