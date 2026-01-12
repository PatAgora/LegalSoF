"""
PDF Document Data Extractor
Extracts structured data from supporting documents (probate grants, completion statements, etc.)
"""
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import pdfplumber


class PDFDocumentExtractor:
    """
    Extract structured data from PDF supporting documents
    """
    
    def extract_document_data(self, pdf_content: bytes, doc_type: str) -> Dict[str, Any]:
        """
        Extract structured data based on document type
        
        Returns:
            {
                "document_type": str,
                "extracted_data": {...},  # Structured data specific to doc type
                "raw_text": str,
                "confidence": float  # 0-1
            }
        """
        # Extract full text
        full_text = self._extract_text(pdf_content)
        
        # Extract data based on document type
        if doc_type == 'Probate grant':
            extracted_data = self._extract_probate_data(full_text)
        elif doc_type == 'completion statement':
            extracted_data = self._extract_property_completion_data(full_text)
        elif doc_type == 'Loan':
            extracted_data = self._extract_loan_data(full_text)
        elif doc_type == "Solicitor's statement":
            extracted_data = self._extract_solicitor_statement_data(full_text)
        else:
            extracted_data = {}
        
        # Calculate confidence score
        confidence = self._calculate_confidence(extracted_data)
        
        return {
            "document_type": doc_type,
            "extracted_data": extracted_data,
            "raw_text": full_text[:2000],  # First 2000 chars for reference
            "confidence": confidence
        }
    
    def _extract_text(self, pdf_content: bytes) -> str:
        """Extract all text from PDF"""
        try:
            import io
            full_text = []
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
            return "\n".join(full_text)
        except Exception as e:
            print(f"PDF text extraction error: {str(e)}")
            return ""
    
    def _extract_probate_data(self, text: str) -> Dict[str, Any]:
        """
        Extract data from Probate Grant / Letters of Administration
        
        Key fields:
        - Deceased name
        - Date of death
        - Executor/Beneficiary name
        - Grant date
        - Estate value (gross/net)
        - Distribution amounts
        - Payment dates
        - Bank account details
        """
        data = {}
        
        # Deceased name
        deceased_match = re.search(r'Estate of[:\s]+([A-Z\s]+)\s*\(Deceased\)', text, re.IGNORECASE)
        if deceased_match:
            data['deceased_name'] = deceased_match.group(1).strip()
        
        # Date of death
        death_date_patterns = [
            r'Date of Death[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
            r'died on[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        ]
        for pattern in death_date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['date_of_death'] = match.group(1).strip()
                break
        
        # Executor/Beneficiary
        executor_patterns = [
            r'TO[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'(?:Executor|Beneficiary)[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        ]
        for pattern in executor_patterns:
            match = re.search(pattern, text)
            if match:
                data['executor_beneficiary'] = match.group(1).strip()
                break
        
        # Grant date
        grant_date_patterns = [
            r'granted.*?on[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
            r'Grant.*?Date[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        ]
        for pattern in grant_date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['grant_date'] = match.group(1).strip()
                break
        
        # Gross Estate
        gross_patterns = [
            r'Gross Estate[:\s]+£?([0-9,]+(?:\.\d{2})?)',
            r'TOTAL GROSS ESTATE[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        ]
        for pattern in gross_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['gross_estate'] = self._parse_amount(match.group(1))
                break
        
        # Net Estate
        net_patterns = [
            r'Net Estate[:\s]+£?([0-9,]+(?:\.\d{2})?)',
            r'NET ESTATE[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        ]
        for pattern in net_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['net_estate'] = self._parse_amount(match.group(1))
                break
        
        # Distribution amounts - look for beneficiary distributions
        # Pattern 1: Name and amount on same line (e.g., "Primary Beneficiary: John Smith - £250,000")
        distribution_pattern1 = r'(?:Primary Beneficiary|Beneficiary)[:\s]*([A-Z][a-z\s]+)\s*[:-]\s*£?([0-9,]+(?:\.\d{2})?)'
        # Pattern 2: Name and amount on separate lines (e.g., "Primary Beneficiary:\nJohn Smith (Son) - £250,000")
        distribution_pattern2 = r'(?:Primary Beneficiary|Beneficiary):\s*\n([A-Z][a-z\s]+(?:\([^)]+\))?)\s*-\s*£?([0-9,]+(?:\.\d{2})?)'
        
        distributions = []
        
        # Try pattern 1
        for match in re.finditer(distribution_pattern1, text, re.IGNORECASE):
            distributions.append({
                'beneficiary': match.group(1).strip(),
                'amount': self._parse_amount(match.group(2))
            })
        
        # Try pattern 2
        for match in re.finditer(distribution_pattern2, text, re.IGNORECASE):
            distributions.append({
                'beneficiary': match.group(1).strip(),
                'amount': self._parse_amount(match.group(2))
            })
        
        if distributions:
            data['distributions'] = distributions
        
        # Payment date
        payment_date_patterns = [
            r'Payment Date[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
            r'Date of Transfer[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
            r'transferred.*?on[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        ]
        for pattern in payment_date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['payment_date'] = match.group(1).strip()
                break
        
        # Bank details
        bank_match = re.search(r'Bank[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text)
        if bank_match:
            data['bank_name'] = bank_match.group(1).strip()
        
        # Account number (last 4 digits)
        account_match = re.search(r'\*+(\d{4})', text)
        if account_match:
            data['account_last_4'] = account_match.group(1)
        
        # Probate reference
        ref_match = re.search(r'(?:Probate.*?Reference|Registry Reference)[:\s]+(\d{4}/\d+)', text, re.IGNORECASE)
        if ref_match:
            data['probate_reference'] = ref_match.group(1)
        
        return data
    
    def _extract_property_completion_data(self, text: str) -> Dict[str, Any]:
        """
        Extract data from Property Completion Statement
        
        Key fields:
        - Vendor name
        - Property address
        - Completion date
        - Contract price
        - Net proceeds
        - Payment details (bank, account, date)
        """
        data = {}
        
        # Vendor name
        vendor_patterns = [
            r'VENDOR[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'Vendor[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        ]
        for pattern in vendor_patterns:
            match = re.search(pattern, text)
            if match:
                data['vendor_name'] = match.group(1).strip()
                break
        
        # Property address
        property_patterns = [
            r'PROPERTY[:\s]+([0-9]+\s+[A-Za-z\s]+,\s*[A-Za-z\s]+,\s*[A-Z0-9\s]+)',
            r'Property[:\s]+([0-9]+\s+[A-Za-z\s]+,\s*[A-Za-z\s]+,\s*[A-Z0-9\s]+)',
        ]
        for pattern in property_patterns:
            match = re.search(pattern, text)
            if match:
                data['property_address'] = match.group(1).strip()
                break
        
        # Completion date
        completion_patterns = [
            r'COMPLETION DATE[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
            r'Completion Date[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        ]
        for pattern in completion_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['completion_date'] = match.group(1).strip()
                break
        
        # Contract price
        contract_patterns = [
            r'Contract Price[:\s]+£?([0-9,]+(?:\.\d{2})?)',
            r'CONTRACT PRICE[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        ]
        for pattern in contract_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['contract_price'] = self._parse_amount(match.group(1))
                break
        
        # Net proceeds
        net_proceeds_patterns = [
            r'NET PROCEEDS[:\s]+£?([0-9,]+(?:\.\d{2})?)',
            r'Net Proceeds[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        ]
        for pattern in net_proceeds_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['net_proceeds'] = self._parse_amount(match.group(1))
                break
        
        # Payment amount transferred
        payment_patterns = [
            r'Amount Transferred[:\s]+£?([0-9,]+(?:\.\d{2})?)',
            r'Payment.*?£?([0-9,]+(?:\.\d{2})?)\s+has been.*?transferred',
        ]
        for pattern in payment_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['payment_amount'] = self._parse_amount(match.group(1))
                break
        
        # Transfer date
        transfer_patterns = [
            r'Transfer Date[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
            r'Payment Date[:\s]+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        ]
        for pattern in transfer_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['transfer_date'] = match.group(1).strip()
                break
        
        # Bank name
        bank_match = re.search(r'Bank[:\s]+([A-Z][A-Z]+(?:\s+[A-Z][a-z]+)*)', text)
        if bank_match:
            data['bank_name'] = bank_match.group(1).strip()
        
        # Account number (last 4)
        account_match = re.search(r'\*+(\d{4})', text)
        if account_match:
            data['account_last_4'] = account_match.group(1)
        
        # Transfer reference
        ref_patterns = [
            r'Transfer Reference[:\s]+([A-Z0-9-]+)',
            r'Reference[:\s]+([A-Z0-9/-]+)',
        ]
        for pattern in ref_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['transfer_reference'] = match.group(1).strip()
                break
        
        # Solicitor details
        solicitor_patterns = [
            r'([A-Z][a-z]+\s+[&]\s+[A-Z][a-z]+\s+Solicitors)',
            r'Solicitor[:\s]*([A-Z][a-z\s&]+)',
        ]
        for pattern in solicitor_patterns:
            match = re.search(pattern, text)
            if match:
                data['solicitor_firm'] = match.group(1).strip()
                break
        
        return data
    
    def _extract_loan_data(self, text: str) -> Dict[str, Any]:
        """Extract data from loan agreements"""
        data = {}
        
        # Borrower
        borrower_match = re.search(r'Borrower[:\s]+([A-Z][a-z\s]+)', text, re.IGNORECASE)
        if borrower_match:
            data['borrower'] = borrower_match.group(1).strip()
        
        # Loan amount
        amount_patterns = [
            r'Loan Amount[:\s]+£?([0-9,]+(?:\.\d{2})?)',
            r'Facility[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data['loan_amount'] = self._parse_amount(match.group(1))
                break
        
        # Lender
        lender_match = re.search(r'Lender[:\s]+([A-Z][a-z\s]+)', text, re.IGNORECASE)
        if lender_match:
            data['lender'] = lender_match.group(1).strip()
        
        return data
    
    def _extract_solicitor_statement_data(self, text: str) -> Dict[str, Any]:
        """Extract data from solicitor's client account statement"""
        data = {}
        
        # Client name
        client_match = re.search(r'Client[:\s]+([A-Z][a-z\s]+)', text, re.IGNORECASE)
        if client_match:
            data['client_name'] = client_match.group(1).strip()
        
        # Statement period
        period_match = re.search(r'Period[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE)
        if period_match:
            data['statement_period'] = period_match.group(1).strip()
        
        return data
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float"""
        try:
            cleaned = amount_str.replace(',', '').replace('£', '').strip()
            return float(cleaned)
        except:
            return 0.0
    
    def _calculate_confidence(self, extracted_data: Dict[str, Any]) -> float:
        """
        Calculate confidence score based on how much data was extracted
        0.0 = nothing extracted
        1.0 = all expected fields extracted
        """
        if not extracted_data:
            return 0.0
        
        # Count non-empty fields
        filled_fields = sum(1 for v in extracted_data.values() if v)
        total_fields = len(extracted_data)
        
        if total_fields == 0:
            return 0.0
        
        return filled_fields / total_fields


# Singleton
pdf_extractor = PDFDocumentExtractor()
