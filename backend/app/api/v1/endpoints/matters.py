"""
Matters API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.db.session import get_db
from app.models import Matter

router = APIRouter()


@router.get("/matters")
async def list_matters(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    risk_rating: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all matters with optional filtering
    """
    # Use sync DB helper for blocking operations
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    
    db_url = str(settings.DATABASE_URL).replace("sqlite+aiosqlite", "sqlite")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    sync_db = SessionLocal()
    
    try:
        query = sync_db.query(Matter)
        
        # Apply filters if provided
        if status:
            query = query.filter(Matter.status == status)
        if risk_rating:
            query = query.filter(Matter.risk_rating == risk_rating)
        
        # Get matters with pagination
        matters = query.offset(skip).limit(limit).all()
        
        # Convert to dict format
        result = []
        for matter in matters:
            result.append({
                "id": matter.id,
                "reference_number": matter.reference_number,
                "client_name": matter.client_name,
                "client_entity_name": matter.client_entity_name,
                "transaction_type": matter.transaction_type.value if matter.transaction_type else None,
                "target_business_name": matter.target_business_name,
                "target_amount": float(matter.target_amount) if matter.target_amount else None,
                "target_currency": "GBP",  # Default currency
                "transaction_date": matter.transaction_date.isoformat() if matter.transaction_date else None,
                "status": matter.status.value if matter.status else "draft",
                "risk_rating": matter.risk_rating.value if matter.risk_rating else "medium",
                "description": matter.description,
                "created_at": matter.created_at.isoformat() if matter.created_at else None,
                "updated_at": matter.updated_at.isoformat() if matter.updated_at else None,
            })
        
        return result
    
    finally:
        sync_db.close()


@router.get("/matters/{matter_id}")
async def get_matter(
    matter_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single matter by ID
    """
    # Use sync DB helper for blocking operations
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    
    db_url = str(settings.DATABASE_URL).replace("sqlite+aiosqlite", "sqlite")
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    sync_db = SessionLocal()
    
    try:
        matter = sync_db.query(Matter).filter(Matter.id == matter_id).first()
        
        if not matter:
            raise HTTPException(status_code=404, detail="Matter not found")
        
        return {
            "id": matter.id,
            "reference_number": matter.reference_number,
            "client_name": matter.client_name,
            "client_entity_name": matter.client_entity_name,
            "transaction_type": matter.transaction_type.value if matter.transaction_type else None,
            "target_business_name": matter.target_business_name,
            "target_amount": float(matter.target_amount) if matter.target_amount else None,
            "target_currency": "GBP",
            "transaction_date": matter.transaction_date.isoformat() if matter.transaction_date else None,
            "status": matter.status.value if matter.status else "draft",
            "risk_rating": matter.risk_rating.value if matter.risk_rating else "medium",
            "risk_rating_auto": matter.risk_rating_auto.value if matter.risk_rating_auto else None,
            "risk_rating_override": matter.risk_rating_override.value if matter.risk_rating_override else None,
            "risk_notes": matter.risk_notes,
            "description": matter.description,
            "created_at": matter.created_at.isoformat() if matter.created_at else None,
            "updated_at": matter.updated_at.isoformat() if matter.updated_at else None,
        }
    
    finally:
        sync_db.close()
