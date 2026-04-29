"""
POPIA COMPLIANCE
PII scrubber, consent gate enforcement, right-to-erasure workflow.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PII Scrubber — pre-send check before any LLM call reaches a provider
# ---------------------------------------------------------------------------
_SA_ID = re.compile(r"\b\d{13}\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_SA_MOBILE = re.compile(r"\b0[6-8]\d{8}\b")
_BANK_ACCOUNT = re.compile(r"\b\d{9,12}\b")
_NAME_PREFIXES = re.compile(r"\b(Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+ [A-Z][a-z]+\b")

PII_PATTERNS = [
    ("SA_ID_NUMBER", _SA_ID),
    ("EMAIL_ADDRESS", _EMAIL),
    ("SA_MOBILE_NUMBER", _SA_MOBILE),
    ("BANK_ACCOUNT", _BANK_ACCOUNT),
    ("FULL_NAME", _NAME_PREFIXES),
]


class PIIDetectionResult:
    def __init__(self, clean: bool, violations: List[str]):
        self.clean = clean
        self.violations = violations


def scrub_pii(text_: str) -> PIIDetectionResult:
    """
    Scan text for PII patterns. Returns clean=False if any PII is detected.
    Does NOT redact — the caller must BLOCK the request, not sanitise it.
    POPIA data minimisation: PII should never reach the LLM in the first place.
    """
    violations = []
    for label, pattern in PII_PATTERNS:
        if pattern.search(text_):
            violations.append(label)

    return PIIDetectionResult(clean=len(violations) == 0, violations=violations)


def assert_pii_clean(text_: str, context: str = "") -> None:
    """Raise ValueError if PII is detected. Call before any LLM request."""
    result = scrub_pii(text_)
    if not result.clean:
        raise ValueError(
            f"PII detected in LLM prompt [{context}]. "
            f"Violations: {result.violations}. Request blocked."
        )


# ---------------------------------------------------------------------------
# Consent Gate
# ---------------------------------------------------------------------------
class ConsentGate:
    """
    Application-layer consent enforcement (backs up the Postgres RLS policy).
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def assert_active(self, learner_pseudonym: str) -> None:
        """
        Raises PermissionError if the learner does not have ACTIVE consent.
        This is checked at _stamp_gate() in WorkerAgent AND by the RLS policy.
        """
        row = (
            await self._session.execute(
                text(
                    """
                    SELECT consent_status FROM consent_log
                    WHERE learner_pseudonym = :p AND revoked_at IS NULL
                    ORDER BY granted_at DESC LIMIT 1
                    """
                ),
                {"p": learner_pseudonym},
            )
        ).first()

        if row is None or row[0] != "ACTIVE":
            raise PermissionError(
                f"Learner {learner_pseudonym} does not have ACTIVE parental consent. "
                "Processing blocked under POPIA Section 35."
            )

    async def grant(
        self, learner_pseudonym: str, granted_by: str, guardian_contact: str
    ) -> str:
        """Grant consent. Returns consent_id. Emits audit stream event."""
        consent_id = str(uuid.uuid4())
        await self._session.execute(
            text(
                """
                INSERT INTO consent_log
                    (consent_id, learner_pseudonym, consent_status, granted_by,
                     guardian_contact, granted_at)
                VALUES (:cid, :p, 'ACTIVE', :gb, :gc, now())
                """
            ),
            {
                "cid": consent_id,
                "p": learner_pseudonym,
                "gb": granted_by,
                "gc": guardian_contact,
            },
        )
        await self._session.commit()

        await self._emit_consent_event(learner_pseudonym, "GRANTED", consent_id, granted_by)
        return consent_id

    async def revoke(self, learner_pseudonym: str, revoked_by: str) -> None:
        """Revoke consent. Marks all active consent records as revoked."""
        await self._session.execute(
            text(
                """
                UPDATE consent_log
                SET consent_status = 'REVOKED', revoked_at = now(), revoked_by = :rb
                WHERE learner_pseudonym = :p AND revoked_at IS NULL
                """
            ),
            {"rb": revoked_by, "p": learner_pseudonym},
        )
        await self._session.commit()
        await self._emit_consent_event(learner_pseudonym, "REVOKED", None, revoked_by)

    async def _emit_consent_event(
        self, pseudonym: str, action: str, consent_id: Optional[str], actor: str
    ) -> None:
        from app.api.pillar_4_fourth_estate.streams import publish_consent_event

        await publish_consent_event({
            "learner_pseudonym": pseudonym,
            "consent_action": action,
            "consent_id": consent_id or "",
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


# ---------------------------------------------------------------------------
# Right-to-Erasure Workflow
# ---------------------------------------------------------------------------
class ErasureService:
    """
    POPIA Section 24: Right to Erasure.
    Cascades deletion across all learner-linked tables and R2/S3 assets.
    Emits a deletion event to the audit stream.
    """

    LEARNER_TABLES = [
        "learner_profiles",
        "irt_responses",
        "study_plans",
        "lesson_results",
        "ether_profiles",
        "session_states",
        "consent_log",
    ]

    def __init__(self, session: AsyncSession):
        self._session = session

    async def erase(self, learner_pseudonym: str, requested_by: str) -> Dict[str, Any]:
        """
        Delete all data for a learner pseudonym.
        Returns a summary of what was deleted.
        """
        summary: Dict[str, Any] = {
            "learner_pseudonym": learner_pseudonym,
            "requested_by": requested_by,
            "tables_cleared": [],
            "r2_objects_deleted": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for table in self.LEARNER_TABLES:
            try:
                result = await self._session.execute(
                    text(f"DELETE FROM {table} WHERE learner_pseudonym = :p"),
                    {"p": learner_pseudonym},
                )
                if result.rowcount > 0:
                    summary["tables_cleared"].append(f"{table}:{result.rowcount}")
            except Exception as exc:
                logger.error("Erasure error on table %s: %s", table, exc)
                summary.setdefault("errors", []).append(f"{table}: {exc}")

        await self._session.commit()

        # Delete R2/S3 assets
        r2_count = await self._delete_r2_assets(learner_pseudonym)
        summary["r2_objects_deleted"] = r2_count

        # Emit deletion event to audit stream (MUST be the last operation)
        await self._emit_deletion_event(learner_pseudonym, summary)

        logger.info("POPIA erasure complete: pseudonym=%s tables=%s r2=%d",
                    learner_pseudonym, summary["tables_cleared"], r2_count)
        return summary

    async def _delete_r2_assets(self, learner_pseudonym: str) -> int:
        """Delete learner assets from R2/S3. Returns count of deleted objects."""
        try:
            import boto3

            s3 = boto3.client(
                "s3",
                endpoint_url=__import__("os").environ.get("R2_ENDPOINT_URL"),
                aws_access_key_id=__import__("os").environ.get("R2_ACCESS_KEY_ID"),
                aws_secret_access_key=__import__("os").environ.get("R2_SECRET_ACCESS_KEY"),
            )
            bucket = __import__("os").environ.get("R2_BUCKET", "eduboost-assets")
            prefix = f"learners/{learner_pseudonym}/"

            paginator = s3.get_paginator("list_objects_v2")
            keys = []
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append({"Key": obj["Key"]})

            if keys:
                s3.delete_objects(Bucket=bucket, Delete={"Objects": keys})

            return len(keys)
        except Exception as exc:
            logger.error("R2 asset deletion failed: %s", exc)
            return 0

    async def _emit_deletion_event(self, pseudonym: str, summary: Dict[str, Any]) -> None:
        from app.api.pillar_4_fourth_estate.streams import publish_action

        await publish_action({
            "event_type": "popia_erasure",
            "learner_pseudonym": pseudonym,
            "summary": str(summary),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
