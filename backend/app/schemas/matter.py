"""
Matter schemas for API requests and responses.
"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional
from decimal import Decimal

from app.models.matter import MatterStatus, RiskRating, TransactionType


class MatterBase(BaseModel):
    """Base matter schema."""
    client_name: str = Field(..., min_length=1, max_length=255)
    client_entity_name: Optional[str] = Field(None, max_length=255)
    transaction_type: TransactionType = TransactionType.BUSINESS_PURCHASE
    target_business_name: Optional[str] = Field(None, max_length=255)
    target_amount: Decimal = Field(..., gt=0, decimal_places=2)
    target_currency: str = Field(default="GBP", max_length=3)
    transaction_date: Optional[datetime] = None
    description: Optional[str] = None


class MatterCreate(MatterBase):
    """Schema for creating a new matter."""
    assigned_analyst_id: Optional[int] = None
    risk_rating: RiskRating = RiskRating.MEDIUM


class MatterUpdate(BaseModel):
    """Schema for updating a matter."""
    client_name: Optional[str] = Field(None, min_length=1, max_length=255)
    client_entity_name: Optional[str] = None
    transaction_type: Optional[TransactionType] = None
    target_business_name: Optional[str] = None
    target_amount: Optional[Decimal] = Field(None, gt=0)
    target_currency: Optional[str] = None
    transaction_date: Optional[datetime] = None
    status: Optional[MatterStatus] = None
    risk_rating: Optional[RiskRating] = None
    risk_rating_override: Optional[bool] = None
    risk_notes: Optional[str] = None
    assigned_analyst_id: Optional[int] = None
    description: Optional[str] = None


class MatterInDB(MatterBase):
    """Schema for matter in database."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    reference_number: str
    status: MatterStatus
    risk_rating: RiskRating
    risk_rating_auto: Optional[RiskRating] = None
    risk_rating_override: bool
    risk_notes: Optional[str] = None
    assigned_analyst_id: Optional[int] = None
    created_by_id: int
    portal_token: Optional[str] = None
    portal_token_expires: Optional[datetime] = None
    portal_accessed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MatterPublic(BaseModel):
    """Public matter schema."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    reference_number: str
    client_name: str
    transaction_type: TransactionType
    target_amount: Decimal
    target_currency: str
    status: MatterStatus
    risk_rating: RiskRating
    assigned_analyst_id: Optional[int] = None
    created_at: datetime


class MatterDetail(MatterInDB):
    """Detailed matter schema with relationships."""
    pass


class MatterStatsResponse(BaseModel):
    """Matter statistics response."""
    total_matters: int
    by_status: dict
    by_risk_rating: dict
    avg_completion_days: Optional[float] = None


class PortalLinkResponse(BaseModel):
    """Portal link generation response."""
    portal_url: str
    token: str
    expires_at: datetime
