# Transaction Review Integration

## 🎯 Overview

The **Transaction Review** tool from the Due Diligence app has been extracted and integrated into the Legal SoF Platform. This provides per-matter transaction monitoring, AML alerts, and automated compliance checks for source of funds reviews.

## ✅ What's Been Integrated

### Backend Components

#### 1. Database Models (`backend/app/models/transaction.py`)
- ✅ **Transaction** - Bank transactions linked to matters
- ✅ **TransactionAlert** - Automated AML alerts with severity levels
- ✅ **CountryRisk** - Country risk reference data (57 countries seeded)
- ✅ **KYCProfile** - Expected transaction volumes per customer
- ✅ **TransactionConfig** - Configurable monitoring rules and thresholds

#### 2. Database Schema Initialized
```bash
python3 backend/app/db/init_transaction_tables.py
```

**Tables Created:**
- `transactions` - Transaction records
- `transaction_alerts` - Generated alerts
- `ref_country_risk` - Country risk levels (LOW, MEDIUM, HIGH, HIGH_3RD, PROHIBITED)
- `kyc_profiles` - Customer KYC profiles
- `transaction_config` - Rule configuration

**Reference Data Seeded:**
- 57 countries with risk levels (5 prohibited, 13 high-risk, 7 high-3rd, 10 medium, 22 low)
- 15 default configuration settings for thresholds and rule toggles

#### 3. API Endpoints (`backend/app/api/v1/endpoints/transactions.py`) - CREATED
Endpoints ready for implementation:
- `POST /api/v1/matters/{matter_id}/transactions/upload` - Bulk upload CSV
- `GET /api/v1/matters/{matter_id}/transactions` - List all transactions
- `GET /api/v1/matters/{matter_id}/transactions/{txn_id}` - Get single transaction
- `GET /api/v1/matters/{matter_id}/transaction-alerts` - List alerts with filters
- `POST /api/v1/matters/{matter_id}/transaction-alerts/{alert_id}/review` - Review alert
- `GET /api/v1/matters/{matter_id}/transaction-dashboard` - KPIs and metrics
- `POST /api/v1/matters/{matter_id}/run-transaction-checks` - Manual check trigger
- `GET /api/v1/transaction-config` - Get configuration
- `PUT /api/v1/transaction-config` - Update configuration (admin only)

### Frontend Components (TO BE CREATED)

#### React Components Needed
Based on the original app, these components need to be created in `frontend/src/components/TransactionReview/`:

1. **TransactionDashboard.tsx** - KPIs, charts, trends
2. **TransactionAlerts.tsx** - Alert list with filtering
3. **TransactionExplore.tsx** - Transaction search and exploration
4. **TransactionUpload.tsx** - CSV upload interface
5. **TransactionConfig.tsx** - Admin configuration panel

#### Integration with MatterDetailPage
Add a new tab "Transaction Review" to `frontend/src/pages/MatterDetailPage.tsx`

## 🔧 Configuration

### Transaction Monitoring Rules

| Rule | Default Threshold | Description |
|------|------------------|-------------|
| High-Risk Country | £10,000 | Alert on transactions to/from high-risk countries |
| Prohibited Country | £0 (all) | Block transactions to sanctioned countries |
| Cash Deposit | £7,500 | Large cash deposit alerts |
| Cash Withdrawal | £7,500 | Large cash withdrawal alerts |
| Outlier Detection | 5× median | Transactions significantly above normal |
| Velocity Alert | 5 txns in 7 days | Rapid transaction patterns |
| Unusual Narrative | Keywords | Flags suspicious payment descriptions |

### Country Risk Levels

- **PROHIBITED** - UK/EU sanctions (Iran, North Korea, Syria, Russia, Belarus)
- **HIGH** - FATF high-risk (Afghanistan, Myanmar, Yemen, Somalia, etc.)
- **HIGH_3RD** - Money laundering risk (Panama, Cayman Islands, BVI, etc.)
- **MEDIUM** - Emerging markets (China, India, Brazil, UAE, etc.)
- **LOW** - UK, EU, US, developed countries

## 🚀 Next Steps

### 1. Complete API Implementation
```python
# backend/app/api/v1/endpoints/transactions.py

# Implement the CSV upload with transaction parsing
# Implement the alert generation engine
# Implement the dashboard data aggregation
```

### 2. Create Frontend Components
```tsx
// frontend/src/components/TransactionReview/TransactionDashboard.tsx
// Port the React component from DueDiligenceFrontend
```

### 3. Add Transaction Review Tab to Matter Detail Page
```tsx
// frontend/src/pages/MatterDetailPage.tsx

// Add new tab
const tabs = [
  'overview',
  'questionnaire',
  'documents',
  'funds-chain',
  'transaction-review',  // NEW TAB
  'checks',
  'notes',
  'audit-trail'
];
```

### 4. Wire Up API Routes
```python
# backend/app/api/v1/api.py

from app.api.v1.endpoints import transactions

router = APIRouter()
router.include_router(transactions.router, tags=["transactions"])
```

### 5. Test with Sample Data
```python
# Create test matter
# Upload CSV with sample transactions
# Verify alerts are generated
# Check dashboard metrics
```

## 📁 File Structure

```
backend/
├── app/
│   ├── models/
│   │   └── transaction.py                    ✅ Created
│   ├── api/v1/endpoints/
│   │   └── transactions.py                   ✅ Created (needs implementation)
│   └── db/
│       └── init_transaction_tables.py        ✅ Created & Run

frontend/src/components/TransactionReview/
├── TransactionDashboard.tsx                  ⏳ To be created
├── TransactionAlerts.tsx                     ⏳ To be created
├── TransactionExplore.tsx                    ⏳ To be created
├── TransactionUpload.tsx                     ⏳ To be created
└── TransactionConfig.tsx                     ⏳ To be created

frontend/src/pages/
└── MatterDetailPage.tsx                      ⏳ Needs transaction tab
```

## 🔍 Key Features

### Automated Alert Generation
- Real-time monitoring as transactions are uploaded
- Severity scoring (INFO, LOW, MEDIUM, HIGH, CRITICAL)
- Multiple simultaneous rule triggers
- Configurable thresholds

### Dashboard & Analytics
- Total money in/out
- Cash transactions summary
- High-risk payment totals
- Alert trends over time
- Country distribution
- Transaction velocity

### Compliance Workflows
- Alert review and disposition
- False positive marking
- Investigation notes
- Audit trail
- Reviewer assignment

### Data Integration
- CSV bulk upload
- Customer ID linking to matters
- Transaction history tracking
- KYC profile expected volumes

## 🎓 How Transaction Monitoring Works

1. **Upload** - CSV with transactions uploaded per matter
2. **Parse** - Extract transaction details (date, amount, country, narrative)
3. **Enrich** - Look up country risk levels
4. **Check** - Run all enabled rules (7 built-in rules)
5. **Score** - Calculate severity based on triggered rules
6. **Alert** - Create alerts for violations
7. **Review** - Analyst reviews and dispositions alerts
8. **Report** - Include alert summary in SoF report

## 🔐 Security & Compliance

- Per-matter transaction isolation
- Role-based access control (RBAC)
- Audit trail for all reviews
- Configuration versioning
- GDPR-compliant (UK/EU AML requirements)
- No PEP/Sanctions screening (out of scope per requirements)

## 📊 Sample Alerts

**CRITICAL - Prohibited Country**
```
Transaction of £5,000 to Iran (IR) on 2024-01-15
Severity: CRITICAL | Score: 100
Reason: Prohibited country under UK sanctions
```

**HIGH - Large Cash Deposit**
```
Cash deposit of £25,000 on 2024-01-10
Severity: HIGH | Score: 75
Reason: Exceeds cash threshold (£7,500) by £17,500
```

**MEDIUM - Unusual Narrative**
```
Payment of £2,500 with narrative "cryptocurrency purchase"
Severity: MEDIUM | Score: 50
Reason: Contains suspicious keyword: "cryptocurrency"
```

## 📞 Support & Maintenance

### Configuration Updates
Admin users can update thresholds and rule toggles via:
- API: `PUT /api/v1/transaction-config`
- Frontend: Transaction Config admin panel

### Country Risk Updates
Compliance team should periodically review and update country risk levels based on:
- FATF grey/black lists
- UK OFSI sanctions
- EU sanctions
- Internal risk appetite

## ✅ Status: Backend Ready, Frontend Pending

**Completed:**
- ✅ Database models
- ✅ Schema created
- ✅ Reference data seeded
- ✅ API endpoint structure defined
- ✅ Configuration system

**In Progress:**
- ⏳ API endpoint implementation
- ⏳ Transaction upload parser
- ⏳ Alert generation engine

**Todo:**
- ⏳ Frontend React components
- ⏳ Matter detail page integration
- ⏳ CSV upload UI
- ⏳ Dashboard visualizations
- ⏳ End-to-end testing

---

**Ready for development:** Backend foundation is complete. Next step is to implement the API endpoints and create the frontend components.
