"""Parallel Domain Sub-Agents for High-Level Design (HLD) Synthesis."""

from __future__ import annotations

import asyncio
from typing import Any

from app.llm import chat_completion
from app.prompts import (
    HLD_ARCH_SPECIALIST_PROMPT,
    HLD_PROTOCOL_SPECIALIST_PROMPT,
    HLD_RISK_SPECIALIST_PROMPT,
)


def _compact_text(text: str, max_chars: int = 4000) -> str:
    """Ensure intermediate context fits comfortably within per-subagent token budgets."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated for synthesis efficiency]..."


class HLDArchitectureSpecialist:
    """Sub-Agent 1: Generates Scope, System Architecture & Mermaid Signaling Call Flows."""

    async def run(
        self,
        feature_name: str,
        impact_map: str,
        parameters_ledger: str,
        *,
        feature_description: str = "",
        target_releases: list[str] | None = None,
    ) -> str:
        desc_clause = f"\nScope Details:\n{feature_description}" if feature_description else ""
        user_message = (
            f"Feature Name: {feature_name}{desc_clause}\n"
            f"Target Releases: {target_releases}\n\n"
            f"Stage 1 Impact Map:\n{_compact_text(impact_map, 3500)}\n\n"
            f"Stage 2 Technical Ledger:\n{_compact_text(parameters_ledger, 3500)}\n\n"
            f"Synthesize Section 1 (Feature Scope & Executive Summary) and Section 3 (End-to-End System Architecture & Mermaid Diagram)."
        )
        messages = [
            {"role": "system", "content": HLD_ARCH_SPECIALIST_PROMPT},
            {"role": "user", "content": user_message},
        ]
        print("  [Sub-Agent 1/3] Generating Architecture & Mermaid Flow...")
        msg = await chat_completion(messages, tools=None, tool_choice=None)
        return msg.content or ""


class HLDProtocolSpecialist:
    """Sub-Agent 2: Generates Interface Tables (Uu, Xn, F1, SBI), IEs, Timers, and Release Progression."""

    async def run(
        self,
        feature_name: str,
        impact_map: str,
        parameters_ledger: str,
        *,
        feature_description: str = "",
        target_releases: list[str] | None = None,
    ) -> str:
        desc_clause = f"\nScope Details:\n{feature_description}" if feature_description else ""
        user_message = (
            f"Feature Name: {feature_name}{desc_clause}\n"
            f"Target Releases: {target_releases}\n\n"
            f"Stage 1 Impact Map:\n{_compact_text(impact_map, 3500)}\n\n"
            f"Stage 2 Technical Ledger:\n{_compact_text(parameters_ledger, 3500)}\n\n"
            f"Synthesize Section 4 (Interface, Protocol & Parameter Changes) and Section 5 (Cross-Release Evolution & Gap Analysis Table)."
        )
        messages = [
            {"role": "system", "content": HLD_PROTOCOL_SPECIALIST_PROMPT},
            {"role": "user", "content": user_message},
        ]
        print("  [Sub-Agent 2/3] Generating Interface Parameters & Release Matrix...")
        msg = await chat_completion(messages, tools=None, tool_choice=None)
        return msg.content or ""


class HLDRiskSpecialist:
    """Sub-Agent 3: Generates Impacted 3GPP Specifications Table, Hardware/RF Risks, and Open Questions."""

    async def run(
        self,
        feature_name: str,
        impact_map: str,
        parameters_ledger: str,
        *,
        feature_description: str = "",
        target_releases: list[str] | None = None,
    ) -> str:
        desc_clause = f"\nScope Details:\n{feature_description}" if feature_description else ""
        user_message = (
            f"Feature Name: {feature_name}{desc_clause}\n"
            f"Target Releases: {target_releases}\n\n"
            f"Stage 1 Impact Map:\n{_compact_text(impact_map, 3500)}\n\n"
            f"Stage 2 Technical Ledger:\n{_compact_text(parameters_ledger, 3500)}\n\n"
            f"Synthesize Section 2 (Impacted 3GPP Specifications Matrix Table) and Section 6 (Design Team Open Questions, Technical Risks & Implementation Considerations)."
        )
        messages = [
            {"role": "system", "content": HLD_RISK_SPECIALIST_PROMPT},
            {"role": "user", "content": user_message},
        ]
        print("  [Sub-Agent 3/3] Generating Spec Matrix, Risks & Open Questions...")
        msg = await chat_completion(messages, tools=None, tool_choice=None)
        return msg.content or ""


def assemble_hld_document(
    feature_name: str,
    arch_section: str,
    protocol_section: str,
    risk_section: str,
) -> str:
    """
    Stitches parallel sub-agent outputs into the standardized 6-section High-Level Design document.
    """
    # Extract Section 1 and Section 3 from arch_section
    # Extract Section 2 and Section 6 from risk_section
    # Extract Section 4 and Section 5 from protocol_section

    document = f"# High-Level Design (HLD): {feature_name}\n\n"

    # Section 1 & 3 (Architecture Specialist)
    # Section 2 & 6 (Risk Specialist)
    # Section 4 & 5 (Protocol Specialist)
    # Order: Section 1 -> Section 2 -> Section 3 -> Section 4 -> Section 5 -> Section 6

    # If the sub-agents output clean markdown headers, we compose them smoothly:
    document += f"{arch_section.strip()}\n\n"
    document += f"---\n\n{risk_section.strip()}\n\n"
    document += f"---\n\n{protocol_section.strip()}\n"

    return document
