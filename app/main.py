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
from app.orchestrator import run_new_feature_hld, run_research_gap_analysis  # noqa: E402

app = FastAPI(
    title="3GPP Research & Gap Analysis + New Feature HLD Studio",
    version="0.2.0",
    description="Multi-agent 3GPP Standards Research & High-Level Design (HLD) Engine",
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


class HLDRequest(BaseModel):
    feature_name: str = Field(
        ..., min_length=1, description="Target feature or study item (e.g. Regenerative Satellite Payloads for NTN)"
    )
    feature_description: str = Field(
        default="", description="Additional requirements, architectural constraints, or scope notes"
    )
    target_releases: list[str] | None = Field(
        default=None, description="Target releases, e.g. ['Rel-17', 'Rel-18', 'Rel-19']"
    )
    include_intermediates: bool = Field(
        default=True, description="If true, return Stage 1 impact map and Stage 2 parameters ledger"
    )


class HLDResponse(BaseModel):
    hld_document: str
    impact_map: str | None = None
    parameters_ledger: str | None = None


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "3GPP Research & Gap Analysis + New Feature HLD Studio API",
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


@app.post("/hld", response_model=HLDResponse)
async def hld_generate(req: HLDRequest) -> HLDResponse:
    """Run the 3-stage New Feature HLD pipeline (Scanner → Extractor → Architect)."""
    try:
        result = await run_new_feature_hld(
            feature_name=req.feature_name,
            feature_description=req.feature_description,
            target_releases=req.target_releases,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return HLDResponse(
        hld_document=result["hld_document"],
        impact_map=result["impact_map"] if req.include_intermediates else None,
        parameters_ledger=result["parameters_ledger"] if req.include_intermediates else None,
    )


@app.post("/hld/stream")
async def hld_stream(req: HLDRequest) -> StreamingResponse:
    """
    SSE stream for the 3-stage New Feature HLD workflow:
      status(scanner) → impact_map → status(extractor) → parameters_ledger → status(architect) → hld_document → done
    """

    async def event_generator():
        try:
            from app.agents.hld_architect import HLDArchitectAgent
            from app.agents.hld_extractor import HLDInterfaceExtractorAgent
            from app.agents.hld_scanner import HLDImpactScannerAgent
            from app.mcp_client import mcp_session

            async with mcp_session() as client:
                scanner = HLDImpactScannerAgent(client)
                extractor = HLDInterfaceExtractorAgent(client)
                architect = HLDArchitectAgent(client)

                # Stage 1: Scanner
                yield _sse(
                    "status",
                    {"stage": "scanner", "message": "Stage 1/3: Scanning impacted 3GPP specifications across Core, RAN, Security & Management…"},
                )
                impact_map = await scanner.run(
                    req.feature_name,
                    feature_description=req.feature_description,
                    target_releases=req.target_releases,
                )
                if req.include_intermediates:
                    yield _sse("impact_map", {"text": impact_map})

                # Stage 2: Extractor
                yield _sse(
                    "status",
                    {"stage": "extractor", "message": "Stage 2/3: Extracting interfaces (Uu, Xn, F1, SBI), parameters, IEs, and release deltas…"},
                )
                parameters_ledger = await extractor.run(
                    req.feature_name,
                    impact_map,
                    feature_description=req.feature_description,
                    target_releases=req.target_releases,
                )
                if req.include_intermediates:
                    yield _sse("parameters_ledger", {"text": parameters_ledger})

                # Stage 3: Architect
                yield _sse(
                    "status",
                    {"stage": "architect", "message": "Stage 3/3: Synthesizing master High-Level Design (HLD) document & architecture diagrams…"},
                )
                hld_document = await architect.run(
                    req.feature_name,
                    impact_map,
                    parameters_ledger,
                    feature_description=req.feature_description,
                    target_releases=req.target_releases,
                )
                yield _sse("hld_document", {"text": hld_document})
                yield _sse("done", {})
        except Exception as exc:  # noqa: BLE001
            import traceback
            print(f"[Error in hld_stream]: {exc}")
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

