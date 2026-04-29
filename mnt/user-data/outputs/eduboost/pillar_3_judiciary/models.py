"""
PILLAR 3 — JUDICIARY
JudiciaryStamp, ConstitutionalViolation models.
ExecutiveActionIn is the inbound schema for the /review endpoint.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class StampVerdict(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ---------------------------------------------------------------------------
# Pydantic — inbound action (mirrors pillar_2_executive ExecutiveAction)
# ---------------------------------------------------------------------------
class ExecutiveActionIn(BaseModel):
    action_id: str
    agent_id: str
    intent: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    claimed_rules: List[str] = Field(default_factory=list)
    learner_pseudonym: Optional[str] = None
    timestamp: datetime
    signature: str = ""


# ---------------------------------------------------------------------------
# Pydantic — stamp returned to workers
# ---------------------------------------------------------------------------
class JudiciaryStamp(BaseModel):
    stamp_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str
    verdict: StampVerdict
    rules_checked: List[str] = Field(default_factory=list)
    reason: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewer_model_version: str = ""


# ---------------------------------------------------------------------------
# ORM — judiciary_stamps table
# ---------------------------------------------------------------------------
class JudiciaryStampORM(Base):
    __tablename__ = "judiciary_stamps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stamp_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    action_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(
        SAEnum(StampVerdict, name="stamp_verdict_enum"), nullable=False
    )
    rules_checked: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewer_model_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


# ---------------------------------------------------------------------------
# ORM — constitutional_violations table
# ---------------------------------------------------------------------------
class ConstitutionalViolationORM(Base):
    __tablename__ = "constitutional_violations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    violation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4())
    )
    action_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    stamp_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    agent_id: Mapped[str] = mapped_column(String(128), nullable=False)
    violation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    learner_pseudonym: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    # FK to audit_log
    audit_event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
