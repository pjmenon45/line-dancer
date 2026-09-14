"""Multi-Provider Stacking LLM Client (Groq, Cerebras, Google Gemini, OpenRouter).

Aggregates free tiers across multiple independent AI clouds behind one unified interface:
- Auto-discovers configured providers from environment variables.
- Round-robin load balancing across cloud providers to distribute token consumption.
- Instant, zero-downtime failover across providers on 429 (rate/daily limit) or 404.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

# In-memory Cooldowns (key: f"{provider}:{model}" -> timestamp)
_cooldowns: dict[str, float] = {}
_rr_provider_idx: int = 0
_lock = asyncio.Lock()


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    models: list[str]


def _get_configured_providers() -> list[ProviderConfig]:
    """Inspect environment variables and return active configured providers."""
    providers: list[ProviderConfig] = []

    # 1. Groq (Llama 3.3 70B Versatile)
    groq_key = os.getenv("GROQ_API_KEY") or (
        os.getenv("LLM_API_KEY") if "groq" in os.getenv("LLM_BASE_URL", "").lower() else None
    )
    if groq_key:
        providers.append(
            ProviderConfig(
                name="Groq",
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_key,
                models=["llama-3.3-70b-versatile", "llama-3.3-70b-specdec"],
            )
        )

    # 2. Cerebras Cloud (Ultra-fast Llama 3.3 70B @ 2,000 tokens/sec)
    cerebras_key = os.getenv("CEREBRAS_API_KEY")
    if cerebras_key:
        providers.append(
            ProviderConfig(
                name="Cerebras",
                base_url="https://api.cerebras.ai/v1",
                api_key=cerebras_key,
                models=["llama3.3-70b", "llama3.1-8b"],
            )
        )

    # 3. Google Gemini (1M+ context window, high token headroom)
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or (
        os.getenv("LLM_API_KEY") if "googleapis" in os.getenv("LLM_BASE_URL", "").lower() else None
    )
    if gemini_key:
        providers.append(
            ProviderConfig(
                name="Google-Gemini",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=gemini_key,
                models=["gemini-2.5-flash", "gemini-2.5-pro"],
            )
        )

    # 4. OpenRouter (Free Tier endpoints)
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        providers.append(
            ProviderConfig(
                name="OpenRouter",
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
                models=[
                    "meta-llama/llama-3.3-70b-instruct:free",
                    "deepseek/deepseek-r1:free",
                    "qwen/qwen-2.5-72b-instruct:free",
                ],
            )
        )

    # 5. Generic / Fallback LLM_API_KEY (if user used legacy single env vars)
    legacy_key = os.getenv("LLM_API_KEY")
    legacy_base = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    legacy_model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    if legacy_key and not any(p.api_key == legacy_key for p in providers):
        providers.append(
            ProviderConfig(
                name="Custom-Gateway",
                base_url=legacy_base,
                api_key=legacy_key,
                models=[legacy_model],
            )
        )

    return providers


def get_llm_client(base_url: str, api_key: str) -> AsyncOpenAI:
    """Create an AsyncOpenAI client targeting a specific provider base_url."""
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def _set_cooldown(provider: str, model: str, duration_seconds: int = 60) -> None:
    """Mark a specific provider model as cooling down."""
    key = f"{provider}:{model}"
    _cooldowns[key] = time.time() + duration_seconds
    print(f"  [Cooldown] {key} placed on cooldown for {duration_seconds}s.")


def _is_cooling_down(provider: str, model: str) -> bool:
    """Check if a specific provider model is on cooldown."""
    key = f"{provider}:{model}"
    return _cooldowns.get(key, 0.0) > time.time()


def _trim_messages(messages: list[dict[str, Any]], max_chars: int = 3500) -> list[dict[str, Any]]:
    """Trim oversized messages to stay safely within provider token limits."""
    trimmed = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str) and len(content) > max_chars:
            content = content[:max_chars] + "\n...[compacted for provider token limit]..."
        trimmed.append({**msg, "content": content})
    return trimmed


async def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict | None = "auto",
) -> Any:
    """
    Multi-Provider Stacking Chat Completion:
      - Rotates requests across active providers (Groq, Cerebras, Gemini, OpenRouter).
      - Seamlessly fails over to next provider if 429 (rate/daily limit) or 404 occurs.
    """
    global _rr_provider_idx
    providers = _get_configured_providers()

    if not providers:
        raise RuntimeError(
            "No LLM API keys configured! Please set at least one of: "
            "GROQ_API_KEY, CEREBRAS_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, or LLM_API_KEY."
        )

    # Determine round-robin starting provider
    async with _lock:
        start_idx = _rr_provider_idx % len(providers)
        _rr_provider_idx = (_rr_provider_idx + 1) % len(providers)

    ordered_providers = providers[start_idx:] + providers[start_idx:]
    current_messages = _trim_messages(messages, max_chars=4000)
    last_exc: Exception | None = None

    for provider in ordered_providers:
        client = get_llm_client(provider.base_url, provider.api_key)

        for model_name in provider.models:
            if _is_cooling_down(provider.name, model_name):
                continue

            kwargs: dict[str, Any] = {
                "model": model_name,
                "messages": current_messages,
            }
            if tools:
                kwargs["tools"] = tools
                if tool_choice is not None:
                    kwargs["tool_choice"] = tool_choice

            print(f"  [LLM Stack] Querying {provider.name} -> model: {model_name}...")
            try:
                response = await client.chat.completions.create(**kwargs)
                print(f"  [LLM Stack] Response successfully received from {provider.name} ({model_name}).")
                return response.choices[0].message
            except Exception as exc:
                last_exc = exc
                err = str(exc).lower()
                print(f"  [LLM Warning] {provider.name} ({model_name}) failed: {exc}")

                # 1. Decommissioned / 404 / Model Not Found -> 1-hour cooldown
                if any(k in err for k in ("404", "decommissioned", "not_found", "does not exist", "no longer supported")):
                    _set_cooldown(provider.name, model_name, duration_seconds=3600)
                    await asyncio.sleep(0.2)
                    continue

                # 2. Daily Token Quota (TPD) -> 24-hour cooldown for this model, failover to next provider
                elif "tokens per day" in err or "tpd" in err:
                    print(f"  [Stack Failover] {provider.name} exhausted daily TPD. Failing over to next provider...")
                    _set_cooldown(provider.name, model_name, duration_seconds=86400)
                    current_messages = _trim_messages(current_messages, max_chars=2500)
                    await asyncio.sleep(0.3)
                    break  # Break out of this provider to try the next provider immediately!

                # 3. Rate Limit / TPM Spike (429 / 413) -> 60s cooldown, failover to next provider
                elif any(k in err for k in ("429", "413", "rate_limit", "quota", "too large", "tokens per minute")):
                    print(f"  [Stack Failover] Rate/TPM limit on {provider.name}. Failing over to next provider...")
                    _set_cooldown(provider.name, model_name, duration_seconds=60)
                    current_messages = _trim_messages(current_messages, max_chars=2500)
                    await asyncio.sleep(0.3)
                    break  # Break out of this provider to try the next provider immediately!

                # 4. Tool Schema format error -> Retry with sanitized messages
                elif "400" in err and tools:
                    _set_cooldown(provider.name, model_name, duration_seconds=30)
                    await asyncio.sleep(0.3)
                    continue
                else:
                    _set_cooldown(provider.name, model_name, duration_seconds=30)
                    await asyncio.sleep(0.2)
                    continue

    raise RuntimeError(
        f"All configured LLM providers ({[p.name for p in providers]}) failed. Last error: {last_exc}"
    )
