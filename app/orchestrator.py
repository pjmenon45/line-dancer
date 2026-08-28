"""Sequential orchestrator: Researcher → Analyst-Synthesizer."""

from __future__ import annotations

from app.agents.analyst import AnalystAgent
from app.agents.hld_extractor import HLDInterfaceExtractorAgent
from app.agents.hld_scanner import HLDImpactScannerAgent
from app.agents.hld_specialists import (
    HLDArchitectureSpecialist,
    HLDProtocolSpecialist,
    HLDRiskSpecialist,
    assemble_hld_document,
)
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
    Run the 2-agent Standards Research & Gap Analysis pipeline.
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


async def run_new_feature_hld(
    feature_name: str,
    *,
    feature_description: str = "",
    target_releases: list[str] | None = None,
    mcp: MCPClient | None = None,
) -> dict[str, str]:
    """
    Run the Multi-Agent New Feature High-Level Design (HLD) pipeline:
    Stage 1: Impact Scanner (maps affected specs across domains)
    Stage 2: Interface & Parameter Extractor (extracts Uu/Xn/F1/SBI deltas, IEs, timers)
    Stage 3: Parallel Domain Specialists (Architecture, Protocols, and Risk Sub-Agents via asyncio.gather)
    Stage 4: Master HLD Document Assembly
    """

    async def _run(client: MCPClient) -> dict[str, str]:
        scanner = HLDImpactScannerAgent(client)
        extractor = HLDInterfaceExtractorAgent(client)

        # Stage 1: Impact Scanning
        impact_map = await scanner.run(
            feature_name,
            feature_description=feature_description,
            target_releases=target_releases,
        )

        # Stage 2: Interface & Parameter Extraction
        parameters_ledger = await extractor.run(
            feature_name,
            impact_map,
            feature_description=feature_description,
            target_releases=target_releases,
        )

        # Stage 3: Parallel Domain Sub-Agents (asyncio.gather)
        arch_spec = HLDArchitectureSpecialist()
        proto_spec = HLDProtocolSpecialist()
        risk_spec = HLDRiskSpecialist()

        arch_res, proto_res, risk_res = await asyncio.gather(
            arch_spec.run(
                feature_name,
                impact_map,
                parameters_ledger,
                feature_description=feature_description,
                target_releases=target_releases,
            ),
            proto_spec.run(
                feature_name,
                impact_map,
                parameters_ledger,
                feature_description=feature_description,
                target_releases=target_releases,
            ),
            risk_spec.run(
                feature_name,
                impact_map,
                parameters_ledger,
                feature_description=feature_description,
                target_releases=target_releases,
            ),
        )

        # Stage 4: Master HLD Assembly
        hld_document = assemble_hld_document(
            feature_name,
            arch_section=arch_res,
            protocol_section=proto_res,
            risk_section=risk_res,
        )

        return {
            "impact_map": impact_map,
            "parameters_ledger": parameters_ledger,
            "hld_document": hld_document,
        }

    if mcp is not None:
        return await _run(mcp)

    async with mcp_session() as client:
        return await _run(client)

