"""
app/api/services/consent_service.py
────────────────────────────────────
[SHORT-TERM FIX 6] Full parental consent lifecycle service.

Implements POPIA ss.11, 13, 18, 23 requirements:
  - Explicit, informed, documented consent before any learner data processing
  - Consent versioning (new consent required when policy changes)
  - Consent withdrawal with immediate data processing suspension
  - Right to erasure with 30-day grace period
  - Complete audit trail for every consent event
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.consent import ParentalConsent
from app.api.models.deletion import DeletionRequest
from app.api.models.guardian import Guardian
from app.api.models.learner import Learner
from app.api.services.audit_service import AuditService
from app.api.core.metrics import (
    CONSENT_GRANTED_TOTAL,
    CONSENT_REVOKED_TOTAL,
    ERASURE_REQUESTED_TOTAL,
    ACTIVE_CONSENTS_TOTAL
)

log = structlog.get_logger()

# Current version of the consent document — bump this string whenever the
# privacy policy or consent terms change. All existing consents for prior
# versions are automatically invalidated, forcing re-consent.
CURRENT_CONSENT_VERSION = "v1.0-2026-05"

# POPIA s.14: data subjects must have a reasonable period to exercise rights
# before deletion is executed. 30 days is the standard grace period.
DELETION_GRACE_PERIOD_DAYS = 30


def _hash(value: str) -> str:
    """SHA-256 hash for PII fields stored in the DB (email, phone, IP)."""
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


class ConsentService:
    def __init__(self, db: AsyncSession, audit: AuditService):
        self.db = db
        self.audit = audit

    # ── Grant consent ─────────────────────────────────────────────────────────
    async def grant_consent(
        self,
        guardian_id: uuid.UUID,
        learner_id: uuid.UUID,
        ip_address: str,
        user_agent: str,
        consent_version: str = CURRENT_CONSENT_VERSION,
    ) -> ParentalConsent:
        """
        Record explicit, informed consent from a guardian for a learner.

        Called after the guardian has been shown and has acknowledged the
        full consent document at the given consent_version.
        """
        # Verify guardian owns this learner
        learner = await self._get_learner(learner_id, guardian_id)
        if not learner:
            raise ValueError("Learner not found or does not belong to this guardian")

        # Check for existing active consent for this version
        existing = await self._get_active_consent(learner_id, consent_version)
        if existing:
            log.info("consent.already_granted", learner_id=str(learner_id), version=consent_version)
            return existing

        consent = ParentalConsent(
            id=uuid.uuid4(),
            guardian_id=guardian_id,
            learner_id=learner_id,
            consent_version=consent_version,
            ip_address_hash=_hash(ip_address),
            user_agent=user_agent[:512] if user_agent else None,
            consented_at=datetime.now(timezone.utc),
        )
        self.db.add(consent)
        await self.db.flush()

        await self.audit.record(
            actor_id=guardian_id,
            actor_type="guardian",
            event_type="consent.granted",
            resource_type="learner",
            resource_id=learner_id,
            payload={"consent_version": consent_version},
            ip_address=ip_address,
        )

        CONSENT_GRANTED_TOTAL.inc()
        # Gauge update would ideally be done periodically, but we can do a simple inc/dec here
        ACTIVE_CONSENTS_TOTAL.inc()

        log.info("consent.granted", learner_id=str(learner_id), version=consent_version)
        return consent

    # ── Withdraw consent ──────────────────────────────────────────────────────
    async def withdraw_consent(
        self,
        guardian_id: uuid.UUID,
        learner_id: uuid.UUID,
        reason: str | None = None,
        ip_address: str = "",
    ) -> None:
        """
        Withdraw all active consents for a learner.

        POPIA s.11(3): withdrawal of consent must be as easy as granting it.
        Processing of the learner's data is immediately suspended.
        """
        result = await self.db.execute(
            update(ParentalConsent)
            .where(
                ParentalConsent.learner_id == learner_id,
                ParentalConsent.guardian_id == guardian_id,
                ParentalConsent.withdrawn_at.is_(None),
            )
            .values(
                withdrawn_at=datetime.now(timezone.utc),
                withdrawal_reason=reason,
            )
            .returning(ParentalConsent.id)
        )
        withdrawn_ids = result.scalars().all()

        if not withdrawn_ids:
            log.warning("consent.withdraw_not_found", learner_id=str(learner_id))
            return

        await self.audit.record(
            actor_id=guardian_id,
            actor_type="guardian",
            event_type="consent.withdrawn",
            resource_type="learner",
            resource_id=learner_id,
            payload={"withdrawn_consent_ids": [str(i) for i in withdrawn_ids], "reason": reason},
            ip_address=ip_address,
        )
        CONSENT_REVOKED_TOTAL.inc()
        ACTIVE_CONSENTS_TOTAL.dec(len(withdrawn_ids))

        log.info("consent.withdrawn", learner_id=str(learner_id), count=len(withdrawn_ids))

    # ── Check active consent ──────────────────────────────────────────────────
    async def has_active_consent(self, learner_id: uuid.UUID) -> bool:
        """
        Returns True only if an active, current-version consent exists.
        Used as a gate in API routes before processing learner data.
        """
        consent = await self._get_active_consent(learner_id, CURRENT_CONSENT_VERSION)
        return consent is not None

    # ── Request right to erasure ──────────────────────────────────────────────
    async def request_erasure(
        self,
        guardian_id: uuid.UUID,
        learner_id: uuid.UUID | None = None,
        scope: str = "learner",
        reason: str | None = None,
        ip_address: str = "",
    ) -> DeletionRequest:
        """
        POPIA s.24: right to erasure / deletion.

        Creates a deletion request with a 30-day grace period.
        The actual data deletion is executed by the Celery task
        `tasks.deletion.process_deletion_request` at `scheduled_for`.

        scope:
          "learner"  — delete a single learner's data
          "guardian" — delete guardian account + all linked learners
          "all"      — nuclear option: guardian + all learners + all data
        """
        # Immediately withdraw all consents
        if learner_id:
            await self.withdraw_consent(guardian_id, learner_id, reason="erasure_requested", ip_address=ip_address)

        scheduled = datetime.now(timezone.utc) + timedelta(days=DELETION_GRACE_PERIOD_DAYS)
        req = DeletionRequest(
            id=uuid.uuid4(),
            guardian_id=guardian_id,
            learner_id=learner_id,
            scope=scope,
            reason=reason,
            requested_at=datetime.now(timezone.utc),
            scheduled_for=scheduled,
            status="pending",
        )
        self.db.add(req)
        await self.db.flush()

        await self.audit.record(
            actor_id=guardian_id,
            actor_type="guardian",
            event_type="erasure.requested",
            resource_type="learner" if learner_id else "guardian",
            resource_id=learner_id or guardian_id,
            payload={"scope": scope, "scheduled_for": scheduled.isoformat(), "reason": reason},
            ip_address=ip_address,
        )

        ERASURE_REQUESTED_TOTAL.inc()

        log.info(
            "erasure.requested",
            guardian_id=str(guardian_id),
            learner_id=str(learner_id) if learner_id else None,
            scope=scope,
            scheduled_for=scheduled.isoformat(),
        )
        return req

    # ── Cancel a pending erasure request ─────────────────────────────────────
    async def cancel_erasure(
        self,
        guardian_id: uuid.UUID,
        deletion_request_id: uuid.UUID,
        ip_address: str = "",
    ) -> None:
        """Cancel an erasure request within the grace period."""
        result = await self.db.execute(
            update(DeletionRequest)
            .where(
                DeletionRequest.id == deletion_request_id,
                DeletionRequest.guardian_id == guardian_id,
                DeletionRequest.status == "pending",
            )
            .values(status="cancelled")
            .returning(DeletionRequest.id)
        )
        if not result.scalar_one_or_none():
            raise ValueError("Deletion request not found, not pending, or not owned by this guardian")

        await self.audit.record(
            actor_id=guardian_id,
            actor_type="guardian",
            event_type="erasure.cancelled",
            resource_type="deletion_request",
            resource_id=deletion_request_id,
            payload={},
            ip_address=ip_address,
        )
        log.info("erasure.cancelled", deletion_request_id=str(deletion_request_id))

    # ── Helpers ───────────────────────────────────────────────────────────────
    async def _get_active_consent(
        self, learner_id: uuid.UUID, version: str
    ) -> ParentalConsent | None:
        result = await self.db.execute(
            select(ParentalConsent).where(
                ParentalConsent.learner_id == learner_id,
                ParentalConsent.consent_version == version,
                ParentalConsent.withdrawn_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _get_learner(
        self, learner_id: uuid.UUID, guardian_id: uuid.UUID
    ) -> Learner | None:
        result = await self.db.execute(
            select(Learner).where(
                Learner.id == learner_id,
                Learner.guardian_id == guardian_id,
                Learner.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()
