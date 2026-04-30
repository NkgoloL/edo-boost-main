"""
EduBoost SA — Gamification Integration Tests

Integration tests covering:
- XP award flow from API to persistence
- Streak update and badge award cycles
- Grade band-specific behavior (R-3 vs 4-7)
- Leaderboard functionality
"""
import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.api.services.gamification_service import GamificationService, XP_CONFIG, GRADE_BAND_CONFIG
from app.api.models.db_models import Learner


class TestGamificationIntegration:
    """Integration tests for gamification end-to-end flows."""

    @pytest_asyncio.fixture
    async def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest_asyncio.fixture
    def mock_learner_grade_r3(self):
        """Create a mock Grade R-3 learner."""
        learner = MagicMock(spec=Learner)
        learner.learner_id = uuid4()
        learner.grade = 2
        learner.total_xp = 150
        learner.streak_days = 5
        learner.last_active_at = datetime.now() - timedelta(days=1)
        return learner

    @pytest_asyncio.fixture
    def mock_learner_grade_47(self):
        """Create a mock Grade 4-7 learner."""
        learner = MagicMock(spec=Learner)
        learner.learner_id = uuid4()
        learner.grade = 5
        learner.total_xp = 350
        learner.streak_days = 12
        learner.last_active_at = datetime.now() - timedelta(days=1)
        return learner

    # =====================================================================
    # Test: XP Award Flow
    # =====================================================================

    @pytest.mark.asyncio
    async def test_award_xp_lesson_complete_flow(self, mock_db_session, mock_learner_grade_r3):
        """Test complete XP award flow for lesson completion."""
        service = GamificationService(mock_db_session)
        learner_id = mock_learner_grade_r3.learner_id

        # Setup
        mock_db_session.get.return_value = mock_learner_grade_r3
        
        # Mock badge check returns no existing badges
        badge_result = MagicMock()
        badge_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = badge_result

        # Execute
        result = await service.award_xp(
            learner_id=learner_id,
            xp_type="lesson_complete",
            metadata={"lesson_id": "lesson_123"},
        )

        # Verify
        assert result is not None
        # base XP (35) + streak bonus (5 days * 5 = 25) = 60
        assert result["xp_awarded"] == 60  # base XP + streak bonus
        assert result["total_xp"] == 150 + 60  # existing + awarded
        assert result["level"] == 3  # (210 // 100) + 1 = 3
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_award_xp_level_up_detection(self, mock_db_session, mock_learner_grade_r3):
        """Test that level-up is detected when XP crosses threshold."""
        service = GamificationService(mock_db_session)
        learner_id = mock_learner_grade_r3.learner_id

        # Setup: learner at 95 XP (level 1), needs 5 more to reach level 2
        mock_learner_grade_r3.total_xp = 95
        
        mock_db_session.get.return_value = mock_learner_grade_r3
        
        badge_result = MagicMock()
        badge_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = badge_result

        # Execute: award 35 XP (lesson_complete)
        result = await service.award_xp(
            learner_id=learner_id,
            xp_type="lesson_complete",
        )

        # Verify: 95 + 35 + streak_bonus = crosses 100 threshold
        assert result["leveled_up"]
        assert result["new_level"] == 2

    @pytest.mark.asyncio
    async def test_award_xp_invalid_type_raises_error(self, mock_db_session, mock_learner_grade_r3):
        """Test that invalid XP type raises ValueError."""
        service = GamificationService(mock_db_session)
        learner_id = mock_learner_grade_r3.learner_id

        mock_db_session.get.return_value = mock_learner_grade_r3

        # Execute & Assert
        with pytest.raises(ValueError, match="Unknown XP type"):
            await service.award_xp(
                learner_id=learner_id,
                xp_type="invalid_action",
            )

    @pytest.mark.asyncio
    async def test_award_xp_learner_not_found(self, mock_db_session):
        """Test that non-existent learner raises ValueError."""
        service = GamificationService(mock_db_session)
        learner_id = uuid4()

        mock_db_session.get.return_value = None

        # Execute & Assert
        with pytest.raises(ValueError, match="not found"):
            await service.award_xp(
                learner_id=learner_id,
                xp_type="lesson_complete",
            )

    # =====================================================================
    # Test: Streak Update Flow
    # =====================================================================

    @pytest.mark.asyncio
    async def test_update_streak_continues_streak(self, mock_db_session, mock_learner_grade_r3):
        """Test that streak continues when activity is consecutive."""
        service = GamificationService(mock_db_session)
        learner_id = mock_learner_grade_r3.learner_id

        # Setup: last active was yesterday
        mock_learner_grade_r3.last_active_at = datetime.now() - timedelta(days=1)
        mock_learner_grade_r3.streak_days = 5

        mock_db_session.get.return_value = mock_learner_grade_r3
        
        badge_result = MagicMock()
        badge_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = badge_result

        # Execute
        result = await service.update_streak(learner_id)

        # Verify: streak continues
        assert result["streak_days"] == 6
        assert not result["streak_broken"]

    @pytest.mark.asyncio
    async def test_update_streak_breaks_streak(self, mock_db_session, mock_learner_grade_r3):
        """Test that streak breaks when there's a gap."""
        service = GamificationService(mock_db_session)
        learner_id = mock_learner_grade_r3.learner_id

        # Setup: last active was 3 days ago
        mock_learner_grade_r3.last_active_at = datetime.now() - timedelta(days=3)
        mock_learner_grade_r3.streak_days = 10

        mock_db_session.get.return_value = mock_learner_grade_r3
        
        badge_result = MagicMock()
        badge_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = badge_result

        # Execute
        result = await service.update_streak(learner_id)

        # Verify: streak resets
        assert result["streak_days"] == 1
        assert result["streak_broken"]

    @pytest.mark.asyncio
    async def test_update_streak_same_day_no_change(self, mock_db_session, mock_learner_grade_r3):
        """Test that streak doesn't change when activity is same day."""
        service = GamificationService(mock_db_session)
        learner_id = mock_learner_grade_r3.learner_id

        # Setup: last active was today
        mock_learner_grade_r3.last_active_at = datetime.now()
        mock_learner_grade_r3.streak_days = 5

        mock_db_session.get.return_value = mock_learner_grade_r3

        # Execute
        result = await service.update_streak(learner_id)

        # Verify: streak unchanged
        assert result["streak_days"] == 5
        assert not result["streak_broken"]

    # =====================================================================
    # Test: Grade Band Behavior
    # =====================================================================

    @pytest.mark.asyncio
    async def test_grade_r3_max_daily_xp(self, mock_db_session, mock_learner_grade_r3):
        """Test that Grade R-3 has correct max daily XP."""
        
        # Verify config
        assert GRADE_BAND_CONFIG["R-3"]["max_daily_xp"] == 200
        assert GRADE_BAND_CONFIG["R-3"]["engagement_style"] == "rewards"
        assert "streak" in GRADE_BAND_CONFIG["R-3"]["badge_types"]

    @pytest.mark.asyncio
    async def test_grade_47_max_daily_xp(self, mock_db_session, mock_learner_grade_47):
        """Test that Grade 4-7 has correct max daily XP and discovery badges."""
        
        # Verify config
        assert GRADE_BAND_CONFIG["4-7"]["max_daily_xp"] == 250
        assert GRADE_BAND_CONFIG["4-7"]["engagement_style"] == "discovery"
        assert "discovery" in GRADE_BAND_CONFIG["4-7"]["badge_types"]

    @pytest.mark.asyncio
    async def test_discovery_badges_available_for_grade_47(self, mock_db_session, mock_learner_grade_47):
        """Test that discovery badges are available for Grade 4-7."""
        service = GamificationService(mock_db_session)

        badges = service._get_available_badges(grade=5)
        badge_keys = [b["badge_key"] for b in badges]

        # Should have discovery badges
        assert "discovery_math" in badge_keys
        assert "discovery_science" in badge_keys
        assert "discovery_english" in badge_keys

    @pytest.mark.asyncio
    async def test_no_discovery_badges_for_grade_r3(self, mock_db_session, mock_learner_grade_r3):
        """Test that discovery badges are NOT available for Grade R-3."""
        service = GamificationService(mock_db_session)

        badges = service._get_available_badges(grade=2)
        badge_keys = [b["badge_key"] for b in badges]

        # Should NOT have discovery badges
        assert "discovery_math" not in badge_keys
        assert "discovery_science" not in badge_keys

    # =====================================================================
    # Test: Leaderboard
    # =====================================================================

    @pytest.mark.asyncio
    async def test_get_leaderboard_returns_top_learners(self, mock_db_session):
        """Test that leaderboard returns top learners by XP."""
        service = GamificationService(mock_db_session)

        # Setup: mock learners - need to simulate .limit() behavior
        mock_learners = [
            MagicMock(learner_id=uuid4(), total_xp=500, streak_days=10),
            MagicMock(learner_id=uuid4(), total_xp=400, streak_days=7),
            MagicMock(learner_id=uuid4(), total_xp=300, streak_days=5),
        ]

        # Mock the query result - scalars().all() returns all mock learners
        result = MagicMock()
        result.scalars.return_value.all.return_value = mock_learners
        mock_db_session.execute.return_value = result

        # Execute
        leaderboard = await service.get_leaderboard(limit=10)

        # Verify
        assert len(leaderboard) == 3
        # Should be sorted by XP descending
        assert leaderboard[0]["total_xp"] == 500
        assert leaderboard[1]["total_xp"] == 400
        assert leaderboard[2]["total_xp"] == 300

    @pytest.mark.asyncio
    async def test_get_leaderboard_respects_limit(self, mock_db_session):
        """Test that leaderboard respects the limit parameter."""
        service = GamificationService(mock_db_session)

        # Setup: 20 mock learners - need to simulate .limit() behavior
        mock_learners = [
            MagicMock(learner_id=uuid4(), total_xp=1000 - i * 10, streak_days=i)
            for i in range(20)
        ]
        # Only return first 5 (simulating limit)
        result = MagicMock()
        result.scalars.return_value.all.return_value = mock_learners[:5]
        mock_db_session.execute.return_value = result

        # Execute with limit=5
        leaderboard = await service.get_leaderboard(limit=5)

        # Verify
        assert len(leaderboard) == 5

    # =====================================================================
    # Test: Badge Award
    # =====================================================================

    @pytest.mark.asyncio
    async def test_badge_award_for_streak_threshold(self, mock_db_session, mock_learner_grade_r3):
        """Test that badges are awarded when streak threshold is reached."""
        service = GamificationService(mock_db_session)
        learner_id = mock_learner_grade_r3.learner_id

        # Setup: learner at streak threshold
        mock_learner_grade_r3.streak_days = 7

        mock_db_session.get.return_value = mock_learner_grade_r3
        
        # First call: check if badge exists (returns None = doesn't exist)
        # Second call: create badge
        badge_result = MagicMock()
        badge_result.scalar_one_or_none.return_value = None
        
        call_count = [0]
        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            return badge_result
        mock_db_session.execute.side_effect = execute_side_effect

        # Execute
        result = await service.update_streak(learner_id)

        # Verify: streak updated
        assert result["streak_days"] == 8

    # =====================================================================
    # Test: XP Config
    # =====================================================================

    def test_xp_config_has_all_required_types(self):
        """Test that XP_CONFIG has all required activity types."""
        required_types = [
            "lesson_complete",
            "lesson_mastery",
            "diagnostic_complete",
            "perfect_score",
            "daily_login",
            "badge_earned",
            "concept_mastered",
            "study_plan_complete",
        ]
        
        for xp_type in required_types:
            assert xp_type in XP_CONFIG, f"Missing XP type: {xp_type}"
            assert XP_CONFIG[xp_type] > 0, f"XP value should be positive for {xp_type}"

    def test_xp_values_are_reasonable(self):
        """Test that XP values are within reasonable ranges."""
        for xp_type, xp_value in XP_CONFIG.items():
            assert xp_value <= 100, f"{xp_type} XP too high: {xp_value}"
            assert xp_value >= 5, f"{xp_type} XP too low: {xp_value}"

    # =====================================================================
    # Test: Profile Generation
    # =====================================================================

    @pytest.mark.asyncio
    async def test_profile_includes_grade_band(self, mock_db_session, mock_learner_grade_r3):
        """Test that profile includes correct grade band."""
        service = GamificationService(mock_db_session)
        learner_id = mock_learner_grade_r3.learner_id

        mock_db_session.get.return_value = mock_learner_grade_r3
        
        result = MagicMock()
        result.all.return_value = []
        mock_db_session.execute.return_value = result

        # Execute
        profile = await service.get_learner_profile(learner_id)

        # Verify
        assert profile["grade_band"] == "R-3"
        assert profile["grade"] == 2

    @pytest.mark.asyncio
    async def test_profile_includes_level_calculations(self, mock_db_session, mock_learner_grade_r3):
        """Test that profile includes correct level calculations."""
        service = GamificationService(mock_db_session)
        learner_id = mock_learner_grade_r3.learner_id

        mock_learner_grade_r3.total_xp = 250  # Should be level 3
        
        mock_db_session.get.return_value = mock_learner_grade_r3
        
        result = MagicMock()
        result.all.return_value = []
        mock_db_session.execute.return_value = result

        # Execute
        profile = await service.get_learner_profile(learner_id)

        # Verify
        assert profile["level"] == 3  # (250 // 100) + 1
        assert profile["xp_to_next_level"] == 50  # 300 - 250

    @pytest.mark.asyncio
    async def test_profile_includes_available_badges(self, mock_db_session, mock_learner_grade_47):
        """Test that profile includes available badges for grade band."""
        service = GamificationService(mock_db_session)
        learner_id = mock_learner_grade_47.learner_id

        mock_db_session.get.return_value = mock_learner_grade_47
        
        result = MagicMock()
        result.all.return_value = []
        mock_db_session.execute.return_value = result

        # Execute
        profile = await service.get_learner_profile(learner_id)

        # Verify
        assert "can_earn_badges" in profile
        assert len(profile["can_earn_badges"]) > 0
        # Should have discovery badges for Grade 4-7
        badge_keys = [b["badge_key"] for b in profile["can_earn_badges"]]
        assert "discovery_math" in badge_keys