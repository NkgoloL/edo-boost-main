"""EduBoost SA — Executive orchestrator (Pillar 2): coordinates pillars for operations."""

from __future__ import annotations

import hashlib
import hmac
import random
import time
from dataclasses import dataclass
from typing import Any, Optional

from app.api.constitutional_schema.types import (
    ActionType,
    EventType,
    ExecutiveAction,
    OperationResult,
    StampStatus,
)
from app.api.core.config import settings
from app.api.fourth_estate import get_fourth_estate
from app.api.judiciary import get_judiciary
from app.api.profiler import get_profiler
from app.api.services.lesson_service import (
    LessonParams,
    build_lesson_prompts,
    generate_lesson,
    generate_parent_report,
    generate_study_plan,
)

_orchestrator: Optional["Orchestrator"] = None


def _learner_hash(learner_id: str) -> str:
    salt = (settings.ENCRYPTION_SALT or "").encode("utf-8")
    return hmac.new(salt, learner_id.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


@dataclass
class OrchestratorRequest:
    operation: str
    learner_id: str
    grade: int
    params: dict[str, Any]


class Orchestrator:
    async def run(self, req: OrchestratorRequest) -> OperationResult:
        t0 = time.perf_counter()
        if req.operation == "GENERATE_LESSON":
            return await self._generate_lesson(req, t0)
        if req.operation == "RUN_DIAGNOSTIC":
            return await self._run_diagnostic(req, t0)
        if req.operation == "GENERATE_STUDY_PLAN":
            return await self._generate_study_plan(req, t0)
        if req.operation == "GENERATE_PARENT_REPORT":
            return await self._generate_parent_report(req, t0)
        elif req.operation == "START_DIAGNOSTIC":
            return await self._start_diagnostic(req, t0)
        elif req.operation == "SUBMIT_DIAGNOSTIC_RESPONSE":
            return await self._submit_diagnostic_response(req, t0)
        return OperationResult(
            success=False,
            error=f"Unsupported operation: {req.operation}",
            stamp_status="REJECTED",
            constitutional_health=0.0,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    async def _review_action(
        self, action_type: ActionType, req: OrchestratorRequest, t0: float
    ) -> tuple[ExecutiveAction, Any, Any, Any, Any]:
        fe = get_fourth_estate()
        j = get_judiciary(use_llm_review=False)
        profiler = get_profiler()
        action = ExecutiveAction(
            action_type=action_type,
            learner_id_hash=_learner_hash(req.learner_id),
            grade=req.grade,
            params=dict(req.params),
            claimed_rules=[],
        )
        await fe.publish_action_submitted(action)
        profile = await profiler.get_profile(req.learner_id)
        await fe.publish_ether_event(
            learner_hash=profile.learner_hash,
            archetype=profile.archetype.value,
            cache_hit=profile.data_points > 0,
        )
        return action, fe, j, profiler, profile

    async def _generate_lesson(
        self, req: OrchestratorRequest, t0: float
    ) -> OperationResult:
        action, fe, j, _profiler, profile = await self._review_action(
            ActionType.GENERATE_LESSON, req, t0
        )
        lp = LessonParams(
            grade=req.grade,
            subject_code=req.params["subject_code"],
            subject_label=req.params.get("subject_label") or req.params["subject_code"],
            topic=req.params["topic"],
            home_language=req.params.get("home_language", "English"),
            learning_style_primary=req.params.get("learning_style_primary", "visual"),
            mastery_prior=float(req.params.get("mastery_prior", 0.5)),
            has_gap=bool(req.params.get("has_gap", False)),
            gap_grade=req.params.get("gap_grade"),
            sa_theme=req.params.get("sa_theme"),
        )
        system_prompt, user_prompt = await build_lesson_prompts(lp)
        stamp = await j.review(
            action, system_prompt=system_prompt, user_prompt=user_prompt
        )
        await fe.publish_stamp_issued(stamp, action)
        if stamp.status == StampStatus.REJECTED:
            return OperationResult(
                success=False,
                error=stamp.reasoning,
                stamp_status=stamp.status.value,
                constitutional_health=0.0,
                stamp_id=action.action_id,
                ether_archetype=profile.archetype.value,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        try:
            lesson, lesson_id = await generate_lesson(lp)
            await fe.publish_llm_result(
                action, provider="groq", success=True, latency_ms=0
            )
        except Exception as e:
            await fe.publish_llm_result(
                action, provider="groq", success=False, latency_ms=30_000
            )
            return OperationResult(
                success=False,
                error=str(e),
                stamp_status=stamp.status.value,
                constitutional_health=0.5,
                stamp_id=action.action_id,
                ether_archetype=profile.archetype.value,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        health = j.get_stats()["approval_rate"]
        return OperationResult(
            success=True,
            output=lesson.model_dump(),
            lesson_id=lesson_id,
            stamp_status=stamp.status.value,
            constitutional_health=float(health),
            stamp_id=action.action_id,
            ether_archetype=profile.archetype.value,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    async def _run_diagnostic(
        self, req: OrchestratorRequest, t0: float
    ) -> OperationResult:
        from app.api.ml.irt_engine import (
            AssessmentSession,
            ITEM_BANK,
            SAMPLE_ITEMS,
            Response,
            SubjectCode,
            activate_gap_probe,
            build_gap_report,
            check_gap_trigger,
            select_next_item,
            should_stop,
            update_theta_mle,
            Item,
        )
        from app.api.core.database import AsyncSessionFactory

        action, fe, j, _profiler, profile = await self._review_action(
            ActionType.RUN_DIAGNOSTIC, req, t0
        )
        stamp = await j.review(action)
        await fe.publish_stamp_issued(stamp, action)
        if stamp.status == StampStatus.REJECTED:
            return OperationResult(
                success=False,
                error=stamp.reasoning,
                stamp_status=stamp.status.value,
                constitutional_health=0.0,
                stamp_id=action.action_id,
                ether_archetype=profile.archetype.value,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        # Fetch items from DB
        async with AsyncSessionFactory() as session_db:
            result_db = await session_db.execute(
                text("SELECT * FROM item_bank WHERE subject_code = :sub AND is_active = TRUE"),
                {"sub": req.params["subject_code"]}
            )
            item_rows = result_db.mappings().all()
            db_items = [
                Item(
                    item_id=r["item_id"],
                    subject=SubjectCode(r["subject_code"]),
                    grade=r["grade_level"],
                    concept_code=r["concept_code"],
                    difficulty_b=r["difficulty"],
                    discrimination_a=r["discrimination"],
                    question_text=r["content"],
                    options=json.loads(r["options"]) if isinstance(r["options"], str) else r["options"],
                    correct_index=0, # Need to find index of correct_answer in options
                )
                for r in item_rows
            ]
            # Fix correct_index
            for i, item_obj in enumerate(db_items):
                try:
                    db_items[i].correct_index = item_obj.options.index(item_rows[i]["correct_answer"])
                except ValueError:
                    db_items[i].correct_index = 0

        subject = SubjectCode(req.params["subject_code"])
        session = AssessmentSession(learner_grade=req.grade, subject=subject)
        administered: set = set()
        max_questions = int(req.params.get("max_questions", 10))
        items_dict = {i.item_id: i for i in db_items}
        for _ in range(max_questions):
            if should_stop(session, max_questions=max_questions):
                break
            item = select_next_item(session, db_items, administered)
            if item is None:
                break
            # Use the correct answer for simulation or random
            is_correct = random.random() < 0.7 # Simulate slightly better than random
            session.responses.append(
                Response(
                    item_id=item.item_id,
                    is_correct=is_correct,
                    time_on_task_ms=random.randint(3000, 12000),
                )
            )
            administered.add(item.item_id)
            session.theta, session.sem = update_theta_mle(session.responses, items_dict)
            if check_gap_trigger(session):
                activate_gap_probe(session)
        gap_report = build_gap_report(session)
        await fe.publish_domain_event(
            EventType.DIAGNOSTIC_RUN,
            action,
            {
                "questions_administered": len(session.responses),
                "gap_probe_active": session.gap_probe_active,
            },
        )
        return OperationResult(
            success=True,
            output={
                "gap_report": gap_report,
                "session_summary": {
                    "questions_administered": len(session.responses),
                    "theta": round(session.theta, 3),
                    "sem": round(session.sem, 3),
                    "gap_probe_active": session.gap_probe_active,
                },
            },
            stamp_status=stamp.status.value,
            constitutional_health=float(j.get_stats()["approval_rate"]),
            stamp_id=action.action_id,
            ether_archetype=profile.archetype.value,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    async def _generate_study_plan(
        self, req: OrchestratorRequest, t0: float
    ) -> OperationResult:
        action, fe, j, _profiler, profile = await self._review_action(
            ActionType.GENERATE_STUDY_PLAN, req, t0
        )
        stamp = await j.review(action)
        await fe.publish_stamp_issued(stamp, action)
        if stamp.status == StampStatus.REJECTED:
            return OperationResult(
                success=False,
                error=stamp.reasoning,
                stamp_status=stamp.status.value,
                constitutional_health=0.0,
                stamp_id=action.action_id,
                ether_archetype=profile.archetype.value,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        try:
            plan = await generate_study_plan(
                grade=req.grade,
                knowledge_gaps=req.params.get("knowledge_gaps", []),
                subjects_mastery=req.params.get("subjects_mastery", {}),
            )
            await fe.publish_domain_event(
                EventType.STUDY_PLAN_GENERATED,
                action,
                {"gap_count": len(req.params.get("knowledge_gaps", []))},
            )
            return OperationResult(
                success=True,
                output=plan,
                stamp_status=stamp.status.value,
                constitutional_health=float(j.get_stats()["approval_rate"]),
                stamp_id=action.action_id,
                ether_archetype=profile.archetype.value,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        except Exception as e:
            return OperationResult(
                success=False,
                error=str(e),
                stamp_status=stamp.status.value,
                constitutional_health=0.5,
                stamp_id=action.action_id,
                ether_archetype=profile.archetype.value,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

    async def _generate_parent_report(
        self, req: OrchestratorRequest, t0: float
    ) -> OperationResult:
        action, fe, j, _profiler, profile = await self._review_action(
            ActionType.GENERATE_PARENT_REPORT, req, t0
        )
        stamp = await j.review(action)
        await fe.publish_stamp_issued(stamp, action)
        if stamp.status == StampStatus.REJECTED:
            return OperationResult(
                success=False,
                error=stamp.reasoning,
                stamp_status=stamp.status.value,
                constitutional_health=0.0,
                stamp_id=action.action_id,
                ether_archetype=profile.archetype.value,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        try:
            report = await generate_parent_report(
                grade=req.grade,
                streak_days=req.params.get("streak_days", 0),
                total_xp=req.params.get("total_xp", 0),
                subjects_mastery=req.params.get("subjects_mastery", {}),
                gaps=req.params.get("gaps", []),
            )
            await fe.publish_domain_event(
                EventType.PARENT_REPORT_GENERATED,
                action,
                {"gap_count": len(req.params.get("gaps", []))},
            )
            return OperationResult(
                success=True,
                output=report,
                stamp_status=stamp.status.value,
                constitutional_health=float(j.get_stats()["approval_rate"]),
                stamp_id=action.action_id,
                ether_archetype=profile.archetype.value,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        except Exception as e:
            return OperationResult(
                success=False,
                error=str(e),
                stamp_status=stamp.status.value,
                constitutional_health=0.5,
                stamp_id=action.action_id,
                ether_archetype=profile.archetype.value,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

    async def _start_diagnostic(
        self, req: OrchestratorRequest, t0: float
    ) -> OperationResult:
        from app.api.ml.irt_engine import (
            AssessmentSession,
            SubjectCode,
            select_next_item,
            Item,
        )
        from app.api.core.database import AsyncSessionFactory

        action, fe, j, _profiler, profile = await self._review_action(
            ActionType.START_DIAGNOSTIC, req, t0
        )
        stamp = await j.review(action)
        await fe.publish_stamp_issued(stamp, action)
        if stamp.status == StampStatus.REJECTED:
            return OperationResult(
                success=False,
                error=stamp.reasoning,
                stamp_status=stamp.status.value,
                constitutional_health=0.0,
                stamp_id=action.action_id,
                ether_archetype=profile.archetype.value,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

        # Fetch items from DB
        async with AsyncSessionFactory() as session_db:
            result_db = await session_db.execute(
                text("SELECT * FROM item_bank WHERE subject_code = :sub AND grade_level = :grade AND is_active = TRUE"),
                {"sub": req.params["subject_code"], "grade": req.grade}
            )
            item_rows = result_db.mappings().all()
            db_items = [
                Item(
                    item_id=r["item_id"],
                    subject=SubjectCode(r["subject_code"]),
                    grade=r["grade_level"],
                    concept_code=r["concept_code"],
                    difficulty_b=r["difficulty"],
                    discrimination_a=r["discrimination"],
                    question_text=r["content"],
                    options=json.loads(r["options"]) if isinstance(r["options"], str) else r["options"],
                    correct_index=0,
                )
                for r in item_rows
            ]

        subject = SubjectCode(req.params["subject_code"])
        session_obj = AssessmentSession(learner_grade=req.grade, subject=subject)

        item = select_next_item(session_obj, db_items, set())

        await fe.publish_domain_event(
            EventType.ACTION_SUBMITTED, action, {"subject": subject.value}
        )

        return OperationResult(
            success=True,
            output={
                "first_item": item,
                "session_state": {"theta": session_obj.theta, "sem": session_obj.sem},
            },
            stamp_status=stamp.status.value,
            constitutional_health=float(j.get_stats()["approval_rate"]),
            stamp_id=action.action_id,
            ether_archetype=profile.archetype.value,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    async def _submit_diagnostic_response(
        self, req: OrchestratorRequest, t0: float
    ) -> OperationResult:
        from app.api.ml.irt_engine import (
            AssessmentSession,
            ITEM_BANK,
            SAMPLE_ITEMS,
            Response,
            SubjectCode,
            activate_gap_probe,
            build_gap_report,
            check_gap_trigger,
            select_next_item,
            should_stop,
            update_theta_mle,
            Item,
        )
        from app.api.core.database import AsyncSessionFactory

        action, fe, j, _profiler, profile = await self._review_action(
            ActionType.SUBMIT_DIAGNOSTIC_RESPONSE, req, t0
        )
        stamp = await j.review(action)
        await fe.publish_stamp_issued(stamp, action)
        if stamp.status == StampStatus.REJECTED:
            return OperationResult(
                success=False,
                error=stamp.reasoning,
                stamp_status=stamp.status.value,
                constitutional_health=0.0,
                stamp_id=action.action_id,
                ether_archetype=profile.archetype.value,
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

        params = req.params
        subject = SubjectCode(params["subject_code"])
        prev_responses = [
            Response(**r) if isinstance(r, dict) else r
            for r in params.get("previous_responses", [])
        ]

        session_obj = AssessmentSession(learner_grade=req.grade, subject=subject)
        session_obj.responses = prev_responses
        session_obj.theta = params.get("theta", 0.0)
        session_obj.sem = params.get("sem", 1.5)
        session_obj.gap_probe_active = params.get("gap_probe_active", False)
        session_obj.current_grade = params.get("current_grade", req.grade)

        # Fetch all items for this subject to build the bank context
        async with AsyncSessionFactory() as session_db:
            result_db = await session_db.execute(
                text("SELECT * FROM item_bank WHERE subject_code = :sub AND is_active = TRUE"),
                {"sub": params["subject_code"]}
            )
            item_rows = result_db.mappings().all()
            db_items = [
                Item(
                    item_id=r["item_id"],
                    subject=SubjectCode(r["subject_code"]),
                    grade=r["grade_level"],
                    concept_code=r["concept_code"],
                    difficulty_b=r["difficulty"],
                    discrimination_a=r["discrimination"],
                    question_text=r["content"],
                    options=json.loads(r["options"]) if isinstance(r["options"], str) else r["options"],
                    correct_index=0,
                )
                for r in item_rows
            ]
            items_dict = {i.item_id: i for i in db_items}

        new_resp = Response(
            item_id=params["item_id"],
            is_correct=params["is_correct"],
            time_on_task_ms=params["time_on_task_ms"],
        )
        session_obj.responses.append(new_resp)

        session_obj.theta, session_obj.sem = update_theta_mle(
            session_obj.responses, items_dict
        )

        if check_gap_trigger(session_obj):
            activate_gap_probe(session_obj)

        is_complete = should_stop(
            session_obj, max_questions=params.get("max_questions", 20)
        )
        next_item = None
        gap_report = None

        if is_complete:
            gap_report = build_gap_report(session_obj)
        else:
            administered = {r.item_id for r in session_obj.responses}
            next_item = select_next_item(session_obj, db_items, administered)
            if not next_item:
                is_complete = True
                gap_report = build_gap_report(session_obj)

        return OperationResult(
            success=True,
            output={
                "is_complete": is_complete,
                "next_item": next_item.item_id if next_item else None,
                "next_item_data": next_item,
                "gap_report": gap_report,
                "session_state": {
                    "theta": session_obj.theta,
                    "sem": session_obj.sem,
                    "gap_probe_active": session_obj.gap_probe_active,
                    "current_grade": session_obj.current_grade,
                    "responses_count": len(session_obj.responses),
                },
            },
            stamp_status=stamp.status.value,
            constitutional_health=float(j.get_stats()["approval_rate"]),
            stamp_id=action.action_id,
            ether_archetype=profile.archetype.value,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
