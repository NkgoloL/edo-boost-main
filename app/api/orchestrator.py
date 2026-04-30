"""
PILLAR 2 — EXECUTIVE
EduBoost SA — Orchestrator
Coordinates high-level operations by delegating to specialized WorkerAgents.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.api.constitutional_schema.types import OperationResult
from app.api.core.database import AsyncSessionFactory
from app.api.services.lesson_service import LessonService
from app.api.services.study_plan_service import StudyPlanService
from app.api.services.parent_portal_service import ParentReportService

logger = logging.getLogger(__name__)

class OrchestratorRequest:
    def __init__(self, operation: str, learner_id: str, grade: int, params: dict[str, Any]):
        self.operation = operation
        self.learner_id = learner_id
        self.grade = grade
        self.params = params

class Orchestrator:
    """
    Main entry point for executive actions.
    Ensures all requests are routed through WorkerAgents that enforce constitutional gates.
    """

    async def run(self, req: OrchestratorRequest) -> OperationResult:
        t0 = time.perf_counter()
        try:
            async with AsyncSessionFactory() as session:
                if req.operation == "GENERATE_LESSON":
                    service = LessonService(session)
                    result = await service.run(
                        learner_pseudonym=req.learner_id,
                        subject=req.params["subject"],
                        grade=req.grade,
                        topic=req.params["topic"]
                    )
                elif req.operation == "GENERATE_STUDY_PLAN":
                    service = StudyPlanService(session)
                    result = await service.run(
                        learner_pseudonym=req.learner_id,
                        grade=req.grade,
                        knowledge_gaps=req.params.get("knowledge_gaps", []),
                        subjects_mastery=req.params.get("subjects_mastery", {})
                    )
                elif req.operation == "GENERATE_PARENT_REPORT":
                    service = ParentReportService(session)
                    result = await service.run(
                        learner_pseudonym=req.learner_id,
                        grade=req.grade,
                        streak_days=req.params.get("streak_days", 0),
                        total_xp=req.params.get("total_xp", 0),
                        subjects_mastery=req.params.get("subjects_mastery", {}),
                        gaps=req.params.get("gaps", [])
                    )
                else:
                    return OperationResult(
                        success=False,
                        error=f"Unsupported operation: {req.operation}",
                        latency_ms=int((time.perf_counter() - t0) * 1000),
                    )

                return OperationResult(
                    success=True,
                    output=result,
                    stamp_id=result.get("stamp_id"),
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                )
        except Exception as e:
            logger.exception("Orchestrator failed to execute operation: %s", req.operation)
            return OperationResult(
                success=False,
                error=str(e),
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

def get_orchestrator() -> Orchestrator:
    return Orchestrator()
