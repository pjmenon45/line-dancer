"""Researcher agent – search and retrieve 3GPP evidence."""

from __future__ import annotations

import os
from typing import Any

from app.agents.base import run_tool_loop
from app.mcp_client import MCPClient, _default_releases, _default_series
from app.prompts import RESEARCHER_SYSTEM


class ResearcherAgent:
    def __init__(self, mcp: MCPClient):
        self.mcp = mcp

    async def run(
        self,
        question: str,
        *,
        series: list[str] | None = None,
        releases: list[str] | None = None,
    ) -> str:
        series_constraint = (
            f"- Prefer series_filter={series}\n"
            if series
            else "- Search across any relevant 3GPP series (TS 23, TS 24, TS 29, TS 32, TS 33, TS 36, TS 38)\n"
        )

        user_message = (
            f"User question:\n{question}\n\n"
            f"Context for this run:\n"
            f"{series_constraint}"
            f"- Releases: {releases}\n"
            f"- Gather structured evidence only; do not write the final user-facing report."
        )

        evidence = await run_tool_loop(
            system_prompt=RESEARCHER_SYSTEM,
            user_message=user_message,
            mcp=self.mcp,
        )
        return evidence
