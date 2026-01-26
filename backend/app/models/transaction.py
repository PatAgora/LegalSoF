from sqlalchemy import Column, Integer, String, Float, Date, Text, ForeignKey, JSON, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class Transaction(Base):
    """Transaction record for AML monitoring"""
    __tablename__ = "transactions"

    id = Column(String(255), primary_key=True)  # Transaction ID from bank
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)
    txn_date = Column(Date, nullable=False, index=True)
    customer_id = Column(String(255), nullable=False, index=True)  # Links transactions to customer/matter
    direction = Column(String(10), nullable=False)  # 'in' or 'out'
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="GBP")
    base_amount = Column(Float, nullable=False)  # Amount in base currency (GBP)
    country_iso2 = Column(String(2), index=True)  # Country code
    payer_sort_code = Column(String(20))
    payee_sort_code = Column(String(20))
    channel = Column(String(50))  # 'cash', 'transfer', 'card', etc.
    narrative = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    matter = relationship("Matter", back_populates="transactions")
    alerts = relationship("TransactionAlert", back_populates="transaction", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Transaction {self.id} {self.direction} £{self.base_amount} on {self.txn_date}>"


class TransactionAlert(Base):
    """Alert generated from transaction monitoring rules"""
    __tablename__ = "transaction_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)
    txn_id = Column(String(255), ForeignKey("transactions.id"), nullable=False, index=True)
    customer_id = Column(String(255), nullable=False, index=True)
    score = Column(Integer, nullable=False)
    severity = Column(String(20), nullable=False, index=True)  # 'INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    reasons = Column(JSON, nullable=False)  # List of reason strings
    rule_tags = Column(JSON, nullable=False)  # List of triggered rule tags
    config_version = Column(Integer)
    status = Column(String(20), default="open")  # 'open', 'reviewed', 'resolved', 'false_positive'
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    reviewed_at = Column(DateTime(timezone=True))
    review_notes = Column(Text)
    ai_rationale = Column(Text)  # AI-generated explanation of why this alert was triggered
    ai_outreach = Column(Text)  # AI-generated suggested customer outreach message
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    matter = relationship("Matter", back_populates="transaction_alerts")
    transaction = relationship("Transaction", back_populates="alerts")
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    def __repr__(self):
        return f"<TransactionAlert {self.id} {self.severity} score={self.score}>"


class CountryRisk(Base):
    """Reference data for country risk levels"""
    __tablename__ = "ref_country_risk"

    iso2 = Column(String(2), primary_key=True)  # ISO 3166-1 alpha-2 code
    risk_level = Column(String(20), nullable=False)  # 'LOW', 'MEDIUM', 'HIGH', 'HIGH_3RD', 'PROHIBITED'
    score = Column(Integer, nullable=False)
    prohibited = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<CountryRisk {self.iso2} {self.risk_level}>"


class KYCProfile(Base):
    """KYC profile for expected transaction volumes"""
    __tablename__ = "kyc_profiles"

    customer_id = Column(String(255), primary_key=True)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)
    expected_monthly_in = Column(Float, default=0.0)
    expected_monthly_out = Column(Float, default=0.0)
    nature_of_business = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    matter = relationship("Matter", back_populates="kyc_profile")

    def __repr__(self):
        return f"<KYCProfile {self.customer_id} in=£{self.expected_monthly_in} out=£{self.expected_monthly_out}>"


class TransactionConfig(Base):
    """Configuration for transaction monitoring rules"""
    __tablename__ = "transaction_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text)
    value_type = Column(String(20), default="string")  # 'string', 'int', 'float', 'bool', 'json'
    description = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<TransactionConfig {self.key}={self.value}>"
