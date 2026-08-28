"""Configurable OpenAI-compatible LLM client with automatic 413/TPM fallback."""

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
    return os.getenv("LLM_MODEL", "openai/gpt-oss-120b")


def _get_candidate_models() -> list[str]:
    primary = get_model_name()
    candidates = [primary]
    # High TPM / 128k context fallback models on Groq
    for fallback in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
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
    """Chat completion call with automatic fallback across models on 413/TPM rate limits."""
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

            # If rate limited (413 or 429 TPM limit), try fallback model or trim content
            if "413" in err_str or "rate_limit" in err_str or "tokens per minute" in err_str or "too large" in err_str:
                print(f"  [LLM Recovery] Switching from {model_name} to higher-TPM fallback model...")
                current_messages = _trim_messages(current_messages, max_chars=8000)
                await asyncio.sleep(1)
                continue
            elif "400" in err_str and tools:
                # If tool schema validation error on a specific model, try without optional tools
                print("  [LLM Recovery] Retrying with sanitized message payload...")
                await asyncio.sleep(0.5)
                continue
            else:
                raise

    if last_exc:
        raise last_exc
    raise RuntimeError("All LLM candidate models failed.")
