"""
INFRASTRUCTURE — ProviderRouter with circuit-breaker pattern.
Architectural recommendation #7: pybreaker-based routing with PROVIDER_FALLBACK audit events.
Groq (primary) → Anthropic (secondary) → HuggingFace local (last resort).
"""
from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Dict, List, Optional

import pybreaker
from prometheus_client import Counter, Gauge

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
provider_calls = Counter(
    "llm_provider_calls_total", "LLM provider call attempts", ["provider", "result"]
)
provider_fallbacks = Counter(
    "llm_provider_fallbacks_total", "LLM provider fallback events", ["from_provider", "to_provider"]
)
circuit_state = Gauge(
    "llm_circuit_breaker_state", "Circuit breaker state (0=closed, 1=open, 2=half-open)", ["provider"]
)


class ProviderName(str, Enum):
    GROQ = "groq"
    ANTHROPIC = "anthropic"
    LOCAL = "local_hf"


# ---------------------------------------------------------------------------
# Circuit breaker listener for metrics
# ---------------------------------------------------------------------------
class _MetricsListener(pybreaker.CircuitBreakerListener):
    def __init__(self, provider: str):
        self.provider = provider

    def state_change(self, cb, old_state, new_state):
        state_val = {"closed": 0, "open": 1, "half-open": 2}.get(new_state.name, -1)
        circuit_state.labels(provider=self.provider).set(state_val)
        logger.warning("Circuit breaker state change: provider=%s %s→%s", self.provider, old_state.name, new_state.name)


# ---------------------------------------------------------------------------
# Provider clients
# ---------------------------------------------------------------------------
def _messages(prompt: str, system_prompt: str = "") -> List[dict]:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    return messages


async def _call_groq(prompt: str, **kwargs) -> str:
    from groq import AsyncGroq

    client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
    completion = await client.chat.completions.create(
        model=os.environ.get("GROQ_MODEL", "llama3-70b-8192"),
        messages=_messages(prompt, kwargs.get("system_prompt", "")),
        max_tokens=2048,
    )
    return completion.choices[0].message.content


async def _call_anthropic(prompt: str, **kwargs) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = await client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        max_tokens=2048,
        system=kwargs.get("system_prompt") or None,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def _call_local(prompt: str, **kwargs) -> str:
    """
    HuggingFace local inference — last resort for ZA network resilience.
    Model should be loaded at startup and kept warm.
    """
    try:

        generator = _get_local_pipeline()
        result = generator(prompt, max_new_tokens=512, do_sample=False)
        return result[0]["generated_text"]
    except Exception as exc:
        logger.error("Local HuggingFace inference failed: %s", exc)
        raise


_local_pipeline = None


def _get_local_pipeline():
    global _local_pipeline
    if _local_pipeline is None:
        from transformers import pipeline  # type: ignore

        model_name = os.environ.get("LOCAL_HF_MODEL", "facebook/opt-1.3b")
        logger.info("Loading local HuggingFace model: %s", model_name)
        _local_pipeline = pipeline("text-generation", model=model_name)
        logger.info("Local model loaded.")
    return _local_pipeline


# ---------------------------------------------------------------------------
# ProviderRouter
# ---------------------------------------------------------------------------
class ProviderRouter:
    """
    Routes LLM calls through Groq → Anthropic → Local with circuit breakers.
    A provider switch emits a PROVIDER_FALLBACK event to the audit stream.
    """

    def __init__(self):
        fail_max = int(os.environ.get("CIRCUIT_FAIL_MAX", "5"))
        reset_timeout = int(os.environ.get("CIRCUIT_RESET_TIMEOUT", "60"))

        self._breakers: Dict[ProviderName, pybreaker.CircuitBreaker] = {
            ProviderName.GROQ: pybreaker.CircuitBreaker(
                fail_max=fail_max,
                reset_timeout=reset_timeout,
                listeners=[_MetricsListener(ProviderName.GROQ)],
                name="groq",
            ),
            ProviderName.ANTHROPIC: pybreaker.CircuitBreaker(
                fail_max=fail_max,
                reset_timeout=reset_timeout,
                listeners=[_MetricsListener(ProviderName.ANTHROPIC)],
                name="anthropic",
            ),
            ProviderName.LOCAL: pybreaker.CircuitBreaker(
                fail_max=3,
                reset_timeout=120,
                listeners=[_MetricsListener(ProviderName.LOCAL)],
                name="local_hf",
            ),
        }

        self._clients = {
            ProviderName.GROQ: _call_groq,
            ProviderName.ANTHROPIC: _call_anthropic,
            ProviderName.LOCAL: _call_local,
        }

        self._priority = [ProviderName.GROQ, ProviderName.ANTHROPIC, ProviderName.LOCAL]

    async def complete(
        self, prompt: str, system_prompt: str = "", action_id: str = "", stamp_id: str = ""
    ) -> str:
        last_exception: Optional[Exception] = None
        used_provider: Optional[ProviderName] = None

        for i, provider in enumerate(self._priority):
            breaker = self._breakers[provider]
            if breaker.current_state == pybreaker.STATE_OPEN:
                logger.warning("Circuit open for %s; skipping.", provider)
                continue

            try:
                result = await breaker.call_async(
                    self._clients[provider], prompt, system_prompt=system_prompt
                )
                provider_calls.labels(provider=provider, result="success").inc()

                if used_provider is not None:
                    # A fallback occurred — emit audit event
                    await self._emit_fallback_event(used_provider, provider, action_id, stamp_id)

                return result

            except pybreaker.CircuitBreakerError:
                logger.warning("Circuit breaker open for %s.", provider)
                provider_calls.labels(provider=provider, result="circuit_open").inc()
            except Exception as exc:
                logger.error("Provider %s failed: %s", provider, exc)
                provider_calls.labels(provider=provider, result="error").inc()
                last_exception = exc

            if used_provider is None:
                used_provider = provider
                provider_fallbacks.labels(
                    from_provider=provider,
                    to_provider=self._priority[i + 1] if i + 1 < len(self._priority) else "none",
                ).inc()

        raise RuntimeError(
            f"All LLM providers exhausted. Last error: {last_exception}"
        )

    async def _emit_fallback_event(
        self, from_provider: ProviderName, to_provider: ProviderName,
        action_id: str, stamp_id: str
    ) -> None:
        from app.api.judiciary.streams import publish_violation

        await publish_violation({
            "violation_type": "PROVIDER_FALLBACK",
            "from_provider": from_provider,
            "to_provider": to_provider,
            "action_id": action_id,
            "stamp_id": stamp_id,
            "description": (
                f"LLM provider fallback: {from_provider} → {to_provider}. "
                "Judiciary reviewed action assuming original provider."
            ),
        })

    def get_health(self) -> Dict[str, str]:
        return {
            p.value: str(self._breakers[p].current_state)
            for p in self._priority
        }
