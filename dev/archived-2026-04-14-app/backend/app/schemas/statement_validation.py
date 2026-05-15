"""
Pydantic schemas for the Statement Authenticity Validation API.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ValidationFlagResponse(BaseModel):
    id: Optional[int] = None
    pipeline_stage: str
    code: str
    severity: str
    message: str
    details: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class ValidationTransactionResponse(BaseModel):
    id: Optional[int] = None
    date: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    direction: Optional[str] = None
    balance: Optional[float] = None
    transaction_type: Optional[str] = None


class StatementValidationResponse(BaseModel):
    id: Optional[int] = None
    matter_id: int
    filename: str
    file_hash_sha256: str
    file_size_bytes: int
    mime_type: Optional[str] = None
    bank_hint: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    authenticity_score: float
    status: str   # Trusted / Review / HighRisk
    identified_bank_template: Optional[str] = None
    file_integrity_result: Optional[Dict[str, Any]] = None
    template_match_result: Optional[Dict[str, Any]] = None
    extraction_result: Optional[Dict[str, Any]] = None
    math_check_result: Optional[Dict[str, Any]] = None
    anomaly_check_result: Optional[Dict[str, Any]] = None
    admin_override: bool = False
    admin_override_by: Optional[str] = None
    admin_override_rationale: Optional[str] = None
    admin_override_at: Optional[str] = None
    blocked: bool = False
    flags: List[ValidationFlagResponse] = []
    transactions_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AdminOverrideRequest(BaseModel):
    admin_user: str = Field(..., min_length=1, description="Username or ID of the admin performing override")
    rationale: str = Field(..., min_length=10, description="Reason for overriding the validation block")


class AdminOverrideResponse(BaseModel):
    validation_id: int
    previous_status: str
    admin_override: bool
    admin_override_by: str
    admin_override_rationale: str
    blocked: bool
    message: str


class ValidationSummaryResponse(BaseModel):
    """Summary of all validations for a matter, returned alongside the SoF assessment."""
    total_statements: int = 0
    trusted_count: int = 0
    review_count: int = 0
    high_risk_count: int = 0
    blocked_count: int = 0
    overridden_count: int = 0
    average_score: float = 0.0
    validations: List[StatementValidationResponse] = []
    all_flags: List[ValidationFlagResponse] = []
    has_blocking_issues: bool = False
