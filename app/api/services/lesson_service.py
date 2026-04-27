"""
EduBoost SA — Lesson Generation Service
Builds CAPS-aligned, SA-contextual lessons using the Inference Gateway.
No PII flows into prompts.
"""
import hashlib
import json
import random
import time
from typing import Optional, Tuple
from pydantic import BaseModel, Field, ValidationError
import redis.asyncio as redis_async
from sqlalchemy import text

from app.api.core.config import settings
from app.api.core.database import AsyncSessionFactory
from app.api.services.inference_gateway import call_llm, parse_json_response
import structlog

log = structlog.get_logger()


# ============================================================================
# Lesson Caching System
# ============================================================================

class LessonCache:
    """Redis-backed TTL cache for generated lessons."""
    
    def __init__(self, redis_url: str, ttl_seconds: int = 3600):
        self._redis = redis_async.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds
    
    def _generate_key(self, params: "LessonParams") -> str:
        """Generate cache key from lesson parameters."""
        key_data = {
            "grade": params.grade,
            "subject_code": params.subject_code,
            "subject_label": params.subject_label,
            "topic": params.topic,
            "home_language": params.home_language,
            "learning_style_primary": params.learning_style_primary,
            "mastery_prior": params.mastery_prior,
            "has_gap": params.has_gap,
            "gap_grade": params.gap_grade,
            "sa_theme": params.sa_theme,
        }
        key_str = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:32]
        return f"lesson:{key_hash}"
    
    async def get(self, params: "LessonParams") -> Optional[Tuple["GeneratedLesson", str]]:
        """Get cached lesson if available and not expired."""
        key = self._generate_key(params)
        try:
            cached_data = await self._redis.get(key)
            if cached_data:
                log.info("lesson_cache.hit", key=key)
                # Return both the lesson and the ID (stripping 'lesson:' prefix)
                return GeneratedLesson.model_validate_json(cached_data), key.replace("lesson:", "")
        except Exception as e:
            log.warning("lesson_cache.get_error", error=str(e), key=key)
        return None
    
    async def set(self, params: "LessonParams", lesson: "GeneratedLesson") -> str:
        """Cache a generated lesson. Returns the generated lesson ID."""
        key = self._generate_key(params)
        try:
            await self._redis.set(key, lesson.model_dump_json(), ex=self._ttl)
            log.info("lesson_cache.stored", key=key, topic=params.topic)
        except Exception as e:
            log.warning("lesson_cache.set_error", error=str(e), key=key)
        return key.replace("lesson:", "")
    
    async def clear(self) -> int:
        """Clear all cached lessons. Returns count of entries cleared."""
        try:
            keys = await self._redis.keys("lesson:*")
            if keys:
                await self._redis.delete(*keys)
                log.info("lesson_cache.cleared", count=len(keys))
                return len(keys)
            return 0
        except Exception as e:
            log.warning("lesson_cache.clear_error", error=str(e))
            return 0
    
    async def stats(self) -> dict:
        """Get cache statistics."""
        try:
            keys = await self._redis.keys("lesson:*")
            return {
                "entries": len(keys),
                "ttl_seconds": self._ttl,
                "status": "connected"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Global cache instance
_lesson_cache = LessonCache(redis_url=settings.REDIS_URL, ttl_seconds=3600)


def get_lesson_cache() -> LessonCache:
    """Get the global lesson cache instance."""
    return _lesson_cache


class LLMOutputValidationError(Exception):
    """
    Raised when LLM output fails Pydantic schema validation
    (Phase 1, item #6). Routers should map this to HTTP 422.
    """

    def __init__(self, message: str, errors: list | None = None, raw: str | None = None):
        super().__init__(message)
        self.errors = errors or []
        self.raw = (raw or "")[:500]

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

GRADES = {0: "Grade R", 1: "Grade 1", 2: "Grade 2", 3: "Grade 3",
          4: "Grade 4", 5: "Grade 5", 6: "Grade 6", 7: "Grade 7"}

LEARNING_STYLES = ["visual", "auditory", "kinesthetic"]


class LessonParams(BaseModel):
    """Anonymised pedagogical parameters — safe to pass to LLM."""
    grade: int = Field(ge=0, le=7)
    subject_code: str
    subject_label: str
    topic: str
    home_language: str = "English"
    learning_style_primary: str = "visual"
    mastery_prior: float = Field(default=0.5, ge=0.0, le=1.0)
    has_gap: bool = False
    gap_grade: Optional[int] = None
    sa_theme: Optional[str] = None


class GeneratedLesson(BaseModel):
    title: str
    story_hook: str
    visual_anchor: str = ""
    steps: list
    practice: list
    try_it: Optional[dict] = None
    xp: int = 35
    badge: Optional[str] = None


async def build_lesson_prompts(params: LessonParams) -> Tuple[str, str]:
    """Build LLM prompts from anonymised lesson parameters only."""
    grade_name = GRADES.get(params.grade, "Grade 3")
    sa_theme = params.sa_theme or random.choice(SA_THEMES)
    style = params.learning_style_primary

    difficulty_note = ""
    if params.has_gap and params.gap_grade is not None:
        gap_name = GRADES.get(params.gap_grade, grade_name)
        difficulty_note = (
            f"NOTE: This learner has a knowledge gap at {gap_name} level. "
            f"Start from {gap_name} fundamentals before progressing to {grade_name} content."
        )

    # Fetch templates from DB
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text("SELECT system_prompt, user_prompt_template FROM prompt_templates WHERE template_type = 'lesson_generation' AND is_active = TRUE LIMIT 1")
        )
        row = result.mappings().first()
    
    if not row:
        raise ValueError("Lesson generation prompt template not found in DB")
        
    system_prompt = row["system_prompt"]
    user_prompt_template = row["user_prompt_template"]

    # Format the prompt
    user_prompt = user_prompt_template.format(
        duration_minutes=15,
        modality="interactive",
        grade=grade_name,
        subject_label=params.subject_label,
        subject_code=params.subject_code,
        topic=params.topic,
        home_language=params.home_language,
        learning_style_primary=style,
        sa_theme=sa_theme,
        mastery_prior=params.mastery_prior,
        gap_instruction=difficulty_note
    )

    return system_prompt, user_prompt


async def generate_lesson_from_prompts(system_prompt: str, user_prompt: str) -> GeneratedLesson:
    text = await call_llm(system_prompt, user_prompt, max_tokens=1600)
    try:
        data = parse_json_response(text)
    except (ValueError, json.JSONDecodeError) as e:
        log.warning("lesson_service.invalid_json", error=str(e))
        raise LLMOutputValidationError(
            "LLM did not return valid JSON", errors=[{"msg": str(e)}], raw=text
        ) from e
    try:
        return GeneratedLesson.model_validate(data)
    except ValidationError as e:
        log.warning("lesson_service.schema_mismatch", errors=e.errors())
        raise LLMOutputValidationError(
            "LLM output failed lesson schema validation",
            errors=e.errors(),
            raw=text,
        ) from e


async def generate_lesson(params: LessonParams) -> Tuple[GeneratedLesson, str]:
    """
    Generate a complete CAPS-aligned lesson.
    params must contain ZERO learner PII.
    
    Uses caching to avoid regenerating identical lessons.
    """
    # Check cache first
    cache = get_lesson_cache()
    cached = await cache.get(params)
    if cached is not None:
        return cached
    
    # Generate new lesson
    grade_name = GRADES.get(params.grade, "Grade 3")
    system_prompt, user_prompt = await build_lesson_prompts(params)
    log.info("lesson_service.generate", grade=grade_name, subject=params.subject_code, topic=params.topic)
    lesson = await generate_lesson_from_prompts(system_prompt, user_prompt)
    
    # Cache the generated lesson and get its ID
    lesson_id = await cache.set(params, lesson)
    
    return lesson, lesson_id


async def generate_study_plan(
    grade: int,
    knowledge_gaps: list,
    subjects_mastery: dict,
) -> dict:
    """
    Generate a CAPS-aligned weekly study plan.
    Accepts only anonymised mastery data — no learner PII.
    """
    grade_name = GRADES.get(grade, "Grade 3")
    gaps_summary = ", ".join([f"{g['subject']} at {GRADES.get(g.get('gap_grade', grade), grade_name)} level" for g in knowledge_gaps]) if knowledge_gaps else "none detected"

    # Fetch templates from DB
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text("SELECT system_prompt, user_prompt_template FROM prompt_templates WHERE template_type = 'study_plan' AND is_active = TRUE LIMIT 1")
        )
        row = result.mappings().first()
    
    if not row:
        log.warning("lesson_service.template_missing", type="study_plan")
        system = "You are a CAPS curriculum planner. Create personalised weekly study plans. Return ONLY valid JSON."
        user_template = "Create a one-week study plan for Grade {grade_name}. Gaps: {gaps_summary}. Mastery: {subjects_mastery_str}."
    else:
        system = row["system_prompt"]
        user_template = row["user_prompt_template"]

    subjects_mastery_str = ', '.join([f'{k}: {v}%' for k, v in subjects_mastery.items()])
    user = user_template.format(
        grade_name=grade_name,
        gaps_summary=gaps_summary,
        subjects_mastery_str=subjects_mastery_str
    )

    text_resp = await call_llm(system, user, max_tokens=900)
    return parse_json_response(text_resp)


async def generate_parent_report(
    grade: int,
    streak_days: int,
    total_xp: int,
    subjects_mastery: dict,
    gaps: list,
) -> dict:
    """
    Generate a parent-facing progress report.
    Uses only aggregate, anonymised metrics — no learner name or PII.
    """
    grade_name = GRADES.get(grade, "Grade 3")

    # Fetch templates from DB
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text("SELECT system_prompt, user_prompt_template FROM prompt_templates WHERE template_type = 'parent_report' AND is_active = TRUE LIMIT 1")
        )
        row = result.mappings().first()
    
    if not row:
        log.warning("lesson_service.template_missing", type="parent_report")
        system = "You are an educational progress report generator for South African parents. Be warm, encouraging, and use SA cultural references. Return only JSON."
        user_template = "Generate a parent progress report for Grade {grade_name}. Streak: {streak_days}, XP: {total_xp}, Mastery: {subjects_mastery_str}, Gaps: {gaps_str}."
    else:
        system = row["system_prompt"]
        user_template = row["user_prompt_template"]

    subjects_mastery_str = ', '.join([f'{k}: {v}%' for k, v in subjects_mastery.items()])
    gaps_str = ', '.join([g.get('subject', '') for g in gaps]) or 'none'
    
    user = user_template.format(
        grade_name=grade_name,
        streak_days=streak_days,
        total_xp=total_xp,
        subjects_mastery_str=subjects_mastery_str,
        gaps_str=gaps_str
    )

    text_resp = await call_llm(system, user, max_tokens=700)
    return parse_json_response(text_resp)
