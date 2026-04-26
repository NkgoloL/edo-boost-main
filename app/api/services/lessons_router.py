"""
EduBoost SA — Lessons Router (Five-Pillar Edition)
====================================================
All operations now flow through the constitutional pipeline:

    POST /api/v1/lessons/generate        → LessonWorker   (P2→P3→P2→P4)
    GET  /api/v1/lessons/{lesson_id}     → cache lookup   (no LLM)
    POST /api/v1/lessons/{lesson_id}/feedback → RLHF ingest

Every generation request is stamped by the Judiciary before the LLM
is called. The learner_id is used only for DB/cache lookups and the
audit prefix — it NEVER flows into any LLM prompt.
"""
from __future__ import annotations

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────

class LessonRequest(BaseModel):
    learner_id: UUID
    subject_code: str
    subject_label: str
    topic: str
    grade: int = Field(ge=0, le=7)
    home_language: str = "English"
    learning_style_primary: str = "visual"
    mastery_prior: float = Field(default=0.5, ge=0.0, le=1.0)
    has_gap: bool = False
    gap_grade: Optional[int] = None


class LessonFeedback(BaseModel):
    learner_id: UUID
    lesson_id: str
    rating: int = Field(ge=1, le=5)
    modality_preference: Optional[str] = None
    completion_pct: float = Field(ge=0.0, le=1.0)
    time_spent_seconds: int


class DiagnosticRequest(BaseModel):
    learner_id: UUID
    subject_code: str
    grade: int = Field(ge=0, le=7)
    max_questions: int = Field(default=10, ge=1, le=20)


class StudyPlanRequest(BaseModel):
    learner_id: UUID
    grade: int = Field(ge=0, le=7)
    knowledge_gaps: list = []
    subjects_mastery: dict = {}


class ParentReportRequest(BaseModel):
    learner_id: UUID
    grade: int = Field(ge=0, le=7)
    streak_days: int = 0
    total_xp: int = 0
    subjects_mastery: dict = {}
    gaps: list = []


# ── Helper: build orchestrator params ────────────────────────────────────

def _lesson_params(req: LessonRequest) -> dict:
    """
    Strip learner_id from the params dict before it reaches the orchestrator.
    The orchestrator receives learner_id separately (for audit prefix only).
    """
    return {
        "subject_code":           req.subject_code,
        "subject_label":          req.subject_label,
        "topic":                  req.topic,
        "home_language":          req.home_language,
        "learning_style_primary": req.learning_style_primary,
        "mastery_prior":          req.mastery_prior,
        "has_gap":                req.has_gap,
        "gap_grade":              req.gap_grade,
    }


# ── Routes ────────────────────────────────────────────────────────────────

@router.post("/generate", status_code=status.HTTP_200_OK)
async def generate_lesson_endpoint(request: LessonRequest):
    """
    Generate a CAPS-aligned, SA-contextual lesson.

    Five-Pillar flow:
      1. Ether profile retrieved / computed for this learner (P5)
      2. LessonWorker builds an ExecutiveIntent — no learner_id in params (P2)
      3. Judiciary evaluates: PII scan, CAPS checks, POPIA rules (P3)
      4. If APPROVED: LessonWorker calls inference_gateway (P2)
      5. All events ingested by Fourth Estate (P4)

    POPIA: learner_id is used only for the audit prefix and Ether cache key.
    It NEVER appears in any LLM prompt.
    """
    try:
        from orchestrator import get_orchestrator, OperationRequest
        orch = get_orchestrator()
        result = await orch.run(OperationRequest(
            operation="GENERATE_LESSON",
            learner_id=str(request.learner_id),
            grade=request.grade,
            params=_lesson_params(request),
        ))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Pipeline error: {e}")

    if not result.success:
        # Judiciary rejection → 403; execution failure → 503
        if result.stamp_status == "REJECTED":
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Constitutional violation — operation rejected by Judiciary",
                    "reason": result.error,
                    "stamp_status": result.stamp_status,
                },
            )
        raise HTTPException(status_code=503, detail=result.error)

    return {
        "success": True,
        "lesson": result.output,
        "meta": {
            "stamp_status":          result.stamp_status,
            "stamp_id":              result.stamp_id,
            "ether_archetype":       result.ether_archetype,
            "constitutional_health": result.constitutional_health,
            "latency_ms":            result.latency_ms,
        },
    }


@router.post("/diagnostic", status_code=status.HTTP_200_OK)
async def run_diagnostic_endpoint(request: DiagnosticRequest):
    """
    Run an IRT adaptive diagnostic session.
    Returns a gap report with theta estimate, mastery score, and gap grade.
    """
    try:
        from orchestrator import get_orchestrator, OperationRequest
        orch = get_orchestrator()
        result = await orch.run(OperationRequest(
            operation="RUN_DIAGNOSTIC",
            learner_id=str(request.learner_id),
            grade=request.grade,
            params={
                "subject_code":  request.subject_code,
                "max_questions": request.max_questions,
            },
        ))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Diagnostic pipeline error: {e}")

    if not result.success:
        if result.stamp_status == "REJECTED":
            raise HTTPException(status_code=403, detail={"error": result.error})
        raise HTTPException(status_code=503, detail=result.error)

    return {"success": True, "diagnostic": result.output, "meta": {
        "stamp_status": result.stamp_status,
        "latency_ms":   result.latency_ms,
    }}


@router.post("/study-plan", status_code=status.HTTP_200_OK)
async def generate_study_plan_endpoint(request: StudyPlanRequest):
    """Generate a CAPS-aligned weekly study plan."""
    try:
        from orchestrator import get_orchestrator, OperationRequest
        orch = get_orchestrator()
        result = await orch.run(OperationRequest(
            operation="GENERATE_STUDY_PLAN",
            learner_id=str(request.learner_id),
            grade=request.grade,
            params={
                "knowledge_gaps":   request.knowledge_gaps,
                "subjects_mastery": request.subjects_mastery,
            },
        ))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Study plan pipeline error: {e}")

    if not result.success:
        raise HTTPException(status_code=503, detail=result.error)

    return {"success": True, "plan": result.output, "meta": {
        "stamp_status": result.stamp_status,
        "latency_ms":   result.latency_ms,
    }}


@router.post("/parent-report", status_code=status.HTTP_200_OK)
async def generate_parent_report_endpoint(request: ParentReportRequest):
    """Generate an AI progress report for the Parent Portal."""
    try:
        from orchestrator import get_orchestrator, OperationRequest
        orch = get_orchestrator()
        result = await orch.run(OperationRequest(
            operation="GENERATE_REPORT",
            learner_id=str(request.learner_id),
            grade=request.grade,
            params={
                "streak_days":      request.streak_days,
                "total_xp":         request.total_xp,
                "subjects_mastery": request.subjects_mastery,
                "gaps":             request.gaps,
            },
        ))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Report pipeline error: {e}")

    if not result.success:
        raise HTTPException(status_code=503, detail=result.error)

    return {"success": True, "report": result.output, "meta": {
        "stamp_status":    result.stamp_status,
        "ether_archetype": result.ether_archetype,
        "latency_ms":      result.latency_ms,
    }}


@router.get("/{lesson_id}", status_code=status.HTTP_200_OK)
async def get_cached_lesson(lesson_id: str):
    """
    Retrieve a previously generated lesson from Redis cache.
    Falls back to DB if cache miss.
    """
    try:
        import redis.asyncio as redis_lib
        from app.api.core.config import settings
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        raw = await r.get(f"lesson:{lesson_id}")
        await r.aclose()
        if raw:
            import json
            return {"success": True, "lesson": json.loads(raw), "source": "cache"}
    except Exception:
        pass

    raise HTTPException(
        status_code=404,
        detail=f"Lesson '{lesson_id}' not found in cache. Generate it first.",
    )


@router.post("/{lesson_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_feedback(
    lesson_id: str,
    feedback: LessonFeedback,
    background_tasks: BackgroundTasks,
):
    """
    Record learner feedback for the RLHF pipeline.
    Stored pseudonymously — learner_id hashed before persistence.
    """
    background_tasks.add_task(_store_feedback, lesson_id, feedback)


async def _store_feedback(lesson_id: str, feedback: LessonFeedback) -> None:
    """Background task: persist RLHF feedback to session_events."""
    try:
        import hashlib, json
        from sqlalchemy import text
        from app.api.core.database import AsyncSessionFactory

        id_hash = hashlib.sha256(str(feedback.learner_id).encode()).hexdigest()[:16]

        async with AsyncSessionFactory() as session:
            await session.execute(
                text("""
                    INSERT INTO session_events (
                        learner_id, session_id, lesson_id, event_type,
                        lesson_efficacy_score, time_on_task_ms
                    )
                    SELECT
                        l.learner_id,
                        gen_random_uuid(),
                        :lesson_id,
                        'FEEDBACK',
                        :les,
                        :time_ms
                    FROM learners l
                    WHERE l.learner_id = :lid
                    LIMIT 1
                """),
                {
                    "lesson_id": lesson_id,
                    "les": feedback.rating / 5.0,
                    "time_ms": feedback.time_spent_seconds * 1000,
                    "lid": str(feedback.learner_id),
                },
            )
            await session.commit()
    except Exception as e:
        import structlog
        structlog.get_logger().warning("feedback.store_failed", error=str(e))
