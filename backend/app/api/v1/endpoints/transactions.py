"""
Transaction Review API endpoints - integrated with Matter workflow
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import List, Optional
from datetime import date, datetime, timedelta
import csv
import io
import statistics
import json

from app.api.dependencies.auth import get_current_active_user
from app.db.session import get_db
from app.models import (
    User, Matter, Transaction, TransactionAlert, CountryRisk,
    KYCProfile, TransactionConfig
)

router = APIRouter()


# ==================== SCHEMAS ====================

from pydantic import BaseModel, Field

class TransactionCreate(BaseModel):
    id: str
    txn_date: date
    customer_id: str
    direction: str = Field(..., pattern="^(in|out)$")
    amount: float
    currency: str = "GBP"
    base_amount: float
    country_iso2: Optional[str] = None
    payer_sort_code: Optional[str] = None
    payee_sort_code: Optional[str] = None
    channel: Optional[str] = None
    narrative: Optional[str] = None


class TransactionResponse(BaseModel):
    id: str
    matter_id: int
    txn_date: date
    customer_id: str
    direction: str
    amount: float
    currency: str
    base_amount: float
    country_iso2: Optional[str]
    channel: Optional[str]
    narrative: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionAlertResponse(BaseModel):
    id: int
    matter_id: int
    txn_id: str
    severity: str
    score: int
    reasons: List[str]
    rule_tags: List[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionStatsResponse(BaseModel):
    total_transactions: int
    total_alerts: int
    critical_alerts: int
    high_alerts: int
    total_in: float
    total_out: float
    high_risk_value: float
    alert_rate: float


class KYCProfileCreate(BaseModel):
    customer_id: str
    expected_monthly_in: float = 0.0
    expected_monthly_out: float = 0.0
    nature_of_business: Optional[str] = None


class CountryRiskCreate(BaseModel):
    iso2: str = Field(..., min_length=2, max_length=2)
    risk_level: str = Field(..., pattern="^(LOW|MEDIUM|HIGH|HIGH_3RD|PROHIBITED)$")
    score: int = Field(..., ge=0, le=100)
    prohibited: bool = False


# ==================== ENDPOINTS ====================

@router.get("/matters/{matter_id}/transactions", response_model=List[TransactionResponse])
async def get_matter_transactions(
    matter_id: int,
    skip: int = 0,
    limit: int = 100,
    direction: Optional[str] = None,
    severity: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all transactions for a matter with optional filters"""
    query = select(Transaction).where(Transaction.matter_id == matter_id)
    
    if direction:
        query = query.where(Transaction.direction == direction)
    
    query = query.order_by(desc(Transaction.txn_date)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    transactions = result.scalars().all()
    
    return transactions


@router.get("/matters/{matter_id}/transactions/stats", response_model=TransactionStatsResponse)
async def get_transaction_stats(
    matter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get transaction statistics for a matter"""
    # Total transactions
    total_tx_query = select(func.count(Transaction.id)).where(Transaction.matter_id == matter_id)
    total_tx_result = await db.execute(total_tx_query)
    total_transactions = total_tx_result.scalar() or 0
    
    # Total alerts
    total_alerts_query = select(func.count(TransactionAlert.id)).where(TransactionAlert.matter_id == matter_id)
    total_alerts_result = await db.execute(total_alerts_query)
    total_alerts = total_alerts_result.scalar() or 0
    
    # Critical and high alerts
    critical_query = select(func.count(TransactionAlert.id)).where(
        and_(TransactionAlert.matter_id == matter_id, TransactionAlert.severity == "CRITICAL")
    )
    critical_result = await db.execute(critical_query)
    critical_alerts = critical_result.scalar() or 0
    
    high_query = select(func.count(TransactionAlert.id)).where(
        and_(TransactionAlert.matter_id == matter_id, TransactionAlert.severity == "HIGH")
    )
    high_result = await db.execute(high_query)
    high_alerts = high_result.scalar() or 0
    
    # Total in/out
    in_query = select(func.sum(Transaction.base_amount)).where(
        and_(Transaction.matter_id == matter_id, Transaction.direction == "in")
    )
    in_result = await db.execute(in_query)
    total_in = float(in_result.scalar() or 0)
    
    out_query = select(func.sum(Transaction.base_amount)).where(
        and_(Transaction.matter_id == matter_id, Transaction.direction == "out")
    )
    out_result = await db.execute(out_query)
    total_out = float(out_result.scalar() or 0)
    
    # High risk value (transactions to high-risk countries)
    hr_query = select(func.sum(Transaction.base_amount)).select_from(Transaction).join(
        CountryRisk, Transaction.country_iso2 == CountryRisk.iso2
    ).where(
        and_(
            Transaction.matter_id == matter_id,
            or_(
                CountryRisk.risk_level.in_(["HIGH", "HIGH_3RD"]),
                CountryRisk.prohibited == True
            )
        )
    )
    hr_result = await db.execute(hr_query)
    high_risk_value = float(hr_result.scalar() or 0)
    
    alert_rate = (total_alerts / total_transactions * 100) if total_transactions > 0 else 0
    
    return TransactionStatsResponse(
        total_transactions=total_transactions,
        total_alerts=total_alerts,
        critical_alerts=critical_alerts,
        high_alerts=high_alerts,
        total_in=total_in,
        total_out=total_out,
        high_risk_value=high_risk_value,
        alert_rate=alert_rate
    )


@router.get("/matters/{matter_id}/transaction-alerts", response_model=List[TransactionAlertResponse])
async def get_matter_transaction_alerts(
    matter_id: int,
    skip: int = 0,
    limit: int = 100,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all transaction alerts for a matter"""
    query = select(TransactionAlert).where(TransactionAlert.matter_id == matter_id)
    
    if severity:
        query = query.where(TransactionAlert.severity == severity.upper())
    
    if status:
        query = query.where(TransactionAlert.status == status)
    
    query = query.order_by(desc(TransactionAlert.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    return alerts


@router.post("/matters/{matter_id}/transactions/upload")
async def upload_transactions_csv(
    matter_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Upload transactions CSV file for a matter"""
    # Verify matter exists
    matter_result = await db.execute(select(Matter).where(Matter.id == matter_id))
    matter = matter_result.scalar_one_or_none()
    
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Read CSV
    contents = await file.read()
    csv_data = io.StringIO(contents.decode('utf-8'))
    reader = csv.DictReader(csv_data)
    
    transactions_added = 0
    errors = []
    
    required_fields = ['id', 'txn_date', 'customer_id', 'direction', 'amount', 'base_amount']
    
    for row_num, row in enumerate(reader, start=2):
        try:
            # Validate required fields
            missing = [f for f in required_fields if f not in row or not row[f]]
            if missing:
                errors.append(f"Row {row_num}: Missing fields: {', '.join(missing)}")
                continue
            
            # Parse date
            txn_date = datetime.strptime(row['txn_date'], '%Y-%m-%d').date()
            
            # Create transaction
            transaction = Transaction(
                id=row['id'],
                matter_id=matter_id,
                txn_date=txn_date,
                customer_id=row['customer_id'],
                direction=row['direction'].lower(),
                amount=float(row['amount']),
                currency=row.get('currency', 'GBP'),
                base_amount=float(row['base_amount']),
                country_iso2=row.get('country_iso2'),
                payer_sort_code=row.get('payer_sort_code'),
                payee_sort_code=row.get('payee_sort_code'),
                channel=row.get('channel'),
                narrative=row.get('narrative')
            )
            
            db.add(transaction)
            transactions_added += 1
            
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")
    
    await db.commit()
    
    # Run transaction scoring (simplified version - you can enhance this)
    # TODO: Implement full scoring logic from the original app
    
    return {
        "status": "success",
        "transactions_added": transactions_added,
        "errors": errors if errors else None,
        "message": f"Successfully uploaded {transactions_added} transactions"
    }


@router.get("/matters/{matter_id}/kyc-profile")
async def get_kyc_profile(
    matter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get KYC profile for a matter"""
    # Get matter to find customer_id
    matter_result = await db.execute(select(Matter).where(Matter.id == matter_id))
    matter = matter_result.scalar_one_or_none()
    
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Try to get KYC profile by matter_id
    kyc_result = await db.execute(
        select(KYCProfile).where(KYCProfile.matter_id == matter_id)
    )
    kyc_profile = kyc_result.scalar_one_or_none()
    
    return kyc_profile


@router.post("/matters/{matter_id}/kyc-profile")
async def create_or_update_kyc_profile(
    matter_id: int,
    kyc_data: KYCProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create or update KYC profile for a matter"""
    # Verify matter exists
    matter_result = await db.execute(select(Matter).where(Matter.id == matter_id))
    matter = matter_result.scalar_one_or_none()
    
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Check if profile exists
    kyc_result = await db.execute(
        select(KYCProfile).where(KYCProfile.customer_id == kyc_data.customer_id)
    )
    kyc_profile = kyc_result.scalar_one_or_none()
    
    if kyc_profile:
        # Update existing
        kyc_profile.expected_monthly_in = kyc_data.expected_monthly_in
        kyc_profile.expected_monthly_out = kyc_data.expected_monthly_out
        kyc_profile.nature_of_business = kyc_data.nature_of_business
    else:
        # Create new
        kyc_profile = KYCProfile(
            customer_id=kyc_data.customer_id,
            matter_id=matter_id,
            expected_monthly_in=kyc_data.expected_monthly_in,
            expected_monthly_out=kyc_data.expected_monthly_out,
            nature_of_business=kyc_data.nature_of_business
        )
        db.add(kyc_profile)
    
    await db.commit()
    await db.refresh(kyc_profile)
    
    return kyc_profile


@router.get("/country-risks", response_model=List[dict])
async def get_country_risks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all country risk configurations"""
    result = await db.execute(select(CountryRisk).order_by(CountryRisk.iso2))
    countries = result.scalars().all()
    
    return [
        {
            "iso2": c.iso2,
            "risk_level": c.risk_level,
            "score": c.score,
            "prohibited": c.prohibited
        }
        for c in countries
    ]


@router.post("/country-risks")
async def create_or_update_country_risk(
    country_data: CountryRiskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create or update country risk configuration"""
    # Check if exists
    result = await db.execute(
        select(CountryRisk).where(CountryRisk.iso2 == country_data.iso2.upper())
    )
    country = result.scalar_one_or_none()
    
    if country:
        # Update
        country.risk_level = country_data.risk_level
        country.score = country_data.score
        country.prohibited = country_data.prohibited
    else:
        # Create
        country = CountryRisk(
            iso2=country_data.iso2.upper(),
            risk_level=country_data.risk_level,
            score=country_data.score,
            prohibited=country_data.prohibited
        )
        db.add(country)
    
    await db.commit()
    await db.refresh(country)
    
    return country


@router.post("/matters/{matter_id}/transactions/score")
async def score_transactions(
    matter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Score all transactions for a matter and generate alerts.
    This is a simplified version - implement full logic from original app.
    """
    # Verify matter exists
    matter_result = await db.execute(select(Matter).where(Matter.id == matter_id))
    matter = matter_result.scalar_one_or_none()
    
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Get all transactions for this matter
    tx_result = await db.execute(
        select(Transaction).where(Transaction.matter_id == matter_id)
    )
    transactions = tx_result.scalars().all()
    
    alerts_created = 0
    
    # Simple scoring logic (enhance this with full rules from original app)
    for txn in transactions:
        reasons = []
        tags = []
        score = 0
        
        # Check if transaction already has alerts
        existing_alert = await db.execute(
            select(TransactionAlert).where(TransactionAlert.txn_id == txn.id)
        )
        if existing_alert.scalar_one_or_none():
            continue  # Skip if already scored
        
        # Rule 1: High-risk country
        if txn.country_iso2:
            country_result = await db.execute(
                select(CountryRisk).where(CountryRisk.iso2 == txn.country_iso2)
            )
            country = country_result.scalar_one_or_none()
            
            if country:
                if country.prohibited:
                    reasons.append(f"Prohibited country: {txn.country_iso2}")
                    tags.append("PROHIBITED_COUNTRY")
                    score += 100
                elif country.risk_level in ["HIGH", "HIGH_3RD"]:
                    reasons.append(f"High-risk country: {txn.country_iso2}")
                    tags.append("HIGH_RISK_COUNTRY")
                    score += country.score
        
        # Rule 2: Large amount (simplified - should check against median)
        if txn.base_amount > 10000:
            reasons.append(f"Large transaction: £{txn.base_amount:,.2f}")
            tags.append("LARGE_AMOUNT")
            score += 15
        
        # Rule 3: Cash transaction
        if txn.channel and txn.channel.lower() == 'cash':
            reasons.append("Cash transaction")
            tags.append("CASH_TRANSACTION")
            score += 20
        
        # Rule 4: Risky narrative terms
        if txn.narrative:
            risky_terms = ['crypto', 'cash', 'gift', 'consultancy', 'shell']
            narrative_lower = txn.narrative.lower()
            for term in risky_terms:
                if term in narrative_lower:
                    reasons.append(f"Risky term in narrative: {term}")
                    tags.append("NLP_RISK")
                    score += 10
                    break
        
        # Only create alert if there are reasons
        if reasons:
            # Determine severity
            if score >= 90 or "PROHIBITED_COUNTRY" in tags:
                severity = "CRITICAL"
            elif score >= 70:
                severity = "HIGH"
            elif score >= 50:
                severity = "MEDIUM"
            elif score >= 30:
                severity = "LOW"
            else:
                severity = "INFO"
            
            alert = TransactionAlert(
                matter_id=matter_id,
                txn_id=txn.id,
                customer_id=txn.customer_id,
                score=min(score, 100),
                severity=severity,
                reasons=reasons,
                rule_tags=list(set(tags)),
                status="open"
            )
            
            db.add(alert)
            alerts_created += 1
    
    await db.commit()
    
    return {
        "status": "success",
        "transactions_scored": len(transactions),
        "alerts_created": alerts_created
    }
