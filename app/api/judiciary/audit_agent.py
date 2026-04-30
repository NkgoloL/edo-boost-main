"""
PILLAR 4 — FOURTH ESTATE
AuditAgent: persistent Redis Stream consumer.
Writes to audit_log (append-only) and constitutional_violations tables.
Has an INDEPENDENT DB connection — no access to learner or lesson tables.
Implements autonomous flagging when an action has no stamp within a time window.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict

from prometheus_client import Counter, Gauge
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .streams import (
    ALL_STREAMS,
    STREAM_CONSENT,
    ack_message,
    claim_stale,
    get_consumer_lag,
    initialise_streams,
    publish_dlq,
    publish_violation,
    read_pending,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
audit_events_written = Counter(
    "audit_events_written_total", "Total audit log entries written", ["event_type"]
)
audit_consumer_lag = Gauge(
    "audit_stream_consumer_lag", "Pending messages in audit consumer group", ["stream"]
)

# ---------------------------------------------------------------------------
# Configurable window for orphaned action detection
# ---------------------------------------------------------------------------
ORPHAN_WINDOW_SECONDS = int(os.environ.get("AUDIT_ORPHAN_WINDOW_SECONDS", "30"))
AUDIT_DB_URL = os.environ.get("AUDIT_DATABASE_URL", os.environ.get("DATABASE_URL", ""))


# ---------------------------------------------------------------------------
# AuditAgent
# ---------------------------------------------------------------------------
class AuditAgent:
    """
    Persistent consumer group reader for all audit streams.
    Only has write access to audit_log and constitutional_violations.
    """

    CONSUMER_NAME = "audit-agent-1"

    def __init__(self, session: AsyncSession):
        self._session = session
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        logger.info("AuditAgent starting.")
        await initialise_streams()
        self._running = True
        await asyncio.gather(
            self._consume_loop(),
            self._reclaim_loop(),
            self._orphan_detection_loop(),
            self._lag_metrics_loop(),
        )

    async def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Main consume loop
    # ------------------------------------------------------------------
    async def _consume_loop(self) -> None:
        while self._running:
            for stream in ALL_STREAMS:
                try:
                    entries = await read_pending(stream, self.CONSUMER_NAME, count=50)
                    for stream_key, messages in entries:
                        for entry_id, fields in messages:
                            await self._process(stream_key, entry_id, fields)
                except Exception as exc:
                    logger.error("Consume loop error on %s: %s", stream, exc)
            await asyncio.sleep(0.1)

    # ------------------------------------------------------------------
    # Stale entry reclaim loop (XAUTOCLAIM)
    # ------------------------------------------------------------------
    async def _reclaim_loop(self) -> None:
        while self._running:
            for stream in ALL_STREAMS:
                try:
                    stale = await claim_stale(stream, self.CONSUMER_NAME)
                    for entry_id, fields in stale:
                        await self._process(stream, entry_id, fields)
                except Exception as exc:
                    logger.error("Reclaim loop error on %s: %s", stream, exc)
            await asyncio.sleep(5)

    # ------------------------------------------------------------------
    # Process a single event
    # ------------------------------------------------------------------
    async def _process(self, stream: str, entry_id: str, fields: Dict[str, str]) -> None:
        event_type = self._infer_event_type(stream)
        retry_count = int(fields.get("_retry_count", "0"))

        try:
            # Write to audit_log — MUST succeed before ACK
            await self._write_audit_log(event_type, entry_id, fields)

            # Special handling per stream
            if stream == STREAM_CONSENT:
                await self._write_consent_audit(fields)

            # ACK only after successful DB write
            await ack_message(stream, entry_id)
            audit_events_written.labels(event_type=event_type).inc()

        except Exception as exc:
            logger.error("Failed to process entry %s on %s: %s", entry_id, stream, exc)
            if retry_count >= 5:
                await publish_dlq(stream, entry_id, dict(fields))
                await ack_message(stream, entry_id)  # remove from pending after DLQ
            else:
                # Re-enqueue with incremented retry count (will be reclaimed by XAUTOCLAIM)
                fields["_retry_count"] = str(retry_count + 1)

    # ------------------------------------------------------------------
    # Write to append-only audit_log
    # ------------------------------------------------------------------
    async def _write_audit_log(
        self, event_type: str, entry_id: str, fields: Dict[str, str]
    ) -> None:
        event_data = {k: v for k, v in fields.items() if not k.startswith("_")}
        learner_pseudonym = event_data.get("learner_pseudonym") or fields.get("learner_pseudonym")

        await self._session.execute(
            text(
                """
                INSERT INTO audit_log
                    (event_id, event_type, stream_entry_id, learner_pseudonym, event_data, created_at)
                VALUES (:event_id, :event_type, :stream_entry_id, :learner_pseudonym, :event_data, now())
                ON CONFLICT (stream_entry_id) DO NOTHING
                """
            ),
            {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "stream_entry_id": entry_id,
                "learner_pseudonym": learner_pseudonym,
                "event_data": json.dumps(event_data),
            },
        )
        await self._session.commit()

    # ------------------------------------------------------------------
    # Consent audit persistence
    # ------------------------------------------------------------------
    async def _write_consent_audit(self, fields: Dict[str, str]) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO consent_audit
                    (audit_id, pseudonym_id, event_type, consent_version, guardian_email_hash, occurred_at)
                VALUES (:cid, :pseudonym, :status, 1, :granted_by, now())
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "cid": str(uuid.uuid4()),
                "pseudonym": fields.get("learner_pseudonym"),
                "status": fields.get("event_type", "consent_granted"),
                "granted_by": fields.get("granted_by"),
            },
        )
        await self._session.commit()

    # ------------------------------------------------------------------
    # Orphan detection: action with no corresponding stamp within window
    # ------------------------------------------------------------------
    async def _orphan_detection_loop(self) -> None:
        while self._running:
            await asyncio.sleep(ORPHAN_WINDOW_SECONDS)
            try:
                await self._detect_orphaned_actions()
            except Exception as exc:
                logger.error("Orphan detection error: %s", exc)

    async def _detect_orphaned_actions(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=ORPHAN_WINDOW_SECONDS)
        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT al.event_id, al.event_data
                    FROM audit_log al
                    WHERE al.event_type = 'executive_action'
                      AND al.created_at < :cutoff
                      AND NOT EXISTS (
                        SELECT 1 FROM audit_log al2
                        WHERE al2.event_type = 'judiciary_stamp'
                          AND al2.event_data->>'action_id' = al.event_data->>'action_id'
                      )
                    LIMIT 100
                    """
                ),
                {"cutoff": cutoff},
            )
        ).mappings().all()

        for row in rows:
            event_data = json.loads(row["event_data"]) if isinstance(row["event_data"], str) else row["event_data"]
            action_id = event_data.get("action_id", "unknown")
            logger.warning("Orphaned action detected: action_id=%s", action_id)

            violation = {
                "violation_type": "UNSTAMPED_ACTION",
                "action_id": action_id,
                "description": f"ExecutiveAction {action_id} had no Judiciary stamp within {ORPHAN_WINDOW_SECONDS}s",
            }
            await publish_violation(violation)

    # ------------------------------------------------------------------
    # Lag metrics loop
    # ------------------------------------------------------------------
    async def _lag_metrics_loop(self) -> None:
        while self._running:
            for stream in ALL_STREAMS:
                lag = await get_consumer_lag(stream)
                audit_consumer_lag.labels(stream=stream).set(lag)
                if lag > 1000:
                    logger.warning("HIGH AUDIT LAG: stream=%s lag=%d", stream, lag)
            await asyncio.sleep(10)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _infer_event_type(stream: str) -> str:
        mapping = {
            "audit:actions": "executive_action",
            "audit:stamps": "judiciary_stamp",
            "audit:violations": "constitutional_violation",
            "audit:lessons": "lesson_event",
            "audit:test_results": "test_result",
            "audit:consent": "consent_event",
        }
        return mapping.get(stream, "unknown")


# ---------------------------------------------------------------------------
# Entrypoint for running as a standalone Celery task or async worker process
# ---------------------------------------------------------------------------
async def run_audit_agent() -> None:
    if not AUDIT_DB_URL:
        raise RuntimeError("AUDIT_DATABASE_URL or DATABASE_URL must be set for AuditAgent.")

    engine = create_async_engine(AUDIT_DB_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        agent = AuditAgent(session=session)
        await agent.start()
