"""
PILLAR 5 — ETHER
EtherProfiler: derives LearnerEtherProfile from session signals.
Run asynchronously via Celery — never in the hot request path.
Implements profile decay for inactive learners.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from .models import (
    LearnerEtherProfile,
    MetaphorStyle,
    NarrativeFrame,
    Sephira,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sephira classification mapping
# See docs/ether_archetype_map.md for full narrative descriptions.
# ---------------------------------------------------------------------------
SEPHIRA_MAP: Dict[str, Dict[str, Any]] = {
    Sephira.KETER: {
        "signals": {"abstract_reasoning_score": (0.85, 1.0), "skip_rate": (0.0, 0.1)},
        "description": "Intuitive synthesiser; thrives on big-picture connections",
    },
    Sephira.CHOKHMAH: {
        "signals": {"response_speed_percentile": (0.8, 1.0), "first_attempt_accuracy": (0.75, 1.0)},
        "description": "Flash-insight learner; fast pattern recognition",
    },
    Sephira.BINAH: {
        "signals": {"reattempt_rate": (0.4, 1.0), "time_on_task_percentile": (0.6, 1.0)},
        "description": "Deep analyser; needs time to internalise",
    },
    Sephira.CHESED: {
        "signals": {"encouragement_responses": (0.7, 1.0), "warmth_level_signal": (0.7, 1.0)},
        "description": "Relational learner; motivation driven by warmth",
    },
    Sephira.GEVURAH: {
        "signals": {"challenge_seek_rate": (0.6, 1.0), "error_recovery_rate": (0.7, 1.0)},
        "description": "Disciplined achiever; responds to structure and rigour",
    },
    Sephira.TIFERET: {
        "signals": {"balance_score": (0.4, 0.7)},
        "description": "Balanced learner; adapts to varied content types",
    },
    Sephira.NETZACH: {
        "signals": {"creative_response_rate": (0.6, 1.0), "engagement_variance": (0.5, 1.0)},
        "description": "Creative responder; driven by emotion and aesthetics",
    },
    Sephira.HOD: {
        "signals": {"structured_task_accuracy": (0.75, 1.0), "note_taking_signals": (0.5, 1.0)},
        "description": "Methodical learner; prefers clear steps and systems",
    },
    Sephira.YESOD: {
        "signals": {"social_signal_responses": (0.5, 1.0), "story_engagement": (0.6, 1.0)},
        "description": "Narrative connector; learns through story and context",
    },
    Sephira.MALKUTH: {
        "signals": {"concrete_task_accuracy": (0.6, 1.0), "hands_on_preference": (0.7, 1.0)},
        "description": "Practical learner; needs concrete, tangible examples",
    },
}


class EtherProfiler:
    """
    Builds a LearnerEtherProfile from session_data signals.
    session_data expected keys (all optional, floats 0–1):
      - response_speed_percentile, first_attempt_accuracy, reattempt_rate,
        time_on_task_percentile, skip_rate, error_recovery_rate,
        challenge_seek_rate, creative_response_rate, engagement_variance,
        structured_task_accuracy, concrete_task_accuracy, story_engagement,
        abstract_reasoning_score, warmth_level_signal, balance_score,
        social_signal_responses, hands_on_preference, note_taking_signals,
        encouragement_responses
    """

    def build_profile(
        self, learner_pseudonym: str, session_data: Dict[str, Any]
    ) -> LearnerEtherProfile:
        dominant = self._classify_sephira(session_data)
        tone_pacing = self._derive_pacing(session_data)
        metaphor_style = self._derive_metaphor(session_data, dominant)
        warmth_level = float(session_data.get("warmth_level_signal", 0.7))
        challenge_tolerance = self._derive_challenge(session_data)
        narrative_frame = self._derive_narrative_frame(dominant)

        return LearnerEtherProfile(
            learner_pseudonym=learner_pseudonym,
            dominant_sephira=dominant,
            tone_pacing=round(min(1.0, max(0.0, tone_pacing)), 3),
            metaphor_style=metaphor_style,
            warmth_level=round(min(1.0, max(0.0, warmth_level)), 3),
            challenge_tolerance=round(min(1.0, max(0.0, challenge_tolerance)), 3),
            preferred_narrative_frame=narrative_frame,
        )

    def apply_decay(
        self, profile: LearnerEtherProfile, days_inactive: int, decay_rate: float = 0.05
    ) -> LearnerEtherProfile:
        """
        Decay profile toward neutral prior for inactive learners.
        Called by Celery beat task; configurable per grade band.
        """
        if days_inactive <= 0:
            return profile

        factor = max(0.0, 1.0 - (decay_rate * days_inactive))
        neutral = 0.5

        return LearnerEtherProfile(
            learner_pseudonym=profile.learner_pseudonym,
            dominant_sephira=Sephira.TIFERET,  # decay toward balanced archetype
            tone_pacing=round(neutral + (profile.tone_pacing - neutral) * factor, 3),
            metaphor_style=profile.metaphor_style,
            warmth_level=round(neutral + (profile.warmth_level - neutral) * factor, 3),
            challenge_tolerance=round(neutral + (profile.challenge_tolerance - neutral) * factor, 3),
            preferred_narrative_frame=profile.preferred_narrative_frame,
        )

    # ------------------------------------------------------------------
    # Classification internals
    # ------------------------------------------------------------------
    def _classify_sephira(self, data: Dict[str, Any]) -> Sephira:
        scores: Dict[Sephira, int] = {s: 0 for s in Sephira}
        for sephira, config in SEPHIRA_MAP.items():
            for signal_key, (low, high) in config["signals"].items():
                value = data.get(signal_key)
                if value is not None and low <= float(value) <= high:
                    scores[Sephira(sephira)] += 1

        best = max(scores, key=lambda s: scores[s])
        return best if scores[best] > 0 else Sephira.TIFERET

    def _derive_pacing(self, data: Dict[str, Any]) -> float:
        speed = float(data.get("response_speed_percentile", 0.5))
        time_on_task = float(data.get("time_on_task_percentile", 0.5))
        # Fast responders → higher pacing; deep thinkers → lower pacing
        return (speed * 0.6 + (1.0 - time_on_task) * 0.4)

    def _derive_metaphor(self, data: Dict[str, Any], sephira: Sephira) -> MetaphorStyle:
        metaphor_map = {
            Sephira.KETER: MetaphorStyle.ANALYTICAL,
            Sephira.CHOKHMAH: MetaphorStyle.VISUAL,
            Sephira.BINAH: MetaphorStyle.ANALYTICAL,
            Sephira.CHESED: MetaphorStyle.NARRATIVE,
            Sephira.GEVURAH: MetaphorStyle.ANALYTICAL,
            Sephira.TIFERET: MetaphorStyle.NARRATIVE,
            Sephira.NETZACH: MetaphorStyle.VISUAL,
            Sephira.HOD: MetaphorStyle.ANALYTICAL,
            Sephira.YESOD: MetaphorStyle.NARRATIVE,
            Sephira.MALKUTH: MetaphorStyle.KINESTHETIC,
        }
        return metaphor_map.get(sephira, MetaphorStyle.NARRATIVE)

    def _derive_challenge(self, data: Dict[str, Any]) -> float:
        challenge_seek = float(data.get("challenge_seek_rate", 0.5))
        error_recovery = float(data.get("error_recovery_rate", 0.5))
        skip_rate = float(data.get("skip_rate", 0.0))
        return (challenge_seek * 0.5 + error_recovery * 0.3 + (1.0 - skip_rate) * 0.2)

    def _derive_narrative_frame(self, sephira: Sephira) -> NarrativeFrame:
        frame_map = {
            Sephira.KETER: NarrativeFrame.EXPLORER,
            Sephira.CHOKHMAH: NarrativeFrame.EXPLORER,
            Sephira.BINAH: NarrativeFrame.BUILDER,
            Sephira.CHESED: NarrativeFrame.HEALER,
            Sephira.GEVURAH: NarrativeFrame.HERO,
            Sephira.TIFERET: NarrativeFrame.EXPLORER,
            Sephira.NETZACH: NarrativeFrame.HERO,
            Sephira.HOD: NarrativeFrame.BUILDER,
            Sephira.YESOD: NarrativeFrame.HEALER,
            Sephira.MALKUTH: NarrativeFrame.BUILDER,
        }
        return frame_map.get(sephira, NarrativeFrame.EXPLORER)
