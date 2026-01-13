# 🎯 ANSWER: Yes! Here's How to Load All Test Scenarios

## Question
**"If I run the test script will that upload all the test scenarios into the relevant areas of the application so I can then go in and view what the output looks like across the new matters?"**

## Answer: YES! 

I've created **TWO different scripts** for you:

---

## Option 1: Load ALL Scenarios at Once (RECOMMENDED) ✅

### Script: `load_all_scenarios.py`

This script loads **all 5 test scenarios into SEPARATE matters** (Matter 1-5) so you can view them all in the UI simultaneously.

### What it does:
- ✅ Loads Scenario 1 → **Matter 1** (Perfect Match)
- ✅ Loads Scenario 2 → **Matter 2** (Missing Solicitor)
- ✅ Loads Scenario 3 → **Matter 3** (Amount Mismatch)
- ✅ Loads Scenario 4 → **Matter 4** (Date Discrepancy)
- ✅ Loads Scenario 5 → **Matter 5** (Wrong Document Type)

### Run it:
```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 load_all_scenarios.py
```

### What happens:
1. Uploads client_info.json for each scenario
2. Uploads bank statement PDF for each scenario
3. Uploads supporting document PDFs for each scenario
4. Runs assessment for each scenario
5. Shows you the results summary
6. **Gives you direct URLs** to view each matter in the frontend

### After running, you can view:
- **Matter 1**: https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/1/sof-assessment
- **Matter 2**: https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/2/sof-assessment
- **Matter 3**: https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/3/sof-assessment
- **Matter 4**: https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/4/sof-assessment
- **Matter 5**: https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/5/sof-assessment

---

## Option 2: Test Scenarios Sequentially (for testing)

### Script: `run_all_tests.py`

This script tests all scenarios **sequentially in Matter 1** (overwrites each time). Good for automated testing but you can only see the last scenario in the UI.

### Run it:
```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 run_all_tests.py
```

---

## 📊 What You'll See in the UI

After running `load_all_scenarios.py`, you'll have **5 different matters**, each showing:

### Matter 1: Perfect Match ✅
- Claim 1: Inheritance £250,000 - **FULLY VERIFIED (100%)**
- Claim 2: Property Sale £200,000 - **FULLY VERIFIED (100%)**
- Green badges, no differences

### Matter 2: Missing Solicitor ⚠️
- Claim 1: Business Sale £500,000 - **REQUIRES REVIEW (~83%)**
  - Difference: Missing solicitor field
  - "Accept Differences" button available
- Claim 2: Business Loan £250,000 - **FULLY VERIFIED (100%)**

### Matter 3: Amount Mismatch ❌
- Claim 1: Property Sale £400,000 - **REQUIRES REVIEW**
  - Difference: Document shows £385,000 (£15k difference)
- Claim 2: Savings £220,000 - **REQUIRES REVIEW**
  - Difference: Statements show £215,000 (£5k difference)

### Matter 4: Date Discrepancy ⚠️
- Claim 1: Inheritance £350,000 - **REQUIRES REVIEW**
  - Difference: Distribution date August (claimed June)
- Claim 2: Business Sale £540,000 - **REQUIRES REVIEW**
  - Difference: Completion date October (claimed September)

### Matter 5: Wrong Document Type ❌
- Claim 1: Gift £100,000 - **FULLY VERIFIED (100%)**
- Claim 2: Savings £220,000 - **REQUIRES REVIEW**
  - Difference: Credit card statement provided (wrong type)

---

## 🎬 Complete Workflow

### Step 1: Ensure Backend is Running
```bash
cd /home/user/webapp
# Check if running
curl http://localhost:8001/health

# If not, start it
uvicorn backend.app.main:app --host 0.0.0.0 --port 8001
```

### Step 2: Load All Scenarios
```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 load_all_scenarios.py
```

### Step 3: View in Frontend
Open your browser and navigate through:
- https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai

Click on each matter to see the different scenarios.

---

## 🔍 What to Look For

### In the UI, you should see:

1. **Verification Status**
   - ✅ Green "FULLY VERIFIED (100%)" badges
   - ⚠️ Yellow "REQUIRES REVIEW (X%)" badges
   - Confidence percentages

2. **Evidence Details**
   - Bank transactions matched
   - Supporting documents verified
   - Evidence comparison (claim vs document)

3. **Differences Listed**
   - Specific field name (e.g., "solicitor_firm")
   - Issue description (e.g., "No solicitor details found")
   - Severity level (missing, mismatch, etc.)

4. **Manual Acceptance**
   - "Accept Differences" button for claims requiring review
   - Justification text box
   - Audit trail after acceptance

5. **Overall Summary**
   - Bank transactions: X/Y matched
   - Supporting documents: X/Y verified
   - Fully verified: X/Y claims

---

## 📝 Summary

**YES** - Running `load_all_scenarios.py` will:
✅ Upload all test scenarios  
✅ Process them through the assessment engine  
✅ Create 5 separate matters you can view  
✅ Show you the URLs to access each one  
✅ Preserve all scenarios so you can compare them  

You'll then be able to navigate through Matter 1-5 in the frontend and see how the system handles:
- Perfect matches (100%)
- Missing fields (reduced confidence)
- Amount mismatches
- Date discrepancies
- Wrong document types

**And you can test the manual "Accept Differences" workflow on any claim that requires review!**

---

## 🚀 Run Now

```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 load_all_scenarios.py
```

Then open the frontend and navigate through Matter 1, 2, 3, 4, and 5 to see all the different verification scenarios!
