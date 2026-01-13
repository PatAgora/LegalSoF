# Test Documents to Create

## Document 1: Probate Grant (PERFECT MATCH) ✅
**Filename:** `probate_grant_johnson.pdf`

```
IN THE HIGH COURT OF JUSTICE
FAMILY DIVISION
PRINCIPAL REGISTRY

GRANT OF PROBATE

In the Estate of ELIZABETH JOHNSON (Deceased)
Date of Death: 15th May 2023
Last Address: 45 Riverside Court, London, SW15 2AB

GRANT OF REPRESENTATION

This is to certify that PROBATE of the Will dated 10th March 2020 
of the above-named deceased was granted by the Principal Registry 
of the Family Division to:

EXECUTOR: John David Thompson
Address: 123 High Street, London, SW1A 1AA

GRANT DATE: 15th June 2023
PROBATE REFERENCE: 2023/PR/12345

ESTATE VALUATION:
Gross Estate Value: £625,000.00
Net Estate Value: £580,000.00

DISTRIBUTIONS TO BENEFICIARIES:
1. John David Thompson (Grandson): £250,000.00
2. Sarah Jane Thompson (Granddaughter): £180,000.00
3. Michael Robert Johnson (Son): £150,000.00

PAYMENT DATE: 15th June 2023
BANK DETAILS: Barclays Bank PLC, Account ending ****1234

Sealed by the Court this 15th day of June 2023
```

**Expected Verification:** 100% confidence - all fields match

---

## Document 2: Property Completion Statement (MISSING SOLICITOR) ⚠️
**Filename:** `property_completion_123_high_street.pdf`

```
PROPERTY COMPLETION STATEMENT

PROPERTY ADDRESS: 123 High Street, London, SW1A 1AA
TITLE NUMBER: TGL789456
DATE OF COMPLETION: 20th July 2023

VENDOR: John David Thompson
PURCHASER: ABC Property Ltd

FINANCIAL SUMMARY:
Contract Price: £300,000.00
Deposit Paid: £30,000.00
Balance Due: £270,000.00

FINAL PAYMENT DETAILS:
Net Proceeds to Vendor: £300,000.82
Payment Date: 20th July 2023
Payment Method: CHAPS Transfer
Bank Account: HSBC Account ****5678

PROPERTY DETAILS:
- 3 Bedroom Semi-Detached House
- Freehold
- Built: 1995
- Last Sold: 2010 for £180,000

[NOTE: Solicitor firm details INTENTIONALLY OMITTED to test missing field detection]
```

**Expected Verification:** ~85% confidence - "Missing: Solicitor Firm"

---

## Document 3: Business Loan Agreement (AMOUNT MISMATCH) 🔴
**Filename:** `natwest_business_loan_agreement.pdf`

```
NATWEST BANK PLC
BUSINESS LOAN AGREEMENT

BORROWER: TestCo Acquisition Ltd
Company Number: 12345678
Registered Address: 10 Tech Park, London, EC1A 1BB

LOAN REFERENCE: BL2024001
AGREEMENT DATE: 10th January 2024

LOAN TERMS:
Principal Amount: £155,000.00
Interest Rate: 5.5% per annum
Term: 5 years
Monthly Repayment: £2,935.00

DRAWDOWN DETAILS:
Drawdown Date: 15th January 2024
Bank Account: NatWest Business Account ****9012
Transfer Reference: BL2024001

PURPOSE: Business expansion and working capital

SECURITY: Personal guarantee by directors

Signed: ________________
Date: 10th January 2024

NatWest Bank PLC
Lending Division
1 Bank Street, London, E14 5NR
```

**Expected Verification:** <100% confidence - "Amount mismatch: document shows £155,000, claim is £150,000"

---

## Document 4: Business Sale Agreement (DATE DISCREPANCY) ⚠️
**Filename:** `business_sale_digital_solutions.pdf`

```
BUSINESS SALE AND PURCHASE AGREEMENT

SELLER: John David Thompson
Trading as: Digital Solutions Ltd
Company Number: 98765432

BUYER: TechCorp PLC
Company Number: 11223344

SALE DATE: 15th March 2023
COMPLETION DATE: 15th March 2023

[NOTE: Customer said "January 2023" but document shows "March 2023"]

BUSINESS DETAILS:
- Digital marketing and web development business
- Established: 2018
- Annual Turnover: £450,000
- Client Base: 50+ active clients

PURCHASE PRICE: £200,000.00

PAYMENT TERMS:
Full payment on completion
Payment Method: Bank Transfer
Completion Date: 15th March 2023
Seller's Bank: Lloyds Bank Account ****3456

ASSETS INCLUDED:
- Client contracts and relationships
- Website and branding
- Equipment and software licenses
- Trading name and goodwill

Signed by both parties on 15th March 2023

SELLER'S SOLICITOR: Smith & Partners LLP
BUYER'S SOLICITOR: Corporate Law Associates
```

**Expected Verification:** <100% confidence - Date discrepancy (March vs January)

---

## Document 5: Credit Card Statement (WRONG DOC TYPE) ❌
**Filename:** `santander_credit_card_statement.pdf`

```
SANTANDER CREDIT CARD STATEMENT

Account Holder: John David Thompson
Card Number: **** **** **** 5678
Statement Period: 1 February 2024 - 29 February 2024

TRANSACTIONS:
Date        Description                     Amount
01/02/2024  Amazon.co.uk                   -£45.99
05/02/2024  Tesco Stores                   -£123.45
12/02/2024  Shell Petrol Station           -£65.00
18/02/2024  British Airways                -£450.00
25/02/2024  Payment Received               +£684.44

SUMMARY:
Previous Balance: £0.00
New Charges: £684.44
Payments: £684.44
Current Balance: £0.00

[NOTE: This is a CREDIT CARD statement, NOT savings account statements]
```

**Expected Verification:** Missing documents error - wrong type

---

## Document 6: Gift Letter (PERFECT MATCH) ✅
**Filename:** `gift_letter_thompson_parents.pdf`

```
GIFT LETTER

From: Mr. David Thompson and Mrs. Margaret Thompson
Address: 78 Garden Lane, Brighton, BN1 4AB
Date: 5th February 2024

To: Mr. John David Thompson
Address: 123 High Street, London, SW1A 1AA

Dear John,

We, David Thompson and Margaret Thompson (your parents), hereby confirm 
that we are making a GIFT of £100,000.00 (One Hundred Thousand Pounds) 
to you, our son, to assist with your business acquisition.

GIFT DETAILS:
Amount: £100,000.00
Date of Gift: 10th February 2024
Payment Method: Bank Transfer
Recipient Account: Business Account ****7890

This is an outright gift with no expectation of repayment. We confirm that:

1. This gift is made freely and without any obligation
2. We have no financial interest in the business being acquired
3. We expect no repayment of this amount
4. This gift does not create any debt or liability

SOURCE OF FUNDS:
These funds come from our joint savings accumulated over our working lives 
and the sale of our previous property in 2022.

We understand this letter may be required for anti-money laundering purposes 
and confirm all information is true and accurate.

Signed: _________________________
        David Thompson
        Date: 5th February 2024

Signed: _________________________
        Margaret Thompson
        Date: 5th February 2024

WITNESS:
Name: James Wilson
Address: 82 Garden Lane, Brighton, BN1 4AB
Signature: _________________
Date: 5th February 2024
```

**Expected Verification:** 100% confidence - all fields match

---

## Summary of Expected Results

| Document | Type | Match Status | Confidence | Issues |
|----------|------|--------------|-----------|--------|
| 1. Probate Grant | Inheritance | ✅ Perfect | 100% | None |
| 2. Property Completion | Property Sale | ⚠️ Missing Field | 85% | No solicitor |
| 3. Loan Agreement | Loan | 🔴 Amount Mismatch | 83% | £155k vs £150k |
| 4. Business Sale | Business Sale | ⚠️ Date Wrong | 85% | March vs Jan |
| 5. Credit Card | Savings | ❌ Wrong Type | 0% | Not savings stmt |
| 6. Gift Letter | Gift | ✅ Perfect | 100% | None |

This will thoroughly test:
- Perfect matches (100% confidence)
- Missing fields detection
- Amount mismatch detection
- Date discrepancy detection
- Wrong document type detection
- Mixed scenarios in single assessment
