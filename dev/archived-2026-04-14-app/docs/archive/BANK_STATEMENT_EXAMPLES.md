# 📄 BANK STATEMENT EXAMPLES FOR SOF ASSESSMENT

## 📦 Available Example Files

### 1. **Simple Example** (`example_bank_statement_simple.csv`)
**Use this for:** Quick testing, straightforward scenarios
**Contains:**
- 7 transactions
- Clear inheritance (£250k)
- Property sale (£300k)
- Final business purchase (£500k)
- Clean, easy-to-follow money trail

**Scenario:** 
Client inherited £250,000 and sold property for £300,000, then used £500,000 to purchase a business.

---

### 2. **Comprehensive Example** (`example_bank_statement_comprehensive.csv`)
**Use this for:** Detailed testing, complex scenarios
**Contains:**
- 30 transactions across 2 accounts
- Multiple fund sources:
  - Inheritance (£250k)
  - Property sale (£300k)
  - Business loan (£50k)
  - Family loan (£25k)
  - Dividends & investments
- Professional fees (solicitors, accountants, valuers)
- Realistic transaction flow over 5 months

**Scenario:**
Complex business acquisition funded by inheritance, property sale, commercial loan, and family support.

---

## 📋 CSV File Format

### Required Columns

| Column | Type | Required | Description | Example |
|--------|------|----------|-------------|---------|
| `account_id` | Text | Yes | Account identifier | `Barclays_****1234` |
| `date` | Date | Yes | Transaction date (YYYY-MM-DD) | `2023-06-15` |
| `amount` | Number | Yes | Transaction amount (positive) | `250000.00` |
| `currency` | Text | Yes | Currency code | `GBP` |
| `direction` | Text | Yes | `credit` or `debit` | `credit` |
| `description` | Text | Yes | Transaction description | `Estate Distribution` |
| `counterparty_name` | Text | No | Other party name | `Smith & Partners Solicitors` |
| `balance` | Number | No | Account balance after transaction | `250000.00` |

### Important Notes

1. **Direction:**
   - `credit` = Money coming IN (deposits, receipts)
   - `debit` = Money going OUT (payments, withdrawals)

2. **Amount:**
   - Always positive numbers
   - Use decimal point for pence: `250000.00`
   - No currency symbols (£, $, etc.)
   - No commas in numbers

3. **Date Format:**
   - Must be `YYYY-MM-DD` (e.g., `2023-06-15`)
   - System can parse other formats but this is safest

4. **Account ID:**
   - Any identifier works: `Barclays_****1234`, `Account_A`, `Current_Account`
   - Used to track transfers between accounts

---

## 🎯 How the System Analyzes Statements

### Step 1: Extract Large Credits
Finds transactions where money comes IN (direction = `credit`)
- Looks for amounts > 10% of purchase amount
- Matches against claimed sources in SoF explanation

### Step 2: Match Evidence
Compares bank transactions to claims:
- **Exact match:** Transaction amount matches claim exactly
- **Approximate match:** Within 5% tolerance
- **Strong match:** Amount + counterparty name match

### Step 3: Trace Funding Path
Follows the money from sources to purchase:
- Identifies transfers between accounts
- Calculates total funds traced
- Determines coverage % (traced funds / purchase amount)

### Step 4: Identify Red Flags
Looks for suspicious patterns:
- Large unexplained credits
- Cash deposits over £5,000
- Third-party funding without documentation
- Transactions outside claimed date ranges

---

## 💡 Tips for Creating Your Own Bank Statements

### ✅ Good Practices

1. **Include Account Identifiers**
   ```csv
   account_id,date,amount,currency,direction,description,counterparty_name,balance
   Barclays_1234,2023-06-15,100000.00,GBP,credit,Inheritance,Estate Solicitors,100000.00
   ```

2. **Use Descriptive Descriptions**
   - ❌ Bad: `Payment`, `Transfer`, `Credit`
   - ✅ Good: `Estate Distribution - Probate Grant 2023/4521`, `Property Sale Proceeds - 45 Oak Street`

3. **Include Counterparty Names**
   - Helps the system verify legitimacy
   - Especially important for large transactions

4. **Show Transaction Flow**
   - If funds move between accounts, include both transactions:
   ```csv
   Barclays,2023-06-15,50000,GBP,debit,Transfer to HSBC,HSBC UK,50000
   HSBC,2023-06-15,50000,GBP,credit,Transfer from Barclays,Barclays Bank,50000
   ```

5. **Include Professional Fees**
   - Solicitor fees
   - Accountant fees
   - Valuation fees
   - Adds credibility to the transaction

### ❌ Common Mistakes

1. **Negative Amounts**
   ```csv
   # Wrong:
   amount,direction
   -100.00,debit
   
   # Correct:
   amount,direction
   100.00,debit
   ```

2. **Wrong Date Format**
   ```csv
   # Wrong:
   date
   15/06/2023
   Jun 15, 2023
   
   # Correct:
   date
   2023-06-15
   ```

3. **Missing Required Columns**
   - Must include: account_id, date, amount, currency, direction, description

4. **Currency Symbols in Amount**
   ```csv
   # Wrong:
   amount
   £100,000.00
   
   # Correct:
   amount
   100000.00
   ```

---

## 🧪 Example Scenarios

### Scenario 1: Pure Inheritance
```csv
account_id,date,amount,currency,direction,description,counterparty_name,balance
Current,2023-06-01,500000.00,GBP,credit,Inheritance - Estate of John Smith,Probate Registry,500000.00
Current,2023-06-15,500000.00,GBP,debit,Business Purchase,Target Ltd,0.00
```

**SoF Explanation:**
> "I inherited £500,000 from my late father John Smith. Probate was granted in May 2023. I used these funds to purchase the business in June 2023."

### Scenario 2: Property Sale
```csv
account_id,date,amount,currency,direction,description,counterparty_name,balance
Current,2023-07-01,750000.00,GBP,credit,Property Sale - 10 Main Street,Smith Solicitors,750000.00
Current,2023-07-02,3000.00,GBP,debit,Solicitor Fees,Smith Solicitors,747000.00
Current,2023-07-15,500000.00,GBP,debit,Business Acquisition,Business Ltd,247000.00
```

**SoF Explanation:**
> "I sold my residential property at 10 Main Street for £750,000 in July 2023. After legal fees, I used £500,000 to acquire the target business."

### Scenario 3: Mixed Sources
```csv
account_id,date,amount,currency,direction,description,counterparty_name,balance
Current,2023-05-01,200000.00,GBP,credit,Inheritance,Probate Registry,200000.00
Current,2023-06-01,250000.00,GBP,credit,Property Sale,Property Solicitors,450000.00
Current,2023-06-15,100000.00,GBP,credit,Business Loan,HSBC Commercial,550000.00
Current,2023-07-01,500000.00,GBP,debit,Business Purchase,Target Business,50000.00
```

**SoF Explanation:**
> "I inherited £200,000, sold my property for £250,000, and obtained a £100,000 commercial loan. Total £550,000 was used to fund the £500,000 business purchase."

---

## 📥 How to Upload

### In the SoF Assessment Interface:

1. Navigate to: **Matters → REF-2024-001 → 📋 SoF Assessment**
2. Click the **🏦 Bank Statements** tile
3. Click **"Choose CSV/PDF"**
4. Select your CSV file
5. System will:
   - Parse all transactions
   - Validate format
   - Count total transactions
   - Show: ✓ X transaction(s)

### You Can Upload Multiple Files:
- Different accounts
- Different time periods
- System combines all transactions for analysis

---

## 🎯 What Happens Next

Once you have:
- ✅ Client Info (manual or uploaded)
- ✅ Bank Statements (CSV uploaded)

Click **"🚀 Run SoF Assessment"**

The system will:
1. Extract claims from SoF explanation
2. Match transactions to claims
3. Trace funding path
4. Fetch Transaction Review alerts (30 alerts for Matter 1)
5. Identify red flags
6. Calculate confidence score
7. Generate outcome: SUFFICIENT / BORDERLINE / INSUFFICIENT
8. Produce audit-ready file note

---

## 📁 File Locations

All example files are in: `/home/user/webapp/test_data/`

- `example_bank_statement_simple.csv` - Quick test (7 transactions)
- `example_bank_statement_comprehensive.csv` - Detailed test (30 transactions)
- `client_info.json` - Example client info file
- `bank_statements.csv` - Original test file (10 transactions)

---

## 🚀 Ready to Test!

**Download Location:**
- Simple: `/home/user/webapp/test_data/example_bank_statement_simple.csv`
- Comprehensive: `/home/user/webapp/test_data/example_bank_statement_comprehensive.csv`

**Test URL:**
https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai

**Steps:**
1. Go to Matters → REF-2024-001 → SoF Assessment
2. Enter Client Info manually OR upload `client_info.json`
3. Upload one of the example bank statements
4. Click "Run Assessment"
5. Review comprehensive results!

---

**Need help?** The system provides detailed error messages if the CSV format is incorrect.
