"""
EduBoost SA — Study Plan Integration Tests

Integration tests covering:
- Plan generation, save, fetch, and refresh cycles
- Conflict, overload, and sparse-data scenarios
- Diagnostic linkage integration
"""
import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.services.study_plan_service import StudyPlanService, CAPS_SUBJECTS
from app.api.models.db_models import Learner, SubjectMastery, StudyPlan


class TestStudyPlanIntegration:
    """Integration tests for study plan end-to-end flows."""

    @pytest_asyncio.fixture
    async def mock_db_session(self):
        """Create a mock database session with realistic setup."""
        session = AsyncMock()
        
        # Mock commit and refresh
        session.commit = AsyncMock()
        
        # Mock refresh to set created_at on the plan object
        async def mock_refresh(plan):
            if hasattr(plan, 'plan_id') and plan.plan_id:
                plan.created_at = datetime.now()
        session.refresh = mock_refresh
        session.add = MagicMock()
        
        return session

    @pytest_asyncio.fixture
    def mock_learner(self):
        """Create a realistic mock learner."""
        learner = MagicMock(spec=Learner)
        learner.learner_id = uuid4()
        learner.grade = 5
        learner.home_language = "eng"
        learner.overall_mastery = 0.55
        learner.streak_days = 3
        learner.total_xp = 150
        learner.created_at = datetime.now() - timedelta(days=30)
        learner.last_active_at = datetime.now() - timedelta(hours=2)
        return learner

    @pytest_asyncio.fixture
    def mock_subject_mastery_records(self):
        """Create mock subject mastery records."""
        return [
            MagicMock(
                subject_code="MATH",
                mastery_score=0.45,
                knowledge_gaps=["fractions", "multiplication"]
            ),
            MagicMock(
                subject_code="ENG",
                mastery_score=0.70,
                knowledge_gaps=["comprehension"]
            ),
            MagicMock(
                subject_code="NS",
                mastery_score=0.35,
                knowledge_gaps=["matter", "energy"]
            ),
        ]

    # =====================================================================
    # Test: Plan Generation, Save, Fetch Cycle
    # =====================================================================

    @pytest.mark.asyncio
    async def test_generate_save_fetch_cycle(self, mock_db_session, mock_learner, mock_subject_mastery_records):
        """Test complete cycle: generate plan -> save to DB -> fetch."""
        service = StudyPlanService(mock_db_session)
        learner_id = mock_learner.learner_id

        # Setup: learner exists
        mock_db_session.get.return_value = mock_learner
        
        # Setup: subject mastery query returns records
        mastery_result = MagicMock()
        mastery_result.scalars.return_value.all.return_value = mock_subject_mastery_records
        mock_db_session.execute.return_value = mastery_result

        # Execute: generate plan
        plan = await service.generate_plan(
            learner_id=learner_id,
            grade=5,
            gap_ratio=0.4,
        )

        # Verify: plan was added to session
        mock_db_session.add.assert_called_once()
        
        # Verify: commit was called
        mock_db_session.commit.assert_called_once()

        # Verify: plan has expected structure
        assert plan["learner_id"] == str(learner_id)
        assert plan["grade"] == 5
        assert "schedule" in plan
        assert "week_focus" in plan
        assert plan["gap_ratio"] == 0.4

        # Verify: schedule has all days
        schedule = plan["schedule"]
        expected_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in expected_days:
            assert day in schedule, f"Missing day: {day}"

    @pytest.mark.asyncio
    async def test_fetch_current_plan(self, mock_db_session, mock_learner):
        """Test fetching the current active plan."""
        service = StudyPlanService(mock_db_session)
        learner_id = mock_learner.learner_id

        # Create a mock existing plan
        existing_plan = MagicMock(spec=StudyPlan)
        existing_plan.plan_id = uuid4()
        existing_plan.learner_id = learner_id
        existing_plan.week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        existing_plan.schedule = {"monday": [], "tuesday": [], "wednesday": []}
        existing_plan.gap_ratio = 0.4
        existing_plan.week_focus = "Focus on fractions remediation"
        existing_plan.generated_by = "ALGORITHM"
        existing_plan.created_at = datetime.now()

        # Setup: query returns existing plan
        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = existing_plan
        mock_db_session.execute.return_value = plan_result

        # Execute
        fetched_plan = await service.get_current_plan(learner_id)

        # Verify
        assert fetched_plan is not None
        assert fetched_plan.plan_id == existing_plan.plan_id

    @pytest.mark.asyncio
    async def test_fetch_no_plan_returns_none(self, mock_db_session):
        """Test that fetching a non-existent plan returns None."""
        service = StudyPlanService(mock_db_session)
        learner_id = uuid4()

        # Setup: query returns None
        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = plan_result

        # Execute
        fetched_plan = await service.get_current_plan(learner_id)

        # Verify
        assert fetched_plan is None

    # =====================================================================
    # Test: Plan Refresh Cycle
    # =====================================================================

    @pytest.mark.asyncio
    async def test_refresh_plan_creates_new_plan(self, mock_db_session, mock_learner, mock_subject_mastery_records):
        """Test that refreshing a plan creates a new one."""
        service = StudyPlanService(mock_db_session)
        learner_id = mock_learner.learner_id

        # Setup
        mock_db_session.get.return_value = mock_learner
        
        mastery_result = MagicMock()
        mastery_result.scalars.return_value.all.return_value = mock_subject_mastery_records
        mock_db_session.execute.return_value = mastery_result

        # Execute: refresh plan
        new_plan = await service.refresh_plan(learner_id=learner_id, gap_ratio=0.5)

        # Verify: new plan was created
        assert new_plan is not None
        assert new_plan["learner_id"] == str(learner_id)
        assert new_plan["gap_ratio"] == 0.5
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_refresh_nonexistent_plan_raises_error(self, mock_db_session):
        """Test that refreshing for non-existent learner raises error."""
        service = StudyPlanService(mock_db_session)
        learner_id = uuid4()

        # Setup: learner not found
        mock_db_session.get.return_value = None

        # Execute & Assert
        with pytest.raises(ValueError, match="not found"):
            await service.refresh_plan(learner_id=learner_id)

    # =====================================================================
    # Test: Conflict, Overload, and Sparse-Data Scenarios
    # =====================================================================

    @pytest.mark.asyncio
    async def test_sparse_data_no_mastery_records(self, mock_db_session, mock_learner):
        """Test plan generation with no subject mastery data (sparse data)."""
        service = StudyPlanService(mock_db_session)
        learner_id = mock_learner.learner_id

        # Setup: no mastery records
        mock_db_session.get.return_value = mock_learner
        
        mastery_result = MagicMock()
        mastery_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mastery_result

        # Execute: generate plan with no data
        plan = await service.generate_plan(
            learner_id=learner_id,
            grade=5,
            gap_ratio=0.4,
        )

        # Verify: plan still generated with defaults
        assert plan is not None
        assert "schedule" in plan
        
        # Should have fallback tasks for empty data
        total_tasks = sum(len(tasks) for tasks in plan["schedule"].values())
        assert total_tasks > 0, "Should generate fallback tasks for sparse data"

    @pytest.mark.asyncio
    async def test_sparse_data_no_knowledge_gaps(self, mock_db_session, mock_learner):
        """Test plan generation with no knowledge gaps (all subjects mastered)."""
        service = StudyPlanService(mock_db_session)
        learner_id = mock_learner.learner_id

        # Setup: high mastery, no gaps
        mock_db_session.get.return_value = mock_learner
        
        high_mastery_records = [
            MagicMock(subject_code="MATH", mastery_score=0.9, knowledge_gaps=[]),
            MagicMock(subject_code="ENG", mastery_score=0.85, knowledge_gaps=[]),
        ]
        mastery_result = MagicMock()
        mastery_result.scalars.return_value.all.return_value = high_mastery_records
        mock_db_session.execute.return_value = mastery_result

        # Execute
        plan = await service.generate_plan(
            learner_id=learner_id,
            grade=5,
            gap_ratio=0.4,
        )

        # Verify: plan generated with grade-level advancement focus
        assert plan is not None
        assert "week_focus" in plan
        # Should focus on advancement, not remediation
        assert "advancement" in plan["week_focus"].lower() or "strengthen" in plan["week_focus"].lower()

    @pytest.mark.asyncio
    async def test_overload_many_knowledge_gaps(self, mock_db_session, mock_learner):
        """Test plan generation with many knowledge gaps (overload scenario)."""
        service = StudyPlanService(mock_db_session)
        learner_id = mock_learner.learner_id

        # Setup: many gaps
        mock_db_session.get.return_value = mock_learner
        
        many_gaps = [
            "fractions", "division", "multiplication", "geometry", "algebra",
            "data", "volume", "measurement", "percentages", "ratios"
        ]
        low_mastery_records = [
            MagicMock(subject_code="MATH", mastery_score=0.2, knowledge_gaps=many_gaps),
        ]
        mastery_result = MagicMock()
        mastery_result.scalars.return_value.all.return_value = low_mastery_records
        mock_db_session.execute.return_value = mastery_result

        # Execute
        plan = await service.generate_plan(
            learner_id=learner_id,
            grade=5,
            gap_ratio=0.6,  # High remediation ratio
        )

        # Verify: plan handles overload by limiting tasks
        assert plan is not None
        total_tasks = sum(len(tasks) for tasks in plan["schedule"].values())
        # Should cap at reasonable number (service limits to 5 gaps)
        assert total_tasks <= 10, "Should limit tasks to prevent overload"

    @pytest.mark.asyncio
    async def test_conflict_gap_ratio_bounds(self, mock_db_session, mock_learner):
        """Test that gap_ratio is properly bounded."""
        service = StudyPlanService(mock_db_session)
        learner_id = mock_learner.learner_id

        mock_db_session.get.return_value = mock_learner
        
        mastery_result = MagicMock()
        mastery_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mastery_result

        # Test with out-of-bounds ratio (should be clamped)
        plan = await service.generate_plan(
            learner_id=learner_id,
            grade=5,
            gap_ratio=0.9,  # Above max of 0.6
        )

        # Verify: ratio is clamped to max
        assert plan["gap_ratio"] <= 0.6, "gap_ratio should be clamped to 0.6"

        plan2 = await service.generate_plan(
            learner_id=learner_id,
            grade=5,
            gap_ratio=0.1,  # Below min of 0.3
        )

        # Verify: ratio is clamped to min
        assert plan2["gap_ratio"] >= 0.3, "gap_ratio should be clamped to 0.3"

    # =====================================================================
    # Test: Diagnostic Linkage
    # =====================================================================

    @pytest.mark.asyncio
    async def test_diagnostic_linkage_integration(self, mock_db_session, mock_learner):
        """Test that study plan uses diagnostic-derived knowledge gaps."""
        service = StudyPlanService(mock_db_session)
        learner_id = mock_learner.learner_id

        # Simulate diagnostic output: specific concept-level gaps
        diagnostic_gaps = [
            {"concept": "fractions", "subject": "MATH", "confidence": 0.9},
            {"concept": "comprehension", "subject": "ENG", "confidence": 0.85},
            {"concept": "matter", "subject": "NS", "confidence": 0.8},
        ]

        # Setup: learner with diagnostic-derived gaps
        mock_db_session.get.return_value = mock_learner
        
        mastery_result = MagicMock()
        mastery_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mastery_result

        # Execute: pass diagnostic gaps directly
        plan = await service.generate_plan(
            learner_id=learner_id,
            grade=5,
            knowledge_gaps=[g["concept"] for g in diagnostic_gaps],
            gap_ratio=0.5,
        )

        # Verify: plan incorporates diagnostic gaps
        schedule = plan["schedule"]
        all_tasks = []
        for tasks in schedule.values():
            all_tasks.extend(tasks)

        remediation_tasks = [t for t in all_tasks if t.get("is_gap_focus")]
        
        # Should have remediation tasks for diagnostic gaps
        assert len(remediation_tasks) > 0, "Should create remediation tasks from diagnostic gaps"
        
        # Verify: gaps are reflected in week focus
        assert "fractions" in plan["week_focus"].lower() or "comprehension" in plan["week_focus"].lower()

    @pytest.mark.asyncio
    async def test_grade_band_diagnostic_integration(self, mock_db_session):
        """Test that diagnostic gaps are handled correctly for different grade bands."""
        service = StudyPlanService(AsyncMock())

        # Test Grade R-3 band
        grade_r3_gaps = ["counting", "phonics", "shapes"]
        schedule_r3 = service._generate_weekly_schedule(
            grade=2,
            grade_band="R-3",
            subjects_mastery={},
            knowledge_gaps=grade_r3_gaps,
            gap_ratio=0.5,
        )

        # Verify: R-3 uses R-3 focus areas
        all_tasks_r3 = [t for tasks in schedule_r3.values() for t in tasks]
        assert len(all_tasks_r3) > 0

        # Test Grade 4-7 band
        grade_47_gaps = ["fractions", "comprehension", "matter"]
        schedule_47 = service._generate_weekly_schedule(
            grade=5,
            grade_band="4-7",
            subjects_mastery={},
            knowledge_gaps=grade_47_gaps,
            gap_ratio=0.5,
        )

        # Verify: 4-7 uses 4-7 focus areas
        all_tasks_47 = [t for tasks in schedule_47.values() for t in tasks]
        assert len(all_tasks_47) > 0

    # =====================================================================
    # Test: Plan with Rationale
    # =====================================================================

    @pytest.mark.asyncio
    async def test_plan_with_rationale_includes_explanations(self, mock_db_session, mock_learner):
        """Test that plan with rationale includes task explanations."""
        service = StudyPlanService(mock_db_session)
        learner_id = mock_learner.learner_id

        # Setup: create existing plan
        mock_db_session.get.return_value = mock_learner
        
        existing_plan = MagicMock(spec=StudyPlan)
        existing_plan.plan_id = uuid4()
        existing_plan.learner_id = learner_id
        existing_plan.week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        existing_plan.schedule = {
            "monday": [
                {"task_id": str(uuid4()), "type": "remediation", "subject": "MATH", "concept": "fractions", "title": "Review: Fractions"}
            ],
            "tuesday": []
        }
        existing_plan.gap_ratio = 0.4
        existing_plan.week_focus = "Focus on fractions remediation"
        existing_plan.generated_by = "ALGORITHM"
        existing_plan.created_at = datetime.now()

        mastery_result = MagicMock()
        mastery_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mastery_result

        # Also need to handle the get_current_plan query
        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = existing_plan
        
        # Need multiple execute calls - use a side_effect function
        call_count = [0]
        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return plan_result
            return mastery_result
        mock_db_session.execute.side_effect = execute_side_effect

        # Execute
        plan_with_rationale = await service.get_plan_with_rationale(learner_id)

        # Verify: rationale is included
        assert "schedule_with_rationale" in plan_with_rationale
        assert "week_focus_rationale" in plan_with_rationale
        
        monday_tasks = plan_with_rationale["schedule_with_rationale"].get("monday", [])
        assert len(monday_tasks) > 0
        assert "rationale" in monday_tasks[0], "Each task should have a rationale"

    # =====================================================================
    # Test: Edge Cases
    # =====================================================================

    @pytest.mark.asyncio
    async def test_grade_0_grade_r_handling(self, mock_db_session):
        """Test plan generation for Grade R (grade=0)."""
        service = StudyPlanService(mock_db_session)
        
        mock_learner = MagicMock(spec=Learner)
        mock_learner.learner_id = uuid4()
        mock_learner.grade = 0
        
        mock_db_session.get.return_value = mock_learner
        
        mastery_result = MagicMock()
        mastery_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mastery_result

        # Execute
        plan = await service.generate_plan(
            learner_id=mock_learner.learner_id,
            grade=0,
            gap_ratio=0.4,
        )

        # Verify: uses R-3 band
        assert plan is not None
        assert plan["grade"] == 0

    @pytest.mark.asyncio
    async def test_empty_schedule_fallback(self, mock_db_session, mock_learner):
        """Test that empty inputs still produce a valid schedule."""
        service = StudyPlanService(mock_db_session)
        learner_id = mock_learner.learner_id

        mock_db_session.get.return_value = mock_learner
        
        mastery_result = MagicMock()
        mastery_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mastery_result

        # Execute with all empty inputs
        plan = await service.generate_plan(
            learner_id=learner_id,
            grade=5,
            knowledge_gaps=[],
            subjects_mastery={},
            gap_ratio=0.4,
        )

        # Verify: still produces valid schedule
        assert plan is not None
        assert "schedule" in plan
        assert len(plan["schedule"]) == 7  # All 7 days
        
        # Should have fallback tasks
        total_tasks = sum(len(tasks) for tasks in plan["schedule"].values())
        assert total_tasks > 0, "Should generate fallback tasks"