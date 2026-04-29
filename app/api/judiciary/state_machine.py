"""
ORCHESTRATOR — Formal Finite State Machine
Manages learner session lifecycle across all five pillars.
Architectural recommendation #10: every state transition emits an audit event.
Holds fast state in Redis; persists durable transitions to Postgres.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------
class SessionState(str, Enum):
    IDLE = "IDLE"
    DIAGNOSTIC_IN_PROGRESS = "DIAGNOSTIC_IN_PROGRESS"
    DIAGNOSTIC_COMPLETE = "DIAGNOSTIC_COMPLETE"
    LESSON_IN_PROGRESS = "LESSON_IN_PROGRESS"
    LESSON_COMPLETE = "LESSON_COMPLETE"
    ASSESSMENT_IN_PROGRESS = "ASSESSMENT_IN_PROGRESS"
    ASSESSMENT_COMPLETE = "ASSESSMENT_COMPLETE"
    PLAN_GENERATION = "PLAN_GENERATION"
    PLAN_ACTIVE = "PLAN_ACTIVE"
    SUSPENDED = "SUSPENDED"   # consent revoked or deletion requested
    ARCHIVED = "ARCHIVED"     # retention period elapsed


# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: dict[SessionState, list[SessionState]] = {
    SessionState.IDLE: [SessionState.DIAGNOSTIC_IN_PROGRESS, SessionState.LESSON_IN_PROGRESS],
    SessionState.DIAGNOSTIC_IN_PROGRESS: [SessionState.DIAGNOSTIC_COMPLETE, SessionState.SUSPENDED],
    SessionState.DIAGNOSTIC_COMPLETE: [SessionState.LESSON_IN_PROGRESS, SessionState.PLAN_GENERATION],
    SessionState.LESSON_IN_PROGRESS: [SessionState.LESSON_COMPLETE, SessionState.SUSPENDED],
    SessionState.LESSON_COMPLETE: [SessionState.ASSESSMENT_IN_PROGRESS, SessionState.IDLE],
    SessionState.ASSESSMENT_IN_PROGRESS: [SessionState.ASSESSMENT_COMPLETE, SessionState.SUSPENDED],
    SessionState.ASSESSMENT_COMPLETE: [SessionState.LESSON_IN_PROGRESS, SessionState.PLAN_GENERATION, SessionState.IDLE],
    SessionState.PLAN_GENERATION: [SessionState.PLAN_ACTIVE, SessionState.SUSPENDED],
    SessionState.PLAN_ACTIVE: [SessionState.LESSON_IN_PROGRESS, SessionState.DIAGNOSTIC_IN_PROGRESS, SessionState.SUSPENDED],
    SessionState.SUSPENDED: [SessionState.ARCHIVED],
    SessionState.ARCHIVED: [],
}

# Any state can transition to SUSPENDED
for _state in list(VALID_TRANSITIONS.keys()):
    if SessionState.SUSPENDED not in VALID_TRANSITIONS[_state]:
        VALID_TRANSITIONS[_state].append(SessionState.SUSPENDED)


class InvalidTransitionError(ValueError):
    pass


class ConsentSuspendedError(RuntimeError):
    """Raised when attempting to use a SUSPENDED session."""


# ---------------------------------------------------------------------------
# SessionOrchestrator
# ---------------------------------------------------------------------------
class SessionOrchestrator:
    """
    Manages the learner session state machine.
    Fast state cached in Redis; durable transitions logged to Postgres and audit stream.
    """

    def __init__(self, session: AsyncSession):
        self._db = session
        self._redis = None  # set lazily

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            import os
            self._redis = aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        return self._redis

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def get_state(self, learner_pseudonym: str) -> SessionState:
        """Return current session state, preferring Redis cache."""
        r = await self._get_redis()
        cached = await r.get(f"session_state:{learner_pseudonym}")
        if cached:
            return SessionState(cached)

        # Fallback to Postgres
        row = (
            await self._db.execute(
                text(
                    "SELECT state FROM session_states WHERE learner_pseudonym = :p "
                    "ORDER BY updated_at DESC LIMIT 1"
                ),
                {"p": learner_pseudonym},
            )
        ).first()
        state = SessionState(row[0]) if row else SessionState.IDLE
        await r.setex(f"session_state:{learner_pseudonym}", 3600, state.value)
        return state

    async def transition(
        self,
        learner_pseudonym: str,
        target: SessionState,
        metadata: Optional[dict] = None,
    ) -> SessionState:
        """
        Attempt a state transition. Raises InvalidTransitionError if illegal.
        Emits an audit event on every successful transition.
        """
        current = await self.get_state(learner_pseudonym)

        if target not in VALID_TRANSITIONS.get(current, []):
            raise InvalidTransitionError(
                f"Cannot transition {learner_pseudonym}: {current} → {target}. "
                f"Valid targets: {[s.value for s in VALID_TRANSITIONS.get(current, [])]}"
            )

        if current == SessionState.SUSPENDED and target != SessionState.ARCHIVED:
            raise ConsentSuspendedError(
                f"Learner {learner_pseudonym} session is SUSPENDED. "
                "Only archival is permitted."
            )

        # Persist transition
        await self._persist_transition(learner_pseudonym, current, target, metadata or {})

        # Update Redis cache
        r = await self._get_redis()
        await r.setex(f"session_state:{learner_pseudonym}", 3600, target.value)

        # Emit audit event
        await self._emit_transition_event(learner_pseudonym, current, target, metadata or {})

        logger.info(
            "Session transition: learner=%s %s → %s", learner_pseudonym, current.value, target.value
        )
        return target

    async def assert_state_allows(
        self, learner_pseudonym: str, required_state: SessionState
    ) -> None:
        """
        Assert that a WorkerAgent's intended action is valid for the current state.
        Prevents race conditions.
        """
        current = await self.get_state(learner_pseudonym)
        if current == SessionState.SUSPENDED:
            raise ConsentSuspendedError(f"Learner {learner_pseudonym} session is SUSPENDED.")
        if current == SessionState.ARCHIVED:
            raise InvalidTransitionError(f"Learner {learner_pseudonym} session is ARCHIVED.")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    async def _persist_transition(
        self,
        pseudonym: str,
        from_state: SessionState,
        to_state: SessionState,
        metadata: dict,
    ) -> None:
        await self._db.execute(
            text(
                """
                INSERT INTO session_states
                    (learner_pseudonym, state, previous_state, metadata, updated_at)
                VALUES (:p, :s, :prev, :meta, now())
                ON CONFLICT (learner_pseudonym) DO UPDATE SET
                    state = EXCLUDED.state,
                    previous_state = EXCLUDED.previous_state,
                    metadata = EXCLUDED.metadata,
                    updated_at = now()
                """
            ),
            {
                "p": pseudonym,
                "s": to_state.value,
                "prev": from_state.value,
                "meta": json.dumps(metadata),
            },
        )
        await self._db.commit()

    async def _emit_transition_event(
        self,
        pseudonym: str,
        from_state: SessionState,
        to_state: SessionState,
        metadata: dict,
    ) -> None:
        try:
            from app.api.pillar_4_fourth_estate.streams import publish_action

            await publish_action({
                "event_type": "session_transition",
                "learner_pseudonym": pseudonym,
                "from_state": from_state.value,
                "to_state": to_state.value,
                "metadata": json.dumps(metadata),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            logger.error("Failed to emit transition event: %s", exc)
