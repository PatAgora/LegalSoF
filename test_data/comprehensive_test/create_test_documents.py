#!/usr/bin/env python3
"""
Generate test documents with intentional variations for comprehensive testing
"""

# Scenario 1: Perfect Match - Probate Grant (100% confidence expected)
probate_grant_perfect = """
GRANT OF PROBATE

High Court of Justice
Family Division
Principal Registry

Estate of: Elizabeth Mary Johnson (Deceased)
Date of Death: 15th May 2023
Date of Grant: 10th June 2023

Probate Registry Reference: 2023/5678

This is to certify that GRANT OF PROBATE of the estate of the above-named deceased was granted to:

EXECUTOR: John David Thompson
Address: 45 Oak Avenue, London, SW1A 2BB

ESTATE VALUATION:
Gross Estate Value: £625,000.00
Net Estate Value: £580,000.00

DISTRIBUTIONS:
The following distributions have been made from the estate:

1. John David Thompson (Son): £250,000.00
   Account: Barclays Bank PLC, Account ending ****1234
   Payment Date: 15th June 2023
   Reference: Estate Distribution - Probate Grant 2023/5678

2. Sarah Elizabeth Thompson (Daughter): £165,000.00
   Payment Date: 15th June 2023

3. Michael James Thompson (Son): £165,000.00
   Payment Date: 15th June 2023

SOLICITORS ACTING:
Johnson Estate Solicitors
123 Legal Street, London, EC1A 1AA
Reference: EST/2023/5678

Sealed and dated this 10th day of June 2023
"""

# Scenario 2: Missing Field - Property Completion Statement (85% confidence expected)
# INTENTIONALLY MISSING: Solicitor firm details
property_completion_missing_solicitor = """
COMPLETION STATEMENT

Property Sale - Final Account

Property Address: 123 High Street, London, SW1A 1AA
Title Number: LN123456
Vendor: John David Thompson

Completion Date: 20th July 2023
Contract Price: £300,000.00

FINANCIAL BREAKDOWN:
Sale Price: £300,000.00
Less: Mortgage Redemption: £0.00
Less: Estate Agent Fees: £3,600.00
Less: Legal Fees: £1,200.00
Less: Other Costs: £180.00

NET PROCEEDS TO VENDOR: £295,020.00

However, upon final reconciliation and including credits:
FINAL NET PROCEEDS: £300,000.82

PAYMENT DETAILS:
Amount Paid: £300,000.82
Bank: HSBC Bank PLC
Account Number: ****5678
Transfer Date: 20th July 2023
Reference: Property Sale - 123 High Street

NOTES:
- All funds cleared
- Title deed transfer completed
- Keys handed over on completion date

[SOLICITOR DETAILS INTENTIONALLY OMITTED FOR TEST]

Completion Statement Prepared: 20th July 2023
"""

# Scenario 3: Amount Mismatch - Loan Agreement (mismatch: doc shows £155k, customer claimed £150k)
loan_agreement_amount_mismatch = """
BUSINESS LOAN AGREEMENT

NatWest Bank PLC
Business Banking Division

Loan Agreement Number: BL-2024-789012
Date: 10th January 2024

BORROWER: John David Thompson t/a TestCo Acquisition Ltd
Address: 45 Oak Avenue, London, SW1A 2BB

LOAN DETAILS:
Loan Amount: £155,000.00  [NOTE: Customer claimed £150,000]
Interest Rate: 5.5% per annum
Loan Term: 5 years (60 months)
Monthly Repayment: £2,948.00

PURPOSE OF LOAN:
Business expansion and working capital for acquisition of Tech Startup Ltd

DISBURSEMENT DETAILS:
Approved Date: 10th January 2024
Disbursement Date: 15th January 2024
Account: NatWest Business Account ****9012
Reference: Business Loan Disbursement

SECURITY:
Personal Guarantee by John David Thompson
Fixed and Floating Charge over business assets

SPECIAL CONDITIONS:
- Loan proceeds to be used solely for stated business purpose
- Quarterly financial statements required
- Business plan milestones to be met

This agreement is subject to the Bank's standard terms and conditions for business loans.

Signed and Sealed: 10th January 2024

For NatWest Bank PLC:
Sarah Mitchell, Business Lending Manager

Borrower:
John David Thompson
"""

# Scenario 4: Date Discrepancy - Business Sale Agreement (customer said Jan 2023, doc shows Mar 2023)
business_sale_date_discrepancy = """
BUSINESS SALE AND PURCHASE AGREEMENT

Agreement for the sale and purchase of:
DIGITAL SOLUTIONS LTD
Company Number: 12345678

VENDOR: John David Thompson
PURCHASER: TechCorp PLC

Completion Date: 10th March 2023  [NOTE: Customer claimed January 2023]

CONSIDERATION:
Total Purchase Price: £200,000.00

PAYMENT TERMS:
Payment Method: Bank Transfer (CHAPS)
Payment Date: 10th March 2023
Vendor's Account: Lloyds Bank PLC, Account ****3456
Reference: Business Sale Proceeds - Digital Solutions Ltd

ASSETS INCLUDED:
- Goodwill and trading name
- Customer contracts and relationships
- Intellectual property
- Equipment and fixtures
- Domain names and websites

WARRANTIES AND INDEMNITIES:
Standard business sale warranties apply
18-month warranty period

SOLICITORS:
Vendor's Solicitors: Thompson Legal LLP
Purchaser's Solicitors: Corporate Law Partners

This agreement was executed on: 10th March 2023

Vendor Signature: John David Thompson
Purchaser Signature: For TechCorp PLC - James Anderson, Director
"""

# Scenario 5: Wrong Document Type - Credit Card Statement (instead of savings statements)
wrong_document_credit_card = """
CREDIT CARD STATEMENT

Santander UK PLC
Credit Card Services

Cardholder: John David Thompson
Card Number: **** **** **** 2345
Statement Date: 31st March 2024

TRANSACTIONS:
Date: 01/03/2024  Description: Supermarket          Amount: £45.67
Date: 05/03/2024  Description: Petrol Station       Amount: £62.00
Date: 10/03/2024  Description: Online Shopping      Amount: £124.99
Date: 15/03/2024  Description: Restaurant           Amount: £85.50
Date: 20/03/2024  Description: Utility Bill Payment Amount: £150.00
Date: 25/03/2024  Description: Travel Booking       Amount: £450.00

SUMMARY:
Previous Balance: £523.45
New Charges: £918.16
Payments Received: £523.45
Credit Limit: £10,000.00
Available Credit: £9,081.84

Payment Due Date: 25th April 2024
Minimum Payment: £45.00

[NOTE: This is a CREDIT CARD statement, NOT savings statements as required]
"""

# Scenario 6: Gift Letter (perfect for one claim in mixed scenario)
gift_letter_perfect = """
GIFT LETTER

Date: 5th February 2024

To Whom It May Concern,

We, David Michael Thompson and Margaret Anne Thompson, of 78 Elm Road, Surrey, GU12 5XY, hereby confirm that we have gifted the sum of ONE HUNDRED THOUSAND POUNDS (£100,000.00) to our son, John David Thompson, of 45 Oak Avenue, London, SW1A 2BB.

PURPOSE OF GIFT:
This gift is provided to assist with the business acquisition and expansion of his company, TestCo Acquisition Ltd.

GIFT DETAILS:
Amount: £100,000.00
Transfer Date: 10th February 2024
Method: Bank Transfer (CHAPS)
From Account: Our joint account at Halifax Bank
To Account: Business Account ****7890
Reference: Gift Transfer from Parents

DECLARATION:
We confirm that:
1. This is an outright gift with no expectation of repayment
2. This gift is made freely and without coercion
3. We have no financial interest in the business
4. This gift is from our own legitimate funds
5. We do not expect any share or stake in the business

We understand this letter may be used for due diligence and anti-money laundering purposes.

Signed:

David Michael Thompson         Date: 5th February 2024

Margaret Anne Thompson         Date: 5th February 2024

WITNESSES:
Name: Robert Wilson
Address: 82 Elm Road, Surrey, GU12 5XY
Signature: Robert Wilson       Date: 5th February 2024
"""

# Write all documents to text files (will be used to create PDFs)
documents = {
    '1_probate_grant_perfect.txt': probate_grant_perfect,
    '2_property_completion_missing_solicitor.txt': property_completion_missing_solicitor,
    '3_loan_agreement_amount_mismatch.txt': loan_agreement_amount_mismatch,
    '4_business_sale_date_discrepancy.txt': business_sale_date_discrepancy,
    '5_wrong_document_credit_card.txt': wrong_document_credit_card,
    '6_gift_letter_perfect.txt': gift_letter_perfect,
}

import os
for filename, content in documents.items():
    with open(filename, 'w') as f:
        f.write(content.strip())
    print(f"Created: {filename}")

print("\n✅ All test documents created!")
print("\nNOTE: These are text files. You'll need to convert them to PDFs.")
print("For now, they can be read as text by the system for testing.")
