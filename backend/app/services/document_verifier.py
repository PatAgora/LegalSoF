"""
Document Verification Service
Validates extracted PDF data against SoF claims
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import re


class DocumentVerifier:
    """
    Verify that extracted document data matches and supports SoF claims
    """
    
    def verify_documents_against_claims(
        self,
        claims: List[Dict[str, Any]],
        supporting_docs: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Cross-reference supporting documents with claims and bank statements
        
        Args:
            claims: List of SoF claims from client explanation
            supporting_docs: List of uploaded supporting documents with extracted data
            bank_statements: List of bank transactions
        
        Returns:
            {
                "verifications": [
                    {
                        "claim_id": int,
                        "claim_source": str,
                        "claim_amount": float,
                        "verified": bool,
                        "verification_details": {...},
                        "confidence": float,
                        "issues": [str]
                    }
                ],
                "overall_verification_rate": float,
                "missing_documents": [str]
            }
        """
        verifications = []
        
        for idx, claim in enumerate(claims):
            verification = self._verify_single_claim(
                claim_id=idx,
                claim=claim,
                supporting_docs=supporting_docs,
                bank_statements=bank_statements
            )
            verifications.append(verification)
        
        # Calculate overall stats
        verified_count = sum(1 for v in verifications if v['verified'])
        overall_rate = verified_count / len(verifications) if verifications else 0.0
        
        # Identify missing documents
        missing_docs = []
        for verification in verifications:
            if not verification['verified']:
                missing_docs.extend(verification.get('missing_documents', []))
        
        return {
            "verifications": verifications,
            "overall_verification_rate": overall_rate,
            "missing_documents": list(set(missing_docs))  # Remove duplicates
        }
    
    def _verify_single_claim(
        self,
        claim_id: int,
        claim: Dict[str, Any],
        supporting_docs: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify a single claim against documents and transactions"""
        
        source_type = claim['source_type'].lower()
        expected_amount = claim['expected_amount']
        
        # Initialize verification result
        result = {
            "claim_id": claim_id,
            "claim_source": claim['source_type'],
            "claim_amount": expected_amount,
            "verified": False,
            "verification_details": {},
            "confidence": 0.0,
            "issues": [],
            "missing_documents": []
        }
        
        # Route to appropriate verification method
        if 'inheritance' in source_type:
            return self._verify_inheritance_claim(result, claim, supporting_docs, bank_statements)
        elif 'business' in source_type:
            return self._verify_business_claim(result, claim, supporting_docs, bank_statements)
        elif 'property' in source_type or 'sale' in source_type:
            return self._verify_property_claim(result, claim, supporting_docs, bank_statements)
        elif 'loan' in source_type:
            return self._verify_loan_claim(result, claim, supporting_docs, bank_statements)
        elif 'gift' in source_type:
            return self._verify_gift_claim(result, claim, supporting_docs, bank_statements)
        elif 'savings' in source_type:
            return self._verify_savings_claim(result, claim, supporting_docs, bank_statements)
        else:
            result['issues'].append(f"Unsupported source type: '{source_type}' - manual verification required")
            result['differences'] = [{
                'field': 'source_type',
                'severity': 'missing',
                'issue': f"Source type '{source_type}' is not currently supported for automatic verification",
                'expected': 'Supported types: inheritance, property sale, loan, gift, savings',
                'found': source_type
            }]
            result['missing_documents'].append(f"Documentation for {source_type} claim")
            return result
    
    def _verify_inheritance_claim(
        self,
        result: Dict[str, Any],
        claim: Dict[str, Any],
        supporting_docs: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify inheritance claim"""
        
        expected_amount = claim['expected_amount']
        checks_passed = []
        issues = []
        
        # Find probate document
        probate_doc = None
        for doc in supporting_docs:
            if doc.get('document_type') == 'Probate grant':
                probate_doc = doc
                break
        
        if not probate_doc:
            issues.append("No probate grant document provided")
            result['missing_documents'].append("Probate grant or letters of administration")
            result['verified'] = False
            result['issues'] = issues
            return result
        
        # AUDIT TRAIL: Record which document was used for verification
        result['verification_details']['document_used'] = {
            'filename': probate_doc.get('filename', 'Unknown'),
            'document_type': probate_doc.get('document_type'),
            'uploaded_at': probate_doc.get('uploaded_at'),
        }
        
        extracted = probate_doc.get('extracted_data', {})
        
        # Check 1: Distribution amount matches claim
        distributions = extracted.get('distributions', [])
        matching_distribution = None
        
        for dist in distributions:
            dist_amount = dist.get('amount', 0)
            # Allow 1% tolerance for amount matching
            if abs(dist_amount - expected_amount) / expected_amount < 0.01:
                matching_distribution = dist
                checks_passed.append("Distribution amount matches claim")
                break
        
        if not matching_distribution:
            # Check if expected amount is close to any distribution
            closest_dist = min(distributions, key=lambda d: abs(d.get('amount', 0) - expected_amount)) if distributions else None
            if closest_dist:
                issues.append(f"Distribution amount mismatch: document shows £{closest_dist.get('amount'):,.2f}, claim is £{expected_amount:,.2f}")
            else:
                issues.append("No matching distribution found in probate document")
        
        # Check 2: Payment date exists
        payment_date = extracted.get('payment_date')
        if payment_date:
            checks_passed.append(f"Payment date documented: {payment_date}")
        else:
            issues.append("No payment date found in probate document")
        
        # Check 3: Bank account details present
        bank_name = extracted.get('bank_name')
        account_last_4 = extracted.get('account_last_4')
        
        matching_transaction = None
        if bank_name and account_last_4:
            checks_passed.append(f"Bank details present: {bank_name} ****{account_last_4}")
            
            # Check 4: Match against bank statements (INFORMATIONAL ONLY - doesn't affect document confidence)
            matching_transaction = self._find_matching_transaction(
                bank_statements,
                expected_amount,
                payment_date,
                account_last_4
            )
            
            if matching_transaction:
                # INFORMATIONAL: Bank transaction found (doesn't affect document verification)
                checks_passed.append(f"Bank transaction found: £{matching_transaction['amount']:,.2f} on {matching_transaction['date']}")
                result['verification_details']['matching_transaction'] = matching_transaction
            # NOTE: We don't add an issue if no bank match - that's handled by the assessment engine
            # The document itself is valid regardless of bank statement matching
        else:
            issues.append("Bank account details incomplete in probate document")
        
        # Check 5: Probate reference exists
        probate_ref = extracted.get('probate_reference')
        if probate_ref:
            checks_passed.append(f"Probate reference: {probate_ref}")
            result['verification_details']['document_used']['probate_reference'] = probate_ref
        probate_ref = extracted.get('probate_reference')
        if probate_ref:
            checks_passed.append(f"Probate reference: {probate_ref}")
        else:
            issues.append("No probate reference number found")
        
        # Calculate confidence
        confidence = len(checks_passed) / (len(checks_passed) + len(issues)) if (checks_passed or issues) else 0.0
        
        # Mark as verified ONLY if:
        # 1. Critical checks passed (distribution, bank details)
        # 2. Confidence is 100% (no issues found)
        result['verified'] = (
            matching_distribution is not None and
            bank_name is not None and
            account_last_4 is not None and
            confidence >= 0.999  # Require 100% confidence (99.9%+ for floating point tolerance)
        )
        
        result['confidence'] = confidence
        result['verification_details']['checks_passed'] = checks_passed
        result['verification_details']['extracted_data'] = extracted
        result['issues'] = issues
        
        # Flag for review if confidence is not 100%
        result['requires_review'] = confidence < 0.999 or len(issues) > 0
        if result['requires_review']:
            result['review_reason'] = issues[0] if issues else "Verification incomplete"
        
        # TRACK SPECIFIC DIFFERENCES: What exactly differs between claim and document?
        differences = []
        for issue in issues:
            differences.append({
                'field': self._extract_field_name(issue),
                'issue': issue,
                'severity': 'missing' if 'not found' in issue.lower() or 'no ' in issue.lower() else 'mismatch',
                'customer_value': None,  # Customer didn't specify these fields
                'document_value': None   # Document missing this field
            })
        
        result['differences'] = differences
        result['manual_review_status'] = 'pending' if result['requires_review'] else 'not_required'
        result['manually_accepted_by'] = None
        result['manually_accepted_at'] = None
        result['acceptance_reason'] = None
        
        # BUILD COMPARISON: Customer Claim vs Document Evidence
        result['verification_details']['comparison'] = {
            'customer_claim': {
                'source_type': claim.get('source_type', 'Unknown'),
                'claimed_amount': expected_amount,
                'description': claim.get('description', 'Not provided'),
            },
            'document_evidence': {
                'deceased_name': extracted.get('deceased_name'),
                'date_of_death': extracted.get('date_of_death'),
                'executor': extracted.get('executor_beneficiary'),
                'distribution_amount': matching_distribution.get('amount') if matching_distribution else None,
                'beneficiary': matching_distribution.get('beneficiary') if matching_distribution else None,
                'payment_date': extracted.get('payment_date'),
                'bank_account': f"{bank_name} ****{account_last_4}" if bank_name and account_last_4 else None,
                'probate_reference': probate_ref,
                'gross_estate': extracted.get('gross_estate'),
                'net_estate': extracted.get('net_estate'),
            },
            'matches': {
                'amount_matches': matching_distribution is not None,
                'amount_difference': abs(matching_distribution.get('amount', 0) - expected_amount) if matching_distribution else None,
                'has_bank_details': bank_name is not None and account_last_4 is not None,
                'has_probate_reference': probate_ref is not None,
                'has_payment_date': payment_date is not None,
            }
        }
        
        return result
    
    def _verify_property_claim(
        self,
        result: Dict[str, Any],
        claim: Dict[str, Any],
        supporting_docs: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify property sale claim"""
        
        expected_amount = claim['expected_amount']
        checks_passed = []
        issues = []
        
        # Find completion statement
        completion_doc = None
        for doc in supporting_docs:
            if doc.get('document_type') == 'completion statement':
                completion_doc = doc
                break
        
        if not completion_doc:
            issues.append("No completion statement provided")
            result['missing_documents'].append("Property completion statement")
            result['verified'] = False
            result['issues'] = issues
            return result
        
        # AUDIT TRAIL: Record which document was used for verification
        result['verification_details']['document_used'] = {
            'filename': completion_doc.get('filename', 'Unknown'),
            'document_type': completion_doc.get('document_type'),
            'uploaded_at': completion_doc.get('uploaded_at'),
        }
        
        extracted = completion_doc.get('extracted_data', {})
        
        # Check 1: Net proceeds or payment amount matches claim
        net_proceeds = extracted.get('net_proceeds') or extracted.get('payment_amount')
        
        if net_proceeds:
            # Allow 1% tolerance
            if abs(net_proceeds - expected_amount) / expected_amount < 0.01:
                checks_passed.append(f"Net proceeds match claim: £{net_proceeds:,.2f}")
            else:
                issues.append(f"Amount mismatch: document shows £{net_proceeds:,.2f}, claim is £{expected_amount:,.2f}")
        else:
            issues.append("No net proceeds amount found in completion statement")
        
        # Check 2: Completion/transfer date
        completion_date = extracted.get('completion_date') or extracted.get('transfer_date')
        if completion_date:
            checks_passed.append(f"Completion date: {completion_date}")
        else:
            issues.append("No completion date found")
        
        # Check 3: Property address
        property_address = extracted.get('property_address')
        if property_address:
            checks_passed.append(f"Property address: {property_address}")
        else:
            issues.append("No property address found")
        
        # Check 4: Bank details
        bank_name = extracted.get('bank_name')
        account_last_4 = extracted.get('account_last_4')
        
        matching_transaction = None
        if bank_name and account_last_4:
            checks_passed.append(f"Bank details: {bank_name} ****{account_last_4}")
            
            # Check 5: Match against bank statements (INFORMATIONAL ONLY - doesn't affect document confidence)
            matching_transaction = self._find_matching_transaction(
                bank_statements,
                net_proceeds or expected_amount,
                completion_date,
                account_last_4
            )
            
            if matching_transaction:
                # INFORMATIONAL: Bank transaction found (doesn't affect document verification)
                checks_passed.append(f"Bank transaction found: £{matching_transaction['amount']:,.2f} on {matching_transaction['date']}")
                result['verification_details']['matching_transaction'] = matching_transaction
            # NOTE: We don't add an issue if no bank match - that's handled by the assessment engine
            # The document itself is valid regardless of bank statement matching
        else:
            issues.append("Bank details incomplete in completion statement")
        
        # Check 6: Solicitor details
        solicitor = extracted.get('solicitor_firm')
        if solicitor:
            checks_passed.append(f"Solicitor: {solicitor}")
            result['verification_details']['document_used']['solicitor_firm'] = solicitor
        else:
            issues.append("No solicitor details found")
        
        # Check 7: Title number (if available)
        title_number = extracted.get('title_number')
        if title_number:
            checks_passed.append(f"Title number: {title_number}")
            result['verification_details']['document_used']['title_number'] = title_number
        
        # Calculate confidence
        confidence = len(checks_passed) / (len(checks_passed) + len(issues)) if (checks_passed or issues) else 0.0
        
        # Mark as verified ONLY if:
        # 1. Critical checks passed (amount match, bank details)
        # 2. Confidence is 100% (no issues found)
        result['verified'] = (
            net_proceeds is not None and
            abs(net_proceeds - expected_amount) / expected_amount < 0.01 and
            bank_name is not None and
            confidence >= 0.999  # Require 100% confidence (99.9%+ for floating point tolerance)
        )
        
        result['confidence'] = confidence
        result['verification_details']['checks_passed'] = checks_passed
        result['verification_details']['extracted_data'] = extracted
        result['issues'] = issues
        
        # Flag for review if confidence is not 100%
        result['requires_review'] = confidence < 0.999 or len(issues) > 0
        if result['requires_review']:
            result['review_reason'] = issues[0] if issues else "Verification incomplete"
        
        # TRACK SPECIFIC DIFFERENCES: What exactly differs between claim and document?
        differences = []
        for issue in issues:
            differences.append({
                'field': self._extract_field_name(issue),
                'issue': issue,
                'severity': 'missing' if 'not found' in issue.lower() or 'no ' in issue.lower() else 'mismatch',
                'customer_value': None,  # Customer didn't specify these fields
                'document_value': None   # Document missing this field
            })
        
        result['differences'] = differences
        result['manual_review_status'] = 'pending' if result['requires_review'] else 'not_required'
        result['manually_accepted_by'] = None
        result['manually_accepted_at'] = None
        result['acceptance_reason'] = None
        
        # BUILD COMPARISON: Customer Claim vs Document Evidence
        result['verification_details']['comparison'] = {
            'customer_claim': {
                'source_type': claim.get('source_type', 'Unknown'),
                'claimed_amount': expected_amount,
                'description': claim.get('description', 'Not provided'),
            },
            'document_evidence': {
                'property_address': property_address,
                'vendor_name': extracted.get('vendor_name'),
                'completion_date': completion_date,
                'contract_price': extracted.get('contract_price'),
                'net_proceeds': net_proceeds,
                'bank_account': f"{bank_name} ****{account_last_4}" if bank_name and account_last_4 else None,
                'title_number': extracted.get('title_number'),
                'solicitor_firm': solicitor,
                'transfer_reference': extracted.get('transfer_reference'),
            },
            'matches': {
                'amount_matches': net_proceeds is not None and abs(net_proceeds - expected_amount) / expected_amount < 0.01,
                'amount_difference': abs(net_proceeds - expected_amount) if net_proceeds else None,
                'has_property_address': property_address is not None,
                'has_completion_date': completion_date is not None,
                'has_bank_details': bank_name is not None and account_last_4 is not None,
                'has_solicitor': solicitor is not None,
                'has_title_number': extracted.get('title_number') is not None,
            }
        }
        
        return result
    
    def _verify_loan_claim(
        self,
        result: Dict[str, Any],
        claim: Dict[str, Any],
        supporting_docs: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify loan claim"""
        
        expected_amount = claim['expected_amount']
        issues = []
        
        # Find loan document
        loan_doc = None
        for doc in supporting_docs:
            if doc.get('document_type') == 'Loan':
                loan_doc = doc
                break
        
        if not loan_doc:
            issues.append("No loan agreement provided")
            result['missing_documents'].append("Loan agreement and offer letter")
            result['verified'] = False
            result['issues'] = issues
            return result
        
        # AUDIT TRAIL: Record which document was used for verification
        result['verification_details']['document_used'] = {
            'filename': loan_doc.get('filename', 'Unknown'),
            'document_type': loan_doc.get('document_type'),
            'uploaded_at': loan_doc.get('uploaded_at'),
        }
        
        # Additional checks can be added here
        result['issues'] = issues
        return result
    
    def _verify_business_claim(
        self,
        result: Dict[str, Any],
        claim: Dict[str, Any],
        supporting_docs: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify business sale claim with share purchase agreement or business sale documentation"""
        
        expected_amount = claim['expected_amount']
        expected_date = claim.get('expected_date_range', {}).get('start', '')
        
        checks_passed = []
        issues = []
        differences = []
        
        # Find business sale document (share purchase agreement, business sale agreement, etc.)
        business_doc = None
        for doc in supporting_docs:
            filename = doc.get('filename', '').lower()
            doc_type = doc.get('document_type', '').lower()
            if any(term in filename or term in doc_type for term in ['share', 'purchase', 'business', 'sale', 'agreement']):
                business_doc = doc
                break
        
        if not business_doc:
            issues.append("No business sale documentation provided")
            result['missing_documents'].append("Share purchase agreement or business sale agreement")
            result['verified'] = False
            result['issues'] = issues
            differences.append({
                'field': 'business_sale_documentation',
                'severity': 'missing',
                'issue': 'No business sale documentation provided',
                'expected': 'Share purchase agreement or business sale agreement',
                'found': None
            })
            result['differences'] = differences
            return result
        
        # AUDIT TRAIL: Record which document was used for verification
        result['verification_details']['document_used'] = {
            'filename': business_doc.get('filename', 'Unknown'),
            'document_type': business_doc.get('document_type', 'Business Sale Agreement'),
            'uploaded_at': business_doc.get('uploaded_at'),
        }
        
        # Extract data from document
        extracted_data = business_doc.get('extracted_data', {})
        
        if not extracted_data:
            issues.append("Business sale document provided but no data could be extracted")
            differences.append({
                'field': 'document_content',
                'severity': 'error',
                'issue': 'Unable to extract data from the business sale document',
                'expected': 'Readable document with sale details, amount, and date',
                'found': 'Unreadable or empty document'
            })
        
        # Verify sale amount
        doc_amount = extracted_data.get('sale_amount') or extracted_data.get('consideration') or extracted_data.get('net_proceeds')
        if doc_amount:
            # Allow 1% tolerance
            amount_match = abs(doc_amount - expected_amount) / expected_amount <= 0.01
            if amount_match:
                checks_passed.append(f"Sale amount matches: £{doc_amount:,.2f}")
            else:
                differences.append({
                    'field': 'sale_amount',
                    'severity': 'error',
                    'issue': 'Sale amount does not match claimed amount',
                    'expected': f'£{expected_amount:,.2f}',
                    'found': f'£{doc_amount:,.2f}' if doc_amount else None
                })
        else:
            differences.append({
                'field': 'sale_amount',
                'severity': 'missing',
                'issue': 'No sale amount found in business sale document',
                'expected': f'£{expected_amount:,.2f}',
                'found': None
            })
        
        # Verify sale date
        doc_date = extracted_data.get('sale_date') or extracted_data.get('completion_date') or extracted_data.get('payment_date')
        if doc_date:
            checks_passed.append(f"Sale date documented: {doc_date}")
        else:
            differences.append({
                'field': 'sale_date',
                'severity': 'missing',
                'issue': 'No sale date found in business sale document',
                'expected': expected_date or 'Sale/completion date',
                'found': None
            })
        
        # Verify buyer name
        buyer_name = extracted_data.get('buyer_name')
        if buyer_name:
            checks_passed.append(f"Buyer identified: {buyer_name}")
        else:
            differences.append({
                'field': 'buyer_name',
                'severity': 'warning',
                'issue': 'No buyer name found in business sale document',
                'expected': 'Buyer/purchaser name',
                'found': None
            })
        
        # Verify seller name
        seller_name = extracted_data.get('seller_name') or extracted_data.get('business_name')
        if seller_name:
            checks_passed.append(f"Seller identified: {seller_name}")
        else:
            differences.append({
                'field': 'seller_name',
                'severity': 'warning',
                'issue': 'No seller name found in business sale document',
                'expected': 'Seller/business name',
                'found': None
            })
        
        # Verify solicitor details
        solicitor = extracted_data.get('solicitor_firm')
        if solicitor:
            checks_passed.append(f"Solicitor: {solicitor}")
        
        # Calculate confidence based on checks passed
        total_checks = 4  # amount, date, buyer, seller
        confidence = len([c for c in checks_passed if any(key in c for key in ['amount', 'date', 'Buyer', 'Seller'])]) / total_checks
        
        # Set verification status
        result['verified'] = confidence >= 0.75  # Need at least 3 out of 4 key fields
        result['confidence'] = confidence
        result['checks_passed'] = checks_passed
        result['issues'] = issues
        result['differences'] = differences
        
        if confidence < 0.999:
            result['requires_review'] = True
        
        return result
    
    def _verify_gift_claim(
        self,
        result: Dict[str, Any],
        claim: Dict[str, Any],
        supporting_docs: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify gift claim with gift letter"""
        
        expected_amount = claim['expected_amount']
        expected_donor = claim.get('expected_payer', '')
        gift_date = claim.get('gift_date', claim.get('expected_date_range', {}).get('start', ''))
        
        checks_passed = []
        issues = []
        differences = []
        
        # Find gift letter document
        gift_doc = None
        for doc in supporting_docs:
            filename = doc.get('filename', '').lower()
            doc_type = doc.get('document_type', '').lower()
            if 'gift' in filename or 'gift' in doc_type:
                gift_doc = doc
                break
        
        if not gift_doc:
            issues.append("No gift letter provided")
            result['missing_documents'].append("Gift letter from donor")
            result['verified'] = False
            result['issues'] = issues
            result['differences'] = [{
                'field': 'gift_letter',
                'severity': 'missing',
                'issue': 'No gift letter document found',
                'expected': 'Gift letter',
                'found': None
            }]
            return result
        
        # AUDIT TRAIL: Record which document was used for verification
        result['verification_details']['document_used'] = {
            'filename': gift_doc.get('filename', 'Unknown'),
            'document_type': 'Gift letter',
            'uploaded_at': gift_doc.get('uploaded_at'),
        }
        
        # Extract data from gift document
        extracted_data = gift_doc.get('extracted_data', {})
        
        # Check for required gift letter fields
        if not extracted_data or len(extracted_data) == 0:
            issues.append("Gift letter document provided but no data could be extracted")
            differences.append({
                'field': 'document_content',
                'severity': 'missing',
                'issue': 'Unable to extract data from gift letter - document may be unreadable or improperly formatted',
                'expected': 'Readable gift letter with donor details, amount, and date',
                'found': 'Unreadable or empty document'
            })
        
        # Check donor name
        donor_found = extracted_data.get('donor_name') or extracted_data.get('sender_name')
        if not donor_found:
            issues.append("No donor name found in gift letter")
            differences.append({
                'field': 'donor_name',
                'severity': 'missing',
                'issue': 'Donor name not found in gift letter',
                'expected': expected_donor if expected_donor else 'Donor name',
                'found': None
            })
        elif expected_donor and expected_donor.lower() not in donor_found.lower():
            differences.append({
                'field': 'donor_name',
                'severity': 'mismatch',
                'issue': f'Donor name mismatch',
                'expected': expected_donor,
                'found': donor_found
            })
        else:
            checks_passed.append(f"Donor name: {donor_found}")
        
        # Check gift amount
        gift_amount = extracted_data.get('gift_amount') or extracted_data.get('amount')
        if not gift_amount:
            issues.append("No gift amount found in gift letter")
            differences.append({
                'field': 'gift_amount',
                'severity': 'missing',
                'issue': 'Gift amount not specified in letter',
                'expected': f'£{expected_amount:,.2f}',
                'found': None
            })
        else:
            # Parse amount if string
            if isinstance(gift_amount, str):
                gift_amount = float(re.sub(r'[£,]', '', gift_amount))
            
            amount_diff = abs(gift_amount - expected_amount) / expected_amount
            if amount_diff > 0.01:  # More than 1% difference
                differences.append({
                    'field': 'gift_amount',
                    'severity': 'mismatch',
                    'issue': f'Gift amount mismatch',
                    'expected': f'£{expected_amount:,.2f}',
                    'found': f'£{gift_amount:,.2f}'
                })
            else:
                checks_passed.append(f"Gift amount: £{gift_amount:,.2f}")
        
        # Check gift date
        letter_date = extracted_data.get('gift_date') or extracted_data.get('date')
        if not letter_date:
            issues.append("No date found in gift letter")
            differences.append({
                'field': 'gift_date',
                'severity': 'missing',
                'issue': 'Date not specified in gift letter',
                'expected': gift_date if gift_date else 'Gift date',
                'found': None
            })
        else:
            checks_passed.append(f"Gift date: {letter_date}")
        
        # Check relationship
        relationship = extracted_data.get('relationship') or extracted_data.get('donor_relationship')
        if not relationship:
            differences.append({
                'field': 'relationship',
                'severity': 'missing',
                'issue': 'Relationship to donor not stated in gift letter',
                'expected': 'Relationship to donor',
                'found': None
            })
        else:
            checks_passed.append(f"Relationship: {relationship}")
        
        # Check declaration that gift is not a loan
        no_repayment = extracted_data.get('no_repayment_required') or extracted_data.get('not_a_loan')
        if not no_repayment:
            differences.append({
                'field': 'repayment_declaration',
                'severity': 'missing',
                'issue': 'No declaration that gift does not require repayment',
                'expected': 'Statement confirming no repayment is required',
                'found': None
            })
        else:
            checks_passed.append("Confirmed: No repayment required")
        
        # Calculate confidence
        required_fields = 5  # donor, amount, date, relationship, no_repayment
        found_fields = len(checks_passed)
        confidence = found_fields / required_fields if required_fields > 0 else 0.0
        
        # Store verification details
        result['verification_details']['checks_passed'] = checks_passed
        result['verification_details']['comparison'] = {
            'customer_claim': {
                'claimed_amount': expected_amount,
                'donor': expected_donor,
                'gift_date': gift_date
            },
            'document_evidence': {
                'donor_name': donor_found,
                'gift_amount': gift_amount,
                'gift_date': letter_date,
                'relationship': relationship,
                'no_repayment': no_repayment
            },
            'matches': {
                'amount_matches': gift_amount and abs(gift_amount - expected_amount) / expected_amount <= 0.01,
                'donor_matches': donor_found and expected_donor and expected_donor.lower() in donor_found.lower()
            }
        }
        
        result['verified'] = len(issues) == 0 and len(differences) == 0
        result['confidence'] = confidence
        result['issues'] = issues
        result['differences'] = differences
        result['requires_review'] = confidence < 0.999
        
        return result
    
    def _verify_savings_claim(
        self,
        result: Dict[str, Any],
        claim: Dict[str, Any],
        supporting_docs: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify savings claim with bank statements and salary evidence"""
        
        expected_amount = claim['expected_amount']
        
        issues = []
        differences = []
        
        # For savings, we need historical bank statements or payslips
        # Be specific to avoid matching completion statements, solicitor statements, etc.
        savings_doc = None
        for doc in supporting_docs:
            filename = doc.get('filename', '').lower()
            doc_type = doc.get('document_type', '').lower()
            
            # Exclude property/solicitor documents
            if any(exclude in filename or exclude in doc_type for exclude in ['completion', 'solicitor', 'completion_statement']):
                continue
            
            # Look for savings-related documents
            if any(keyword in filename or keyword in doc_type for keyword in ['bank_statement', 'bank statement', 'payslip', 'salary', 'pay slip', 'p60', 'p45', 'savings']):
                savings_doc = doc
                break
        
        if not savings_doc:
            issues.append("No document provided for savings account")
            result['missing_documents'].append("Historical bank statements or payslips showing savings accumulation")
            result['verified'] = False
            result['issues'] = issues
            result['differences'] = [{
                'field': 'savings_documentation',
                'severity': 'missing',
                'issue': 'No document provided for savings account - historical bank statements or payslips required to evidence savings accumulation',
                'expected': f'Bank statements showing £{expected_amount:,.2f} savings accumulated over time',
                'found': None
            }]
            return result
        
        # AUDIT TRAIL: Record which document was used for verification
        result['verification_details']['document_used'] = {
            'filename': savings_doc.get('filename', 'Unknown'),
            'document_type': 'Bank statements / Payslips',
            'uploaded_at': savings_doc.get('uploaded_at'),
        }
        
        # For now, mark as requiring manual review
        issues.append("Savings claims require detailed manual review of accumulation over time")
        differences.append({
            'field': 'savings_verification',
            'severity': 'review_required',
            'issue': 'Savings accumulation requires detailed verification of income sources and account history',
            'expected': f'Evidence of £{expected_amount:,.2f} savings accumulation',
            'found': 'Document provided but requires manual verification'
        })
        
        result['verified'] = False
        result['confidence'] = 0.3  # Low confidence, requires manual review
        result['issues'] = issues
        result['differences'] = differences
        result['requires_review'] = True
        
        return result
    
    def _find_matching_transaction(
        self,
        bank_statements: List[Dict[str, Any]],
        expected_amount: float,
        expected_date: Optional[str],
        account_last_4: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Find a transaction that matches the expected criteria"""
        
        for txn in bank_statements:
            # Check amount (allow 1% tolerance)
            if abs(txn.get('amount', 0) - expected_amount) / expected_amount > 0.01:
                continue
            
            # Check direction (should be credit for incoming funds)
            if txn.get('direction') != 'credit':
                continue
            
            # Check account if provided
            if account_last_4:
                account_id = txn.get('account_id', '')
                if account_last_4 not in account_id:
                    continue
            
            # Check date if provided (allow ±7 days)
            if expected_date:
                try:
                    txn_date = datetime.strptime(txn.get('date', ''), '%Y-%m-%d')
                    # Parse expected date (various formats)
                    for fmt in ['%d %B %Y', '%d %b %Y', '%Y-%m-%d', '%d/%m/%Y']:
                        try:
                            exp_date = datetime.strptime(expected_date.replace('st', '').replace('nd', '').replace('rd', '').replace('th', ''), fmt)
                            break
                        except:
                            continue
                    else:
                        # Couldn't parse date, skip date check
                        return txn
                    
                    # Check if within 7 days
                    if abs((txn_date - exp_date).days) <= 7:
                        return txn
                except:
                    # Date parsing failed, return the transaction anyway if amount matches
                    return txn
            else:
                # No date to check, return if amount matches
                return txn
        
        return None
    
    def _extract_field_name(self, issue: str) -> str:
        """Extract the field name from an issue description"""
        # Map common issue patterns to field names
        if 'solicitor' in issue.lower():
            return 'solicitor_firm'
        elif 'probate reference' in issue.lower():
            return 'probate_reference'
        elif 'bank details' in issue.lower() or 'bank account' in issue.lower():
            return 'bank_details'
        elif 'payment date' in issue.lower():
            return 'payment_date'
        elif 'completion date' in issue.lower():
            return 'completion_date'
        elif 'property address' in issue.lower():
            return 'property_address'
        elif 'net proceeds' in issue.lower() or 'amount' in issue.lower():
            return 'amount'
        elif 'title number' in issue.lower():
            return 'title_number'
        elif 'vendor' in issue.lower():
            return 'vendor_name'
        else:
            return 'unknown_field'


# Singleton
document_verifier = DocumentVerifier()
