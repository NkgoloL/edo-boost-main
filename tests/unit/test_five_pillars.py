"""
TESTS — Pillar integration test suite.
Covers:
  - ConstitutionalRule immutability (hash + ORM events)
  - PII scrubber (all known patterns)
  - WorkerAgent stamp gate (approved / rejected / missing stamp)
  - JudiciaryService fast-path checks
  - Consent gate enforcement
  - Orchestrator state machine valid/invalid transitions
  - AuditAgent orphan detection
"""
from __future__ import annotations

import uuid
from datetime import date

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def valid_rule():
    from app.api.judiciary.models import ConstitutionalRule, ScopeModel
    return ConstitutionalRule(
        rule_id="POPIA-S11-DATA-MIN",
        source_document="Protection of Personal Information Act (4/2013)",
        rule_text="Personal information must be collected for a specific, explicitly defined purpose.",
        scope=ScopeModel(subjects=[], grade_min=0, grade_max=12),
        effective_date=date(2021, 7, 1),
    )


@pytest.fixture
def sample_action():
    from app.api.judiciary.base import ExecutiveAction
    return ExecutiveAction(
        agent_id="lesson-service",
        intent="generate_lesson",
        parameters={"subject": "Mathematics", "grade": 5, "topic": "Fractions"},
        claimed_rules=["POPIA-S11-DATA-MIN", "CAPS-LESSON-SCOPE"],
        learner_pseudonym="PSEUDO-ABC123",
    )


# ============================================================================
# PILLAR 1: ConstitutionalRule immutability
# ============================================================================
class TestConstitutionalRuleImmutability:
    def test_hash_is_computed_on_construction(self, valid_rule):
        assert valid_rule.immutable_hash != ""
        assert len(valid_rule.immutable_hash) == 64

    def test_hash_is_deterministic(self, valid_rule):
        from app.api.judiciary.models import ConstitutionalRule, ScopeModel
        rule2 = ConstitutionalRule(
            rule_id=valid_rule.rule_id,
            source_document=valid_rule.source_document,
            rule_text=valid_rule.rule_text,
            scope=ScopeModel(),
            effective_date=valid_rule.effective_date,
        )
        assert rule2.immutable_hash == valid_rule.immutable_hash

    def test_verify_returns_true_for_unmodified_rule(self, valid_rule):
        assert valid_rule.verify_integrity() is True

    def test_pydantic_frozen_prevents_mutation(self, valid_rule):
        with pytest.raises(Exception):
            valid_rule.rule_text = "tampered"

    def test_different_text_produces_different_hash(self, valid_rule):
        from app.api.judiciary.models import ConstitutionalRule, ScopeModel
        tampered = ConstitutionalRule(
            rule_id=valid_rule.rule_id,
            source_document=valid_rule.source_document,
            rule_text="DIFFERENT TEXT",
            scope=ScopeModel(),
            effective_date=valid_rule.effective_date,
        )
        assert tampered.immutable_hash != valid_rule.immutable_hash

    def test_orm_update_event_raises(self):
        from app.api.judiciary.models import ConstitutionalRuleORM, _block_update
        orm = ConstitutionalRuleORM()
        with pytest.raises(RuntimeError, match="immutable"):
            _block_update(None, None, orm)

    def test_orm_delete_event_raises(self):
        from app.api.judiciary.models import _block_delete, ConstitutionalRuleORM
        with pytest.raises(RuntimeError, match="cannot be deleted"):
            _block_delete(None, None, ConstitutionalRuleORM())


# ============================================================================
# POPIA: PII Scrubber
# ============================================================================
class TestPIIScrubber:
    def _scrub(self, text_: str):
        from app.api.judiciary.compliance import scrub_pii
        return scrub_pii(text_)

    def test_clean_text_passes(self):
        result = self._scrub("A learner struggled with fractions in Grade 5.")
        assert result.clean is True
        assert result.violations == []

    def test_sa_id_number_detected(self):
        result = self._scrub("The learner's ID is 9001015800089.")
        assert result.clean is False
        assert "SA_ID_NUMBER" in result.violations

    def test_email_detected(self):
        result = self._scrub("Contact parent@example.co.za for more info.")
        assert result.clean is False
        assert "EMAIL_ADDRESS" in result.violations

    def test_sa_mobile_detected(self):
        result = self._scrub("Call 0821234567 to follow up.")
        assert result.clean is False
        assert "SA_MOBILE_NUMBER" in result.violations

    def test_assert_pii_clean_raises_on_pii(self):
        from app.api.judiciary.compliance import assert_pii_clean
        with pytest.raises(ValueError, match="PII detected"):
            assert_pii_clean("Email: parent@example.co.za", context="test")

    def test_assert_pii_clean_passes_clean_text(self):
        from app.api.judiciary.compliance import assert_pii_clean
        assert_pii_clean("Grade 5 Mathematics: Introduction to Fractions")

    def test_multiple_pii_types_detected(self):
        result = self._scrub("ID: 9001015800089 and email: test@test.com and mobile 0821234567")
        assert result.clean is False
        assert len(result.violations) >= 2


# ============================================================================
# PILLAR 2: WorkerAgent stamp gate
# ============================================================================
class TestWorkerAgentStampGate:
    @pytest.mark.asyncio
    async def test_approved_stamp_unblocks_execution(self, sample_action):
        from app.api.judiciary.base import JudiciaryStampRef, WorkerAgent

        class _ConcreteWorker(WorkerAgent):
            def __init__(self):
                super().__init__("test-agent", "test-intent")
                self.executed = False

            async def _build_action(self, **kwargs):
                return sample_action

            async def _execute(self, action, stamp, **kwargs):
                self._assert_stamped()
                self.executed = True
                return "done"

        mock_stamp = JudiciaryStampRef(
            stamp_id=str(uuid.uuid4()),
            action_id=sample_action.action_id,
            verdict="APPROVED",
        )

        worker = _ConcreteWorker()
        with patch("app.api.judiciary.client.JudiciaryClient") as MockClient:
            instance = AsyncMock()
            instance.review = AsyncMock(return_value=mock_stamp)
            MockClient.return_value = instance
            result = await worker.run()

        assert worker.executed is True
        assert result == "done"

    @pytest.mark.asyncio
    async def test_rejected_stamp_raises_unauthorized(self, sample_action):
        from app.api.judiciary.base import (
            JudiciaryStampRef, UnauthorizedExecutionError, WorkerAgent
        )

        class _ConcreteWorker(WorkerAgent):
            def __init__(self):
                super().__init__("test-agent", "test-intent")

            async def _build_action(self, **kwargs):
                return sample_action

            async def _execute(self, action, stamp, **kwargs):
                return "should not reach"

        mock_stamp = JudiciaryStampRef(
            stamp_id=str(uuid.uuid4()),
            action_id=sample_action.action_id,
            verdict="REJECTED",
            reason="PII detected in parameters",
        )

        worker = _ConcreteWorker()
        with patch("app.api.judiciary.client.JudiciaryClient") as MockClient:
            instance = AsyncMock()
            instance.review = AsyncMock(return_value=mock_stamp)
            MockClient.return_value = instance
            with pytest.raises(UnauthorizedExecutionError, match="REJECTED"):
                await worker.run()

    @pytest.mark.asyncio
    async def test_assert_stamped_raises_without_prior_stamp(self):
        from app.api.judiciary.base import UnauthorizedExecutionError, WorkerAgent

        class _BadWorker(WorkerAgent):
            def __init__(self):
                super().__init__("bad-agent", "bad-intent")

            async def _build_action(self, **kwargs):
                pass

            async def _execute(self, action, stamp, **kwargs):
                pass

            def try_assert(self):
                self._assert_stamped()

        worker = _BadWorker()
        with pytest.raises(UnauthorizedExecutionError, match="without a valid stamp"):
            worker.try_assert()

    @pytest.mark.asyncio
    async def test_hmac_signature_verification(self, sample_action):
        key = "test-secret-key"
        signed = sample_action.sign(key)
        assert signed.signature != ""
        assert signed.verify_signature(key) is True

    @pytest.mark.asyncio
    async def test_tampered_signature_fails_verification(self, sample_action):
        key = "test-secret-key"
        signed = sample_action.sign(key)
        tampered = signed.model_copy(update={"signature": "00000000"})
        assert tampered.verify_signature(key) is False


# ============================================================================
# PILLAR 3: JudiciaryService fast-path
# ============================================================================
class TestJudiciaryFastPath:
    def _make_action(self, params=None, learner_pseudonym="PSEUDO-XYZ"):
        from app.api.judiciary.models import ExecutiveActionIn
        from datetime import datetime, timezone
        return ExecutiveActionIn(
            action_id=str(uuid.uuid4()),
            agent_id="test-agent",
            intent="test",
            parameters=params or {},
            claimed_rules=[],
            learner_pseudonym=learner_pseudonym,
            timestamp=datetime.now(timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_sa_id_number_triggers_fast_rejection(self):
        from app.api.judiciary.service import JudiciaryService
        action = self._make_action(params={"data": "9001015800089"})
        service = JudiciaryService(session=MagicMock())
        result = await service._fast_path_check(action)
        assert result is not None
        assert "PII pattern" in result

    @pytest.mark.asyncio
    async def test_email_in_params_triggers_fast_rejection(self):
        from app.api.judiciary.service import JudiciaryService
        action = self._make_action(params={"contact": "parent@example.co.za"})
        service = JudiciaryService(session=MagicMock())
        result = await service._fast_path_check(action)
        assert result is not None

    @pytest.mark.asyncio
    async def test_clean_action_passes_fast_path(self):
        from app.api.judiciary.service import JudiciaryService
        action = self._make_action(params={"subject": "Maths", "grade": 5})
        service = JudiciaryService(session=MagicMock())
        result = await service._fast_path_check(action)
        assert result is None


# ============================================================================
# CONSENT GATE
# ============================================================================
class TestConsentGate:
    @pytest.mark.asyncio
    async def test_active_consent_passes(self):
        from app.api.judiciary.compliance import ConsentGate
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=("ACTIVE",)))
        )
        gate = ConsentGate(mock_session)
        await gate.assert_active("PSEUDO-123")  # should not raise

    @pytest.mark.asyncio
    async def test_no_consent_raises_permission_error(self):
        from app.api.judiciary.compliance import ConsentGate
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=None))
        )
        gate = ConsentGate(mock_session)
        with pytest.raises(PermissionError, match="ACTIVE"):
            await gate.assert_active("PSEUDO-NOCONSENT")

    @pytest.mark.asyncio
    async def test_revoked_consent_raises_permission_error(self):
        from app.api.judiciary.compliance import ConsentGate
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(first=MagicMock(return_value=("REVOKED",)))
        )
        gate = ConsentGate(mock_session)
        with pytest.raises(PermissionError):
            await gate.assert_active("PSEUDO-REVOKED")


# ============================================================================
# ORCHESTRATOR: State Machine
# ============================================================================
class TestSessionOrchestrator:
    @pytest.mark.asyncio
    async def test_valid_transition_succeeds(self):
        from app.api.judiciary.state_machine import SessionOrchestrator, SessionState

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=None)))
        mock_session.commit = AsyncMock()

        orch = SessionOrchestrator(mock_session)

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock()
        orch._redis = mock_redis

        with patch.object(orch, "_emit_transition_event", new_callable=AsyncMock):
            with patch.object(orch, "_persist_transition", new_callable=AsyncMock):
                # Patch get_state to return IDLE
                with patch.object(orch, "get_state", new_callable=AsyncMock, return_value=SessionState.IDLE):
                    result = await orch.transition("PSEUDO-1", SessionState.DIAGNOSTIC_IN_PROGRESS)
        assert result == SessionState.DIAGNOSTIC_IN_PROGRESS

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self):
        from app.api.judiciary.state_machine import InvalidTransitionError, SessionOrchestrator, SessionState

        mock_session = AsyncMock()
        orch = SessionOrchestrator(mock_session)
        with patch.object(orch, "get_state", new_callable=AsyncMock, return_value=SessionState.IDLE):
            with pytest.raises(InvalidTransitionError):
                await orch.transition("PSEUDO-1", SessionState.ARCHIVED)

    @pytest.mark.asyncio
    async def test_suspended_learner_cannot_transition_except_to_archived(self):
        from app.api.judiciary.state_machine import (
            ConsentSuspendedError, InvalidTransitionError, SessionOrchestrator, SessionState
        )
        mock_session = AsyncMock()
        orch = SessionOrchestrator(mock_session)
        with patch.object(orch, "get_state", new_callable=AsyncMock, return_value=SessionState.SUSPENDED):
            with pytest.raises((ConsentSuspendedError, InvalidTransitionError)):
                await orch.transition("PSEUDO-1", SessionState.LESSON_IN_PROGRESS)


# ============================================================================
# IRT ENGINE: parameter versioning
# ============================================================================
class TestIRTEngine:
    @pytest.mark.asyncio
    async def test_parameter_update_creates_new_version(self):
        from app.api.judiciary.engine import IRTEngine

        mock_session = AsyncMock()
        # First call: MAX(version) = 0
        mock_session.execute = AsyncMock(
            side_effect=[
                MagicMock(first=MagicMock(return_value=(0,))),  # SELECT MAX(version)
                MagicMock(),                                      # INSERT
            ]
        )
        mock_session.commit = AsyncMock()
        engine = IRTEngine(mock_session)
        version = await engine.update_item_params("ITEM-001", a=1.2, b=0.5, c=0.2)
        assert version == 1

    def test_irt_3pl_probability_bounds(self):
        from app.api.judiciary.engine import IRTItem
        item = IRTItem("TEST-001", a=1.0, b=0.0, c=0.25)
        # P(theta=high) should approach 1.0
        assert item.probability(5.0) > 0.99
        # P(theta=low) should approach c (guessing)
        assert item.probability(-5.0) < 0.30
        # P(theta=b) should be midpoint between c and 1
        p_at_b = item.probability(0.0)
        assert 0.5 < p_at_b < 0.7

    def test_eap_update_increases_theta_on_correct(self):
        from app.api.judiciary.engine import IRTEngine, IRTItem
        engine = IRTEngine(session=MagicMock())
        item = IRTItem("ITEM-001", a=1.0, b=0.0, c=0.25)
        updated = engine._eap_update(0.0, item, correct=True)
        assert updated > 0.0

    def test_eap_update_decreases_theta_on_incorrect(self):
        from app.api.judiciary.engine import IRTEngine, IRTItem
        engine = IRTEngine(session=MagicMock())
        item = IRTItem("ITEM-001", a=1.0, b=0.0, c=0.25)
        updated = engine._eap_update(0.0, item, correct=False)
        assert updated < 0.0


# ============================================================================
# ETHER: Profile build and decay
# ============================================================================
class TestEtherProfiler:
    def test_build_profile_returns_valid_sephira(self):
        from app.api.judiciary.profiler import EtherProfiler
        profiler = EtherProfiler()
        profile = profiler.build_profile(
            "PSEUDO-001",
            {
                "response_speed_percentile": 0.85,
                "first_attempt_accuracy": 0.80,
                "reattempt_rate": 0.1,
                "time_on_task_percentile": 0.4,
                "skip_rate": 0.05,
            },
        )
        assert profile.learner_pseudonym == "PSEUDO-001"
        assert profile.tone_pacing >= 0.0 and profile.tone_pacing <= 1.0
        assert profile.warmth_level >= 0.0 and profile.warmth_level <= 1.0

    def test_profile_decay_toward_neutral(self):
        from app.api.judiciary.models import LearnerEtherProfile
        from app.api.judiciary.profiler import EtherProfiler
        profiler = EtherProfiler()
        profile = LearnerEtherProfile(
            learner_pseudonym="PSEUDO-DECAY",
            tone_pacing=0.9,
            warmth_level=0.9,
            challenge_tolerance=0.9,
        )
        decayed = profiler.apply_decay(profile, days_inactive=10, decay_rate=0.05)
        assert decayed.tone_pacing < profile.tone_pacing
        assert decayed.warmth_level < profile.warmth_level

    def test_decay_zero_days_unchanged(self):
        from app.api.judiciary.models import LearnerEtherProfile
        from app.api.judiciary.profiler import EtherProfiler
        profiler = EtherProfiler()
        profile = LearnerEtherProfile(learner_pseudonym="PSEUDO-NODECAY", tone_pacing=0.8)
        result = profiler.apply_decay(profile, days_inactive=0)
        assert result.tone_pacing == profile.tone_pacing
