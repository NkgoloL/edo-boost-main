"""
app/api/models/consent.py

SQLAlchemy 2.0 ORM model for parental consent records.
Maps to the parental_consents table created by migration 0001.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import (
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.api.models.base import Base


class ConsentStatus(str, enum.Enum):
    pending = "pending"
    granted = "granted"
    revoked = "revoked"
    expired = "expired"


CONSENT_VALIDITY_DAYS = 365  # POPIA: annual renewal required


class ParentalConsent(Base):
    __tablename__ = "parental_consents"
    __table_args__ = (
        UniqueConstraint("learner_id", "guardian_id", name="uq_consent_learner_guardian"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guardians.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ConsentStatus] = mapped_column(
        SAEnum(ConsentStatus, name="consent_status_enum", create_type=False),
        nullable=False,
        default=ConsentStatus.pending,
        index=True,
    )
    granted_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    ip_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_agent_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consent_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="1.0"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships (back-populated in learner/guardian models)
    learner: Mapped["Learner"] = relationship(back_populates="consents")  # noqa: F821
    guardian: Mapped["Guardian"] = relationship(back_populates="consents")  # noqa: F821

    # ── Domain helpers ────────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        """True only when status is granted AND not expired."""
        if self.status != ConsentStatus.granted:
            return False
        if self.expires_at and datetime.now(tz=timezone.utc) > self.expires_at:
            return False
        return True

    def mark_granted(
        self,
        *,
        ip_hash: Optional[str] = None,
        user_agent_hash: Optional[str] = None,
        consent_version: str = "1.0",
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        self.status = ConsentStatus.granted
        self.granted_at = now
        self.expires_at = now + timedelta(days=CONSENT_VALIDITY_DAYS)
        self.revoked_at = None
        if ip_hash:
            self.ip_hash = ip_hash
        if user_agent_hash:
            self.user_agent_hash = user_agent_hash
        self.consent_version = consent_version

    def mark_revoked(self) -> None:
        self.status = ConsentStatus.revoked
        self.revoked_at = datetime.now(tz=timezone.utc)
        self.expires_at = None

    def __repr__(self) -> str:
        return (
            f"<ParentalConsent learner={self.learner_id} "
            f"guardian={self.guardian_id} status={self.status}>"
        )
