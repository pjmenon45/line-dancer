"""Analyst-Synthesizer agent – gap analysis and final cited report."""

from __future__ import annotations

from app.agents.base import run_tool_loop
from app.mcp_client import MCPClient, _default_releases, _default_series
from app.prompts import ANALYST_SYSTEM


class AnalystAgent:
    def __init__(self, mcp: MCPClient):
        self.mcp = mcp

    async def run(
        self,
        question: str,
        evidence: str,
        *,
        series: list[str] | None = None,
        releases: list[str] | None = None,
        max_rounds: int = 3,
    ) -> str:
        """
        Produce the final cited answer.

        max_rounds is kept low (default 3): evidence is already gathered;
        extra tool calls are only for filling clear gaps.
        """
        series_note = f"series {series} and " if series else "any relevant series and "
        user_message = (
            f"Original user question:\n{question}\n\n"
            f"Evidence from the Researcher:\n{evidence}\n\n"
            f"Instructions:\n"
            f"- Prefer {series_note}releases {releases} when making further tool calls.\n"
            f"- If the evidence is sufficient, do NOT call tools — write the final answer immediately.\n"
            f"- Only call tools if a critical fact is missing from the evidence.\n"
            f"- Produce the final answer in the mandatory format."
        )

        answer = await run_tool_loop(
            system_prompt=ANALYST_SYSTEM,
            user_message=user_message,
            mcp=self.mcp,
            max_rounds=max_rounds,
        )
        return answer
