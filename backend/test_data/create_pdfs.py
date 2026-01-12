#!/usr/bin/env python3
"""
Convert text documents to professional PDF format
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
import os

def create_inheritance_pdf():
    """Create professional PDF for Inheritance Proof (Probate Grant)"""
    
    # Create PDF
    pdf_path = '/home/user/webapp/backend/test_data/inheritance_proof_probate_grant.pdf'
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=72)
    
    # Container for content
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor='black',
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor='black',
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        textColor='black',
        spaceAfter=6,
        alignment=TA_LEFT,
        fontName='Helvetica'
    )
    
    centered_style = ParagraphStyle(
        'Centered',
        parent=body_style,
        alignment=TA_CENTER
    )
    
    # Document content
    story.append(Paragraph("GRANT OF PROBATE", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("In the High Court of Justice", centered_style))
    story.append(Paragraph("Family Division", centered_style))
    story.append(Paragraph("Principal Registry of the Family Division", centered_style))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("<b>Estate of:</b> MARGARET ELIZABETH SMITH (Deceased)", body_style))
    story.append(Paragraph("<b>Date of Death:</b> 15th January 2023", body_style))
    story.append(Paragraph("<b>Last Address:</b> 42 Oakwood Avenue, Manchester, M20 4QT", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("GRANT OF PROBATE", header_style))
    
    grant_text = """BE IT KNOWN that MARGARET ELIZABETH SMITH of 42 Oakwood Avenue, Manchester, M20 4QT died on 15th January 2023.<br/><br/>
    AND BE IT KNOWN that at the date of her death she had her fixed place of abode in England and Wales.<br/><br/>
    AND BE IT KNOWN that the last Will and Testament of the said deceased (a copy of which is annexed hereto) is proved and registered in the Principal Registry of the Family Division.<br/><br/>
    AND BE IT KNOWN that Administration of all the estate which by law devolves to and vests in the personal representative of the said deceased was granted by the said Court on 10th April 2023."""
    
    story.append(Paragraph(grant_text, body_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("<b>TO:</b> John David Smith<br/>123 Richmond Road<br/>London<br/>SW15 2TN", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("<b>Power is reserved to:</b> None", body_style))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("<b>The Gross Estate passing under the grant amounts to:</b> £625,000.00", body_style))
    story.append(Paragraph("<b>The Net Estate amounts to:</b> £580,000.00", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("<b>Signed:</b> [Court Seal]", body_style))
    story.append(Paragraph("<b>Date:</b> 10th April 2023", body_style))
    story.append(Paragraph("<b>Probate Registry Reference:</b> 2023/4521", body_style))
    
    story.append(PageBreak())
    
    # Schedule of Assets
    story.append(Paragraph("SCHEDULE OF ASSETS", header_style))
    story.append(Spacer(1, 0.1*inch))
    
    assets = [
        ("<b>Property:</b>", ""),
        ("42 Oakwood Avenue, Manchester, M20 4QT", "£320,000.00"),
        ("", ""),
        ("<b>Bank Accounts:</b>", ""),
        ("Barclays Bank - Current Account ****1234", "£85,000.00"),
        ("HSBC - Savings Account ****5678", "£120,000.00"),
        ("", ""),
        ("<b>Investments:</b>", ""),
        ("Portfolio - Smith &amp; Partners Financial", "£75,000.00"),
        ("", ""),
        ("<b>Life Insurance:</b>", ""),
        ("Aviva Life Insurance Policy", "£20,000.00"),
        ("", ""),
        ("<b>Personal Effects and Chattels:</b>", "£5,000.00"),
        ("", ""),
        ("<b>TOTAL GROSS ESTATE:</b>", "<b>£625,000.00</b>"),
    ]
    
    for item, value in assets:
        if item or value:
            line = f"{item}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{value}" if value else item
            story.append(Paragraph(line, body_style))
    
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("<b>LESS: Liabilities</b>", body_style))
    liabilities = [
        ("Funeral Expenses", "£4,500.00"),
        ("Legal Fees", "£3,200.00"),
        ("Outstanding Bills", "£2,300.00"),
        ("Inheritance Tax (Nil Rate Band Applied)", "£35,000.00"),
        ("", ""),
        ("<b>TOTAL LIABILITIES:</b>", "<b>£45,000.00</b>"),
        ("", ""),
        ("<b>NET ESTATE:</b>", "<b>£580,000.00</b>"),
    ]
    
    for item, value in liabilities:
        if item or value:
            line = f"{item}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{value}" if value else item
            story.append(Paragraph(line, body_style))
    
    story.append(PageBreak())
    
    # Beneficiaries
    story.append(Paragraph("BENEFICIARIES AND DISTRIBUTION", header_style))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("<b>Primary Beneficiary:</b>", body_style))
    story.append(Paragraph("John David Smith (Son) - £250,000.00", body_style))
    story.append(Paragraph("Payment Date: 15th May 2023", body_style))
    story.append(Paragraph("Payment Method: Bank Transfer to Barclays ****1234", body_style))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("<b>Secondary Beneficiaries:</b>", body_style))
    story.append(Paragraph("Sarah Jane Thompson (Daughter) - £250,000.00", body_style))
    story.append(Paragraph("Emily Rose Smith (Granddaughter) - £80,000.00", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Executor's Statement
    story.append(Paragraph("EXECUTOR'S STATEMENT", header_style))
    story.append(Spacer(1, 0.1*inch))
    
    executor_text = """I, John David Smith, being the Executor named in the Will of Margaret Elizabeth Smith, hereby certify that:<br/><br/>
    1. The estate has been distributed in accordance with the terms of the Will<br/>
    2. All debts and liabilities have been settled<br/>
    3. Inheritance Tax has been paid where applicable<br/>
    4. All beneficiaries have received their entitlements"""
    
    story.append(Paragraph(executor_text, body_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("<b>Distribution to primary beneficiary (myself) of £250,000.00 was transferred to:</b>", body_style))
    story.append(Paragraph("Account Name: John David Smith", body_style))
    story.append(Paragraph("Bank: Barclays Bank PLC", body_style))
    story.append(Paragraph("Account Number: ****1234", body_style))
    story.append(Paragraph("Sort Code: 20-XX-XX", body_style))
    story.append(Paragraph("Date of Transfer: 15th May 2023", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Executor Signature: _______________________", body_style))
    story.append(Paragraph("Date: 15th May 2023", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("<b>Witnessed by:</b>", body_style))
    story.append(Paragraph("Smith &amp; Partners Solicitors", body_style))
    story.append(Paragraph("42 High Street, Manchester, M1 2ND", body_style))
    story.append(Paragraph("Solicitor Reference: SPS/2023/1247", body_style))
    story.append(Paragraph("Contact: James Wilson, Senior Partner", body_style))
    story.append(Paragraph("Tel: 0161 234 5678", body_style))
    story.append(Paragraph("Email: jwilson@smithpartners.co.uk", body_style))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph("OFFICE USE ONLY", centered_style))
    story.append(Paragraph("Probate Registry Seal: [SEAL]", centered_style))
    story.append(Paragraph("Registry Reference: 2023/4521", centered_style))
    story.append(Paragraph("Issued: 10th April 2023", centered_style))
    story.append(Paragraph("Extracted: 12th April 2023", centered_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("<i>This is a true copy of the Grant of Probate issued by the High Court of Justice.</i>", centered_style))
    
    # Build PDF
    doc.build(story)
    print(f"✓ Created: {pdf_path}")
    return pdf_path


def create_property_pdf():
    """Create professional PDF for Property Completion Statement"""
    
    pdf_path = '/home/user/webapp/backend/test_data/property_completion_statement.pdf'
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=72)
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor='black',
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=13,
        textColor='black',
        spaceAfter=10,
        spaceBefore=10,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        textColor='black',
        spaceAfter=4,
        alignment=TA_LEFT,
        fontName='Helvetica'
    )
    
    small_style = ParagraphStyle(
        'Small',
        parent=body_style,
        fontSize=9
    )
    
    # Header
    story.append(Paragraph("COMPLETION STATEMENT", title_style))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("<b>Taylor &amp; Brown Solicitors</b>", body_style))
    story.append(Paragraph("12 Market Square, London, EC1A 4NP", small_style))
    story.append(Paragraph("Tel: 020 7123 4567 | Email: completions@taylorbrown.co.uk", small_style))
    story.append(Paragraph("Reference: TB/2023/7821", small_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("<b>Date:</b> 1st July 2023", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("PROPERTY SALE COMPLETION STATEMENT", header_style))
    
    story.append(Paragraph("<b>VENDOR:</b> John David Smith", body_style))
    story.append(Paragraph("<b>PROPERTY:</b> 45 Oak Street, London, SW18 3QR", body_style))
    story.append(Paragraph("<b>TITLE NUMBER:</b> TGL123456", body_style))
    story.append(Paragraph("<b>PURCHASER:</b> Williams Property Investment Ltd", body_style))
    story.append(Paragraph("<b>COMPLETION DATE:</b> 1st July 2023", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Contract Details
    story.append(Paragraph("CONTRACT DETAILS", header_style))
    story.append(Paragraph("Contract Date: 15th June 2023", body_style))
    story.append(Paragraph("Contract Price: <b>£450,000.00</b>", body_style))
    story.append(Paragraph("Deposit Paid (10%): £45,000.00", body_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;Paid to: Taylor &amp; Brown Solicitors Client Account", small_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;Date Received: 15th June 2023", small_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Financial Statement
    story.append(Paragraph("FINANCIAL STATEMENT", header_style))
    story.append(Paragraph("<b>SALE PROCEEDS</b>", body_style))
    
    financial_lines = [
        ("Contract Price:", "£450,000.00"),
        ("Less: Deposit Already Received:", "(£45,000.00)"),
        ("", "____________"),
        ("<b>Balance Due on Completion:</b>", "<b>£405,000.00</b>"),
    ]
    
    for label, amount in financial_lines:
        if label or amount:
            story.append(Paragraph(f"{label} {amount}", body_style))
    
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("<b>RECEIVED ON COMPLETION (1st July 2023):</b>", body_style))
    story.append(Paragraph("Bank Transfer from: Williams Property Investment Ltd", small_style))
    story.append(Paragraph("Via: Stevenson &amp; Co Solicitors", small_style))
    story.append(Paragraph("Amount Received: <b>£405,000.00</b>", small_style))
    story.append(Paragraph("Reference: PROP-45-OAK-STREET", small_style))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("<b>TOTAL SALE PROCEEDS: £450,000.00</b>", body_style))
    
    story.append(PageBreak())
    
    # Deductions
    story.append(Paragraph("DEDUCTIONS FROM SALE PROCEEDS", header_style))
    
    deductions = [
        ("<b>Estate Agent Fees:</b>", ""),
        ("Prime Properties London - Commission (1.5% + VAT)", "£8,100.00"),
        ("", ""),
        ("<b>Legal Fees:</b>", ""),
        ("Professional Fees", "£1,800.00"),
        ("VAT (20%)", "£360.00"),
        ("Disbursements", "£450.00"),
        ("Land Registry Fees", "£295.00"),
        ("Search Fees", "£180.00"),
        ("Bank Transfer Fees", "£35.00"),
        ("<i>Total Legal Costs:</i>", "<i>£3,120.00</i>"),
        ("", ""),
        ("<b>Outstanding Mortgage:</b>", ""),
        ("Halifax Bank PLC Account ****8642", ""),
        ("Capital Outstanding", "£138,037.00"),
        ("Interest to Completion", "£342.18"),
        ("<i>Total Mortgage Redemption:</i>", "<i>£138,379.18</i>"),
        ("", ""),
        ("<b>Utilities and Other:</b>", ""),
        ("Service Charges", "£420.00"),
        ("Final Utility Bills", "£11.00"),
        ("Royal Mail Redirection", "£52.00"),
        ("", ""),
        ("<b>TOTAL DEDUCTIONS:</b>", "<b>£149,999.18</b>"),
    ]
    
    for label, amount in deductions:
        if label or amount:
            line = f"{label} {amount}" if amount else label
            story.append(Paragraph(line, body_style))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Net Proceeds
    story.append(Paragraph("NET PROCEEDS CALCULATION", header_style))
    
    net_calc = [
        ("Total Sale Proceeds:", "£450,000.00"),
        ("Less: Total Deductions:", "(£149,999.18)"),
        ("", "____________"),
        ("<b>NET PROCEEDS TO VENDOR:</b>", "<b>£300,000.82</b>"),
    ]
    
    for label, amount in net_calc:
        if label or amount:
            story.append(Paragraph(f"{label} {amount}", body_style))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Payment to Vendor
    story.append(Paragraph("PAYMENT TO VENDOR", header_style))
    
    story.append(Paragraph("<b>Vendor Bank Details:</b>", body_style))
    story.append(Paragraph("Account Name: John David Smith", body_style))
    story.append(Paragraph("Bank: HSBC Bank PLC", body_style))
    story.append(Paragraph("Account Number: ****5678", body_style))
    story.append(Paragraph("Sort Code: 40-XX-XX", body_style))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("<b>Payment Details:</b>", body_style))
    story.append(Paragraph("Amount Transferred: <b>£300,000.82</b>", body_style))
    story.append(Paragraph("Transfer Date: 1st July 2023", body_style))
    story.append(Paragraph("Transfer Time: 16:15 BST", body_style))
    story.append(Paragraph("Transfer Reference: 45-OAK-ST-SALE-PROCEEDS", body_style))
    story.append(Paragraph("Payment Method: CHAPS", body_style))
    story.append(Spacer(1, 0.1*inch))
    
    story.append(Paragraph("<b>CONFIRMATION:</b> Payment of £300,000.82 has been successfully transferred to the vendor's account.", body_style))
    
    story.append(PageBreak())
    
    # Solicitor's Certification
    story.append(Paragraph("SOLICITOR'S CERTIFICATION", header_style))
    
    cert_text = """I hereby certify that:<br/><br/>
    • The sale of 45 Oak Street, London, SW18 3QR has been completed in accordance with the contract dated 15th June 2023<br/>
    • All monies have been received and properly accounted for<br/>
    • The net proceeds of £300,000.82 have been transferred to the vendor as instructed<br/>
    • All legal requirements have been satisfied<br/>
    • The property has been legally transferred to the purchaser"""
    
    story.append(Paragraph(cert_text, body_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("Signed: _______________________", body_style))
    story.append(Paragraph("Amanda Brown, Senior Partner", body_style))
    story.append(Paragraph("Taylor &amp; Brown Solicitors", body_style))
    story.append(Paragraph("Date: 1st July 2023", body_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Contact Info
    story.append(Paragraph("CONTACT INFORMATION", header_style))
    story.append(Paragraph("For any queries regarding this completion statement, please contact:", body_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("Amanda Brown, Senior Partner", body_style))
    story.append(Paragraph("Taylor &amp; Brown Solicitors", body_style))
    story.append(Paragraph("12 Market Square, London, EC1A 4NP", body_style))
    story.append(Paragraph("Direct Line: 020 7123 4571", body_style))
    story.append(Paragraph("Email: abrown@taylorbrown.co.uk", body_style))
    story.append(Paragraph("Reference: TB/2023/7821", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph("<i>This completion statement has been prepared in accordance with the Solicitors Regulation Authority requirements and the Law Society's Conveyancing Protocol.</i>", small_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("<i>Taylor &amp; Brown Solicitors is a partnership regulated by the Solicitors Regulation Authority. SRA Number: 123456</i>", small_style))
    
    # Build PDF
    doc.build(story)
    print(f"✓ Created: {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    print("Creating professional PDF documents...")
    print()
    
    inheritance_pdf = create_inheritance_pdf()
    property_pdf = create_property_pdf()
    
    print()
    print("✓ PDF documents created successfully!")
    print()
    print("Download links:")
    print(f"Inheritance Proof: https://8080-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/backend/test_data/inheritance_proof_probate_grant.pdf")
    print(f"Property Statement: https://8080-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/backend/test_data/property_completion_statement.pdf")
