"""Configurable OpenAI-compatible LLM client."""

from __future__ import annotations

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


async def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict | None = "auto",
) -> Any:
    """Single chat completion call. Returns the raw OpenAI message object."""
    client = get_llm_client()
    model_name = get_model_name()
    kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

    print(f"  [LLM] Calling model: {model_name}...")
    try:
        response = await client.chat.completions.create(**kwargs)
        print(f"  [LLM] Response received from {model_name}.")
        return response.choices[0].message
    except Exception as exc:
        print(f"  [LLM Error] Error calling {model_name}: {exc}")
        raise
