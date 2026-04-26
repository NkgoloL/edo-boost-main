"""
EduBoost SA — Gamification Service

Handles XP calculation, badge awards, streak tracking, and
progression mechanics for Grade R-3 and Grade 4-7 modes.
"""
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

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
        grade_band = "R-3" if grade <= 3 else "4-7"
        config = GRADE_BAND_CONFIG[grade_band]
        badges = []
        for badge_type in config["badge_types"]:
            if badge_type == "streak":
                for threshold in STREAK_THRESHOLDS:
                    badges.append({
                        "badge_key": f"streak_{threshold}",
                        "name": f"{threshold}-Day Streak",
                        "description": f"Complete lessons for {threshold} consecutive days",
                        "badge_type": "streak",
                        "threshold": threshold,
                    })
            elif badge_type == "mastery":
                badges.extend([
                    {"badge_key": "mastery_5", "name": "Quick Learner", "description": "Master 5 concepts", "badge_type": "mastery", "threshold": 5},
                    {"badge_key": "mastery_10", "name": "Knowledge Seeker", "description": "Master 10 concepts", "badge_type": "mastery", "threshold": 10},
                    {"badge_key": "mastery_25", "name": "Subject Expert", "description": "Master 25 concepts", "badge_type": "mastery", "threshold": 25},
                ])
            elif badge_type == "milestone":
                badges.extend([
                    {"badge_key": "first_lesson", "name": "First Steps", "description": "Complete your first lesson", "badge_type": "milestone", "threshold": 1},
                    {"badge_key": "lessons_10", "name": "Dedicated Learner", "description": "Complete 10 lessons", "badge_type": "milestone", "threshold": 10},
                    {"badge_key": "lessons_50", "name": "Scholar", "description": "Complete 50 lessons", "badge_type": "milestone", "threshold": 50},
                ])
            elif badge_type == "discovery":
                badges.extend([
                    {"badge_key": "discovery_math", "name": "Math Explorer", "description": "Explore 5 different math topics", "badge_type": "discovery", "threshold": 5},
                    {"badge_key": "discovery_science", "name": "Science Explorer", "description": "Explore 5 different science topics", "badge_type": "discovery", "threshold": 5},
                    {"badge_key": "discovery_english", "name": "Language Explorer", "description": "Explore 5 different language topics", "badge_type": "discovery", "threshold": 5},
                    {"badge_key": "discovery_10", "name": "Curious Mind", "description": "Explore 10 different topics", "badge_type": "discovery", "threshold": 10},
                    {"badge_key": "discovery_25", "name": "Renaissance Learner", "description": "Explore 25 different topics", "badge_type": "discovery", "threshold": 25},
                ])
        return badges

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

        total_awarded = base_xp + streak_bonus
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
        }

    async def _check_and_award_badges(self, learner: Learner) -> list[dict]:
        """Check and award badges based on learner progress."""
        earned_badges = []
        grade_band = "R-3" if learner.grade <= 3 else "4-7"
        available_badges = self._get_available_badges(learner.grade)

        # Check streak badges
        for threshold in STREAK_THRESHOLDS:
            if learner.streak_days >= threshold:
                badge_key = f"streak_{threshold}"
                if not await self._has_badge(learner.learner_id, badge_key):
                    badge = await self._create_badge(learner.learner_id, badge_key, f"{threshold}-Day Streak", f"Complete lessons for {threshold} consecutive days", grade_band)
                    if badge:
                        earned_badges.append(badge)

        return earned_badges

    async def _has_badge(self, learner_id: UUID, badge_key: str) -> bool:
        """Check if learner already has a specific badge."""
        result = await self.session.execute(
            select(LearnerBadge).join(Badge).where(
                LearnerBadge.learner_id == learner_id,
                Badge.badge_key == badge_key,
            )
        )
        try:
            badge = await result.scalar_one_or_none()
        except TypeError:
            badge = result.scalar_one_or_none()
        return badge is not None

    async def _create_badge(self, learner_id: UUID, badge_key: str, name: str, description: str, grade_band: str) -> Optional[dict]:
        """Create and award a badge to a learner."""
        # Check if badge exists
        result = await self.session.execute(
            select(Badge).where(Badge.badge_key == badge_key)
        )
        badge = result.scalar_one_or_none()

        if not badge:
            # Create new badge
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

        # Check if learner already has this badge
        if await self._has_badge(learner_id, badge_key):
            return None

        # Award badge to learner
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