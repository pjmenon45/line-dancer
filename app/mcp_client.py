"""
MCP client wrapper for the lightweight 3GPP MCP server.

Supports:
  - stdio: spawns `npx 3gpp-mcp-charging@latest serve` (default)
  - http:  connects to MCP_URL (for a separately deployed MCP service)

Exposes the four tools as async Python callables and as OpenAI-compatible
tool schemas for the LLM.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

# Official MCP Python SDK
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Tool names expected from the lightweight MCP
TOOL_NAMES = [
    "search_specifications",
    "get_specification_details",
    "compare_specifications",
    "find_implementation_requirements",
]


def _default_series() -> list[str] | None:
    raw = os.getenv("DEFAULT_SERIES", "")
    if not raw.strip():
        return None
    return [s.strip() for s in raw.split(",") if s.strip()]


def _default_releases() -> list[str]:
    raw = os.getenv("DEFAULT_RELEASES", "Rel-15,Rel-16,Rel-17,Rel-18,Rel-19")
    return [r.strip() for r in raw.split(",") if r.strip()]


def openai_tool_schemas() -> list[dict[str, Any]]:
    """
    OpenAI-compatible tool definitions for the four MCP tools.
    These match the lightweight MCP (edhijlu / 3gpp-mcp-charging) schemas.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "search_specifications",
                "description": (
                    "Search 3GPP specifications across all supported series: "
                    "TS 23 (System Architecture/Core/NWDAF), TS 24 (NAS/Protocols), "
                    "TS 29 (SBI/APIs), TS 32 (Charging/Management), TS 33 (Security/5G-AKA), "
                    "TS 36 (LTE/NB-IoT), and TS 38 (5G NR RAN). "
                    "Returns structured content and metadata."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query, e.g. '5G charging CHF', 'NWDAF analytics', 'RRC setup', or 'authentication 5G-AKA'",
                        },
                        "max_results": {
                            "type": "number",
                            "description": "Max results (default 5)",
                        },
                        "series_filter": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional series filter, e.g. ['23'], ['32'], ['33'], ['38']. Omit to search all series.",
                        },
                        "release_filter": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Releases, e.g. ['Rel-16','Rel-17','Rel-18']",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_specification_details",
                "description": (
                    "Get comprehensive details for one specification "
                    "(metadata, content, dependencies)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "specification_id": {
                            "type": "string",
                            "description": 'e.g. "TS 38.331" or "TS 38.300"',
                        },
                    },
                    "required": ["specification_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compare_specifications",
                "description": (
                    "Compare multiple 3GPP specifications "
                    "(architecture, procedures, evolution, implementation differences)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "specification_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": 'e.g. ["TS 38.300", "TS 38.331"]',
                        },
                    },
                    "required": ["specification_ids"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_implementation_requirements",
                "description": (
                    "Extract implementation requirements for a feature or scope "
                    "(mandatory/optional, dependencies, testing guidance)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "spec_scope": {
                            "type": "string",
                            "description": "Feature or area, e.g. 'RedCap' or 'network slicing in NR'",
                        },
                        "focus": {
                            "type": "string",
                            "description": "Optional focus, e.g. 'Rel-17' or 'UE requirements'",
                        },
                    },
                    "required": ["spec_scope"],
                },
            },
        },
    ]


class MCPClient:
    """
    Thin wrapper around an MCP ClientSession.
    Use via the `mcp_session()` async context manager below.
    """

    def __init__(self, session: ClientSession):
        self.session = session

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call an MCP tool and return text content (JSON-serialised if needed)."""
        cleaned_args = {}
        for k, v in (arguments or {}).items():
            if isinstance(v, str) and v.lower() in ("true", "false"):
                cleaned_args[k] = v.lower() == "true"
            else:
                cleaned_args[k] = v

        result = await self.session.call_tool(name, arguments=cleaned_args)

        # MCP 2.x may return CallToolResult or other result shapes
        content = getattr(result, "content", None)
        if content is None:
            return json.dumps(result.model_dump() if hasattr(result, "model_dump") else str(result))

        parts: list[str] = []
        for block in content:
            if hasattr(block, "text") and block.text is not None:
                parts.append(block.text)
            elif hasattr(block, "model_dump"):
                parts.append(json.dumps(block.model_dump(), default=str))
            else:
                parts.append(str(block))
        text = "\n".join(parts) if parts else ""
        return text or "(empty tool result)"

    async def list_tools(self) -> list[str]:
        listed = await self.session.list_tools()
        return [t.name for t in listed.tools]


@asynccontextmanager
async def mcp_session() -> AsyncIterator[MCPClient]:
    """
    Async context manager that yields an MCPClient connected to the
    lightweight 3GPP MCP server (stdio by default).
    """
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport == "http":
        # HTTP transport requires a different client path.
        # For Phase 1 we focus on stdio; HTTP can be added later.
        raise NotImplementedError(
            "MCP HTTP transport not yet implemented in this scaffold. "
            "Use MCP_TRANSPORT=stdio (default)."
        )

    command = os.getenv("MCP_COMMAND", "npx")
    # --yes avoids npx interactive prompts on first download
    args_raw = os.getenv("MCP_ARGS", "--yes,3gpp-mcp-charging@latest,serve")
    args = [a.strip() for a in args_raw.split(",") if a.strip()]

    env = os.environ.copy()
    hf = os.getenv("HUGGINGFACE_TOKEN")
    if hf:
        env["HUGGINGFACE_TOKEN"] = hf

    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=env,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield MCPClient(session)
