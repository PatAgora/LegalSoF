#!/usr/bin/env python3
"""
Test script for the comprehensive bank statement PDF parser.

This script tests the parser with a sample NatWest-style PDF.
"""

import sys
sys.path.insert(0, '/home/claude/LegalSoF-backup-2026-01-26-full-working-version/backend')

from app.services.bank_statement_pdf_parser import bank_statement_parser

# Create a simple test PDF with reportlab
def create_test_pdf():
    """Create a test NatWest-style bank statement PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    import io
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # Header
    elements.append(Paragraph("NatWest Bank", styles['Heading1']))
    elements.append(Paragraph("Statement of Account", styles['Heading2']))
    elements.append(Spacer(1, 20))
    
    # Account details
    elements.append(Paragraph("Account: Mr John Smith", styles['Normal']))
    elements.append(Paragraph("Account Number: 12345678", styles['Normal']))
    elements.append(Paragraph("Sort Code: 60-00-00", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Transaction table - NatWest style
    table_data = [
        ['Date', 'Description', 'Paid Out', 'Paid In', 'Balance'],
        ['02 Jan', 'OPENING BALANCE', '', '', '1,250.00'],
        ['03 Jan', 'DIRECT DEBIT - INSURANCE CO', '125.50', '', '1,124.50'],
        ['05 Jan', 'BANK TRANSFER FROM J SMITH', '', '500.00', '1,624.50'],
        ['07 Jan', 'CARD PAYMENT - TESCO', '45.67', '', '1,578.83'],
        ['10 Jan', 'SALARY - EMPLOYER LTD', '', '3,500.00', '5,078.83'],
        ['12 Jan', 'STANDING ORDER - RENT', '1,200.00', '', '3,878.83'],
        ['15 Jan', 'CARD PAYMENT - AMAZON', '29.99', '', '3,848.84'],
        ['18 Jan', 'BANK TRANSFER TO SAVINGS', '500.00', '', '3,348.84'],
        ['20 Jan', 'DIRECT DEBIT - COUNCIL TAX', '185.00', '', '3,163.84'],
        ['22 Jan', 'CARD PAYMENT - RESTAURANT', '78.50', '', '3,085.34'],
        ['25 Jan', 'TRANSFER FROM INHERITANCE', '', '50,000.00', '53,085.34'],
        ['26 Jan', 'SOLICITOR FEES - SMITH & CO', '2,500.00', '', '50,585.34'],
        ['28 Jan', 'PROPERTY PURCHASE DEPOSIT', '25,000.00', '', '25,585.34'],
    ]
    
    table = Table(table_data, colWidths=[60, 200, 80, 80, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    
    elements.append(table)
    
    doc.build(elements)
    return buffer.getvalue()


def main():
    print("=" * 60)
    print("Bank Statement PDF Parser Test")
    print("=" * 60)
    
    # Create test PDF
    print("\n📄 Creating test NatWest-style PDF...")
    pdf_bytes = create_test_pdf()
    print(f"   PDF created: {len(pdf_bytes)} bytes")
    
    # Parse the PDF
    print("\n🔍 Parsing PDF...")
    result = bank_statement_parser.parse(pdf_bytes)
    
    # Show results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    print(f"\n✅ Success: {result['success']}")
    print(f"📊 Transactions found: {len(result['transactions'])}")
    print(f"🏦 Bank detected: {result['metadata'].get('bank', 'Unknown')}")
    print(f"📋 Extraction method: {result['metadata'].get('extraction_method', 'Unknown')}")
    
    if result['transactions']:
        print("\n📜 Transactions extracted:")
        print("-" * 60)
        for i, txn in enumerate(result['transactions'], 1):
            direction_symbol = "⬆️" if txn['direction'] == 'credit' else "⬇️"
            print(f"{i:2}. {txn['date']} | {direction_symbol} £{txn['amount']:,.2f} | {txn['description'][:40]}")
        
        # Summary
        credits = sum(t['amount'] for t in result['transactions'] if t['direction'] == 'credit')
        debits = sum(t['amount'] for t in result['transactions'] if t['direction'] == 'debit')
        
        print("-" * 60)
        print(f"Total credits:  £{credits:,.2f}")
        print(f"Total debits:   £{debits:,.2f}")
        print(f"Net movement:   £{credits - debits:,.2f}")
    
    if result.get('error'):
        print(f"\n❌ Error: {result['error']}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
