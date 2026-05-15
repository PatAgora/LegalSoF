# How to Access and Use Your Test Files

## 📍 Location
All test files are in: `/home/user/webapp/test_data/comprehensive_test/`

## 📦 What You Have

### 5 Complete Test Scenarios

Each scenario has:
- ✅ `client_info.json` - SoF explanation with detailed claims
- ✅ PDF bank statements (matching and non-matching versions)
- ✅ PDF supporting documents (probate grants, completion statements, etc.)

#### Scenario 1: Perfect Match
```
scenario_1_perfect_match/
├── client_info.json                     ← SoF: Inheritance £250k + Property £200k
├── bank_statement_matching.pdf          ← Shows both transactions
└── Supporting docs:
    ├── probate_grant_2023_8765.pdf      ← Margaret Elizabeth Thompson estate
    └── completion_statement_*.pdf       ← 78 Victoria Road, Brighton
```

#### Scenario 2: Missing Solicitor
```
scenario_2_missing_solicitor/
├── client_info.json                     ← SoF: Business Sale £500k + Loan £250k
├── bank_statement_matching.pdf
└── Supporting docs:
    ├── business_sale_*.pdf              ← Missing solicitor field (!)
    └── loan_agreement_*.pdf             ← HSBC loan
```

#### Scenario 3: Amount Mismatch
```
scenario_3_amount_mismatch/
├── client_info.json                     ← SoF: Property £400k + Savings £220k
├── bank_statement_non_matching.pdf      ← Shows £385k and £215k (!)
└── Supporting docs:
    └── completion_statement_*.pdf       ← Shows £385k (not £400k!)
```

#### Scenario 4: Date Discrepancy
```
scenario_4_date_discrepancy/
├── client_info.json                     ← SoF: Inheritance £350k + Business £540k
├── bank_statement_non_matching.pdf      ← Dates don't match claims (!)
└── Supporting docs:
    ├── probate_grant_*.pdf              ← August (claimed June!)
    └── business_sale_*.pdf              ← October (claimed September!)
```

#### Scenario 5: Wrong Document Type
```
scenario_5_wrong_documents/
├── client_info.json                     ← SoF: Gift £100k + Savings £220k
├── bank_statement_matching.pdf
└── Supporting docs:
    ├── gift_letter.pdf                  ← Proper gift letter
    └── credit_card_statement.pdf        ← Wrong doc type (!)
```

## 🚀 How to Run Tests

### Option 1: Quick Test (Easiest)

```bash
# Navigate to test directory
cd /home/user/webapp/test_data/comprehensive_test

# Run all 5 scenarios automatically
python3 run_all_tests.py
```

This will test all scenarios and show you:
- ✅ Which claims are FULLY VERIFIED (100%)
- ⚠️ Which claims REQUIRE REVIEW (<100%)
- 📊 Specific differences found
- 🎯 Confidence percentages

### Option 2: Test One Scenario

```bash
cd /home/user/webapp/test_data/comprehensive_test

# Test a specific scenario
./test_scenario.sh scenario_1_perfect_match

# Available scenarios:
./test_scenario.sh scenario_1_perfect_match
./test_scenario.sh scenario_2_missing_solicitor
./test_scenario.sh scenario_3_amount_mismatch
./test_scenario.sh scenario_4_date_discrepancy
./test_scenario.sh scenario_5_wrong_documents
```

### Option 3: View in Frontend

1. Open the frontend: https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai

2. Upload files manually:
   - Go to any scenario folder
   - Upload the `client_info.json`
   - Upload the bank statement PDF
   - Upload the supporting document PDFs
   - Click "Run Assessment"

## 📄 View Individual Files

### View a client SoF explanation:
```bash
cd /home/user/webapp/test_data/comprehensive_test

# Scenario 1 - Perfect Match
cat scenario_1_perfect_match/client_info.json | python3 -m json.tool
```

### Check a bank statement PDF:
```bash
# See what's in the PDF
python3 << 'EOF'
import PyPDF2
with open('scenario_1_perfect_match/bank_statement_matching.pdf', 'rb') as f:
    pdf = PyPDF2.PdfReader(f)
    print(pdf.pages[0].extract_text())
EOF
```

### List all files:
```bash
cd /home/user/webapp/test_data/comprehensive_test
tree
# or
find . -type f -name "*.pdf" -o -name "*.json" | sort
```

## 🎯 What Each Scenario Tests

| Scenario | What It Tests | Expected Result |
|----------|---------------|-----------------|
| **1 - Perfect Match** | All fields present, amounts match, dates correct | ✅ 100% confidence |
| **2 - Missing Solicitor** | Document missing required field | ⚠️ ~83% confidence |
| **3 - Amount Mismatch** | Document shows different amounts | ⚠️ Amount difference detected |
| **4 - Date Discrepancy** | Document dates don't match claims | ⚠️ Date difference detected |
| **5 - Wrong Doc Type** | Credit card statement instead of bank | ⚠️ Wrong document type |

## 🔍 Key Points

1. **All Bank Statements are PDFs** ✅
   - The system must extract transaction data from PDFs
   - No CSV files - everything is PDF-based

2. **Intentional Discrepancies** ⚠️
   - Some scenarios have purposeful errors
   - These test the verification and difference detection
   - Manual acceptance workflow can be tested on these

3. **Realistic Documents** 📄
   - All PDFs contain realistic content
   - HSBC bank statement format
   - Official-looking probate grants, completion statements, etc.

4. **Complete Coverage** ✅
   - Tests all SoF source types (inheritance, property, business, loan, gift, savings)
   - Tests all document types (probate grants, completion statements, etc.)
   - Tests all verification scenarios (perfect, missing fields, mismatches, date issues, wrong docs)

## 📊 Expected Test Results

When you run the tests, you should see:

**Scenario 1**: 2/2 claims **FULLY VERIFIED (100%)**  
**Scenario 2**: 1/2 claims REQUIRES REVIEW (missing solicitor)  
**Scenario 3**: 2/2 claims REQUIRE REVIEW (amount mismatches)  
**Scenario 4**: 2/2 claims REQUIRE REVIEW (date discrepancies)  
**Scenario 5**: 1/2 claims REQUIRES REVIEW (wrong doc type)  

## 🛠️ Troubleshooting

### If backend is not running:
```bash
cd /home/user/webapp
uvicorn backend.app.main:app --host 0.0.0.0 --port 8001
```

### If you need to regenerate all files:
```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 generate_test_suite.py
```

### If you want to check file sizes:
```bash
cd /home/user/webapp/test_data/comprehensive_test
du -sh scenario_*
```

## 📚 Documentation

- **README.md** - Overview and quick start guide
- **TEST_SUITE_COMPLETE.md** - Comprehensive documentation with all details
- This file - Quick access guide

## 🎉 You're Ready!

You now have **5 complete test scenarios** with **27 PDF files** covering every verification scenario.

**Run the tests now:**
```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 run_all_tests.py
```

Then review the results in the frontend and test the manual acceptance workflow for claims that require review!
