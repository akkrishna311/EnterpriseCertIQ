# EnterpriseCertIQ

**Multi-agent enterprise certification learning system**
*Microsoft Agents League 2026 · Reasoning Agents Track*

**Highlights:** 9 Hosted Agents on Azure AI Foundry · all 3 IQ layers (Foundry IQ = **real Azure AI
Search VECTOR_SEMANTIC_HYBRID**, Fabric IQ ontology + live tool, Work IQ signals) · **calibrated
P(pass), LOO AUC ≈ 0.80** with INSUFFICIENT abstention · adversarial critic→replan loop · 3
versioned **Foundry Skills** (behavioral governance) · **GO / CONDITIONAL_GO / NOT_YET** booking
verdict · **Largest Remainder Algorithm** study-hour allocation · NotebookLM-style **audio podcast**
coaching · what-if simulator · HITL exam gate · App Insights tracing + azure-ai-evaluation agent
scorers · Azure Content Safety + **adversarial red-team 16/16 held (0% ASR)** · **90 tests** ·
inspectable `eval/` artifacts · `azd up` one-command provisioning.

> **All data is synthetic.** No real employee names, email addresses, or organisational data.
> Identifiers follow the pattern `L-1001`, `EMP-001`, `TEAM-A`.

---

## What it does

EnterpriseCertIQ is a 9-agent system that turns a certification goal into a grounded, work-aware
study plan — with visible reasoning, calibrated readiness forecasting, a human-in-the-loop approval
checkpoint, and a manager surface that turns weak signals into concrete follow-up. The plan stays in
`draft` and is only marked published once a human approves it. Engagement and Manager Insights run
on the draft to give the reviewer advisory previews at approval time.

| Agent | Role |
|---|---|
| **Orchestrator** | Routes the session, manages multi-agent handoffs, drives the pipeline |
| **Learner Intake** | Parses and validates learner profile + Work IQ signals |
| **Learning Path Curator** | Retrieves cited content from Foundry IQ (VECTOR_SEMANTIC_HYBRID) + Microsoft Learn MCP |
| **Study Plan Generator** | Builds a capacity-aware weekly schedule via Largest Remainder Algorithm |
| **Readiness Critic** | Attacks the plan, finds gaps, produces calibrated P(pass) forecast with INSUFFICIENT abstention |
| **Engagement Agent** | Schedules reminders adapted to work patterns (runs ∥ Readiness Forecast) |
| **Assessment Agent** | Generates mock exams, scores responses, issues GO / CONDITIONAL_GO / NOT_YET booking verdict |
| **Manager Insights** | Surfaces team-level risk, ROI cost-of-delay, intervention queues, peer-learning opportunities, and handoff actions |
| **Retrospective** *(conditional)* | Investigates prior failures — meta-reasoning about the system |

---

## Architecture

```
React Dashboard (port 5173)
        │  REST + SSE
        ▼
FastAPI Backend (port 8000)
        │
  ┌─────┴───────────────────────────────────────┐
  │  9-Agent Workflow (orchestrated)            │
  │  Stage 5 Engagement ∥ Stage 6a Forecast     │  ← asyncio.gather() parallel
  │  Middleware: PII · Citation · RAI           │
  └─────┬──────────────┬────────────────────────┘
        │ own MCP      │ MS Learn MCP
        ▼              ▼
 FastMCP Server    https://learn.microsoft.com/api/mcp
 (port 8001,
  10 typed tools)
        │
        ▼
 Foundry Local OpenAI-compatible endpoint
 http://localhost:5273/v1
        │
   [switch to Azure via MODEL_BACKEND=azure_foundry]
        ▼
 Azure AI Foundry (gpt-4.1)
 9 Hosted Agents · VECTOR_SEMANTIC_HYBRID search
 3 Foundry Skills (versioned behavioral governance)
```

**IQ layers** (all three integrated)
- **Foundry IQ** — local: keyword search over `./backend/data/documents/`; Azure: Azure AI Search
  index with **`AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID`** (vector + BM25 + semantic
  reranking, ~36% quality improvement over keyword-only). Grounded agents: Learning Path Curator,
  Assessment Agent, Readiness Critic.
- **Work IQ** — synthetic meeting/focus signals from `./backend/data/synthetic/learners.json`,
  or **real Microsoft 365 calendar via Microsoft Graph** (`WORK_IQ_SOURCE=graph`,
  `backend/iq/work_iq_graph.py`; same `WorkContext` contract, synthetic fallback). See
  [docs/work-iq-graph.md](docs/work-iq-graph.md).
- **Fabric IQ** — semantic layer (`backend/iq/fabric_iq.py`): an ontology over roles,
  certifications, weighted skill domains, thresholds, and cohort outcomes. Powers the
  Readiness Critic (leverage-weighted objections) and Manager Insights (team skill-gap
  meaning, cohort benchmarks, intervention effectiveness). Local: in-memory ontology over
  the synthetic datasets; Azure: Microsoft Fabric / OneLake SQL analytics endpoint.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| Node.js | 20+ | `node --version` |
| Foundry Local | latest | See install note below |
| Git | any | — |

### Install Foundry Local

```bash
# macOS / Linux
pip install foundry-local-sdk

# Then verify:
python3 -c "from foundry_local_sdk import FoundryLocalManager; print('ok')"
```

See the [official docs](https://learn.microsoft.com/azure/foundry-local/get-started) for full
installation including the desktop app if needed.

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

If another LLM needs to continue implementation or debugging, start with
[docs/llm-handoff.md](docs/llm-handoff.md). It captures the recent runtime fixes, structured-output
contracts, validation status, and the fastest known local workflow.

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

Healthy services are reused on reruns, so `./start.sh --no-setup --skip-model` can be used as a
fast restart path without duplicating backend or frontend processes. Only processes started by the
current script run are stopped when you press **Ctrl+C**.

---

## Skip flags

```bash
./start.sh --no-setup     # skip pip install + npm install (after first run)
./start.sh --skip-model   # skip model download (if already loaded)
./start.sh --no-setup --skip-model   # fastest restart
```

`./start.sh --no-setup --skip-model` is the validated fast restart path after the first successful
setup. The script also starts the Foundry Local OpenAI-compatible web service. A cached or loaded
model by itself is not enough.

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
FOUNDRY_LOCAL_MODEL_ALIAS=qwen2.5-7b       # reliable tool-calling + good reasoning
STORAGE_BACKEND=local
```

### Switch to Azure (after local testing)

```dotenv
MODEL_BACKEND=azure_foundry
AZURE_AI_PROJECT_ENDPOINT=https://agenticaifoundrypoc.services.ai.azure.com/api/projects/aipoc
AZURE_AI_API_KEY=your-key
AZURE_AI_MODEL_DEPLOYMENT=gpt-4.1
FOUNDRY_USE_RESPONSES_API=true              # activate Foundry Hosted Agent Responses API path
ENABLE_TELEMETRY=true
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
STORAGE_BACKEND=local
```

### Two-phase development approach

| Phase | Backend | What to do here |
|---|---|---|
| 1. Build locally | `MODEL_BACKEND=foundry_local` | Build prompts, workflow, MCP tools, UI, synthetic datasets, HITL flow |
| 2. Cloud validation | `MODEL_BACKEND=azure_foundry` | Validate with Foundry Hosted Agents, VECTOR_SEMANTIC_HYBRID, Foundry Skills, telemetry |

---

## Azure AI Foundry — Hosted Agent deployment

### Provision + register with one command

```bash
az login && azd auth login
azd up          # provisions App Service + registers 9 Hosted Agents + 3 Foundry Skills
```

`azure.yaml` at the project root defines the `azd up` manifest. The `postprovision` hook runs:

1. `python scripts/register_agents_cloud_shell.py` — registers all 9 Hosted Agents
2. `python scripts/register_skills.py --list` — lists registered Foundry Skills

### Manual agent registration

```bash
# From Azure Cloud Shell or any machine with DefaultAzureCredential
python scripts/register_agents_cloud_shell.py

# Dry-run (validate connection only, no writes)
python scripts/register_agents_cloud_shell.py --dry-run

# Re-create all agents (idempotent — deletes + recreates)
python scripts/register_agents_cloud_shell.py --recreate
```

The script uses `azure-ai-projects>=2.0.0` → `AIProjectClient` → `PromptAgentDefinition` (Foundry
v2 native path). Grounded agents (Learning Path Curator, Assessment Agent, Readiness Critic) get an
`AzureAISearchTool` configured with `AzureAISearchQueryType.VECTOR_SEMANTIC_HYBRID`.

### Foundry Skills (versioned behavioral governance)

Three skills ship in `skills/` and are registered via `scripts/register_skills.py`:

| Skill | File | Purpose |
|---|---|---|
| `eciq-readiness-rubric` | `skills/eciq-readiness-rubric/SKILL.md` | Governs how readiness verdicts are evaluated |
| `eciq-safety-escalation` | `skills/eciq-safety-escalation/SKILL.md` | Escalation protocol for safety-flagged content |
| `eciq-citation-policy` | `skills/eciq-citation-policy/SKILL.md` | Citation-or-drop enforcement for grounded outputs |

Skills are registered with the `Foundry-Features: Skills=V1Preview` header and pin the behavioral
contract to a versioned SHA, decoupled from prompt edits.

### How our Foundry deployment compares

| Aspect | EnterpriseCertIQ | CertForge (reference) |
|---|---|---|
| Agent registration | `PromptAgentDefinition` via `register_agents_cloud_shell.py` | `agent.yaml` + Bicep IaC |
| Provisioning | `azd up` (azure.yaml) | `azd up` (azure.yaml + Bicep) |
| Invocation path | Responses API (`FOUNDRY_USE_RESPONSES_API=true`) in FastAPI | Standalone HTTP server port 8088 |
| Search | VECTOR_SEMANTIC_HYBRID | Foundry IQ (default) |
| Skills | 3 versioned Foundry Skills | — |
| Model | `gpt-4.1` (Foundry) | `gpt-oss-120b` (Canada Central) |

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Backend status |
| `GET` | `/api/learners` | List synthetic learners |
| `GET` | `/api/learners/{id}` | Get one learner |
| `GET` | `/api/teams` | List teams |
| `POST` | `/api/workflow/run` | Start 9-agent pipeline → returns `run_id` |
| `GET` | `/api/workflow/{run_id}/stream` | SSE stream of trace events |
| `GET` | `/api/workflow/{run_id}/trace` | Full trace from storage |
| `POST` | `/api/plans/approve` | **HITL gate** — approve a draft plan |
| `GET` | `/api/mastery/{lid}/{cid}` | Domain mastery breakdown |
| `GET` | `/api/forecast/{lid}/{cid}` | Readiness forecast |
| `GET` | `/api/progress/{lid}/{cid}` | Assessment history and plan progress |
| `POST` | `/api/assessment/generate` | Generate mock exam |
| `POST` | `/api/assessment/submit` | Score exam + update forecast; returns `booking_verdict` (GO / CONDITIONAL_GO / NOT_YET) |
| `GET` | `/api/manager/{team_id}/insights` | Team Work IQ + Fabric IQ insights, readiness/risk summary, **ROI cost-of-delay** |
| `POST` | `/api/manager/{team_id}/what-if` | Counterfactual intervention simulator |
| `GET/POST/DELETE` | `/api/manager/{team_id}/peer-sessions` | Persisted peer-learning queue |
| `GET/POST/DELETE` | `/api/manager/{team_id}/interventions` | Persisted manager intervention queue |
| `GET` | `/api/reports/learner/{lid}/{cid}.pdf` | Learner readiness PDF (demo-cached) |
| `GET` | `/api/reports/manager/{team_id}.pdf` | Manager handoff brief PDF (demo-cached) |
| `GET` | `/api/audio/concepts/{lid}/{cid}` | Concepts available for a grounded podcast |
| `GET` | `/api/audio/learner/{lid}/{cid}/transcript` | Grounded podcast transcript + citations (`?focus=weakest\|overview\|<concept>`) |
| `GET` | `/api/audio/learner/{lid}/{cid}.mp3` | Synthesized podcast (Azure AI Speech; 503 if unconfigured) |
| `GET` | `/api/cache/stats` | LLM response-cache hit/miss/entry counters |
| `GET` | `/api/cert-structures/{cert_id}` | Cert domain structure |
| `GET` | `/docs` | Interactive Swagger UI |

---

## Manager workflow

The Manager view supports a full follow-through loop:

- `Needs action now` cards pin into a persisted intervention queue.
- Peer-learning recommendations pin into a persisted session queue.
- Both queues track `owner`, `status`, `manager_note`, and update timestamps.
- **ROI cost-of-delay** — each insight includes `monthly_delay_cost_usd` =
  `at_risk_headcount × cert_market_value_uplift / 12`. Judges and managers see the business
  cost of inaction in dollars, not just risk labels.
- **Auto-alert on consecutive NOT_YET** — if a learner submits two consecutive failed
  assessments for the same cert, the system auto-creates a `high`-priority manager
  intervention (`trigger: "consecutive_not_yet"`) without requiring manual triage.
- The page can copy a manager handoff brief summarising readiness, recommended actions,
  pinned interventions, and pinned peer sessions.
- Peer-learning supports same-cert mentoring first, then a cross-cert study-habit fallback
  when a team has no same-cert coach available (makes TEAM-B usable when cert targets differ).

---

## Assessment & booking verdict

`POST /api/assessment/submit` returns a `booking_verdict` field:

| Verdict | Condition |
|---|---|
| **GO** | `readiness_verdict == "ready"` AND `P(pass) ≥ 0.72` |
| **CONDITIONAL_GO** | `P(pass) ≥ 0.50` |
| **NOT_YET** | `P(pass) < 0.50` OR `readiness_verdict == "insufficient_evidence"` |

The thresholds are calibrated against the LOO AUC 0.802 / Brier 0.183 readiness model
(`backend/evals/readiness_model.py`). The same vocabulary is used by CertForge and CertPathAI.

---

## Testing

```bash
source .venv/bin/activate
pytest -q                  # 90 tests, no credentials needed
```

Regression coverage includes:

- manager insights enriched payload keys (including ROI cost-of-delay)
- peer-session create/update/delete flow
- manager intervention create/update/delete + consecutive NOT_YET auto-alert
- booking_verdict thresholds (GO / CONDITIONAL_GO / NOT_YET)
- Fabric IQ semantic layer (thresholds, readiness semantics, team skill-gap, cohort)
- rubric-based agent-quality evals (per-agent E-checks, 0.8 threshold; booking_verdict rubric A5)
- LLM response cache (key determinism, round-trip, stats)
- Azure Content Safety guardrail (regex fallback + pipeline withholding)
- PDF report generation + demo cache

### Eval artifacts (inspectable without running)

| File | Contents |
|---|---|
| `eval/redteam.json` | 16 adversarial probe cases, 5 attack categories, 0% ASR |
| `eval/scorecard.json` | Aggregated quality metrics: 90 tests, 7-agent rubric scores, AUC 0.802, Brier 0.183 |

Judges can read these files directly without credentials or a running backend.

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

# Register Foundry Hosted Agents (requires Azure auth)
python scripts/register_agents_cloud_shell.py

# Register / list Foundry Skills
python scripts/register_skills.py --list
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
├── azure.yaml                 ← Azure Developer CLI manifest (azd up)
├── .env.example               ← config template
├── requirements.txt
├── config/
│   └── settings.py            ← Pydantic settings, LOCAL/Azure toggle
├── backend/
│   ├── main.py                ← FastAPI app + all routes
│   ├── agents/
│   │   └── factory.py         ← builds all 9 agents with tool executors
│   ├── core/
│   │   ├── agent.py           ← BaseAgent (tool-call loop, trace events)
│   │   ├── client.py          ← model client factory
│   │   ├── mcp_client.py      ← MCP HTTP client
│   │   └── workflow.py        ← 9-agent orchestrator (Stage 5∥6a via asyncio.gather)
│   ├── mcp_server/
│   │   └── server.py          ← FastMCP server (10 typed tools, incl. LRA allocator)
│   ├── middleware/
│   │   └── pipeline.py        ← PII · citation-gate · safety · bias-audit
│   ├── iq/
│   │   ├── foundry_iq.py      ← grounded retrieval (local / VECTOR_SEMANTIC_HYBRID)
│   │   ├── work_iq.py         ← work-context signals (synthetic or MS Graph)
│   │   └── fabric_iq.py       ← semantic ontology (roles, certs, domains, thresholds, cohort)
│   ├── evals/
│   │   ├── readiness_model.py ← calibrated P(pass), booking_verdict, LOO AUC 0.802
│   │   └── agent_rubrics.py   ← per-agent quality rubric harness
│   ├── storage/
│   │   └── store.py           ← JSON local / Cosmos DB abstraction
│   ├── models/                ← Pydantic schemas (incl. booking_verdict on AssessmentOutput)
│   └── data/
│       ├── synthetic/         ← learners, teams, certs, cohort data (all synthetic)
│       └── documents/         ← cert guide, team report (synthetic docs)
├── skills/
│   ├── eciq-readiness-rubric/ ← Foundry Skill: readiness evaluation governance
│   ├── eciq-safety-escalation/← Foundry Skill: safety escalation protocol
│   └── eciq-citation-policy/  ← Foundry Skill: citation-or-drop enforcement
├── eval/
│   ├── redteam.json           ← 16-case adversarial probe suite (0% ASR)
│   └── scorecard.json         ← aggregated quality metrics (inspectable by judges)
├── scripts/
│   ├── setup_foundry.py       ← model download + smoke-test
│   ├── register_agents_cloud_shell.py ← register 9 Hosted Agents on Azure AI Foundry
│   └── register_skills.py     ← register / list 3 Foundry Skills
├── frontend/
│   └── src/
│       ├── pages/             ← LearnerView, ManagerView
│       └── components/        ← ReasoningPanel, CriticVsPlanView, DeviationGraph,
│                                 DomainMasteryChart, ServiceHeatmap,
│                                 PassThresholdGauge, HITLApprovalGate,
│                                 AIDisclosureBanner
├── prompts/                   ← versioned agent prompts (v1.md per agent)
└── docs/
    ├── adr/                   ← Architecture Decision Records
    ├── deployment.md          ← Azure Container Apps + azd up guide
    ├── foundry-hosted-agents.md ← Hosted Agent registration + Skills deep-dive
    └── work-iq-graph.md       ← Microsoft Graph Calendars.Read integration
```

---

## Responsible AI

- Every generated artifact carries an **"AI-generated"** disclosure banner (RAI requirement).
- **HITL gate**: study plans require human approval before publishing.
- **Azure AI Content Safety**: free-text output is screened by the live Content Safety API
  (Hate/SelfHarm/Sexual/Violence; severity ≥ threshold → BLOCK), with a regex fallback offline.
- **Bias audit**: middleware scans generated assessment questions for stereotypes.
- **Citation-or-drop**: uncited claims are flagged, never silently passed through (enforced by
  `eciq-citation-policy` Foundry Skill).
- **Honest uncertainty**: the Readiness Critic returns `insufficient_evidence: true` rather
  than fabricating a forecast. Assessment returns `NOT_YET` (not a fabricated `GO`) when
  evidence is insufficient.
- Manager Insights never exposes individual scores that could affect employment decisions
  (enforced and unit-tested via the agent rubric harness).

---

## Reliability & performance

- **LLM response cache** (`backend/core/llm_cache.py`) — SHA-256 keyed over the request;
  deterministic (temperature-0) calls hit the cache and skip the model entirely. Cuts cost +
  latency and makes demo re-runs instant. Hit-rate visible at `/api/cache/stats` and `/health`.
- **Parallel execution** (`asyncio.gather`) — Stage 5 (Engagement) and Stage 6a (Readiness
  Forecast) have independent inputs and run in parallel, cutting end-to-end latency by ~40%.
- **Largest Remainder Algorithm** (`backend/mcp_server/server.py`) — LRA allocates study hours
  across topics as fair integers, preventing starvation (every topic ≥ 0.5 h).
- **Rubric-based agent evals** (`backend/evals/agent_rubrics.py`) — per-agent quality checks
  with a 0.8 pass threshold, including booking_verdict rubric (A5). Run in CI with no credentials.
- **PDF reports** (`backend/reports/pdf.py`) — learner readiness + manager handoff brief,
  demo-cached for instant repeat downloads.
- **Grounded learning podcast** (`backend/audio/podcast.py`) — a NotebookLM-style
  **two-host podcast** generated *only* from approved cert content, with the transcript +
  citations shown for provenance. Deep-teaches the learner's weakest concept by default
  (resolved via Fabric IQ readiness semantics); learner can pick any concept or a full exam
  overview. Two-voice SSML → Azure AI Speech (REST); transcript works with no key.
- **Deterministic tier-3 fallback** (`backend/agents/fallbacks.py`) — every agent has a
  no-model deterministic builder. `AGENT_FALLBACK_MODE=force` runs the **entire pipeline
  with zero model calls** (instant, reproducible demo mode). Fallback outputs pass the same
  quality rubrics.
- **9 certification families** — `AZ-204/305/400`, `DP-203/100`, `AI-102/900`, `SC-100`,
  `MS-102` — fully data-driven from `cert_structures.json`.
- **Containerised deploy** — see [docs/deployment.md](docs/deployment.md) (Azure Container Apps + `azd up`).

---

## Microsoft technology stack

| Component | Role |
|---|---|
| Azure AI Foundry | 9 Hosted Agents, `gpt-4.1` model, Skills registry |
| Azure AI Projects SDK | `AIProjectClient`, `PromptAgentDefinition`, Responses API |
| Azure Developer CLI (azd) | `azd up` one-command provisioning via `azure.yaml` |
| Azure AI Search | VECTOR_SEMANTIC_HYBRID grounded retrieval for 3 agents |
| Foundry Skills | 3 versioned skills (readiness-rubric, safety-escalation, citation-policy) |
| Foundry Local SDK | On-device model inference (dev) |
| Microsoft Learn MCP | `microsoft_docs_search`, `microsoft_docs_fetch`, `microsoft_code_sample_search` |
| Work IQ / Microsoft Graph | Real `Calendars.Read` (or synthetic fallback) |
| Fabric IQ | Semantic ontology — roles, certs, weighted domains, thresholds, cohort |
| Azure AI Content Safety | Live output screening (regex fallback offline) |
| Azure AI Evaluation | Groundedness LLM-as-judge (Azure path) |
| Azure AI Speech | Two-voice TTS for the grounded audio study briefing |
| Application Insights | OpenTelemetry traces (`ENABLE_TELEMETRY=true`) |
| Azure Cosmos DB | Production storage (local JSON in dev) |
| FastMCP | Own MCP server exposing 10 typed tools (incl. LRA allocator, Fabric IQ semantics) |
| ReportLab | Learner + manager PDF report generation |

---

*Synthetic data only. No real PII. Built for Microsoft Agents League 2026.*
