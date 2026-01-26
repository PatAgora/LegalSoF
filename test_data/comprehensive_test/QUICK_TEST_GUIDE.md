# ⚡ Quick Test Guide

## 🚀 Start Testing in 3 Steps

### Step 1: Open the Application
```
https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai
```

### Step 2: Navigate to a Matter
- **Matter 1** → `/matters/1/sof-assessment` (Perfect Match - 100% verified)
- **Matter 2** → `/matters/2/sof-assessment` (Missing Solicitor - ~83%)
- **Matter 3** → `/matters/3/sof-assessment` (Amount Mismatch)
- **Matter 4** → `/matters/4/sof-assessment` (Date Discrepancy)
- **Matter 5** → `/matters/5/sof-assessment` (Wrong Document Type)

### Step 3: Explore the Assessment Results
Each matter shows:
- ✅ Claims extracted from client info
- ✅ Bank transactions matched to claims
- ✅ Supporting documents verified
- ✅ Comparison view (claim vs documents)
- ✅ Accept Differences workflow (if applicable)

---

## 📊 What Each Scenario Tests

| Matter | Scenario | What It Tests | Expected Result |
|--------|----------|---------------|-----------------|
| **1** | Perfect Match | All data matches perfectly | 100% FULLY VERIFIED |
| **2** | Missing Solicitor | Missing field in document | ~83% REQUIRES REVIEW |
| **3** | Amount Mismatch | £15k & £5k discrepancies | Amount differences detected |
| **4** | Date Discrepancy | 1-2 month date differences | Date differences detected |
| **5** | Wrong Document | Credit card vs bank statement | Wrong document type detected |

---

## 🔍 Quick API Tests

### Check Matter 1 (Perfect Match)
```bash
curl http://localhost:8001/api/v1/matters/1/sof-assessment/results | python3 -m json.tool
```

### Check All Matters Status
```bash
for i in {1..5}; do
  echo "=== Matter $i ==="
  curl -s http://localhost:8001/api/v1/matters/$i/sof-assessment/results \
    | python3 -c "import json, sys; data=json.load(sys.stdin); print('Claims:', len(data.get('assessment', {}).get('claims', [])))"
done
```

### Reload All Scenarios
```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 load_all_scenarios.py
```

---

## ✅ Verification Checklist

Run this verification to confirm everything works:

```bash
cd /home/user/webapp
python3 << 'EOF'
import requests

BASE_URL = "http://localhost:8001"
print("🔍 QUICK VERIFICATION\n")

for matter_id in range(1, 6):
    try:
        response = requests.get(f"{BASE_URL}/api/v1/matters/{matter_id}/sof-assessment/results")
        if response.status_code == 200:
            data = response.json()
            claims = len(data.get('assessment', {}).get('claims', []))
            print(f"✅ Matter {matter_id}: {claims} claims processed")
        else:
            print(f"❌ Matter {matter_id}: Error {response.status_code}")
    except Exception as e:
        print(f"❌ Matter {matter_id}: {str(e)}")

print("\n✅ Done!")
EOF
```

---

## 🎯 Key Features to Test

### 1. Document Verification
- View which documents were used for each claim
- See extracted data from PDFs
- Compare claim vs document fields

### 2. Transaction Matching
- Bank transactions displayed for each claim
- Match quality indicators
- Transaction details (date, amount, description)

### 3. Difference Detection
- Amount mismatches highlighted
- Date discrepancies shown
- Missing fields identified

### 4. Manual Acceptance Workflow
- "Accept Differences" button (for non-100% claims)
- Audit trail of acceptances
- Justification notes

### 5. Risk Assessment
- AML alerts displayed
- Red flags identified
- Overall risk rating

---

## 📁 Test Data Files

All test files are located at:
```
/home/user/webapp/test_data/comprehensive_test/
```

Each scenario contains:
- `client_info.json` - Client and SoF details
- `bank_statement.csv` - Transaction data (2 transactions per scenario)
- Supporting PDFs (probate grants, completion statements, etc.)

---

## 🆘 Troubleshooting

### Backend Not Responding
```bash
curl http://localhost:8001/health
```
Expected: `{"status": "healthy"}`

### Matter Not Found
The database should have 5 matters. Verify:
```bash
cd /home/user/webapp
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/user/webapp/backend')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.matter import Matter

engine = create_engine("sqlite:////home/user/webapp/backend/sof_platform.db")
Session = sessionmaker(bind=engine)
db = Session()

matters = db.query(Matter).all()
for m in matters:
    print(f"Matter {m.id}: {m.client_name}")
db.close()
EOF
```

### Reload Scenarios
```bash
cd /home/user/webapp/test_data/comprehensive_test
python3 load_all_scenarios.py
```

---

## 📞 Quick Links

- **Frontend**: https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs
- **Health**: http://localhost:8001/health
- **GitHub PR**: https://github.com/PatAgora/LegalSoF/pull/1

---

## 🎉 You're Ready!

The application is fully functional with all bugs fixed. Start exploring the UI to see the Source of Funds assessment system in action!

**Happy Testing! 🚀**
