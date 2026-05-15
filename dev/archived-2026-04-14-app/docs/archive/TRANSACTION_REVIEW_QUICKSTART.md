# Transaction Review - Quick Start Guide

## 🚀 What Was Integrated

The **Transaction Review** tool from the Due Diligence app is now integrated into the Legal SoF Platform. This provides automated transaction monitoring and AML alerts for source of funds reviews.

---

## ✅ Backend Status: COMPLETE

### Database Tables (5 new tables created)
```sql
✅ transactions           -- Bank transactions linked to matters
✅ transaction_alerts     -- Automated AML alerts
✅ ref_country_risk       -- 57 countries with risk levels
✅ kyc_profiles          -- Expected transaction volumes
✅ transaction_config     -- Monitoring rules (15 settings)
```

### Reference Data Seeded
- **57 countries** with risk classifications:
  - 5 PROHIBITED (Iran, North Korea, Syria, Russia, Belarus)
  - 13 HIGH (Afghanistan, Myanmar, Yemen, etc.)
  - 7 HIGH_3RD (Panama, Cayman Islands, etc.)
  - 10 MEDIUM (China, India, Brazil, etc.)
  - 22 LOW (UK, US, EU, developed nations)

- **15 configuration settings** for monitoring rules:
  - High-risk min amount: £10,000
  - Cash thresholds: £7,500 (deposit/withdrawal)
  - Outlier detection: 5× median
  - Velocity: 5 transactions in 7 days
  - 16 suspicious narrative keywords

---

## ⏳ Frontend Status: PENDING

Need to create React components in `frontend/src/components/TransactionReview/`:

1. **TransactionDashboard.tsx** - KPIs, charts, metrics
2. **TransactionAlerts.tsx** - Alert list with filters
3. **TransactionExplore.tsx** - Transaction search
4. **TransactionUpload.tsx** - CSV upload interface
5. **TransactionConfig.tsx** - Admin config panel

---

## 🎯 How Transaction Monitoring Works

```
1. UPLOAD    → User uploads CSV of bank transactions
2. PARSE     → System extracts date, amount, country, narrative
3. ENRICH    → Lookup country risk level from ref_country_risk
4. CHECK     → Run 7 AML rules (high-risk country, cash, outlier, etc.)
5. SCORE     → Calculate severity (INFO/LOW/MEDIUM/HIGH/CRITICAL)
6. ALERT     → Create transaction_alerts records
7. REVIEW    → Analyst reviews and dispositions alerts
8. REPORT    → Include alert summary in SoF report
```

---

## 🔧 Built-in AML Rules

| Rule | Trigger | Severity |
|------|---------|----------|
| **Prohibited Country** | Transaction to sanctioned country | CRITICAL |
| **High-Risk Country** | Transaction >£10k to high-risk country | HIGH |
| **Large Cash Deposit** | Cash deposit >£7,500 | HIGH |
| **Large Cash Withdrawal** | Cash withdrawal >£7,500 | HIGH |
| **Outlier Detection** | Transaction >5× median | MEDIUM |
| **Velocity Alert** | >5 transactions in 7 days | MEDIUM |
| **Unusual Narrative** | Suspicious keywords in description | LOW-MEDIUM |

---

## 📝 Example Alert

**CRITICAL - Prohibited Country**
```
Transaction ID: TXN-2024-001234
Date: 15/01/2024
Amount: £5,000 GBP
Country: Iran (IR)
Severity: CRITICAL
Score: 100
Reason: Prohibited country under UK sanctions
Status: BLOCKED
```

---

## 🛠️ Next Steps

### Step 1: Implement API Logic
The endpoint structure is defined in `backend/app/api/v1/endpoints/transactions.py` but needs implementation:

```python
# TODO: Implement these functions
- upload_transactions()     # Parse CSV and store
- run_transaction_checks()  # Execute 7 AML rules
- get_transaction_dashboard() # Aggregate KPIs
```

### Step 2: Create Frontend Components
Port the React components from the Due Diligence app and adapt to new API structure.

### Step 3: Add Tab to Matter Detail Page
In `frontend/src/pages/MatterDetailPage.tsx`, add "Transaction Review" as the 8th tab.

---

## 📁 Key Files

**Backend:**
- `backend/app/models/transaction.py` - SQLAlchemy models
- `backend/app/db/init_transaction_tables.py` - DB initialization (already run)
- `backend/app/api/v1/endpoints/transactions.py` - API endpoints (structure only)

**Documentation:**
- `TRANSACTION_REVIEW_INTEGRATION.md` - Full integration guide
- `CURRENT_STATUS.md` - Updated project status
- `TRANSACTION_REVIEW_QUICKSTART.md` - This file

**Original Source:**
- Downloaded from: https://github.com/PatAgora/due-diligence-app
- Tag: v2.0-ai-working-backup
- Location: `/home/user/due-diligence-app-2.0-ai-working-backup/`

---

## 🚀 Testing Once Implemented

1. Create a test matter in the app
2. Prepare CSV with sample transactions:
   ```csv
   id,txn_date,customer_id,direction,amount,currency,country_iso2,narrative
   TXN001,2024-01-15,CUST001,in,5000,GBP,IR,Payment from supplier
   TXN002,2024-01-16,CUST001,out,25000,GBP,GB,Large cash withdrawal
   ```
3. Upload via Transaction Review tab
4. Check that alerts are generated:
   - CRITICAL alert for Iran transaction
   - HIGH alert for large cash withdrawal
5. Review dashboard metrics
6. Disposition alerts (mark as reviewed/false positive)

---

## 📞 Configuration

Admins can update monitoring rules via:
- **API:** `PUT /api/v1/transaction-config`
- **Frontend:** Transaction Config panel (to be created)

Configurable settings:
- Thresholds for each rule
- Enable/disable individual rules
- Narrative keyword list
- Country risk levels

---

## ✅ Current Integration Status

| Component | Status | Notes |
|-----------|--------|-------|
| Database Models | ✅ Complete | 5 tables, 57 countries, 15 configs |
| Database Schema | ✅ Initialized | Run via init_transaction_tables.py |
| API Endpoint Structure | ✅ Defined | Function signatures ready |
| API Logic Implementation | ⏳ Pending | CSV parser, alert engine needed |
| Frontend Components | ⏳ Pending | 5 React components to create |
| Matter Detail Tab | ⏳ Pending | Add 8th tab for transactions |
| Testing | ⏳ Pending | End-to-end workflow |

---

## 🎓 Understanding the Code

**transaction.py** - Five SQLAlchemy models:
```python
Transaction          # Bank transaction records
TransactionAlert     # Generated AML alerts
CountryRisk          # ISO codes with risk levels
KYCProfile          # Expected volumes per customer
TransactionConfig    # Rule thresholds and toggles
```

**init_transaction_tables.py** - Database initialization:
```python
seed_country_risk_data()      # 57 countries
seed_transaction_config()     # 15 rule settings
```

**transactions.py** - API endpoints (to implement):
```python
upload_transactions()         # POST CSV upload
get_transaction_dashboard()   # GET KPIs and metrics
get_transaction_alerts()      # GET alert list with filters
review_alert()                # POST alert review
run_transaction_checks()      # POST manual check trigger
```

---

**Ready to Continue Implementation!**

Backend foundation is complete. Next: implement the API logic and create the frontend components.
