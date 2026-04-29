"""
PILLAR 2 — EXECUTIVE
Refactored LessonService and StudyPlanService as WorkerAgent subclasses.
Neither service may call an LLM or write to the DB without a valid JudiciaryStamp.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .base import ExecutiveAction, JudiciaryStampRef, WorkerAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LessonService
# ---------------------------------------------------------------------------
class LessonService(WorkerAgent):
    """
    Generates AI-powered lessons.
    Stamp gate ensures every LLM call is Judiciary-approved before execution.
    Ether prompt modifier is applied AFTER stamp approval (pure function, no I/O).
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

        # Apply Ether prompt modification (pure function — no I/O)
        base_prompt = self._build_base_prompt(subject, grade, topic)
        modified_prompt = await self._apply_ether(learner_pseudonym, base_prompt)

        # Call LLM via ProviderRouter (circuit-breaker aware)
        from app.api.infrastructure.provider_router import ProviderRouter

        router = ProviderRouter()
        raw_content = await router.complete(
            prompt=modified_prompt,
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

        # Persist to DB (only possible because self._stamped is True)
        await self._persist_lesson(lesson_result)
        return lesson_result

    def _build_base_prompt(self, subject: str, grade: int, topic: str) -> str:
        return (
            f"You are a South African CAPS-aligned educational assistant for Grade {grade}.\n"
            f"Subject: {subject}\nTopic: {topic}\n"
            "Deliver the lesson with authentic South African context. "
            "Never include any learner's real name, email, or ID number."
        )

    async def _apply_ether(self, learner_pseudonym: Optional[str], prompt: str) -> str:
        """Fetch cached EtherProfile and inject tone/pacing parameters."""
        try:
            from app.api.pillar_5_ether.prompt_modifier import EtherPromptModifier

            modifier = EtherPromptModifier(self._session)
            return await modifier.apply(prompt, learner_pseudonym)
        except Exception as exc:
            logger.warning("Ether modifier failed (using base prompt): %s", exc)
            return prompt

    async def _persist_lesson(self, result: Dict[str, Any]) -> None:
        from sqlalchemy import text

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


# ---------------------------------------------------------------------------
# StudyPlanService
# ---------------------------------------------------------------------------
class StudyPlanService(WorkerAgent):
    """
    Generates CAPS-aligned study plans. Stamp gate applies before any LLM call
    or DB write to study_plans table.
    """

    def __init__(self, session: AsyncSession, encryption_key: Optional[str] = None):
        super().__init__(
            agent_id="study-plan-service",
            intent="generate_study_plan",
            encryption_key=encryption_key,
        )
        self._session = session

    async def _build_action(self, **kwargs) -> ExecutiveAction:  # type: ignore[override]
        learner_pseudonym: str = kwargs["learner_pseudonym"]
        grade: int = kwargs["grade"]
        gap_subjects: List[str] = kwargs.get("gap_subjects", [])

        await self._assert_consent(learner_pseudonym, self._session)

        return ExecutiveAction(
            agent_id=self.agent_id,
            intent=self.intent,
            parameters={"grade": grade, "gap_subjects": gap_subjects},
            claimed_rules=["CAPS-STUDY-PLAN", "POPIA-S11-DATA-MIN"],
            learner_pseudonym=learner_pseudonym,
        )

    async def _execute(
        self, action: ExecutiveAction, stamp: JudiciaryStampRef, **kwargs
    ) -> Dict[str, Any]:
        self._assert_stamped()

        grade = action.parameters["grade"]
        gap_subjects = action.parameters["gap_subjects"]
        learner_pseudonym = action.learner_pseudonym

        prompt = self._build_plan_prompt(grade, gap_subjects)

        from app.api.infrastructure.provider_router import ProviderRouter

        router = ProviderRouter()
        plan_content = await router.complete(
            prompt=prompt,
            action_id=action.action_id,
            stamp_id=stamp.stamp_id,
        )

        plan = {
            "action_id": action.action_id,
            "stamp_id": stamp.stamp_id,
            "learner_pseudonym": learner_pseudonym,
            "grade": grade,
            "plan_content": plan_content,
        }
        await self._persist_plan(plan)
        return plan

    def _build_plan_prompt(self, grade: int, gap_subjects: List[str]) -> str:
        gaps = ", ".join(gap_subjects) if gap_subjects else "no identified gaps"
        return (
            f"Create a CAPS-aligned 4-week study plan for a Grade {grade} South African learner. "
            f"Priority gaps: {gaps}. "
            "Format as a weekly schedule with daily 30-minute sessions. "
            "Do not include any learner personal information."
        )

    async def _persist_plan(self, plan: Dict[str, Any]) -> None:
        from sqlalchemy import text

        await self._session.execute(
            text(
                """
                INSERT INTO study_plans
                    (action_id, stamp_id, learner_pseudonym, grade, plan_content, created_at)
                VALUES (:action_id, :stamp_id, :learner_pseudonym, :grade, :plan_content, now())
                """
            ),
            plan,
        )
        await self._session.commit()


# ---------------------------------------------------------------------------
# ParentReportService
# ---------------------------------------------------------------------------
class ParentReportService(WorkerAgent):
    """
    Generates parent-facing progress reports. Touches learner data — must be stamped.
    """

    def __init__(self, session: AsyncSession, encryption_key: Optional[str] = None):
        super().__init__(
            agent_id="parent-report-service",
            intent="generate_parent_report",
            encryption_key=encryption_key,
        )
        self._session = session

    async def _build_action(self, **kwargs) -> ExecutiveAction:  # type: ignore[override]
        learner_pseudonym: str = kwargs["learner_pseudonym"]
        await self._assert_consent(learner_pseudonym, self._session)

        return ExecutiveAction(
            agent_id=self.agent_id,
            intent=self.intent,
            parameters={},
            claimed_rules=["POPIA-S11-DATA-MIN", "POPIA-S23-GUARDIAN-ACCESS"],
            learner_pseudonym=learner_pseudonym,
        )

    async def _execute(
        self, action: ExecutiveAction, stamp: JudiciaryStampRef, **kwargs
    ) -> Dict[str, Any]:
        self._assert_stamped()
        # Read aggregated lesson results and IRT scores from audit_log (read-only path)
        from sqlalchemy import text

        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT event_type, event_data, created_at
                    FROM audit_log
                    WHERE learner_pseudonym = :p
                      AND event_type IN ('lesson_complete', 'assessment_complete')
                    ORDER BY created_at DESC
                    LIMIT 50
                    """
                ),
                {"p": action.learner_pseudonym},
            )
        ).mappings().all()

        report_data = [dict(r) for r in rows]
        return {
            "stamp_id": stamp.stamp_id,
            "learner_pseudonym": action.learner_pseudonym,
            "report": report_data,
        }
