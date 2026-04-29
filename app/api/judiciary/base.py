"""
PILLAR 2 — EXECUTIVE
WorkerAgent abstract base class + ExecutiveAction model.
No worker may call an LLM or write to the DB unless self._stamped is True.
Architectural recommendation: stamp gate blocks execution until JudiciaryStamp received.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class UnauthorizedExecutionError(RuntimeError):
    """Raised when a WorkerAgent attempts execution without a valid stamp."""


class ConsentViolationError(RuntimeError):
    """Raised when a learner's consent_status is not ACTIVE."""


# ---------------------------------------------------------------------------
# ExecutiveAction — payload emitted by every WorkerAgent before execution
# ---------------------------------------------------------------------------
class ExecutiveAction(BaseModel):
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    intent: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    claimed_rules: List[str] = Field(
        default_factory=list,
        description="List of ConstitutionalRule rule_ids this action claims to comply with",
    )
    learner_pseudonym: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signature: str = Field(default="", description="HMAC-SHA256 of canonical payload")

    model_config = {"frozen": True}

    def sign(self, encryption_key: str) -> "ExecutiveAction":
        """Return a new instance with the HMAC signature populated."""
        sig = self._compute_signature(encryption_key)
        return self.model_copy(update={"signature": sig})

    def verify_signature(self, encryption_key: str) -> bool:
        expected = self._compute_signature(encryption_key)
        return hmac.compare_digest(self.signature, expected)

    def _compute_signature(self, key: str) -> str:
        payload = (
            f"{self.action_id}|{self.agent_id}|{self.intent}|"
            f"{self.learner_pseudonym or ''}|{self.timestamp.isoformat()}"
        )
        return hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# JudiciaryStamp — returned by JudiciaryService after review
# ---------------------------------------------------------------------------
class JudiciaryStampRef(BaseModel):
    """Lightweight reference; full model lives in pillar_3_judiciary/models.py"""
    stamp_id: str
    action_id: str
    verdict: str  # "APPROVED" | "REJECTED"
    rules_checked: List[str] = Field(default_factory=list)
    reason: str = ""
    reviewer_model_version: str = ""


# ---------------------------------------------------------------------------
# WorkerAgent abstract base
# ---------------------------------------------------------------------------
class WorkerAgent(ABC):
    """
    All service classes that touch learner data or call an LLM must extend this.
    Execution contract:
      1. Build an ExecutiveAction via _build_action()
      2. Call await _stamp_gate(action) — blocks until JudiciaryStamp is received
      3. If stamp.verdict == APPROVED, execute; otherwise raise UnauthorizedExecutionError
    """

    def __init__(self, agent_id: str, intent: str, encryption_key: Optional[str] = None):
        self.agent_id = agent_id
        self.intent = intent
        self._encryption_key = encryption_key or os.environ.get("ENCRYPTION_KEY", "")
        self._stamped: bool = False
        self._current_stamp: Optional[JudiciaryStampRef] = None

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------
    @abstractmethod
    async def _build_action(self, **kwargs) -> ExecutiveAction:
        """Construct the ExecutiveAction describing the intended operation."""

    @abstractmethod
    async def _execute(self, action: ExecutiveAction, stamp: JudiciaryStampRef, **kwargs) -> Any:
        """Run the actual operation. Only called after stamp is verified."""

    # ------------------------------------------------------------------
    # Gate
    # ------------------------------------------------------------------
    async def _stamp_gate(self, action: ExecutiveAction) -> JudiciaryStampRef:
        """
        Submit action to JudiciaryService and block until a stamp is returned.
        Raises UnauthorizedExecutionError if verdict is REJECTED or stamp is invalid.
        """
        from app.api.judiciary_client import JudiciaryClient  # lazy import to avoid cycles

        # Verify HMAC integrity before sending
        if self._encryption_key and not action.verify_signature(self._encryption_key):
            raise UnauthorizedExecutionError(
                f"ExecutiveAction {action.action_id} has invalid HMAC signature."
            )

        client = JudiciaryClient()
        stamp = await client.review(action)

        if stamp.verdict != "APPROVED":
            raise UnauthorizedExecutionError(
                f"Action {action.action_id} REJECTED by Judiciary: {stamp.reason}"
            )

        self._stamped = True
        self._current_stamp = stamp
        return stamp

    # ------------------------------------------------------------------
    # Consent check (enforced before stamp gate)
    # ------------------------------------------------------------------
    async def _assert_consent(self, learner_pseudonym: str, session) -> None:  # noqa: ANN001
        """Verify learner has ACTIVE parental consent. Raises ConsentViolationError if not."""
        from sqlalchemy import text

        row = (
            await session.execute(
                text(
                    "SELECT consent_status FROM consent_log "
                    "WHERE learner_pseudonym = :p AND revoked_at IS NULL "
                    "ORDER BY granted_at DESC LIMIT 1"
                ),
                {"p": learner_pseudonym},
            )
        ).first()

        if row is None or row[0] != "ACTIVE":
            raise ConsentViolationError(
                f"Learner {learner_pseudonym} does not have ACTIVE parental consent. "
                "Processing is blocked until consent is granted."
            )

    # ------------------------------------------------------------------
    # Safe execution entry point
    # ------------------------------------------------------------------
    async def run(self, **kwargs) -> Any:
        """
        Public entry point.  Enforces the full stamp-gate contract.
        Subclasses must NOT override this — override _build_action and _execute.
        """
        action = await self._build_action(**kwargs)

        # Sign the action
        if self._encryption_key:
            action = action.sign(self._encryption_key)

        stamp = await self._stamp_gate(action)
        return await self._execute(action, stamp, **kwargs)

    # ------------------------------------------------------------------
    # DB/LLM guard methods — call these instead of raw clients
    # ------------------------------------------------------------------
    def _assert_stamped(self) -> None:
        """Call at the start of any DB write or LLM call within _execute."""
        if not self._stamped:
            raise UnauthorizedExecutionError(
                f"WorkerAgent {self.agent_id} attempted execution without a valid stamp."
            )
