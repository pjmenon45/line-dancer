"""Shared tool-calling loop used by Researcher and Analyst agents."""

from __future__ import annotations

import json
import os
from typing import Any

from app.llm import chat_completion
from app.mcp_client import MCPClient, openai_tool_schemas


async def run_tool_loop(
    *,
    system_prompt: str,
    user_message: str,
    mcp: MCPClient,
    max_rounds: int | None = None,
    extra_messages: list[dict[str, Any]] | None = None,
) -> str:
    """
    Generic LLM + tools loop.

    Returns the final assistant text content (after tool rounds complete).
    """
    if max_rounds is None:
        max_rounds = int(os.getenv("MAX_TOOL_ROUNDS", "3"))

    tools = openai_tool_schemas()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]
    if extra_messages:
        messages.extend(extra_messages)
    messages.append({"role": "user", "content": user_message})

    for round_idx in range(1, max_rounds + 1):
        print(f"  [Round {round_idx}/{max_rounds}] Querying LLM...")
        message = await chat_completion(messages, tools=tools, tool_choice="auto")

        # No tool calls → model is done
        if not getattr(message, "tool_calls", None):
            print(f"  [Round {round_idx}] LLM finished research without further tool calls.")
            return message.content or ""

        # Append the assistant message that requested tools
        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
        )

        # Execute each tool call
        for tc in message.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            print(f"  -> Calling MCP tool: {name} with args: {args}")
            try:
                result_text = await mcp.call_tool(name, args)
                print(f"  <- Tool {name} returned {len(result_text)} characters.")
            except Exception as exc:  # noqa: BLE001
                result_text = f"Tool error ({name}): {exc}"
                print(f"  <- Tool error: {exc}")

            # Optional tool response truncation (set MAX_TOOL_CHARS=0 in .env for full unlimited output)
            max_tool_chars = int(os.getenv("MAX_TOOL_CHARS", "0"))
            if max_tool_chars > 0 and len(result_text) > max_tool_chars:
                result_text = result_text[:max_tool_chars] + "\n...[truncated to fit token limit]..."

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text,
                }
            )

    # Max rounds reached — ask for a final answer without more tools
    print("  [Limit reached] Generating final synthesis...")
    messages.append(
        {
            "role": "user",
            "content": "You have reached the tool-call limit. Produce your structured evidence pack now based on the gathered evidence. Do not call any more tools.",
        }
    )
    final = await chat_completion(messages, tools=None, tool_choice=None)
    return final.content or ""
