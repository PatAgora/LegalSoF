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
        elif 'property' in source_type or 'sale' in source_type:
            return self._verify_property_claim(result, claim, supporting_docs, bank_statements)
        elif 'loan' in source_type:
            return self._verify_loan_claim(result, claim, supporting_docs, bank_statements)
        else:
            result['issues'].append(f"Unknown source type: {source_type}")
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
        
        if bank_name and account_last_4:
            checks_passed.append(f"Bank details present: {bank_name} ****{account_last_4}")
            
            # Check 4: Match against bank statements
            matching_transaction = self._find_matching_transaction(
                bank_statements,
                expected_amount,
                payment_date,
                account_last_4
            )
            
            if matching_transaction:
                checks_passed.append(f"Transaction found in bank statement: £{matching_transaction['amount']:,.2f} on {matching_transaction['date']}")
                result['verification_details']['matching_transaction'] = matching_transaction
            else:
                issues.append("No matching transaction found in bank statements")
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
        
        # Mark as verified if critical checks passed
        result['verified'] = (
            matching_distribution is not None and
            bank_name is not None and
            account_last_4 is not None
        )
        
        result['confidence'] = confidence
        result['verification_details']['checks_passed'] = checks_passed
        result['verification_details']['extracted_data'] = extracted
        result['issues'] = issues
        
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
        
        if bank_name and account_last_4:
            checks_passed.append(f"Bank details: {bank_name} ****{account_last_4}")
            
            # Check 5: Match against bank statements
            matching_transaction = self._find_matching_transaction(
                bank_statements,
                net_proceeds or expected_amount,
                completion_date,
                account_last_4
            )
            
            if matching_transaction:
                checks_passed.append(f"Transaction found: £{matching_transaction['amount']:,.2f} on {matching_transaction['date']}")
                result['verification_details']['matching_transaction'] = matching_transaction
            else:
                issues.append("No matching transaction in bank statements")
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
        
        # Mark as verified if critical checks passed
        result['verified'] = (
            net_proceeds is not None and
            abs(net_proceeds - expected_amount) / expected_amount < 0.01 and
            bank_name is not None
        )
        
        result['confidence'] = confidence
        result['verification_details']['checks_passed'] = checks_passed
        result['verification_details']['extracted_data'] = extracted
        result['issues'] = issues
        
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


# Singleton
document_verifier = DocumentVerifier()
