"""
PILLAR 4 — FOURTH ESTATE
Redis Streams topology:
  - Stream keys, consumer group setup, XADD helpers, XAUTOCLAIM for stale entries.
  - Architectural recommendation #5: proper consumer group design, XACK after DB write, DLQ.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# Stream keys
# ---------------------------------------------------------------------------
STREAM_ACTIONS = "audit:actions"
STREAM_STAMPS = "audit:stamps"
STREAM_VIOLATIONS = "audit:violations"
STREAM_LESSONS = "audit:lessons"
STREAM_TEST_RESULTS = "audit:test_results"
STREAM_CONSENT = "audit:consent"
STREAM_DLQ = "audit:dlq"

ALL_STREAMS = [
    STREAM_ACTIONS,
    STREAM_STAMPS,
    STREAM_VIOLATIONS,
    STREAM_LESSONS,
    STREAM_TEST_RESULTS,
    STREAM_CONSENT,
]

CONSUMER_GROUP = "auditAgent"
STREAM_MAXLEN = int(os.environ.get("AUDIT_STREAM_MAXLEN", "100000"))
PENDING_CLAIM_TIMEOUT_MS = int(os.environ.get("PENDING_CLAIM_TIMEOUT_MS", "60000"))
MAX_RETRY_COUNT = int(os.environ.get("AUDIT_MAX_RETRY", "5"))


# ---------------------------------------------------------------------------
# Connection pool (shared singleton)
# ---------------------------------------------------------------------------
_redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_pool


# ---------------------------------------------------------------------------
# Stream initialisation — call once at startup
# ---------------------------------------------------------------------------
async def initialise_streams() -> None:
    """
    Create all consumer groups if they don't exist.
    Uses '$' as start ID so we don't replay historical events on first boot.
    """
    r = await get_redis()
    for stream in ALL_STREAMS:
        try:
            await r.xgroup_create(stream, CONSUMER_GROUP, id="$", mkstream=True)
            logger.info("Consumer group created: stream=%s group=%s", stream, CONSUMER_GROUP)
        except aioredis.ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                logger.debug("Consumer group already exists: stream=%s", stream)
            else:
                raise

        # Set retention cap
        await r.xtrim(stream, maxlen=STREAM_MAXLEN, approximate=True)
        logger.debug("MAXLEN set: stream=%s maxlen=%d", stream, STREAM_MAXLEN)


# ---------------------------------------------------------------------------
# Publish helpers — called by WorkerAgents, JudiciaryService, AuditAgent
# ---------------------------------------------------------------------------
async def publish_action(action_dict: Dict[str, Any]) -> str:
    return await _publish(STREAM_ACTIONS, action_dict)


async def publish_stamp(stamp_dict: Dict[str, Any]) -> str:
    return await _publish(STREAM_STAMPS, stamp_dict)


async def publish_violation(violation_dict: Dict[str, Any]) -> str:
    return await _publish(STREAM_VIOLATIONS, violation_dict)


async def publish_lesson(lesson_dict: Dict[str, Any]) -> str:
    return await _publish(STREAM_LESSONS, lesson_dict)


async def publish_test_result(result_dict: Dict[str, Any]) -> str:
    return await _publish(STREAM_TEST_RESULTS, result_dict)


async def publish_consent_event(consent_dict: Dict[str, Any]) -> str:
    return await _publish(STREAM_CONSENT, consent_dict)


async def publish_dlq(original_stream: str, entry_id: str, payload: Dict[str, Any]) -> str:
    dlq_entry = {
        "original_stream": original_stream,
        "original_entry_id": entry_id,
        "payload": json.dumps(payload),
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    entry_id = await _publish(STREAM_DLQ, dlq_entry)
    logger.warning(
        "Event moved to DLQ: stream=%s original_id=%s dlq_id=%s",
        original_stream, entry_id, entry_id,
    )
    return entry_id


async def _publish(stream: str, data: Dict[str, Any]) -> str:
    r = await get_redis()
    # Flatten nested dicts to strings for Redis Stream compatibility
    flat = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in data.items()}
    flat["_published_at"] = datetime.now(timezone.utc).isoformat()
    entry_id = await r.xadd(stream, flat, maxlen=STREAM_MAXLEN, approximate=True)
    return entry_id


# ---------------------------------------------------------------------------
# Consumer helpers — used by AuditAgent
# ---------------------------------------------------------------------------
async def read_pending(
    stream: str, consumer_name: str, count: int = 50
) -> list:
    """Read messages assigned to this consumer that haven't been ACKed."""
    r = await get_redis()
    entries = await r.xreadgroup(
        groupname=CONSUMER_GROUP,
        consumername=consumer_name,
        streams={stream: ">"},
        count=count,
        block=1000,
    )
    return entries or []


async def claim_stale(
    stream: str, consumer_name: str, count: int = 10
) -> list:
    """Claim stale pending entries that have been idle for PENDING_CLAIM_TIMEOUT_MS."""
    r = await get_redis()
    try:
        result = await r.xautoclaim(
            stream,
            CONSUMER_GROUP,
            consumer_name,
            min_idle_time=PENDING_CLAIM_TIMEOUT_MS,
            start_id="0-0",
            count=count,
        )
        # xautoclaim returns (next-start-id, entries, deleted-ids)
        return result[1] if result else []
    except Exception as exc:
        logger.warning("xautoclaim failed on %s: %s", stream, exc)
        return []


async def ack_message(stream: str, entry_id: str) -> None:
    """Acknowledge a message ONLY after the DB write has committed."""
    r = await get_redis()
    await r.xack(stream, CONSUMER_GROUP, entry_id)


async def get_consumer_lag(stream: str) -> int:
    """Return the number of pending (unprocessed) messages in the consumer group."""
    r = await get_redis()
    try:
        info = await r.xinfo_groups(stream)
        for group in info:
            if group["name"] == CONSUMER_GROUP:
                return group.get("pending", 0)
    except Exception:
        pass
    return 0
