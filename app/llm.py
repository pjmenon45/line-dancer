"""Clean, dynamic LLM client with active:true auto-discovery, 1-hr TTL cache, and failover."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from openai import AsyncOpenAI

# In-memory Model Cache (1-hour TTL)
_model_cache: dict[str, Any] = {"models": [], "fetched_at": 0.0}
_CACHE_TTL_SECONDS = 3600  # Re-check what's active once an hour

# In-memory cooldowns (model_name -> cooldown_until_timestamp)
_cooldowns: dict[str, float] = {}

# Patterns to exclude from chat completions (audio, moderation, embedding, low-quota previews)
_NON_CHAT_HINTS = (
    "whisper",
    "tts",
    "guard",
    "moderation",
    "embed",
    "vision-preview",
    "rerank",
    "distil",
    "gpt-oss",  # 200k daily TPD preview limit
)

# Verified fallback models if /models API call fails
DEFAULT_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.3-70b-specdec",
]

DEFAULT_GOOGLE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

DEFAULT_OPENAI_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
]


def get_llm_client() -> AsyncOpenAI:
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set")
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def _get_default_models_for_provider(base_url: str) -> list[str]:
    url = base_url.lower()
    if "googleapis" in url or "google" in url:
        return list(DEFAULT_GOOGLE_MODELS)
    if "openai.com" in url:
        return list(DEFAULT_OPENAI_MODELS)
    return list(DEFAULT_GROQ_MODELS)


async def get_active_models(client: AsyncOpenAI) -> list[str]:
    """Ask provider for active: true models instead of hardcoding, cached for 1 hour."""
    now = time.time()
    if _model_cache["models"] and (now - _model_cache["fetched_at"] < _CACHE_TTL_SECONDS):
        return _model_cache["models"]

    base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    primary_override = os.getenv("LLM_MODEL", "").strip()
    active_models: list[str] = []

    try:
        resp = await client.models.list()
        active_models = [
            m.id
            for m in resp.data
            if getattr(m, "active", True)
            and not any(h in m.id.lower() for h in _NON_CHAT_HINTS)
        ]
    except Exception:
        active_models = _get_default_models_for_provider(base_url)

    if not active_models:
        active_models = _get_default_models_for_provider(base_url)

    # Prioritize user's configured LLM_MODEL if specified
    if primary_override and primary_override in active_models:
        active_models.remove(primary_override)
        active_models.insert(0, primary_override)
    elif primary_override and not any(h in primary_override.lower() for h in _NON_CHAT_HINTS):
        active_models.insert(0, primary_override)

    _model_cache["models"] = active_models
    _model_cache["fetched_at"] = now
    return active_models


def _available(models: list[str]) -> list[str]:
    """Filter out models currently on cooldown."""
    now = time.time()
    return [m for m in models if _cooldowns.get(m, 0.0) <= now]


def _trim_messages(messages: list[dict[str, Any]], max_chars: int = 3500) -> list[dict[str, Any]]:
    """Trim oversized tool/user messages to stay safely within strict TPM limits."""
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
    Executes a chat completion across active provider models with dynamic failover:
      - Uses active: true models from Groq /models API.
      - Automatically skips decommissioned (404/400) and rate-limited (429/413) models.
    """
    client = get_llm_client()
    models = await get_active_models(client)
    candidates = _available(models)

    if not candidates:
        # If all candidates are on cooldown, reset cooldowns and retry all
        _cooldowns.clear()
        candidates = list(models)

    current_messages = _trim_messages(messages, max_chars=4000)
    last_exc: Exception | None = None

    for model_name in candidates:
        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": current_messages,
        }
        if tools:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice

        print(f"  [LLM] Calling active model: {model_name} (candidates: {len(candidates)})...")
        try:
            response = await client.chat.completions.create(**kwargs)
            print(f"  [LLM] Response successfully received from {model_name}.")
            return response.choices[0].message
        except Exception as exc:
            last_exc = exc
            err = str(exc).lower()
            print(f"  [LLM Warning] Call to {model_name} failed: {exc}")

            # 1. Decommissioned / Not Found -> Cooldown for 1 hour until next /models refresh
            if any(k in err for k in ("404", "decommissioned", "not_found", "does not exist", "no longer supported")):
                _cooldowns[model_name] = time.time() + _CACHE_TTL_SECONDS
                await asyncio.sleep(0.2)
                continue

            # 2. Daily Token Quota (TPD) -> 24-hour cooldown
            elif "tokens per day" in err or "tpd" in err:
                _cooldowns[model_name] = time.time() + 86400
                current_messages = _trim_messages(current_messages, max_chars=2500)
                await asyncio.sleep(0.3)
                continue

            # 3. Rate Limit / TPM Spike (429 / 413) -> 60s cooldown & trim payload
            elif any(k in err for k in ("429", "413", "rate_limit", "quota", "too large", "tokens per minute")):
                _cooldowns[model_name] = time.time() + 60
                current_messages = _trim_messages(current_messages, max_chars=2500)
                await asyncio.sleep(0.5)
                continue

            # 4. Tool schema format error -> Retry with sanitized messages
            elif "400" in err and tools:
                _cooldowns[model_name] = time.time() + 30
                await asyncio.sleep(0.5)
                continue
            else:
                _cooldowns[model_name] = time.time() + 30
                await asyncio.sleep(0.2)
                continue

    raise RuntimeError(f"All {len(candidates)} candidates failed. Last error: {last_exc}")
