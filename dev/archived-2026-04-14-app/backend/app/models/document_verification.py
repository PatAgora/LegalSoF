"""
Document Verification models for the document tampering detection pipeline.

Tables:
- document_verifications: Core verification result per uploaded document
- document_verification_flags: Individual flags/issues found during verification
"""
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Boolean,
    Float, JSON, LargeBinary, Enum as SQLEnum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class VerificationVerdict(str, enum.Enum):
    """Verification outcome verdict."""
    VERIFIED = "Verified"
    SUSPICIOUS = "Suspicious"
    LIKELY_TAMPERED = "LikelyTampered"
    PENDING = "Pending"


class DocumentVerification(Base):
    """Core verification result for an uploaded document."""
    __tablename__ = "document_verifications"

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)

    # File metadata
    filename = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=False)
    file_category = Column(String(100))  # bank_statement, supporting_doc, etc.
    disk_filename = Column(String(500), nullable=True)  # filename on disk in /app/uploads/{matter_id}/
    # Raw file bytes — kept in the database so documents survive a
    # container redeploy (the upload directory on the host is
    # ephemeral). The serve endpoint falls back to this when the
    # on-disk copy is missing.
    file_bytes = Column(LargeBinary, nullable=True)

    # Pipeline results
    authenticity_score = Column(Float, nullable=False, default=0.0)
    verdict = Column(SQLEnum(VerificationVerdict), nullable=False, default=VerificationVerdict.SUSPICIOUS)

    # Verification phase and method
    verification_phase = Column(String(30), default="complete")  # structural_only, statement_only, complete
    verification_method = Column(String(100))  # Human-readable description

    # Structural pipeline stage results (JSON blobs)
    metadata_result = Column(JSON)
    structural_result = Column(JSON)
    font_text_result = Column(JSON)
    image_result = Column(JSON)
    content_consistency_result = Column(JSON)
    signature_result = Column(JSON)
    annotation_form_result = Column(JSON)
    hidden_content_result = Column(JSON)

    # Statement validation pipeline stage results (JSON blobs)
    file_integrity_result = Column(JSON)
    template_match_result = Column(JSON)
    extraction_result = Column(JSON)
    math_check_result = Column(JSON)
    anomaly_check_result = Column(JSON)

    # Statement metadata
    identified_bank_template = Column(String(200))
    bank_hint = Column(String(200))
    period_start = Column(String(20))
    period_end = Column(String(20))

    # Separate pipeline scores for combining
    structural_pipeline_score = Column(Float)
    statement_pipeline_score = Column(Float)

    # Admin override
    admin_override = Column(Boolean, default=False)
    admin_override_by = Column(String(200))
    admin_override_rationale = Column(Text)
    admin_override_at = Column(DateTime(timezone=True))

    # Two-reviewer ("4-eyes") override workflow. propose-* gets filled
    # when an analyst proposes lifting the block; approve-* gets filled
    # when a DIFFERENT admin approves. Once approve-* is set, the regular
    # admin_override_* fields above are populated too and `blocked` is
    # cleared.
    override_proposed_by = Column(String(200))
    override_proposed_at = Column(DateTime(timezone=True))
    override_proposed_rationale = Column(Text)

    # Downstream blocking
    blocked = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    matter = relationship("Matter", backref="document_verifications")
    flags = relationship(
        "DocumentVerificationFlag",
        back_populates="verification",
        cascade="all, delete-orphan",
        order_by="DocumentVerificationFlag.severity.desc()"
    )
    transactions = relationship(
        "DocumentVerificationTransaction",
        back_populates="verification",
        cascade="all, delete-orphan",
        order_by="DocumentVerificationTransaction.id"
    )

    def to_dict(self):
        """Serialise to dict for API responses."""
        return {
            "id": self.id,
            "matter_id": self.matter_id,
            "filename": self.filename,
            "file_hash": self.file_hash,
            "file_category": self.file_category,
            "disk_filename": self.disk_filename,
            "authenticity_score": self.authenticity_score,
            "verdict": self.verdict.value if self.verdict else None,
            "verification_phase": self.verification_phase,
            "verification_method": self.verification_method,
            # Structural pipeline stage results
            "metadata_result": self.metadata_result,
            "structural_result": self.structural_result,
            "font_text_result": self.font_text_result,
            "image_result": self.image_result,
            "content_consistency_result": self.content_consistency_result,
            "signature_result": self.signature_result,
            "annotation_form_result": self.annotation_form_result,
            "hidden_content_result": self.hidden_content_result,
            # Statement pipeline stage results
            "file_integrity_result": self.file_integrity_result,
            "template_match_result": self.template_match_result,
            "extraction_result": self.extraction_result,
            "math_check_result": self.math_check_result,
            "anomaly_check_result": self.anomaly_check_result,
            # Statement metadata
            "identified_bank_template": self.identified_bank_template,
            "bank_hint": self.bank_hint,
            "period_start": self.period_start,
            "period_end": self.period_end,
            # Separate pipeline scores
            "structural_pipeline_score": self.structural_pipeline_score,
            "statement_pipeline_score": self.statement_pipeline_score,
            # Admin override
            "admin_override": self.admin_override,
            "admin_override_by": self.admin_override_by,
            "admin_override_rationale": self.admin_override_rationale,
            "admin_override_at": self.admin_override_at.isoformat() if self.admin_override_at else None,
            "override_proposed_by": self.override_proposed_by,
            "override_proposed_at": self.override_proposed_at.isoformat() if self.override_proposed_at else None,
            "override_proposed_rationale": self.override_proposed_rationale,
            "blocked": self.blocked,
            "flags": [f.to_dict() for f in self.flags] if self.flags else [],
            "transactions_count": len(self.transactions) if self.transactions else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<DocumentVerification {self.id} matter={self.matter_id} verdict={self.verdict}>"


class DocumentVerificationFlag(Base):
    """Individual flag raised during the document verification pipeline."""
    __tablename__ = "document_verification_flags"

    id = Column(Integer, primary_key=True, index=True)
    verification_id = Column(
        Integer,
        ForeignKey("document_verifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    pipeline_stage = Column(String(50), nullable=False)  # metadata, structural, font_text, etc.
    code = Column(String(100), nullable=False)             # machine-readable flag code
    severity = Column(String(20), nullable=False, default="medium")  # info, low, medium, high, critical
    message = Column(Text, nullable=False)
    details = Column(JSON)                                 # extra context

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    verification = relationship("DocumentVerification", back_populates="flags")

    def to_dict(self):
        return {
            "id": self.id,
            "pipeline_stage": self.pipeline_stage,
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<DocVerFlag {self.code} [{self.severity}]>"


class DocumentVerificationTransaction(Base):
    """Extracted transaction from a verified bank statement."""
    __tablename__ = "document_verification_transactions"

    id = Column(Integer, primary_key=True, index=True)
    verification_id = Column(
        Integer,
        ForeignKey("document_verifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    date = Column(String(20))
    description = Column(Text)
    amount = Column(Float)
    direction = Column(String(10))  # credit / debit
    balance = Column(Float)
    transaction_type = Column(String(50))
    raw_row = Column(JSON)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    verification = relationship("DocumentVerification", back_populates="transactions")

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "description": self.description,
            "amount": self.amount,
            "direction": self.direction,
            "balance": self.balance,
            "transaction_type": self.transaction_type,
            "raw_row": self.raw_row,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<DocVerTxn {self.id} {self.date} {self.amount}>"
