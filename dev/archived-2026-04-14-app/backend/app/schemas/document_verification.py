"""
Pydantic schemas for the Document Verification API.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class VerificationFlagResponse(BaseModel):
    id: Optional[int] = None
    pipeline_stage: str
    code: str
    severity: str
    message: str
    details: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


class DocumentVerificationResponse(BaseModel):
    id: Optional[int] = None
    matter_id: int
    filename: str
    file_hash: str
    file_category: Optional[str] = None
    disk_filename: Optional[str] = None
    authenticity_score: Optional[float] = 0.0
    verdict: str   # Verified / Suspicious / LikelyTampered / Pending
    verification_phase: Optional[str] = None
    verification_method: Optional[str] = None
    # Structural pipeline stage results
    metadata_result: Optional[Dict[str, Any]] = None
    structural_result: Optional[Dict[str, Any]] = None
    font_text_result: Optional[Dict[str, Any]] = None
    image_result: Optional[Dict[str, Any]] = None
    content_consistency_result: Optional[Dict[str, Any]] = None
    signature_result: Optional[Dict[str, Any]] = None
    annotation_form_result: Optional[Dict[str, Any]] = None
    hidden_content_result: Optional[Dict[str, Any]] = None
    # Statement pipeline stage results
    file_integrity_result: Optional[Dict[str, Any]] = None
    template_match_result: Optional[Dict[str, Any]] = None
    extraction_result: Optional[Dict[str, Any]] = None
    math_check_result: Optional[Dict[str, Any]] = None
    anomaly_check_result: Optional[Dict[str, Any]] = None
    # Statement metadata
    identified_bank_template: Optional[str] = None
    bank_hint: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    # Separate pipeline scores
    structural_pipeline_score: Optional[float] = None
    statement_pipeline_score: Optional[float] = None
    # Admin override
    admin_override: bool = False
    admin_override_by: Optional[str] = None
    admin_override_rationale: Optional[str] = None
    admin_override_at: Optional[str] = None
    blocked: bool = False
    flags: List[VerificationFlagResponse] = []
    transactions_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AdminOverrideRequest(BaseModel):
    admin_user: str = Field(..., min_length=1, description="Username or ID of the admin performing override")
    rationale: str = Field(..., min_length=10, description="Reason for overriding the verification block")


class AdminOverrideResponse(BaseModel):
    verification_id: int
    previous_verdict: str
    admin_override: bool
    admin_override_by: str
    admin_override_rationale: str
    blocked: bool
    message: str


class VerificationSummaryResponse(BaseModel):
    """Summary of all document verifications for a matter."""
    total_documents: int = 0
    verified_count: int = 0
    suspicious_count: int = 0
    likely_tampered_count: int = 0
    blocked_count: int = 0
    overridden_count: int = 0
    average_score: float = 0.0
    verifications: List[DocumentVerificationResponse] = []
    all_flags: List[VerificationFlagResponse] = []
    has_blocking_issues: bool = False
