#!/usr/bin/env python3
"""
Comprehensive Test Suite Generator for SoF Assessment System
Generates realistic test data including:
- Multiple client info files with different SoF scenarios
- PDF bank statements (matching and non-matching)
- Supporting documents (matching and non-matching)
"""

import json
import os
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import random

# Ensure output directory exists
OUTPUT_DIR = "/home/user/webapp/test_data/comprehensive_test"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Test scenarios
TEST_SCENARIOS = {
    "scenario_1_perfect_match": {
        "name": "Perfect Match - All Documents Verified",
        "client_name": "Residential Property Ltd",
        "client_id": "TEST-001",
        "matter_id": "MAT-2024-001",
        "purchase_amount": 450000,
        "sources": [
            {
                "type": "inheritance",
                "amount": 250000,
                "description": "Inheritance from Estate of Margaret Elizabeth Thompson",
                "deceased_name": "Margaret Elizabeth Thompson",
                "probate_ref": "2023/8765",
                "date_of_death": "2023-03-15",
                "distribution_date": "2023-08-20"
            },
            {
                "type": "property_sale",
                "amount": 200000,
                "description": "Sale of residential property at 78 Victoria Road, Brighton",
                "property_address": "78 Victoria Road, Brighton, BN1 3FS",
                "title_number": "ESX234567",
                "completion_date": "2023-09-10",
                "solicitor": "Brighton Conveyancing LLP"
            }
        ]
    },
    "scenario_2_missing_solicitor": {
        "name": "Missing Solicitor Field",
        "client_name": "Commercial Ventures PLC",
        "client_id": "TEST-002",
        "matter_id": "MAT-2024-002",
        "purchase_amount": 750000,
        "sources": [
            {
                "type": "business_sale",
                "amount": 500000,
                "description": "Sale of Digital Marketing Agency Ltd",
                "company_name": "Digital Marketing Agency Ltd",
                "company_number": "08765432",
                "completion_date": "2023-10-15"
                # Missing solicitor - will trigger REQUIRES REVIEW
            },
            {
                "type": "business_loan",
                "amount": 250000,
                "description": "Business loan from HSBC Bank",
                "lender": "HSBC Bank PLC",
                "loan_date": "2023-11-01",
                "account_number": "****9876"
            }
        ]
    },
    "scenario_3_amount_mismatch": {
        "name": "Amount Mismatch - Documents Show Different Values",
        "client_name": "Property Investors Group",
        "client_id": "TEST-003",
        "matter_id": "MAT-2024-003",
        "purchase_amount": 620000,
        "sources": [
            {
                "type": "property_sale",
                "amount": 400000,  # Client claims £400k
                "description": "Sale of flat at 15A Kensington Gardens",
                "property_address": "15A Kensington Gardens, London, W2 4RU",
                "title_number": "NGL456789",
                "completion_date": "2023-07-22"
                # Document will show £385,000 (£15k difference)
            },
            {
                "type": "savings",
                "amount": 220000,  # Client claims £220k
                "description": "Personal savings accumulated over 15 years",
                "bank": "Santander UK",
                "account_number": "****3456"
                # Statements will show £215,000 (£5k difference)
            }
        ]
    },
    "scenario_4_date_discrepancy": {
        "name": "Date Discrepancy - Timeline Inconsistencies",
        "client_name": "Tech Acquisitions Ltd",
        "client_id": "TEST-004",
        "matter_id": "MAT-2024-004",
        "purchase_amount": 890000,
        "sources": [
            {
                "type": "inheritance",
                "amount": 350000,
                "description": "Inheritance from Estate of Robert James Wilson",
                "deceased_name": "Robert James Wilson",
                "probate_ref": "2023/5432",
                "date_of_death": "2023-01-10",
                "distribution_date": "2023-06-15"  # Client claims June
                # Document will show distribution in August (2 month difference)
            },
            {
                "type": "business_sale",
                "amount": 540000,
                "description": "Sale of Software Development Ltd",
                "company_name": "Software Development Ltd",
                "company_number": "09876543",
                "completion_date": "2023-09-30",  # Client claims September
                "solicitor": "Legal Partners LLP"
                # Document will show October completion (1 month difference)
            }
        ]
    },
    "scenario_5_wrong_documents": {
        "name": "Wrong Document Types - Credit Card Statements Instead of Proper Docs",
        "client_name": "Startup Ventures Ltd",
        "client_id": "TEST-005",
        "matter_id": "MAT-2024-005",
        "purchase_amount": 320000,
        "sources": [
            {
                "type": "gift",
                "amount": 100000,
                "description": "Gift from parents John and Sarah Mitchell",
                "donor_name": "John and Sarah Mitchell",
                "gift_date": "2023-10-01"
                # Will have proper gift letter
            },
            {
                "type": "savings",
                "amount": 220000,
                "description": "Savings from salary over 10 years",
                "bank": "NatWest",
                "account_number": "****7890"
                # Will provide credit card statement instead of bank statement
            }
        ]
    }
}


def create_client_info(scenario_id, scenario_data):
    """Create client_info.json file for a scenario"""
    
    client_info = {
        "client_info": {
            "client_name": scenario_data["client_name"],
            "client_id": scenario_data["client_id"],
            "matter_id": scenario_data["matter_id"],
            "client_risk_rating": "medium",
            "is_pep": False,
            "business_sector": "Real Estate Investment" if "Property" in scenario_data["client_name"] else "Business Services",
            "high_risk_jurisdictions": [],
            "purchase": {
                "description": "Purchase of commercial property / business acquisition",
                "amount": scenario_data["purchase_amount"],
                "currency": "GBP",
                "expected_payment_date": "2024-01-15"
            },
            "sof_explanation": {
                "total_funds": scenario_data["purchase_amount"],
                "currency": "GBP",
                "sources": []
            },
            "bank_statement_period": {
                "start_date": "2023-01-01",
                "end_date": "2023-12-31"
            },
            "known_documents": []
        }
    }
    
    # Add sources to SoF explanation
    for source in scenario_data["sources"]:
        sof_source = {
            "source_type": source["type"],
            "amount": source["amount"],
            "currency": "GBP",
            "description": source["description"]
        }
        
        # Add type-specific fields
        if source["type"] == "inheritance":
            sof_source.update({
                "deceased_name": source.get("deceased_name"),
                "probate_reference": source.get("probate_ref"),
                "date_of_death": source.get("date_of_death"),
                "distribution_date": source.get("distribution_date")
            })
            client_info["client_info"]["known_documents"].append({
                "type": "probate_grant",
                "description": f"Probate Grant for {source.get('deceased_name')}"
            })
            
        elif source["type"] == "property_sale":
            sof_source.update({
                "property_address": source.get("property_address"),
                "title_number": source.get("title_number"),
                "completion_date": source.get("completion_date"),
                "solicitor_firm": source.get("solicitor")
            })
            client_info["client_info"]["known_documents"].append({
                "type": "completion_statement",
                "description": f"Completion Statement for {source.get('property_address')}"
            })
            
        elif source["type"] == "business_sale":
            sof_source.update({
                "company_name": source.get("company_name"),
                "company_number": source.get("company_number"),
                "completion_date": source.get("completion_date"),
                "solicitor_firm": source.get("solicitor")
            })
            client_info["client_info"]["known_documents"].append({
                "type": "business_sale_agreement",
                "description": f"Sale Agreement for {source.get('company_name')}"
            })
            
        elif source["type"] == "business_loan":
            sof_source.update({
                "lender": source.get("lender"),
                "loan_date": source.get("loan_date"),
                "account_number": source.get("account_number")
            })
            client_info["client_info"]["known_documents"].append({
                "type": "loan_agreement",
                "description": f"Loan Agreement with {source.get('lender')}"
            })
            
        elif source["type"] == "gift":
            sof_source.update({
                "donor_name": source.get("donor_name"),
                "gift_date": source.get("gift_date")
            })
            client_info["client_info"]["known_documents"].append({
                "type": "gift_letter",
                "description": f"Gift Letter from {source.get('donor_name')}"
            })
            
        elif source["type"] == "savings":
            sof_source.update({
                "bank": source.get("bank"),
                "account_number": source.get("account_number")
            })
            client_info["client_info"]["known_documents"].append({
                "type": "bank_statements",
                "description": f"Bank statements from {source.get('bank')}"
            })
        
        client_info["client_info"]["sof_explanation"]["sources"].append(sof_source)
    
    # Write to file
    output_path = os.path.join(OUTPUT_DIR, f"{scenario_id}/client_info.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(client_info, f, indent=2)
    
    print(f"✓ Created {output_path}")
    return client_info


def create_pdf_bank_statement(scenario_id, scenario_data, matching=True):
    """Create realistic PDF bank statement"""
    
    filename = f"{scenario_id}/bank_statement_{'matching' if matching else 'non_matching'}.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#003366'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#003366'),
        spaceAfter=12
    )
    
    # Bank header
    story.append(Paragraph("HSBC BANK PLC", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Account details
    story.append(Paragraph(f"<b>Account Holder:</b> {scenario_data['client_name']}", header_style))
    story.append(Paragraph(f"<b>Account Number:</b> ****5678", header_style))
    story.append(Paragraph(f"<b>Sort Code:</b> 40-47-84", header_style))
    story.append(Paragraph(f"<b>Statement Period:</b> 01 January 2023 - 31 December 2023", header_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Transaction table
    transactions = []
    transactions.append(['Date', 'Description', 'Paid Out', 'Paid In', 'Balance'])
    
    balance = 5000.00
    
    # Generate transactions based on sources
    for source in scenario_data['sources']:
        if source['type'] == 'inheritance':
            amount = source['amount']
            if not matching:
                amount = amount * 0.95  # 5% less than claimed
            
            date = source.get('distribution_date', '2023-08-20')
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            
            transactions.append([
                date_obj.strftime('%d/%m/%Y'),
                f"Transfer from Estate Executors - {source.get('deceased_name', 'Estate')}",
                '',
                f"£{amount:,.2f}",
                f"£{balance + amount:,.2f}"
            ])
            balance += amount
            
        elif source['type'] == 'property_sale':
            amount = source['amount']
            if not matching:
                amount = amount * 0.9625  # Reduced by ~4% (£15k on £400k)
            
            date = source.get('completion_date', '2023-09-10')
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            
            transactions.append([
                date_obj.strftime('%d/%m/%Y'),
                f"Property Sale - {source.get('property_address', 'Property Sale')}",
                '',
                f"£{amount:,.2f}",
                f"£{balance + amount:,.2f}"
            ])
            balance += amount
            
        elif source['type'] == 'business_sale':
            amount = source['amount']
            if not matching:
                # Adjust date by 1 month for date discrepancy test
                date = source.get('completion_date', '2023-09-30')
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                date_obj = date_obj + timedelta(days=30)
                date = date_obj.strftime('%Y-%m-%d')
            else:
                date = source.get('completion_date', '2023-09-30')
                date_obj = datetime.strptime(date, '%Y-%m-%d')
            
            transactions.append([
                date_obj.strftime('%d/%m/%Y'),
                f"Business Sale - {source.get('company_name', 'Company')}",
                '',
                f"£{amount:,.2f}",
                f"£{balance + amount:,.2f}"
            ])
            balance += amount
            
        elif source['type'] == 'business_loan':
            amount = source['amount']
            date = source.get('loan_date', '2023-11-01')
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            
            transactions.append([
                date_obj.strftime('%d/%m/%Y'),
                f"Loan Advance - {source.get('lender', 'Bank Loan')}",
                '',
                f"£{amount:,.2f}",
                f"£{balance + amount:,.2f}"
            ])
            balance += amount
            
        elif source['type'] == 'gift':
            amount = source['amount']
            date = source.get('gift_date', '2023-10-01')
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            
            transactions.append([
                date_obj.strftime('%d/%m/%Y'),
                f"Gift from {source.get('donor_name', 'Family')}",
                '',
                f"£{amount:,.2f}",
                f"£{balance + amount:,.2f}"
            ])
            balance += amount
            
        elif source['type'] == 'savings':
            amount = source['amount']
            if not matching:
                amount = amount * 0.977  # Slightly less (£5k on £220k)
            
            # Split savings into multiple deposits to look realistic
            num_deposits = 5
            deposit_amount = amount / num_deposits
            
            for i in range(num_deposits):
                months_ago = 12 - (i * 2)
                date_obj = datetime(2023, months_ago, 15)
                
                transactions.append([
                    date_obj.strftime('%d/%m/%Y'),
                    f"Transfer from Savings - {source.get('bank', 'Savings Account')}",
                    '',
                    f"£{deposit_amount:,.2f}",
                    f"£{balance + deposit_amount:,.2f}"
                ])
                balance += deposit_amount
    
    # Add some regular transactions to make it look realistic
    regular_transactions = [
        ('05/01/2023', 'Salary Payment', '', '£5,500.00'),
        ('10/02/2023', 'Utility Bill', '£150.00', ''),
        ('15/03/2023', 'Salary Payment', '', '£5,500.00'),
        ('20/04/2023', 'Mortgage Payment', '£1,200.00', ''),
    ]
    
    for trans in regular_transactions:
        transactions.insert(1, [trans[0], trans[1], trans[2], trans[3], ''])
    
    # Create table
    table = Table(transactions, colWidths=[80, 220, 80, 80, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')])
    ]))
    
    story.append(table)
    
    # Footer
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("<i>This is a computer-generated statement. HSBC Bank PLC is authorised by the Prudential Regulation Authority and regulated by the Financial Conduct Authority.</i>", styles['Normal']))
    
    doc.build(story)
    print(f"✓ Created {output_path}")


def create_probate_grant_pdf(scenario_id, source_data, matching=True):
    """Create probate grant PDF"""
    
    filename = f"{scenario_id}/probate_grant_{source_data.get('probate_ref', 'REF').replace('/', '_')}.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    story.append(Paragraph("HM COURTS & TRIBUNALS SERVICE", title_style))
    story.append(Paragraph("GRANT OF PROBATE", title_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Adjust distribution date if non-matching
    distribution_date = source_data.get('distribution_date', '2023-08-20')
    if not matching:
        # Add 2 months for date discrepancy
        date_obj = datetime.strptime(distribution_date, '%Y-%m-%d')
        date_obj = date_obj + timedelta(days=60)
        distribution_date = date_obj.strftime('%Y-%m-%d')
    
    content = f"""
    <b>Probate Reference:</b> {source_data.get('probate_ref', 'N/A')}<br/>
    <b>Deceased:</b> {source_data.get('deceased_name', 'N/A')}<br/>
    <b>Date of Death:</b> {source_data.get('date_of_death', 'N/A')}<br/>
    <b>Grant Issued:</b> {source_data.get('date_of_death', '2023-05-01')}<br/>
    <br/>
    <b>Gross Estate Value:</b> £{source_data.get('amount', 0) * 1.1:,.2f}<br/>
    <b>Net Estate Value:</b> £{source_data.get('amount', 0):,.2f}<br/>
    <br/>
    <b>Executor:</b> Thompson Family Solicitors<br/>
    <b>Beneficiary:</b> [Client Name]<br/>
    <br/>
    <b>Distribution Details:</b><br/>
    Date of Distribution: {distribution_date}<br/>
    Amount Distributed: £{source_data.get('amount', 0):,.2f}<br/>
    Bank Account: ****5678<br/>
    Payment Reference: Estate Distribution - {source_data.get('probate_ref', 'REF')}<br/>
    <br/>
    This grant authorizes the executor to administer the estate of the deceased.
    """
    
    story.append(Paragraph(content, styles['Normal']))
    
    doc.build(story)
    print(f"✓ Created {output_path}")


def create_completion_statement_pdf(scenario_id, source_data, matching=True):
    """Create property completion statement PDF"""
    
    safe_address = source_data.get('property_address', 'Property').replace(',', '').replace(' ', '_')[:30]
    filename = f"{scenario_id}/completion_statement_{safe_address}.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    story.append(Paragraph("COMPLETION STATEMENT", title_style))
    story.append(Paragraph("Property Sale", ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=12, alignment=TA_CENTER, spaceAfter=20)))
    story.append(Spacer(1, 0.3*inch))
    
    # Adjust amount if non-matching
    net_proceeds = source_data.get('amount', 0)
    if not matching:
        net_proceeds = net_proceeds * 0.9625  # Reduce for amount mismatch scenario
    
    # Include or exclude solicitor based on matching flag
    solicitor_info = ""
    if matching and source_data.get('solicitor'):
        solicitor_info = f"<b>Solicitor Acting:</b> {source_data.get('solicitor')}<br/>"
    
    content = f"""
    <b>Property Address:</b> {source_data.get('property_address', 'N/A')}<br/>
    <b>Title Number:</b> {source_data.get('title_number', 'N/A')}<br/>
    <b>Vendor:</b> [Vendor Name]<br/>
    <b>Completion Date:</b> {source_data.get('completion_date', 'N/A')}<br/>
    {solicitor_info}
    <br/>
    <b>FINANCIAL SUMMARY</b><br/>
    <br/>
    Sale Price: £{source_data.get('amount', 0):,.2f}<br/>
    Less: Estate Agent Fees: £{source_data.get('amount', 0) * 0.015:,.2f}<br/>
    Less: Legal Fees: £{1500.00:,.2f}<br/>
    Less: Other Costs: £{200.00:,.2f}<br/>
    <br/>
    <b>Net Proceeds to Vendor: £{net_proceeds:,.2f}</b><br/>
    <br/>
    <b>PAYMENT DETAILS</b><br/>
    Amount Paid: £{net_proceeds:,.2f}<br/>
    Bank: HSBC Bank PLC<br/>
    Account Number: ****5678<br/>
    Transfer Date: {source_data.get('completion_date', 'N/A')}<br/>
    Reference: Property Sale - {source_data.get('title_number', 'REF')}<br/>
    """
    
    story.append(Paragraph(content, styles['Normal']))
    
    doc.build(story)
    print(f"✓ Created {output_path}")


def create_business_sale_agreement_pdf(scenario_id, source_data, matching=True):
    """Create business sale agreement PDF"""
    
    safe_company = source_data.get('company_name', 'Company').replace(' ', '_')[:30]
    filename = f"{scenario_id}/business_sale_{safe_company}.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    story.append(Paragraph("BUSINESS SALE AGREEMENT", title_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Adjust completion date if non-matching (for date discrepancy test)
    completion_date = source_data.get('completion_date', '2023-09-30')
    if not matching:
        date_obj = datetime.strptime(completion_date, '%Y-%m-%d')
        date_obj = date_obj + timedelta(days=30)  # Add 1 month
        completion_date = date_obj.strftime('%Y-%m-%d')
    
    # Include or exclude solicitor based on matching flag
    solicitor_info = ""
    if matching and source_data.get('solicitor'):
        solicitor_info = f"<b>Legal Representatives:</b> {source_data.get('solicitor')}<br/>"
    
    content = f"""
    <b>Company Name:</b> {source_data.get('company_name', 'N/A')}<br/>
    <b>Company Number:</b> {source_data.get('company_number', 'N/A')}<br/>
    <b>Sale Date:</b> {completion_date}<br/>
    <b>Vendor:</b> [Current Owner]<br/>
    <b>Purchaser:</b> [Client Name]<br/>
    {solicitor_info}
    <br/>
    <b>SALE CONSIDERATION</b><br/>
    <br/>
    Total Purchase Price: £{source_data.get('amount', 0):,.2f}<br/>
    Payment Method: Bank Transfer<br/>
    <br/>
    <b>PAYMENT DETAILS</b><br/>
    Amount: £{source_data.get('amount', 0):,.2f}<br/>
    Payment Date: {completion_date}<br/>
    Bank Account: ****5678<br/>
    Reference: {source_data.get('company_name', 'Company')} Acquisition<br/>
    <br/>
    This agreement confirms the sale and purchase of the above company for the consideration stated.
    """
    
    story.append(Paragraph(content, styles['Normal']))
    
    doc.build(story)
    print(f"✓ Created {output_path}")


def create_loan_agreement_pdf(scenario_id, source_data):
    """Create loan agreement PDF"""
    
    filename = f"{scenario_id}/loan_agreement_{source_data.get('lender', 'Lender').replace(' ', '_')}.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    story.append(Paragraph("BUSINESS LOAN AGREEMENT", title_style))
    story.append(Spacer(1, 0.3*inch))
    
    content = f"""
    <b>Lender:</b> {source_data.get('lender', 'N/A')}<br/>
    <b>Borrower:</b> [Client Name]<br/>
    <b>Loan Date:</b> {source_data.get('loan_date', 'N/A')}<br/>
    <b>Account Number:</b> {source_data.get('account_number', 'N/A')}<br/>
    <br/>
    <b>LOAN DETAILS</b><br/>
    <br/>
    Loan Amount: £{source_data.get('amount', 0):,.2f}<br/>
    Interest Rate: 4.5% per annum<br/>
    Term: 10 years<br/>
    Purpose: Business expansion / acquisition<br/>
    <br/>
    <b>DISBURSEMENT</b><br/>
    Disbursement Date: {source_data.get('loan_date', 'N/A')}<br/>
    Account Credited: {source_data.get('account_number', 'N/A')}<br/>
    Amount: £{source_data.get('amount', 0):,.2f}<br/>
    <br/>
    This agreement confirms the terms of the business loan facility.
    """
    
    story.append(Paragraph(content, styles['Normal']))
    
    doc.build(story)
    print(f"✓ Created {output_path}")


def create_gift_letter_pdf(scenario_id, source_data):
    """Create gift letter PDF"""
    
    filename = f"{scenario_id}/gift_letter.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    story.append(Paragraph("GIFT LETTER", title_style))
    story.append(Spacer(1, 0.3*inch))
    
    content = f"""
    Date: {source_data.get('gift_date', 'N/A')}<br/>
    <br/>
    <b>From:</b> {source_data.get('donor_name', 'N/A')}<br/>
    <b>To:</b> [Client Name]<br/>
    <br/>
    We, {source_data.get('donor_name', 'N/A')}, hereby confirm that we are making a gift of:<br/>
    <br/>
    <b>Amount: £{source_data.get('amount', 0):,.2f}</b><br/>
    <br/>
    This is an unconditional gift and we have no expectation of repayment. The funds are given freely and without any legal obligation to repay.<br/>
    <br/>
    <b>PAYMENT DETAILS</b><br/>
    Date of Transfer: {source_data.get('gift_date', 'N/A')}<br/>
    Bank Account: ****5678<br/>
    Amount: £{source_data.get('amount', 0):,.2f}<br/>
    <br/>
    <b>SOURCE OF FUNDS</b><br/>
    The funds gifted originate from our personal savings accumulated over many years from salary and pension income.<br/>
    <br/>
    Signed: ________________________<br/>
    {source_data.get('donor_name', 'N/A')}<br/>
    Date: {source_data.get('gift_date', 'N/A')}
    """
    
    story.append(Paragraph(content, styles['Normal']))
    
    doc.build(story)
    print(f"✓ Created {output_path}")


def create_credit_card_statement_pdf(scenario_id):
    """Create credit card statement (wrong document type)"""
    
    filename = f"{scenario_id}/credit_card_statement.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)
    
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    story.append(Paragraph("CREDIT CARD STATEMENT", title_style))
    story.append(Paragraph("This is NOT a bank statement", ParagraphStyle('Warning', parent=styles['Normal'], textColor=colors.red, alignment=TA_CENTER, spaceAfter=20)))
    story.append(Spacer(1, 0.3*inch))
    
    content = """
    <b>Card Number:</b> **** **** **** 1234<br/>
    <b>Statement Period:</b> 01/10/2023 - 31/10/2023<br/>
    <br/>
    <b>TRANSACTIONS</b><br/>
    <br/>
    05/10/2023 - Amazon.co.uk - £45.99<br/>
    12/10/2023 - Sainsbury's - £87.50<br/>
    18/10/2023 - Shell Petrol - £65.00<br/>
    25/10/2023 - Restaurant - £120.00<br/>
    <br/>
    <b>Total Owed: £318.49</b><br/>
    <br/>
    <i>This is a credit card statement and does not show savings or bank account balances.</i>
    """
    
    story.append(Paragraph(content, styles['Normal']))
    
    doc.build(story)
    print(f"✓ Created {output_path}")


def main():
    """Generate all test files"""
    
    print("\n" + "="*80)
    print("GENERATING COMPREHENSIVE TEST SUITE")
    print("="*80 + "\n")
    
    for scenario_id, scenario_data in TEST_SCENARIOS.items():
        print(f"\n--- {scenario_data['name']} ---")
        
        # Create client info
        create_client_info(scenario_id, scenario_data)
        
        # Create matching and non-matching bank statements
        create_pdf_bank_statement(scenario_id, scenario_data, matching=True)
        create_pdf_bank_statement(scenario_id, scenario_data, matching=False)
        
        # Create supporting documents
        for source in scenario_data['sources']:
            if source['type'] == 'inheritance':
                create_probate_grant_pdf(scenario_id, source, matching=True)
                if scenario_id == 'scenario_4_date_discrepancy':
                    create_probate_grant_pdf(scenario_id, source, matching=False)
                    
            elif source['type'] == 'property_sale':
                if scenario_id == 'scenario_2_missing_solicitor':
                    # Create without solicitor (non-matching)
                    create_completion_statement_pdf(scenario_id, source, matching=False)
                elif scenario_id == 'scenario_3_amount_mismatch':
                    # Create with amount mismatch
                    create_completion_statement_pdf(scenario_id, source, matching=False)
                else:
                    create_completion_statement_pdf(scenario_id, source, matching=True)
                    
            elif source['type'] == 'business_sale':
                if scenario_id == 'scenario_2_missing_solicitor':
                    create_business_sale_agreement_pdf(scenario_id, source, matching=False)
                elif scenario_id == 'scenario_4_date_discrepancy':
                    create_business_sale_agreement_pdf(scenario_id, source, matching=False)
                else:
                    create_business_sale_agreement_pdf(scenario_id, source, matching=True)
                    
            elif source['type'] == 'business_loan':
                create_loan_agreement_pdf(scenario_id, source)
                
            elif source['type'] == 'gift':
                create_gift_letter_pdf(scenario_id, source)
                
            elif source['type'] == 'savings':
                if scenario_id == 'scenario_5_wrong_documents':
                    # Provide credit card statement instead (wrong doc type)
                    create_credit_card_statement_pdf(scenario_id)
    
    print("\n" + "="*80)
    print("TEST SUITE GENERATION COMPLETE")
    print("="*80 + "\n")
    
    # Create README
    create_readme()


def create_readme():
    """Create comprehensive README for test suite"""
    
    readme_content = """# Comprehensive SoF Assessment Test Suite

## Overview

This test suite contains 5 complete test scenarios with realistic PDF documents to test all aspects of the SoF Assessment system.

## Test Scenarios

### Scenario 1: Perfect Match ✅
- **Client**: Residential Property Ltd
- **Sources**: Inheritance (£250k) + Property Sale (£200k)
- **Expected Result**: Both claims FULLY VERIFIED (100% confidence)
- **Files**:
  - `client_info.json`
  - `bank_statement_matching.pdf` ✓
  - `probate_grant_2023_8765.pdf` ✓
  - `completion_statement_*.pdf` ✓

### Scenario 2: Missing Solicitor ⚠️
- **Client**: Commercial Ventures PLC
- **Sources**: Business Sale (£500k) + Business Loan (£250k)
- **Expected Result**: 
  - Business Sale: REQUIRES REVIEW (~83% confidence) - Missing solicitor field
  - Business Loan: FULLY VERIFIED (100%)
- **Files**:
  - `client_info.json`
  - `bank_statement_matching.pdf` ✓
  - `business_sale_*.pdf` (missing solicitor) ⚠️
  - `loan_agreement_*.pdf` ✓

### Scenario 3: Amount Mismatch ❌
- **Client**: Property Investors Group
- **Sources**: Property Sale (£400k claimed) + Savings (£220k claimed)
- **Expected Result**:
  - Property Sale: REQUIRES REVIEW - Document shows £385k (£15k difference)
  - Savings: REQUIRES REVIEW - Statements show £215k (£5k difference)
- **Files**:
  - `client_info.json`
  - `bank_statement_non_matching.pdf` (lower amounts) ❌
  - `completion_statement_*.pdf` (shows £385k) ❌

### Scenario 4: Date Discrepancy ⚠️
- **Client**: Tech Acquisitions Ltd
- **Sources**: Inheritance (£350k) + Business Sale (£540k)
- **Expected Result**:
  - Inheritance: REQUIRES REVIEW - Distribution date differs by 2 months
  - Business Sale: REQUIRES REVIEW - Completion date differs by 1 month
- **Files**:
  - `client_info.json`
  - `bank_statement_non_matching.pdf` (dates don't match) ⚠️
  - `probate_grant_*.pdf` (August vs June) ⚠️
  - `business_sale_*.pdf` (October vs September) ⚠️

### Scenario 5: Wrong Document Type ❌
- **Client**: Startup Ventures Ltd
- **Sources**: Gift (£100k) + Savings (£220k)
- **Expected Result**:
  - Gift: FULLY VERIFIED (100%)
  - Savings: REQUIRES REVIEW - Credit card statement provided instead of bank statement
- **Files**:
  - `client_info.json`
  - `bank_statement_matching.pdf` ✓
  - `gift_letter.pdf` ✓
  - `credit_card_statement.pdf` (wrong document type) ❌

## Running Tests

### Quick Test All Scenarios

```bash
cd /home/user/webapp/test_data/comprehensive_test
python run_all_tests.py
```

### Test Individual Scenario

```bash
# Example: Test Scenario 1
cd scenario_1_perfect_match

# 1. Reset assessment
curl -X DELETE http://localhost:8001/api/v1/matters/1/sof-assessment/reset

# 2. Upload client info
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \\
  -F "file=@client_info.json" \\
  -F "file_category=client_info"

# 3. Upload bank statement
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \\
  -F "file=@bank_statement_matching.pdf" \\
  -F "file_category=bank_statement"

# 4. Upload supporting documents
for doc in *.pdf; do
  if [[ $doc != bank_statement* ]]; then
    curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \\
      -F "file=@$doc" \\
      -F "file_category=supporting_doc"
  fi
done

# 5. Run assessment
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/run

# 6. View results
curl http://localhost:8001/api/v1/matters/1/sof-assessment/results
```

## Expected Outcomes Summary

| Scenario | Claim 1 | Claim 2 | Overall |
|----------|---------|---------|---------|
| 1 - Perfect Match | ✅ 100% | ✅ 100% | All verified |
| 2 - Missing Solicitor | ⚠️ ~83% | ✅ 100% | Requires review |
| 3 - Amount Mismatch | ❌ Amount diff | ❌ Amount diff | Requires review |
| 4 - Date Discrepancy | ⚠️ Date diff | ⚠️ Date diff | Requires review |
| 5 - Wrong Docs | ✅ 100% | ❌ Wrong type | Requires review |

## Manual Acceptance Testing

For scenarios requiring review, test the manual acceptance workflow:

```bash
# Accept differences for a claim
curl -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/accept-differences \\
  -H "Content-Type: application/json" \\
  -d '{
    "claim_index": 0,
    "accepted_by": "Test User",
    "reason": "Verified through alternative means"
  }'
```

## What to Test

1. **PDF Extraction**: Verify system can extract data from all PDF files
2. **Transaction Matching**: Confirm bank transactions are correctly matched to claims
3. **Confidence Scoring**: Validate confidence percentages match expected values
4. **Difference Detection**: Check specific differences are identified (field, amount, date)
5. **Review Badges**: Verify REQUIRES REVIEW badges appear correctly
6. **Manual Acceptance**: Test acceptance workflow and audit trail
7. **UI Display**: Confirm all data displays correctly in frontend

## File Structure

```
comprehensive_test/
├── scenario_1_perfect_match/
│   ├── client_info.json
│   ├── bank_statement_matching.pdf
│   ├── probate_grant_2023_8765.pdf
│   └── completion_statement_*.pdf
├── scenario_2_missing_solicitor/
│   ├── client_info.json
│   ├── bank_statement_matching.pdf
│   ├── business_sale_*.pdf
│   └── loan_agreement_*.pdf
├── scenario_3_amount_mismatch/
│   ├── client_info.json
│   ├── bank_statement_non_matching.pdf
│   └── completion_statement_*.pdf
├── scenario_4_date_discrepancy/
│   ├── client_info.json
│   ├── bank_statement_non_matching.pdf
│   ├── probate_grant_*.pdf
│   └── business_sale_*.pdf
└── scenario_5_wrong_documents/
    ├── client_info.json
    ├── bank_statement_matching.pdf
    ├── gift_letter.pdf
    └── credit_card_statement.pdf
```

## Notes

- All bank statements are PDF files that must be parsed by the system
- Transaction review data comes exclusively from uploaded PDF bank statements
- Supporting documents have intentional discrepancies to test verification logic
- Test both the automated verification and manual acceptance workflows
"""
    
    readme_path = os.path.join(OUTPUT_DIR, "README.md")
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    print(f"✓ Created {readme_path}")


if __name__ == "__main__":
    main()
