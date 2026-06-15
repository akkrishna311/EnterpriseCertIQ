# EnterpriseCertIQ — Technical Design Document

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Project Structure](#3-project-structure)
4. [Configuration System](#4-configuration-system)
5. [Agent Pipeline](#5-agent-pipeline)
   - 5.1 [Orchestration Flow](#51-orchestration-flow)
   - 5.2 [BaseAgent](#52-baseagent)
   - 5.3 [Agent Factory](#53-agent-factory)
   - 5.4 [Individual Agents](#54-individual-agents)
6. [The Three IQ Layers](#6-the-three-iq-layers)
   - 6.1 [Foundry IQ — Knowledge Retrieval](#61-foundry-iq--knowledge-retrieval)
   - 6.2 [Work IQ — Work-Context Signals](#62-work-iq--work-context-signals)
   - 6.3 [Fabric IQ — Semantic Layer / Ontology](#63-fabric-iq--semantic-layer--ontology)
7. [MCP Tools](#7-mcp-tools)
8. [Pipeline Middleware & RAI](#8-pipeline-middleware--rai)
9. [Storage Layer](#9-storage-layer)
10. [Evaluation & Readiness Model](#10-evaluation--readiness-model)
11. [Azure AI Foundry Integration](#11-azure-ai-foundry-integration)
12. [Hosted Agent](#12-hosted-agent)
13. [Observability & Telemetry](#13-observability--telemetry)
14. [API Surface](#14-api-surface)
15. [Deployment Modes](#15-deployment-modes)
16. [Key Design Decisions](#16-key-design-decisions)

---

## 1. System Overview

EnterpriseCertIQ is an enterprise-scale, multi-agent AI system for certification learning. It integrates Microsoft's **Three IQ** framework — Foundry IQ (knowledge retrieval), Work IQ (work-context signals), and Fabric IQ (semantic ontology) — to deliver personalized, capacity-aware learning plans with calibrated readiness forecasting and manager-level workforce insights.

**Default runtime is local-first.** All `settings.py` defaults point to the local stack — `MODEL_BACKEND=foundry_local`, `STORAGE_BACKEND=local`, `WORK_IQ_SOURCE=synthetic`, `FABRIC_IQ_ENDPOINT=local`. The Azure and Hosted Agent paths are opt-in by setting the appropriate env vars.

**Runtime modes:**

Application data (plans, traces, assessments) is always persisted to local JSON files. The table below describes the **knowledge grounding sources** that change across modes.

| Mode | Model Backend | Foundry IQ grounding | Fabric IQ | Work IQ | Default? |
|---|---|---|---|---|---|
| **Local dev** | `foundry_local` | TF-IDF over `./data/documents/` | Synthetic JSON ontology | Synthetic seed data | **Yes** |
| Cloud — direct path | `azure_foundry` | Azure AI Search via direct httpx (`FOUNDRY_IQ_ENDPOINT`) | Local ontology fallback or Fabric SQL | Microsoft Graph (opt-in) | No |
| Cloud — Responses API | `azure_foundry` + `FOUNDRY_USE_RESPONSES_API=true` | Server-side Azure AI Search KB via MCPTool on registered Foundry agents (`eciq-learning-path-curator`, `eciq-readiness-critic`, `eciq-assessment-agent`) | Fabric IQ KB (`eciq-study-plan-generator`, `eciq-manager-insights`) + Fabric ontology endpoint | Microsoft Graph (opt-in) | No |
| Hosted Agent | `azure_foundry` container | Same as Cloud — Responses API, configured via `ECIQ_*` env vars | Same as Cloud — Responses API | Synthetic (no Graph in container) | No |

**Three execution tiers (no single point of failure):**

- **Tier 1** — LLM call with SHA-256 response cache
- **Tier 2** — Transient retry via `tenacity` (3 attempts, exponential back-off)
- **Tier 3** — Deterministic Python fallback (`backend/agents/fallbacks.py`); zero network calls

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        React Dashboard (port 5173)                   │
│            SSE stream  ·  REST calls  ·  HITL approval UI            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP / SSE
┌──────────────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend  (port 8000)                        │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                  WorkflowOrchestrator                          │  │
│  │                                                                │  │
│  │  [Intake] → [Curator] → [Planner] ↔ [Critic loop (×2)] →     │  │
│  │  HITL gate →                                                   │  │
│  │  [Engagement ∥ Readiness Forecast] → [Assessment] →           │  │
│  │  [Manager Insights] → [Retrospective?]                        │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │  Foundry IQ  │  │   Work IQ    │  │       Fabric IQ           │   │
│  │  (retrieval) │  │ (schedule)   │  │   (semantic ontology)     │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │  MCP Server  │  │  Middleware  │  │  Evaluation / RAI         │   │
│  │  (port 8001) │  │  (pipeline)  │  │  (rubrics + model)        │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                 │                          │
        ┌────────▼────────┐      ┌──────────▼──────────┐
        │ Azure AI Foundry│      │  Azure AI Search      │
        │ (model + agents │      │  (Foundry IQ index)   │
        │  + Tracing)     │      └──────────────────────┘
        └────────┬────────┘
                 │
        ┌────────▼────────────────────┐
        │  Fabric Lakehouse / SQL     │
        │  (Fabric IQ ontology)       │
        └─────────────────────────────┘

Hosted Agent path (Foundry Hosted Agent Service):
┌────────────────────────────────────────────────┐
│  ACR → eciqregistry.azurecr.io                  │
│  Container: Dockerfile.hosted (port 8088)        │
│  Entry: hosted/main.py (Responses API contract) │
│  Delegates to same WorkflowOrchestrator          │
└────────────────────────────────────────────────┘
```

---

## 3. Project Structure

```
EnterpriseCertIQ/
├── backend/
│   ├── main.py                        # FastAPI app: REST + SSE endpoints
│   ├── agents/
│   │   ├── factory.py                 # Build all 9 agents (8 pipeline + orchestrator); wire tools + prompts
│   │   └── fallbacks.py               # Tier-3 deterministic builders (no LLM)
│   ├── core/
│   │   ├── agent.py                   # BaseAgent: tool-call loop, cache, retry
│   │   ├── client.py                  # OpenAI client manager, model selection
│   │   ├── workflow.py                # WorkflowOrchestrator: 9-agent pipeline DAG
│   │   ├── foundry_orchestration.py   # Azure AI Foundry agent registration + sessions
│   │   ├── foundry_grounded_agent.py  # Responses API native grounded calls
│   │   ├── fabric_iq_agent.py         # Fabric IQ on-behalf-of agent caller
│   │   ├── telemetry.py               # OpenTelemetry spans → App Insights
│   │   ├── llm_cache.py               # SHA-256 keyed LLM response cache
│   │   ├── mcp_client.py              # HTTP clients for Learn MCP + own MCP
│   │   └── azure_credentials.py       # Multi-tenant Entra auth
│   ├── iq/
│   │   ├── foundry_iq.py              # Grounded knowledge retrieval
│   │   ├── fabric_iq.py               # Semantic ontology layer
│   │   ├── work_iq.py                 # Work-context signals (synthetic)
│   │   └── work_iq_graph.py           # Microsoft Graph calendar integration
│   ├── mcp_server/
│   │   ├── server.py                  # FastMCP: 10 typed tools
│   │   └── __main__.py                # Standalone MCP server entry
│   ├── models/
│   │   ├── agent_outputs.py           # Structured output schemas
│   │   ├── learner.py                 # LearnerProfile, WorkIQSignals, PriorAttempt
│   │   ├── plan.py                    # StudyPlan, StudyWeek, Citation
│   │   ├── assessment.py              # AssessmentQuestion, submitted answers
│   │   ├── mastery.py                 # Domain mastery breakdown
│   │   ├── audio.py                   # PodcastScript (two-host briefing)
│   │   └── trace.py                   # TraceEvent, ReasoningTrace
│   ├── middleware/
│   │   ├── pipeline.py                # PII redaction, citation gate, bias audit
│   │   ├── content_safety.py          # Azure AI Content Safety + regex fallback
│   │   └── red_team.py                # Input/output jailbreak screening
│   ├── evals/
│   │   ├── agent_rubrics.py           # Deterministic quality checks
│   │   ├── groundedness.py            # LLM-as-judge citation coverage
│   │   └── readiness_model.py         # Calibrated logistic regression forecaster
│   ├── audio/
│   │   └── podcast.py                 # Azure AI Speech TTS synthesis
│   ├── reports/
│   │   └── pdf.py                     # PDF report generation (reportlab)
│   ├── storage/
│   │   └── store.py                   # Local JSON persistence (AppStorage / LocalJSONStore)
│   └── data/
│       ├── synthetic/                 # learners.json, teams.json, cohort_outcomes.json
│       ├── documents/                 # Foundry IQ knowledge base (local mode)
│       ├── eval/                      # agent_eval_dataset.jsonl, eval_dataset.jsonl
│       ├── fabric_export/             # Fabric IQ CSV exports (domain weights, ontology)
│       └── store/                     # Persisted plans, traces, assessments
├── config/
│   ├── settings.py                    # Pydantic BaseSettings (env-driven)
│   └── key_vault.py                   # Azure Key Vault secret loading
├── prompts/                           # System prompts for all 9 agents (v1.md)
│   ├── learner_intake/v1.md
│   ├── curator/v1.md
│   ├── plan_generator/v1.md
│   ├── readiness_critic/v1.md
│   ├── assessment/v1.md
│   ├── engagement/v1.md
│   ├── manager_insights/v1.md
│   ├── retrospective/v1.md
│   └── audio_curriculum/v1.md
├── hosted/
│   └── main.py                        # Hosted Agent entry (port 8088)
├── frontend/src/                      # React dashboard
├── scripts/                           # Deployment and data ingestion utilities
├── tests/                             # 13 test modules
├── Dockerfile                         # Backend image (port 8000)
├── Dockerfile.hosted                  # Hosted Agent image (port 8088)
├── requirements.txt                   # Core dependencies
├── requirements.azure.txt             # Azure SDK additions
├── requirements.hosted.txt            # Hosted Agent minimal dependencies
└── azure.yaml                         # Azure Developer CLI manifest
```

---

## 4. Configuration System

**File:** [config/settings.py](../config/settings.py)

All configuration is environment-driven via `pydantic-settings BaseSettings`. Values are read from `.env.local` → `.env.azure` → `.env` → environment variables.

### Backend Selection

```
MODEL_BACKEND   foundry_local | azure_foundry
STORAGE_BACKEND local | cosmos
```

### Azure AI Foundry (cloud inference)

| Variable | Description |
|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | Hub endpoint (agents SDK) |
| `AZURE_OPENAI_ENDPOINT` | OpenAI-compatible v1 endpoint for inference |
| `AZURE_AI_API_KEY` | Leave empty → `DefaultAzureCredential` |
| `AZURE_AI_MODEL_DEPLOYMENT` | Deployment name (e.g. `gpt-4.1`) |
| `AZURE_AI_REASONING_DEPLOYMENT` | Separate reasoning model deployment |
| `AZURE_USE_MANAGED_IDENTITY` | `True` → force `DefaultAzureCredential` |

### Foundry IQ (Knowledge Retrieval)

| Variable | Description |
|---|---|
| `FOUNDRY_IQ_ENDPOINT` | `local` (TF-IDF over `./data/documents/`) or Azure AI Search URL |
| `FOUNDRY_IQ_INDEX_NAME` | Azure AI Search index name |
| `AZURE_SEARCH_KEY` | Dedicated Search key (fallback to model key) |
| `FOUNDRY_SEARCH_CONNECTION_NAME` | Foundry portal connection name for native `AzureAISearchTool` |
| `FOUNDRY_USE_RESPONSES_API` | `true` → curator/critic/assessment use Foundry Responses API for server-side grounding |
| `FOUNDRY_AUTO_REGISTER` | `false` (default) → use `register_agents_cloud_shell.py` instead of startup auto-registration |

### Fabric IQ (Semantic Layer)

| Variable | Description |
|---|---|
| `FABRIC_IQ_ENDPOINT` | `local` (synthetic JSON) or Azure Fabric workspace endpoint |
| `FABRIC_SQL_ENDPOINT` / `FABRIC_SQL_DATABASE` | SKU-free Lakehouse SQL analytics endpoint (works on Fabric Trial) |
| `FABRIC_IQ_AGENT_NAME` | Foundry agent with Fabric IQ (OneLake Catalog) tool — used for on-behalf-of calls |
| `FABRIC_TENANT_ID`, `FABRIC_CLIENT_ID`, `FABRIC_CLIENT_SECRET` | Multi-account: Fabric can live in a different Entra tenant |

### Work IQ (Capacity Signals)

| Variable | Description |
|---|---|
| `WORK_IQ_SOURCE` | `synthetic` (seed data) or `graph` (Microsoft Graph Calendars.Read) |
| `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_ACCESS_TOKEN` | Graph authentication |
| `GRAPH_LEARNER_UPN_MAP` | JSON map `{"L-1004": "alex@contoso.com"}` for per-learner mailbox routing |

### Hosted Agent Aliases

The Foundry platform reserves `FOUNDRY_*` and `AGENT_*` env var prefixes. The hosted container receives these under `ECIQ_*` instead. A `model_validator` in `settings.py` transparently maps them:

```python
@model_validator(mode="after")
def _apply_eciq_overrides(self) -> "Settings":
    eciq_endpoint = os.environ.get("ECIQ_IQ_ENDPOINT")
    if eciq_endpoint:
        self.foundry_iq_endpoint = eciq_endpoint
    # also ECIQ_IQ_INDEX_NAME → foundry_iq_index_name
    # also ECIQ_USE_RESPONSES_API → foundry_use_responses_api
```

Local `.env.local` using `FOUNDRY_*` names is completely unaffected (ECIQ vars absent → validator is a no-op).

### Reliability & Caching

| Variable | Default | Description |
|---|---|---|
| `AGENT_FALLBACK_MODE` | `auto` | `auto` → deterministic fallback on model error; `force` → skip model entirely; `off` → surface errors |
| `ENABLE_LLM_CACHE` | `true` | SHA-256 cache skips duplicate model calls |
| `LLM_CACHE_MAX_ENTRIES` | `2000` | Max in-memory cached entries |

### RAI & Telemetry

| Variable | Description |
|---|---|
| `AZURE_CONTENT_SAFETY_ENDPOINT` + `_KEY` | Live Content Safety API (falls back to regex) |
| `AZURE_CONTENT_SAFETY_THRESHOLD` | Severity 0–6 (default 2 = medium) |
| `ENABLE_TELEMETRY` | `false` (local console) / `true` + `APPLICATIONINSIGHTS_CONNECTION_STRING` |

### Audio

| Variable | Description |
|---|---|
| `SPEECH_KEY` + `SPEECH_REGION` | Azure AI Speech TTS |
| `AUDIO_VOICE_HOST_A` / `_HOST_B` | Neural voice names (default: `AvaNeural`, `AndrewNeural`) |

### Azure Key Vault (cloud secret store)

**File:** [config/key_vault.py](../config/key_vault.py)

When `AZURE_KEY_VAULT_URL` is set, `load_key_vault_secrets()` is called at startup (before telemetry or model init) and overwrites the matching `Settings` fields in place. This makes Key Vault the source of truth for all sensitive credentials in cloud without touching the env var plumbing.

**Behaviour:**
- No-op when `AZURE_KEY_VAULT_URL` is empty — local dev and CI stay offline and credential-free.
- Never raises on failure: vault outage → warning logged, startup continues with env values.
- On `ClientAuthenticationError` (no `az login`, no managed identity): stops early rather than retrying every secret.
- After loading, each value is also mirrored into `os.environ[UPPER_NAME]` so SDK clients that read env vars directly pick up the same values.

**Auth resolution order** (via `DefaultAzureCredential`):
1. `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` / `AZURE_TENANT_ID` (service principal)
2. Managed identity (Azure Container Apps / App Service)
3. `az login` (local developer)

**Secret name mapping** (Key Vault secret name → `Settings` field → env var):

| Key Vault secret | Settings field | Env var |
|---|---|---|
| `azure-ai-api-key` | `azure_ai_api_key` | `AZURE_AI_API_KEY` |
| `azure-search-key` | `azure_search_key` | `AZURE_SEARCH_KEY` |
| `azure-content-safety-key` | `azure_content_safety_key` | `AZURE_CONTENT_SAFETY_KEY` |
| `graph-access-token` | `graph_access_token` | `GRAPH_ACCESS_TOKEN` |
| `appinsights-connection-string` | `applicationinsights_connection_string` | `APPLICATIONINSIGHTS_CONNECTION_STRING` |
| `speech-key` | `speech_key` | `SPEECH_KEY` |

Key Vault uses hyphens in secret names (underscores are not allowed); the mapping above handles the translation. Secrets not present in the vault are silently skipped — the env var fallback applies.

---

## 5. Agent Pipeline

### 5.1 Orchestration Flow

**File:** [backend/core/workflow.py](../backend/core/workflow.py)

The `WorkflowOrchestrator` runs agents as a **sequential spine** with one point of parallelism, bounded loops, a HITL gate, and a conditional retrospective. There is no multi-domain curator fan-out — the curator runs once per workflow. The only concurrent execution is at the Engagement + Readiness Forecast stage.

```
LEARNER INPUT (LearnerProfile)
         │
         ▼
┌────────────────────────────────────────────────────────────────────┐
│  Stage 1: LEARNER INTAKE                                            │
│  Parse + validate profile; extract Work IQ signals; flag risks      │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│  Stage 2: LEARNING PATH CURATOR                                     │
│  Map cert → skill topics; retrieve from Foundry IQ + MS Learn;     │
│  citation-or-drop on every recommendation                           │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│  Stage 3: STUDY PLAN GENERATOR                                      │
│  Convert topics → capacity-aware weekly schedule (LRA allocation)   │
│  → canonical plan via generate_study_plan.fn() every time           │
└────────────────────────────┬───────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │      CRITIC LOOP (max 2 rounds)        │
         │                                        │
         ▼                                        │
┌─────────────────────┐                           │
│ READINESS CRITIC    │    red objections?         │
│ weighted by domain  │──── YES ──────────────────┤
│ leverage (Fabric IQ)│                           │
└──────┬──────────────┘         revise plan       │
       │ no red objections                        │
       │ (or round 2 exhausted)                   │
       ▼                                          │
┌────────────────────────────────────────────────────────────────────┐
│  HITL GATE                                                          │
│  Plan status = DRAFT — not published until /api/plans/approve       │
│  Engagement + Manager outputs are advisory previews                 │
└────────────────────────────┬───────────────────────────────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          │  asyncio.gather() — only parallel   │
          │  point in the pipeline              │
          ▼                                     ▼
┌───────────────────┐               ┌────────────────────────┐
│  ENGAGEMENT AGENT │               │  READINESS FORECAST     │
│  Work IQ slots,   │               │  (MCP tool, deterministic│
│  capacity blocks  │               │   calibrated P(pass))   │
└────────┬──────────┘               └────────────┬───────────┘
         │                                       │
         └──────────────────┬────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────────┐
│  Stage 6b: ASSESSMENT AGENT                                         │
│  Grounded practice questions; narrative readiness verdict;          │
│  next-step cert recommendation grounded via foundry_iq_search       │
└────────────────────────────┬───────────────────────────────────────┘
                             │
          ┌──────────────────┴─────────────────────────┐
          │  READINESS DECISION (deterministic)          │
          │  from calibrated forecast, not LLM variance  │
          ├─── ready   → ADVANCE: emit READINESS_ADVANCE  │
          ├─── not_ready → REMEDIATE: one focused re-plan │
          └─── insufficient → GATHER EVIDENCE              │
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│  Stage 7: MANAGER INSIGHTS                                          │
│  Team readiness, capacity risk, peer-learning pairs                 │
│  Cohort benchmarks + intervention effectiveness from Fabric IQ      │
└────────────────────────────┬───────────────────────────────────────┘
                             │
           [if learner.has_prior_failures]
                             │
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│  Stage 8: RETROSPECTIVE                                             │
│  Root-cause analysis on prior failures; recovery recommendations    │
└────────────────────────────┬───────────────────────────────────────┘
                             │
                             ▼
                   WORKFLOW_COMPLETE
                   (trace persisted; status = hitl_pending)
```

**Trace events** are emitted at every stage transition and tool call. They stream live to the frontend via SSE and are persisted to storage so the trace survives page reloads.

### 5.2 BaseAgent

**File:** [backend/core/agent.py](../backend/core/agent.py)

`BaseAgent` is a thin wrapper over `openai.AsyncOpenAI` that handles:

- **Tool-call loop** — submits messages, receives tool calls, dispatches via registered executors, and resubmits until the model returns a plain response (or `max_tool_rounds` is exhausted)
- **Structured output parsing** — resolves JSON from `response_format` (Pydantic schema) or extracts from code-fenced blocks
- **`<think>` stripping** — removes chain-of-thought tags from reasoning models (phi-4-reasoning, DeepSeek-R1) before JSON parsing
- **Trace event emission** — emits `AGENT_START`, `TOOL_CALL`, `TOOL_RESULT`, `AGENT_COMPLETE` via `on_event` callback
- **Middleware** — calls `apply_pipeline()` on the final response (PII, citation gate, safety)
- **Bounded retry** — `tenacity` with 3 attempts and exponential back-off for transient model errors
- **Tier-3 fallback** — when `supports_fallback=True` and the model errors or `AGENT_FALLBACK_MODE=force`, delegates to `backend/agents/fallbacks.py`

```python
class AgentResult(BaseModel):
    agent_name: str
    content: str
    parsed: Optional[Any] = None        # Pydantic model if response_format set
    tool_calls_made: list[dict] = []
    token_usage: dict = {}
```

### 5.3 Agent Factory

**File:** [backend/agents/factory.py](../backend/agents/factory.py)

`build_agents()` constructs all 9 agents: 8 pipeline agents (Intake → Curator → Planner → Critic →
Engagement → Assessment → Manager → Retrospective) plus the **Orchestrator** registered as the
top-level Foundry Hosted Agent (`eciq-orchestrator`). The Orchestrator coordinates the pipeline
from outside; the 8 pipeline agents are the reasoning workers. Each agent is built by:

1. Loading its system prompt from `prompts/{dir}/v1.md`
2. Selecting the appropriate tool subset from `_OWN_TOOLS` + `_LEARN_TOOLS`
3. Setting `model_role` (`default` or `reasoning`), `temperature`, and `response_format`
4. Registering tool executors for all MCP tools

Tool execution is **in-process** for own tools (direct `await fn()`) and **HTTP** for Microsoft Learn MCP tools.

A separate `build_audio_agent()` function constructs the standalone audio briefing agent on demand.

### 5.4 Individual Agents

#### Learner Intake Agent

| Property | Value |
|---|---|
| Name | `learner_intake` |
| Prompt | [prompts/learner_intake/v1.md](../prompts/learner_intake/v1.md) |
| Tools | `parse_learner_profile` |
| Model role | `default` |
| Temperature | `0.3` |
| Response format | unstructured text |

Parses and validates the `LearnerProfile` JSON. Extracts capacity risk signals, confirms all critical fields, and surfaces `warnings` for downstream agents. The workflow then independently emits Work IQ signals as a trace event after intake completes.

---

#### Learning Path Curator Agent

| Property | Value |
|---|---|
| Name | `curator` |
| Prompt | [prompts/curator/v1.md](../prompts/curator/v1.md) |
| Tools | `foundry_iq_search`, `validate_citation`, `microsoft_docs_search`, `microsoft_docs_fetch`, `microsoft_code_sample_search` |
| Model role | `default` |
| Temperature | `0.1` |
| Response format | `CuratedTopicList` |
| Max tool rounds | `4` |

Maps the learner's certification target to skill topics. Every topic recommendation **must** cite a source from Foundry IQ or Microsoft Learn. The **citation-or-drop** rule prohibits fabricated sources: if no source is found, the agent states "No governing source found" rather than inventing content.

When `FOUNDRY_USE_RESPONSES_API=true`, the workflow calls `call_grounded_agent("curator", ...)` instead, delegating retrieval and citation injection to the Foundry Responses API.

**Output schema (`CuratedTopicList`):**
```json
[
  {
    "title": "Azure Functions — triggers and bindings",
    "domain": "Develop Azure compute solutions",
    "hours": 2.5,
    "priority": "high",
    "citations": [
      {
        "doc_id": "az204-guide",
        "title": "AZ-204 Learning Path",
        "span_id": "func-001",
        "excerpt": "Azure Functions provide serverless compute...",
        "source_url": "https://learn.microsoft.com/..."
      }
    ],
    "ms_learn_url": "https://learn.microsoft.com/en-us/training/..."
  }
]
```

---

#### Study Plan Generator Agent

| Property | Value |
|---|---|
| Name | `plan_generator` |
| Prompt | [prompts/plan_generator/v1.md](../prompts/plan_generator/v1.md) |
| Tools | `parse_learner_profile`, `foundry_iq_search`, `validate_citation`, `generate_study_plan` |
| Model role | `default` |
| Temperature | `0.0` |
| Response format | `StudyPlan` |

Converts curated topics into a capacity-aware weekly study schedule. The workflow **always** runs the agent result through `generate_study_plan.fn()` afterward — this guarantees the Largest Remainder Algorithm (LRA) is applied for hour allocation regardless of whether the model called the tool directly. This prevents topic starvation when many topics compete for limited weekly hours.

Effective study hours per week are derived conservatively:
```python
max(declared_study_hours, focus_hours / 2, 2.0)
```

**Output schema (`StudyPlan`):**
```json
{
  "plan_id": "plan-abc123",
  "learner_id": "L-1004",
  "cert_id": "AZ-204",
  "status": "draft",
  "deadline": "2026-12-31",
  "total_planned_hours": 24.0,
  "weeks": [
    {
      "week": 1,
      "topics": [
        {
          "topic_id": "topic_01",
          "title": "Azure Functions — triggers",
          "domain": "Develop Azure compute solutions",
          "hours_allocated": 2.5,
          "difficulty": "Medium",
          "citations": [...]
        }
      ],
      "planned_hours": 6.0,
      "notes": "Foundation week"
    }
  ]
}
```

---

#### Readiness Critic Agent

| Property | Value |
|---|---|
| Name | `readiness_critic` |
| Prompt | [prompts/readiness_critic/v1.md](../prompts/readiness_critic/v1.md) |
| Tools | `validate_citation`, `compute_readiness_forecast`, `compute_domain_mastery`, `compute_service_heatmap`, `fabric_iq_semantics` (if model supports tools) |
| Model role | `reasoning` |
| Temperature | `0.0` |
| Response format | `CriticOutput` |

**Attacks the plan** to find where the learner is most likely to fail. Objections are weighted by domain **leverage** (domain weight × mastery gap), not raw gap alone. This ensures high-weight domains receive attention even when the absolute gap is similar to low-weight domains.

Some reasoning models (e.g. phi-4-reasoning) do not support tool-calling. In that case, `model_supports_tools("reasoning")` returns `False` and the agent receives an empty tool list — it reasons over Fabric IQ domain thresholds passed in-context instead.

After the model returns, `_enrich_critic_payload()` backfills any missing `forecast`, `domain_mastery`, or `objections` from the deterministic fallback for display purposes. The loop-control decision still uses the model's own objections.

**Output schema (`CriticOutput`):**
```json
{
  "objections": [
    {
      "objection_id": "O1",
      "plan_element_id": "week_2",
      "severity": "red",
      "description": "Plan allocates only 2h to Networking (25% weight); mastery 0.41 vs target 0.70.",
      "recommendation": "Double Networking to 4h; prioritize Service Bus and Event Grid.",
      "citation": "cert_structures: Domain NET01, weight 25%"
    }
  ],
  "forecast": {...},
  "domain_mastery": {...},
  "overall_risk": "high"
}
```

---

#### Engagement Agent

| Property | Value |
|---|---|
| Name | `engagement` |
| Prompt | [prompts/engagement/v1.md](../prompts/engagement/v1.md) |
| Tools | `compute_progress_series` |
| Model role | `default` |
| Temperature | `0.1` |
| Response format | `EngagementOutput` |

Uses Work IQ signals to recommend realistic study time slots and flag capacity conflicts (sprint reviews, high meeting weeks, upcoming milestones). Runs **concurrently** with the Readiness Forecast — both are launched with `asyncio.gather()` because they have independent inputs.

**Output schema (`EngagementOutput`):**
```json
{
  "employee_id": "L-1004",
  "recommended_study_slots": ["Tuesday 08:00-09:30", "Thursday 08:00-09:30"],
  "blocked_periods": ["Sprint review week of 2026-07-10"],
  "engagement_strategy": "Morning-focused; protect Tue/Thu before meetings start",
  "capacity_risk": "medium",
  "replan_trigger": false
}
```

---

#### Assessment Agent

| Property | Value |
|---|---|
| Name | `assessment` |
| Prompt | [prompts/assessment/v1.md](../prompts/assessment/v1.md) |
| Tools | `foundry_iq_search`, `generate_assessment`, `compute_readiness_forecast` |
| Model role | `default` |
| Temperature | `0.1` |
| Response format | `AssessmentOutput` |
| Max tool rounds | `3` |

Generates grounded, domain-weighted practice questions and evaluates readiness. The **readiness verdict** from this agent is narrative and advisory; the **authoritative readiness decision** that controls loop-back vs. advance comes from `_readiness_from_forecast()` — a deterministic function operating on the calibrated forecast — to prevent model variance from breaking control flow.

**Output schema (`AssessmentOutput`):**
```json
{
  "learner_id": "L-1004",
  "cert_id": "AZ-204",
  "readiness_verdict": "ready",
  "pass_probability": 0.78,
  "estimated_exam_score": 745,
  "pass_threshold": 700,
  "weak_areas": ["Develop Azure compute solutions"],
  "sample_questions": [
    {
      "question_text": "[Synthetic] A developer is deploying Azure Functions...",
      "domain": "Develop Azure compute solutions",
      "citation": "Cert Guide — 'Azure Functions provide serverless compute...'"
    }
  ],
  "recommendation": "advance",
  "next_step": "Recommend AZ-305 as the next certification.",
  "booking_verdict": "GO"
}
```

---

#### Manager Insights Agent

| Property | Value |
|---|---|
| Name | `manager_insights` |
| Prompt | [prompts/manager_insights/v1.md](../prompts/manager_insights/v1.md) |
| Tools | `parse_learner_profile`, `foundry_iq_search`, `fabric_iq_semantics` |
| Model role | `default` |
| Temperature | `0.1` |
| Response format | `ManagerInsightsOutput` |

Aggregates team-level certification readiness, surfaces capacity conflicts, ranks team skill gaps by `coverage × leverage`, and identifies peer-learning pairs (learner A's strength covers learner B's gap). The prompt enforces a strict constraint: **never expose individual scores** that could affect employment decisions.

Uses Fabric IQ `get_cohort_benchmark()` and `get_intervention_effectiveness()` to ground recommendations with data-anchored priors rather than generic advice.

**ROI cost-of-delay**: every insight that surfaces an at-risk learner includes a `monthly_delay_cost_usd` field:

```
monthly_delay_cost_usd = at_risk_headcount × cert_market_value_uplift / 12
```

This converts risk labels into dollar-denominated business impact — managers see the cost of inaction, not just a risk band.

**Consecutive NOT_YET auto-alert**: when a learner submits two consecutive `NOT_YET` booking verdicts for the same certification, the system automatically creates a `high`-priority Manager Intervention record (`trigger: "consecutive_not_yet"`) without requiring manual triage. This is handled in `POST /api/assessment/submit` before the response is returned, and is unit-tested in the test suite.

**Output schema (`ManagerInsightsOutput`):**
```json
{
  "team_id": "team-blue",
  "summary": "Team of 3 targeting AZ-204/AZ-400. 2 members at capacity risk.",
  "readiness_distribution": {"on_track": 1, "at_risk": 1, "insufficient_evidence": 1},
  "capacity_conflicts": ["All 3 members have sprint review 2026-07-10 blocking study"],
  "risk_areas": ["2 learners > 25 meeting hours/week; cohort data shows 35% pass-rate drop"],
  "peer_learning_pairs": [
    {"learner_a": "L-1004", "strength": "compute", "learner_b": "L-1005", "gap": "networking"}
  ],
  "manager_actions": [
    "Protect Tue/Thu mornings for L-1004 and L-1005",
    "Schedule L-1004 to coach L-1005 on networking"
  ]
}
```

---

#### Retrospective Agent

| Property | Value |
|---|---|
| Name | `retrospective` |
| Prompt | [prompts/retrospective/v1.md](../prompts/retrospective/v1.md) |
| Tools | `parse_learner_profile`, `foundry_iq_search`, `validate_citation` |
| Model role | `reasoning` |
| Temperature | `0.0` |
| Response format | unstructured text |

Runs **only when** `learner.has_prior_failures == True`. Investigates whether a prior exam failure was due to retrieval quality, plan quality, engagement gap, or genuine skill gap. Produces a postmortem and recovery recommendations.

---

#### Audio Curriculum Agent (standalone)

| Property | Value |
|---|---|
| Name | `audio_curriculum` |
| Prompt | [prompts/audio_curriculum/v1.md](../prompts/audio_curriculum/v1.md) |
| Tools | `foundry_iq_search`, `fabric_iq_semantics` |
| Model role | `default` |
| Temperature | `0.4` |
| Response format | `PodcastScript` |
| Max tool rounds | `2` |

Not part of the main pipeline. Built on demand by audio endpoints. Produces a two-host dialogue (`HOST_A`, `HOST_B`) grounded in Foundry IQ excerpts and Fabric IQ ontology. Output is passed to Azure AI Speech for synthesis.

---

## 6. The Three IQ Layers

### 6.1 Foundry IQ — Knowledge Retrieval

**File:** [backend/iq/foundry_iq.py](../backend/iq/foundry_iq.py)

Answers: "What approved content exists for this topic?"

**Local mode** (`FOUNDRY_IQ_ENDPOINT=local`):
- TF-IDF keyword search over `./backend/data/documents/*.md` and `cert_structures.json`
- No network calls; instant and zero-credential
- Suitable for CI/CD and offline development

**Azure mode** (`FOUNDRY_IQ_ENDPOINT=https://{search}.search.windows.net`):
- HTTP POST to Azure AI Search REST API
- Auth: `AZURE_SEARCH_KEY` (dedicated) or fallback to `AZURE_AI_API_KEY`
- Returns `@search.score`-ranked results

**Foundry native mode** (`FOUNDRY_SEARCH_CONNECTION_NAME` set):
- Agents are registered with `AzureAISearchTool` pointing to the named connection
- Foundry handles retrieval server-side; the agent receives grounded output

**Output schema:**
```json
{
  "doc_id": "az204-guide",
  "title": "AZ-204 Learning Path",
  "excerpt": "Azure Functions provide serverless compute...",
  "score": 0.95,
  "span_id": "func-001",
  "source_url": "https://learn.microsoft.com/...",
  "ai_disclosure": "Retrieved from approved knowledge base via Foundry IQ"
}
```

---

### 6.2 Work IQ — Work-Context Signals

**File:** [backend/iq/work_iq.py](../backend/iq/work_iq.py) | [backend/iq/work_iq_graph.py](../backend/iq/work_iq_graph.py)

Answers: "What is happening in this person's workweek?"

**Signals:**

| Signal | Description |
|---|---|
| `meeting_hours_per_week` | Calendar-derived meeting load |
| `focus_hours_per_week` | Uninterrupted focus blocks |
| `available_study_hours_per_week` | Declared study time (conservative fallback: `focus_hours / 2`) |
| `preferred_learning_slot` | `Morning` / `Afternoon` / `Evening` |
| `upcoming_milestones` | Project deadlines that block study |

**Synthetic mode** (`WORK_IQ_SOURCE=synthetic`): reads from `LearnerProfile.work_iq_signals` (seeded from `learners.json`).

**Graph mode** (`WORK_IQ_SOURCE=graph`): queries Microsoft Graph `Calendars.Read` to derive actual meeting load from the learner's M365 calendar. Falls back to synthetic per-call on any token or mailbox error — the pipeline never breaks.

---

### 6.3 Fabric IQ — Semantic Layer / Ontology

**File:** [backend/iq/fabric_iq.py](../backend/iq/fabric_iq.py)

Answers: "What do these entities and rules *mean* for enterprise learning?"

**Ontology entities and relationships:**

```
Learner ──belongs_to──► Team
Learner ──has──► Role
Role ──recommends──► Certification
Certification ──contains──► SkillDomain (weighted)
Certification ──advances_to──► Certification  (e.g. AZ-204 → AZ-305)
ReadinessForecast ──depends_on──► evidence + work_context
```

**Local mode** (`FABRIC_IQ_ENDPOINT=local`): builds in-memory ontology from synthetic JSON files:
- `cert_structures.json` — domains, weights, services, passing score
- `learners.json` — learner seed data
- `teams.json` — team organization
- `cohort_outcomes.json` — historical pass rates

**Azure mode** (two paths, graceful fallback):

1. **SKU-free path** (Fabric Trial-compatible): Lakehouse SQL analytics endpoint via pyodbc with Entra token:
   ```sql
   SELECT domain_id, name, weight_pct, minimum_mastery
   FROM cert_domains WHERE cert_id = ?
   ```
2. **Data agent path** (paid F2+ capacity): NL2Ontology Fabric data agent via REST.

Any Azure failure falls back to local ontology automatically.

**Semantic query methods:**

| Method | Returns |
|---|---|
| `get_domain_thresholds(cert_id)` | Per-domain weight, leverage (weight/100), minimum_mastery, services |
| `get_readiness_semantics(cert_id, evidence)` | Weighted mastery, highest-leverage gap, per-domain status |
| `get_cohort_benchmark(cert_id)` | Historical pass rate, avg hours, protected-capacity effect |
| `get_intervention_effectiveness(cert_id)` | Estimated lift from protecting study time |
| `get_team_skill_gap_summary(team_id, evidence_by_learner)` | Gaps ranked by gap × leverage × coverage |
| `get_role_certification_map(role)` | Primary cert, recommended hours, next cert |
| `get_next_certification(cert_id)` | Canonical advances_to relationship (single source of truth) |

---

## 7. MCP Tools

**File:** [backend/mcp_server/server.py](../backend/mcp_server/server.py)

The FastMCP server exposes 10 typed tools as OpenAI-compatible function schemas. They are also reachable over HTTP (port 8001) for external callers. Inside the agent factory, own tools are executed in-process (direct `await fn()`) without HTTP overhead.

| Tool | Purpose |
|---|---|
| `parse_learner_profile` | Validate and normalize learner data; derive capacity risk |
| `foundry_iq_search` | Grounded knowledge retrieval from Foundry IQ |
| `validate_citation` | Verify a citation exists and supports the claim |
| `generate_study_plan` | Canonical capacity-aware study plan via LRA allocation |
| `generate_assessment` | Domain-weighted practice questions with answer key (server-side only) |
| `compute_readiness_forecast` | Calibrated P(pass), estimated score, weakest topic, confidence interval |
| `compute_domain_mastery` | Per-domain mastery breakdown from accumulated evidence |
| `compute_service_heatmap` | Service-level coverage heatmap within each cert domain |
| `compute_progress_series` | Planned-vs-actual study progress time series |
| `fabric_iq_semantics` | Semantic ontology queries (thresholds, benchmarks, role map, etc.) |

External tools linked via HTTP:

| Tool | Source |
|---|---|
| `microsoft_docs_search` | Microsoft Learn MCP (content chunks) |
| `microsoft_docs_fetch` | Microsoft Learn MCP (full page markdown) |
| `microsoft_code_sample_search` | Microsoft Learn MCP (code samples) |

---

## 8. Pipeline Middleware & RAI

**File:** [backend/middleware/pipeline.py](../backend/middleware/pipeline.py)

Applied via `apply_pipeline()` to every agent result before it leaves the system.

### PII Redaction

- Unconditional regex: email addresses, phone numbers
- Domain-aware name redaction: TitleCase bigrams redacted **only** if neither token is in `_DOMAIN_VOCAB` (preserves "Cloud Engineer", redacts "John Smith")

### Citation Gate

- Flags curator, assessment, and critic outputs that lack citation markers
- Logs a warning to the trace; does not rewrite content

### Safety Guard

- Regex patterns: `hack`, `exploit`, `bypass`, `jailbreak`
- Returns `[SAFETY BLOCK]` message on match

### Bias Audit

- Scans for gendered pronouns and role-stereotype patterns
- Logs findings to trace; does not block

### Content Safety

**File:** [backend/middleware/content_safety.py](../backend/middleware/content_safety.py)

- **Azure mode**: Live Azure AI Content Safety API; Hate/SelfHarm/Sexual/Violence categories; severity ≥ threshold → BLOCK
- **Local fallback**: Regex patterns for common harmful content patterns

### Red Team Screening

**File:** [backend/middleware/red_team.py](../backend/middleware/red_team.py)

- **Input screening**: jailbreak patterns, prompt injection signatures, high-risk keywords
- **Output screening**: harmful content, PII leakage, bias patterns
- 16 defensive patterns; regex-based (no model call)

---

## 9. Storage Layer

**File:** [backend/storage/store.py](../backend/storage/store.py)

Storage is **local JSON files only** in the current deployment. The codebase also contains a `CosmosStore` class with a full async Cosmos SDK implementation, but no Cosmos resource is provisioned and `STORAGE_BACKEND` always defaults to `local`.

### Local mode

- JSON files in `backend/data/store/`, one file per container
- Upsert-by-id with full replace; `_updated_at` timestamp on every write
- Zero dependencies beyond the Python standard library

### Persisted entities

**StudyPlan** — lifecycle: `draft` → `approved` → `active`
- Stores all revisions (`revision_count`)
- HITL approval gate sets `approved_by` and `approved_at`

**Assessment** — practice questions, submitted answers, and scoring
- `answer_key` stored server-side only
- `evidence` (domain-level correctness), `estimated_exam_score`, `passed`

**ReasoningTrace** — full list of `TraceEvent` objects
- Persisted after workflow completes; enables trace replay after page reload

**Manager Interventions** — high-priority actions flagged on a learner
- Auto-triggered after 2 consecutive "NOT_YET" booking verdicts
- Manually addable by manager via API

**Peer Learning Sessions** — scheduled coaching between peers
- `mentor_id`, `learner_id`, `focus_domain`, `rationale`
- Status: `planned` → `completed`

---

## 10. Evaluation & Readiness Model

### Calibrated Readiness Model

**File:** [backend/evals/readiness_model.py](../backend/evals/readiness_model.py)

Logistic regression trained on synthetic cohort outcomes (pure numpy, seeded for determinism — no sklearn dependency).

**Features:**

| Feature | Effect |
|---|---|
| `practice_score` (0–100) | Primary positive signal |
| `hours_studied` | Positive (diminishing returns) |
| `meeting_hours_pw` | Negative (capacity drain) |

**Outputs:**
- `pass_probability` ∈ [0, 1]
- `estimated_exam_score` (scaled to 700–1000 for Azure certs)
- `weakest_topic`
- `insufficient_evidence` flag (honest abstention when evidence is too thin)

**Booking verdict thresholds** (aligned with AUC 0.802 calibration):
- `GO` — P(pass) ≥ 0.72 and verdict = ready
- `CONDITIONAL_GO` — 0.50 ≤ P(pass) < 0.72
- `NOT_YET` — below threshold or insufficient evidence

LOO cross-validation metrics exposed via `/api/eval/summary`:
- AUC ≈ 0.80
- Brier score ≈ 0.15

### Agent Quality Rubrics

**File:** [backend/evals/agent_rubrics.py](../backend/evals/agent_rubrics.py)

Deterministic checks on agent outputs (no LLM required):

| Prefix | Agent | Example checks |
|---|---|---|
| C1–C4 | Curator | Citation coverage, topic count, domain mapping, priority weighting |
| P1–P5 | Plan | Hour allocation, deadline respect, prerequisite ordering, week distribution |
| CR1–CR4 | Critic | Objection count, severity weighting, domain leverage, citation presence |
| A1–A4 | Assessment | Question count, domain coverage, difficulty distribution, citation presence |
| E1–E3 | Engagement | Slot count, capacity risk accuracy, blocked period identification |
| M1–M4 | Manager | Team size, readiness distribution, action count, peer-pair count |
| R1–R4 | Retrospective | Root-cause clarity, evidence count, recovery recommendations |

Returns `{passing_checks, failing_checks, score: float 0–1}` per agent.

### Groundedness Evaluator

**File:** [backend/evals/groundedness.py](../backend/evals/groundedness.py)

- **Azure mode**: LLM-as-judge via `azure-ai-evaluation` SDK; counts cited vs uncited assertions
- **Local fallback**: Regex citation patterns; activates on `foundry_local` backend or timeout > 25s
- Endpoint: `GET /api/evals/groundedness/{run_id}`

---

## 11. Azure AI Foundry Integration

**File:** [backend/core/foundry_orchestration.py](../backend/core/foundry_orchestration.py)

### Agent Registration (opt-in)

`register_all_agents()` exists but is **skipped by default** (`FOUNDRY_AUTO_REGISTER=false`). The standard workflow is to pre-register agents once via `scripts/register_agents_cloud_shell.py` and leave auto-registration off at runtime. Set `FOUNDRY_AUTO_REGISTER=true` only for fresh installs or CI environments that have no pre-registered state.

When enabled (at startup, `MODEL_BACKEND=azure_foundry`), it registers 8 agent definitions:

```python
_AGENT_DEFINITIONS = [
    {"name": "eciq-learner-intake", ...},
    {"name": "eciq-learning-path-curator", ...},
    {"name": "eciq-study-plan-generator", ...},
    {"name": "eciq-readiness-critic", ...},
    {"name": "eciq-engagement-agent", ...},
    {"name": "eciq-assessment-agent", ...},
    {"name": "eciq-manager-insights", ...},
    {"name": "eciq-retrospective", ...},
]
```

With `FOUNDRY_AUTO_REGISTER=false` (default), the call is a no-op and agents are assumed pre-registered.

### FoundrySession

Wraps each workflow run as a Foundry Agent thread:

```python
async with FoundrySession(run_id, learner_id, cert_id) as session:
    ctx = await orchestrator.run(learner, on_event=session.relay_event)
    await session.complete(ctx)
```

- Relays trace events into the Foundry thread message stream
- Workflow runs become visible in Foundry portal → Build → Agents → Tracing tab
- Falls back to a no-op context manager when the SDK is unavailable

### Responses API (opt-in grounding)

**File:** [backend/core/foundry_grounded_agent.py](../backend/core/foundry_grounded_agent.py)

The default path uses `BaseAgent` (local Foundry Local or Azure OpenAI direct). The Responses API path is **opt-in** via `FOUNDRY_USE_RESPONSES_API=true`.

When enabled, curator, critic, and assessment agents are called via `call_grounded_agent()` instead:

- Knowledge-base retrieval and citation injection happen server-side in Foundry
- Spans appear in the Foundry project Tracing tab
- If `call_grounded_agent()` returns `None` (unavailable or error), the workflow falls back to the standard `BaseAgent` call — the pipeline never breaks regardless of this setting

### Agent SDK Version

Requires `azure-ai-projects >= 2.1.0`. The `AIProjectClient` is initialized with `allow_preview=True` to access hosted agent and Responses API features.

---

## 12. Hosted Agent (optional)

**File:** [hosted/main.py](../hosted/main.py)  
**Dockerfile:** [Dockerfile.hosted](../Dockerfile.hosted)

The Hosted Agent is **not required for normal operation** — the FastAPI backend (`backend/main.py`, port 8000) is the primary runtime. The hosted path is an optional deployment target for running the same pipeline inside Foundry Hosted Agent Service.

`hosted/main.py` wraps the full `WorkflowOrchestrator` behind the Foundry **Responses API contract** on port 8088.

### Protocol

```
POST /responses   { "input": "Evaluate readiness for L-1004 (AZ-204)" }
→ { "output_text": "EnterpriseCertIQ readiness for L-1004 (AZ-204): verdict=ready; ..." }

GET  /readiness   → { "status": "ready" }
```

### Runtime selection (graceful fallback)

The entry point tries the official Foundry protocol library first, then falls back to a minimal FastAPI implementation that satisfies the same contract — so the container runs and is testable even when `azure-ai-agentserver-responses` is not installed:

```python
try:
    from azure.ai.agentserver.responses import app, TextResponse
    # Use official Foundry protocol library
    @app.response_handler
    async def handler(request, context, cancellation_signal):
        return TextResponse(await run_pipeline(request.input))
except Exception:
    # FastAPI fallback — same contract; no SDK required
    app = FastAPI(...)
    @app.post("/responses")
    async def responses(body): ...
```

### Container image

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.hosted.txt ./
RUN pip install -r requirements.hosted.txt
RUN pip install azure-ai-agentserver-responses || echo "fallback"
COPY backend/ config/ prompts/ hosted/ ./
EXPOSE 8088
HEALTHCHECK --interval=30s CMD curl -fsS http://localhost:8088/readiness || exit 1
CMD ["python", "-m", "hosted.main"]
```

Built for `linux/amd64` and pushed to `eciqregistry.azurecr.io/enterprisecertiq-hosted:latest`.

### Deployed to Foundry via

```python
from azure.ai.projects.models import HostedAgentDefinition, ContainerConfiguration
client.agents.create_version(
    agent_name="eciq-orchestrator",
    definition=HostedAgentDefinition(
        container_configuration=ContainerConfiguration(image=ACR_IMAGE),
        environment_variables=AGENT_ENV_VARS,  # ECIQ_* prefix (not FOUNDRY_*)
        cpu="1", memory="2Gi",
    )
)
```

Script: [scripts/deploy_hosted_agent.py](../scripts/deploy_hosted_agent.py)

---

## 13. Observability & Telemetry

**File:** [backend/core/telemetry.py](../backend/core/telemetry.py)

### OpenTelemetry Spans

| Span | Created when |
|---|---|
| `workflow_span(run_id, learner_id, cert_id)` | Wraps the entire pipeline run |
| `agent_span(name, run_id, model)` | Each agent's LLM call |
| `span(name)` | Individual MCP tool calls |

**Azure mode** (`ENABLE_TELEMETRY=true` + connection string): Azure Monitor exporter → Application Insights.

**Local mode**: Console exporter for debug output.

### Foundry Agent Tracing

`instrument_foundry_agents()` adds GenAI/agent spans that appear in the **Foundry portal → project → Tracing tab**, giving visibility into per-agent latency, token usage, and tool calls in the Azure console.

### SSE Event Bus

In-memory fan-out (`_sse_queues`) per `run_id`:
- `GET /api/workflow/{run_id}/stream` — live trace events as newline-delimited JSON
- Events: `WORKFLOW_START`, `AGENT_START`, `AGENT_COMPLETE`, `TOOL_CALL`, `TOOL_RESULT`, `CRITIC_OBJECTION`, `HITL_REQUEST`, `READINESS_ADVANCE`, `READINESS_LOOPBACK`, `WORKFLOW_COMPLETE`

### Structured Logging

- `structlog` + stdlib `logging`
- Agent calls, tool executions, fallback triggers, and model errors all logged with context
- Searchable in Application Insights Log Analytics

### LLM Cache Metrics

- `GET /api/cache/stats` — hit count, miss count, current entry count
- Each cache entry stores the full response including token usage

---

## 14. API Surface

**File:** [backend/main.py](../backend/main.py) — `FastAPI v1.2.0`

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/workflow/run` | Start pipeline for a learner; returns `run_id` |
| `GET` | `/api/workflow/{run_id}/stream` | SSE stream of trace events |
| `GET` | `/api/workflow/{run_id}/result` | Final workflow outputs |
| `POST` | `/api/plans/approve` | HITL approval gate (publishes draft plan) |
| `GET` | `/api/plans/{learner_id}` | List plans for a learner |
| `POST` | `/api/assessments/submit` | Submit practice question answers |
| `GET` | `/api/assessments/{learner_id}` | Assessment history |
| `GET` | `/api/manager/{team_id}` | Manager insights for a team |
| `POST` | `/api/interventions` | Create a manager intervention |
| `POST` | `/api/peer-sessions` | Schedule a peer learning session |
| `GET` | `/api/audio/{learner_id}/briefing` | Generate two-host audio study briefing |
| `GET` | `/api/reports/{learner_id}/pdf` | Download PDF readiness report |
| `GET` | `/api/eval/summary` | Readiness model AUC + Brier score |
| `GET` | `/api/evals/groundedness/{run_id}` | Citation groundedness score |
| `GET` | `/api/cache/stats` | LLM cache hit/miss statistics |
| `GET` | `/health` | Health check |

CORS is configured via `CORS_ORIGINS` (default: `http://localhost:5173,http://localhost:3000`).

---

## 15. Deployment Modes

The intended progression is **local-first → cloud with Responses API → Hosted Agent (optional)**. Each step is independently useful and each adds to the one before it.

### Step 1 — Local Development (default)

All `settings.py` defaults point here. No Azure credentials required.

```bash
export MODEL_BACKEND=foundry_local
export FOUNDRY_LOCAL_ENDPOINT=http://localhost:5273/v1
# STORAGE_BACKEND, WORK_IQ_SOURCE, FABRIC_IQ_ENDPOINT all default to local/synthetic
uvicorn backend.main:app --reload --port 8000
python -m backend.mcp_server.server     # port 8001
cd frontend && npm run dev              # port 5173
```

### Step 2 — Azure AI Foundry with Responses API (cloud, opt-in)

Switch the model backend to Azure and point Foundry IQ at your Azure AI Search index.
Application data (plans, traces) still persists to local JSON — `STORAGE_BACKEND` stays `local`.

Enabling `FOUNDRY_USE_RESPONSES_API=true` routes curator, critic, and assessment through the
Foundry Responses API, so knowledge retrieval happens server-side via the MCPTool connections
attached to the pre-registered prompt agents (`eciq-learning-path-curator`, `eciq-readiness-critic`,
`eciq-assessment-agent`). The other five agents continue to use the direct Azure AI Search path.

```bash
export MODEL_BACKEND=azure_foundry
export AZURE_AI_PROJECT_ENDPOINT=https://{hub}.services.ai.azure.com/api/projects/{project}
export AZURE_AI_MODEL_DEPLOYMENT=gpt-4.1
# Direct Azure AI Search path (used by all agents on the non-Responses-API path)
export FOUNDRY_IQ_ENDPOINT=https://{search}.search.windows.net
export FOUNDRY_IQ_INDEX_NAME=cert-knowledge-base
# AZURE_SEARCH_KEY: set in .env.local for local dev; in cloud, loaded automatically
# from Key Vault secret "azure-search-key" when AZURE_KEY_VAULT_URL is set.
export AZURE_KEY_VAULT_URL=https://your-keyvault-name.vault.azure.net
# Enable server-side grounding for curator/critic/assessment via registered Foundry agents
export FOUNDRY_USE_RESPONSES_API=true
# Auth: az login (local) or managed identity (cloud)
```

Pre-register all 9 prompt agents once (not at every startup):
```bash
cd ~/eciq && python scripts/register_agents_cloud_shell.py
```

After registration, the agents visible in Foundry portal → Build → Agents each carry their
Foundry IQ KB and Fabric IQ KB MCPTool connections. The Responses API path calls them by name
(`eciq-learning-path-curator` etc.) so retrieval and citation injection happen inside Foundry.

### Step 3 — Foundry Hosted Agent (optional)

Deploys the same pipeline as a containerized agent in Foundry Hosted Agent Service. Requires an Azure Container Registry and a Foundry project in a supported region (East US 2).

```bash
# Build and push image
az acr build -r eciqregistry -t enterprisecertiq-hosted:latest -f Dockerfile.hosted .

# Assign Container Registry Repository Reader to the Foundry project managed identity
az role assignment create \
  --assignee <project-mi-object-id> \
  --role "Container Registry Repository Reader" \
  --scope /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.ContainerRegistry/registries/eciqregistry

# Wait 5 minutes for IAM propagation, then deploy
python scripts/deploy_hosted_agent.py
# Poll until status = active; invoke via Foundry portal playground or Responses API
```

---

## 16. Key Design Decisions

### Three-Tier Fallback — No Pipeline Breaks

Every agent has a deterministic Python builder (`fallbacks.py`) that produces schema-shaped output without any model or network call. `AGENT_FALLBACK_MODE=force` makes this the primary path (instant, zero-credential demo mode). `auto` activates it only on model error after retries.

### Plan Canonicalization — Separate LRA from the LLM

The Planner agent generates a plan in natural language or JSON, but the workflow **always** runs the result through `generate_study_plan.fn()` afterward. This decouples the LLM from the hour-allocation algorithm: LRA runs every time, topic starvation is impossible regardless of what the model returns.

### Critic Uses Fabric IQ Leverage Weights — Not Raw Gaps

Objections are scored by `domain_weight × mastery_gap`. A 10-point gap in a 30%-weight domain is three times more actionable than a 10-point gap in a 10%-weight domain. This drives the planner's revisions toward the changes that most improve pass probability.

### Deterministic Readiness Decision — Separates LLM from Control Flow

The loop-back vs. advance decision is made by `_readiness_from_forecast()` — a pure function of the calibrated model output. The Assessment Agent provides grounded questions and a narrative, but the authoritative control signal is never subject to LLM variance.

### HITL Gate — Trust Boundary

Plans remain `draft` status and are never published until a human calls `/api/plans/approve`. The Engagement and Manager outputs produced after the HITL gate are explicitly labelled "advisory previews" in the trace, so the reviewing human has full context at approval time.

### Concurrent Fan-Out — Critical-Path Latency

Engagement (Work IQ signals) and Readiness Forecast (calibrated model) run via `asyncio.gather()`. Neither depends on the other's output. This saves approximately 40% end-to-end latency on the critical path.

### Citation-or-Drop — Hallucination Prevention

The Curator and Assessment agents are instructed: if no approved source is found, state that rather than inventing content. The middleware Citation Gate flags any outputs that lack citation markers, surfacing this in the trace for review. The `validate_citation` tool allows models to verify citations before committing to them.

### Multi-Account Azure — Fabric in a Separate Tenant

`FABRIC_TENANT_ID`, `FABRIC_CLIENT_ID`, and `FABRIC_CLIENT_SECRET` allow Fabric to live in a different Entra tenant from the Foundry hub. The `get_service_credential("fabric")` helper selects `ClientSecretCredential` when all three are set, and falls back to `DefaultAzureCredential` otherwise.

### Env Var Prefix Isolation for Hosted Agent

The Foundry platform fully reserves `FOUNDRY_*` and `AGENT_*` env var prefixes. Hosted container environment variables use the `ECIQ_*` prefix instead. The `_apply_eciq_overrides` validator in `settings.py` transparently maps them, leaving local `.env.local` (using `FOUNDRY_*` names) completely unaffected.
