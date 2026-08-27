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
    return os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


async def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict | None = "auto",
) -> Any:
    """Single chat completion call. Returns the raw OpenAI message object."""
    client = get_llm_client()
    kwargs: dict[str, Any] = {
        "model": get_model_name(),
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

    response = await client.chat.completions.create(**kwargs)
    return response.choices[0].message
