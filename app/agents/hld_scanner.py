"""Stage 1: HLD Impact Scanner Agent – maps impacted 3GPP specifications across domains."""

from __future__ import annotations

from app.agents.base import run_tool_loop
from app.mcp_client import MCPClient, _default_releases
from app.prompts import HLD_IMPACT_SCANNER_PROMPT


class HLDImpactScannerAgent:
    def __init__(self, mcp: MCPClient):
        self.mcp = mcp

    async def run(
        self,
        feature_name: str,
        *,
        feature_description: str = "",
        target_releases: list[str] | None = None,
        max_rounds: int = 2,
    ) -> str:
        releases = target_releases or _default_releases()
        desc_clause = f"\nAdditional Context / Requirements:\n{feature_description}" if feature_description else ""

        user_message = (
            f"Target Feature for High-Level Design (HLD):\n{feature_name}{desc_clause}\n\n"
            f"Target Releases: {releases}\n\n"
            f"Your Task:\n"
            f"1. Search 3GPP specifications to identify all impacted TS numbers across Stage 1, Stage 2 Architecture, Stage 3 Radio (PHY/MAC/RRC), Core Network Protocols, Security, and OAM.\n"
            f"2. Output the structured 'Specifications Impact Map' with exact TS numbers, Titles, Working Groups, and functional scopes."
        )

        impact_map = await run_tool_loop(
            system_prompt=HLD_IMPACT_SCANNER_PROMPT,
            user_message=user_message,
            mcp=self.mcp,
            max_rounds=max_rounds,
        )
        return impact_map
