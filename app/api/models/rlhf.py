"""
app/api/models/rlhf.py
──────────────────────
SQLAlchemy ORM models for the RLHF feedback pipeline.

Tables:
  lesson_feedback    — individual learner ratings per lesson (1-5 Likert)
  rlhf_exports       — records of fine-tuning dataset exports
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Float, Integer, SmallInteger, String, Text,
    TIMESTAMP, ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class LessonFeedback(Base):
    """
    A single learner or educator rating of an AI-generated lesson.

    Pseudonym only — no learner PII stored here.
    comment is PII-scrubbed before insert (see RLHFService._scrub_comment).
    """
    __tablename__ = "lesson_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lesson_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    learner_pseudonym = Column(Text, nullable=False, comment="Opaque pseudonym — no PII")
    rating = Column(SmallInteger, nullable=False, comment="1 (poor) – 5 (excellent)")
    comment = Column(Text, nullable=True, comment="Optional free-text, PII-scrubbed")
    subject = Column(Text, nullable=True)
    grade_level = Column(SmallInteger, nullable=True)
    language_code = Column(String(8), nullable=False, server_default="en")
    prompt_version = Column(Text, nullable=True)
    submitted_at = Column(TIMESTAMP(timezone=True), nullable=False)
    exported_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)


class RLHFExport(Base):
    """Metadata record for each RLHF dataset export run."""
    __tablename__ = "rlhf_exports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    format = Column(Text, nullable=False, comment="openai_messages | anthropic | jsonl")
    language_code = Column(String(8), nullable=True)
    positive_count = Column(Integer, nullable=False)
    negative_count = Column(Integer, nullable=False)
    record_count = Column(Integer, nullable=False)
    dataset_json = Column(Text, nullable=False, comment="Serialised fine-tuning dataset")
    exported_at = Column(TIMESTAMP(timezone=True), nullable=False)
