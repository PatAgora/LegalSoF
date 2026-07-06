"""
Transaction Context Analyzer
Gathers comprehensive context from all matter sources for rule-based
contextual analysis (no AI/LLM involvement — deterministic rules only).
"""
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import json

class TransactionContextAnalyzer:
    """
    Analyzes transactions in context of all available matter information
    NO external API calls - all analysis is local
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def gather_matter_context(self, matter_id: int) -> Dict[str, Any]:
        """
        Gather all available context for a matter from all sources
        Returns comprehensive context dictionary
        """
        from app.models import (
            Matter, Document, QuestionnaireResponse, 
            FundsEvent, Transaction, KYCProfile, Entity
        )
        
        context = {
            "matter": {},
            "documents": [],
            "questionnaire": [],
            "funds_chain": [],
            "transactions": [],
            "kyc_profile": {},
            "entities": [],
            "summary": {}
        }
        
        # 1. Get Matter Details
        matter = self.db.query(Matter).filter(Matter.id == matter_id).first()
        if matter:
            context["matter"] = {
                "reference": matter.reference_number,
                "client": matter.client_name,
                "type": matter.transaction_type,
                "amount": matter.target_amount,
                "currency": matter.target_currency,
                "status": matter.status,
                "risk_rating": matter.risk_rating,
                "description": matter.description
            }
        
        # 2. Get Documents
        documents = self.db.query(Document).filter(
            Document.matter_id == matter_id
        ).all()
        
        for doc in documents:
            context["documents"].append({
                "type": doc.document_type,
                "name": doc.file_name,
                "status": doc.status,
                "notes": doc.notes,
                "uploaded": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "verified": doc.verified_at.isoformat() if doc.verified_at else None
            })
        
        # 3. Get Questionnaire Responses
        responses = self.db.query(QuestionnaireResponse).filter(
            QuestionnaireResponse.matter_id == matter_id
        ).all()
        
        for resp in responses:
            context["questionnaire"].append({
                "question": resp.question_text,
                "answer": resp.answer_text,
                "section": resp.section,
                "completed": resp.completed_at.isoformat() if resp.completed_at else None
            })
        
        # 4. Get Funds Chain
        funds_events = self.db.query(FundsEvent).filter(
            FundsEvent.matter_id == matter_id
        ).order_by(FundsEvent.sequence_order).all()
        
        for event in funds_events:
            context["funds_chain"].append({
                "sequence": event.sequence_order,
                "description": event.description,
                "amount": event.amount,
                "currency": event.currency,
                "event_date": event.event_date.isoformat() if event.event_date else None,
                "source": event.source,
                "destination": event.destination,
                "verified": event.verified
            })
        
        # 5. Get KYC Profile
        kyc = self.db.query(KYCProfile).filter(
            KYCProfile.matter_id == matter_id
        ).first()
        
        if kyc:
            context["kyc_profile"] = {
                "customer_id": kyc.customer_id,
                "risk_score": kyc.risk_score,
                "pep_status": kyc.pep_status,
                "sanctions_hit": kyc.sanctions_hit,
                "adverse_media": kyc.adverse_media,
                "occupation": kyc.occupation,
                "industry": kyc.industry,
                "countries": kyc.countries_of_operation,
                "last_review": kyc.last_review_date.isoformat() if kyc.last_review_date else None
            }
        
        # 6. Get Entities
        entities = self.db.query(Entity).filter(
            Entity.matter_id == matter_id
        ).all()
        
        for entity in entities:
            context["entities"].append({
                "name": entity.entity_name,
                "type": entity.entity_type,
                "role": entity.role,
                "jurisdiction": entity.jurisdiction,
                "ownership": entity.ownership_percentage,
                "verified": entity.verified
            })
        
        # 7. Get All Transactions for pattern analysis
        transactions = self.db.query(Transaction).filter(
            Transaction.matter_id == matter_id
        ).order_by(Transaction.txn_date).all()
        
        total_in = 0
        total_out = 0
        countries = set()
        
        for txn in transactions:
            context["transactions"].append({
                "id": txn.id,
                "date": txn.txn_date.isoformat(),
                "direction": txn.direction,
                "amount": txn.amount,
                "currency": txn.currency,
                "country": txn.country_iso2,
                "narrative": txn.narrative
            })
            
            if txn.direction == 'in':
                total_in += txn.amount
            else:
                total_out += txn.amount
            
            if txn.country_iso2:
                countries.add(txn.country_iso2)
        
        # 8. Generate Summary Statistics
        context["summary"] = {
            "total_documents": len(context["documents"]),
            "verified_documents": sum(1 for d in context["documents"] if d["verified"]),
            "questionnaire_completed": len([r for r in context["questionnaire"] if r["completed"]]),
            "total_questionnaire": len(context["questionnaire"]),
            "funds_chain_events": len(context["funds_chain"]),
            "verified_funds_events": sum(1 for f in context["funds_chain"] if f["verified"]),
            "total_transactions": len(context["transactions"]),
            "transaction_value_in": total_in,
            "transaction_value_out": total_out,
            "countries_involved": list(countries),
            "entities_count": len(context["entities"]),
            "verified_entities": sum(1 for e in context["entities"] if e["verified"])
        }
        
        return context
    
    def analyze_documentation_sufficiency(
        self, 
        context: Dict[str, Any],
        alert_severity: str,
        alert_reasons: List[str],
        transaction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze if provided documentation is sufficient for regulatory compliance
        Uses rule-based logic - NO external AI calls
        """
        
        # Initialize assessment
        assessment = {
            "overall_sufficiency": "INSUFFICIENT",
            "confidence_score": 0,
            "gaps_identified": [],
            "strengths_identified": [],
            "regulatory_concerns": [],
            "recommendations": [],
            "required_actions": []
        }
        
        summary = context.get("summary", {})
        docs = context.get("documents", [])
        kyc = context.get("kyc_profile", {})
        questionnaire = context.get("questionnaire", [])
        funds_chain = context.get("funds_chain", [])
        
        # Score components (0-100 each)
        doc_score = 0
        kyc_score = 0
        questionnaire_score = 0
        funds_score = 0
        verification_score = 0
        
        # 1. Document Completeness Assessment
        if summary.get("total_documents", 0) > 0:
            doc_completeness = summary.get("verified_documents", 0) / summary.get("total_documents", 1)
            doc_score = int(doc_completeness * 100)
            
            if doc_completeness >= 0.8:
                assessment["strengths_identified"].append(
                    f"Strong documentation: {summary['verified_documents']}/{summary['total_documents']} documents verified"
                )
            elif doc_completeness < 0.5:
                assessment["gaps_identified"].append(
                    f"Insufficient verified documents: Only {summary['verified_documents']}/{summary['total_documents']} verified"
                )
                assessment["required_actions"].append("Verify remaining uploaded documents")
        else:
            assessment["gaps_identified"].append("No supporting documentation uploaded")
            assessment["required_actions"].append("Request and upload source of funds documentation")
        
        # 2. KYC Profile Assessment
        if kyc:
            kyc_score = 40  # Base score for having KYC
            
            if kyc.get("risk_score"):
                if kyc["risk_score"] < 30:
                    kyc_score += 30
                    assessment["strengths_identified"].append(
                        f"Low KYC risk score: {kyc['risk_score']}/100"
                    )
                elif kyc["risk_score"] > 70:
                    kyc_score -= 20
                    assessment["regulatory_concerns"].append(
                        f"High KYC risk score: {kyc['risk_score']}/100 requires enhanced due diligence"
                    )
            
            if kyc.get("pep_status"):
                assessment["regulatory_concerns"].append(
                    "Customer identified as Politically Exposed Person (PEP) - enhanced due diligence mandatory"
                )
                assessment["required_actions"].append("Complete PEP due diligence questionnaire")
                kyc_score -= 20
            
            if kyc.get("sanctions_hit"):
                assessment["regulatory_concerns"].append(
                    "CRITICAL: Customer has sanctions screening hit - immediate escalation required"
                )
                assessment["required_actions"].append("Escalate to MLRO for sanctions review")
                kyc_score = 0
            
            if kyc.get("adverse_media"):
                assessment["regulatory_concerns"].append(
                    "Adverse media identified - requires detailed review and documentation"
                )
                assessment["required_actions"].append("Document adverse media review findings")
                kyc_score -= 10
            
            # Ensure non-negative
            kyc_score = max(0, kyc_score)
        else:
            assessment["gaps_identified"].append("No KYC profile completed")
            assessment["required_actions"].append("Complete customer KYC/CDD checks")
        
        # 3. Questionnaire Completeness
        if summary.get("total_questionnaire", 0) > 0:
            q_completeness = summary.get("questionnaire_completed", 0) / summary.get("total_questionnaire", 1)
            questionnaire_score = int(q_completeness * 100)
            
            if q_completeness >= 0.9:
                assessment["strengths_identified"].append(
                    f"Comprehensive questionnaire: {summary['questionnaire_completed']}/{summary['total_questionnaire']} sections completed"
                )
            elif q_completeness < 0.7:
                assessment["gaps_identified"].append(
                    f"Incomplete questionnaire: Only {summary['questionnaire_completed']}/{summary['total_questionnaire']} sections completed"
                )
                assessment["required_actions"].append("Complete remaining questionnaire sections")
        else:
            assessment["gaps_identified"].append("No source of funds questionnaire completed")
            assessment["required_actions"].append("Client to complete source of funds questionnaire")
        
        # 4. Funds Chain Verification
        if summary.get("funds_chain_events", 0) > 0:
            funds_completeness = summary.get("verified_funds_events", 0) / summary.get("funds_chain_events", 1)
            funds_score = int(funds_completeness * 100)
            
            if funds_completeness >= 0.8:
                assessment["strengths_identified"].append(
                    f"Well-documented funds chain: {summary['verified_funds_events']}/{summary['funds_chain_events']} events verified"
                )
            elif funds_completeness < 0.5:
                assessment["gaps_identified"].append(
                    f"Unverified funds chain: Only {summary['verified_funds_events']}/{summary['funds_chain_events']} events verified"
                )
                assessment["required_actions"].append("Verify and document all funds chain events")
        else:
            assessment["gaps_identified"].append("No funds chain documented")
            assessment["required_actions"].append("Document complete source and application of funds")
        
        # 5. Transaction-Specific Assessment
        if alert_severity == "CRITICAL":
            verification_score = 0  # Start at zero for critical
            
            # Check for prohibited countries
            if "Prohibited country" in " ".join(alert_reasons):
                assessment["regulatory_concerns"].append(
                    "CRITICAL: Transaction involves prohibited jurisdiction under sanctions - cannot proceed without regulatory approval"
                )
                assessment["required_actions"].append("Seek legal/regulatory guidance before processing")
            
            # Check for high-value transactions
            txn_amount = transaction.get("amount", 0)
            if txn_amount > 10000:
                if doc_score < 60:
                    assessment["gaps_identified"].append(
                        f"High-value transaction (£{txn_amount:,.2f}) requires enhanced documentation"
                    )
                    assessment["required_actions"].append("Obtain additional supporting documentation for large transaction")
        
        elif alert_severity == "HIGH":
            verification_score = 30  # Base score for high
            
            if doc_score >= 70:
                verification_score += 20
            
            if "High-risk" in " ".join(alert_reasons):
                assessment["regulatory_concerns"].append(
                    "HIGH: Transaction involves high-risk jurisdiction - enhanced due diligence required"
                )
                assessment["required_actions"].append("Complete enhanced due diligence checklist")
        
        else:  # MEDIUM or LOW
            verification_score = 50  # Base score for medium/low
            
            if doc_score >= 60 and questionnaire_score >= 70:
                verification_score += 30
        
        # 6. Calculate Overall Confidence Score
        weights = {
            "documents": 0.3,
            "kyc": 0.25,
            "questionnaire": 0.2,
            "funds_chain": 0.15,
            "verification": 0.1
        }
        
        assessment["confidence_score"] = int(
            doc_score * weights["documents"] +
            kyc_score * weights["kyc"] +
            questionnaire_score * weights["questionnaire"] +
            funds_score * weights["funds_chain"] +
            verification_score * weights["verification"]
        )
        
        # 7. Determine Overall Sufficiency
        if assessment["confidence_score"] >= 80:
            assessment["overall_sufficiency"] = "SUFFICIENT"
        elif assessment["confidence_score"] >= 60:
            assessment["overall_sufficiency"] = "PARTIALLY_SUFFICIENT"
        else:
            assessment["overall_sufficiency"] = "INSUFFICIENT"

        # 7b. HARD FAIL: a sanctions screening hit or a prohibited /
        # sanctioned-jurisdiction alert can never be outweighed by
        # good documentation elsewhere — force INSUFFICIENT regardless
        # of the weighted score.
        sanctions_blocked = bool(kyc.get("sanctions_hit")) or any(
            ("prohibited" in r.lower() or "sanction" in r.lower())
            for r in (alert_reasons or [])
        )
        if sanctions_blocked:
            assessment["overall_sufficiency"] = "INSUFFICIENT"
            assessment["regulatory_concerns"].append(
                "BLOCKING: Sanctions / prohibited-jurisdiction exposure forces an "
                "INSUFFICIENT verdict irrespective of documentation completeness."
            )
            if "Escalate to MLRO for sanctions review" not in assessment["required_actions"]:
                assessment["required_actions"].append("Escalate to MLRO for sanctions review")

        # 8. Add severity-specific recommendations
        if alert_severity == "CRITICAL":
            if assessment["overall_sufficiency"] != "SUFFICIENT":
                assessment["recommendations"].append(
                    "CRITICAL alert requires comprehensive documentation before proceeding. Current evidence is insufficient for regulatory defense."
                )
        elif alert_severity == "HIGH":
            if assessment["overall_sufficiency"] == "INSUFFICIENT":
                assessment["recommendations"].append(
                    "HIGH risk transaction requires enhanced documentation to meet regulatory standards."
                )
        
        # 9. Regulatory Scrutiny Assessment
        if assessment["overall_sufficiency"] == "SUFFICIENT":
            assessment["recommendations"].append(
                "Documentation appears sufficient to withstand regulatory scrutiny based on current standards."
            )
        elif assessment["overall_sufficiency"] == "PARTIALLY_SUFFICIENT":
            assessment["recommendations"].append(
                "Additional documentation recommended to strengthen case for potential regulatory review."
            )
        else:
            assessment["recommendations"].append(
                "Current documentation would likely be deemed insufficient under regulatory examination. Immediate action required."
            )
        
        return assessment
    
    def generate_context_aware_rationale(
        self,
        context: Dict[str, Any],
        alert_severity: str,
        alert_reasons: List[str],
        transaction: Dict[str, Any],
        assessment: Dict[str, Any]
    ) -> str:
        """
        Generate a comprehensive rule-based contextual analysis rationale
        considering all available context.
        100% local, deterministic rules - no AI and no external API calls
        """
        
        summary = context.get("summary", {})
        matter = context.get("matter", {})
        
        # Build rationale components
        rationale_parts = []
        
        # 1. Transaction Overview
        rationale_parts.append(
            f"This {alert_severity} risk transaction of {transaction.get('currency', 'GBP')} "
            f"{transaction.get('amount', 0):,.2f} from {transaction.get('country_iso2', 'Unknown')} "
            f"has been flagged for the following reasons: {', '.join(alert_reasons[:2])}."
        )
        
        # 2. Context Analysis
        if summary.get("total_documents", 0) > 0:
            rationale_parts.append(
                f"Available documentation: {summary['verified_documents']}/{summary['total_documents']} "
                f"documents verified."
            )
        else:
            rationale_parts.append("No supporting documentation currently on file.")
        
        if summary.get("questionnaire_completed", 0) > 0:
            rationale_parts.append(
                f"Client questionnaire: {summary['questionnaire_completed']}/{summary['total_questionnaire']} "
                f"sections completed."
            )
        
        if summary.get("funds_chain_events", 0) > 0:
            rationale_parts.append(
                f"Funds chain: {summary['verified_funds_events']}/{summary['funds_chain_events']} "
                f"events verified."
            )
        
        # 3. Sufficiency Assessment
        sufficiency_text = {
            "SUFFICIENT": "The available documentation appears SUFFICIENT to support this transaction and withstand regulatory scrutiny.",
            "PARTIALLY_SUFFICIENT": "The current documentation is PARTIALLY SUFFICIENT. Additional evidence would strengthen the compliance case.",
            "INSUFFICIENT": "The current documentation is INSUFFICIENT to adequately support this transaction under regulatory standards."
        }
        
        rationale_parts.append(sufficiency_text.get(assessment["overall_sufficiency"], ""))
        
        # 4. Key Concerns
        if assessment["regulatory_concerns"]:
            rationale_parts.append(
                f"Key concerns: {' '.join(assessment['regulatory_concerns'][:2])}"
            )
        
        # 5. Recommendation
        if alert_severity == "CRITICAL":
            rationale_parts.append(
                "CRITICAL RECOMMENDATION: Do not proceed without obtaining and verifying all required documentation. "
                "Escalate to MLRO/compliance officer for final approval."
            )
        elif alert_severity == "HIGH":
            rationale_parts.append(
                "RECOMMENDATION: Enhanced due diligence required before processing. "
                "Obtain additional supporting evidence and document decision rationale."
            )
        else:
            rationale_parts.append(
                "RECOMMENDATION: Complete standard verification procedures and document findings before proceeding."
            )
        
        return " ".join(rationale_parts)
    
    def generate_context_aware_outreach(
        self,
        context: Dict[str, Any],
        alert_severity: str,
        transaction: Dict[str, Any],
        assessment: Dict[str, Any]
    ) -> str:
        """
        Generate context-aware client outreach based on actual gaps
        100% local - no external API calls
        """
        
        matter = context.get("matter", {})
        customer_id = transaction.get("customer_id", "Client")
        txn_date = transaction.get("txn_date", "")
        amount = transaction.get("amount", 0)
        currency = transaction.get("currency", "GBP")
        
        # Build outreach template
        outreach_parts = []
        
        # 1. Opening
        outreach_parts.append(
            f"Dear {customer_id},\n\n"
            f"Regarding your {'incoming' if transaction.get('direction') == 'in' else 'outgoing'} "
            f"transaction of {currency} {amount:,.2f} dated {txn_date}, we are conducting our "
            f"standard compliance review and require additional information.\n\n"
        )
        
        # 2. Specific Document Requests (based on actual gaps)
        if assessment["gaps_identified"] or assessment["required_actions"]:
            outreach_parts.append("To complete our review, please provide:\n\n")
            
            doc_requests = []
            
            # Check what's actually missing
            summary = context.get("summary", {})
            
            if summary.get("total_documents", 0) == 0:
                doc_requests.append("• Source of funds documentation (bank statements, sale agreements, etc.)")
            elif summary.get("verified_documents", 0) < summary.get("total_documents", 0):
                doc_requests.append("• Verification of previously uploaded documents")
            
            if summary.get("questionnaire_completed", 0) < summary.get("total_questionnaire", 1):
                doc_requests.append("• Completion of outstanding source of funds questionnaire sections")
            
            if summary.get("funds_chain_events", 0) == 0:
                doc_requests.append("• Detailed breakdown of funds source and application")
            elif summary.get("verified_funds_events", 0) < summary.get("funds_chain_events", 0):
                doc_requests.append("• Supporting evidence for funds chain events")
            
            # Add severity-specific requests
            if alert_severity == "CRITICAL":
                doc_requests.append("• Enhanced due diligence documentation")
                doc_requests.append("• Beneficial ownership information")
                doc_requests.append("• Business relationship evidence")
            elif alert_severity == "HIGH":
                doc_requests.append("• Purpose of transaction statement")
                doc_requests.append("• Proof of business activity")
            
            # Add specific gaps from assessment
            for action in assessment["required_actions"][:3]:
                if "Request" in action or "Complete" in action or "Obtain" in action:
                    doc_requests.append(f"• {action}")
            
            outreach_parts.append("\n".join(doc_requests))
        
        # 3. Urgency Level
        if alert_severity == "CRITICAL":
            outreach_parts.append(
                "\n\nIMPORTANT: This transaction requires enhanced review before we can proceed. "
                "Please provide the requested information within 2 business days to avoid delays."
            )
        elif alert_severity == "HIGH":
            outreach_parts.append(
                "\n\nPlease provide the requested information within 5 business days to complete our review."
            )
        else:
            outreach_parts.append(
                "\n\nPlease provide the requested information at your earliest convenience."
            )
        
        # 4. Closing
        outreach_parts.append(
            "\n\nIf you have any questions, please don't hesitate to contact us. "
            "Thank you for your cooperation.\n\n"
            "Best regards,\n"
            "Compliance Team"
        )
        
        return "".join(outreach_parts)

