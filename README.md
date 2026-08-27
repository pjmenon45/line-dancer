# 3GPP Research & Gap Analysis Agent

2-agent FastAPI service for Standards Research & Gap Analysis over the lightweight 3GPP MCP (`3gpp-mcp-charging`).

## Architecture

```
Vercel AI Chatbot  →  FastAPI (Render)  →  Researcher + Analyst agents
                                              ↓
                                    Lightweight 3GPP MCP (stdio/npx)
                                              ↓
                                    Configurable LLM (Groq / OpenAI-compatible)
```

### Agents

| Agent | Role |
|-------|------|
| **Researcher** | Search & retrieve evidence via MCP tools |
| **Analyst-Synthesizer** | Gap analysis, comparison, final cited report |

## Project layout

```
app/
  main.py              # FastAPI endpoints
  llm.py               # Configurable OpenAI-compatible client
  mcp_client.py        # MCP stdio wrapper + tool schemas
  prompts.py           # System prompts
  orchestrator.py      # Researcher → Analyst pipeline
  agents/
    base.py            # Shared tool-calling loop
    researcher.py
    analyst.py
```

## Local setup

```bash
cd 3gpp-research-agent
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with LLM_API_KEY and optional HUGGINGFACE_TOKEN
```

Requires Node.js (for `npx 3gpp-mcp-charging@latest serve`).

### Run

```bash
uvicorn app.main:app --reload --port 8000
```

- Health: `GET http://localhost:8000/health`
- Chat: `POST http://localhost:8000/chat`  
  ```json
  { "message": "What does TS 38.331 say about RRC connection establishment?", "include_evidence": true }
  ```
- Stream: `POST http://localhost:8000/chat/stream`

## Render deploy

1. New Web Service from this repo.
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Set env vars from `.env.example` (especially `LLM_API_KEY`).
5. Ensure the runtime has Node.js if using stdio MCP via `npx`.

## Next steps

- Wire Vercel AI Chatbot to `/chat` or `/chat/stream`
- Add token-level streaming from the LLM
- Optional: MCP HTTP transport for a separate MCP service
- Expand to Feature Impact prompts / third agent
