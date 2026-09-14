"""Multi-Provider Stacking LLM Client with Live Provider /models Auto-Discovery.

Aggregates free tiers across multiple independent AI clouds:
- Dynamically queries each provider's GET /models endpoint to discover currently active models.
- Never relies on hardcoded or stale model names.
- Round-robin load balancing and instant failover across clouds on rate limits (429/TPD/TPM).
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

# In-memory Cooldowns (key: f"{provider}:{model}" -> timestamp)
_cooldowns: dict[str, float] = {}
# In-memory model cache per provider: {provider_name: {"models": [...], "fetched_at": float}}
_provider_model_cache: dict[str, dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 1800  # Refresh live active models every 30 minutes

_rr_provider_idx: int = 0
_lock = asyncio.Lock()

# Non-chat models to exclude from discovery
_NON_CHAT_HINTS = (
    "whisper",
    "tts",
    "guard",
    "moderation",
    "embed",
    "vision-preview",
    "rerank",
    "dall-e",
    "distil-whisper",
    "prompt-guard",
)


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    fallback_models: list[str] = field(default_factory=list)


def _get_configured_providers() -> list[ProviderConfig]:
    """Inspect environment variables and key prefixes to detect active providers."""
    providers: list[ProviderConfig] = []
    seen_keys: set[str] = set()

    # 1. Groq (gsk_...)
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        llm_key = os.getenv("LLM_API_KEY", "")
        if llm_key.startswith("gsk_") or "groq" in os.getenv("LLM_BASE_URL", "").lower():
            groq_key = llm_key

    if groq_key and groq_key not in seen_keys:
        seen_keys.add(groq_key)
        providers.append(
            ProviderConfig(
                name="Groq",
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_key,
                fallback_models=[
                    "llama-3.3-70b-versatile",
                    "deepseek-r1-distill-llama-70b",
                    "qwen-2.5-32b",
                    "gemma2-9b-it",
                ],
            )
        )

    # 2. Cerebras Cloud (csk-...)
    cerebras_key = os.getenv("CEREBRAS_API_KEY")
    if not cerebras_key:
        llm_key = os.getenv("LLM_API_KEY", "")
        if llm_key.startswith("csk-") or "cerebras" in os.getenv("LLM_BASE_URL", "").lower():
            cerebras_key = llm_key

    if cerebras_key and cerebras_key not in seen_keys:
        seen_keys.add(cerebras_key)
        providers.append(
            ProviderConfig(
                name="Cerebras",
                base_url="https://api.cerebras.ai/v1",
                api_key=cerebras_key,
                fallback_models=["llama3.3-70b", "llama3.1-70b", "llama3.1-8b", "llama-3.3-70b"],
            )
        )

    # 3. Google Gemini (AIzaSy...)
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not gemini_key:
        llm_key = os.getenv("LLM_API_KEY", "")
        if llm_key.startswith("AIzaSy") or "googleapis" in os.getenv("LLM_BASE_URL", "").lower():
            gemini_key = llm_key

    if gemini_key and gemini_key not in seen_keys:
        seen_keys.add(gemini_key)
        providers.append(
            ProviderConfig(
                name="Google-Gemini",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=gemini_key,
                fallback_models=[
                    "gemini-2.5-flash",
                    "gemini-3.6-flash",
                    "gemini-2.5-pro",
                    "gemini-1.5-flash-latest",
                    "gemini-1.5-pro-latest",
                ],
            )
        )

    # 4. OpenRouter (sk-or-...)
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        llm_key = os.getenv("LLM_API_KEY", "")
        if llm_key.startswith("sk-or-") or "openrouter" in os.getenv("LLM_BASE_URL", "").lower():
            openrouter_key = llm_key

    if openrouter_key and openrouter_key not in seen_keys:
        seen_keys.add(openrouter_key)
        providers.append(
            ProviderConfig(
                name="OpenRouter",
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
                fallback_models=[
                    "meta-llama/llama-3.3-70b-instruct:free",
                    "google/gemini-2.0-flash-exp:free",
                    "google/gemini-2.5-flash:free",
                ],
            )
        )

    # 5. Generic / Custom Gateway (if not already categorized)
    legacy_key = os.getenv("LLM_API_KEY")
    legacy_base = os.getenv("LLM_BASE_URL", "").strip()
    legacy_model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    if legacy_key and legacy_key not in seen_keys:
        providers.append(
            ProviderConfig(
                name="Custom-Gateway",
                base_url=legacy_base or "https://api.groq.com/openai/v1",
                api_key=legacy_key,
                fallback_models=[legacy_model],
            )
        )

    return providers


def get_llm_client(base_url: str, api_key: str) -> AsyncOpenAI:
    """Create an AsyncOpenAI client targeting a specific provider base_url."""
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


async def get_live_provider_models(provider: ProviderConfig) -> list[str]:
    """
    Asks the provider's /models API for currently active models in real time.
    Falls back gracefully to verified defaults if /models endpoint is restricted.
    """
    now = time.time()
    cached = _provider_model_cache.get(provider.name)
    if cached and (now - cached.get("fetched_at", 0.0) < _CACHE_TTL_SECONDS) and cached.get("models"):
        return cached["models"]

    client = get_llm_client(provider.base_url, provider.api_key)
    discovered: list[str] = []

    try:
        resp = await client.models.list()
        for m in resp.data:
            model_id = getattr(m, "id", "")
            if not model_id:
                continue

            model_id_lower = model_id.lower()
            # Exclude audio, moderation, embedding models
            if any(h in model_id_lower for h in _NON_CHAT_HINTS):
                continue

            # On OpenRouter, strictly filter for currently active :free endpoints
            if "openrouter" in provider.base_url.lower():
                if not model_id.endswith(":free"):
                    continue

            # Filter active: true if supported
            if getattr(m, "active", True):
                discovered.append(model_id)

    except Exception as exc:
        print(f"  [Model Discovery Notice] {provider.name} /models check: {exc}. Using fallback models.")

    if not discovered:
        discovered = list(provider.fallback_models)

    _provider_model_cache[provider.name] = {"models": discovered, "fetched_at": now}
    return discovered


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
      - Live auto-discovery of currently active models from each provider.
      - Rotates requests across active providers (Groq, Cerebras, Gemini, OpenRouter).
      - Seamlessly fails over to next provider if 429 (rate/daily limit), 404, or 400 occurs.
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

    ordered_providers = providers[start_idx:] + providers[:start_idx]
    current_messages = _trim_messages(messages, max_chars=4000)
    provider_errors: list[str] = []

    for provider in ordered_providers:
        client = get_llm_client(provider.base_url, provider.api_key)
        models = await get_live_provider_models(provider)

        for model_name in models:
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
                err = str(exc).lower()
                err_summary = f"{provider.name} ({model_name}): {exc}"
                provider_errors.append(err_summary)
                print(f"  [LLM Warning] {err_summary}")

                # 1. Unavailable / Decommissioned / 404 / Paid model slug -> 1-hour cooldown & continue to next model
                if any(k in err for k in ("404", "decommissioned", "not_found", "does not exist", "unavailable for free", "no longer supported")):
                    _set_cooldown(provider.name, model_name, duration_seconds=3600)
                    await asyncio.sleep(0.2)
                    continue

                # 2. Daily Token Quota (TPD) -> 24-hour cooldown for this model, failover to next provider
                elif "tokens per day" in err or "tpd" in err:
                    print(f"  [Stack Failover] {provider.name} exhausted daily TPD. Failing over to next provider...")
                    _set_cooldown(provider.name, model_name, duration_seconds=86400)
                    current_messages = _trim_messages(current_messages, max_chars=2500)
                    await asyncio.sleep(0.3)
                    break  # Try next provider immediately!

                # 3. Rate Limit / TPM Spike (429 / 413) -> 60s cooldown, failover to next provider
                elif any(k in err for k in ("429", "413", "rate_limit", "quota", "too large", "tokens per minute")):
                    print(f"  [Stack Failover] Rate/TPM limit on {provider.name}. Failing over to next provider...")
                    _set_cooldown(provider.name, model_name, duration_seconds=60)
                    current_messages = _trim_messages(current_messages, max_chars=2500)
                    await asyncio.sleep(0.3)
                    break  # Try next provider immediately!

                # 4. Tool Schema format error -> Retry next model/provider
                elif "400" in err and tools:
                    _set_cooldown(provider.name, model_name, duration_seconds=60)
                    await asyncio.sleep(0.3)
                    continue
                else:
                    _set_cooldown(provider.name, model_name, duration_seconds=30)
                    await asyncio.sleep(0.2)
                    continue

    raise RuntimeError(
        f"All configured LLM providers failed:\n" + "\n".join(f"• {e}" for e in provider_errors)
    )
