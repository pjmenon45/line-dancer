"""Sequential orchestrator: Researcher → Analyst-Synthesizer."""

from __future__ import annotations

from app.agents.analyst import AnalystAgent
from app.agents.researcher import ResearcherAgent
from app.mcp_client import MCPClient, mcp_session


async def run_research_gap_analysis(
    question: str,
    *,
    series: list[str] | None = None,
    releases: list[str] | None = None,
    mcp: MCPClient | None = None,
) -> dict[str, str]:
    """
    Run the 2-agent pipeline.

    If `mcp` is provided, reuse that session (useful for tests).
    Otherwise open a short-lived MCP session for this request.
    """

    async def _run(client: MCPClient) -> dict[str, str]:
        researcher = ResearcherAgent(client)
        analyst = AnalystAgent(client)

        evidence = await researcher.run(question, series=series, releases=releases)
        answer = await analyst.run(
            question, evidence, series=series, releases=releases
        )
        return {
            "evidence": evidence,
            "answer": answer,
        }

    if mcp is not None:
        return await _run(mcp)

    async with mcp_session() as client:
        return await _run(client)
