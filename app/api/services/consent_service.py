"""
app/api/services/consent_service.py

Service layer for parental consent management.

All learner-data-touching operations MUST call require_active_consent()
before proceeding.  This is the single enforcement point for POPIA compliance.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.consent import ConsentStatus, ParentalConsent
from app.api.models.learner import Learner  # noqa: F401 (for type hints)


class ConsentNotGrantedError(Exception):
    """Raised when learner data is requested without active parental consent."""

    def __init__(self, learner_id: uuid.UUID) -> None:
        self.learner_id = learner_id
        super().__init__(
            f"Active parental consent is required before accessing data for "
            f"learner {learner_id}.  Guardian must grant consent at /api/v1/consent/grant."
        )


class ConsentService:
    """
    All methods are async and accept an AsyncSession injected via FastAPI
    dependency injection.

    Usage in a router:

        from app.api.services.consent_service import ConsentService, ConsentNotGrantedError
        from app.api.core.db import get_db

        @router.get("/learners/{learner_id}/lessons")
        async def get_lessons(learner_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
            await ConsentService.require_active_consent(db, learner_id)
            ...
    """

    # ── Static helpers ────────────────────────────────────────────────────

    @staticmethod
    def _hash(value: str) -> str:
        """One-way SHA-256 hash for IP addresses and user-agents."""
        return hashlib.sha256(value.encode()).hexdigest()

    # ── Read ──────────────────────────────────────────────────────────────

    @staticmethod
    async def get_consent(
        db: AsyncSession,
        learner_id: uuid.UUID,
        guardian_id: uuid.UUID,
    ) -> Optional[ParentalConsent]:
        result = await db.execute(
            select(ParentalConsent).where(
                ParentalConsent.learner_id == learner_id,
                ParentalConsent.guardian_id == guardian_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_consent_for_learner(
        db: AsyncSession, learner_id: uuid.UUID
    ) -> Optional[ParentalConsent]:
        """Return the active consent record for a learner (any guardian), or None."""
        result = await db.execute(
            select(ParentalConsent).where(
                ParentalConsent.learner_id == learner_id,
                ParentalConsent.status == ConsentStatus.granted,
                # Exclude expired rows
                (ParentalConsent.expires_at == None)  # noqa: E711
                | (ParentalConsent.expires_at > datetime.now(tz=timezone.utc)),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def require_active_consent(
        db: AsyncSession, learner_id: uuid.UUID
    ) -> ParentalConsent:
        """
        POPIA enforcement gate.

        Call this at the top of every endpoint that reads or writes
        learner personal data.  Raises ConsentNotGrantedError if no
        active consent exists — FastAPI will convert this to a 403.
        """
        consent = await ConsentService.get_active_consent_for_learner(db, learner_id)
        if consent is None:
            raise ConsentNotGrantedError(learner_id)
        return consent

    # ── Write ─────────────────────────────────────────────────────────────

    @staticmethod
    async def create_pending(
        db: AsyncSession,
        learner_id: uuid.UUID,
        guardian_id: uuid.UUID,
        consent_version: str = "1.0",
    ) -> ParentalConsent:
        """Create a consent record in 'pending' state when a learner is registered."""
        existing = await ConsentService.get_consent(db, learner_id, guardian_id)
        if existing:
            return existing

        consent = ParentalConsent(
            learner_id=learner_id,
            guardian_id=guardian_id,
            status=ConsentStatus.pending,
            consent_version=consent_version,
        )
        db.add(consent)
        await db.flush()
        return consent

    @staticmethod
    async def grant(
        db: AsyncSession,
        learner_id: uuid.UUID,
        guardian_id: uuid.UUID,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        consent_version: str = "1.0",
    ) -> ParentalConsent:
        """
        Guardian grants consent.  Creates the record if it doesn't exist yet
        (idempotent re-grant is allowed — e.g. annual renewal).
        """
        consent = await ConsentService.get_consent(db, learner_id, guardian_id)
        if consent is None:
            consent = ParentalConsent(
                learner_id=learner_id,
                guardian_id=guardian_id,
            )
            db.add(consent)

        consent.mark_granted(
            ip_hash=ConsentService._hash(ip_address) if ip_address else None,
            user_agent_hash=ConsentService._hash(user_agent) if user_agent else None,
            consent_version=consent_version,
        )
        await db.flush()
        return consent

    @staticmethod
    async def revoke(
        db: AsyncSession,
        learner_id: uuid.UUID,
        guardian_id: uuid.UUID,
    ) -> ParentalConsent:
        """Guardian revokes consent.  Learner data access is immediately blocked."""
        consent = await ConsentService.get_consent(db, learner_id, guardian_id)
        if consent is None:
            raise ValueError(
                f"No consent record found for learner {learner_id} / guardian {guardian_id}"
            )
        consent.mark_revoked()
        await db.flush()
        return consent

    # ── Right to erasure ──────────────────────────────────────────────────

    @staticmethod
    async def execute_erasure(
        db: AsyncSession,
        learner_id: uuid.UUID,
        guardian_id: uuid.UUID,
    ) -> dict:
        """
        POPIA right-to-erasure workflow.

        Steps performed atomically within the caller's transaction:
          1. Revoke consent (blocks all further access immediately).
          2. Soft-delete the learner row (sets deleted_at = now).
          3. Cascade: study_plans and diagnostic_sessions are CASCADE-deleted by FK.
          4. Returns a summary of what was erased for the audit log.

        Callers MUST commit the transaction and write an audit_log entry
        after this method returns.
        """
        # Step 1 — revoke consent
        consent = await ConsentService.revoke(db, learner_id, guardian_id)

        # Step 2 — soft-delete the learner record
        result = await db.execute(
            update(Learner)
            .where(Learner.id == learner_id, Learner.deleted_at == None)  # noqa: E711
            .values(deleted_at=datetime.now(tz=timezone.utc))
            .returning(Learner.id, Learner.pseudonym_id)
        )
        row = result.fetchone()

        return {
            "learner_id": str(learner_id),
            "pseudonym_id": row.pseudonym_id if row else None,
            "consent_revoked_at": consent.revoked_at.isoformat(),
            "learner_soft_deleted": row is not None,
            "erasure_timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
