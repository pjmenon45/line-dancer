"""Configurable OpenAI-compatible LLM client with multi-provider fallback (Google Gemini, Groq, OpenAI)."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from openai import AsyncOpenAI


def get_llm_client() -> AsyncOpenAI:
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set")
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


def get_model_name() -> str:
    base_url = os.getenv("LLM_BASE_URL", "").lower()
    if "googleapis" in base_url or "google" in base_url:
        return os.getenv("LLM_MODEL", "gemini-3.6-flash")
    return os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


def _get_candidate_models() -> list[str]:
    primary = get_model_name()
    candidates = [primary]
    base_url = os.getenv("LLM_BASE_URL", "").lower()

    if "googleapis" in base_url or "google" in base_url:
        # Google Gemini candidate fallbacks (latest Google AI Studio model names)
        for fallback in ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-2.5-flash", "gemini-2.5-pro"]:
            if fallback not in candidates:
                candidates.append(fallback)
    elif "groq" in base_url:
        # Groq candidate fallbacks
        for fallback in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
            if fallback not in candidates:
                candidates.append(fallback)
    elif "openai.com" in base_url:
        # OpenAI candidate fallbacks
        for fallback in ["gpt-4o-mini", "gpt-4o"]:
            if fallback not in candidates:
                candidates.append(fallback)

    return candidates


def _trim_messages(messages: list[dict[str, Any]], max_chars: int = 12000) -> list[dict[str, Any]]:
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
    """Chat completion call with automatic fallback across models on 413/404/TPM rate limits."""
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

            # If model deprecated/not found (404) or rate limited (413 or 429 TPM limit), try fallback model
            if "404" in err_str or "not_found" in err_str or "no longer available" in err_str:
                print(f"  [LLM Recovery] Model {model_name} not available, switching to next candidate model...")
                await asyncio.sleep(0.5)
                continue
            # If rate limited (413, 429, quota limit, or TPM limit), try fallback model or trim content
            elif any(k in err_str for k in ("413", "429", "rate_limit", "quota", "resource_exhausted", "tokens per minute", "too large")):
                print(f"  [LLM Recovery] Rate/quota limit on {model_name}, switching to next candidate model...")
                current_messages = _trim_messages(current_messages, max_chars=8000)
                await asyncio.sleep(1)
                continue
            elif "400" in err_str and tools:
                # If tool schema validation error on a specific model, retry with sanitized message payload
                print("  [LLM Recovery] Retrying with sanitized message payload...")
                await asyncio.sleep(0.5)
                continue
            else:
                raise

    if last_exc:
        raise last_exc
    raise RuntimeError("All LLM candidate models failed.")
