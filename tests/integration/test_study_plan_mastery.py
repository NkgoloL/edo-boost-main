import pytest
import uuid
from sqlalchemy import text
from app.api.core.database import AsyncSessionFactory
from app.api.services.study_plan_service import StudyPlanService
from app.api.models.db_models import Learner, SubjectMastery

@pytest.mark.asyncio
async def test_study_plan_mastery_prioritization():
    """
    Verify that the study plan prioritizes foundational gaps and handles low mastery.
    """
    async with AsyncSessionFactory() as session:
        # 1. Create a dummy learner
        learner_id = uuid.uuid4()
        learner = Learner(
            learner_id=learner_id,
            grade=5,
            home_language="eng"
        )
        session.add(learner)
        
        # 2. Set up Subject Mastery with gaps
        # Gaps: MATH_FRAC (Grade 3), MATH_DEC (Grade 5, high severity)
        mastery = SubjectMastery(
            learner_id=learner_id,
            subject_code="MATH",
            grade_level=5,
            mastery_score=0.2, # Critically low
            knowledge_gaps=[
                {"concept": "MATH_DECIMAL", "gap_grade": 5, "severity": 0.9},
                {"concept": "MATH_FRACTION", "gap_grade": 3, "severity": 0.4}
            ]
        )
        session.add(mastery)
        await session.commit()

        # 3. Generate plan
        service = StudyPlanService(session)
        plan_data = await service.generate_plan(learner_id, grade=5)
        
        schedule = plan_data["schedule"]
        tasks = []
        for day in schedule.values():
            tasks.extend(day)
            
        # 4. Asserts
        # - Foundational gap (Grade 3) should be present
        fraction_tasks = [t for t in tasks if t["concept"] == "MATH_FRACTION"]
        assert len(fraction_tasks) > 0
        assert fraction_tasks[0]["grade"] == 3
        
        # - Critically low mastery (0.2) should trigger spaced repetition
        # Math tasks should be abundant
        math_tasks = [t for t in tasks if t["subject"] == "MATH"]
        assert len(math_tasks) >= 4 # Should have several due to low mastery
        
        # - High severity gap should have longer duration
        decimal_tasks = [t for t in tasks if t["concept"] == "MATH_DECIMAL"]
        assert decimal_tasks[0]["duration_minutes"] == 30 # Severity 0.9 > 0.7
        
        print(f"Plan Week Focus: {plan_data['week_focus']}")
        assert "Foundational Bridge" in plan_data["week_focus"]
        assert "Math Fraction" in plan_data["week_focus"] # Grade 3 gap prioritized

if __name__ == "__main__":
    # This is for manual running if needed, but normally run via pytest
    import asyncio
    asyncio.run(test_study_plan_mastery_prioritization())
