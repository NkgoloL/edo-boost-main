"""EduBoost SA — Study Plans Router"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import Field

from app.api.models.api_models import CurrentStudyPlanResponse, ErrorResponse, StudyPlanGenerationResponse
from app.api.models.api_models import StrictSchema
from app.api.services.study_plan_service import StudyPlanService
from app.api.core.database import AsyncSessionFactory

router = APIRouter()


class StudyPlanRequest(StrictSchema):
    learner_id: UUID
    grade: int = Field(ge=0, le=7)
    knowledge_gaps: list = Field(default_factory=list)
    subjects_mastery: dict = Field(default_factory=dict)
    gap_ratio: float = Field(default=0.4, ge=0.3, le=0.6)


@router.post("/generate", status_code=status.HTTP_200_OK, response_model=StudyPlanGenerationResponse)
async def generate_study_plan(request: StudyPlanRequest):
    """Generate a new study plan for a learner."""
    async with AsyncSessionFactory() as session:
        try:
            service = StudyPlanService(session)
            plan = await service.generate_plan(
                learner_id=request.learner_id,
                grade=request.grade,
                knowledge_gaps=request.knowledge_gaps,
                subjects_mastery=request.subjects_mastery,
                gap_ratio=request.gap_ratio,
            )
            
            # Emit audit event
            from app.api.core.audit_helpers import emit_study_plan_event
            await emit_study_plan_event(
                session=session,
                learner_id=request.learner_id,
                plan_id=plan['plan_id'],
                event_type="STUDY_PLAN_GENERATED",
            )
            await session.commit()
            
            return StudyPlanGenerationResponse(success=True, plan=plan)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(error=str(e), code="STUDY_PLAN_REQUEST_INVALID").model_dump(),
            ) from e
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Study plan generation failed: {e}") from e


@router.get("/{learner_id}/current", response_model=CurrentStudyPlanResponse)
async def get_current_plan(learner_id: UUID):
    """Retrieve the learner's current active study plan."""
    async with AsyncSessionFactory() as session:
        service = StudyPlanService(session)
        plan = await service.get_current_plan(learner_id)

        if not plan:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(error="No study plan found for this learner", code="STUDY_PLAN_NOT_FOUND").model_dump(),
            )

        return CurrentStudyPlanResponse(
            success=True,
            plan={
                "plan_id": str(plan.plan_id),
                "learner_id": str(plan.learner_id),
                "week_start": plan.week_start.isoformat(),
                "schedule": plan.schedule,
                "gap_ratio": plan.gap_ratio,
                "week_focus": plan.week_focus,
                "generated_by": plan.generated_by,
                "created_at": plan.created_at.isoformat(),
            },
        )


@router.post("/{learner_id}/refresh", response_model=StudyPlanGenerationResponse)
async def refresh_study_plan(learner_id: UUID, gap_ratio: float = Query(default=0.4, ge=0.3, le=0.6)):
    """Regenerate a study plan with updated learner data."""
    async with AsyncSessionFactory() as session:
        try:
            service = StudyPlanService(session)
            plan = await service.refresh_plan(learner_id=learner_id, gap_ratio=gap_ratio)
            
            # Emit audit event
            from app.api.core.audit_helpers import emit_study_plan_event
            await emit_study_plan_event(
                session=session,
                learner_id=learner_id,
                plan_id=plan['plan_id'],
                event_type="STUDY_PLAN_REFRESHED",
            )
            await session.commit()
            
            return StudyPlanGenerationResponse(success=True, plan=plan)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Study plan refresh failed: {e}") from e


@router.get("/{learner_id}/current/rationale")
async def get_study_plan_rationale(learner_id: UUID):
    """
    Get the current study plan with rationale explanations for each task.
    
    This endpoint returns the study plan with detailed explanations for why
    each task is included. Useful for educators and parents.
    """
    async with AsyncSessionFactory() as session:
        try:
            service = StudyPlanService(session)
            plan_with_rationale = await service.get_plan_with_rationale(learner_id=learner_id)
            return {"success": True, "plan": plan_with_rationale}
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Failed to get plan rationale: {e}") from e


@router.get("/{learner_id}/history")
async def get_study_plan_history(learner_id: UUID, limit: int = Query(default=20, ge=1, le=100)):
    """
    Get historical study plans for a learner.
    
    Returns all previously generated plans for this learner, ordered by creation date (newest first).
    Useful for tracking learning trajectory and plan evolution.
    """
    async with AsyncSessionFactory() as session:
        try:
            from sqlalchemy import select
            from app.api.models.db_models import StudyPlan
            
            result = await session.execute(
                select(StudyPlan)
                .where(StudyPlan.learner_id == learner_id)
                .order_by(StudyPlan.created_at.desc())
                .limit(limit)
            )
            plans = result.scalars().all()
            
            if not plans:
                return {
                    "success": True,
                    "learner_id": str(learner_id),
                    "plans": [],
                    "count": 0,
                }
            
            return {
                "success": True,
                "learner_id": str(learner_id),
                "plans": [
                    {
                        "plan_id": str(plan.plan_id),
                        "week_start": plan.week_start.isoformat(),
                        "gap_ratio": plan.gap_ratio,
                        "week_focus": plan.week_focus,
                        "generated_by": plan.generated_by,
                        "created_at": plan.created_at.isoformat(),
                        "schedule": plan.schedule,
                    }
                    for plan in plans
                ],
                "count": len(plans),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
