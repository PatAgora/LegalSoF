# How to Load and View Test Scenarios

## 📋 Two Ways to Run Tests

### Option 1: Load ALL Scenarios into Separate Matters (RECOMMENDED) ⭐

**What it does:**
- Loads all 5 scenarios into **separate matters** (Matter 1, 2, 3, 4, 5)
- You can view **ALL scenarios at once** in the frontend
- Navigate between matters to see different test cases

**Run this:**
```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 load_all_scenarios.py
```

**Result:**
- Matter 1: Perfect Match (100% confidence)
- Matter 2: Missing Solicitor (~83% confidence)
- Matter 3: Amount Mismatch
- Matter 4: Date Discrepancy
- Matter 5: Wrong Document Type

**View in UI:**
Each matter will have its own URL:
- https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/1/sof-assessment
- https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/2/sof-assessment
- https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/3/sof-assessment
- https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/4/sof-assessment
- https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/5/sof-assessment

---

### Option 2: Run Tests Sequentially (Testing/Validation)

**What it does:**
- Tests scenarios **one at a time**
- Each scenario **overwrites** the previous one (all use Matter 1)
- Good for **automated testing** and **validation**
- Shows detailed results in terminal

**Run this:**
```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 run_all_tests.py
```

**Result:**
- Runs all 5 scenarios sequentially
- Only the **last scenario** remains in Matter 1
- Detailed terminal output with verification results

---

## 🎯 Which One Should You Use?

### Use `load_all_scenarios.py` if you want to:
✅ **View all test scenarios in the frontend at once**  
✅ Navigate between different matters to see all test cases  
✅ Demonstrate the system with multiple examples  
✅ Compare different verification outcomes side-by-side  

### Use `run_all_tests.py` if you want to:
✅ **Test the system is working correctly**  
✅ See detailed verification logic in terminal  
✅ Validate PDF extraction and matching  
✅ Debug specific scenarios  

---

## 🚀 Recommended Workflow

**Step 1: Load All Scenarios**
```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 load_all_scenarios.py
```

**Step 2: View in Frontend**
Open the frontend and navigate to each matter:
- Go to: https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai
- Click on "Matters" or navigate directly to Matter 1, 2, 3, 4, 5
- View the SoF Assessment for each matter

**Step 3: Test Features**
For each matter, you can:
- View verification status (FULLY VERIFIED vs REQUIRES REVIEW)
- See specific differences detected
- Click "Accept Differences" for claims requiring review
- Check confidence percentages
- Review the audit trail

---

## 📊 Expected Results by Matter

### Matter 1: Perfect Match ✅
**Client:** Residential Property Ltd  
**Claims:**
- Inheritance: £250,000
- Property Sale: £200,000

**Expected:**
- ✅ Both claims FULLY VERIFIED (100%)
- All fields present
- Amounts match exactly
- Dates correct

---

### Matter 2: Missing Solicitor ⚠️
**Client:** Commercial Ventures PLC  
**Claims:**
- Business Sale: £500,000
- Business Loan: £250,000

**Expected:**
- ⚠️ Business Sale: REQUIRES REVIEW (~83%) - Missing solicitor field
- ✅ Business Loan: FULLY VERIFIED (100%)

**Difference:**
- Field: solicitor_firm
- Issue: No solicitor details found
- Severity: missing

---

### Matter 3: Amount Mismatch ❌
**Client:** Property Investors Group  
**Claims:**
- Property Sale: £400,000
- Savings: £220,000

**Expected:**
- ❌ Property Sale: REQUIRES REVIEW - Document shows £385,000 (£15k difference)
- ❌ Savings: REQUIRES REVIEW - Statements show £215,000 (£5k difference)

**Differences:**
- Amount mismatch: claimed vs document
- Both outside 1% tolerance

---

### Matter 4: Date Discrepancy ⚠️
**Client:** Tech Acquisitions Ltd  
**Claims:**
- Inheritance: £350,000
- Business Sale: £540,000

**Expected:**
- ⚠️ Inheritance: REQUIRES REVIEW - Distribution date August (claimed June) - 2 month difference
- ⚠️ Business Sale: REQUIRES REVIEW - Completion October (claimed September) - 1 month difference

**Differences:**
- Date discrepancies in both claims
- Timeline inconsistencies

---

### Matter 5: Wrong Document Type ❌
**Client:** Startup Ventures Ltd  
**Claims:**
- Gift: £100,000
- Savings: £220,000

**Expected:**
- ✅ Gift: FULLY VERIFIED (100%) - Proper gift letter provided
- ❌ Savings: REQUIRES REVIEW - Credit card statement instead of bank statement

**Difference:**
- Wrong document type provided for savings claim

---

## 🔍 What to Look For

When viewing each matter in the UI, check:

1. **Verification Badges**
   - Green ✅ "FULLY VERIFIED (100%)" for perfect matches
   - Yellow ⚠️ "REQUIRES REVIEW (X%)" for issues

2. **Confidence Percentages**
   - 100% for fully verified
   - Lower percentages for missing fields/mismatches

3. **Differences List**
   - Specific fields that are missing or don't match
   - Field name, issue description, severity

4. **Accept Differences Button**
   - Should appear for claims requiring review
   - Test the manual acceptance workflow
   - Provide justification
   - Check audit trail is recorded

5. **Evidence Comparison**
   - Customer claim vs document evidence
   - Side-by-side comparison of values

---

## 💡 Quick Commands

```bash
# Load all scenarios into separate matters (RECOMMENDED)
cd /home/user/webapp/test_data/comprehensive_test
python3 load_all_scenarios.py

# Test scenarios sequentially (for validation)
python3 run_all_tests.py

# Test just one scenario
./test_scenario.sh scenario_1_perfect_match

# View a scenario's client info
cat scenario_1_perfect_match/client_info.json | python3 -m json.tool
```

---

## 🎬 Summary

✅ **`load_all_scenarios.py`** = Load into separate matters → View all in UI  
✅ **`run_all_tests.py`** = Sequential testing → Detailed terminal output  
✅ **`test_scenario.sh`** = Test individual scenario → Quick validation  

**Start here:**
```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 load_all_scenarios.py
```

Then open the frontend and navigate through Matter 1, 2, 3, 4, 5 to see all test scenarios! 🚀
