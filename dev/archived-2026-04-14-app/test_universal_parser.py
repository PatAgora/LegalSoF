#!/usr/bin/env python3
"""
Comprehensive test for Universal Financial Parser

Tests:
1. NatWest PDF (UK traditional bank)
2. Monzo CSV (UK digital bank)  
3. Chase CSV (US bank)
4. Image/Screenshot OCR
5. Various date formats
6. Various column formats
"""

import sys
sys.path.insert(0, '/home/claude/LegalSoF-backup-2026-01-26-full-working-version/backend')

from app.services.universal_financial_parser import universal_parser

# Create test files
def create_natwest_pdf():
    """Create NatWest-style PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    import io
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph("NatWest Bank Statement", styles['Heading1']))
    elements.append(Spacer(1, 20))
    
    # NatWest format: Date | Description | Paid Out | Paid In | Balance
    table_data = [
        ['Date', 'Description', 'Paid Out', 'Paid In', 'Balance'],
        ['02 Jan', 'SALARY - EMPLOYER LTD', '', '3,500.00', '3,500.00'],
        ['03 Jan', 'DIRECT DEBIT - INSURANCE', '125.50', '', '3,374.50'],
        ['05 Jan', 'CARD PAYMENT - TESCO', '45.67', '', '3,328.83'],
        ['10 Jan', 'TRANSFER FROM J SMITH', '', '500.00', '3,828.83'],
        ['15 Jan', 'STANDING ORDER - RENT', '1,200.00', '', '2,628.83'],
        ['20 Jan', 'FASTER PAYMENT - SAVINGS', '500.00', '', '2,128.83'],
    ]
    
    table = Table(table_data, colWidths=[60, 200, 80, 80, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)
    
    doc.build(elements)
    return buffer.getvalue()


def create_monzo_csv():
    """Create Monzo-style CSV."""
    return b"""Transaction ID,Date,Time,Type,Name,Emoji,Category,Amount,Currency,Local amount,Local currency,Notes and #tags,Address,Receipt,Description,Category split
tx_001,02/01/2025,10:30:45,Card payment,Tesco,,Groceries,-45.67,GBP,-45.67,GBP,Weekly shop,123 High St,,Card payment to Tesco,
tx_002,03/01/2025,09:15:00,Direct Debit,Netflix,,Entertainment,-15.99,GBP,-15.99,GBP,,,Monthly subscription,,
tx_003,05/01/2025,14:00:00,Faster payment,John Smith,,Income,500.00,GBP,500.00,GBP,Rent share,,,Transfer from John,
tx_004,10/01/2025,08:00:00,Direct Debit,Council Tax,,Bills,-185.00,GBP,-185.00,GBP,,,Council Tax,
tx_005,15/01/2025,12:30:00,Card payment,Amazon,,Shopping,-29.99,GBP,-29.99,GBP,Books,,,Amazon purchase,
tx_006,20/01/2025,09:00:00,Salary,Employer Ltd,,Income,3500.00,GBP,3500.00,GBP,January salary,,,Monthly salary,
"""


def create_starling_csv():
    """Create Starling-style CSV."""
    return b"""Date,Counter Party,Reference,Type,Amount (GBP),Balance (GBP)
02/01/2025,Employer Ltd,SALARY JAN,Faster Payment,3500.00,3500.00
03/01/2025,Sky UK,SKY123456,Direct Debit,-45.00,3455.00
05/01/2025,Sainsburys,CARD PAYMENT,Card Payment,-32.50,3422.50
07/01/2025,John Smith,TRANSFER,Faster Payment,250.00,3672.50
10/01/2025,Landlord,RENT JAN,Standing Order,-1200.00,2472.50
15/01/2025,Amazon,AMZN123,Card Payment,-19.99,2452.51
"""


def create_revolut_csv():
    """Create Revolut-style CSV."""
    return b"""Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance
CARD_PAYMENT,Current,2025-01-02 10:30:00,2025-01-02 10:30:00,Uber,-15.50,0.00,GBP,COMPLETED,2984.50
TRANSFER,Current,2025-01-03 09:00:00,2025-01-03 09:00:00,To John Smith,-100.00,0.00,GBP,COMPLETED,2884.50
TOPUP,Current,2025-01-05 14:00:00,2025-01-05 14:00:00,Top-Up by *1234,500.00,0.00,GBP,COMPLETED,3384.50
CARD_PAYMENT,Current,2025-01-07 12:30:00,2025-01-07 12:30:00,Deliveroo,-22.45,0.00,GBP,COMPLETED,3362.05
EXCHANGE,Current,2025-01-10 08:00:00,2025-01-10 08:00:00,Exchanged to EUR,-200.00,0.00,GBP,COMPLETED,3162.05
"""


def create_chase_us_csv():
    """Create US Chase-style CSV."""
    return b"""Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
DEBIT,01/02/2025,STARBUCKS STORE #1234,-5.75,ACH_DEBIT,2994.25,
CREDIT,01/03/2025,PAYROLL - ACME CORP,3500.00,ACH_CREDIT,6494.25,
DEBIT,01/05/2025,AMAZON.COM,-89.99,DEBIT_CARD,6404.26,
DEBIT,01/07/2025,COMCAST CABLE,-125.00,ACH_DEBIT,6279.26,
CREDIT,01/10/2025,VENMO PAYMENT FROM JOHN,50.00,ACH_CREDIT,6329.26,
DEBIT,01/12/2025,CHECK #1234,-500.00,CHECK,5829.26,1234
"""


def create_amex_csv():
    """Create American Express credit card CSV."""
    return b"""Date,Description,Card Member,Account #,Amount
01/02/2025,HILTON HOTELS,JOHN SMITH,XXXX-XXXXXX-12345,250.00
01/05/2025,AMAZON MARKETPLACE,JOHN SMITH,XXXX-XXXXXX-12345,45.99
01/07/2025,UBER EATS,JOHN SMITH,XXXX-XXXXXX-12345,32.50
01/10/2025,PAYMENT RECEIVED - THANK YOU,JOHN SMITH,XXXX-XXXXXX-12345,-500.00
01/12/2025,TESCO STORES,JOHN SMITH,XXXX-XXXXXX-12345,78.25
"""


def test_parser(name: str, content: bytes, filename: str):
    """Test parser with given content."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)
    
    result = universal_parser.parse(content, filename=filename)
    
    print(f"\n✅ Success: {result['success']}")
    print(f"📊 Transactions: {len(result['transactions'])}")
    print(f"🏦 Bank: {result['metadata'].get('bank', 'Unknown')}")
    print(f"📋 Method: {result['metadata'].get('extraction_method', 'Unknown')}")
    
    if result['transactions']:
        print("\n📜 Sample transactions:")
        for txn in result['transactions'][:5]:
            direction = "⬆️" if txn['direction'] == 'credit' else "⬇️"
            print(f"   {txn['date']} | {direction} £{txn['amount']:,.2f} | {txn['description'][:35]}")
        
        if len(result['transactions']) > 5:
            print(f"   ... and {len(result['transactions']) - 5} more")
    
    if result.get('error'):
        print(f"\n❌ Error: {result['error']}")
    
    return result


def main():
    print("="*60)
    print("UNIVERSAL FINANCIAL PARSER - COMPREHENSIVE TEST")
    print("="*60)
    
    results = []
    
    # Test 1: NatWest PDF
    pdf_content = create_natwest_pdf()
    results.append(('NatWest PDF', test_parser("NatWest PDF (UK Traditional)", pdf_content, "natwest_statement.pdf")))
    
    # Test 2: Monzo CSV
    results.append(('Monzo CSV', test_parser("Monzo CSV (UK Digital)", create_monzo_csv(), "monzo_transactions.csv")))
    
    # Test 3: Starling CSV
    results.append(('Starling CSV', test_parser("Starling CSV (UK Digital)", create_starling_csv(), "starling_statement.csv")))
    
    # Test 4: Revolut CSV
    results.append(('Revolut CSV', test_parser("Revolut CSV (Multi-currency)", create_revolut_csv(), "revolut_statement.csv")))
    
    # Test 5: Chase US CSV
    results.append(('Chase US CSV', test_parser("Chase CSV (US Bank)", create_chase_us_csv(), "chase_statement.csv")))
    
    # Test 6: Amex Credit Card
    results.append(('Amex CSV', test_parser("American Express (Credit Card)", create_amex_csv(), "amex_statement.csv")))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    total_success = 0
    total_txns = 0
    
    for name, result in results:
        status = "✅" if result['success'] else "❌"
        txn_count = len(result['transactions'])
        total_txns += txn_count
        if result['success']:
            total_success += 1
        print(f"{status} {name}: {txn_count} transactions")
    
    print(f"\n📊 Total: {total_success}/{len(results)} tests passed")
    print(f"📊 Total transactions extracted: {total_txns}")
    print("="*60)


if __name__ == "__main__":
    main()
