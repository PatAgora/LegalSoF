"""
Statement Validation models for authenticity checking pipeline.

Tables:
- statement_validations: Core validation result per statement file
- statement_validation_flags: Individual flags/issues found during validation
- statement_validation_transactions: Extracted transactions from validated statements
"""
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, Boolean,
    Float, JSON, Enum as SQLEnum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class ValidationStatus(str, enum.Enum):
    """Validation outcome status."""
    TRUSTED = "Trusted"
    REVIEW = "Review"
    HIGH_RISK = "HighRisk"


class StatementValidation(Base):
    """Core validation result for an uploaded bank statement."""
    __tablename__ = "statement_validations"

    id = Column(Integer, primary_key=True, index=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)

    # File metadata
    filename = Column(String(500), nullable=False)
    file_hash_sha256 = Column(String(64), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100))

    # Validation inputs
    bank_hint = Column(String(200))
    period_start = Column(String(20))
    period_end = Column(String(20))

    # Pipeline results
    authenticity_score = Column(Float, nullable=False, default=0.0)
    status = Column(SQLEnum(ValidationStatus), nullable=False, default=ValidationStatus.REVIEW)
    identified_bank_template = Column(String(200))

    # Pipeline stage results (JSON blobs for flexibility)
    file_integrity_result = Column(JSON)
    template_match_result = Column(JSON)
    extraction_result = Column(JSON)
    math_check_result = Column(JSON)
    anomaly_check_result = Column(JSON)

    # Admin override
    admin_override = Column(Boolean, default=False)
    admin_override_by = Column(String(200))
    admin_override_rationale = Column(Text)
    admin_override_at = Column(DateTime(timezone=True))

    # Downstream blocking
    blocked = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    matter = relationship("Matter", backref="statement_validations")
    flags = relationship(
        "StatementValidationFlag",
        back_populates="validation",
        cascade="all, delete-orphan",
        order_by="StatementValidationFlag.severity.desc()"
    )
    transactions = relationship(
        "StatementValidationTransaction",
        back_populates="validation",
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        """Serialise to dict for API responses."""
        return {
            "id": self.id,
            "matter_id": self.matter_id,
            "filename": self.filename,
            "file_hash_sha256": self.file_hash_sha256,
            "file_size_bytes": self.file_size_bytes,
            "mime_type": self.mime_type,
            "bank_hint": self.bank_hint,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "authenticity_score": self.authenticity_score,
            "status": self.status.value if self.status else None,
            "identified_bank_template": self.identified_bank_template,
            "file_integrity_result": self.file_integrity_result,
            "template_match_result": self.template_match_result,
            "extraction_result": self.extraction_result,
            "math_check_result": self.math_check_result,
            "anomaly_check_result": self.anomaly_check_result,
            "admin_override": self.admin_override,
            "admin_override_by": self.admin_override_by,
            "admin_override_rationale": self.admin_override_rationale,
            "admin_override_at": self.admin_override_at.isoformat() if self.admin_override_at else None,
            "blocked": self.blocked,
            "flags": [f.to_dict() for f in self.flags] if self.flags else [],
            "transactions_count": len(self.transactions) if self.transactions else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<StatementValidation {self.id} matter={self.matter_id} status={self.status}>"


class FlagSeverity(str, enum.Enum):
    """Severity of a validation flag."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StatementValidationFlag(Base):
    """Individual flag raised during the validation pipeline."""
    __tablename__ = "statement_validation_flags"

    id = Column(Integer, primary_key=True, index=True)
    validation_id = Column(
        Integer,
        ForeignKey("statement_validations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    pipeline_stage = Column(String(50), nullable=False)  # e.g. file_integrity, template_match, etc.
    code = Column(String(100), nullable=False)            # machine-readable flag code
    severity = Column(SQLEnum(FlagSeverity), nullable=False, default=FlagSeverity.MEDIUM)
    message = Column(Text, nullable=False)
    details = Column(JSON)                                 # extra context

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    validation = relationship("StatementValidation", back_populates="flags")

    def to_dict(self):
        return {
            "id": self.id,
            "pipeline_stage": self.pipeline_stage,
            "code": self.code,
            "severity": self.severity.value if self.severity else None,
            "message": self.message,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Flag {self.code} [{self.severity}]>"


class StatementValidationTransaction(Base):
    """Transaction extracted during validation (optional, only if parsing succeeded)."""
    __tablename__ = "statement_validation_transactions"

    id = Column(Integer, primary_key=True, index=True)
    validation_id = Column(
        Integer,
        ForeignKey("statement_validations.id", ondelete="CASCADE"),
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
    validation = relationship("StatementValidation", back_populates="transactions")

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date,
            "description": self.description,
            "amount": self.amount,
            "direction": self.direction,
            "balance": self.balance,
            "transaction_type": self.transaction_type,
        }

    def __repr__(self):
        return f"<ValTxn {self.date} {self.direction} {self.amount}>"
