#!/usr/bin/env python3
"""
Full pipeline test: Researcher → Analyst (same path as POST /chat).

Usage:
  cd 3gpp-research-agent
  PYTHONPATH=. python scripts/test_chat_pipeline.py
  PYTHONPATH=. python scripts/test_chat_pipeline.py --question "Your question here"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.orchestrator import run_research_gap_analysis  # noqa: E402


DEFAULT_QUESTION = (
    "What does TS 38.331 cover regarding RRC connection establishment? "
    "Cite the relevant content."
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument(
        "--series",
        nargs="*",
        default=None,
        help="Optional series filter, e.g. --series 38",
    )
    parser.add_argument(
        "--releases",
        nargs="*",
        default=None,
        help="Optional releases, e.g. --releases Rel-17 Rel-18",
    )
    args = parser.parse_args()

    if not os.getenv("LLM_API_KEY"):
        print("ERROR: LLM_API_KEY is not set in environment or .env")
        sys.exit(1)

    print("Question:", args.question)
    print("Running Researcher → Analyst …\n")

    result = await run_research_gap_analysis(
        args.question,
        series=args.series,
        releases=args.releases,
    )

    print("=" * 60)
    print("EVIDENCE (Researcher)")
    print("=" * 60)
    print(result["evidence"])
    print()
    print("=" * 60)
    print("ANSWER (Analyst)")
    print("=" * 60)
    print(result["answer"])


if __name__ == "__main__":
    asyncio.run(main())
