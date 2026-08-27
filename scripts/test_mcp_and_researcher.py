#!/usr/bin/env python3
"""
Local test: MCP connectivity + optional Researcher agent.

Usage:
  # MCP only (no LLM key required)
  cd 3gpp-research-agent
  PYTHONPATH=. python scripts/test_mcp_and_researcher.py --mcp-only

  # Full Researcher (needs LLM_API_KEY in env or .env)
  PYTHONPATH=. python scripts/test_mcp_and_researcher.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

# Project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.mcp_client import mcp_session  # noqa: E402


PHASE1_QUESTIONS = [
    "What does TS 38.331 cover regarding RRC connection establishment? Cite the relevant content.",
    "Summarize the main changes related to RedCap or reduced capability UEs in TS 38 series across recent releases.",
    "Extract implementation requirements for network slicing related features in NR (TS 38 series).",
]


async def test_mcp_only() -> None:
    print("=== MCP connectivity test ===")
    async with mcp_session() as client:
        tools = await client.list_tools()
        print(f"Tools exposed by MCP ({len(tools)}):")
        for t in tools:
            print(f"  - {t}")

        print("\nCalling search_specifications (TS 38 RRC)…")
        result = await client.call_tool(
            "search_specifications",
            {
                "query": "RRC connection establishment",
                "series_filter": ["38"],
                "release_filter": ["Rel-16", "Rel-17", "Rel-18"],
                "max_results": 3,
                "include_content": True,
            },
        )
        preview = result[:1200] + ("…" if len(result) > 1200 else "")
        print(preview)
        print("\nMCP test OK.")


async def test_researcher(question: str) -> None:
    if not os.getenv("LLM_API_KEY"):
        print("LLM_API_KEY not set — skipping Researcher agent test.")
        print("Set it in .env and re-run without --mcp-only.")
        return

    from app.agents.researcher import ResearcherAgent

    print("=== Researcher agent test ===")
    print(f"Question: {question}\n")
    async with mcp_session() as client:
        agent = ResearcherAgent(client)
        evidence = await agent.run(question)
        print("--- Evidence pack ---")
        print(evidence)
        print("--- end ---")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-only", action="store_true", help="Only test MCP tools")
    parser.add_argument(
        "--question",
        type=str,
        default=PHASE1_QUESTIONS[0],
        help="Question for Researcher (default: first Phase-1 question)",
    )
    parser.add_argument(
        "--all-questions",
        action="store_true",
        help="Run Researcher on all Phase-1 sample questions",
    )
    args = parser.parse_args()

    if args.mcp_only:
        await test_mcp_only()
        return

    # Always smoke-test MCP first
    await test_mcp_only()
    print()

    if args.all_questions:
        for q in PHASE1_QUESTIONS:
            await test_researcher(q)
            print("\n" + "=" * 60 + "\n")
    else:
        await test_researcher(args.question)


if __name__ == "__main__":
    asyncio.run(main())
