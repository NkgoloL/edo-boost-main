"""
EduBoost SA — Audit Event Emission Helpers

Utility functions for emitting audit events on protected mutations.
"""
import json
from uuid import UUID
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger()


async def emit_audit_event(
    session: AsyncSession,
    event_type: str,
    learner_id: Optional[UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    pillar: str = "EXECUTIVE",
    details: Optional[dict] = None,
    actor_id: Optional[str] = None,
) -> None:
    """
    Emit an audit event to the database.
    
    Args:
        session: AsyncSession for database writes
        event_type: Type of event (e.g., "LESSON_GENERATED", "CONSENT_RECORDED", "DELETION_REQUESTED")
        learner_id: UUID of affected learner (if applicable)
        resource_type: Type of resource affected (e.g., "lesson", "study_plan", "consent_record")
        resource_id: ID of the affected resource
        pillar: Constitutional pillar responsible (LEGISLATURE, EXECUTIVE, JUDICIARY, FOURTH_ESTATE)
        details: Additional event metadata
        actor_id: ID of the actor/system performing the action
    """
    try:
        from app.api.models.db_models import AuditEvent
        from uuid import uuid4
        
        event = AuditEvent(
            event_id=uuid4(),
            event_type=event_type,
            pillar=pillar,
            actor_id=actor_id or "SYSTEM",
            learner_id=learner_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            occurred_at=datetime.utcnow(),
        )
        
        session.add(event)
        await session.flush()
        
        log.info(
            "audit.event_emitted",
            event_type=event_type,
            learner_id=str(learner_id) if learner_id else None,
            resource_type=resource_type,
        )
    except Exception as e:
        log.error(
            "audit.event_emit_failed",
            event_type=event_type,
            error=str(e),
        )
        # Do not raise — audit emission failure should not block operations


async def emit_lesson_generation_event(
    session: AsyncSession,
    learner_id: UUID,
    lesson_id: str,
    subject_code: str,
    topic: str,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """Emit audit event for lesson generation."""
    await emit_audit_event(
        session=session,
        event_type="LESSON_GENERATED" if success else "LESSON_GENERATION_FAILED",
        learner_id=learner_id,
        resource_type="lesson",
        resource_id=lesson_id,
        pillar="EXECUTIVE",
        details={
            "subject_code": subject_code,
            "topic": topic,
            "success": success,
            "error": error,
        },
        actor_id="LESSON_SERVICE",
    )


async def emit_diagnostic_event(
    session: AsyncSession,
    learner_id: UUID,
    session_id: str,
    subject_code: str,
    status: str = "COMPLETED",
) -> None:
    """Emit audit event for diagnostic completion."""
    await emit_audit_event(
        session=session,
        event_type="DIAGNOSTIC_COMPLETED",
        learner_id=learner_id,
        resource_type="diagnostic_session",
        resource_id=session_id,
        pillar="EXECUTIVE",
        details={
            "subject_code": subject_code,
            "status": status,
        },
        actor_id="DIAGNOSTIC_SERVICE",
    )


async def emit_study_plan_event(
    session: AsyncSession,
    learner_id: UUID,
    plan_id: str,
    event_type: str = "STUDY_PLAN_GENERATED",
) -> None:
    """Emit audit event for study plan generation/refresh."""
    await emit_audit_event(
        session=session,
        event_type=event_type,
        learner_id=learner_id,
        resource_type="study_plan",
        resource_id=plan_id,
        pillar="EXECUTIVE",
        details={"action": event_type},
        actor_id="STUDY_PLAN_SERVICE",
    )


async def emit_consent_event(
    session: AsyncSession,
    learner_id: UUID,
    consent_event_type: str,
    consent_version: int = 1,
) -> None:
    """Emit audit event for consent recording."""
    await emit_audit_event(
        session=session,
        event_type=f"CONSENT_{consent_event_type}",
        learner_id=learner_id,
        resource_type="consent_record",
        pillar="LEGISLATURE",
        details={
            "event_type": consent_event_type,
            "consent_version": consent_version,
        },
        actor_id="CONSENT_SERVICE",
    )


async def emit_deletion_event(
    session: AsyncSession,
    learner_id: UUID,
    event_type: str = "DELETION_REQUESTED",
) -> None:
    """Emit audit event for data deletion."""
    await emit_audit_event(
        session=session,
        event_type=event_type,
        learner_id=learner_id,
        resource_type="learner_deletion",
        resource_id=str(learner_id),
        pillar="LEGISLATURE",
        details={"action": event_type},
        actor_id="POPIA_SERVICE",
    )
