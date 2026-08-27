"""
FastAPI entrypoint for the 3GPP Research & Gap Analysis service.

Endpoints:
  GET  /health
  POST /chat          – non-streaming JSON (Researcher → Analyst)
  POST /chat/stream   – SSE with stage events, then final answer
"""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()

from app.agents.analyst import AnalystAgent  # noqa: E402
from app.agents.researcher import ResearcherAgent  # noqa: E402
from app.mcp_client import mcp_session  # noqa: E402
from app.orchestrator import run_research_gap_analysis  # noqa: E402

app = FastAPI(
    title="3GPP Research & Gap Analysis",
    version="0.1.0",
    description="2-agent Standards Research & Gap Analysis over the lightweight 3GPP MCP",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User question")
    series: list[str] | None = Field(
        default=None, description="Series filter, e.g. ['38']"
    )
    releases: list[str] | None = Field(
        default=None, description="Release filter, e.g. ['Rel-17','Rel-18']"
    )
    include_evidence: bool = Field(
        default=False, description="If true, return Researcher evidence as well"
    )


class ChatResponse(BaseModel):
    answer: str
    evidence: str | None = None


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "3GPP Research & Gap Analysis API",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Full pipeline: Researcher gathers evidence, Analyst produces final answer."""
    try:
        result = await run_research_gap_analysis(
            req.message,
            series=req.series,
            releases=req.releases,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        answer=result["answer"],
        evidence=result["evidence"] if req.include_evidence else None,
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """
    SSE stream with accurate stage events:
      status(researcher) → evidence? → status(analyst) → answer → done
    """

    async def event_generator():
        yield _sse(
            "status",
            {"stage": "researcher", "message": "Gathering evidence from 3GPP specifications…"},
        )
        try:
            result = await run_research_gap_analysis(
                req.message,
                series=req.series,
                releases=req.releases,
            )
            if req.include_evidence and result.get("evidence"):
                yield _sse("evidence", {"text": result["evidence"]})

            yield _sse("status", {"stage": "analyst", "message": "Synthesizing technical report…"})
            yield _sse("answer", {"text": result["answer"]})
            yield _sse("done", {})
        except Exception as exc:  # noqa: BLE001
            import traceback
            print(f"[Error in chat_stream]: {exc}")
            traceback.print_exc()
            yield _sse("error", {"detail": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
