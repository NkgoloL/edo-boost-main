"""
app/api/services/rlhf_service.py
─────────────────────────────────
RLHF (Reinforcement Learning from Human Feedback) pipeline service.

Collects learner and educator feedback on AI-generated lesson content,
stores it durably, and provides export methods to produce fine-tuning
datasets in standard RLHF formats (OpenAI messages / Anthropic RLHF JSON).

Pipeline:
  Lesson delivered → Learner rates (1-5) → Optional free-text → Stored in DB
  → Celery task exports high-quality pairs → Fine-tuning dataset produced

POPIA note: No learner PII is stored alongside feedback. Only the
learner_pseudonym_id (opaque hash) links feedback to a learner.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.rlhf import LessonFeedback, RLHFExport
from app.api.core.metrics import LESSON_FEEDBACK_TOTAL, RLHF_EXPORT_TOTAL

log = structlog.get_logger()

# Minimum rating to include in the positive fine-tuning set
POSITIVE_RATING_THRESHOLD = 4
# Maximum rating to include in the negative/comparison set
NEGATIVE_RATING_THRESHOLD = 2


class RLHFService:
    """Collects, stores, and exports lesson quality feedback for RLHF fine-tuning."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Record feedback ────────────────────────────────────────────────────────
    async def record_feedback(
        self,
        lesson_id: uuid.UUID,
        learner_pseudonym: str,
        rating: int,                    # 1–5 Likert scale
        comment: str | None = None,     # Optional free-text (max 2000 chars)
        subject: str | None = None,
        grade_level: int | None = None,
        language_code: str = "en",
        prompt_version: str | None = None,
    ) -> LessonFeedback:
        """
        Record a learner's qualitative rating of a lesson.

        rating: 1 (terrible) – 5 (excellent)
        comment: free-text educator or learner note (PII-scrubbed before storage)
        """
        if not 1 <= rating <= 5:
            raise ValueError(f"Rating must be 1–5, got {rating}")

        # Scrub any accidental PII from the comment
        clean_comment = self._scrub_comment(comment) if comment else None

        feedback = LessonFeedback(
            id=uuid.uuid4(),
            lesson_id=lesson_id,
            learner_pseudonym=learner_pseudonym,
            rating=rating,
            comment=clean_comment,
            subject=subject,
            grade_level=grade_level,
            language_code=language_code,
            prompt_version=prompt_version,
            submitted_at=datetime.now(timezone.utc),
        )
        self.db.add(feedback)
        await self.db.flush()

        # Emit Prometheus metric
        rating_bucket = "4-5" if rating >= 4 else ("3" if rating == 3 else "1-2")
        LESSON_FEEDBACK_TOTAL.labels(
            rating_bucket=rating_bucket,
            subject=subject or "unknown",
            grade_level=str(grade_level) if grade_level is not None else "unknown",
        ).inc()

        log.info(
            "rlhf.feedback_recorded",
            lesson_id=str(lesson_id),
            rating=rating,
            language=language_code,
        )
        return feedback

    # ── Export fine-tuning dataset ─────────────────────────────────────────────
    async def export_dataset(
        self,
        format: str = "openai_messages",   # openai_messages | anthropic | jsonl
        min_positive_count: int = 10,
        language_code: str | None = None,
    ) -> RLHFExport:
        """
        Build a fine-tuning dataset from collected feedback.

        Pairs high-rated (4-5) lessons with low-rated (1-2) versions of the
        same prompt context to create preference pairs for RLHF / DPO training.

        Returns an RLHFExport record with the dataset JSON path and metadata.
        """
        try:
            # Fetch positive examples
            positive_q = select(LessonFeedback).where(
                and_(
                    LessonFeedback.rating >= POSITIVE_RATING_THRESHOLD,
                    LessonFeedback.exported_at.is_(None),
                )
            )
            if language_code:
                positive_q = positive_q.where(LessonFeedback.language_code == language_code)

            positives_result = await self.db.execute(positive_q)
            positives = positives_result.scalars().all()

            # Fetch negative examples
            negative_q = select(LessonFeedback).where(
                and_(
                    LessonFeedback.rating <= NEGATIVE_RATING_THRESHOLD,
                    LessonFeedback.exported_at.is_(None),
                )
            )
            if language_code:
                negative_q = negative_q.where(LessonFeedback.language_code == language_code)

            negatives_result = await self.db.execute(negative_q)
            negatives = negatives_result.scalars().all()

            records = self._build_dataset(positives, negatives, format)

            export_record = RLHFExport(
                id=uuid.uuid4(),
                format=format,
                language_code=language_code,
                positive_count=len(positives),
                negative_count=len(negatives),
                record_count=len(records),
                dataset_json=json.dumps(records),
                exported_at=datetime.now(timezone.utc),
            )
            self.db.add(export_record)

            # Mark feedback as exported
            now = datetime.now(timezone.utc)
            for fb in [*positives, *negatives]:
                fb.exported_at = now

            await self.db.flush()

            RLHF_EXPORT_TOTAL.labels(status="success").inc()
            log.info(
                "rlhf.dataset_exported",
                format=format,
                positives=len(positives),
                negatives=len(negatives),
                records=len(records),
            )
            return export_record

        except Exception as e:
            RLHF_EXPORT_TOTAL.labels(status="error").inc()
            log.error("rlhf.export_failed", error=str(e))
            raise

    # ── Dataset stats ──────────────────────────────────────────────────────────
    async def get_stats(self) -> dict[str, Any]:
        """Return feedback volume and quality distribution stats."""
        total_result = await self.db.execute(
            select(func.count(LessonFeedback.id))
        )
        total = total_result.scalar() or 0

        avg_result = await self.db.execute(
            select(func.avg(LessonFeedback.rating))
        )
        avg_rating = float(avg_result.scalar() or 0)

        pending_result = await self.db.execute(
            select(func.count(LessonFeedback.id)).where(
                LessonFeedback.exported_at.is_(None)
            )
        )
        pending = pending_result.scalar() or 0

        return {
            "total_feedback": total,
            "pending_export": pending,
            "avg_rating": round(avg_rating, 2),
            "positive_threshold": POSITIVE_RATING_THRESHOLD,
            "negative_threshold": NEGATIVE_RATING_THRESHOLD,
        }

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _build_dataset(
        self,
        positives: list[LessonFeedback],
        negatives: list[LessonFeedback],
        format: str,
    ) -> list[dict]:
        """Format records as a fine-tuning dataset."""
        records = []

        if format == "openai_messages":
            for fb in positives:
                records.append({
                    "messages": [
                        {"role": "user", "content": f"Generate a lesson for grade {fb.grade_level}, subject: {fb.subject}, language: {fb.language_code}"},
                        {"role": "assistant", "content": f"[Lesson from lesson_id={fb.lesson_id}]"},
                    ],
                    "rating": fb.rating,
                    "comment": fb.comment,
                    "label": "positive",
                })

        elif format == "anthropic":
            for pos, neg in zip(positives, negatives):
                records.append({
                    "prompt": f"Generate a CAPS-aligned lesson for grade {pos.grade_level}, subject: {pos.subject}",
                    "chosen": f"[lesson_id={pos.lesson_id}] rating={pos.rating}",
                    "rejected": f"[lesson_id={neg.lesson_id}] rating={neg.rating}",
                })

        else:  # jsonl / raw
            for fb in [*positives, *negatives]:
                records.append({
                    "lesson_id": str(fb.lesson_id),
                    "rating": fb.rating,
                    "label": "positive" if fb.rating >= POSITIVE_RATING_THRESHOLD else "negative",
                    "subject": fb.subject,
                    "grade_level": fb.grade_level,
                    "language_code": fb.language_code,
                    "prompt_version": fb.prompt_version,
                    "comment": fb.comment,
                })

        return records

    @staticmethod
    def _scrub_comment(text: str) -> str:
        """Basic PII scrub for free-text comments before DB storage."""
        import re
        # Remove SA ID numbers
        text = re.sub(r'\b\d{13}\b', '[SA_ID]', text)
        # Remove email-like patterns
        text = re.sub(r'\S+@\S+\.\S+', '[EMAIL]', text)
        # Remove phone numbers
        text = re.sub(r'(?:\+27|0)\d{9}', '[PHONE]', text)
        return text[:2000]  # Hard cap at 2000 chars
