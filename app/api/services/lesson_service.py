"""
PILLAR 2 — EXECUTIVE
EduBoost SA — Lesson Generation Service (Refactored)
Uses WorkerAgent base class to enforce JudiciaryStamp gate.
"""
from __future__ import annotations

import logging
import random
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.judiciary.base import ExecutiveAction, JudiciaryStampRef, WorkerAgent
from app.api.judiciary.provider_router import ProviderRouter
from app.api.judiciary.profiler import EtherPromptModifier
from app.api.services.prompt_manager import PromptManager
from app.api.core.config import settings

import redis.asyncio as redis_async
import json
import hashlib

# ============================================================================
# Lesson Caching System
# ============================================================================

class LessonCache:
    """Redis-backed TTL cache for generated lessons."""
    def __init__(self, redis_url: str, ttl_seconds: int = 3600):
        self._redis = redis_async.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds

    def _generate_key(
        self, subject: str, grade: int, topic: str, learner_id: str | None = None
    ) -> str:
        key_str = f"{learner_id or 'shared'}:{subject}:{grade}:{topic}"
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:32]
        return f"lesson:{learner_id or 'shared'}:{key_hash}"

    async def get(self, subject: str, grade: int, topic: str) -> Optional[Dict[str, Any]]:
        key = self._generate_key(subject, grade, topic)
        try:
            cached_data = await self._redis.get(key)
            if cached_data:
                return json.loads(cached_data)
        except Exception:
            pass
        return None

    async def set(self, subject: str, grade: int, topic: str, lesson: Dict[str, Any]) -> str:
        key = self._generate_key(subject, grade, topic)
        try:
            await self._redis.set(key, json.dumps(lesson), ex=self._ttl)
        except Exception:
            pass
        return key.replace("lesson:", "")

    async def clear(self) -> int:
        keys = await self._redis.keys("lesson:*")
        if keys:
            await self._redis.delete(*keys)
            return len(keys)
        return 0

    async def stats(self) -> dict:
        keys = await self._redis.keys("lesson:*")
        return {"entries": len(keys), "ttl_seconds": self._ttl, "status": "connected"}

_lesson_cache = LessonCache(redis_url=settings.REDIS_URL, ttl_seconds=3600)

def get_lesson_cache() -> LessonCache:
    return _lesson_cache

class LLMOutputValidationError(Exception):
    def __init__(self, message: str, errors: list | None = None, raw: str | None = None):
        super().__init__(message)
        self.errors = errors or []
        self.raw = (raw or "")[:500]

logger = logging.getLogger(__name__)

SA_THEMES = [
    "sharing food at a family braai",
    "buying sweets at a tuck shop",
    "counting animals on a game reserve",
    "travelling between SA cities",
    "growing a vegetable garden",
    "playing soccer on a dusty field",
    "going to a spaza shop",
    "collecting water at a communal tap",
]

GRADES = {
    0: "Grade R", 1: "Grade 1", 2: "Grade 2", 3: "Grade 3",
    4: "Grade 4", 5: "Grade 5", 6: "Grade 6", 7: "Grade 7",
}

class LessonService(WorkerAgent):
    """
    Generates AI-powered lessons.
    Stamp gate ensures every LLM call is Judiciary-approved before execution.
    """

    def __init__(
        self,
        session: AsyncSession,
        encryption_key: Optional[str] = None,
    ):
        super().__init__(
            agent_id="lesson-service",
            intent="generate_lesson",
            encryption_key=encryption_key,
        )
        self._session = session

    async def _build_action(self, **kwargs) -> ExecutiveAction:  # type: ignore[override]
        learner_pseudonym: str = kwargs["learner_pseudonym"]
        subject: str = kwargs["subject"]
        grade: int = kwargs["grade"]
        topic: str = kwargs["topic"]

        await self._assert_consent(learner_pseudonym, self._session)

        return ExecutiveAction(
            agent_id=self.agent_id,
            intent=self.intent,
            parameters={
                "subject": subject,
                "grade": grade,
                "topic": topic,
            },
            claimed_rules=[
                "POPIA-S11-DATA-MIN",
                "POPIA-S19-SECURITY",
                "CAPS-LESSON-SCOPE",
            ],
            learner_pseudonym=learner_pseudonym,
        )

    async def _execute(
        self, action: ExecutiveAction, stamp: JudiciaryStampRef, **kwargs
    ) -> Dict[str, Any]:
        self._assert_stamped()

        subject = action.parameters["subject"]
        grade = action.parameters["grade"]
        topic = action.parameters["topic"]
        learner_pseudonym = action.learner_pseudonym

        # Build prompt
        system_prompt, user_prompt = await self._build_prompts(subject, grade, topic)

        # Apply Ether prompt modification (Pillar 5)
        modifier = EtherPromptModifier(self._session)
        modified_prompt = await modifier.apply(user_prompt, learner_pseudonym)

        # Call LLM via ProviderRouter (Infrastructure)
        router = ProviderRouter()
        raw_content = await router.complete(
            prompt=modified_prompt,
            system_prompt=system_prompt,
            action_id=action.action_id,
            stamp_id=stamp.stamp_id,
        )

        lesson_result = {
            "action_id": action.action_id,
            "stamp_id": stamp.stamp_id,
            "learner_pseudonym": learner_pseudonym,
            "subject": subject,
            "grade": grade,
            "topic": topic,
            "content": raw_content,
        }
        self._validate_lesson_output(lesson_result)

        # Persist to DB
        await self._persist_lesson(lesson_result)
        return lesson_result

    async def _build_prompts(self, subject: str, grade: int, topic: str) -> Tuple[str, str]:
        grade_name = GRADES.get(grade, f"Grade {grade}")
        sa_theme = random.choice(SA_THEMES)

        try:
            system_prompt = PromptManager.get_template("lesson_generation", "system")
            user_template = PromptManager.get_template("lesson_generation", "user")
            
            user_prompt = user_template.format(
                duration_minutes=15,
                modality="interactive",
                grade=grade_name,
                subject_label=subject,
                subject_code=subject, # Simplify for now
                topic=topic,
                home_language="English",
                learning_style_primary="visual",
                sa_theme=sa_theme,
                mastery_prior=0.5,
                gap_instruction="",
            )
        except Exception:
            # Fallback
            system_prompt = f"You are a South African CAPS-aligned educational assistant for {grade_name}."
            user_prompt = f"Topic: {topic}. Subject: {subject}. Theme: {sa_theme}."

        return system_prompt, user_prompt

    async def _persist_lesson(self, result: Dict[str, Any]) -> None:
        await self._session.execute(
            text(
                """
                INSERT INTO lesson_results
                    (action_id, stamp_id, learner_pseudonym, subject, grade, topic, content, created_at)
                VALUES (:action_id, :stamp_id, :learner_pseudonym, :subject, :grade, :topic, :content, now())
                """
            ),
            result,
        )
        await self._session.commit()

    def _validate_lesson_output(self, lesson: Dict[str, Any]) -> None:
        missing = [
            key
            for key in ("subject", "grade", "topic", "content")
            if lesson.get(key) in (None, "")
        ]
        if missing:
            raise LLMOutputValidationError(
                "Generated lesson is missing required fields",
                errors=missing,
                raw=str(lesson),
            )

# Backward compatibility procedural wrapper
async def generate_lesson(
    session: AsyncSession,
    learner_id: str,
    subject: str,
    grade: int,
    topic: str
) -> Dict[str, Any]:
    service = LessonService(session)
    return await service.run(
        learner_pseudonym=learner_id,
        subject=subject,
        grade=grade,
        topic=topic
    )
