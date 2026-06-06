# EnterpriseCertIQ

**Multi-agent enterprise certification learning system**
*Microsoft Agents League 2026 · Reasoning Agents Track*

> **All data is synthetic.** No real employee names, email addresses, or organisational data.
> Identifiers follow the pattern `L-1001`, `EMP-001`, `TEAM-A`.

---

## What it does

EnterpriseCertIQ is a 6-agent pipeline that turns a certification goal into a grounded, work-aware study plan — with visible reasoning, calibrated readiness forecasting, a human-in-the-loop approval checkpoint, and a manager surface that turns weak signals into concrete follow-up. The plan stays in `draft` and is only marked published once a human approves it. Engagement and Manager Insights run on the draft to give the reviewer advisory previews at approval time.

| Agent | Role |
|---|---|
| **Learner Intake** | Parses and validates learner profile + Work IQ signals |
| **Learning Path Curator** | Retrieves cited content from Foundry IQ + Microsoft Learn MCP |
| **Study Plan Generator** | Builds a capacity-aware weekly schedule |
| **Readiness Critic** | Attacks the plan, finds gaps, produces calibrated forecast |
| **Engagement Agent** | Schedules reminders adapted to work patterns |
| **Manager Insights** | Surfaces team-level risk, intervention queues, peer-learning opportunities, and handoff actions |
| **Retrospective** *(conditional)* | Investigates prior failures — meta-reasoning about the system |

---

## Architecture

```
React Dashboard (port 5173)
        │  REST + SSE
        ▼
FastAPI Backend (port 8000)
        │
  ┌─────┴──────────────────────────────┐
  │  6-Agent Workflow (orchestrated)   │
  │  Middleware: PII · Citation · RAI  │
  └─────┬──────────────┬───────────────┘
        │ own MCP      │ MS Learn MCP
        ▼              ▼
 FastMCP Server    https://learn.microsoft.com/api/mcp
 (port 8001)
        │
        ▼
 Foundry Local OpenAI-compatible endpoint
 http://localhost:5273/v1
        │
   [switch to Azure via MODEL_BACKEND=azure_foundry]
        ▼
 Azure OpenAI / APIM Gateway
```

**IQ layers** (all three integrated)
- **Foundry IQ** — local: keyword search over `./backend/data/documents/`; Azure: Azure AI Search index
- **Work IQ** — synthetic meeting/focus signals from `./backend/data/synthetic/learners.json`,
  or **real Microsoft 365 calendar via Microsoft Graph** (`WORK_IQ_SOURCE=graph`,
  `backend/iq/work_iq_graph.py`; same `WorkContext` contract, synthetic fallback). See
  [docs/work-iq-graph.md](docs/work-iq-graph.md).
- **Fabric IQ** — semantic layer (`backend/iq/fabric_iq.py`): an ontology over roles,
  certifications, weighted skill domains, thresholds, and cohort outcomes. Powers the
  Readiness Critic (leverage-weighted objections) and Manager Insights (team skill-gap
  meaning, cohort benchmarks, intervention effectiveness). Local: in-memory ontology over
  the synthetic datasets; Azure: Microsoft Fabric semantic model / OneLake.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| Foundry Local | latest | See install note below |
| Git | any | — |

### Install Foundry Local

Foundry Local is a Microsoft tool that runs AI models on your device.

```bash
# macOS / Linux
pip install foundry-local-sdk

# Then verify:
python3 -c "from foundry_local_sdk import FoundryLocalManager; print('ok')"
```

See the [official docs](https://learn.microsoft.com/azure/foundry-local/get-started) for full installation including the desktop app if needed.

---

## Quick start

```bash
# 1. Clone / enter the project
cd enterprisecertiq

# 2. Run everything (first run installs deps and downloads model)
chmod +x start.sh
./start.sh
```

Open **http://localhost:5173** in your browser.

### LLM handoff

If another LLM needs to continue implementation or debugging, start with [docs/llm-handoff.md](docs/llm-handoff.md).
It captures the recent runtime fixes, structured-output contracts, validation status, and the fastest known local workflow.

---

## What `start.sh` does

| Step | What happens |
|---|---|
| 1 | Copies `.env.example` → `.env.local` if missing |
| 2 | Creates `.venv` and installs Python deps |
| 3 | Downloads + loads the configured Foundry Local model |
| 4 | Creates `backend/data/store/` for local JSON storage |
| 5 | Starts own MCP server on port 8001 |
| 6 | Starts FastAPI backend on port 8000 (`--reload` only when `BACKEND_RELOAD=true`) |
| 7 | `npm install` + starts Vite dev server on port 5173 |

Healthy services are reused on reruns, so `./start.sh --no-setup --skip-model` can be used as a fast restart path without duplicating backend or frontend processes.
Only processes started by the current script run are stopped when you press **Ctrl+C**.

---

## Skip flags

```bash
./start.sh --no-setup     # skip pip install + npm install (after first run)
./start.sh --skip-model   # skip model download (if already loaded)
./start.sh --no-setup --skip-model   # fastest restart
```

`./start.sh --no-setup --skip-model` is the validated fast restart path after the first successful setup.
The script now also starts the Foundry Local OpenAI-compatible web service. A cached or loaded model by itself is not enough.

### Foundry Local notes

- Keep the endpoint at `http://localhost:5273/v1`.
- Use the Foundry Local app name `enterprisecertiq` so the SDK reuses the cached model path.
- `start.sh` is the preferred entry point because it keeps the model service, MCP server, backend, and frontend aligned.
- During an active run, `/api/workflow/{run_id}/trace` can return `404` until the workflow has finished and the trace is persisted.

---

## Configuration (`.env.local`)

Copy `.env.example` to `.env.local` and edit as needed.

```bash
cp .env.example .env.local
```

### Local mode (default — no Azure needed)

```dotenv
MODEL_BACKEND=foundry_local
FOUNDRY_LOCAL_ENDPOINT=http://localhost:5273/v1
FOUNDRY_LOCAL_MODEL_ALIAS=qwen2.5-7b       # reliable tool-calling + good reasoning (measured best on M-series)
STORAGE_BACKEND=local
```

### List available Foundry Local models

```bash
source .venv/bin/activate
python3 scripts/setup_foundry.py --list
```

### Switch to Azure (after local testing)

```dotenv
MODEL_BACKEND=azure_foundry
AZURE_AI_PROJECT_ENDPOINT=https://your-hub.api.azureml.ms
AZURE_AI_API_KEY=your-key
AZURE_AI_MODEL_DEPLOYMENT=gpt-4o
AZURE_AI_REASONING_DEPLOYMENT=gpt-4o
FOUNDRY_IQ_ENDPOINT=https://your-hub.api.azureml.ms
ENABLE_TELEMETRY=true
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
STORAGE_BACKEND=local
```

### Lowest-cost build path for the hackathon

Use two phases instead of developing in Azure from day one.

| Phase | Backend | What to do here | Why this keeps costs down |
|---|---|---|---|
| 1. Build locally | `MODEL_BACKEND=foundry_local` | Build prompts, agent workflow, MCP tools, UI, synthetic datasets, HITL flow, and charts. | No cloud model cost while you iterate. |
| 2. Criteria proof | `MODEL_BACKEND=azure_foundry` | Validate the final demo path with real Foundry deployment, real Foundry IQ grounding, telemetry, and evaluation. | Azure is only used for criteria-critical proof, not day-to-day iteration. |

Recommended sequence:

1. Finish the product loop in Foundry Local.
2. Switch only the model and IQ settings to Azure Foundry.
3. Keep `STORAGE_BACKEND=local` unless you specifically need Cosmos DB for the demo.
4. Run the final demo and screenshots against Azure so the IQ and hosted-platform story are real.

If you want strict criteria coverage with minimal Azure spend, the minimum Azure scope is:

1. One Azure Foundry model deployment.
2. One real Foundry IQ knowledge source/index over the synthetic cert documents.
3. Telemetry export to Application Insights.
4. Groundedness evaluation in the Azure path.

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Backend status |
| `GET` | `/api/learners` | List synthetic learners |
| `GET` | `/api/learners/{id}` | Get one learner |
| `GET` | `/api/teams` | List teams |
| `POST` | `/api/workflow/run` | Start 6-agent pipeline → returns `run_id` |
| `GET` | `/api/workflow/{run_id}/stream` | SSE stream of trace events |
| `GET` | `/api/workflow/{run_id}/trace` | Full trace from storage |
| `POST` | `/api/plans/approve` | **HITL gate** — approve a draft plan |
| `GET` | `/api/mastery/{lid}/{cid}` | Domain mastery breakdown |
| `GET` | `/api/forecast/{lid}/{cid}` | Readiness forecast |
| `GET` | `/api/progress/{lid}/{cid}` | Assessment history and plan progress |
| `POST` | `/api/assessment/generate` | Generate mock exam |
| `POST` | `/api/assessment/submit` | Score exam + update forecast |
| `GET` | `/api/manager/{team_id}/insights` | Team Work IQ + Fabric IQ insights plus readiness/risk summary |
| `POST` | `/api/manager/{team_id}/what-if` | Counterfactual intervention simulator |
| `GET/POST/DELETE` | `/api/manager/{team_id}/peer-sessions` | Persisted peer-learning queue |
| `GET/POST/DELETE` | `/api/manager/{team_id}/interventions` | Persisted manager intervention queue |
| `GET` | `/api/reports/learner/{lid}/{cid}.pdf` | Learner readiness PDF (demo-cached) |
| `GET` | `/api/reports/manager/{team_id}.pdf` | Manager handoff brief PDF (demo-cached) |
| `GET` | `/api/audio/learner/{lid}/{cid}/transcript` | Grounded two-host audio briefing transcript + citations |
| `GET` | `/api/audio/learner/{lid}/{cid}.mp3` | Synthesized audio briefing (Azure AI Speech; 503 if unconfigured) |
| `GET` | `/api/cache/stats` | LLM response-cache hit/miss/entry counters |
| `GET` | `/api/cert-structures/{cert_id}` | Cert domain structure |
| `GET` | `/docs` | Interactive Swagger UI |

---

## Manager workflow

The Manager view now supports a full follow-through loop instead of just labels:

- `Needs action now` cards can be pinned into a persisted intervention queue.
- Peer-learning recommendations can be pinned into a persisted session queue.
- Both queues track `owner`, `status`, `manager_note`, and update timestamps.
- The page can copy a manager handoff brief that summarizes readiness, recommended actions, pinned interventions, and pinned peer sessions.
- Peer-learning now supports same-cert mentoring first, then a cross-cert study-habit fallback when a team has no same-cert coach available.

This makes TEAM-B usable in demos even when cert targets differ.

---

## Testing

```bash
source .venv/bin/activate
pytest -q
```

Regression coverage now includes:

- manager insights enriched payload keys
- peer-session create/update/delete flow
- manager intervention create/update/delete flow
- Fabric IQ semantic layer (thresholds, readiness semantics, team skill-gap, cohort)
- rubric-based agent-quality evals (per-agent E-checks, 0.8 threshold)
- LLM response cache (key determinism, round-trip, stats)
- Azure Content Safety guardrail (regex fallback + pipeline withholding)
- PDF report generation + demo cache

---

## Running parts individually

```bash
source .venv/bin/activate

# Backend only
uvicorn backend.main:app --reload --port 8000

# MCP server only
python3 -m backend.mcp_server.server

# Model setup only
python3 scripts/setup_foundry.py --alias qwen2.5-7b
python3 scripts/setup_foundry.py --list

# Frontend only
cd frontend && npm run dev
```

---

## Synthetic learner scenarios

| ID | Role | Cert | Scenario |
|---|---|---|---|
| L-1004 | Cloud Engineer | AZ-204 | Clean win path — lead demo here |
| L-1005 | DevOps Engineer | AZ-400 | Tight schedule, engagement triggers re-plan |
| L-1006 | Data Engineer | DP-203 | Prior failed attempt — retrospective fires |
| L-1007 | Cloud Engineer | AZ-204 | No prior evidence — honest "insufficient" forecast |
| L-1008 | Cloud Architect | AZ-305 | Good capacity, long deadline |

---

## Project structure

```
enterprisecertiq/
├── start.sh                   ← entry point
├── .env.example               ← config template
├── requirements.txt
├── config/
│   └── settings.py            ← Pydantic settings, LOCAL/Azure toggle
├── backend/
│   ├── main.py                ← FastAPI app + all routes
│   ├── agents/
│   │   └── factory.py         ← builds all 6 agents with tool executors
│   ├── core/
│   │   ├── agent.py           ← BaseAgent (tool-call loop, trace events)
│   │   ├── client.py          ← model client factory
│   │   ├── mcp_client.py      ← MCP HTTP client
│   │   └── workflow.py        ← 6-stage orchestrator
│   ├── mcp_server/
│   │   └── server.py          ← FastMCP server (9 tools)
│   ├── middleware/
│   │   └── pipeline.py        ← PII · citation-gate · safety · bias-audit
│   ├── iq/
│   │   ├── foundry_iq.py      ← grounded retrieval (local files / Azure AI Search)
│   │   ├── work_iq.py         ← work-context signals
│   │   └── fabric_iq.py       ← semantic ontology (roles, certs, domains, thresholds, cohort)
│   ├── storage/
│   │   └── store.py           ← JSON local / Cosmos DB abstraction
│   ├── models/                ← Pydantic schemas
│   └── data/
│       ├── synthetic/         ← learners, teams, certs, cohort data (all synthetic)
│       └── documents/         ← cert guide, team report (synthetic docs)
├── frontend/
│   └── src/
│       ├── pages/             ← LearnerView, ManagerView
│       └── components/        ← ReasoningPanel, CriticVsPlanView, DeviationGraph,
│                                 DomainMasteryChart, ServiceHeatmap,
│                                 PassThresholdGauge, HITLApprovalGate,
│                                 AIDisclosureBanner
├── prompts/                   ← versioned agent prompts (v1.md per agent)
├── scripts/
│   └── setup_foundry.py       ← model download + smoke-test
└── docs/adr/                  ← Architecture Decision Records
```

---

## Responsible AI

- Every generated artifact carries an **"AI-generated"** disclosure banner (RAI requirement).
- **HITL gate**: study plans require human approval before publishing.
- **Azure AI Content Safety**: free-text output is screened by the live Content Safety API
  (Hate/SelfHarm/Sexual/Violence; severity ≥ threshold → BLOCK), with a regex fallback offline.
- **Bias audit**: middleware scans generated assessment questions for stereotypes.
- **Citation-or-drop**: uncited claims are flagged, never silently passed through.
- **Honest uncertainty**: the Readiness Critic returns `insufficient_evidence: true` rather than fabricating a forecast.
- Manager Insights never exposes individual scores that could affect employment decisions
  (enforced and unit-tested via the agent rubric harness).

## Reliability & performance

- **LLM response cache** (`backend/core/llm_cache.py`) — SHA-256 keyed over the request;
  deterministic (temperature-0) calls hit the cache and skip the model entirely. Cuts cost +
  latency and makes demo re-runs instant. Hit-rate visible at `/api/cache/stats` and `/health`.
- **Rubric-based agent evals** (`backend/evals/agent_rubrics.py`) — per-agent quality checks
  with a 0.8 pass threshold, run in CI with no credentials.
- **PDF reports** (`backend/reports/pdf.py`) — learner readiness + manager handoff brief,
  demo-cached for instant repeat downloads.
- **Grounded audio study briefing** (`backend/audio/podcast.py`) — a NotebookLM-style
  **two-host podcast** generated *only* from approved cert content, with the transcript +
  citations shown for provenance. Two-voice SSML → Azure AI Speech (REST); transcript works
  with no key, audio synthesis is opt-in, MP3s demo-cached. Deterministic fallback → a full
  script with zero model.
- **Deterministic tier-3 fallback** (`backend/agents/fallbacks.py`) — every agent has a
  no-model deterministic builder. `AGENT_FALLBACK_MODE=auto` (default) degrades gracefully on
  a model error; `=force` runs the **entire pipeline with zero model calls** (instant,
  reproducible demo mode). Fallback outputs pass the same quality rubrics.
- **9 certification families** — `AZ-204/305/400`, `DP-203/100`, `AI-102/900`, `SC-100`,
  `MS-102` — fully data-driven from `cert_structures.json` (every agent/IQ layer adapts; no
  code change to add a cert).
- **Containerised deploy** — see [docs/deployment.md](docs/deployment.md) (Azure Container Apps).

---

## Microsoft technology stack

| Component | Role |
|---|---|
| Foundry Local SDK | On-device model inference (dev) |
| Azure OpenAI / APIM | Cloud model inference (demo) |
| Microsoft Learn MCP | `microsoft_docs_search`, `microsoft_docs_fetch`, `microsoft_code_sample_search` |
| Foundry IQ | Grounded knowledge retrieval from cert content |
| Work IQ | Work-context signals (meeting load, focus windows) |
| Fabric IQ | Semantic ontology — roles, certs, weighted domains, thresholds, cohort outcomes |
| Azure AI Content Safety | Live output screening (regex fallback offline) |
| Azure AI Evaluation | Groundedness LLM-as-judge (Azure path) |
| Azure AI Speech | Two-voice TTS for the grounded audio study briefing |
| Azure Cosmos DB | Production storage (local JSON in dev) |
| FastMCP | Own MCP server exposing 10 typed tools (incl. Fabric IQ semantics) |
| ReportLab | Learner + manager PDF report generation |

---

*Synthetic data only. No real PII. Built for Microsoft Agents League 2026.*
