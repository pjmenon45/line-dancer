#!/usr/bin/env python3
"""
Full pipeline test: Researcher → Analyst (same path as POST /chat).

Requires LLM_API_KEY in .env

  PYTHONPATH=. python scripts/test_pipeline.py
  PYTHONPATH=. python scripts/test_pipeline.py --question "..."
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


DEFAULT_Q = (
    "What does TS 38.331 cover regarding RRC connection establishment? "
    "Cite the relevant content."
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", default=DEFAULT_Q)
    parser.add_argument(
        "--releases",
        default=None,
        help="Comma-separated, e.g. Rel-16,Rel-17",
    )
    args = parser.parse_args()

    if not os.getenv("LLM_API_KEY"):
        print("ERROR: LLM_API_KEY not set in environment / .env")
        sys.exit(1)

    releases = (
        [r.strip() for r in args.releases.split(",") if r.strip()]
        if args.releases
        else None
    )

    print(f"Question: {args.question}\n")
    print("Running Researcher → Analyst …\n")
    result = await run_research_gap_analysis(args.question, releases=releases)

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
