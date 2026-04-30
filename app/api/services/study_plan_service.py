"""
PILLAR 2 — EXECUTIVE
EduBoost SA — Study Plan Service (Refactored)
Uses WorkerAgent base class to enforce JudiciaryStamp gate.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.judiciary.base import ExecutiveAction, JudiciaryStampRef, WorkerAgent
from app.api.judiciary.provider_router import ProviderRouter
from app.api.models.db_models import Learner, StudyPlan, SubjectMastery
from app.api.services.prompt_manager import PromptManager
from app.api.core.metrics import STUDY_PLANS_GENERATED_TOTAL

logger = logging.getLogger(__name__)

class StudyPlanService(WorkerAgent):
    """
    Generates AI-powered weekly study plans.
    """

    def __init__(
        self,
        session: AsyncSession,
        encryption_key: Optional[str] = None,
    ):
        super().__init__(
            agent_id="study-plan-service",
            intent="generate_study_plan",
            encryption_key=encryption_key,
        )
        self._session = session

    async def _build_action(self, **kwargs) -> ExecutiveAction:  # type: ignore[override]
        learner_pseudonym: str = kwargs["learner_pseudonym"]
        grade: int = kwargs["grade"]
        knowledge_gaps: list = kwargs.get("knowledge_gaps", [])
        subjects_mastery: dict = kwargs.get("subjects_mastery", {})

        await self._assert_consent(learner_pseudonym, self._session)

        return ExecutiveAction(
            agent_id=self.agent_id,
            intent=self.intent,
            parameters={
                "grade": grade,
                "knowledge_gaps": knowledge_gaps,
                "subjects_mastery": subjects_mastery,
            },
            claimed_rules=[
                "POPIA-S11-DATA-MIN",
                "CAPS-STUDY-PLAN-ALIGNED",
            ],
            learner_pseudonym=learner_pseudonym,
        )

    async def _execute(
        self, action: ExecutiveAction, stamp: JudiciaryStampRef, **kwargs
    ) -> Dict[str, Any]:
        self._assert_stamped()

        # Build prompt
        system_prompt, user_prompt = await self._build_prompts(
            action.parameters["grade"],
            action.parameters["knowledge_gaps"],
            action.parameters["subjects_mastery"]
        )

        # Call LLM
        router = ProviderRouter()
        raw_content = await router.complete(
            prompt=user_prompt,
            system_prompt=system_prompt,
            action_id=action.action_id,
            stamp_id=stamp.stamp_id,
        )
        schedule = self._normalize_schedule(raw_content)

        plan_id = str(uuid.uuid4())
        plan_result = {
            "plan_id": plan_id,
            "action_id": action.action_id,
            "stamp_id": stamp.stamp_id,
            "learner_id": action.learner_pseudonym,
            "grade": action.parameters["grade"],
            "schedule": schedule,
            "days": schedule,
            "gap_ratio": kwargs.get("gap_ratio", 0.4),
            "week_focus": self._week_focus(action.parameters["knowledge_gaps"]),
            "generated_by": "AI",
        }

        # Persist to DB
        await self._persist_plan(plan_result)

        STUDY_PLANS_GENERATED_TOTAL.labels(grade_level=str(action.parameters["grade"])).inc()

        return plan_result

    async def _build_prompts(self, grade: int, gaps: list, mastery: dict) -> tuple:
        try:
            system = PromptManager.get_template("study_plan", "system")
            user_template = PromptManager.get_template("study_plan", "user")
            
            gaps_summary = ", ".join([str(g) for g in gaps]) or "none"
            mastery_str = ", ".join([f"{k}: {v}%" for k, v in mastery.items()])
            
            user_prompt = user_template.format(
                grade_name=f"Grade {grade}",
                gaps_summary=gaps_summary,
                subjects_mastery_str=mastery_str,
            )
        except Exception:
            system = "You are a CAPS curriculum planner."
            user_prompt = f"Create a study plan for Grade {grade}. Gaps: {gaps}. Mastery: {mastery}."

        return system, user_prompt

    async def _persist_plan(self, result: Dict[str, Any]) -> None:
        self._session.add(
            StudyPlan(
                plan_id=uuid.UUID(result["plan_id"]),
                learner_id=uuid.UUID(str(result["learner_id"])),
                week_start=datetime.now(timezone.utc),
                schedule=result["schedule"],
                gap_ratio=result["gap_ratio"],
                week_focus=result["week_focus"],
                generated_by=result["generated_by"],
            )
        )
        await self._session.commit()

    async def generate_plan(
        self,
        learner_id: str | uuid.UUID,
        grade: int,
        knowledge_gaps: list | None = None,
        subjects_mastery: dict | None = None,
        gap_ratio: float = 0.4,
    ) -> Dict[str, Any]:
        """
        Main entry point for generating a study plan.
        """
        knowledge_gaps = knowledge_gaps or []
        subjects_mastery = subjects_mastery or {}
        return await self.run(
            learner_pseudonym=str(learner_id),
            grade=grade,
            knowledge_gaps=knowledge_gaps,
            subjects_mastery=subjects_mastery,
            gap_ratio=gap_ratio,
        )

    async def get_current_plan(self, learner_id: uuid.UUID) -> StudyPlan | None:
        result = await self._session.execute(
            select(StudyPlan)
            .where(StudyPlan.learner_id == learner_id)
            .order_by(StudyPlan.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def refresh_plan(
        self, learner_id: uuid.UUID, gap_ratio: float = 0.4
    ) -> Dict[str, Any]:
        learner = await self._session.get(Learner, learner_id)
        if learner is None:
            raise ValueError(f"Learner {learner_id} not found")

        mastery_result = await self._session.execute(
            select(SubjectMastery).where(SubjectMastery.learner_id == learner_id)
        )
        mastery_rows = mastery_result.scalars().all()
        subjects_mastery = {
            row.subject_code: row.mastery_score for row in mastery_rows
        }
        knowledge_gaps = [
            gap
            for row in mastery_rows
            for gap in (row.knowledge_gaps or [])
        ]
        return await self.generate_plan(
            learner_id=learner_id,
            grade=learner.grade,
            knowledge_gaps=knowledge_gaps,
            subjects_mastery=subjects_mastery,
            gap_ratio=gap_ratio,
        )

    async def get_plan_with_rationale(self, learner_id: uuid.UUID) -> Dict[str, Any]:
        plan = await self.get_current_plan(learner_id)
        if plan is None:
            raise ValueError("No study plan found for this learner")
        return {
            "plan_id": str(plan.plan_id),
            "learner_id": str(plan.learner_id),
            "week_start": plan.week_start.isoformat(),
            "schedule": plan.schedule,
            "days": plan.schedule,
            "gap_ratio": plan.gap_ratio,
            "week_focus": plan.week_focus,
            "generated_by": plan.generated_by,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "rationale": "Prioritises known gaps while preserving grade-level CAPS practice.",
        }

    def _normalize_schedule(self, raw_content: Any) -> Dict[str, list]:
        if isinstance(raw_content, dict):
            if isinstance(raw_content.get("schedule"), dict):
                return raw_content["schedule"]
            if isinstance(raw_content.get("days"), dict):
                return raw_content["days"]
        if isinstance(raw_content, str):
            import json

            try:
                parsed = json.loads(raw_content)
                if isinstance(parsed, dict):
                    return self._normalize_schedule(parsed)
            except json.JSONDecodeError:
                pass
        return {
            "Mon": [{"label": "Foundation review", "type": "gap-fill"}],
            "Tue": [{"label": "CAPS practice", "type": "curriculum"}],
            "Wed": [{"label": "Guided examples", "type": "curriculum"}],
            "Thu": [{"label": "Gap consolidation", "type": "gap-fill"}],
            "Fri": [{"label": "Weekly mastery check", "type": "assessment"}],
            "Sat": [],
            "Sun": [],
        }

    def _week_focus(self, gaps: list) -> str:
        if not gaps:
            return "Grade-level CAPS mastery"
        return f"Close {len(gaps)} priority learning gap(s)"

    def _determine_week_focus(self, knowledge_gaps: list, subjects_mastery: dict) -> str:
        """Determine week focus based on gaps and mastery."""
        if not knowledge_gaps:
            return "Grade-level CAPS mastery"
        priority_subject = min(subjects_mastery.keys(), key=lambda s: subjects_mastery.get(s, 0))
        return f"Focus on {priority_subject}: {', '.join(knowledge_gaps[:2])}"

    def _prioritize_subjects(self, subjects_mastery: Dict[str, float]) -> list[str]:
        """Sort subjects by mastery score ascending (highest gap first)."""
        return sorted(subjects_mastery.keys(), key=lambda s: subjects_mastery.get(s, 0))

    def _generate_remediation_tasks(self, knowledge_gaps: list, grade: int, grade_band: str) -> list[Dict[str, Any]]:
        """Stub for remediation task generation."""
        return [{"label": f"Review {gap}", "type": "gap-fill"} for gap in knowledge_gaps]

    def _generate_grade_tasks(self, focus_subjects: list, grade: int, grade_band: str) -> list[Dict[str, Any]]:
        """Stub for grade-level task generation."""
        return [{"label": f"{subject} Practice", "type": "curriculum"} for subject in focus_subjects]

    def _generate_weekly_schedule(
        self, grade: int, grade_band: str, subjects_mastery: dict, knowledge_gaps: list, gap_ratio: float = 0.4
    ) -> Dict[str, list]:
        """Distribute tasks across a 7-day week (lowercase keys)."""
        schedule: Dict[str, list] = {d: [] for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]}
        
        # Simple task distribution
        for gap in knowledge_gaps:
            schedule["monday"].append({"label": f"Review {gap}", "type": "gap-fill"})
        
        for subject in subjects_mastery:
            schedule["tuesday"].append({"label": f"{subject} Practice", "type": "curriculum"})
            
        return schedule

# Procedural wrapper
async def generate_study_plan(
    session: AsyncSession,
    learner_id: str,
    grade: int,
    knowledge_gaps: list,
    subjects_mastery: dict
) -> Dict[str, Any]:
    service = StudyPlanService(session)
    return await service.generate_plan(
        learner_id=uuid.UUID(str(learner_id)),
        grade=grade,
        knowledge_gaps=knowledge_gaps,
        subjects_mastery=subjects_mastery,
    )
