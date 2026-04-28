import os
from functools import lru_cache
import structlog

log = structlog.get_logger()

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

class PromptManager:
    """Manages loading and versioning of LLM prompts from the filesystem."""

    @staticmethod
    @lru_cache(maxsize=32)
    def get_template(template_type: str, role: str) -> str:
        """
        Loads a prompt template from the prompts directory.
        template_type: e.g. 'lesson_generation', 'study_plan', 'parent_report'
        role: 'system' or 'user'
        """
        filename = f"{template_type}.{role}.txt"
        filepath = os.path.join(PROMPTS_DIR, filename)
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                log.info("prompt_manager.loaded", template=template_type, role=role)
                return content
        except FileNotFoundError:
            log.error("prompt_manager.not_found", path=filepath)
            raise ValueError(f"Prompt template {filename} not found")
        except Exception as e:
            log.error("prompt_manager.error", error=str(e), path=filepath)
            raise e

    @staticmethod
    def clear_cache():
        """Clears the template cache (useful for hot-reloading in dev)."""
        PromptManager.get_template.cache_clear()
