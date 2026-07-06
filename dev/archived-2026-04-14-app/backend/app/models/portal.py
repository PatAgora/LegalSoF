"""
Client portal models.

ClientUploadToken — a shareable, time-limited, revocable link that lets a
client upload evidence for ONE matter without a platform account. The token
value is a high-entropy random string (secrets.token_urlsafe(32)); knowing
the URL is the only credential, so tokens expire quickly (14 days by
default), carry an upload budget, and can be revoked by staff at any time.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


def _default_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=14)


class ClientUploadToken(Base):
    """A client evidence-upload link for a matter."""

    __tablename__ = "client_upload_tokens"

    id = Column(Integer, primary_key=True, index=True)
    # secrets.token_urlsafe(32) produces 43 chars; column sized with headroom.
    token = Column(String(64), unique=True, index=True, nullable=False)
    matter_id = Column(Integer, ForeignKey("matters.id"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    expires_at = Column(DateTime(timezone=True), nullable=False, default=_default_expiry)
    max_uploads = Column(Integer, nullable=False, default=20)
    upload_count = Column(Integer, nullable=False, default=0)
    revoked = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # One-directional relationships — no back_populates so the Matter and
    # User models stay untouched.
    matter = relationship("Matter", foreign_keys=[matter_id])
    created_by = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<ClientUploadToken {self.id} for Matter {self.matter_id}>"
