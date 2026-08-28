"""Stage 3: Lead 3GPP System Architect Agent – synthesizes the master High-Level Design (HLD) document."""

from __future__ import annotations

from app.agents.base import run_tool_loop
from app.mcp_client import MCPClient, _default_releases
from app.prompts import HLD_ARCHITECT_PROMPT


class HLDArchitectAgent:
    def __init__(self, mcp: MCPClient):
        self.mcp = mcp

    async def run(
        self,
        feature_name: str,
        impact_map: str,
        parameters_ledger: str,
        *,
        feature_description: str = "",
        target_releases: list[str] | None = None,
        max_rounds: int = 1,
    ) -> str:
        releases = target_releases or _default_releases()
        desc_clause = f"\nAdditional Context:\n{feature_description}" if feature_description else ""

        user_message = (
            f"Feature Name: {feature_name}{desc_clause}\n"
            f"Target Releases: {releases}\n\n"
            f"Stage 1 Specifications Impact Map:\n{impact_map}\n\n"
            f"Stage 2 Technical Parameters & Interfaces Ledger:\n{parameters_ledger}\n\n"
            f"Your Task:\n"
            f"Synthesize the master High-Level Design (HLD) document following the mandatory 6-section template:\n"
            f"1. Feature Scope & Executive Summary\n"
            f"2. Impacted 3GPP Specifications Matrix (Table with TS, WG, Title, Impact, Baseline & Evolution)\n"
            f"3. End-to-End System Architecture & Information Flows (with valid Mermaid diagram with quoted labels)\n"
            f"4. Interface, Protocol & Parameter Changes (Detailed tables for Uu, Xn, F1, N2/N3/SBI, IEs, Timers)\n"
            f"5. Cross-Release Evolution & Gap Analysis (Comparison matrix across {releases})\n"
            f"6. Design Team Open Questions, Technical Risks & Implementation Considerations"
        )

        hld_document = await run_tool_loop(
            system_prompt=HLD_ARCHITECT_PROMPT,
            user_message=user_message,
            mcp=self.mcp,
            max_rounds=max_rounds,
        )
        return hld_document
