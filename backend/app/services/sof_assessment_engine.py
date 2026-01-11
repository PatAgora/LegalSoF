"""
Source of Funds (SoF) Assessment Engine
UK Legal Sector - Business Purchase Matters

100% LOCAL - No external API calls
Integrates with Transaction Review for comprehensive AML assessment
"""
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import re
import json
from decimal import Decimal

class SoFAssessmentEngine:
    """
    Automated SoF assessment engine for UK legal sector
    Analyzes client explanations against bank statement evidence
    Integrates with Transaction Review for holistic AML assessment
    """
    
    def __init__(self, matter_id: int, db: Session):
        self.matter_id = matter_id
        self.db = db
        
    def assess(
        self,
        client_info: Dict[str, Any],
        purchase: Dict[str, Any],
        sof_explanation: str,
        bank_statements: List[Dict[str, Any]],
        known_documents: List[str] = None,
        constraints: Dict[str, Any] = None,
        flags: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Main assessment method
        Returns structured JSON with claims, evidence, decision, and actions
        """
        
        # Extract client risk rating
        risk_rating = client_info.get('client_risk_rating', 'medium').lower()
        
        # Step 1: Parse SoF explanation into testable claims
        claims = self.parse_sof_claims(sof_explanation, purchase)
        
        # Step 2: Find evidence in bank statements
        evidence_matches = self.match_evidence(claims, bank_statements)
        
        # Step 3: Trace funding paths
        funding_paths = self.trace_funding_paths(
            bank_statements, 
            purchase, 
            claims
        )
        
        # Step 4: Check date alignment
        date_alignment = self.check_date_alignment(
            claims,
            bank_statements,
            constraints
        )
        
        # Step 5: Get Transaction Review alerts (CRITICAL INTEGRATION)
        transaction_review_data = self.get_transaction_review_data()
        
        # Step 6: Identify red flags
        red_flags = self.identify_red_flags(
            bank_statements,
            claims,
            evidence_matches,
            flags or {},
            transaction_review_data
        )
        
        # Step 7: Make overall decision
        outcome = self.make_decision(
            risk_rating,
            claims,
            evidence_matches,
            funding_paths,
            red_flags,
            transaction_review_data
        )
        
        # Step 8: Generate next actions
        next_actions = self.generate_next_actions(
            risk_rating,
            claims,
            evidence_matches,
            red_flags,
            known_documents or [],
            transaction_review_data
        )
        
        # Step 9: Generate file note
        file_note = self.generate_file_note(
            client_info,
            purchase,
            claims,
            evidence_matches,
            funding_paths,
            red_flags,
            transaction_review_data,
            outcome,
            next_actions
        )
        
        return {
            "claims": claims,
            "evidence_matches": evidence_matches,
            "funding_paths": funding_paths,
            "date_alignment": date_alignment,
            "red_flags": red_flags,
            "transaction_review_summary": transaction_review_data.get('summary', {}),
            "outcome": outcome,
            "next_actions": next_actions,
            "file_note_summary": file_note,
            "assessment_date": datetime.utcnow().isoformat(),
            "matter_id": self.matter_id
        }
    
    def parse_sof_claims(
        self, 
        sof_explanation: str, 
        purchase: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract testable claims from client's SoF explanation
        """
        claims = []
        
        # Common source patterns
        patterns = {
            'inheritance': r'inherit(?:ed|ance).*?(?:£|GBP|EUR|USD)?\s*([0-9,]+(?:\.[0-9]{2})?)',
            'property_sale': r'(?:sold|sale of).*?property.*?(?:£|GBP)?\s*([0-9,]+(?:\.[0-9]{2})?)',
            'savings': r'savings.*?(?:£|GBP)?\s*([0-9,]+(?:\.[0-9]{2})?)',
            'loan': r'loan.*?(?:£|GBP)?\s*([0-9,]+(?:\.[0-9]{2})?)',
            'business_sale': r'(?:sold|sale of).*?(?:business|company).*?(?:£|GBP)?\s*([0-9,]+(?:\.[0-9]{2})?)',
            'investment': r'investment.*?(?:£|GBP)?\s*([0-9,]+(?:\.[0-9]{2})?)',
            'gift': r'gift.*?(?:£|GBP)?\s*([0-9,]+(?:\.[0-9]{2})?)',
            'dividend': r'dividend.*?(?:£|GBP)?\s*([0-9,]+(?:\.[0-9]{2})?)'
        }
        
        # Bank account mentions
        banks = ['barclays', 'hsbc', 'lloyds', 'natwest', 'santander', 'nationwide', 
                 'rbs', 'halifax', 'bank of scotland', 'tesco bank', 'metro bank']
        
        claim_id = 1
        sof_lower = sof_explanation.lower()
        
        for source_type, pattern in patterns.items():
            matches = re.finditer(pattern, sof_lower, re.IGNORECASE)
            for match in matches:
                amount_str = match.group(1).replace(',', '')
                try:
                    amount = float(amount_str)
                    
                    # Extract date mentions near this claim
                    date_range = self._extract_date_range(sof_explanation, match.start())
                    
                    # Extract payer/counterparty mentions
                    counterparty = self._extract_counterparty(
                        sof_explanation, 
                        match.start(),
                        source_type
                    )
                    
                    # Extract account mentions
                    expected_account = None
                    for bank in banks:
                        if bank in sof_lower:
                            expected_account = bank.title()
                            break
                    
                    claims.append({
                        "claim_id": claim_id,
                        "source_type": source_type.replace('_', ' ').title(),
                        "expected_amount": amount,
                        "expected_currency": purchase.get('currency', 'GBP'),
                        "expected_date_range": date_range,
                        "expected_payer": counterparty,
                        "expected_account": expected_account,
                        "claim_text": match.group(0)
                    })
                    claim_id += 1
                except ValueError:
                    continue
        
        # If no claims extracted, create a generic claim based on purchase amount
        if not claims:
            claims.append({
                "claim_id": 1,
                "source_type": "Unspecified",
                "expected_amount": purchase.get('amount', 0),
                "expected_currency": purchase.get('currency', 'GBP'),
                "expected_date_range": None,
                "expected_payer": None,
                "expected_account": None,
                "claim_text": "Source not clearly specified in explanation"
            })
        
        return claims
    
    def _extract_date_range(self, text: str, position: int) -> Optional[Dict[str, str]]:
        """Extract date range from text near position"""
        # Look 200 chars before and after
        snippet = text[max(0, position-200):min(len(text), position+200)]
        
        # Common date patterns
        date_patterns = [
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # DD/MM/YYYY
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # YYYY-MM-DD
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',  # Month Year
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})'  # Mon Year
        ]
        
        dates_found = []
        for pattern in date_patterns:
            matches = re.finditer(pattern, snippet, re.IGNORECASE)
            for match in matches:
                dates_found.append(match.group(0))
        
        if dates_found:
            # Simple heuristic: use first and last date as range
            if len(dates_found) >= 2:
                return {"start": dates_found[0], "end": dates_found[-1]}
            else:
                return {"start": dates_found[0], "end": dates_found[0]}
        
        return None
    
    def _extract_counterparty(
        self, 
        text: str, 
        position: int, 
        source_type: str
    ) -> Optional[str]:
        """Extract counterparty/payer from text"""
        snippet = text[max(0, position-150):min(len(text), position+150)]
        
        # Source-specific patterns
        if source_type == 'inheritance':
            patterns = [
                r'(?:from|estate of)\s+([A-Z][a-z]+ [A-Z][a-z]+)',
                r'(?:grandmother|grandfather|mother|father|aunt|uncle)\s+([A-Z][a-z]+ [A-Z][a-z]+)?'
            ]
        elif source_type == 'loan':
            patterns = [
                r'(?:from|lender)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?(?:\s+Bank)?)'
            ]
        elif source_type in ['property_sale', 'business_sale']:
            patterns = [
                r'(?:buyer|purchaser)\s+([A-Z][a-z]+ [A-Z][a-z]+)',
                r'sold to\s+([A-Z][a-z]+ [A-Z][a-z]+)'
            ]
        else:
            patterns = [r'(?:from|by)\s+([A-Z][a-z]+ [A-Z][a-z]+)']
        
        for pattern in patterns:
            match = re.search(pattern, snippet)
            if match:
                return match.group(1).strip()
        
        return None
    
    def match_evidence(
        self,
        claims: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find evidence in bank statements supporting each claim
        """
        evidence_matches = []
        
        for claim in claims:
            matches = []
            expected_amount = claim['expected_amount']
            tolerance = expected_amount * 0.05  # 5% tolerance
            
            # Filter to credit transactions
            credits = [t for t in bank_statements if t.get('direction') == 'credit']
            
            for txn in credits:
                txn_amount = txn.get('amount', 0)
                
                # Check amount match (within tolerance)
                if abs(txn_amount - expected_amount) <= tolerance:
                    match_quality = "exact" if txn_amount == expected_amount else "approximate"
                    
                    # Check counterparty match if specified
                    counterparty_match = False
                    if claim.get('expected_payer'):
                        payer_lower = claim['expected_payer'].lower()
                        desc_lower = txn.get('description', '').lower()
                        counterparty_lower = txn.get('counterparty_name', '').lower()
                        
                        if payer_lower in desc_lower or payer_lower in counterparty_lower:
                            counterparty_match = True
                            match_quality = "strong"
                    
                    matches.append({
                        "account_id": txn.get('account_id'),
                        "date": txn.get('date'),
                        "amount": txn.get('amount'),
                        "currency": txn.get('currency', 'GBP'),
                        "direction": txn.get('direction'),
                        "description": txn.get('description'),
                        "counterparty": txn.get('counterparty_name'),
                        "balance": txn.get('balance'),
                        "match_quality": match_quality,
                        "counterparty_match": counterparty_match
                    })
            
            evidence_matches.append({
                "claim_id": claim['claim_id'],
                "match_quality": "strong" if any(m['match_quality'] == 'strong' for m in matches) else 
                                "exact" if matches else "none",
                "transactions": matches,
                "verified": len(matches) > 0
            })
        
        return evidence_matches
    
    def trace_funding_paths(
        self,
        bank_statements: List[Dict[str, Any]],
        purchase: Dict[str, Any],
        claims: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Attempt to trace funds from sources to purchase payment
        """
        paths = []
        purchase_amount = purchase.get('amount', 0)
        purchase_date = purchase.get('expected_payment_date')
        
        # Group transactions by account
        accounts = {}
        for txn in bank_statements:
            acc_id = txn.get('account_id', 'Unknown')
            if acc_id not in accounts:
                accounts[acc_id] = []
            accounts[acc_id].append(txn)
        
        # Sort each account by date
        for acc_id in accounts:
            accounts[acc_id].sort(key=lambda x: x.get('date', ''))
        
        # Simple heuristic: find large credits, then check if balance/transfers support purchase
        large_credits = [
            t for t in bank_statements 
            if t.get('direction') == 'credit' and t.get('amount', 0) > purchase_amount * 0.1
        ]
        
        if large_credits:
            # Build a plausible path
            path_steps = []
            total_traced = 0
            
            for credit in large_credits[:3]:  # Top 3 credits
                path_steps.append(
                    f"£{credit['amount']:,.2f} received into {credit.get('account_id', 'account')} "
                    f"on {credit.get('date', 'unknown date')}"
                )
                total_traced += credit['amount']
                
                if total_traced >= purchase_amount:
                    break
            
            # Check for transfers between accounts
            transfers = [
                t for t in bank_statements
                if t.get('direction') == 'debit' and 
                   'transfer' in t.get('description', '').lower() and
                   t.get('amount', 0) > purchase_amount * 0.1
            ]
            
            for transfer in transfers[:2]:
                path_steps.append(
                    f"£{transfer['amount']:,.2f} transferred from {transfer.get('account_id', 'account')} "
                    f"on {transfer.get('date', 'unknown date')}"
                )
            
            # Calculate coverage
            coverage = min(100, int((total_traced / purchase_amount) * 100))
            
            paths.append({
                "path_id": 1,
                "description": " → ".join([c.get('account_id', 'Account') for c in large_credits[:2]]) + " → Purchase",
                "steps": path_steps,
                "total_traced": total_traced,
                "purchase_amount": purchase_amount,
                "coverage": coverage,
                "plausible": coverage >= 80
            })
        else:
            # No clear path
            paths.append({
                "path_id": 1,
                "description": "Unable to trace clear funding path",
                "steps": ["No large credits identified that match purchase amount"],
                "total_traced": 0,
                "purchase_amount": purchase_amount,
                "coverage": 0,
                "plausible": False
            })
        
        return paths
    
    def check_date_alignment(
        self,
        claims: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]],
        constraints: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Check if statement periods cover claimed receipt periods
        """
        # Get statement date range
        dates = [t.get('date') for t in bank_statements if t.get('date')]
        if not dates:
            return {
                "statement_coverage": None,
                "claimed_receipt_period": None,
                "coverage_adequate": False,
                "gaps": ["No transaction dates available"]
            }
        
        dates.sort()
        stmt_start = dates[0]
        stmt_end = dates[-1]
        
        # Get claimed date ranges
        claimed_ranges = [
            c.get('expected_date_range') 
            for c in claims 
            if c.get('expected_date_range')
        ]
        
        coverage_adequate = True
        gaps = []
        
        if claimed_ranges:
            # Check if statements cover claimed periods
            for claim_range in claimed_ranges:
                claim_start = claim_range.get('start')
                claim_end = claim_range.get('end')
                
                # Simple string comparison (assuming ISO dates)
                if claim_start and claim_start < stmt_start:
                    gaps.append(
                        f"Statements start {stmt_start} but claim mentions {claim_start}"
                    )
                    coverage_adequate = False
                
                if claim_end and claim_end > stmt_end:
                    gaps.append(
                        f"Statements end {stmt_end} but claim mentions {claim_end}"
                    )
                    coverage_adequate = False
        
        # Check for unexplained large credits outside claimed periods
        # (implementation detail - would need date parsing)
        
        return {
            "statement_coverage": {
                "start": stmt_start,
                "end": stmt_end
            },
            "claimed_receipt_period": claimed_ranges[0] if claimed_ranges else None,
            "coverage_adequate": coverage_adequate,
            "gaps": gaps if gaps else []
        }
    
    def get_transaction_review_data(self) -> Dict[str, Any]:
        """
        CRITICAL: Get Transaction Review alerts for this matter
        This integrates AML monitoring findings into SoF assessment
        """
        from app.models import TransactionAlert, Transaction
        
        alerts = self.db.query(TransactionAlert).filter(
            TransactionAlert.matter_id == self.matter_id
        ).all()
        
        if not alerts:
            return {
                "summary": {
                    "total_alerts": 0,
                    "critical_alerts": 0,
                    "high_alerts": 0,
                    "medium_alerts": 0,
                    "key_concerns": []
                },
                "alerts": []
            }
        
        # Count by severity
        critical = sum(1 for a in alerts if a.severity == 'CRITICAL')
        high = sum(1 for a in alerts if a.severity == 'HIGH')
        medium = sum(1 for a in alerts if a.severity == 'MEDIUM')
        
        # Extract key concerns
        key_concerns = []
        sanctions_count = sum(1 for a in alerts if any('sanction' in r.lower() or 'prohibited' in r.lower() for r in a.reasons))
        cash_count = sum(1 for a in alerts if any('cash' in r.lower() for r in a.reasons))
        structuring_count = sum(1 for a in alerts if any('structur' in r.lower() for r in a.reasons))
        
        if sanctions_count > 0:
            key_concerns.append(f"{sanctions_count} transaction(s) involving prohibited/sanctioned jurisdictions")
        if cash_count > 0:
            key_concerns.append(f"{cash_count} suspicious cash deposit(s) identified")
        if structuring_count > 0:
            key_concerns.append(f"{structuring_count} potential structuring pattern(s) detected")
        
        # Build alert details
        alert_details = []
        for alert in alerts[:10]:  # Top 10 most severe
            txn = self.db.query(Transaction).filter(Transaction.id == alert.txn_id).first()
            alert_details.append({
                "alert_id": alert.id,
                "severity": alert.severity,
                "score": alert.score,
                "reasons": alert.reasons if isinstance(alert.reasons, list) else [],
                "transaction": {
                    "id": alert.txn_id,
                    "amount": txn.amount if txn else 0,
                    "currency": txn.currency if txn else 'GBP',
                    "country": txn.country_iso2 if txn else None,
                    "date": txn.txn_date.isoformat() if txn else None,
                    "narrative": txn.narrative if txn else None
                }
            })
        
        return {
            "summary": {
                "total_alerts": len(alerts),
                "critical_alerts": critical,
                "high_alerts": high,
                "medium_alerts": medium,
                "key_concerns": key_concerns
            },
            "alerts": alert_details
        }
    
    def identify_red_flags(
        self,
        bank_statements: List[Dict[str, Any]],
        claims: List[Dict[str, Any]],
        evidence_matches: List[Dict[str, Any]],
        flags: Dict[str, Any],
        transaction_review_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Identify red flags including Transaction Review alerts
        """
        red_flags = []
        
        # 1. Add Transaction Review CRITICAL and HIGH alerts as red flags
        tr_alerts = transaction_review_data.get('alerts', [])
        for alert in tr_alerts:
            if alert['severity'] in ['CRITICAL', 'HIGH']:
                red_flags.append({
                    "severity": alert['severity'],
                    "source": "TRANSACTION_REVIEW",
                    "flag": f"{alert['reasons'][0] if alert['reasons'] else 'AML alert'} - "
                           f"£{alert['transaction']['amount']:,.2f} on {alert['transaction']['date']}",
                    "transaction_ref": alert['transaction']['id'],
                    "alert_id": alert['alert_id'],
                    "details": alert['reasons']
                })
        
        # 2. Unmatched claims
        for i, evidence in enumerate(evidence_matches):
            if not evidence['verified']:
                claim = claims[i]
                red_flags.append({
                    "severity": "HIGH",
                    "source": "SoF_ANALYSIS",
                    "flag": f"No evidence found for claimed {claim['source_type']} of "
                           f"£{claim['expected_amount']:,.2f}",
                    "claim_id": claim['claim_id']
                })
        
        # 3. Large unexplained credits
        explained_amounts = set()
        for evidence in evidence_matches:
            for txn in evidence['transactions']:
                explained_amounts.add((txn['date'], txn['amount']))
        
        large_threshold = 10000  # £10k
        for txn in bank_statements:
            if txn.get('direction') == 'credit' and txn.get('amount', 0) > large_threshold:
                if (txn.get('date'), txn.get('amount')) not in explained_amounts:
                    red_flags.append({
                        "severity": "MEDIUM",
                        "source": "SoF_ANALYSIS",
                        "flag": f"Large unexplained credit of £{txn['amount']:,.2f} on {txn.get('date')} "
                               f"in {txn.get('account_id', 'account')}",
                        "transaction_ref": f"{txn.get('account_id')}-{txn.get('date')}"
                    })
        
        # 4. Cash deposits
        cash_keywords = ['cash', 'deposit', 'atm deposit']
        for txn in bank_statements:
            desc = txn.get('description', '').lower()
            if txn.get('direction') == 'credit' and any(kw in desc for kw in cash_keywords):
                if txn.get('amount', 0) > 5000:  # £5k threshold
                    red_flags.append({
                        "severity": "MEDIUM",
                        "source": "SoF_ANALYSIS",
                        "flag": f"Cash deposit of £{txn['amount']:,.2f} on {txn.get('date')}",
                        "transaction_ref": f"{txn.get('account_id')}-{txn.get('date')}"
                    })
        
        # 5. PEP flag
        if flags.get('pep'):
            red_flags.append({
                "severity": "HIGH",
                "source": "CLIENT_FLAGS",
                "flag": "Client is a Politically Exposed Person (PEP) - enhanced due diligence required"
            })
        
        # 6. High-risk jurisdictions
        if flags.get('high_risk_jurisdictions'):
            for txn in bank_statements:
                # Check if any transaction involves these jurisdictions
                # (would need more detailed transaction data)
                pass
        
        # Sort by severity
        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        red_flags.sort(key=lambda x: severity_order.get(x['severity'], 4))
        
        return red_flags
    
    def make_decision(
        self,
        risk_rating: str,
        claims: List[Dict[str, Any]],
        evidence_matches: List[Dict[str, Any]],
        funding_paths: List[Dict[str, Any]],
        red_flags: List[Dict[str, Any]],
        transaction_review_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make overall risk decision considering all factors
        """
        # Count verified claims
        verified_claims = sum(1 for e in evidence_matches if e['verified'])
        total_claims = len(claims)
        verification_rate = verified_claims / total_claims if total_claims > 0 else 0
        
        # Check funding coverage
        best_coverage = max([p['coverage'] for p in funding_paths], default=0)
        
        # Count red flags by severity
        critical_flags = sum(1 for f in red_flags if f['severity'] == 'CRITICAL')
        high_flags = sum(1 for f in red_flags if f['severity'] == 'HIGH')
        
        # Transaction Review integration - CRITICAL impact
        tr_summary = transaction_review_data.get('summary', {})
        tr_critical = tr_summary.get('critical_alerts', 0)
        tr_high = tr_summary.get('high_alerts', 0)
        
        # Base confidence score
        confidence = 50
        
        # Adjust for claim verification
        confidence += int(verification_rate * 30)
        
        # Adjust for funding coverage
        confidence += int(best_coverage * 0.2)
        
        # Penalize for red flags
        confidence -= (critical_flags * 30)
        confidence -= (high_flags * 15)
        
        # Transaction Review penalties - SEVERE impact
        if tr_critical > 0:
            confidence = min(confidence, 40)  # Cap at 40% if CRITICAL alerts exist
        if tr_high > 0:
            confidence -= (tr_high * 10)
        
        # Adjust for risk rating
        if risk_rating == 'high':
            confidence -= 10
        elif risk_rating == 'low':
            confidence += 10
        
        # Clamp confidence
        confidence = max(0, min(100, confidence))
        
        # Determine status
        if confidence >= 80 and critical_flags == 0 and tr_critical == 0:
            status = "sufficient"
        elif confidence >= 50 and critical_flags == 0 and tr_critical == 0:
            status = "borderline"
        else:
            status = "insufficient"
        
        # Build rationale
        rationale_parts = []
        
        # Claims verification
        if verification_rate == 1.0:
            rationale_parts.append(f"All {total_claims} SoF claim(s) verified by bank statement evidence.")
        elif verification_rate > 0:
            rationale_parts.append(
                f"{verified_claims}/{total_claims} SoF claims verified. "
                f"{total_claims - verified_claims} claim(s) lack supporting evidence."
            )
        else:
            rationale_parts.append("No claims could be verified against bank statements.")
        
        # Funding tracing
        if best_coverage >= 90:
            rationale_parts.append(f"Funding path traced with {best_coverage}% coverage to purchase amount.")
        elif best_coverage >= 70:
            rationale_parts.append(
                f"Partial funding trace achieved ({best_coverage}% coverage). "
                f"Some gaps in transaction flow."
            )
        else:
            rationale_parts.append("Unable to trace clear funding path from sources to purchase.")
        
        # Transaction Review integration - CRITICAL
        if tr_critical > 0 or tr_high > 0:
            rationale_parts.append(
                f"CRITICAL: Automated Transaction Review has identified {tr_critical} CRITICAL "
                f"and {tr_high} HIGH risk alerts that materially impact this assessment. "
                f"{', '.join(tr_summary.get('key_concerns', []))}. "
                f"These AML concerns must be resolved before proceeding."
            )
        
        # Red flags
        if critical_flags > 0:
            rationale_parts.append(
                f"{critical_flags} CRITICAL red flag(s) identified requiring immediate resolution."
            )
        elif high_flags > 0:
            rationale_parts.append(
                f"{high_flags} HIGH priority issue(s) require attention."
            )
        
        # Final statement
        if status == "sufficient":
            rationale_parts.append(
                "Documentation appears sufficient for a risk-based SoF assessment."
            )
        elif status == "borderline":
            rationale_parts.append(
                "Additional documentation recommended to strengthen SoF case."
            )
        else:
            rationale_parts.append(
                "Current evidence is insufficient to proceed. Material gaps must be addressed."
            )
        
        return {
            "status": status,
            "confidence": confidence,
            "rationale": " ".join(rationale_parts)
        }
    
    def generate_next_actions(
        self,
        risk_rating: str,
        claims: List[Dict[str, Any]],
        evidence_matches: List[Dict[str, Any]],
        red_flags: List[Dict[str, Any]],
        known_documents: List[str],
        transaction_review_data: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        Generate specific questions and document requests
        """
        questions = []
        documents = []
        
        # 1. Transaction Review issues - HIGHEST PRIORITY
        tr_alerts = transaction_review_data.get('alerts', [])
        critical_tr = [a for a in tr_alerts if a['severity'] == 'CRITICAL']
        high_tr = [a for a in tr_alerts if a['severity'] == 'HIGH']
        
        if critical_tr:
            for alert in critical_tr[:3]:  # Top 3 critical
                txn = alert['transaction']
                reason = alert['reasons'][0] if alert['reasons'] else "AML concern"
                questions.append(
                    f"URGENT: Transaction Review flagged £{txn['amount']:,.2f} transaction "
                    f"on {txn['date']} as CRITICAL - {reason}. Provide immediate explanation."
                )
            documents.append("Written explanation and supporting evidence for all CRITICAL flagged transactions")
        
        if high_tr:
            questions.append(
                f"{len(high_tr)} HIGH risk transaction(s) identified by AML monitoring. "
                f"Please review Transaction Review tab and provide explanations."
            )
        
        # 2. Unverified claims
        for i, evidence in enumerate(evidence_matches):
            if not evidence['verified']:
                claim = claims[i]
                questions.append(
                    f"No bank statement evidence found for your claimed {claim['source_type']} "
                    f"of £{claim['expected_amount']:,.2f}. Please provide supporting documentation."
                )
                
                # Source-specific documents
                source_lower = claim['source_type'].lower()
                if 'inheritance' in source_lower:
                    documents.append("Probate grant or letters of administration")
                    documents.append("Estate account summary showing distribution")
                elif 'property' in source_lower:
                    documents.append("Property completion statement")
                    documents.append("Solicitor's statement of account")
                elif 'loan' in source_lower:
                    documents.append("Loan offer letter and agreement")
                    documents.append("Evidence of loan drawdown")
                elif 'business' in source_lower:
                    documents.append("Share purchase agreement")
                    documents.append("Completion accounts")
                elif 'savings' in source_lower:
                    documents.append("Historical bank statements showing savings accumulation")
        
        # 3. Red flags from analysis
        for flag in red_flags:
            if flag['source'] == 'SoF_ANALYSIS':
                if 'unexplained credit' in flag['flag'].lower():
                    questions.append(f"Explain the {flag['flag']}")
                elif 'cash deposit' in flag['flag'].lower():
                    questions.append(f"Provide source documentation for {flag['flag']}")
        
        # 4. Risk-specific requirements
        if risk_rating == 'high':
            if 'Beneficial ownership details' not in documents:
                documents.append("Beneficial ownership details and structure chart")
            if 'Source of wealth statement' not in documents:
                documents.append("Source of wealth statement covering last 5 years")
        
        # 5. Standard documents if not already provided
        standard_docs = {
            "Bank statements": "Complete bank statements covering receipt and payment periods",
            "ID verification": "Certified copies of photo ID and proof of address"
        }
        
        for doc_type, doc_desc in standard_docs.items():
            if doc_type.lower() not in [d.lower() for d in known_documents]:
                documents.append(doc_desc)
        
        # Deduplicate
        questions = list(dict.fromkeys(questions))
        documents = list(dict.fromkeys(documents))
        
        return {
            "questions": questions,
            "documents": documents
        }
    
    def generate_file_note(
        self,
        client_info: Dict[str, Any],
        purchase: Dict[str, Any],
        claims: List[Dict[str, Any]],
        evidence_matches: List[Dict[str, Any]],
        funding_paths: List[Dict[str, Any]],
        red_flags: List[Dict[str, Any]],
        transaction_review_data: Dict[str, Any],
        outcome: Dict[str, Any],
        next_actions: Dict[str, List[str]]
    ) -> str:
        """
        Generate audit-ready file note
        """
        note_parts = []
        
        # Header
        note_parts.append(
            f"SOURCE OF FUNDS ASSESSMENT\n"
            f"Date: {datetime.utcnow().strftime('%d %B %Y')}\n"
            f"Matter: {self.matter_id}\n"
            f"Client: {client_info.get('client_name', 'N/A')}\n"
            f"Risk Rating: {client_info.get('client_risk_rating', 'N/A').upper()}\n"
            f"Purchase: {purchase.get('description', 'Business purchase')} - "
            f"£{purchase.get('amount', 0):,.2f} {purchase.get('currency', 'GBP')}\n"
        )
        
        # Claims summary
        note_parts.append("\nCLIENT'S SoF EXPLANATION:")
        for claim in claims:
            verified = "VERIFIED" if evidence_matches[claim['claim_id']-1]['verified'] else "NOT VERIFIED"
            note_parts.append(
                f"- {claim['source_type']}: £{claim['expected_amount']:,.2f} [{verified}]"
            )
        
        # Evidence
        note_parts.append("\nEVIDENCE REVIEW:")
        for evidence in evidence_matches:
            if evidence['verified']:
                txns = evidence['transactions']
                note_parts.append(
                    f"Claim {evidence['claim_id']}: Supported by {len(txns)} transaction(s). "
                    f"Match quality: {evidence['match_quality']}."
                )
            else:
                note_parts.append(
                    f"Claim {evidence['claim_id']}: No supporting evidence found in bank statements."
                )
        
        # Funding trace
        note_parts.append("\nFUNDING TRACE:")
        for path in funding_paths:
            note_parts.append(
                f"Path {path['path_id']}: {path['coverage']}% coverage. "
                f"{'PLAUSIBLE' if path['plausible'] else 'INCOMPLETE'}."
            )
            for step in path['steps'][:3]:
                note_parts.append(f"  • {step}")
        
        # Transaction Review - CRITICAL SECTION
        tr_summary = transaction_review_data.get('summary', {})
        if tr_summary.get('total_alerts', 0) > 0:
            note_parts.append("\nAUTOMATED TRANSACTION MONITORING (TRANSACTION REVIEW):")
            note_parts.append(
                f"System identified {tr_summary['total_alerts']} alert(s): "
                f"{tr_summary['critical_alerts']} CRITICAL, "
                f"{tr_summary['high_alerts']} HIGH, "
                f"{tr_summary['medium_alerts']} MEDIUM."
            )
            if tr_summary.get('key_concerns'):
                note_parts.append("Key concerns:")
                for concern in tr_summary['key_concerns']:
                    note_parts.append(f"  • {concern}")
            note_parts.append(
                "Full alert details available in Transaction Review tab. "
                "These findings materially impact the SoF assessment."
            )
        
        # Red flags
        if red_flags:
            note_parts.append(f"\nRED FLAGS IDENTIFIED ({len(red_flags)}):")
            for flag in red_flags[:5]:  # Top 5
                note_parts.append(f"  • [{flag['severity']}] {flag['flag']}")
        
        # Decision
        note_parts.append(f"\nASSESSMENT DECISION:")
        note_parts.append(
            f"Status: {outcome['status'].upper()} (Confidence: {outcome['confidence']}%)\n"
            f"Rationale: {outcome['rationale']}"
        )
        
        # Actions required
        if next_actions['questions']:
            note_parts.append("\nQUESTIONS FOR CLIENT:")
            for i, q in enumerate(next_actions['questions'][:5], 1):
                note_parts.append(f"{i}. {q}")
        
        if next_actions['documents']:
            note_parts.append("\nDOCUMENTS REQUIRED:")
            for i, d in enumerate(next_actions['documents'][:5], 1):
                note_parts.append(f"{i}. {d}")
        
        # Footer
        note_parts.append(
            f"\n---\n"
            f"This assessment was conducted using a risk-based approach in accordance with "
            f"UK AML regulations. The matter {'CAN' if outcome['status'] == 'sufficient' else 'CANNOT'} "
            f"proceed to completion in its current state."
        )
        
        return "\n".join(note_parts)

