"""EduBoost SA — Lessons Router"""
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import text

from app.api.core.database import AsyncSessionFactory, get_db
from app.api.models.api_models import (
    CachedLessonResponse,
    ErrorResponse,
    LessonFeedback,
    LessonGenerationResponse,
    LessonMeta,
    LessonRequest,
)

router = APIRouter()


def _lesson_params(req: LessonRequest) -> dict:
    return {
        "subject_code": req.subject_code,
        "subject_label": req.subject_label,
        "topic": req.topic,
        "home_language": req.home_language,
        "learning_style_primary": req.learning_style_primary,
        "mastery_prior": req.mastery_prior,
        "has_gap": req.has_gap,
        "gap_grade": req.gap_grade,
    }


@router.post(
    "/generate",
    status_code=status.HTTP_200_OK,
    response_model=LessonGenerationResponse,
    responses={403: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def generate_lesson_endpoint(request: LessonRequest, _db=Depends(get_db)):
    from app.api.orchestrator import OrchestratorRequest, get_orchestrator
    from app.api.services.lesson_service import LLMOutputValidationError

    try:
        orch = get_orchestrator()
        result = await orch.run(
            OrchestratorRequest(
                operation="GENERATE_LESSON",
                learner_id=str(request.learner_id),
                grade=request.grade,
                params=_lesson_params(request),
            )
        )
    except LLMOutputValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=ErrorResponse(error="LLM output validation failed", code="LLM_OUTPUT_INVALID", details={"reason": str(e), "errors": e.errors}).model_dump(),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(error="Lesson pipeline error", code="LESSON_PIPELINE_ERROR", details={"reason": str(e)}).model_dump(),
        ) from e

    if not result.success:
        if result.stamp_status == "REJECTED":
            raise HTTPException(
                status_code=403,
                detail=ErrorResponse(error="Constitutional violation", code="CONSTITUTIONAL_REJECTION", details={"reason": result.error}).model_dump(),
            )
        if result.error and "validation" in result.error.lower():
            raise HTTPException(
                status_code=422,
                detail=ErrorResponse(error="Lesson validation failed", code="LESSON_VALIDATION_FAILED", details={"reason": result.error}).model_dump(),
            )
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(error="Lesson generation failed", code="LESSON_GENERATION_FAILED", details={"reason": result.error}).model_dump(),
        )

    return LessonGenerationResponse(
        success=True,
        lesson_id=result.lesson_id or "unknown",
        lesson=result.output,
        meta=LessonMeta(
            stamp_status=result.stamp_status,
            stamp_id=result.stamp_id,
            ether_archetype=result.ether_archetype,
            constitutional_health=result.constitutional_health,
            latency_ms=result.latency_ms,
        ),
    )


@router.get("/{lesson_id}", status_code=status.HTTP_200_OK, response_model=CachedLessonResponse)
async def get_cached_lesson(lesson_id: str):
    try:
        import json
        import redis.asyncio as redis_lib

        from app.api.core.config import settings

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        raw = await r.get(f"lesson:{lesson_id}")
        await r.aclose()
        if raw:
            return CachedLessonResponse(success=True, lesson=json.loads(raw), source="cache")
    except Exception:
        pass
    raise HTTPException(
        status_code=404,
        detail=ErrorResponse(error="Lesson not found", code="LESSON_NOT_FOUND", details={"lesson_id": lesson_id}).model_dump(),
    )


@router.post("/{lesson_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_feedback(lesson_id: str, feedback: LessonFeedback, background_tasks: BackgroundTasks, db=Depends(get_db)):
    background_tasks.add_task(_store_feedback_bg, lesson_id, feedback)


async def _store_feedback_bg(lesson_id: str, feedback: LessonFeedback) -> None:
    try:
        from sqlalchemy import text

        from app.api.core.database import AsyncSessionFactory

        async with AsyncSessionFactory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO session_events (
                        learner_id, session_id, lesson_id, event_type,
                        lesson_efficacy_score, time_on_task_ms
                    )
                    SELECT l.learner_id, gen_random_uuid(), :lesson_id,
                           'FEEDBACK', :les, :time_ms
                    FROM learners l WHERE l.learner_id = :lid LIMIT 1
                """
                ),
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


@router.get("/cache/stats")
async def get_cache_stats():
    """Get lesson cache statistics."""
    from app.api.services.lesson_service import get_lesson_cache
    
    cache = get_lesson_cache()
    stats = await cache.stats()
    return {"cache": stats}


@router.delete("/cache")
async def clear_cache():
    """Clear the lesson cache."""
    from app.api.services.lesson_service import get_lesson_cache
    
    cache = get_lesson_cache()
    count = await cache.clear()
    return {"cleared": count, "success": True}


# ── Lesson Catalog (DB-backed) ────────────────────────────────────────────────

@router.get(
    "/catalog",
    status_code=status.HTTP_200_OK,
    summary="Browse the CAPS-aligned lesson catalog",
)
async def list_lesson_catalog(
    subject_code: Optional[str] = Query(default=None, description="Filter by subject code (e.g. MATH, ENG, NS)"),
    grade_level: Optional[int] = Query(default=None, ge=0, le=7, description="Filter by grade (0=Grade R)"),
    topic: Optional[str] = Query(default=None, description="Filter by topic (partial match)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Return paginated list of DB-backed lessons. Filterable by subject, grade, and topic."""
    conditions = ["is_active = TRUE"]
    params: dict = {"limit": limit, "offset": offset}

    if subject_code:
        conditions.append("subject_code = :subject_code")
        params["subject_code"] = subject_code.upper()
    if grade_level is not None:
        conditions.append("grade_level = :grade_level")
        params["grade_level"] = grade_level
    if topic:
        conditions.append("topic ILIKE :topic")
        params["topic"] = f"%{topic}%"

    where = " AND ".join(conditions)

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text(
                f"""
                SELECT lesson_id, title, subject_code, grade_level, unit, topic,
                       content_modality, duration_minutes, difficulty_level,
                       learning_objectives, is_cap_aligned
                FROM lessons
                WHERE {where}
                ORDER BY grade_level, subject_code, difficulty_level
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        rows = [dict(r) for r in result.mappings().all()]

        count_result = await session.execute(
            text(f"SELECT COUNT(*) FROM lessons WHERE {where}"),
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        )
        total = count_result.scalar()

    return {"total": total, "offset": offset, "limit": limit, "lessons": rows}


@router.get(
    "/catalog/{lesson_id}",
    status_code=status.HTTP_200_OK,
    summary="Fetch a single lesson from the catalog",
    responses={404: {"model": ErrorResponse}},
)
async def get_catalog_lesson(lesson_id: str):
    """Fetch full lesson content by lesson_id from the DB catalog."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text("SELECT * FROM lessons WHERE lesson_id = :id AND is_active = TRUE"),
            {"id": lesson_id},
        )
        row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error="Lesson not found in catalog",
                code="LESSON_CATALOG_NOT_FOUND",
                details={"lesson_id": lesson_id},
            ).model_dump(),
        )
    return dict(row)
