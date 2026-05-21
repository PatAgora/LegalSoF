#!/usr/bin/env python3
"""
Seed (or remove) demo data for testing — a varied set of matters,
demo reviewer users and assessment records so the dashboards, the
compliance views and the Root Cause Analysis page have data to show.

Everything created here is tagged so it can be removed cleanly:
  - demo matters have reference numbers starting "DEMO-"
  - demo reviewer users have emails ending "@agora.demo"

Usage (run where the database is reachable, e.g. `railway run`):
    python scripts/seed_demo_data.py            # create demo data
    python scripts/seed_demo_data.py --remove   # delete all demo data

Removal only touches the tagged rows (assessment storage for demo
matters, the demo matters, the demo users) and creates no audit,
notification or document-verification rows, so it leaves the rest of
the system untouched.
"""
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, ".")

from app.db.session import get_sync_session
from app.models import Matter, MatterStatus, RiskRating, TransactionType
from app.models.user import User, UserRole
from app.models.assessment_storage import AssessmentStorage
from app.core.security import get_password_hash

DEMO_REF_PREFIX = "DEMO-"
DEMO_EMAIL_DOMAIN = "@agora.demo"
NOW = datetime.now(timezone.utc).isoformat()


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).date().isoformat()


# --- per-claim action builders --------------------------------------------
def sufficient(by, rationale):
    return {"sufficient": {"by": by, "at": NOW, "rationale": rationale}}


def referred(by, reason):
    return {"compliance": {
        "state": "in_review", "sent_by": by, "sent_at": NOW, "reason": reason,
        "thread": [{"actor": "fee_earner", "action": "sent", "message": reason, "by": by, "at": NOW}],
    }}


def returned(by, reason, officer, response):
    return {"compliance": {
        "state": "returned", "sent_by": by, "sent_at": NOW, "reason": reason,
        "returned_by": officer, "returned_at": NOW, "return_rationale": response,
        "thread": [
            {"actor": "fee_earner", "action": "sent", "message": reason, "by": by, "at": NOW},
            {"actor": "compliance", "action": "returned", "message": response, "by": officer, "at": NOW},
        ],
    }}


def build_blob(claims_spec, item_actions=None, confirmed_by=None, purchase_amount=0):
    claims, evidence_matches, claim_actions = [], [], {}
    for i, c in enumerate(claims_spec):
        claims.append({
            "source_type": c["source_type"],
            "expected_amount": c["amount"],
            "expected_evidence": c.get("evidence", []),
        })
        evidence_matches.append({
            "document_verification": {"differences": c.get("differences", []), "verdict": "Verified"}
        })
        if c.get("action"):
            claim_actions[str(i)] = c["action"]
    blob = {
        "status": "completed",
        "last_updated": NOW,
        "uploaded_files": [],
        "bank_statements": [],
        "supporting_docs": [],
        "client_info": {"purchase": {"amount": purchase_amount, "currency": "GBP"}},
        "assessment_result": {
            "claims": claims,
            "evidence_matches": evidence_matches,
            "funding_paths": [],
            "red_flags": [],
            "outcome": {"status": "borderline", "rationale": "Demo matter seeded for testing."},
            "transaction_review_summary": {
                "total_alerts": 0, "critical_alerts": 0, "high_alerts": 0,
                "medium_alerts": 0, "key_concerns": [], "alerts": [],
            },
            "next_actions": {"questions": [], "documents": []},
            "file_note_summary": "Demo matter seeded for testing the dashboards and RCA page.",
        },
        "claim_actions": claim_actions,
        "item_actions": item_actions or {},
    }
    if confirmed_by:
        blob["sof_confirmed"] = {"by": confirmed_by, "at": NOW}
    return blob


# --- demo reviewers --------------------------------------------------------
REVIEWERS = [
    {"email": f"demo.reviewer.a{DEMO_EMAIL_DOMAIN}", "full_name": "Demo Reviewer A", "role": UserRole.ANALYST},
    {"email": f"demo.reviewer.b{DEMO_EMAIL_DOMAIN}", "full_name": "Demo Reviewer B", "role": UserRole.ANALYST},
    {"email": f"demo.reviewer.c{DEMO_EMAIL_DOMAIN}", "full_name": "Demo Reviewer C", "role": UserRole.ANALYST},
    {"email": f"demo.officer{DEMO_EMAIL_DOMAIN}", "full_name": "Demo Compliance Officer", "role": UserRole.ADMIN},
]
A, B, C, OFF = "Demo Reviewer A", "Demo Reviewer B", "Demo Reviewer C", "Demo Compliance Officer"

UNTRACED = [{"field": "untraced_funds", "amount": 25000, "date": _days_ago(120)}]
GAP = [{"field": "statement_gap", "gap_account": "40-11-22/5678", "gap_account_earliest": _days_ago(200)}]
DISCREPANCY = [{"field": "funds_discrepancy", "discrepancy_amount": 18000}]


# --- demo matters ----------------------------------------------------------
def demo_matters():
    return [
        dict(ref="DEMO-001", client="Hartley & Co (Demo)", txn=TransactionType.PROPERTY_PURCHASE,
             amount=620000, risk=RiskRating.MEDIUM, compliance_status="in_review",
             claims=[
                 dict(source_type="savings", amount=400000, differences=UNTRACED,
                      action=sufficient(A, "Statements reviewed; accumulation consistent with declared salary.")),
                 dict(source_type="gift", amount=220000,
                      action=referred(A, "Donor identity and the donor's own source of funds need compliance sign-off.")),
             ]),
        dict(ref="DEMO-002", client="Okonkwo Holdings (Demo)", txn=TransactionType.PROPERTY_PURCHASE,
             amount=850000, risk=RiskRating.HIGH, compliance_status="none",
             claims=[
                 dict(source_type="business_sale", amount=850000, differences=GAP,
                      action=sufficient(B, "Share purchase agreement and completion statement reviewed and consistent.")),
             ], confirmed_by=B),
        dict(ref="DEMO-003", client="Pemberton Estate (Demo)", txn=TransactionType.BUSINESS_PURCHASE,
             amount=300000, risk=RiskRating.MEDIUM, compliance_status="in_review",
             claims=[
                 dict(source_type="inheritance", amount=180000, differences=UNTRACED,
                      action=referred(B, "Grant of probate received but the distribution cannot be traced on the statements.")),
                 dict(source_type="investment", amount=120000,
                      action=sufficient(A, "Brokerage statement reviewed; disposal proceeds match the claim.")),
             ]),
        dict(ref="DEMO-004", client="Whitaker (Demo)", txn=TransactionType.PROPERTY_PURCHASE,
             amount=275000, risk=RiskRating.LOW, compliance_status="none",
             claims=[
                 dict(source_type="salary", amount=275000,
                      action=sufficient(A, "Payslips and salary credits reviewed; fully consistent.")),
             ], confirmed_by=A),
        dict(ref="DEMO-005", client="Castellan Group (Demo)", txn=TransactionType.PROPERTY_PURCHASE,
             amount=1200000, risk=RiskRating.HIGH, compliance_status="in_review",
             claims=[
                 dict(source_type="gift", amount=400000,
                      action=referred(C, "Large parental gift; donor source of funds requires compliance review.")),
                 dict(source_type="loan", amount=800000, differences=DISCREPANCY,
                      action=referred(B, "Private loan; lender's regulated status and source of funds unclear.")),
             ]),
        dict(ref="DEMO-006", client="Northbridge Ventures (Demo)", txn=TransactionType.INVESTMENT,
             amount=500000, risk=RiskRating.MEDIUM, compliance_status="returned",
             claims=[
                 dict(source_type="savings", amount=320000, differences=GAP,
                      action=sufficient(B, "Savings history reviewed; statement gap explained by the client.")),
                 dict(source_type="dividend", amount=180000,
                      action=sufficient(A, "Dividend vouchers and company accounts reviewed.")),
             ],
             item_actions={"transaction-review": returned(
                 B, "Several high-value transfers need a second look.",
                 OFF, "Transfers explained; obtain the counterparty confirmation on file.")}),
        dict(ref="DEMO-007", client="Aldgate Conveyancing (Demo)", txn=TransactionType.PROPERTY_PURCHASE,
             amount=460000, risk=RiskRating.HIGH, compliance_status="none",
             claims=[
                 dict(source_type="savings", amount=460000, differences=UNTRACED + GAP),
             ]),
        dict(ref="DEMO-008", client="Sterling Trade (Demo)", txn=TransactionType.BUSINESS_PURCHASE,
             amount=540000, risk=RiskRating.MEDIUM, compliance_status="none",
             claims=[
                 dict(source_type="business_sale", amount=540000,
                      action=sufficient(C, "Disposal documented; Companies House filing reviewed.")),
             ], confirmed_by=C),
    ]


def seed(db):
    # Demo reviewer users.
    user_by_name = {}
    for spec in REVIEWERS:
        existing = db.query(User).filter(User.email == spec["email"]).first()
        if existing:
            user_by_name[spec["full_name"]] = existing
            continue
        u = User(
            email=spec["email"], full_name=spec["full_name"], role=spec["role"],
            hashed_password=get_password_hash("DemoReviewer!2026"), is_active=True,
        )
        db.add(u)
        db.flush()
        user_by_name[spec["full_name"]] = u
        print(f"  + user {spec['email']}")
    creator = user_by_name[A]

    created = 0
    for m in demo_matters():
        if db.query(Matter).filter(Matter.reference_number == m["ref"]).first():
            print(f"  = matter {m['ref']} already exists, skipping")
            continue
        matter = Matter(
            reference_number=m["ref"],
            client_name=m["client"],
            transaction_type=m["txn"],
            target_amount=m["amount"],
            target_currency="GBP",
            status=MatterStatus.UNDER_REVIEW,
            risk_rating=m["risk"],
            compliance_status=m["compliance_status"],
            created_by_id=creator.id,
            description="Seeded demo matter — safe to delete.",
        )
        if m["compliance_status"] in ("in_review", "returned"):
            matter.compliance_submitted_at = datetime.now(timezone.utc)
            matter.compliance_submitted_by = B
            matter.compliance_reason = "Demo referral."
        if m["compliance_status"] == "returned":
            matter.compliance_reviewed_at = datetime.now(timezone.utc)
            matter.compliance_reviewed_by = OFF
            matter.compliance_review_outcome = "returned"
        db.add(matter)
        db.flush()
        blob = build_blob(
            m["claims"], item_actions=m.get("item_actions"),
            confirmed_by=m.get("confirmed_by"), purchase_amount=m["amount"],
        )
        db.add(AssessmentStorage(matter_id=matter.id, data=blob))
        created += 1
        print(f"  + matter {m['ref']} ({m['client']})")
    db.commit()
    print(f"\nDone — {created} demo matter(s) created.")


def remove(db):
    demo_matters_rows = db.query(Matter).filter(
        Matter.reference_number.like(f"{DEMO_REF_PREFIX}%")
    ).all()
    ids = [mt.id for mt in demo_matters_rows]
    if ids:
        db.query(AssessmentStorage).filter(AssessmentStorage.matter_id.in_(ids)).delete(
            synchronize_session=False
        )
        for mt in demo_matters_rows:
            db.delete(mt)
        print(f"  - removed {len(ids)} demo matter(s) and their assessment storage")
    demo_users = db.query(User).filter(User.email.like(f"%{DEMO_EMAIL_DOMAIN}")).all()
    for u in demo_users:
        db.delete(u)
    if demo_users:
        print(f"  - removed {len(demo_users)} demo user(s)")
    db.commit()
    print("\nDone — demo data removed.")


if __name__ == "__main__":
    session = get_sync_session()()
    try:
        if "--remove" in sys.argv:
            print("Removing demo data...")
            remove(session)
        else:
            print("Seeding demo data...")
            seed(session)
    finally:
        session.close()
