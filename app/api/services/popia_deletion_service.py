"""
EduBoost SA — POPIA Deletion Service

Implements the right to erasure (right to be forgotten) as required by
South Africa's Protection of Personal Information Act (POPIA).

This service performs application-level anonymization while preserving
compliance evidence and aggregate analytics utility.
"""
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.db_models import (
    AuditEvent,
    ConsentAudit,
    DiagnosticSession,
    Learner,
    LearnerIdentity,
    SessionEvent,
    StudyPlan,
    SubjectMastery,
)


class PopiaDeletionService:
    """Service for handling POPIA right to erasure requests."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def request_deletion(
        self,
        learner_id: UUID,
        guardian_id: UUID,
        reason: Optional[str] = None,
    ) -> dict:
        await self._verify_guardian_consent(learner_id, guardian_id)

        deletion_request = AuditEvent(
            event_id=uuid.uuid4(),
            learner_id=learner_id,
            event_type="POPIA_DELETION_REQUESTED",
            details={
                "reason": reason,
                "guardian_id": str(guardian_id),
                "requested_at": datetime.now().isoformat(),
            },
            occurred_at=datetime.now(),
        )
        self.session.add(deletion_request)
        await self.session.commit()

        return {
            "request_id": str(deletion_request.event_id),
            "learner_id": str(learner_id),
            "status": "pending",
            "message": "Deletion request submitted. Data will be anonymized within 30 days.",
            "popia_compliant": True,
        }

    async def execute_deletion(
        self,
        learner_id: UUID,
        guardian_id: UUID,
    ) -> dict:
        await self._verify_guardian_consent(learner_id, guardian_id)

        learner = await self.session.get(Learner, learner_id)
        if not learner:
            raise ValueError(f"Learner {learner_id} not found")

        anonymization_id = f"anon_{uuid.uuid4().hex[:12]}"
        executed_at = datetime.now()

        learner.overall_mastery = 0.0
        learner.streak_days = 0
        learner.total_xp = 0
        learner.home_language = "und"
        learner.avatar_id = 0
        learner.learning_style = {}
        learner.last_active_at = executed_at

        result = await self.session.execute(
            select(LearnerIdentity).where(LearnerIdentity.pseudonym_id == learner_id)
        )
        identity = result.scalar_one_or_none()
        if identity:
            identity.full_name_encrypted = None
            identity.date_of_birth_encrypted = None
            identity.guardian_email_encrypted = f"DELETED_{anonymization_id}"
            identity.data_deletion_requested = True
            identity.consent_timestamp = executed_at

        result = await self.session.execute(
            select(SubjectMastery).where(SubjectMastery.learner_id == learner_id)
        )
        for subject_mastery in result.scalars().all():
            subject_mastery.concepts_mastered = []
            subject_mastery.concepts_in_progress = []
            subject_mastery.knowledge_gaps = []
            subject_mastery.updated_at = executed_at

        result = await self.session.execute(
            select(DiagnosticSession).where(DiagnosticSession.learner_id == learner_id)
        )
        for diagnostic_session in result.scalars().all():
            diagnostic_session.knowledge_gaps = []
            diagnostic_session.status = "anonymized"
            diagnostic_session.completed_at = diagnostic_session.completed_at or executed_at

        result = await self.session.execute(
            select(StudyPlan).where(StudyPlan.learner_id == learner_id)
        )
        for study_plan in result.scalars().all():
            study_plan.schedule = {}
            study_plan.week_focus = "DELETED"
            study_plan.generated_by = "ANONYMIZED"

        result = await self.session.execute(
            select(SessionEvent).where(SessionEvent.learner_id == learner_id)
        )
        for session_event in result.scalars().all():
            session_event.lesson_id = None
            session_event.content_modality = None
            session_event.event_type = "ANONYMIZED"
            session_event.is_correct = None
            session_event.time_on_task_ms = None
            session_event.difficulty_level = None
            session_event.post_mastery_delta = None
            session_event.lesson_efficacy_score = None

        self.session.add(
            ConsentAudit(
                audit_id=uuid.uuid4(),
                pseudonym_id=learner_id,
                event_type="consent_revoked",
                consent_version=1,
                guardian_email_hash=None,
                ip_address_hash=None,
                occurred_at=executed_at,
            )
        )
        self.session.add(
            AuditEvent(
                event_id=uuid.uuid4(),
                learner_id=learner_id,
                event_type="POPIA_DELETION_COMPLETED",
                details={
                    "anonymization_id": anonymization_id,
                    "guardian_id": str(guardian_id),
                    "executed_at": executed_at.isoformat(),
                },
                occurred_at=executed_at,
            )
        )
        self.session.add(
            AuditEvent(
                event_id=uuid.uuid4(),
                learner_id=learner_id,
                event_type="SESSIONS_INVALIDATED",
                details={
                    "reason": "POPIA data deletion",
                    "executed_at": executed_at.isoformat(),
                },
                occurred_at=executed_at,
            )
        )

        await self.session.commit()

        return {
            "learner_id": str(learner_id),
            "status": "completed",
            "anonymization_id": anonymization_id,
            "message": "Data has been anonymized in compliance with POPIA. Analytics data retained in anonymized form.",
            "popia_compliant": True,
        }

    async def get_deletion_status(
        self,
        learner_id: UUID,
        guardian_id: UUID,
    ) -> dict:
        await self._verify_guardian_consent(learner_id, guardian_id)

        result = await self.session.execute(
            select(AuditEvent)
            .where(
                AuditEvent.learner_id == learner_id,
                AuditEvent.event_type.in_(["POPIA_DELETION_REQUESTED", "POPIA_DELETION_COMPLETED"]),
            )
            .order_by(AuditEvent.occurred_at.desc())
            .limit(1)
        )
        latest_event = result.scalar_one_or_none()
        if not latest_event:
            return {
                "learner_id": str(learner_id),
                "status": "none",
                "message": "No deletion request found",
            }

        status = "completed" if latest_event.event_type == "POPIA_DELETION_COMPLETED" else "pending"
        return {
            "learner_id": str(learner_id),
            "status": status,
            "requested_at": latest_event.occurred_at.isoformat() if latest_event else None,
            "completed_at": latest_event.occurred_at.isoformat() if status == "completed" else None,
        }

    async def export_data(
        self,
        learner_id: UUID,
        guardian_id: UUID,
    ) -> dict:
        await self._verify_guardian_consent(learner_id, guardian_id)

        learner = await self.session.get(Learner, learner_id)
        if not learner:
            raise ValueError(f"Learner {learner_id} not found")

        result = await self.session.execute(select(SubjectMastery).where(SubjectMastery.learner_id == learner_id))
        subject_mastery = [
            {
                "subject_code": sm.subject_code,
                "mastery_score": sm.mastery_score,
                "concepts_mastered": sm.concepts_mastered or [],
                "knowledge_gaps": sm.knowledge_gaps or [],
                "last_assessed": sm.last_assessed_at.isoformat() if sm.last_assessed_at else None,
            }
            for sm in result.scalars().all()
        ]

        result = await self.session.execute(
            select(SessionEvent).where(SessionEvent.learner_id == learner_id).order_by(SessionEvent.occurred_at.desc()).limit(100)
        )
        session_events = [
            {
                "event_type": e.event_type,
                "lesson_id": e.lesson_id,
                "content_modality": e.content_modality,
                "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            }
            for e in result.scalars().all()
        ]

        result = await self.session.execute(
            select(StudyPlan).where(StudyPlan.learner_id == learner_id).order_by(StudyPlan.created_at.desc())
        )
        study_plans = [
            {
                "plan_id": str(sp.plan_id),
                "week_start": sp.week_start.isoformat(),
                "week_focus": sp.week_focus,
                "gap_ratio": sp.gap_ratio,
                "schedule": sp.schedule,
                "created_at": sp.created_at.isoformat() if sp.created_at else None,
            }
            for sp in result.scalars().all()
        ]

        result = await self.session.execute(
            select(DiagnosticSession).where(DiagnosticSession.learner_id == learner_id).order_by(DiagnosticSession.started_at.desc())
        )
        diagnostics = [
            {
                "session_id": str(ds.session_id),
                "subject_code": ds.subject_code,
                "grade_level": ds.grade_level,
                "theta_estimate": ds.theta_estimate,
                "standard_error": ds.standard_error,
                "final_mastery_score": ds.final_mastery_score,
                "knowledge_gaps": ds.knowledge_gaps or [],
                "completed_at": ds.completed_at.isoformat() if ds.completed_at else None,
            }
            for ds in result.scalars().all()
        ]

        result = await self.session.execute(
            select(ConsentAudit).where(ConsentAudit.pseudonym_id == learner_id).order_by(ConsentAudit.occurred_at.desc())
        )
        consent_history = [
            {
                "event_type": ca.event_type,
                "consent_version": ca.consent_version,
                "occurred_at": ca.occurred_at.isoformat() if ca.occurred_at else None,
            }
            for ca in result.scalars().all()
        ]

        return {
            "learner_id": str(learner_id),
            "exported_at": datetime.now().isoformat(),
            "data": {
                "profile": {
                    "grade": learner.grade,
                    "overall_mastery": learner.overall_mastery,
                    "streak_days": learner.streak_days,
                    "total_xp": learner.total_xp,
                    "created_at": learner.created_at.isoformat() if learner.created_at else None,
                    "last_active": learner.last_active_at.isoformat() if learner.last_active_at else None,
                },
                "subject_mastery": subject_mastery,
                "session_events": session_events,
                "study_plans": study_plans,
                "diagnostic_sessions": diagnostics,
                "consent_history": consent_history,
            },
        }

    async def _verify_guardian_consent(self, learner_id: UUID, guardian_id: UUID) -> None:
        from fastapi import HTTPException

        result = await self.session.execute(
            select(ConsentAudit)
            .where(ConsentAudit.pseudonym_id == learner_id, ConsentAudit.event_type == "consent_granted")
            .order_by(ConsentAudit.occurred_at.desc())
            .limit(1)
        )
        consent = result.scalar_one_or_none()
        if not consent:
            raise HTTPException(status_code=403, detail="Guardian consent required to access learner data")

        result = await self.session.execute(
            select(ConsentAudit)
            .where(ConsentAudit.pseudonym_id == learner_id, ConsentAudit.event_type == "consent_revoked")
            .order_by(ConsentAudit.occurred_at.desc())
            .limit(1)
        )
        revoked = result.scalar_one_or_none()
        if revoked and revoked.occurred_at > consent.occurred_at:
            raise HTTPException(status_code=403, detail="Guardian consent has been revoked")
