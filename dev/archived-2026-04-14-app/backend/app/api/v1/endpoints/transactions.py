"""
Transaction Review API endpoints - Full implementation with CSV upload and alert generation
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, text
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import date, datetime, timedelta, timezone
import io
from collections import defaultdict

from app.api.dependencies.auth import get_current_active_user, require_analyst, require_admin
from app.models.user import User
from app.db.session import get_db, get_sync_db
from app.models import (
    User, Matter, Transaction, TransactionAlert, CountryRisk,
    KYCProfile, TransactionConfig
)
from app.models.audit import AuditLog, AuditLogAction
from app.services.transaction_parser import TransactionCSVParser
from app.services.pdf_transaction_parser import PDFTransactionParser
from app.services.transaction_monitoring import TransactionMonitoringService

from pydantic import BaseModel, Field

router = APIRouter()

# Helper to parse dates in multiple formats
def parse_date_flexible(date_str: str):
    """Parse date string in multiple formats, returns date object or None"""
    if not date_str:
        return None
    # Try UK format first (dd/mm/yyyy) since that's our standard
    for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d %b %Y', '%d %B %Y']:
        try:
            return datetime.strptime(str(date_str).strip(), fmt).date()
        except:
            continue
    return None

class TransactionResponse(BaseModel):
    id: str
    matter_id: int
    txn_date: date
    customer_id: str
    direction: str
    amount: float
    currency: str
    base_amount: float
    country_iso2: Optional[str] = None
    channel: Optional[str] = None
    narrative: Optional[str] = None
    created_at: datetime
    # Account identification fields - use empty string as default to ensure serialization
    account_id: str = ""
    account_type: str = ""
    bank_name: str = ""
    sort_code: str = ""

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


# ==================== ENDPOINTS ====================

@router.post("/matters/{matter_id}/transactions/upload", response_model=UploadResponse)
async def upload_transactions(
    matter_id: int,
    file: UploadFile = File(...),
    customer_id: str = Form(...),
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db)
):
    """
    Upload CSV or PDF file with bank transactions and run AML checks.
    
    Supports:
    - CSV files with transaction data
    - PDF bank statements (automatically extracts transactions)
    
    File types accepted: .csv, .pdf
    
    Requires authenticated user with analyst role or above.
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
    limit: int = 1000,  # Increased to get all transactions
    offset: int = 0,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db)
):
    """
    Get all transactions for a matter
    
    NEW: Returns transactions from SoF assessment bank statements instead of separate upload.
    This allows Transaction Review to analyze the same bank statements used for SoF verification.
    """
    from app.models.assessment_storage import AssessmentStorage

    # Load SoF assessment storage from database
    row = db.query(AssessmentStorage).filter(AssessmentStorage.matter_id == matter_id).first()
    matter_storage = row.data if row and row.data else None
    if matter_storage and matter_storage.get('bank_statements'):
            bank_statements = matter_storage['bank_statements']
            
            # DEBUG: Log what's in the stored bank statements
            print(f"🔍 DEBUG /transactions - Found {len(bank_statements)} bank statements for matter {matter_id}")
            
            # Count unique accounts
            account_counts = {}
            for stmt in bank_statements:
                acc = stmt.get('account_id', 'MISSING')
                account_counts[acc] = account_counts.get(acc, 0) + 1
            
            print(f"   🔍 Unique accounts in storage: {len(account_counts)}")
            for acc, count in account_counts.items():
                print(f"      - {acc}: {count} transactions")
            
            if bank_statements:
                first_stmt = bank_statements[0]
                print(f"   🔍 First stmt keys: {list(first_stmt.keys())}")
                print(f"   🔍 First stmt account_id: {first_stmt.get('account_id', 'MISSING')}")
                print(f"   🔍 First stmt account_type: {first_stmt.get('account_type', 'MISSING')}")
                print(f"   🔍 First stmt bank_name: {first_stmt.get('bank_name', 'MISSING')}")
            
            # Convert bank statement transactions to Transaction response format
            transactions = []
            for idx, stmt in enumerate(bank_statements):
                # Convert date string to date object using flexible parsing
                txn_date_obj = parse_date_flexible(stmt.get('date', ''))
                if not txn_date_obj:
                    txn_date_obj = date.today()
                
                # Use account_id from statement, fallback to matter ID
                account_id = stmt.get('account_id') or stmt.get('customer_id') or f"MATTER-{matter_id}"
                
                # Infer channel from narrative if not explicitly provided
                narrative = stmt.get('description', '')
                channel = stmt.get('channel')
                if not channel and narrative:
                    narrative_upper = narrative.upper()
                    if any(term in narrative_upper for term in ['CASH DEPOSIT', 'CASH DEP', 'BRANCH DEPOSIT', 'COUNTER DEPOSIT']):
                        channel = 'cash_deposit'
                    elif any(term in narrative_upper for term in ['CASH WITHDRAWAL', 'CASH W/D', 'ATM WITHDRAWAL', 'ATM W/D', 'CASH - ATM', 'ATM CASH']):
                        channel = 'cash_withdrawal'
                    elif 'ATM' in narrative_upper:
                        channel = 'atm'
                    elif any(term in narrative_upper for term in ['CARD PAYMENT', 'CARD PURCHASE', 'DEBIT CARD']):
                        channel = 'card'
                    elif any(term in narrative_upper for term in ['FASTER PAYMENT', 'FP-', 'FPS']):
                        channel = 'faster_payment'
                    elif any(term in narrative_upper for term in ['BACS', 'DIRECT DEBIT', 'STANDING ORDER']):
                        channel = 'bacs'
                    elif any(term in narrative_upper for term in ['CHAPS', 'SWIFT', 'INTERNATIONAL', 'WIRE TRANSFER']):
                        channel = 'wire'
                
                transactions.append(TransactionResponse(
                    id=f"SOF-{matter_id}-{idx+1}",
                    matter_id=matter_id,
                    txn_date=txn_date_obj,
                    customer_id=account_id,  # Use actual account ID from statement
                    direction=stmt.get('direction', 'credit'),
                    amount=float(stmt.get('amount', 0)),
                    currency=stmt.get('currency', 'GBP'),
                    base_amount=float(stmt.get('amount', 0)),  # Assume same as amount for GBP
                    country_iso2=stmt.get('country_iso2') or 'GB',  # Default to GB for UK bank statements
                    channel=channel,  # Inferred from narrative if not provided
                    narrative=stmt.get('description', ''),
                    created_at=datetime.now(timezone.utc),
                    # Account identification - use empty string if not present
                    account_id=stmt.get('account_id') or account_id or '',
                    account_type=stmt.get('account_type') or '',
                    bank_name=stmt.get('bank_name') or '',
                    sort_code=stmt.get('sort_code') or ''
                ))
            
            # Log what we're returning
            response_accounts = {}
            for txn in transactions:
                acc = txn.account_id or txn.customer_id
                response_accounts[acc] = response_accounts.get(acc, 0) + 1
            print(f"   🔍 Returning {len(transactions)} transactions")
            print(f"   🔍 Accounts in response: {response_accounts}")
            
            return transactions[offset:offset+limit]
    
    # Fallback to empty list if no SoF data
    return []


@router.get("/matters/{matter_id}/transactions-debug")
async def get_transactions_debug(
    matter_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db)
):
    """
    Debug endpoint to see raw stored bank_statements data.
    """
    from app.models.assessment_storage import AssessmentStorage

    row = db.query(AssessmentStorage).filter(AssessmentStorage.matter_id == matter_id).first()
    matter_storage = row.data if row and row.data else None
    if not matter_storage:
        return {"error": f"No data for matter {matter_id}", "matter_id": matter_id}
    
    bank_statements = matter_storage.get('bank_statements', [])
    
    # Analyze unique accounts
    accounts_info = {}
    for txn in bank_statements:
        acc_id = txn.get('account_id', 'MISSING')
        if acc_id not in accounts_info:
            accounts_info[acc_id] = {
                'count': 0,
                'sample_txn': None,
                'bank_name': txn.get('bank_name'),
                'account_type': txn.get('account_type')
            }
        accounts_info[acc_id]['count'] += 1
        if accounts_info[acc_id]['sample_txn'] is None:
            accounts_info[acc_id]['sample_txn'] = {
                'date': txn.get('date'),
                'description': txn.get('description', '')[:100],
                'amount': txn.get('amount'),
                'direction': txn.get('direction'),
                'account_id': txn.get('account_id'),
                'bank_name': txn.get('bank_name'),
                'account_type': txn.get('account_type'),
                'sort_code': txn.get('sort_code')
            }
    
    return {
        "matter_id": matter_id,
        "total_transactions": len(bank_statements),
        "unique_accounts": len(accounts_info),
        "accounts": accounts_info,
        "first_3_transactions": bank_statements[:3] if bank_statements else []
    }


@router.get("/matters/{matter_id}/transaction-alerts", response_model=List[TransactionAlertResponse])
async def get_transaction_alerts(
    matter_id: int,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    include_context: bool = True,
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db)
):
    """
    Get transaction alerts for a matter with optional filters
    
    Now also generates alerts from SoF Assessment bank statements
    when they contain high-risk country data.
    """
    import json
    from pathlib import Path
    
    # Sanctioned/high-risk countries that should trigger CRITICAL alerts
    SANCTIONED_COUNTRIES = {'IR', 'KP', 'SY', 'CU', 'VE', 'RU', 'BY', 'AF'}
    HIGH_RISK_COUNTRIES = {'PK', 'MM', 'YE', 'LY', 'SO', 'SD', 'SS', 'IQ', 'LB', 'ZW'}
    
    # First, try to get alerts from database
    try:
        query = db.query(TransactionAlert).join(Transaction).filter(
            TransactionAlert.matter_id == matter_id
        )
        
        if severity:
            query = query.filter(TransactionAlert.severity == severity.upper())
        
        if status:
            query = query.filter(TransactionAlert.status == status)
        
        alerts = query.order_by(desc(TransactionAlert.created_at)).all()
    except Exception as e:
        print(f"⚠️ Database alert query failed: {e}")
        alerts = []
    
    # Convert database alerts to response format
    result = []
    db_txn_ids = set()
    
    for alert in alerts:
        txn = db.query(Transaction).filter(Transaction.id == alert.txn_id).first()
        db_txn_ids.add(alert.txn_id)
        
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
            'transaction_date': txn.txn_date if txn else None,
            'amount': txn.base_amount if txn else None,
            'currency': txn.currency if txn else None,
            'country_iso2': txn.country_iso2 if txn else None
        }
        
        result.append(TransactionAlertResponse(**alert_dict))
    
    # Now check SoF Assessment bank statements for high-risk countries
    from app.models.assessment_storage import AssessmentStorage as _AS
    _as_row = db.query(_AS).filter(_AS.matter_id == matter_id).first()
    _as_data = _as_row.data if _as_row and _as_row.data else None
    if _as_data:
        try:
            matter_storage = _as_data
            if matter_storage and matter_storage.get('bank_statements'):
                bank_statements = matter_storage['bank_statements']
                
                for idx, stmt in enumerate(bank_statements):
                    txn_id = f"SOF-{matter_id}-{idx+1}"
                    
                    # Skip if we already have a database alert for this transaction
                    if txn_id in db_txn_ids:
                        continue
                    
                    country = stmt.get('country_iso2', '').upper() if stmt.get('country_iso2') else None
                    
                    if country:
                        alert_data = None
                        
                        if country in SANCTIONED_COUNTRIES:
                            country_names = {
                                'IR': 'Iran', 'KP': 'North Korea', 'SY': 'Syria', 
                                'CU': 'Cuba', 'VE': 'Venezuela', 'RU': 'Russia',
                                'BY': 'Belarus', 'AF': 'Afghanistan'
                            }
                            alert_data = {
                                'id': 10000 + idx,  # Synthetic ID
                                'matter_id': matter_id,
                                'txn_id': txn_id,
                                'customer_id': stmt.get('account_id', f"MATTER-{matter_id}"),
                                'severity': 'CRITICAL',
                                'score': 95,
                                'reasons': [f'Transaction to/from sanctioned country: {country_names.get(country, country)}', 
                                           'UK/EU sanctions regulations apply', 
                                           'Immediate review and enhanced due diligence required'],
                                'rule_tags': ['SANCTIONED_COUNTRY', 'AML_HIGH_RISK', 'OFSI_SANCTIONS'],
                                'status': 'pending',
                                'created_at': datetime.now(timezone.utc),
                                'transaction_date': parse_date_flexible(stmt.get('date', '')),
                                'amount': float(stmt.get('amount', 0)),
                                'currency': stmt.get('currency', 'GBP'),
                                'country_iso2': country
                            }
                        elif country in HIGH_RISK_COUNTRIES:
                            alert_data = {
                                'id': 20000 + idx,
                                'matter_id': matter_id,
                                'txn_id': txn_id,
                                'customer_id': stmt.get('account_id', f"MATTER-{matter_id}"),
                                'severity': 'HIGH',
                                'score': 75,
                                'reasons': [f'Transaction to/from high-risk country: {country}', 
                                           'Enhanced due diligence recommended'],
                                'rule_tags': ['HIGH_RISK_COUNTRY', 'AML_RISK'],
                                'status': 'pending',
                                'created_at': datetime.now(timezone.utc),
                                'transaction_date': parse_date_flexible(stmt.get('date', '')),
                                'amount': float(stmt.get('amount', 0)),
                                'currency': stmt.get('currency', 'GBP'),
                                'country_iso2': country
                            }
                        
                        if alert_data:
                            # Apply filters
                            if severity and alert_data['severity'] != severity.upper():
                                continue
                            if status and alert_data['status'] != status:
                                continue
                            
                            result.append(TransactionAlertResponse(**alert_data))
                    
                    # CHECK FOR CASH DEPOSITS/WITHDRAWALS
                    narrative = stmt.get('description', '').upper()
                    # Ensure amount is a float for comparison
                    try:
                        amount = float(stmt.get('amount', 0))
                    except (ValueError, TypeError):
                        amount = 0.0
                    direction = stmt.get('direction', 'credit')
                    cash_threshold = 7500.0  # £7,500 threshold
                    
                    # Detect cash deposit
                    is_cash_deposit = any(term in narrative for term in [
                        'CASH DEPOSIT', 'CASH DEP', 'BRANCH DEPOSIT', 'COUNTER DEPOSIT', 'CASH PAID IN'
                    ])
                    
                    # Detect cash withdrawal - improved pattern matching
                    is_cash_withdrawal = any(term in narrative for term in [
                        'CASH WITHDRAWAL', 'CASH W/D', 'ATM WITHDRAWAL', 'CASH - ATM', 
                        'ATM CASH', 'WITHDRAWAL - ATM', 'ATM W/D'
                    ]) or ('CASH' in narrative and 'WITHDRAWAL' in narrative) or \
                       ('ATM' in narrative and direction in ('out', 'debit'))
                    
                    if is_cash_deposit and amount >= cash_threshold and direction in ('in', 'credit'):
                        excess = amount - cash_threshold
                        cash_alert = {
                            'id': 30000 + idx,
                            'matter_id': matter_id,
                            'txn_id': txn_id,
                            'customer_id': stmt.get('account_id', f"MATTER-{matter_id}"),
                            'severity': 'HIGH',
                            'score': 75,
                            'reasons': [
                                f'Large cash deposit exceeds £{cash_threshold:,.0f} threshold',
                                f'Amount: £{amount:,.2f} (excess: £{excess:,.2f})',
                                'Cash deposits over threshold require source verification'
                            ],
                            'rule_tags': ['LARGE_CASH_DEPOSIT', 'AML_RISK', 'SOURCE_OF_FUNDS'],
                            'status': 'pending',
                            'created_at': datetime.now(timezone.utc),
                            'transaction_date': parse_date_flexible(stmt.get('date', '')),
                            'amount': amount,
                            'currency': stmt.get('currency', 'GBP'),
                            'country_iso2': stmt.get('country_iso2', 'GB')
                        }
                        
                        # Apply filters
                        if not (severity and cash_alert['severity'] != severity.upper()):
                            if not (status and cash_alert['status'] != status):
                                result.append(TransactionAlertResponse(**cash_alert))
                    
                    elif is_cash_withdrawal and amount >= cash_threshold and direction in ('out', 'debit'):
                        excess = amount - cash_threshold
                        cash_alert = {
                            'id': 40000 + idx,
                            'matter_id': matter_id,
                            'txn_id': txn_id,
                            'customer_id': stmt.get('account_id', f"MATTER-{matter_id}"),
                            'severity': 'HIGH',
                            'score': 75,
                            'reasons': [
                                f'Large cash withdrawal exceeds £{cash_threshold:,.0f} threshold',
                                f'Amount: £{amount:,.2f} (excess: £{excess:,.2f})',
                                'Large cash withdrawals may indicate suspicious activity'
                            ],
                            'rule_tags': ['LARGE_CASH_WITHDRAWAL', 'AML_RISK'],
                            'status': 'pending',
                            'created_at': datetime.now(timezone.utc),
                            'transaction_date': parse_date_flexible(stmt.get('date', '')),
                            'amount': amount,
                            'currency': stmt.get('currency', 'GBP'),
                            'country_iso2': stmt.get('country_iso2', 'GB')
                        }
                        
                        # Apply filters
                        if not (severity and cash_alert['severity'] != severity.upper()):
                            if not (status and cash_alert['status'] != status):
                                result.append(TransactionAlertResponse(**cash_alert))
                            
        except Exception as e:
            print(f"⚠️ Error checking bank statements for alerts: {e}")
    
    # Sort by severity (CRITICAL first)
    severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    result.sort(key=lambda x: severity_order.get(x.severity, 4))
    
    return result


@router.post("/matters/{matter_id}/transaction-alerts/{alert_id}/review")
async def review_alert(
    matter_id: int,
    alert_id: int,
    status: str = Form(...),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(require_analyst),
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
    alert.reviewed_at = datetime.now(timezone.utc)

    # Audit log for alert review
    audit = AuditLog(
        matter_id=matter_id,
        user_id=current_user.id,
        action=AuditLogAction.ALERT_REVIEWED,
        entity_type="transaction_alert",
        entity_id=alert_id,
        description=f"Transaction alert #{alert_id} reviewed: {status}",
        details={
            "alert_id": alert_id,
            "new_status": status,
            "review_notes": notes,
            "txn_id": alert.txn_id,
            "severity": alert.severity,
        },
    )
    db.add(audit)

    db.commit()

    return {"success": True, "message": "Alert reviewed successfully"}


@router.post("/matters/{matter_id}/run-transaction-checks")
async def run_transaction_checks(
    matter_id: int,
    current_user: User = Depends(require_analyst),
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
    current_user: User = Depends(require_analyst),
    db: Session = Depends(get_sync_db)
):
    """
    Get dashboard statistics and charts for transaction review
    
    NEW: Uses bank statement data from SoF assessment for consistency
    """
    from app.models.assessment_storage import AssessmentStorage as _AS

    # Load bank statement transactions from database
    bank_transactions = []
    _as_row = db.query(_AS).filter(_AS.matter_id == matter_id).first()
    matter_storage = _as_row.data if _as_row and _as_row.data else None
    if matter_storage and matter_storage.get('bank_statements'):
            bank_statements = matter_storage['bank_statements']
            
            # Convert to transaction objects with necessary fields
            for idx, stmt in enumerate(bank_statements):
                bank_transactions.append({
                    'id': f"SOF-{matter_id}-{idx+1}",
                    'direction': stmt.get('direction', 'credit'),
                    'base_amount': float(stmt.get('amount', 0)),
                    'country_iso2': stmt.get('country_iso2') or 'GB',  # Default to GB for UK bank statements
                })
    
    # Get all alerts (still from database)
    alerts = db.query(TransactionAlert).filter(TransactionAlert.matter_id == matter_id).all()
    
    # Calculate stats using bank statement transactions
    total_transactions = len(bank_transactions)
    total_alerts = len(alerts)
    
    total_in = sum(t['base_amount'] for t in bank_transactions if t['direction'] in ('in', 'credit'))
    total_out = sum(t['base_amount'] for t in bank_transactions if t['direction'] in ('out', 'debit'))
    
    # High-risk transactions (with CRITICAL or HIGH alerts)
    high_risk_txn_ids = {a.txn_id for a in alerts if a.severity in ('CRITICAL', 'HIGH')}
    high_risk_value = sum(t['base_amount'] for t in bank_transactions if t['id'] in high_risk_txn_ids)
    
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
    if bank_transactions:
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
    # Note: Bank statements don't include country data, so this will be empty
    country_alerts = defaultdict(int)
    for alert in alerts:
        txn = next((t for t in bank_transactions if t['id'] == alert.txn_id), None)
        if txn and txn.get('country_iso2'):
            country_alerts[txn['country_iso2']] += 1
    
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
    current_user: User = Depends(require_analyst),
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
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_sync_db)
):
    """
    Update transaction monitoring configuration (admin only)
    """
    
    for key, value in updates.items():
        config_item = db.query(TransactionConfig).filter(TransactionConfig.key == key).first()
        if config_item:
            config_item.value = value
    
    db.commit()
    
    return {"success": True, "message": "Configuration updated"}

@router.get("/matters/{matter_id}/transaction-alerts/{alert_id}/context-analysis")
async def get_alert_context_analysis(
    matter_id: int,
    alert_id: int,
    current_user: User = Depends(require_analyst),
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
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_method": "LOCAL_RULE_BASED",
        "data_security": "ALL_DATA_REMAINS_ON_PLATFORM"
    }

