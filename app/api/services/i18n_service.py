"""
app/api/services/i18n_service.py
─────────────────────────────────
Multilingual lesson generation service for EduBoost SA.

Supported languages (Phase 1):
  en  — English
  zu  — isiZulu
  af  — Afrikaans
  xh  — isiXhosa

All four are official South African languages with significant learner populations.
Language selection is stored on the Learner model (home_language field).

Architecture:
  The inference gateway (call_llm) handles the LLM call.
  This service handles:
    1. Selecting the correct system/user prompt template for the language
    2. Enriching prompts with language-specific cultural context
    3. Post-processing: ensuring language fidelity in the response
    4. Emitting LESSON_LANGUAGE_TOTAL metrics
"""

from __future__ import annotations

from typing import Any

import structlog

from app.api.core.metrics import LESSON_LANGUAGE_TOTAL
from app.api.services.inference_gateway import call_llm, parse_json_response

log = structlog.get_logger()

# ── Supported languages ────────────────────────────────────────────────────────
SUPPORTED_LANGUAGES: dict[str, dict] = {
    "en": {
        "name": "English",
        "greeting": "Hello",
        "cultural_context": (
            "Use South African English. Include references to local culture: "
            "ubuntu philosophy, braai culture, South African fauna (elephant, rhino, "
            "protea), rands and cents for maths, local place names."
        ),
    },
    "zu": {
        "name": "isiZulu",
        "greeting": "Sawubona",
        "cultural_context": (
            "Generate content ENTIRELY in isiZulu. Use simple, grade-appropriate "
            "isiZulu vocabulary. Include ubuntu values (umuntu ngumuntu ngabantu). "
            "Reference familiar Zulu cultural elements: isigodi, ikhaya, izinkomo. "
            "For maths, use rand/cent. Ensure explanations suit the SA CAPS curriculum."
        ),
    },
    "af": {
        "name": "Afrikaans",
        "greeting": "Hallo",
        "cultural_context": (
            "Generate content ENTIRELY in Afrikaans. Use simple, grade-appropriate "
            "Afrikaans. Reference South African culture: braai, veld, fynbos, "
            "Karoo, rand en sent vir wiskunde. Align with CAPS kurrikulum vereistes."
        ),
    },
    "xh": {
        "name": "isiXhosa",
        "greeting": "Molo",
        "cultural_context": (
            "Generate content ENTIRELY in isiXhosa. Use grade-appropriate isiXhosa. "
            "Ubuntu values: umntu ngumntu ngabantu. Reference familiar elements: "
            "ilali, imizi, iinkomo. For maths, use rand/cent. CAPS-aligned content."
        ),
    },
}

DEFAULT_LANGUAGE = "en"


def get_language_config(language_code: str) -> dict:
    """Return language config, falling back to English if unsupported."""
    code = language_code.lower()[:2]
    if code not in SUPPORTED_LANGUAGES:
        log.warning("i18n.unsupported_language", requested=language_code, fallback=DEFAULT_LANGUAGE)
        code = DEFAULT_LANGUAGE
    return {"code": code, **SUPPORTED_LANGUAGES[code]}


def build_multilingual_system_prompt(
    base_system_prompt: str,
    language_code: str,
    grade: int,
    subject: str,
) -> str:
    """
    Augment a base system prompt with language and cultural instructions.

    The base system prompt defines the pedagogical role;
    this function layers on the target language and SA cultural context.
    """
    lang = get_language_config(language_code)

    language_instruction = (
        f"\n\n## Language & Cultural Context\n"
        f"Target language: {lang['name']} ({lang['code']})\n"
        f"{lang['cultural_context']}\n\n"
        f"IMPORTANT: The ENTIRE lesson content — titles, explanations, examples, "
        f"questions and answers — must be written in {lang['name']}. "
        f"Do NOT mix languages unless showing a word borrowed from another language "
        f"as a teaching example."
    )

    return base_system_prompt + language_instruction


async def generate_multilingual_lesson(
    grade: int,
    subject: str,
    topic: str,
    knowledge_gaps: list[str],
    language_code: str = "en",
    system_prompt_base: str | None = None,
) -> dict[str, Any]:
    """
    Generate a fully localised lesson in the learner's home language.

    This wraps call_llm with language-aware prompt enrichment and
    tracks per-language metrics for observability.

    Returns the parsed lesson JSON dict.
    """
    lang = get_language_config(language_code)

    if system_prompt_base is None:
        system_prompt_base = _default_system_prompt()

    system_prompt = build_multilingual_system_prompt(
        system_prompt_base, language_code, grade, subject
    )

    gap_list = "\n".join(f"- {g}" for g in knowledge_gaps) if knowledge_gaps else "None identified"
    grade_label = "R" if grade == 0 else str(grade)

    user_prompt = (
        f"Create a CAPS-aligned lesson for Grade {grade_label} learners.\n"
        f"Subject: {subject}\n"
        f"Topic: {topic}\n"
        f"Language: {lang['name']}\n"
        f"Knowledge gaps to address:\n{gap_list}\n\n"
        f"Return a JSON object with keys: title, introduction, content_sections "
        f"(list of {{heading, body, example}}), summary, quiz_questions "
        f"(list of {{question, options, correct_index, explanation}}).\n"
        f"All text must be in {lang['name']}."
    )

    log.info(
        "i18n.generating_lesson",
        language=language_code,
        grade=grade,
        subject=subject,
        topic=topic,
    )

    raw = await call_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=1500,
    )

    lesson_data = parse_json_response(raw)

    # Emit language metric
    LESSON_LANGUAGE_TOTAL.labels(language_code=lang["code"]).inc()

    log.info("i18n.lesson_generated", language=language_code, grade=grade)
    return lesson_data


def _default_system_prompt() -> str:
    return (
        "You are EduBoost — an expert South African educator and curriculum specialist "
        "trained in CAPS (Curriculum and Assessment Policy Statement). "
        "You create engaging, age-appropriate lesson content for Grade R–7 learners. "
        "Your lessons use culturally relevant South African examples and an ubuntu-inspired "
        "philosophy that celebrates collaboration and community. "
        "Always return valid JSON matching the requested schema."
    )


def list_supported_languages() -> list[dict]:
    """Return a list of supported languages for the API language selector endpoint."""
    return [
        {"code": code, "name": cfg["name"], "greeting": cfg["greeting"]}
        for code, cfg in SUPPORTED_LANGUAGES.items()
    ]
