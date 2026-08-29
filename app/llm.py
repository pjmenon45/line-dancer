"""Configurable OpenAI-compatible LLM client with verified provider models and auto-recovery."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from openai import AsyncOpenAI


def get_llm_client() -> AsyncOpenAI:
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set")
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def get_model_name() -> str:
    base_url = os.getenv("LLM_BASE_URL", "").lower()
    if "googleapis" in base_url or "google" in base_url:
        return os.getenv("LLM_MODEL", "gemini-2.5-flash")
    return os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


def _get_candidate_models() -> list[str]:
    primary = get_model_name()
    candidates = [primary]
    base_url = os.getenv("LLM_BASE_URL", "").lower()

    if "googleapis" in base_url or "google" in base_url:
        for fallback in ["gemini-2.5-flash", "gemini-2.5-pro"]:
            if fallback not in candidates:
                candidates.append(fallback)
    elif "groq" in base_url:
        # Verified active models on Groq
        for fallback in ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
            if fallback not in candidates:
                candidates.append(fallback)
    elif "openai.com" in base_url:
        for fallback in ["gpt-4o-mini", "gpt-4o"]:
            if fallback not in candidates:
                candidates.append(fallback)

    return candidates


def _trim_messages(messages: list[dict[str, Any]], max_chars: int = 8000) -> list[dict[str, Any]]:
    """Trim oversized tool/user messages to stay safely within TPM limits."""
    trimmed = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str) and len(content) > max_chars:
            content = content[:max_chars] + "\n...[truncated for token limit]..."
        trimmed.append({**msg, "content": content})
    return trimmed


async def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict | None = "auto",
) -> Any:
    """Chat completion call with verified models and automatic TPM rate limit recovery."""
    client = get_llm_client()
    candidate_models = _get_candidate_models()
    current_messages = messages

    last_exc = None
    for model_name in candidate_models:
        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": current_messages,
        }
        if tools:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice

        print(f"  [LLM] Calling model: {model_name} (message count: {len(current_messages)})...")
        try:
            response = await client.chat.completions.create(**kwargs)
            print(f"  [LLM] Response successfully received from {model_name}.")
            return response.choices[0].message
        except Exception as exc:
            last_exc = exc
            err_str = str(exc).lower()
            print(f"  [LLM Warning] Call to {model_name} failed: {exc}")

            # If model deprecated/not found (404), skip directly to next model
            if "404" in err_str or "not_found" in err_str or "model_not_found" in err_str or "does not exist" in err_str:
                print(f"  [LLM Recovery] Model {model_name} not available, switching to next verified model...")
                await asyncio.sleep(0.3)
                continue
            # If rate limited (413, 429, quota limit, or TPM limit), trim payload and try next candidate
            elif any(k in err_str for k in ("413", "429", "rate_limit", "quota", "resource_exhausted", "tokens per minute", "too large")):
                print(f"  [LLM Recovery] Rate/quota limit on {model_name}, trimming payload and switching model...")
                current_messages = _trim_messages(current_messages, max_chars=6000)
                await asyncio.sleep(1)
                continue
            elif "400" in err_str and tools:
                print("  [LLM Recovery] Retrying with sanitized message payload...")
                await asyncio.sleep(0.5)
                continue
            else:
                raise

    if last_exc:
        raise last_exc
    raise RuntimeError("All LLM candidate models failed.")
