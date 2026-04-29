"""
PILLAR 5 — ETHER
LearnerEtherProfile model + EtherProfiler + EtherPromptModifier.
Architectural recommendation #3: profile store is materialized in Postgres,
updated by async Celery task — never in the hot request path.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Float, String, Text, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Sephira(str, Enum):
    KETER = "Keter"
    CHOKHMAH = "Chokhmah"
    BINAH = "Binah"
    CHESED = "Chesed"
    GEVURAH = "Gevurah"
    TIFERET = "Tiferet"
    NETZACH = "Netzach"
    HOD = "Hod"
    YESOD = "Yesod"
    MALKUTH = "Malkuth"


class MetaphorStyle(str, Enum):
    NARRATIVE = "narrative"
    ANALYTICAL = "analytical"
    VISUAL = "visual"
    KINESTHETIC = "kinesthetic"


class NarrativeFrame(str, Enum):
    HERO = "hero"
    EXPLORER = "explorer"
    BUILDER = "builder"
    HEALER = "healer"


# ---------------------------------------------------------------------------
# ORM
# ---------------------------------------------------------------------------
class LearnerEtherProfileORM(Base):
    __tablename__ = "ether_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    learner_pseudonym: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    dominant_sephira: Mapped[str] = mapped_column(String(32), nullable=False, default=Sephira.TIFERET.value)
    tone_pacing: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    metaphor_style: Mapped[str] = mapped_column(String(32), nullable=False, default=MetaphorStyle.NARRATIVE.value)
    warmth_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    challenge_tolerance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    preferred_narrative_frame: Mapped[str] = mapped_column(String(32), nullable=False, default=NarrativeFrame.EXPLORER.value)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=datetime.now
    )


# ---------------------------------------------------------------------------
# Pydantic schema
# ---------------------------------------------------------------------------
class LearnerEtherProfile(BaseModel):
    learner_pseudonym: str
    dominant_sephira: Sephira = Sephira.TIFERET
    tone_pacing: float = Field(0.5, ge=0.0, le=1.0)
    metaphor_style: MetaphorStyle = MetaphorStyle.NARRATIVE
    warmth_level: float = Field(0.7, ge=0.0, le=1.0)
    challenge_tolerance: float = Field(0.5, ge=0.0, le=1.0)
    preferred_narrative_frame: NarrativeFrame = NarrativeFrame.EXPLORER
    updated_at: Optional[datetime] = None

    @classmethod
    def from_orm(cls, row: LearnerEtherProfileORM) -> "LearnerEtherProfile":
        return cls(
            learner_pseudonym=row.learner_pseudonym,
            dominant_sephira=Sephira(row.dominant_sephira),
            tone_pacing=row.tone_pacing,
            metaphor_style=MetaphorStyle(row.metaphor_style),
            warmth_level=row.warmth_level,
            challenge_tolerance=row.challenge_tolerance,
            preferred_narrative_frame=NarrativeFrame(row.preferred_narrative_frame),
            updated_at=row.updated_at,
        )

    @classmethod
    def default_for_grade(cls, learner_pseudonym: str, grade: int) -> "LearnerEtherProfile":
        """Grade-band defaults — used when no profile exists yet (first session)."""
        if grade <= 3:
            return cls(
                learner_pseudonym=learner_pseudonym,
                dominant_sephira=Sephira.MALKUTH,
                tone_pacing=0.3,
                metaphor_style=MetaphorStyle.NARRATIVE,
                warmth_level=0.9,
                challenge_tolerance=0.3,
                preferred_narrative_frame=NarrativeFrame.HERO,
            )
        elif grade <= 7:
            return cls(
                learner_pseudonym=learner_pseudonym,
                dominant_sephira=Sephira.YESOD,
                tone_pacing=0.5,
                metaphor_style=MetaphorStyle.VISUAL,
                warmth_level=0.7,
                challenge_tolerance=0.5,
                preferred_narrative_frame=NarrativeFrame.EXPLORER,
            )
        return cls(learner_pseudonym=learner_pseudonym)


# ---------------------------------------------------------------------------
# Hot-path: EtherPromptModifier — pure function, sub-millisecond
# ---------------------------------------------------------------------------
class EtherPromptModifier:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def apply(self, base_prompt: str, learner_pseudonym: Optional[str]) -> str:
        """
        Fetch cached profile (single SELECT) and inject tone/pacing parameters.
        Falls back to grade-band defaults if no profile exists.
        Never blocks on profile computation.
        """
        if not learner_pseudonym:
            return base_prompt

        profile = await self._get_cached_profile(learner_pseudonym)
        if profile is None:
            logger.debug("No Ether profile for %s; using neutral defaults.", learner_pseudonym)
            return base_prompt

        return self._inject(base_prompt, profile)

    async def _get_cached_profile(self, pseudonym: str) -> Optional[LearnerEtherProfile]:
        row = (
            await self._session.execute(
                text("SELECT * FROM ether_profiles WHERE learner_pseudonym = :p"),
                {"p": pseudonym},
            )
        ).mappings().first()
        if not row:
            return None
        return LearnerEtherProfile(
            learner_pseudonym=row["learner_pseudonym"],
            dominant_sephira=Sephira(row["dominant_sephira"]),
            tone_pacing=row["tone_pacing"],
            metaphor_style=MetaphorStyle(row["metaphor_style"]),
            warmth_level=row["warmth_level"],
            challenge_tolerance=row["challenge_tolerance"],
            preferred_narrative_frame=NarrativeFrame(row["preferred_narrative_frame"]),
        )

    @staticmethod
    def _inject(prompt: str, profile: LearnerEtherProfile) -> str:
        """Append a tone/pacing instruction block to the prompt."""
        pacing_desc = "slow and deliberate" if profile.tone_pacing < 0.4 else (
            "moderate and steady" if profile.tone_pacing < 0.7 else "brisk and energetic"
        )
        warmth_desc = "very warm and encouraging" if profile.warmth_level > 0.7 else "professional and clear"
        challenge_desc = "gentle" if profile.challenge_tolerance < 0.4 else (
            "moderate" if profile.challenge_tolerance < 0.7 else "challenging"
        )

        ether_block = (
            f"\n\n[PEDAGOGICAL GUIDANCE — do not expose to learner]\n"
            f"Tone: {warmth_desc}. Pacing: {pacing_desc}. "
            f"Challenge level: {challenge_desc}. "
            f"Metaphor style: {profile.metaphor_style.value}. "
            f"Narrative frame: {profile.preferred_narrative_frame.value}. "
            f"Archetype: {profile.dominant_sephira.value}."
        )
        return prompt + ether_block


# ---------------------------------------------------------------------------
# Async Celery task — profile update (NOT in hot path)
# ---------------------------------------------------------------------------
async def update_ether_profile(
    learner_pseudonym: str, session_data: dict, session: AsyncSession
) -> None:
    """
    Called AFTER a session completes — runs as a Celery background task.
    Computes updated profile from IRT response patterns and engagement signals.
    """
    from .profiler import EtherProfiler

    profiler = EtherProfiler()
    updated = profiler.build_profile(learner_pseudonym, session_data)

    await session.execute(
        text(
            """
            INSERT INTO ether_profiles
                (learner_pseudonym, dominant_sephira, tone_pacing, metaphor_style,
                 warmth_level, challenge_tolerance, preferred_narrative_frame, updated_at)
            VALUES (:pseudonym, :sephira, :pacing, :metaphor, :warmth, :challenge, :frame, now())
            ON CONFLICT (learner_pseudonym) DO UPDATE SET
                dominant_sephira = EXCLUDED.dominant_sephira,
                tone_pacing = EXCLUDED.tone_pacing,
                metaphor_style = EXCLUDED.metaphor_style,
                warmth_level = EXCLUDED.warmth_level,
                challenge_tolerance = EXCLUDED.challenge_tolerance,
                preferred_narrative_frame = EXCLUDED.preferred_narrative_frame,
                updated_at = now()
            """
        ),
        {
            "pseudonym": updated.learner_pseudonym,
            "sephira": updated.dominant_sephira.value,
            "pacing": updated.tone_pacing,
            "metaphor": updated.metaphor_style.value,
            "warmth": updated.warmth_level,
            "challenge": updated.challenge_tolerance,
            "frame": updated.preferred_narrative_frame.value,
        },
    )
    await session.commit()
    logger.info("Ether profile updated for %s.", learner_pseudonym)
