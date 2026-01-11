"""
Transaction Review API endpoints - Full implementation with CSV upload and alert generation
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, text
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import date, datetime, timedelta
import io
from collections import defaultdict

from app.api.dependencies.auth import get_current_active_user
from app.db.session import get_db
from app.models import (
    User, Matter, Transaction, TransactionAlert, CountryRisk,
    KYCProfile, TransactionConfig
)
from app.services.transaction_parser import TransactionCSVParser
from app.services.pdf_transaction_parser import PDFTransactionParser
from app.services.transaction_monitoring import TransactionMonitoringService

from pydantic import BaseModel, Field

router = APIRouter()


# ==================== SCHEMAS ====================

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
    customer_id: str
    severity: str
    score: int
    reasons: List[str]
    rule_tags: List[str]
    status: str
    created_at: datetime
    
    # Include transaction details for display
    transaction_date: Optional[date] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    country_iso2: Optional[str] = None

    class Config:
        from_attributes = True


class UploadResponse(BaseModel):
    success: bool
    message: str
    transactions_created: int
    alerts_generated: int


class DashboardResponse(BaseModel):
    stats: Dict
    alerts_by_severity: Dict[str, int]
    alerts_over_time: List[Dict]
    top_countries: List[Dict]


# ==================== HELPER FUNCTIONS ====================

def get_sync_db():
    """Get synchronous database session for blocking operations"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    
    db_url = str(settings.DATABASE_URL).replace("sqlite+aiosqlite", "sqlite")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== ENDPOINTS ====================

@router.post("/matters/{matter_id}/transactions/upload", response_model=UploadResponse)
async def upload_transactions(
    matter_id: int,
    file: UploadFile = File(...),
    customer_id: str = Form(...),
    db: Session = Depends(get_sync_db)
):
    """
    Upload CSV or PDF file with bank transactions and run AML checks.
    
    Supports:
    - CSV files with transaction data
    - PDF bank statements (automatically extracts transactions)
    
    File types accepted: .csv, .pdf
    
    Note: Authentication removed - accessible without login
    """
    # Verify matter exists
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Read file content
    file_content = await file.read()
    
    # Determine file type and parse accordingly
    filename = file.filename.lower() if file.filename else ""
    
    try:
        if filename.endswith('.pdf'):
            # Parse PDF bank statement
            pdf_parser = PDFTransactionParser()
            parsed_transactions = pdf_parser.parse_pdf(file_content, customer_id)
            
            if not parsed_transactions:
                raise HTTPException(
                    status_code=400, 
                    detail="No transactions found in PDF. Please ensure it's a valid bank statement."
                )
            
        elif filename.endswith('.csv'):
            # Parse CSV file
            csv_str = file_content.decode('utf-8')
            csv_parser = TransactionCSVParser()
            parsed_transactions = csv_parser.parse_csv(csv_str, customer_id)
            
        else:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file type. Please upload a CSV or PDF file."
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"File parsing error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    
    # Create transaction records
    transactions_created = 0
    for txn_data in parsed_transactions:
        # Check if transaction already exists
        existing = db.query(Transaction).filter(
            Transaction.id == txn_data['id'],
            Transaction.matter_id == matter_id
        ).first()
        
        if not existing:
            txn = Transaction(
                **txn_data,
                matter_id=matter_id
            )
            db.add(txn)
            transactions_created += 1
    
    db.commit()
    
    # Run AML checks
    monitoring_service = TransactionMonitoringService(db)
    alerts = monitoring_service.run_checks_for_matter(matter_id)
    
    file_type = "PDF" if filename.endswith('.pdf') else "CSV"
    
    return UploadResponse(
        success=True,
        message=f"Successfully processed {file_type} file: {transactions_created} transactions uploaded, {len(alerts)} alerts generated",
        transactions_created=transactions_created,
        alerts_generated=len(alerts)
    )


@router.get("/matters/{matter_id}/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    matter_id: int,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_sync_db)
):
    """
    Get all transactions for a matter
    """
    transactions = db.query(Transaction).filter(
        Transaction.matter_id == matter_id
    ).order_by(desc(Transaction.txn_date)).limit(limit).offset(offset).all()
    
    return transactions


@router.get("/matters/{matter_id}/transaction-alerts", response_model=List[TransactionAlertResponse])
async def get_transaction_alerts(
    matter_id: int,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    include_context: bool = True,
    db: Session = Depends(get_sync_db)
):
    """
    Get transaction alerts for a matter with optional filters
    Includes context-aware AI analysis by default (100% local, no external API calls)
    """
    from app.services.transaction_context_analyzer import TransactionContextAnalyzer
    
    query = db.query(TransactionAlert).join(Transaction).filter(
        TransactionAlert.matter_id == matter_id
    )
    
    if severity:
        query = query.filter(TransactionAlert.severity == severity.upper())
    
    if status:
        query = query.filter(TransactionAlert.status == status)
    
    alerts = query.order_by(desc(TransactionAlert.created_at)).all()
    
    # Initialize context analyzer (once for all alerts)
    context = None
    analyzer = None
    if include_context:
        analyzer = TransactionContextAnalyzer(db)
        context = analyzer.gather_matter_context(matter_id)
    
    # Enrich alerts with transaction data and context-aware AI
    result = []
    for alert in alerts:
        alert_dict = {
            'id': alert.id,
            'matter_id': alert.matter_id,
            'txn_id': alert.txn_id,
            'customer_id': alert.customer_id,
            'severity': alert.severity,
            'score': alert.score,
            'reasons': alert.reasons if isinstance(alert.reasons, list) else [],
            'rule_tags': alert.rule_tags if isinstance(alert.rule_tags, list) else [],
            'status': alert.status,
            'created_at': alert.created_at,
        }
        
        # Get transaction details
        txn = db.query(Transaction).filter(Transaction.id == alert.txn_id).first()
        if txn:
            alert_dict['transaction_date'] = txn.txn_date
            alert_dict['amount'] = txn.base_amount
            alert_dict['currency'] = txn.currency
            alert_dict['country_iso2'] = txn.country_iso2
            
            # Generate context-aware AI analysis (100% local)
            if include_context and analyzer and context:
                txn_dict = {
                    "id": txn.id,
                    "customer_id": txn.customer_id,
                    "txn_date": txn.txn_date.isoformat(),
                    "direction": txn.direction,
                    "amount": txn.amount,
                    "currency": txn.currency,
                    "country_iso2": txn.country_iso2,
                    "narrative": txn.narrative
                }
                
                # Analyze documentation sufficiency
                assessment = analyzer.analyze_documentation_sufficiency(
                    context=context,
                    alert_severity=alert.severity,
                    alert_reasons=alert.reasons if isinstance(alert.reasons, list) else [],
                    transaction=txn_dict
                )
                
                # Generate context-aware AI rationale
                alert_dict['ai_rationale'] = analyzer.generate_context_aware_rationale(
                    context=context,
                    alert_severity=alert.severity,
                    alert_reasons=alert.reasons if isinstance(alert.reasons, list) else [],
                    transaction=txn_dict,
                    assessment=assessment
                )
                
                # Generate context-aware AI outreach
                alert_dict['ai_outreach'] = analyzer.generate_context_aware_outreach(
                    context=context,
                    alert_severity=alert.severity,
                    transaction=txn_dict,
                    assessment=assessment
                )
        
        result.append(TransactionAlertResponse(**alert_dict))
    
    return result


@router.post("/matters/{matter_id}/transaction-alerts/{alert_id}/review")
async def review_alert(
    matter_id: int,
    alert_id: int,
    status: str = Form(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_sync_db)
):
    """
    Review and update alert status
    """
    alert = db.query(TransactionAlert).filter(
        TransactionAlert.id == alert_id,
        TransactionAlert.matter_id == matter_id
    ).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.status = status
    alert.review_notes = notes
    alert.reviewed_by = current_user.id
    alert.reviewed_at = datetime.utcnow()
    
    db.commit()
    
    return {"success": True, "message": "Alert reviewed successfully"}


@router.post("/matters/{matter_id}/run-transaction-checks")
async def run_transaction_checks(
    matter_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Manually trigger AML checks for all transactions in a matter
    """
    matter = db.query(Matter).filter(Matter.id == matter_id).first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    
    # Delete existing alerts to regenerate
    db.query(TransactionAlert).filter(TransactionAlert.matter_id == matter_id).delete()
    db.commit()
    
    # Run checks
    monitoring_service = TransactionMonitoringService(db)
    alerts = monitoring_service.run_checks_for_matter(matter_id)
    
    return {
        "success": True,
        "message": f"Generated {len(alerts)} alerts",
        "alerts_generated": len(alerts)
    }


@router.get("/matters/{matter_id}/transaction-dashboard", response_model=DashboardResponse)
async def get_transaction_dashboard(
    matter_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Get dashboard statistics and charts for transaction review
    """
    # Get all transactions
    transactions = db.query(Transaction).filter(Transaction.matter_id == matter_id).all()
    
    # Get all alerts
    alerts = db.query(TransactionAlert).filter(TransactionAlert.matter_id == matter_id).all()
    
    # Calculate stats
    total_transactions = len(transactions)
    total_alerts = len(alerts)
    
    total_in = sum(t.base_amount for t in transactions if t.direction == 'in')
    total_out = sum(t.base_amount for t in transactions if t.direction == 'out')
    
    # High-risk transactions (with CRITICAL or HIGH alerts)
    high_risk_txn_ids = {a.txn_id for a in alerts if a.severity in ('CRITICAL', 'HIGH')}
    high_risk_value = sum(t.base_amount for t in transactions if t.id in high_risk_txn_ids)
    
    # Alert counts by severity
    alerts_by_severity = defaultdict(int)
    for alert in alerts:
        alerts_by_severity[alert.severity] += 1
    
    critical_alerts = alerts_by_severity.get('CRITICAL', 0)
    high_alerts = alerts_by_severity.get('HIGH', 0)
    
    alert_rate = (total_alerts / total_transactions * 100) if total_transactions > 0 else 0
    
    stats = {
        'total_transactions': total_transactions,
        'total_alerts': total_alerts,
        'critical_alerts': critical_alerts,
        'high_alerts': high_alerts,
        'total_in': round(total_in, 2),
        'total_out': round(total_out, 2),
        'high_risk_value': round(high_risk_value, 2),
        'alert_rate': round(alert_rate, 1)
    }
    
    # Alerts over time (last 12 months)
    alerts_over_time = []
    if transactions:
        # Group by month
        monthly_alerts = defaultdict(int)
        for alert in alerts:
            month_key = alert.created_at.strftime('%Y-%m')
            monthly_alerts[month_key] += 1
        
        # Sort by month
        for month in sorted(monthly_alerts.keys()):
            alerts_over_time.append({
                'month': month,
                'count': monthly_alerts[month]
            })
    
    # Top countries by alert count
    country_alerts = defaultdict(int)
    for alert in alerts:
        txn = next((t for t in transactions if t.id == alert.txn_id), None)
        if txn and txn.country_iso2:
            country_alerts[txn.country_iso2] += 1
    
    top_countries = [
        {'country': country, 'alert_count': count}
        for country, count in sorted(country_alerts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    
    return DashboardResponse(
        stats=stats,
        alerts_by_severity=dict(alerts_by_severity),
        alerts_over_time=alerts_over_time,
        top_countries=top_countries
    )


@router.get("/transaction-config")
async def get_transaction_config(
    db: Session = Depends(get_sync_db)
):
    """
    Get transaction monitoring configuration
    """
    config_items = db.query(TransactionConfig).all()
    
    config = {}
    for item in config_items:
        config[item.key] = {
            'value': item.value,
            'type': item.value_type,
            'description': item.description
        }
    
    return config


@router.put("/transaction-config")
async def update_transaction_config(
    updates: Dict[str, str],
    db: Session = Depends(get_sync_db)
):
    """
    Update transaction monitoring configuration (admin only)
    """
    # TODO: Add admin role check
    
    for key, value in updates.items():
        config_item = db.query(TransactionConfig).filter(TransactionConfig.key == key).first()
        if config_item:
            config_item.value = value
    
    db.commit()
    
    return {"success": True, "message": "Configuration updated"}

@router.get("/matters/{matter_id}/transaction-alerts/{alert_id}/context-analysis")
def get_alert_context_analysis(
    matter_id: int,
    alert_id: int,
    db: Session = Depends(get_sync_db)
):
    """
    Get context-aware AI analysis for a specific alert
    Reviews ALL available documentation and provides regulatory sufficiency assessment
    
    100% LOCAL - No external API calls, no data leaves the platform
    """
    from app.models import TransactionAlert, Transaction
    from app.services.transaction_context_analyzer import TransactionContextAnalyzer
    
    # Get the alert
    alert = db.query(TransactionAlert).filter(
        TransactionAlert.id == alert_id,
        TransactionAlert.matter_id == matter_id
    ).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Get the transaction
    transaction = db.query(Transaction).filter(
        Transaction.id == alert.txn_id,
        Transaction.matter_id == matter_id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Initialize context analyzer
    analyzer = TransactionContextAnalyzer(db)
    
    # Gather comprehensive context from all sources
    context = analyzer.gather_matter_context(matter_id)
    
    # Build transaction dict
    txn_dict = {
        "id": transaction.id,
        "customer_id": transaction.customer_id,
        "txn_date": transaction.txn_date.isoformat(),
        "direction": transaction.direction,
        "amount": transaction.amount,
        "currency": transaction.currency,
        "country_iso2": transaction.country_iso2,
        "narrative": transaction.narrative
    }
    
    # Analyze documentation sufficiency
    assessment = analyzer.analyze_documentation_sufficiency(
        context=context,
        alert_severity=alert.severity,
        alert_reasons=alert.reasons,
        transaction=txn_dict
    )
    
    # Generate context-aware AI rationale
    ai_rationale = analyzer.generate_context_aware_rationale(
        context=context,
        alert_severity=alert.severity,
        alert_reasons=alert.reasons,
        transaction=txn_dict,
        assessment=assessment
    )
    
    # Generate context-aware AI outreach
    ai_outreach = analyzer.generate_context_aware_outreach(
        context=context,
        alert_severity=alert.severity,
        transaction=txn_dict,
        assessment=assessment
    )
    
    # Return comprehensive analysis
    return {
        "alert_id": alert_id,
        "transaction_id": transaction.id,
        "severity": alert.severity,
        "score": alert.score,
        "context_summary": context["summary"],
        "assessment": assessment,
        "ai_rationale": ai_rationale,
        "ai_outreach": ai_outreach,
        "generated_at": datetime.utcnow().isoformat(),
        "analysis_method": "LOCAL_RULE_BASED",
        "data_security": "ALL_DATA_REMAINS_ON_PLATFORM"
    }

