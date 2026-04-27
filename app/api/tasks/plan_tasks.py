"""Celery background tasks for study plan generation and auto-linkage."""
import asyncio
from typing import Optional
from uuid import UUID

from celery.utils.log import get_task_logger

from app.api.core.celery_app import celery_app
from app.api.core.database import AsyncSessionFactory
from app.api.services.lesson_service import generate_study_plan
from sqlalchemy import text

logger = get_task_logger(__name__)


async def _refresh_study_plan(learner_id: str):
    """Async helper to generate and persist a study plan for a learner."""
    # 1. Fetch learner's current grade and gaps from the latest diagnostic session
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text("""
                SELECT grade_level, knowledge_gaps, final_mastery_score
                FROM diagnostic_sessions
                WHERE learner_id = :learner_id AND status = 'completed'
                ORDER BY completed_at DESC
                LIMIT 1
            """),
            {"learner_id": learner_id}
        )
        row = result.mappings().first()

    if not row:
        logger.warning(f"No completed diagnostic sessions found for learner {learner_id}")
        return

    grade = row["grade_level"]
    knowledge_gaps = row["knowledge_gaps"] or []
    
    # 2. Fetch subject mastery
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text("""
                SELECT subject_code, mastery_score
                FROM subject_mastery
                WHERE learner_id = :learner_id
            """),
            {"learner_id": learner_id}
        )
        mastery_rows = result.mappings().all()
    
    subjects_mastery = {r["subject_code"]: round(r["mastery_score"] * 100) for r in mastery_rows}

    # 3. Generate the plan via Orchestrator (handles constitutional review, profiling, audit)
    from app.api.orchestrator import get_orchestrator, OrchestratorRequest
    orch = get_orchestrator()
    result = await orch.run(
        OrchestratorRequest(
            operation="GENERATE_STUDY_PLAN",
            learner_id=learner_id,
            grade=grade,
            params={
                "knowledge_gaps": knowledge_gaps,
                "subjects_mastery": subjects_mastery,
            },
        )
    )

    if not result.success:
        logger.error(f"Orchestrator failed to generate study plan: {result.error}")
        return

    plan_data = result.output

    # 4. Persist the plan to DB
    import json
    async with AsyncSessionFactory() as session:
        await session.execute(
            text("""
                INSERT INTO study_plans (learner_id, target_grade, focus_areas, schedule, rationale)
                VALUES (:learner_id, :target_grade, :focus_areas, :schedule::jsonb, :rationale)
            """),
            {
                "learner_id": learner_id,
                "target_grade": grade,
                "focus_areas": json.dumps(knowledge_gaps),
                "schedule": json.dumps(plan_data.get("days", {})),
                "rationale": plan_data.get("week_focus", "Auto-generated after diagnostic."),
            }
        )
        await session.commit()
    logger.info(f"Successfully refreshed study plan for learner {learner_id}")


@celery_app.task(
    name="eduboost.tasks.refresh_study_plan",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def refresh_study_plan_task(self, learner_id_str: str) -> str:
    """
    Celery task to automatically generate a new study plan after a diagnostic session.
    Retries up to 3 times on transient failures.
    """
    logger.info(f"Starting auto-linkage study plan refresh for learner: {learner_id_str}")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_refresh_study_plan(learner_id_str))
        return f"Study plan generated for {learner_id_str}"
    except Exception as exc:
        logger.error(f"Study plan refresh failed for {learner_id_str}: {exc}")
        raise self.retry(exc=exc)
    finally:
        loop.close()


@celery_app.task(
    name="eduboost.tasks.daily_plan_refresh",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def daily_plan_refresh(self) -> str:
    """
    Beat-triggered: refresh study plans for all active learners.
    Runs daily at 05:00 SAST.
    """
    logger.info("Starting daily plan refresh for all active learners")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_daily_plan_refresh_all())
        return "Daily plan refresh completed"
    except Exception as exc:
        logger.error(f"Daily plan refresh failed: {exc}")
        raise self.retry(exc=exc)
    finally:
        loop.close()


async def _daily_plan_refresh_all():
    """Fetch all active learners and refresh their plans."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            text("""
                SELECT DISTINCT learner_id::text FROM diagnostic_sessions
                WHERE status = 'completed'
                AND completed_at >= NOW() - INTERVAL '7 days'
            """)
        )
        learner_ids = [row[0] for row in result.fetchall()]

    logger.info(f"Daily refresh: {len(learner_ids)} learners with recent diagnostics")
    for lid in learner_ids:
        try:
            await _refresh_study_plan(lid)
        except Exception as e:
            logger.error(f"Daily refresh failed for learner {lid}: {e}")

