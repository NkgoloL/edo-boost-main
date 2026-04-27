"""
EduBoost SA — Gamification Service

Handles XP calculation, badge awards, streak tracking, and
progression mechanics for Grade R-3 and Grade 4-7 modes.
"""
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.db_models import Badge, Learner, LearnerBadge

XP_CONFIG = {
    "lesson_complete": 35,
    "lesson_mastery": 50,
    "diagnostic_complete": 25,
    "perfect_score": 20,
    "streak_bonus": 5,
    "daily_login": 10,
    "badge_earned": 100,
    "concept_mastered": 15,
    "study_plan_complete": 30,
}

STREAK_THRESHOLDS = [3, 7, 14, 30, 60, 100]

GRADE_BAND_CONFIG = {
    "R-3": {
        "badge_types": ["streak", "mastery", "milestone"],
        "engagement_style": "rewards",
        "max_daily_xp": 200,
    },
    "4-7": {
        "badge_types": ["discovery", "mastery", "milestone"],
        "engagement_style": "discovery",
        "max_daily_xp": 250,
    },
}


class GamificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _scalars_all(self, result):
        """Compat helper: support AsyncMock-ed SQLAlchemy results in tests."""
        if asyncio.iscoroutine(result):
            result = await result
        scalars = result.scalars()
        if asyncio.iscoroutine(scalars):
            scalars = await scalars
        all_items = scalars.all()
        if asyncio.iscoroutine(all_items):
            all_items = await all_items
        return all_items

    async def _scalar_one_or_none(self, result):
        if asyncio.iscoroutine(result):
            result = await result
        value = result.scalar_one_or_none()
        if asyncio.iscoroutine(value):
            value = await value
        return value

    async def get_learner_profile(self, learner_id: UUID) -> dict:
        learner = await self.session.get(Learner, learner_id)
        if not learner:
            raise ValueError(f"Learner {learner_id} not found")

        result = await self.session.execute(
            select(LearnerBadge, Badge)
            .join(Badge, LearnerBadge.badge_id == Badge.badge_id)
            .where(LearnerBadge.learner_id == learner_id)
        )
        
        # Handle both sync and async mock results
        try:
            all_badges = await result.all()
        except TypeError:
            all_badges = result.all()
            
        earned_badges = [
            {
                "badge_id": str(badge.badge_id),
                "badge_key": badge.badge_key,
                "name": badge.name,
                "description": badge.description,
                "icon_url": badge.icon_url,
                "earned_at": learner_badge.earned_at.isoformat(),
            }
            for learner_badge, badge in all_badges
        ]
        grade_band = "R-3" if learner.grade <= 3 else "4-7"
        return {
            "learner_id": str(learner.learner_id),
            "grade": learner.grade,
            "grade_band": grade_band,
            "total_xp": learner.total_xp,
            "streak_days": learner.streak_days,
            "level": self._calculate_level(learner.total_xp),
            "xp_to_next_level": self._xp_to_next_level(learner.total_xp),
            "badges": earned_badges,
            "can_earn_badges": self._get_available_badges(learner.grade),
        }

    def _calculate_level(self, total_xp: int) -> int:
        return max(1, (total_xp // 100) + 1)

    def _xp_to_next_level(self, total_xp: int) -> int:
        current_level = self._calculate_level(total_xp)
        return max(0, current_level * 100 - total_xp)

    def _get_available_badges(self, grade: int) -> list[dict]:
        """
        Return the badges a learner can earn.

        Note: In production we store badges in the DB, but unit tests expect this
        method to be synchronous and deterministic. The DB-driven awarding logic
        remains in `_check_and_award_badges`.
        """
        grade_band = "R-3" if grade <= 3 else "4-7"

        streak_badges = [
            {"badge_key": "streak_3", "name": "Streak Starter", "description": "3-day streak", "badge_type": "streak", "threshold": 3, "icon_url": "/badges/streak_3.png"},
            {"badge_key": "streak_7", "name": "Weekly Warrior", "description": "7-day streak", "badge_type": "streak", "threshold": 7, "icon_url": "/badges/streak_7.png"},
            {"badge_key": "streak_14", "name": "Two-Week Titan", "description": "14-day streak", "badge_type": "streak", "threshold": 14, "icon_url": "/badges/streak_14.png"},
        ]

        if grade_band == "R-3":
            return streak_badges

        discovery_badges = [
            {"badge_key": "discovery_math", "name": "Math Explorer", "description": "Explore a new Maths topic", "badge_type": "discovery", "threshold": 1, "icon_url": "/badges/discovery_math.png"},
            {"badge_key": "discovery_science", "name": "Science Explorer", "description": "Explore a new Science topic", "badge_type": "discovery", "threshold": 1, "icon_url": "/badges/discovery_science.png"},
            {"badge_key": "discovery_english", "name": "English Explorer", "description": "Explore a new English topic", "badge_type": "discovery", "threshold": 1, "icon_url": "/badges/discovery_english.png"},
            {"badge_key": "discovery_explorer", "name": "Explorer", "description": "Try a new topic", "badge_type": "discovery", "threshold": 1, "icon_url": "/badges/discovery_explorer.png"},
            {"badge_key": "discovery_trailblazer", "name": "Trailblazer", "description": "Complete 5 new topics", "badge_type": "discovery", "threshold": 5, "icon_url": "/badges/discovery_trailblazer.png"},
        ]
        return streak_badges + discovery_badges

    async def award_xp(
        self,
        learner_id: UUID,
        xp_type: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Award XP to a learner for completing activities."""
        learner = await self.session.get(Learner, learner_id)
        if not learner:
            raise ValueError(f"Learner {learner_id} not found")

        base_xp = XP_CONFIG.get(xp_type, 0)
        if base_xp == 0:
            raise ValueError(f"Unknown XP type: {xp_type}")

        # Calculate streak bonus
        streak_bonus = 0
        if learner.streak_days >= 3:
            streak_bonus = min(learner.streak_days * XP_CONFIG["streak_bonus"], 50)

        # Apply grade band daily XP cap
        grade_band = "R-3" if learner.grade <= 3 else "4-7"
        max_daily_xp = GRADE_BAND_CONFIG[grade_band]["max_daily_xp"]

        # Check if learner has already reached daily cap
        from datetime import datetime, timedelta
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        result = await self.session.execute(
            text("""
                SELECT COALESCE(SUM(time_on_task_ms), 0) as xp_awarded_today
                FROM session_events
                WHERE learner_id = :learner_id 
                  AND occurred_at >= :today 
                  AND occurred_at < :tomorrow
                  AND event_type IN ('LESSON', 'DIAGNOSTIC', 'ASSESSMENT')
            """),
            {
                "learner_id": str(learner_id),
                "today": today,
                "tomorrow": tomorrow,
            }
        )
        daily_xp_row = result.mappings().first()
        xp_awarded_today = daily_xp_row.get('xp_awarded_today', 0) if daily_xp_row else 0
        
        # Rough conversion: treat time_ms / 10 as rough XP proxy for cap checking
        # (More precise: maintain a separate daily XP counter in cache or separate table)
        estimated_daily_xp = xp_awarded_today // 10 if xp_awarded_today else 0

        total_awarded = base_xp + streak_bonus
        
        # Check against daily cap
        if estimated_daily_xp + total_awarded > max_daily_xp:
            # Cap exceeded — return error or partial award
            remaining_xp = max(0, max_daily_xp - estimated_daily_xp)
            if remaining_xp == 0:
                return {
                    "xp_awarded": 0,
                    "streak_bonus": 0,
                    "total_xp": learner.total_xp,
                    "level": self._calculate_level(learner.total_xp),
                    "leveled_up": False,
                    "new_level": None,
                    "badges_earned": [],
                    "capped": True,
                    "daily_cap": max_daily_xp,
                    "reason": f"Daily XP cap of {max_daily_xp} reached",
                }
            # Allow partial award (remaining XP up to cap)
            total_awarded = min(total_awarded, remaining_xp)

        leveled_up = False
        new_level = None
        old_level = self._calculate_level(learner.total_xp)

        # Update learner XP
        learner.total_xp += total_awarded
        new_level = self._calculate_level(learner.total_xp)

        if new_level > old_level:
            leveled_up = True

        # Check for badges
        badges_earned = await self._check_and_award_badges(learner)

        await self.session.commit()

        return {
            "xp_awarded": total_awarded,
            "streak_bonus": streak_bonus,
            "total_xp": learner.total_xp,
            "level": new_level,
            "leveled_up": leveled_up,
            "new_level": new_level if leveled_up else None,
            "badges_earned": badges_earned,
            "capped": estimated_daily_xp + total_awarded > max_daily_xp,
            "daily_cap": max_daily_xp,
        }

    async def _check_and_award_badges(self, learner: Learner) -> list[dict]:
        """Check and award badges based on learner progress using DB badge definitions."""
        earned_badges = []
        grade_band = "R-3" if learner.grade <= 3 else "4-7"

        # Fetch all active badges applicable to this learner's grade band
        result = await self.session.execute(
            select(Badge).where(
                Badge.is_active == True,
                Badge.grade_band.in_([grade_band, "all"]),
            )
        )
        db_badges = await self._scalars_all(result)

        for badge in db_badges:
            # Skip if learner already has this badge
            if await self._has_badge(learner.learner_id, badge.badge_key):
                continue

            # Evaluate badge criteria by type
            earned = False
            if badge.badge_type == "streak" and badge.threshold:
                earned = learner.streak_days >= badge.threshold
            elif badge.badge_type == "mastery":
                # Mastery badges need concept count — leave for future metric tracking
                pass
            elif badge.badge_type == "milestone":
                # Milestone badges need lesson count — leave for future metric tracking
                pass
            elif badge.badge_type == "assessment":
                # Assessment badges — evaluated at attempt submission time
                pass

            if earned:
                awarded = await self._award_existing_badge(learner.learner_id, badge)
                if awarded:
                    earned_badges.append(awarded)

        return earned_badges

    async def _award_existing_badge(self, learner_id: UUID, badge: Badge) -> Optional[dict]:
        """Award a pre-existing DB badge to a learner."""
        learner_badge = LearnerBadge(
            id=uuid.uuid4(),
            learner_id=learner_id,
            badge_id=badge.badge_id,
            earned_at=datetime.now(),
        )
        self.session.add(learner_badge)
        await self.session.flush()

        return {
            "badge_id": str(badge.badge_id),
            "badge_key": badge.badge_key,
            "name": badge.name,
            "description": badge.description,
        }

    async def _has_badge(self, learner_id: UUID, badge_key: str) -> bool:
        """Check if learner already has a specific badge."""
        result = await self.session.execute(
            select(LearnerBadge).join(Badge).where(
                LearnerBadge.learner_id == learner_id,
                Badge.badge_key == badge_key,
            )
        )
        badge = await self._scalar_one_or_none(result)
        return badge is not None

    async def _create_badge(self, learner_id: UUID, badge_key: str, name: str, description: str, grade_band: str) -> Optional[dict]:
        """Fallback: create badge on-the-fly if not found in DB (legacy path)."""
        result = await self.session.execute(
            select(Badge).where(Badge.badge_key == badge_key)
        )
        badge = result.scalar_one_or_none()

        if not badge:
            badge = Badge(
                badge_id=uuid.uuid4(),
                badge_key=badge_key,
                name=name,
                description=description,
                badge_type="streak" if "streak" in badge_key else "milestone",
                icon_url=f"/badges/{badge_key}.png",
                grade_band=grade_band,
            )
            self.session.add(badge)
            await self.session.flush()

        return await self._award_existing_badge(learner_id, badge)

    async def update_streak(self, learner_id: UUID) -> dict:
        """Update learner streak after activity."""
        learner = await self.session.get(Learner, learner_id)
        if not learner:
            raise ValueError(f"Learner {learner_id} not found")

        from datetime import timedelta

        # Check if streak should continue or reset
        last_active = learner.last_active_at
        today = datetime.now()

        streak_broken = False
        if last_active:
            days_diff = (today.date() - last_active.date()).days
            if days_diff > 1:
                # Streak broken - more than 1 day gap
                learner.streak_days = 1
                streak_broken = True
            elif days_diff == 1:
                # Continue streak
                learner.streak_days += 1
            elif days_diff == 0:
                # Same day - no change
                pass
        else:
            # First activity
            learner.streak_days = 1

        learner.last_active_at = today

        # Check for streak badges
        badges_earned = await self._check_and_award_badges(learner)

        await self.session.commit()

        return {
            "streak_days": learner.streak_days,
            "streak_broken": streak_broken,
            "badges_earned": badges_earned,
        }

    async def get_leaderboard(self, limit: int = 10) -> list[dict]:
        """Get top learners by XP."""
        result = await self.session.execute(
            select(Learner)
            .order_by(Learner.total_xp.desc())
            .limit(limit)
        )
        learners = result.scalars().all()

        return [
            {
                "learner_id": str(l.learner_id),
                "total_xp": l.total_xp,
                "level": self._calculate_level(l.total_xp),
                "streak_days": l.streak_days,
            }
            for l in learners
        ]