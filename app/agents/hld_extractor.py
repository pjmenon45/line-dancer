"""Stage 2: HLD Interface & Parameter Extractor Agent – extracts interface deltas, IEs, and release progression."""

from __future__ import annotations

from app.agents.base import run_tool_loop
from app.mcp_client import MCPClient, _default_releases
from app.prompts import HLD_INTERFACE_EXTRACTOR_PROMPT


class HLDInterfaceExtractorAgent:
    def __init__(self, mcp: MCPClient):
        self.mcp = mcp

    async def run(
        self,
        feature_name: str,
        impact_map: str,
        *,
        feature_description: str = "",
        target_releases: list[str] | None = None,
        max_rounds: int = 2,
    ) -> str:
        releases = target_releases or _default_releases()
        desc_clause = f"\nAdditional Context:\n{feature_description}" if feature_description else ""

        user_message = (
            f"Feature: {feature_name}{desc_clause}\n"
            f"Target Releases: {releases}\n\n"
            f"Stage 1 Specifications Impact Map:\n{impact_map}\n\n"
            f"Your Task:\n"
            f"1. Extract concrete interface changes (Uu, Xn, F1, E1, N2, N3, N4, SBI).\n"
            f"2. Extract Information Elements (IEs), RRC/SIB parameters, DCI formats, and UE capabilities.\n"
            f"3. Detail cross-release delta evolution across {releases}.\n"
            f"4. Output the structured 'Technical Parameters & Interfaces Ledger'."
        )

        parameters_ledger = await run_tool_loop(
            system_prompt=HLD_INTERFACE_EXTRACTOR_PROMPT,
            user_message=user_message,
            mcp=self.mcp,
            max_rounds=max_rounds,
        )
        return parameters_ledger
