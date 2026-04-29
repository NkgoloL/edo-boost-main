"""
PILLAR 3 — JUDICIARY
JudiciaryService: full review pipeline.
  1. Fast-path deterministic checks (regex/keyword) — short-circuit on obvious violations.
  2. Cache lookup — identical (agent_id, intent, rules_hash) within TTL returns cached stamp.
  3. LLM review — structured prompt to Claude, parse APPROVED/REJECTED.
  4. Persist stamp + insert ConstitutionalViolation on REJECTED.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from anthropic import AsyncAnthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    ConstitutionalViolationORM,
    ExecutiveActionIn,
    JudiciaryStamp,
    JudiciaryStampORM,
    StampVerdict,
)

logger = logging.getLogger(__name__)

ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
STAMP_CACHE_TTL_SECONDS = int(os.environ.get("JUDICIARY_CACHE_TTL", "300"))

# ---------------------------------------------------------------------------
# Fast-path PII patterns
# ---------------------------------------------------------------------------
_PII_PATTERNS = [
    re.compile(r"\b\d{13}\b"),                                  # SA ID number
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"\b(0[6-8]\d{8})\b"),                           # SA mobile
    re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),   # credit card
]

_UNDER_13_FLAG = "UNDER_13"
_PII_VIOLATION_TYPE = "PII_IN_PROMPT"


class JudiciaryService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._anthropic = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def review(self, action: ExecutiveActionIn) -> JudiciaryStamp:
        """Full review pipeline. Returns a JudiciaryStamp."""

        # 1. Fast-path checks
        fast_rejection = await self._fast_path_check(action)
        if fast_rejection:
            stamp = await self._issue_stamp(
                action, StampVerdict.REJECTED, [], fast_rejection, "fast-path"
            )
            await self._record_violation(action, stamp, _PII_VIOLATION_TYPE, fast_rejection)
            return stamp

        # 2. Cache lookup
        rules_hash = self._compute_rules_hash(action.claimed_rules)
        cached = await self._cache_lookup(action.agent_id, action.intent, rules_hash)
        if cached:
            logger.debug("Judiciary cache hit: action=%s", action.action_id)
            return cached._replace(stamp_id=str(uuid.uuid4()), action_id=action.action_id)

        # 3. Retrieve active ConstitutionalRules for context
        active_rules = await self._get_relevant_rules(action.claimed_rules)

        # 4. LLM review
        verdict, reason, model_version = await self._llm_review(action, active_rules)

        # 5. Issue and persist stamp
        stamp = await self._issue_stamp(action, verdict, action.claimed_rules, reason, model_version)

        # 6. Record violation on rejection
        if verdict == StampVerdict.REJECTED:
            await self._record_violation(action, stamp, "LLM_REVIEW_REJECTED", reason)

        # 7. Cache approved stamps
        if verdict == StampVerdict.APPROVED:
            await self._cache_store(action.agent_id, action.intent, rules_hash, stamp)

        return stamp

    async def get_stamp(self, action_id: str) -> Optional[JudiciaryStamp]:
        row = (
            await self._session.execute(
                text("SELECT * FROM judiciary_stamps WHERE action_id = :a ORDER BY created_at DESC LIMIT 1"),
                {"a": action_id},
            )
        ).mappings().first()
        if not row:
            return None
        return JudiciaryStamp(
            stamp_id=row["stamp_id"],
            action_id=row["action_id"],
            verdict=StampVerdict(row["verdict"]),
            rules_checked=json.loads(row["rules_checked"]),
            reason=row["reason"],
            reviewer_model_version=row["reviewer_model_version"],
        )

    # ------------------------------------------------------------------
    # Fast-path
    # ------------------------------------------------------------------
    async def _fast_path_check(self, action: ExecutiveActionIn) -> Optional[str]:
        """Returns rejection reason string if fast-path violation, else None."""
        payload_str = json.dumps(action.parameters)

        for pattern in _PII_PATTERNS:
            if pattern.search(payload_str):
                return f"PII pattern detected in action parameters: {pattern.pattern[:40]}"

        if action.parameters.get("learner_age") and int(action.parameters["learner_age"]) < 13:
            flag = action.parameters.get("under_13_flag")
            if flag != _UNDER_13_FLAG:
                return "Under-13 learner flag not set — POPIA parental consent gate required."

        return None

    # ------------------------------------------------------------------
    # LLM review
    # ------------------------------------------------------------------
    async def _llm_review(
        self, action: ExecutiveActionIn, rules: List[dict]
    ) -> tuple[StampVerdict, str, str]:
        rules_text = "\n".join(
            f"- [{r['rule_id']}] {r['rule_text'][:200]}" for r in rules
        )
        prompt = f"""You are the EduBoost Judiciary — a constitutional compliance firewall 
for a POPIA-compliant South African educational platform serving children.

Review the following ExecutiveAction for compliance with the cited rules.

## ExecutiveAction
- Agent: {action.agent_id}
- Intent: {action.intent}
- Parameters: {json.dumps(action.parameters, indent=2)}
- Learner Pseudonym Present: {bool(action.learner_pseudonym)}
- Claimed Rules: {action.claimed_rules}

## Active Constitutional Rules
{rules_text if rules_text else "No specific rules retrieved."}

## Task
Respond ONLY with a JSON object with exactly these fields:
{{
  "verdict": "APPROVED" | "REJECTED",
  "reason": "<concise explanation, max 200 chars>",
  "rules_checked": ["rule_id_1", "rule_id_2"]
}}

REJECT if: PII is present, consent is absent for a learner action, the action scope 
exceeds the claimed rules, or the intent violates POPIA data minimisation principles.
"""
        try:
            response = await self._anthropic.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            # Strip markdown fences
            raw = re.sub(r"```(?:json)?|```", "", raw).strip()
            data = json.loads(raw)
            verdict = StampVerdict(data.get("verdict", "REJECTED"))
            reason = data.get("reason", "")
            return verdict, reason, ANTHROPIC_MODEL
        except Exception as exc:
            logger.error("LLM review failed: %s", exc)
            # Fail closed
            return StampVerdict.REJECTED, f"LLM review error: {exc}", "error"

    # ------------------------------------------------------------------
    # Stamp persistence
    # ------------------------------------------------------------------
    async def _issue_stamp(
        self,
        action: ExecutiveActionIn,
        verdict: StampVerdict,
        rules_checked: List[str],
        reason: str,
        model_version: str,
    ) -> JudiciaryStamp:
        stamp = JudiciaryStamp(
            action_id=action.action_id,
            verdict=verdict,
            rules_checked=rules_checked,
            reason=reason,
            reviewer_model_version=model_version,
        )
        orm = JudiciaryStampORM(
            stamp_id=stamp.stamp_id,
            action_id=stamp.action_id,
            verdict=verdict.value,
            rules_checked=json.dumps(rules_checked),
            reason=reason,
            reviewer_model_version=model_version,
        )
        self._session.add(orm)
        await self._session.commit()
        return stamp

    async def _record_violation(
        self,
        action: ExecutiveActionIn,
        stamp: JudiciaryStamp,
        violation_type: str,
        description: str,
    ) -> None:
        v = ConstitutionalViolationORM(
            violation_id=str(uuid.uuid4()),
            action_id=action.action_id,
            stamp_id=stamp.stamp_id,
            agent_id=action.agent_id,
            violation_type=violation_type,
            description=description[:1000],
            learner_pseudonym=action.learner_pseudonym,
        )
        self._session.add(v)
        await self._session.commit()

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------
    def _compute_rules_hash(self, rule_ids: List[str]) -> str:
        return hashlib.sha256("|".join(sorted(rule_ids)).encode()).hexdigest()[:16]

    async def _cache_lookup(
        self, agent_id: str, intent: str, rules_hash: str
    ) -> Optional[JudiciaryStamp]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=STAMP_CACHE_TTL_SECONDS)
        row = (
            await self._session.execute(
                text(
                    """
                    SELECT stamp_id, rules_checked, reason, reviewer_model_version, created_at
                    FROM judiciary_stamps js
                    WHERE js.verdict = 'APPROVED'
                      AND created_at > :cutoff
                      AND EXISTS (
                        SELECT 1 FROM judiciary_stamp_cache jsc
                        WHERE jsc.stamp_id = js.stamp_id
                          AND jsc.agent_id = :ag
                          AND jsc.intent = :i
                          AND jsc.rules_hash = :rh
                      )
                    ORDER BY created_at DESC LIMIT 1
                    """
                ),
                {"cutoff": cutoff, "ag": agent_id, "i": intent, "rh": rules_hash},
            )
        ).mappings().first()

        if not row:
            return None
        return JudiciaryStamp(
            stamp_id=row["stamp_id"],
            action_id="cached",
            verdict=StampVerdict.APPROVED,
            rules_checked=json.loads(row["rules_checked"]),
            reason=row["reason"],
            reviewer_model_version=row["reviewer_model_version"],
        )

    async def _cache_store(
        self, agent_id: str, intent: str, rules_hash: str, stamp: JudiciaryStamp
    ) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO judiciary_stamp_cache (stamp_id, agent_id, intent, rules_hash, created_at)
                VALUES (:sid, :ag, :i, :rh, now())
                ON CONFLICT DO NOTHING
                """
            ),
            {"sid": stamp.stamp_id, "ag": agent_id, "i": intent, "rh": rules_hash},
        )
        await self._session.commit()

    # ------------------------------------------------------------------
    # Rule retrieval
    # ------------------------------------------------------------------
    async def _get_relevant_rules(self, rule_ids: List[str]) -> List[dict]:
        if not rule_ids:
            return []
        stmt = text(
            """
            SELECT DISTINCT ON (rule_id)
                rule_id, rule_text, source_document
            FROM constitutional_rules
            WHERE rule_id = ANY(:ids) AND effective_date <= CURRENT_DATE
            ORDER BY rule_id, effective_date DESC
            """
        )
        rows = (await self._session.execute(stmt, {"ids": rule_ids})).mappings().all()
        return [dict(r) for r in rows]
