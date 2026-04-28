"""
EduBoost SA — Study Plan Generation Service

Generates dynamic CAPS-aligned study plans that blend remediation
and grade-level pacing based on diagnostic output and learner progress.
"""

import uuid
from datetime import datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.db_models import Learner, StudyPlan, SubjectMastery
from app.api.core.config import settings

log = structlog.get_logger()

CAPS_SUBJECTS = {
    "MATH": {"name": "Mathematics", "weekly_hours": 6},
    "ENG": {"name": "English", "weekly_hours": 5},
    "AFR": {"name": "Afrikaans", "weekly_hours": 4},
    "LIFE": {"name": "Life Skills", "weekly_hours": 4},
    "NS": {"name": "Natural Sciences", "weekly_hours": 3},
    "SS": {"name": "Social Sciences", "weekly_hours": 3},
}

GRADE_FOCUS = {
    (0, 3): {
        "MATH": ["counting", "addition", "subtraction", "shapes", "measurement"],
        "ENG": ["phonics", "reading", "writing", "vocabulary"],
        "LIFE": ["health", "safety", "community"],
    },
    (4, 7): {
        "MATH": ["fractions", "multiplication", "geometry", "data", "algebra"],
        "ENG": ["comprehension", "grammar", "writing", "literature"],
        "NS": ["matter", "energy", "life_systems", "earth_science"],
        "SS": ["history", "geography", "civics"],
    },
}


class StudyPlanService:
    """Service for generating and managing study plans."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_plan(
        self,
        learner_id: UUID,
        grade: int,
        knowledge_gaps: list | None = None,
        subjects_mastery: dict | None = None,
        gap_ratio: float = 0.4,
    ) -> dict:
        learner = await self.session.get(Learner, learner_id)
        if not learner:
            raise ValueError(f"Learner {learner_id} not found")

        subjects_mastery = subjects_mastery or await self._get_subject_mastery(
            learner_id
        )
        knowledge_gaps = knowledge_gaps or await self._get_knowledge_gaps(learner_id)
        normalized_gap_ratio = max(0.3, min(0.6, gap_ratio))
        grade_band = "R-3" if grade <= 3 else "4-7"

        # Test mode: avoid orchestrator + LLM dependencies; use deterministic algorithmic schedule.
        if settings.APP_ENV == "test":
            schedule = self._generate_weekly_schedule(
                grade=grade,
                grade_band=grade_band,
                subjects_mastery=subjects_mastery,
                knowledge_gaps=knowledge_gaps,
                gap_ratio=normalized_gap_ratio,
            )
            week_focus = self._determine_week_focus(knowledge_gaps, subjects_mastery)
        else:
            from app.api.orchestrator import get_orchestrator, OrchestratorRequest

            orch = get_orchestrator()
            result = await orch.run(
                OrchestratorRequest(
                    operation="GENERATE_STUDY_PLAN",
                    learner_id=str(learner_id),
                    grade=grade,
                    params={
                        "knowledge_gaps": knowledge_gaps,
                        "subjects_mastery": subjects_mastery,
                        "gap_ratio": normalized_gap_ratio,
                    },
                )
            )

            if not result.success:
                log.error("study_plan_service.orchestrator_failed", error=result.error)
                # Fallback to programmatic logic if orchestrator fails
                schedule = self._generate_weekly_schedule(
                    grade=grade,
                    grade_band=grade_band,
                    subjects_mastery=subjects_mastery,
                    knowledge_gaps=knowledge_gaps,
                    gap_ratio=normalized_gap_ratio,
                )
                week_focus = self._determine_week_focus(
                    knowledge_gaps, subjects_mastery
                )
            else:
                plan_data = result.output or {}
                schedule = plan_data.get("days") or plan_data.get("schedule") or {}
                week_focus = plan_data.get("week_focus", "Focus on key concepts.")

        plan = StudyPlan(
            plan_id=uuid.uuid4(),
            learner_id=learner_id,
            week_start=self._get_week_start(),
            schedule=schedule,
            gap_ratio=normalized_gap_ratio,
            week_focus=week_focus,
            generated_by="ALGORITHM",
        )
        self.session.add(plan)
        await self.session.commit()
        await self.session.refresh(plan)

        return {
            "plan_id": str(plan.plan_id),
            "learner_id": str(plan.learner_id),
            "grade": grade,
            "week_start": plan.week_start.isoformat(),
            "schedule": plan.schedule,
            "gap_ratio": plan.gap_ratio,
            "week_focus": plan.week_focus,
            "generated_by": plan.generated_by,
            "created_at": (plan.created_at or datetime.now()).isoformat(),
        }

    async def _get_subject_mastery(self, learner_id: UUID) -> dict[str, float]:
        result = await self.session.execute(
            select(SubjectMastery).where(SubjectMastery.learner_id == learner_id)
        )
        return {
            record.subject_code: record.mastery_score
            for record in result.scalars().all()
        }

    async def _get_knowledge_gaps(self, learner_id: UUID) -> list[dict]:
        result = await self.session.execute(
            select(SubjectMastery).where(SubjectMastery.learner_id == learner_id)
        )
        gaps: list[dict] = []
        for record in result.scalars().all():
            if record.knowledge_gaps:
                for gap in record.knowledge_gaps:
                    if isinstance(gap, dict):
                        gaps.append({
                            "concept": gap.get("concept") or gap.get("concept_code") or gap.get("name"),
                            "subject": record.subject_code,
                            "gap_grade": gap.get("gap_grade", record.grade_level),
                            "severity": gap.get("severity", 0.5)
                        })
        # Remove duplicates by concept
        seen = set()
        unique_gaps = []
        for g in gaps:
            if g["concept"] not in seen:
                unique_gaps.append(g)
                seen.add(g["concept"])
        return unique_gaps

    def _generate_weekly_schedule(
        self,
        grade: int,
        grade_band: str,
        subjects_mastery: dict[str, float],
        knowledge_gaps: list | None,
        gap_ratio: float,
    ) -> dict:
        schedule = {
            day: []
            for day in [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
        }
        focus_subjects = self._prioritize_subjects(subjects_mastery)
        remediation_tasks = self._generate_remediation_tasks(
            knowledge_gaps, grade, grade_band
        )
        
        # Spaced Repetition: Inject extra tasks for critically low mastery subjects
        critical_subjects = [s for s, m in subjects_mastery.items() if m < 0.35]
        extra_grade_tasks = self._generate_grade_tasks(critical_subjects, grade, grade_band)
        
        grade_tasks = self._generate_grade_tasks(focus_subjects, grade, grade_band)
        # Mix in extra tasks for spaced repetition
        grade_tasks = extra_grade_tasks + grade_tasks

        target_remediation = (
            min(
                len(remediation_tasks),
                max(1, round((len(remediation_tasks) + len(grade_tasks)) * gap_ratio)),
            )
            if remediation_tasks
            else 0
        )
        target_grade = (
            min(
                len(grade_tasks),
                max(
                    1, (len(remediation_tasks) + len(grade_tasks)) - target_remediation
                ),
            )
            if grade_tasks
            else 0
        )
        selected_tasks = (
            remediation_tasks[:target_remediation] + grade_tasks[:target_grade]
        )
        if not selected_tasks:
            selected_tasks = self._generate_grade_tasks(
                list(CAPS_SUBJECTS.keys()), grade, grade_band
            )[:3]

        weekday_slots = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        for index, task in enumerate(selected_tasks):
            schedule[weekday_slots[index % len(weekday_slots)]].append(task)
        return schedule

    def _prioritize_subjects(self, subjects_mastery: dict[str, float]) -> list[str]:
        """
        Return subjects ordered from weakest → strongest.

        Tests and downstream scheduling expect a list of subject codes, not tuples.
        """
        prioritized = [
            (subject, score)
            for subject, score in subjects_mastery.items()
            if score is not None
        ]
        prioritized.sort(key=lambda item: item[1])
        return [subject for subject, _score in prioritized]

    def _generate_remediation_tasks(
        self, knowledge_gaps: list | None, grade: int, grade_band: str
    ) -> list[dict]:
        tasks = []
        # Normalize gaps: tests and callers may pass either list[str] (concepts)
        # or list[dict] with keys ('concept','gap_grade','severity'). Convert
        # strings to dicts so downstream logic can rely on `.get()`.
        normalized: list[dict] = []
        if knowledge_gaps:
            for g in knowledge_gaps:
                if isinstance(g, dict):
                    normalized.append(g)
                elif isinstance(g, str):
                    normalized.append({"concept": g, "gap_grade": grade, "severity": 0.5})
        sorted_gaps = sorted(
            normalized,
            key=lambda x: (x.get("gap_grade", 9), -x.get("severity", 0)),
        )
        
        for gap_obj in sorted_gaps[:6]:
            concept = gap_obj["concept"]
            subject = gap_obj.get("subject") or self._concept_to_subject(concept)
            severity = gap_obj.get("severity", 0.5)
            
            tasks.append(
                {
                    "task_id": str(uuid.uuid4()),
                    "type": "remediation",
                    "subject": subject,
                    "concept": concept,
                    "grade": gap_obj.get("gap_grade", grade),
                    "title": f"Bridge Foundations: {concept.replace('_', ' ').title()}",
                    "duration_minutes": 20 if severity < 0.7 else 30,
                    "difficulty": "remedial",
                    "is_gap_focus": True,
                    "severity": severity
                }
            )
        return tasks

    def _generate_grade_tasks(
        self, focus_subjects: list[str], grade: int, grade_band: str
    ) -> list[dict]:
        tasks = []
        focus_areas = GRADE_FOCUS[(0, 3) if grade <= 3 else (4, 7)]
        for subject in focus_subjects[:4]:
            for concept in focus_areas.get(subject, [])[:2]:
                tasks.append(
                    {
                        "task_id": str(uuid.uuid4()),
                        "type": "lesson",
                        "subject": subject,
                        "concept": concept,
                        "grade": grade,
                        "title": f"{CAPS_SUBJECTS.get(subject, {}).get('name', subject)}: {concept.replace('_', ' ').title()}",
                        "duration_minutes": 25,
                        "difficulty": "grade_level",
                        "is_gap_focus": False,
                    }
                )
        return tasks

    def _concept_to_subject(self, concept: str) -> str:
        concept_lower = concept.lower()
        if any(
            x in concept_lower
            for x in [
                "math",
                "number",
                "calc",
                "geom",
                "algebra",
                "fraction",
                "addition",
                "subtraction",
                "division",
            ]
        ):
            return "MATH"
        if any(
            x in concept_lower
            for x in ["read", "write", "phon", "vocab", "gram", "comprehension"]
        ):
            return "ENG"
        if any(
            x in concept_lower for x in ["life", "health", "safety", "community", "bio"]
        ):
            return "LIFE"
        if any(
            x in concept_lower for x in ["nature", "phys", "chem", "energy", "matter"]
        ):
            return "NS"
        if any(x in concept_lower for x in ["history", "geog", "civic"]):
            return "SS"
        return "MATH"

    def _determine_week_focus(
        self, knowledge_gaps: list | None, subjects_mastery: dict[str, float]
    ) -> str:
        if knowledge_gaps:
            normalized: list[dict] = []
            for g in knowledge_gaps:
                if isinstance(g, dict):
                    normalized.append(g)
                elif isinstance(g, str):
                    normalized.append({"concept": g, "gap_grade": None, "severity": 0.5})
            # Sort as we do for tasks
            sorted_gaps = sorted(
                normalized,
                key=lambda x: (x.get("gap_grade", 9), -x.get("severity", 0)),
            )
            top_gap = sorted_gaps[0]
            concept = top_gap.get("concept")
            subject = top_gap.get("subject") or self._concept_to_subject(concept)
            return (
                f"Foundational Bridge: Mastering {subject} {concept.replace('_', ' ').title()}"
            )
        if subjects_mastery:
            weakest = min(
                subjects_mastery.items(),
                key=lambda item: item[1] if item[1] is not None else 1.0,
            )
            return f"Strengthen {CAPS_SUBJECTS.get(weakest[0], {}).get('name', weakest[0])} fundamentals"
        return "General review and advancement"

    def _get_week_start(self) -> datetime:
        today = datetime.now()
        monday = today - timedelta(days=today.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)

    async def get_current_plan(self, learner_id: UUID):
        result = await self.session.execute(
            select(StudyPlan)
            .where(StudyPlan.learner_id == learner_id)
            .order_by(StudyPlan.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def refresh_plan(self, learner_id: UUID, gap_ratio: float = 0.4) -> dict:
        learner = await self.session.get(Learner, learner_id)
        if not learner:
            raise ValueError(f"Learner {learner_id} not found")
        return await self.generate_plan(
            learner_id=learner_id,
            grade=learner.grade,
            knowledge_gaps=await self._get_knowledge_gaps(learner_id),
            subjects_mastery=await self._get_subject_mastery(learner_id),
            gap_ratio=gap_ratio,
        )

    def _generate_task_rationale(
        self, task: dict, subjects_mastery: dict[str, float], knowledge_gaps: list[str]
    ) -> str:
        task_type = task.get("type", "unknown")
        subject = task.get("subject", "")
        concept = task.get("concept", "")
        if task_type == "remediation":
            mastery = subjects_mastery.get(subject, 0) or 0
            if mastery < 0.4:
                level = "significant weakness"
            elif mastery < 0.6:
                level = "area for improvement"
            else:
                level = "minor gap"
            return f"Remediation task: {concept.replace('_', ' ').title()} is a {level} in {CAPS_SUBJECTS.get(subject, {}).get('name', subject)}. This concept has been identified as a knowledge gap and targeted practice will strengthen the learner's foundation."
        if task_type == "lesson":
            return f"Grade-level advancement: Introducing {concept.replace('_', ' ').title()} in {CAPS_SUBJECTS.get(subject, {}).get('name', subject)}. This aligns with Grade {task.get('grade', 'current')} CAPS curriculum pacing."
        if task_type == "assessment":
            return f"Assessment: This diagnostic in {concept} will help identify the learner's current level and personalize future lessons."
        if task_type == "review":
            return f"Review and consolidation: Reinforcing {concept.replace('_', ' ').title()} to build automaticity and confidence."
        return f"Complete this {concept.replace('_', ' ').title()} task in {subject} to progress in the learning journey."

    async def get_plan_with_rationale(self, learner_id: UUID) -> dict:
        plan = await self.get_current_plan(learner_id)
        if not plan:
            raise ValueError(f"No active study plan for learner {learner_id}")
        subjects_mastery = await self._get_subject_mastery(learner_id)
        knowledge_gaps = await self._get_knowledge_gaps(learner_id)
        schedule_with_rationale = {
            day: [
                {
                    **task,
                    "rationale": self._generate_task_rationale(
                        task, subjects_mastery, knowledge_gaps
                    ),
                }
                for task in tasks
            ]
            for day, tasks in (plan.schedule or {}).items()
        }
        return {
            "plan_id": str(plan.plan_id),
            "learner_id": str(learner_id),
            "week_start": plan.week_start.isoformat(),
            "week_focus": plan.week_focus,
            "week_focus_rationale": f"This week focuses on {plan.week_focus.lower()}. This targets stronger gaps while maintaining grade-level pace.",
            "gap_ratio": plan.gap_ratio,
            "remediation_percentage": int(plan.gap_ratio * 100),
            "advancement_percentage": int((1 - plan.gap_ratio) * 100),
            "schedule_with_rationale": schedule_with_rationale,
            "generated_by": plan.generated_by,
            "created_at": plan.created_at.isoformat(),
        }
