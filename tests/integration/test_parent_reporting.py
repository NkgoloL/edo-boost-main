import pytest
import uuid
from datetime import datetime, timedelta
from app.api.core.database import AsyncSessionFactory
from app.api.services.parent_portal_service import ParentPortalService
from app.api.models.db_models import Learner, SubjectMastery, ParentLearnerLink, ConsentAudit

@pytest.mark.asyncio
async def test_parent_report_loop():
    """
    Verify the parent report generation loop including access checks.
    """
    async with AsyncSessionFactory() as session:
        learner_id = uuid.uuid4()
        guardian_id = uuid.uuid4()
        
        # 1. Setup learner and link
        learner = Learner(learner_id=learner_id, grade=3, total_xp=500, overall_mastery=0.6)
        session.add(learner)
        
        link = ParentLearnerLink(parent_id=guardian_id, learner_id=learner_id, relationship="guardian")
        session.add(link)
        
        # 2. Add some mastery data
        mastery = SubjectMastery(
            learner_id=learner_id, 
            subject_code="MATH", 
            grade_level=3,
            mastery_score=0.75,
            knowledge_gaps=[{"concept": "MATH_ADD", "severity": 0.5}]
        )
        session.add(mastery)
        
        await session.commit()
        
        # 3. Generate Report
        service = ParentPortalService(session)
        report = await service.generate_parent_report(learner_id, guardian_id)
        
        # 4. Asserts
        assert report["learner_id"] == str(learner_id)
        assert "summary" in report
        assert "sections" in report
        assert "recommendations" in report
        assert len(report["mastery_snapshot"]) > 0
        assert report["mastery_snapshot"][0]["subject_code"] == "MATH"
        
        print(f"Report Summary: {report['summary']}")

@pytest.mark.asyncio
async def test_parent_access_revoked():
    """
    Verify that report generation fails if consent is revoked.
    """
    async with AsyncSessionFactory() as session:
        learner_id = uuid.uuid4()
        guardian_id = uuid.uuid4()
        
        now = datetime.now()
        # No link, but legacy consent
        consent = ConsentAudit(
            pseudonym_id=learner_id, 
            event_type="consent_granted",
            occurred_at=now - timedelta(hours=1)
        )
        session.add(consent)
        await session.flush()
        
        # Revoke consent
        revoke = ConsentAudit(
            pseudonym_id=learner_id, 
            event_type="consent_revoked",
            occurred_at=now
        )
        session.add(revoke)
        await session.commit()
        
        service = ParentPortalService(session)
        with pytest.raises(ValueError, match="Guardian consent has been revoked"):
            await service.generate_parent_report(learner_id, guardian_id)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_parent_report_loop())
