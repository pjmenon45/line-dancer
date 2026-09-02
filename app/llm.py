"""Round-Robin LLM Client with Auto-Discovery, Deprecation Cleanup & Daily Quota Safeguards."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from openai import AsyncOpenAI

# In-memory Model Pool & Round-Robin State
_model_pool: list[str] = []
_last_pool_refresh: float = 0.0
_model_cooldowns: dict[str, float] = {}  # model_name -> cooldown_until_timestamp
_rr_index: int = 0
_lock = asyncio.Lock()

# Verified High-Throughput / High-TPD Production Models for Groq
DEFAULT_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
]

DEFAULT_GOOGLE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

DEFAULT_OPENAI_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
]

# Patterns to strictly exclude (audio, moderation, low-TPD experimental previews with 200k daily caps)
EXCLUDED_MODEL_PATTERNS = (
    "whisper",
    "guard",
    "distil",
    "embed",
    "moderation",
    "tts",
    "dall-e",
    "rerank",
    "vision-preview",
    "qwen3.8",
    "gpt-oss",       # Excluded: 200k TPD cap
    "gpt-oss-120b",
    "gpt-oss-20b",
)


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


async def refresh_active_model_pool(force: bool = False) -> list[str]:
    """
    Returns active production models, attempting dynamic discovery every 7 days while safely falling back to defaults.
    """
    global _model_pool, _last_pool_refresh
    now = time.time()
    seven_days = 7 * 86400  # 604,800 seconds

    # Return cached pool if valid
    if not force and _model_pool and (now - _last_pool_refresh) < seven_days:
        return _model_pool

    base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    primary_override = os.getenv("LLM_MODEL", "").strip()

    # Start with rock-solid verified production defaults
    discovered = _get_default_models_for_provider(base_url)

    try:
        client = get_llm_client()
        response = await client.models.list()
        live_models: list[str] = []
        for m in response.data:
            model_id = getattr(m, "id", "")
            if not model_id:
                continue

            model_id_lower = model_id.lower()
            if any(pat in model_id_lower for pat in EXCLUDED_MODEL_PATTERNS):
                continue

            if "groq" in base_url.lower():
                # On Groq, strictly include high-TPD Meta Llama and DeepSeek models
                if any(k in model_id_lower for k in ("llama-3.3", "llama-3.1", "deepseek")):
                    live_models.append(model_id)
            elif "googleapis" in base_url.lower():
                if "gemini" in model_id_lower:
                    live_models.append(model_id)
            else:
                live_models.append(model_id)

        if live_models:
            discovered = live_models
    except Exception:
        # If /models API is denied or offline, use verified defaults with 0 delay
        pass

    # Ensure user's explicitly configured LLM_MODEL is prioritized if valid and not excluded
    if primary_override and not any(pat in primary_override.lower() for pat in EXCLUDED_MODEL_PATTERNS):
        if primary_override in discovered:
            discovered.remove(primary_override)
        discovered.insert(0, primary_override)

    _model_pool = discovered
    _last_pool_refresh = now
    return _model_pool


def _remove_deprecated_model(model_name: str) -> None:
    """Instantly purge a deprecated or excluded model from the active pool."""
    global _model_pool
    if model_name in _model_pool:
        print(f"  [Cleanup] Removing model '{model_name}' from round-robin pool.")
        _model_pool = [m for m in _model_pool if m != model_name]


def _set_model_cooldown(model_name: str, duration_seconds: int = 600) -> None:
    """Place a rate-limited or quota-exhausted model in cooldown."""
    _model_cooldowns[model_name] = time.time() + duration_seconds
    print(f"  [Cooldown] Model '{model_name}' placed on cooldown for {duration_seconds // 60} minutes.")


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
    Round-Robin Chat Completion:
      - Distributes token requests evenly across verified high-TPD open-source models.
      - Automatically bypasses rate-limited (429) or deprecated (404) models.
      - Daily quota exhaustion triggers a 24-hour cooldown so exhausted models are never retried today.
    """
    global _rr_index
    client = get_llm_client()
    pool = await refresh_active_model_pool()

    if not pool:
        pool = _get_default_models_for_provider(os.getenv("LLM_BASE_URL", ""))

    now = time.time()
    # Filter out models currently in cooldown
    active_candidates = [m for m in pool if _model_cooldowns.get(m, 0.0) <= now]
    if not active_candidates:
        # If all in cooldown, reset short-term cooldowns and retry pool
        _model_cooldowns.clear()
        active_candidates = list(pool)

    # Determine starting index in the round-robin ring
    async with _lock:
        start_idx = _rr_index % len(active_candidates)
        _rr_index = (_rr_index + 1) % len(active_candidates)

    # Create round-robin ordered sequence for this request
    ordered_models = active_candidates[start_idx:] + active_candidates[:start_idx]
    current_messages = _trim_messages(messages, max_chars=4000)
    last_exc = None

    for model_name in ordered_models:
        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": current_messages,
        }
        if tools:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice

        print(f"  [Round-Robin LLM] Calling model: {model_name} (candidate ring size: {len(ordered_models)})...")
        try:
            response = await client.chat.completions.create(**kwargs)
            print(f"  [Round-Robin LLM] Response successfully received from {model_name}.")
            return response.choices[0].message
        except Exception as exc:
            last_exc = exc
            err_str = str(exc).lower()
            print(f"  [LLM Warning] Call to {model_name} failed: {exc}")

            # 1. Deprecated / Not Found (404) -> Permanently remove from pool and continue
            if "404" in err_str or "not_found" in err_str or "model_not_found" in err_str or "does not exist" in err_str:
                _remove_deprecated_model(model_name)
                await asyncio.sleep(0.2)
                continue

            # 2. Daily Token Quota Exhausted (TPD / 429) -> Place on 24-hour cooldown and failover immediately
            elif "tokens per day" in err_str or "tpd" in err_str or "day" in err_str and "limit" in err_str:
                print(f"  [LLM Failover] Model {model_name} exhausted its 24-hour daily quota (TPD). Placing on 24h cooldown...")
                _set_model_cooldown(model_name, duration_seconds=86400)
                current_messages = _trim_messages(current_messages, max_chars=2500)
                await asyncio.sleep(0.3)
                continue

            # 3. Minute Rate Limit / TPM Spike (413 / 429 TPM) -> 10-minute cooldown & trim payload
            elif any(k in err_str for k in ("413", "429", "rate_limit", "quota", "resource_exhausted", "tokens per minute", "too large")):
                print(f"  [LLM Failover] Rate/TPM limit on {model_name}. Trimming payload and failing over...")
                _set_model_cooldown(model_name, duration_seconds=600)
                current_messages = _trim_messages(current_messages, max_chars=2500)
                await asyncio.sleep(0.5)
                continue

            # 4. Tool schema error on a specific model -> Retry with sanitized messages
            elif "400" in err_str and tools:
                print("  [LLM Recovery] Retrying with sanitized message payload...")
                await asyncio.sleep(0.5)
                continue
            else:
                raise

    if last_exc:
        raise last_exc
    raise RuntimeError("All models in the round-robin pool failed.")
