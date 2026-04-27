"""EduBoost SA — Learners Router (Pseudonymous CRUD)"""
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from app.api.core.database import AsyncSessionFactory, get_db
from app.api.models.api_models import (
    DeletionRequestResponse,
    ErrorResponse,
    LearnerCreateRequest,
    LearnerCreateResponse,
    LearnerUpdateRequest,
    LearnerUpdateResponse,
    SubjectMasteryEntry,
    SubjectMasteryResponse,
)

router = APIRouter()


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=LearnerCreateResponse,
    responses={500: {"model": ErrorResponse}},
)
async def create_learner(request: LearnerCreateRequest, db=Depends(get_db)):
    """Create a new pseudonymous learner profile. Returns the UUID — no PII stored."""
    learner_id = uuid4()
    async with AsyncSessionFactory() as session:
        try:
            # Convert learning_style dict to JSON string
            import json
            style_json = json.dumps(request.learning_style)
            await session.execute(
                text("""
                    INSERT INTO learners (learner_id, grade, home_language, avatar_id, learning_style)
                    VALUES (:id, :grade, :lang, :avatar, :style)
                """),
                {
                    "id": str(learner_id),
                    "grade": request.grade,
                    "lang": request.home_language,
                    "avatar": request.avatar_id,
                    "style": style_json,
                },
            )
            await session.commit()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(error="Failed to create learner", code="LEARNER_CREATE_FAILED", details={"reason": str(e)}).model_dump(),
            ) from e
    return LearnerCreateResponse(learner_id=learner_id, grade=request.grade)


@router.get("/{learner_id}")
async def get_learner(learner_id: UUID, db=Depends(get_db)):
    """Retrieve pseudonymous learner profile by UUID."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(text("SELECT * FROM learners WHERE learner_id = :id"), {"id": str(learner_id)})
        row = result.mappings().first()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(error="Learner not found", code="LEARNER_NOT_FOUND").model_dump(),
            )
        return dict(row)


@router.patch(
    "/{learner_id}",
    response_model=LearnerUpdateResponse,
    responses={400: {"model": ErrorResponse}},
)
async def update_learner(learner_id: UUID, request: LearnerUpdateRequest, db=Depends(get_db)):
    """Update learner profile fields."""
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(error="No fields to update", code="EMPTY_UPDATE").model_dump(),
        )
    set_clause = ", ".join([f"{k} = :{k}" for k in updates])
    updates["id"] = str(learner_id)
    async with AsyncSessionFactory() as session:
        await session.execute(text(f"UPDATE learners SET {set_clause}, last_active_at = NOW() WHERE learner_id = :id"), updates)
        await session.commit()
    return LearnerUpdateResponse(updated=True)


@router.delete(
    "/{learner_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DeletionRequestResponse,
)
async def request_data_deletion(learner_id: UUID, db=Depends(get_db)):
    """POPIA Right to Erasure — marks learner for deletion within 30 days."""
    async with AsyncSessionFactory() as session:
        await session.execute(
            text("""
                UPDATE learner_identities
                SET data_deletion_requested = TRUE
                WHERE pseudonym_id = :id
            """),
            {"id": str(learner_id)},
        )
        await session.commit()
    return DeletionRequestResponse(
        status="deletion_requested",
        learner_id=learner_id,
        note="Data will be purged within 30 days per POPIA Section 24.",
    )


@router.get("/{learner_id}/mastery", response_model=SubjectMasteryResponse)
async def get_subject_mastery(learner_id: UUID, db=Depends(get_db)):
    """Retrieve subject mastery scores for a learner."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(text("SELECT * FROM subject_mastery WHERE learner_id = :id"), {"id": str(learner_id)})
        rows = result.mappings().all()
        return SubjectMasteryResponse(
            learner_id=learner_id,
            mastery=[SubjectMasteryEntry(**dict(r)) for r in rows],
        )


@router.post("/{learner_id}/mastery", status_code=status.HTTP_200_OK, response_model=SubjectMasteryResponse)
async def upsert_subject_mastery(
    learner_id: UUID,
    request: SubjectMasteryEntry,
    db=Depends(get_db),
):
    """Create or update a subject mastery entry for a learner."""
    async with AsyncSessionFactory() as session:
        try:
            # Check if learner exists
            learner_check = await session.execute(
                text("SELECT learner_id FROM learners WHERE learner_id = :id"),
                {"id": str(learner_id)}
            )
            if not learner_check.scalar_one_or_none():
                raise HTTPException(
                    status_code=404,
                    detail=ErrorResponse(error="Learner not found", code="LEARNER_NOT_FOUND").model_dump(),
                )
            
            # Check if mastery entry exists for this subject
            existing = await session.execute(
                text("""
                    SELECT mastery_id FROM subject_mastery 
                    WHERE learner_id = :learner_id AND subject_code = :subject_code
                """),
                {"learner_id": str(learner_id), "subject_code": request.subject_code},
            )
            existing_id = existing.scalar_one_or_none()
            
            if existing_id:
                # Update existing entry
                import json
                concepts_mastered_json = json.dumps(request.concepts_mastered or [])
                concepts_in_progress_json = json.dumps(request.concepts_in_progress or [])
                knowledge_gaps_json = json.dumps(request.knowledge_gaps or [])
                
                await session.execute(
                    text("""
                        UPDATE subject_mastery
                        SET mastery_score = :mastery_score,
                            concepts_mastered = :concepts_mastered,
                            concepts_in_progress = :concepts_in_progress,
                            knowledge_gaps = :knowledge_gaps,
                            last_assessed_at = NOW(),
                            updated_at = NOW()
                        WHERE mastery_id = :mastery_id
                    """),
                    {
                        "mastery_score": request.mastery_score or 0.0,
                        "concepts_mastered": concepts_mastered_json,
                        "concepts_in_progress": concepts_in_progress_json,
                        "knowledge_gaps": knowledge_gaps_json,
                        "mastery_id": str(existing_id),
                    },
                )
            else:
                # Insert new entry
                import json
                concepts_mastered_json = json.dumps(request.concepts_mastered or [])
                concepts_in_progress_json = json.dumps(request.concepts_in_progress or [])
                knowledge_gaps_json = json.dumps(request.knowledge_gaps or [])
                
                await session.execute(
                    text("""
                        INSERT INTO subject_mastery
                        (mastery_id, learner_id, subject_code, grade_level, mastery_score,
                         concepts_mastered, concepts_in_progress, knowledge_gaps, last_assessed_at)
                        VALUES (:mastery_id, :learner_id, :subject_code, :grade_level, :mastery_score,
                                :concepts_mastered, :concepts_in_progress, :knowledge_gaps, NOW())
                    """),
                    {
                        "mastery_id": str(UUID(int=0)),  # Will be replaced by gen_random_uuid() default
                        "learner_id": str(learner_id),
                        "subject_code": request.subject_code,
                        "grade_level": request.grade_level or 0,
                        "mastery_score": request.mastery_score or 0.0,
                        "concepts_mastered": concepts_mastered_json,
                        "concepts_in_progress": concepts_in_progress_json,
                        "knowledge_gaps": knowledge_gaps_json,
                    },
                )
            
            await session.commit()
            
            # Fetch updated/created entry
            result = await session.execute(
                text("SELECT * FROM subject_mastery WHERE learner_id = :id"),
                {"id": str(learner_id)}
            )
            rows = result.mappings().all()
            return SubjectMasteryResponse(
                learner_id=learner_id,
                mastery=[SubjectMasteryEntry(**dict(r)) for r in rows],
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(error="Failed to upsert mastery entry", code="MASTERY_UPSERT_FAILED", details={"reason": str(e)}).model_dump(),
            ) from e


@router.get("/{learner_id}/progress")
async def get_learner_progress(learner_id: UUID, db=Depends(get_db)):
    """
    Retrieve learner's session event summary.
    
    Returns:
    - Total lessons completed
    - Total time on task (ms)
    - XP history (by event type)
    - Recent session events
    - Current streak and level
    """
    async with AsyncSessionFactory() as session:
        try:
            # Check learner exists
            learner_result = await session.execute(
                text("SELECT learner_id, total_xp, streak_days FROM learners WHERE learner_id = :id"),
                {"id": str(learner_id)}
            )
            learner = learner_result.mappings().first()
            
            if not learner:
                raise HTTPException(
                    status_code=404,
                    detail=ErrorResponse(error="Learner not found", code="LEARNER_NOT_FOUND").model_dump(),
                )
            
            # Get session event summary
            summary_result = await session.execute(
                text("""
                    SELECT
                        COUNT(*) as total_events,
                        COUNT(CASE WHEN event_type = 'LESSON' THEN 1 END) as lessons_completed,
                        SUM(time_on_task_ms) as total_time_ms,
                        COUNT(DISTINCT session_id) as unique_sessions,
                        COUNT(CASE WHEN is_correct = TRUE THEN 1 END) as correct_responses,
                        COUNT(CASE WHEN is_correct = FALSE THEN 1 END) as incorrect_responses
                    FROM session_events
                    WHERE learner_id = :learner_id
                """),
                {"learner_id": str(learner_id)}
            )
            summary = summary_result.mappings().first()
            
            # Get recent events (last 20)
            recent_result = await session.execute(
                text("""
                    SELECT event_id, session_id, lesson_id, event_type, time_on_task_ms,
                           is_correct, occurred_at
                    FROM session_events
                    WHERE learner_id = :learner_id
                    ORDER BY occurred_at DESC
                    LIMIT 20
                """),
                {"learner_id": str(learner_id)}
            )
            recent_events = [dict(r) for r in recent_result.mappings().all()]
            
            # Calculate level from XP
            level = (learner['total_xp'] // 100) + 1
            xp_in_current_level = learner['total_xp'] % 100
            xp_to_next_level = 100 - xp_in_current_level
            
            return {
                "success": True,
                "learner_id": str(learner_id),
                "current_xp": learner['total_xp'],
                "current_level": level,
                "xp_in_level": xp_in_current_level,
                "xp_to_next_level": xp_to_next_level,
                "streak_days": learner['streak_days'],
                "summary": {
                    "total_events": summary['total_events'] or 0,
                    "lessons_completed": summary['lessons_completed'] or 0,
                    "total_time_ms": summary['total_time_ms'] or 0,
                    "unique_sessions": summary['unique_sessions'] or 0,
                    "correct_responses": summary['correct_responses'] or 0,
                    "incorrect_responses": summary['incorrect_responses'] or 0,
                    "accuracy": (
                        (summary['correct_responses'] or 0) / ((summary['correct_responses'] or 0) + (summary['incorrect_responses'] or 0))
                        if (summary['correct_responses'] or 0) + (summary['incorrect_responses'] or 0) > 0
                        else None
                    ),
                },
                "recent_events": recent_events,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(error="Failed to retrieve progress", code="PROGRESS_RETRIEVAL_FAILED", details={"reason": str(e)}).model_dump(),
            ) from e
