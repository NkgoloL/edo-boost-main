"""
PILLAR 1 — LEGISLATURE
ConstitutionalRule Pydantic schema + SQLAlchemy ORM.
Rules are content-addressable and immutable after creation.
Architectural recommendation #4: SHA-256 hash, Postgres trigger, version rows.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Date, DateTime, String, Text, UniqueConstraint, event, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# ORM — Postgres trigger (see migrations/constitutional_immutability.sql)
# blocks UPDATE/DELETE at DB level; SQLAlchemy events add Python-layer defence.
# ---------------------------------------------------------------------------
class ConstitutionalRuleORM(Base):
    __tablename__ = "constitutional_rules"
    __table_args__ = (
        UniqueConstraint("rule_id", "effective_date", name="uq_rule_version"),
        {"comment": "Immutable policy rules; UPDATE/DELETE blocked by DB trigger"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_document: Mapped[str] = mapped_column(String(256), nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    scope_subjects: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    scope_grade_min: Mapped[Optional[int]] = mapped_column(nullable=True)
    scope_grade_max: Mapped[Optional[int]] = mapped_column(nullable=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    immutable_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False,
    )


@event.listens_for(ConstitutionalRuleORM, "before_update")
def _block_rule_update(mapper, connection, target):  # noqa: ANN001
    raise RuntimeError(
        "ConstitutionalRule records are immutable. "
        "Insert a new row with a later effective_date instead."
    )


@event.listens_for(ConstitutionalRuleORM, "before_delete")
def _block_rule_delete(mapper, connection, target):  # noqa: ANN001
    raise RuntimeError("ConstitutionalRule records cannot be deleted.")


# ---------------------------------------------------------------------------
# Pydantic schema (frozen = immutable after construction)
# ---------------------------------------------------------------------------
class ScopeModel(BaseModel):
    subjects: List[str] = Field(default_factory=list)
    grade_min: int = Field(0, ge=0, le=12)
    grade_max: int = Field(12, ge=0, le=12)


class ConstitutionalRule(BaseModel):
    """Immutable policy rule with SHA-256 content hash."""

    rule_id: str = Field(..., description="Stable rule identifier, e.g. POPIA-S11-DATA-MIN")
    source_document: str = Field(..., description="Document name + version slug")
    rule_text: str = Field(..., description="Full normative text of the rule")
    scope: ScopeModel = Field(default_factory=ScopeModel)
    effective_date: date
    immutable_hash: str = Field(
        default="", description="SHA-256 of canonical fields; auto-computed if empty"
    )

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _auto_hash(self) -> "ConstitutionalRule":
        if not self.immutable_hash:
            object.__setattr__(self, "immutable_hash", self._compute_hash())
        return self

    def _compute_hash(self) -> str:
        canonical = (
            f"{self.rule_id}\x00{self.source_document}\x00"
            f"{self.rule_text}\x00{self.effective_date.isoformat()}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """True if stored hash matches freshly-computed hash."""
        return self.immutable_hash == self._compute_hash()

    @classmethod
    def from_orm(cls, row: ConstitutionalRuleORM) -> "ConstitutionalRule":
        return cls(
            rule_id=row.rule_id,
            source_document=row.source_document,
            rule_text=row.rule_text,
            scope=ScopeModel(
                subjects=row.scope_subjects or [],
                grade_min=row.scope_grade_min or 0,
                grade_max=row.scope_grade_max or 12,
            ),
            effective_date=row.effective_date,
            immutable_hash=row.immutable_hash,
        )


# ---------------------------------------------------------------------------
# Operator-signed rule-set bundle
# ---------------------------------------------------------------------------
class RuleSetSignatureORM(Base):
    """Stores operator keypair signature over the full rule bundle."""
    __tablename__ = "rule_set_signatures"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bundle_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    rule_count: Mapped[int] = mapped_column(nullable=False)
    signer_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
