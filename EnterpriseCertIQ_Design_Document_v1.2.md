# EnterpriseCertIQ

**Technical Design Document · v1.2**

*Microsoft Agents League 2026 · Reasoning Agents Track*

A multi-agent enterprise learning system that turns certification goals into grounded, work-aware study plans — with honest readiness forecasting, failure-mode retrospectives, and visible reasoning across every step. Built on Microsoft Agent Framework + Microsoft Foundry.

*Prepared for Kalyan · v1.2 · May 26, 2026 · Build window: June 4–14, 2026*

---

**Why this design exists.** EnterpriseCertIQ is the on-scenario pivot of the Appealsmith v3 architecture (Agent Framework + MCP + A2A + APIM AI Gateway + Foundry IQ + observability + evals + red-teaming) onto the official Core Challenge Scenario: *"build a multi-agent enterprise learning system that helps organisations manage internal team certification programmes."* Microsoft confirmed on Discord that submissions must be based on the official scenarios. EnterpriseCertIQ keeps the engineering depth and pivots the domain.

**Stack at a glance:** Microsoft Agent Framework 1.0 (GA) · 6 specialized agents · MCP tool calling · Microsoft Learn MCP server integration · A2A v1 · typed tool calling · Azure API Management AI Gateway · Microsoft Foundry models + Agent Service (Hosted Agents) · Foundry IQ (cert content grounding) · Work IQ (work-context personalization) · Foundry Observability (OTel → App Insights) · Foundry Evaluation SDK · AI Red Teaming Agent (PyRIT) · Azure Cosmos DB.

**Prize targets:** **Best Reasoning Agent** + **Best Use of IQ Tools** + a real shot at **Best Overall Agent ($15,000)**.

**What's new in v1.1:** three demo-core readiness features (Domain Mastery, Service-level Heatmap, Pass-threshold Awareness) sourced from Microsoft Learn MCP exam objectives, plus a Foundry Local + Foundry Cloud flexibility layer for dev-vs-demo backend switching.

**What's new in v1.2:** four gap fixes from a careful re-read of the official criteria — explicit **AI-disclosure pattern** on every generated artifact (RAI requirement "be transparent"), **bias audit promoted from future-flagged to must-ship** in CI (RAI requirement "test for bias"), **Microsoft Foundry synthetic data generation tool** called out in §13, and a **visible HITL approval moment** added to the demo walkthrough so judges see human oversight happen on camera.

## Contents

1. [Problem & Scenario Alignment](#1-problem--scenario-alignment)
2. [Product Walkthrough](#2-product-walkthrough-what-the-judge-sees)
3. [System Architecture](#3-system-architecture)
4. [Tool Calling, MCP, A2A & the APIM AI Gateway](#4-tool-calling-mcp-a2a--the-apim-ai-gateway)
5. [The Multi-Agent Reasoning Design](#5-the-multi-agent-reasoning-design)
6. [Creative Features](#6-creative-features)
7. [Engineering Best Practices](#7-engineering-best-practices)
8. [Implementation Skeleton](#8-implementation-skeleton)
9. [Cosmos DB Data Model](#9-cosmos-db-data-model)
10. [Observability](#10-observability)
11. [Evaluation Strategy](#11-evaluation-strategy)
12. [Red Teaming & Safety](#12-red-teaming--safety)
13. [Synthetic Data & Test Scenarios](#13-synthetic-data--test-scenarios)
14. [10-Day Build Plan](#14-10-day-build-plan)
15. [Scope Discipline & Cut List](#15-scope-discipline--cut-list)
16. [Future Work](#16-future-work-honestly-disclosed-not-built)

## 1. Problem & Scenario Alignment


### 1.1 The scenario, restated

From the official starter kit: *"Build a multi-agent enterprise learning system that helps organisations manage internal team certification programmes. The system should be able to understand certification requirements mapped to organisational roles, generate team-level and role-based study plans, provide grounded practice questions from approved knowledge sources, offer feedback on team and individual progress, adapt learning schedules to real work context and team capacity, and surface manager-level insights across team readiness and risk."*

**EnterpriseCertIQ's reading.** This is fundamentally a **multi-step reasoning** problem under uncertainty — not a content recommendation problem. The hard part isn't recommending an AZ-204 study guide; it's reasoning about whether **this learner** with **this workload**, **these prior attempts**, and **these knowledge gaps** will actually be ready by the deadline. EnterpriseCertIQ optimizes for that reasoning, not for content delivery.

### 1.2 Scenario alignment — explicit mapping

Each official submission requirement mapped to the section that satisfies it. The mapping is deliberate — judges can verify alignment by reading the table below, not by scanning the whole document.

| Official requirement | Status | Where in this doc |
|---|---|---|
| Multi-agent system aligned to scenario | ✅ COVERED | §3 (architecture) §5 (agents) |
| Use Foundry SDK and/or Agent Framework | ✅ COVERED | §3.2, §6 |
| Reasoning + multi-step decision-making | ✅ COVERED | §5.1 orchestration; §6 visible reasoning |
| External tools / APIs / MCP where they add value | ✅ COVERED | §4.2 (own MCP) + §4.3 (Microsoft Learn MCP) |
| At least one Microsoft IQ layer | ✅ TWO COVERED | §3.3 — Foundry IQ + Work IQ. Fabric IQ as future work. |
| Synthetic data + synthetic documents only | ✅ COVERED | §13 |
| Demoable + clearly explains agent interactions | ✅ COVERED | §2 walkthrough; §6.1 reasoning visualization |
| Clear docs (responsibilities, orchestration, tools, data) | ✅ COVERED | This document |
| **Highly valued:** Evaluations, telemetry, observability | ✅ COVERED | §10 (observability), §11 (evals) |
| **Highly valued:** Advanced reasoning patterns | ✅ COVERED | §5.1 (planner-executor, critic, self-reflection) |
| **Highly valued:** Responsible AI controls + fallbacks | ✅ COVERED | §7 (engineering practices), §12 (red teaming) |
| **Highly valued:** Clear hosted deployment story | ✅ COVERED | §3.4 — Hosted Agents in Foundry Agent Service |

> ⚠️ **Note on scope and discipline**
> This is an ambitious build. EnterpriseCertIQ bundles six agents, two IQ layers, MCP + Microsoft Learn MCP + A2A + APIM, ten creative features, and the full engineering-practices set. A 10-day timeline cannot ship all of this at full polish. §14 (build plan) and §15 (cut list) are explicit about what stays vs what is documented and stubbed if the calendar tightens. Read those sections before you start building.

## 2. Product Walkthrough (What the Judge Sees)

The 5-minute demo, beat by beat. Build backward from this.

1. **Setup (0:00–0:30).** Open the EnterpriseCertIQ dashboard. Pick a synthetic learner (L-1004, Cloud Engineer, targeting AZ-204) and a synthetic team (TEAM-A, 5 members, mixed cert targets).
2. **Watch the agents reason (0:30–1:30).** A live reasoning panel shows six specialized agents lighting up in sequence — Learner Intake, Learning Path Curator, Study Plan Generator, Engagement Agent, Readiness Critic, Manager Insights — with intermediate conclusions streaming.
3. **Inspect the grounded plan (1:30–2:15).** Generated study plan appears on the right with an **"AI-generated; review before publishing" banner**. Every recommendation has a citation chip; clicking it highlights the source span in the indexed cert content. Microsoft Learn MCP links surface alongside organisational content. **System pauses for human approval before the plan is published** — demo presenter clicks Approve on camera to make the HITL gate visible. The criteria explicitly require "human oversight in important decisions"; this is where judges see it happen.
4. **The Critic finds the weak spots (2:15–3:00).** Readiness Critic attaches red sticky notes to risky parts of the plan: "too little networking time given role gap," "deadline collides with sprint review." Resolved objections turn green; unresolved ones stay amber. This is the hero visualization.
5. **The deviation graph (3:00–3:20).** Planned vs actual progress chart. Planned trajectory is steady; actual trajectory shows L-1004 fell behind in week 2. The Engagement Agent intervention point is marked with an arrow.
6. **Exam-day rehearsal (3:00–3:20).** Hit "Run mock exam." Assessment Agent generates a timed, weighted set of cited questions matching the real cert's structure (sourced from Microsoft Learn MCP).
7. **Readiness breakdown (3:20–4:00).** Three views stacked:
   - Domain mastery breakdown — horizontal bars per cert domain ("Develop Azure compute solutions: 78%, Develop for Azure storage: 54%…"), each labelled with confidence intervals.
   - Service-level heatmap — cells inside each domain (Functions / App Service / Container Apps / Logic Apps) light up red/amber/green based on accumulated evidence.
   - Pass-threshold awareness — overlay the real exam's passing score (700/1000 for most Microsoft exams, sourced via Microsoft Learn MCP). The learner's forecast appears as "estimated 685/1000, 15 points below pass threshold; gap concentrated in two services." Honest, calibrated, actionable.
8. **Manager view (4:00–4:30).** Switch to Manager Insights: team-level risk heatmap, capacity conflicts highlighted, peer-learning pairs suggested ("Lin is strong on networking where Priya is weak; Priya is strong on security where Lin is weak").
9. **Honesty moment (4:30–5:00).** Show the failure-mode retrospective for a different learner (L-1007) who failed an earlier mock exam. The system's postmortem: "retrieval quality was strong, plan was reasonable, but engagement signals showed actual study hours ≤ 40% of plan. Recommend recovery plan with shorter sessions." Show the red-team scan results and APIM token chart on a second screen.

> 🎯 **The demo line that wins the room**
> *"Watch a multi-agent system reason about a real learner, find the gaps in their plan, forecast their exam readiness with honest uncertainty — and show you exactly where it would intervene if they fell behind."*

## 3. System Architecture


### 3.1 Component map

EnterpriseCertIQ is a graph-based multi-agent workflow on Microsoft Agent Framework 1.0. Tools are exposed via MCP (own server + Microsoft Learn MCP). Cross-runtime collaboration uses A2A. Every model call exits through Azure API Management acting as the AI Gateway. State and traces live in Cosmos DB; observability flows to Foundry via OpenTelemetry. The container runs as a Hosted Agent in Foundry Agent Service.

```
  External A2A clients              React Dashboard (learner + manager views)
  (HR systems, LMS agents)  ────┐         │
                                ▼         ▼
                       ┌──────────────────────────────────┐
                       │  API / BFF (FastAPI) + Entra ID  │
                       │  A2A server (A2AExecutor)        │
                       └──────────────┬───────────────────┘
                                      │
                       ┌──────────────▼───────────────────┐
                       │  MICROSOFT AGENT FRAMEWORK 1.0   │
   ┌──────────────────┐│  Workflow (graph orchestration)  │
   │ Middleware       ││   [1] Learner Intake             │
   │ - PII redaction  ││   [2] Learning Path Curator      │
   │ - content safety ││   [3] Study Plan Generator       │
   │ - citation gate  ││   [4] Engagement Agent           │
   │ - fairness check ││   [5] Readiness Critic           │
   └──────────────────┘│   [6] Manager Insights           │
                       │   +  Retrospective (on failure)  │
                       └─────┬────────────┬───────────────┘
                             │            │ MCP client
                             ▼            ▼
                   ┌─────────────┐  ┌──────────────────────────┐
                   │ Own MCP     │  │ Microsoft Learn MCP      │
                   │ Server      │  │ (exam skills, cert paths)│
                   │ (FastMCP)   │  └──────────────────────────┘
                   └─────┬───────┘
                         │  model calls
   ┌─────────────────────▼────────────────────────────────────────┐
   │  AZURE API MANAGEMENT — AI GATEWAY                           │
   │  llm-token-limit → llm-semantic-cache → llm-content-safety   │
   │  outbound: llm-semantic-cache-store + emit-token-metric      │
   │  backends: load-balanced Foundry / Azure OpenAI deployments  │
   └────┬─────────────────────┬──────────────────────────┬────────┘
        ▼                     ▼                          ▼
   Foundry Models       Foundry IQ                  Work IQ
   (GPT-class)          (cert content grounding)    (work-context signals)
        │                     │                          │
        └─────────────────────▼──────────────────────────┘
                       Cosmos DB
          (study_plans, reasoning_trace, learner_memory,
           cache, eval_results, a2a_audit, progress_series,
           mastery_grid)

   Deployment: Container → ACR → Foundry Agent Service (Hosted Agent)
   Observability: OTel traces → App Insights → Foundry dashboard
                  + APIM emit-token-metric → App Insights
   Offline gates: Evaluation SDK + AI Red Teaming Agent (PyRIT) in CI
                  + Bias audit evaluator (every prompt change)
```

### 3.2 Why these specific Microsoft components


| Component | Role in EnterpriseCertIQ & why it earns judge points |
|---|---|
| Agent Framework 1.0 | GA April 3, 2026. Graph workflows give explicit, checkpointed, streamable multi-agent orchestration with built-in HITL — the backbone of the Reasoning score (25%). |
| MCP — own server | Four typed tools. Reusable, discoverable at runtime. |
| MCP — Microsoft Learn | Explicitly called out as a tip in the criteria. Surfaces real exam-skills outlines and learning paths. |
| A2A v1 | Released April 28, 2026. EnterpriseCertIQ published as an A2A agent so external HR/LMS systems can request study plans. |
| APIM AI Gateway | Token limits, semantic cache, content safety, per-call token metrics emitted to App Insights. |
| Microsoft Foundry | Hosts models behind each agent via the Agent Service. |
| Foundry IQ | The IQ-Tools centerpiece: agentic retrieval over the indexed cert content. |
| Work IQ | Personalizes Engagement Agent and Manager Insights. |
| Foundry Observability | OTel → App Insights → Foundry monitoring dashboard. |
| Evaluation SDK + Red Teaming Agent | Offline + continuous evaluators; PyRIT-based adversarial scans. |
| Foundry Agent Service (Hosted) | The hosted deployment story the criteria explicitly call out. |
| Azure Cosmos DB | Low-latency JSON backend for workflow state, conversational memory, eval cache, reasoning trace, progress time-series, and the new mastery grid. |

### 3.3 IQ integration depth (the criteria's core requirement)

The criteria require **at least one** IQ layer and explicitly say "you can choose one, or combine all three." EnterpriseCertIQ integrates two with depth, and documents Fabric IQ as honest future work — not a half-built feature.

| IQ layer | EnterpriseCertIQ usage | Why this depth |
|---|---|---|
| **Foundry IQ** | Primary grounding. Cert guides indexed; Learning Path Curator and Assessment Agent both retrieve through it; citation-or-drop enforced. | Non-negotiable — it is what makes assessment questions trustworthy and what powers the IQ-Tools prize alignment. |
| **Work IQ** | Engagement Agent reads synthetic Work IQ signals (meeting load, focus windows). Manager Insights uses team-level capacity signals to flag conflicts. | Directly addresses two scenario requirements ("adapt to work context," "team capacity"). |
| *Fabric IQ* | *Documented as future work — ontology of role/cert/skill/threshold/study-hours. Sketched in §16.* | *Heavier to set up well. We honestly disclose this rather than half-build and break the demo.* |

### 3.4 Hosted deployment story

The criteria list this under "Highly Valued Extras" explicitly. EnterpriseCertIQ is packaged as a **Hosted Agent in Foundry Agent Service**:

- **Container image** of the Agent Framework workflow + FastAPI BFF + own MCP server pushed to Azure Container Registry.
- **Foundry Agent Service** hosts the container with a dedicated endpoint and an **Entra ID agent identity** (not the developer's identity).
- **Immutable image versions; staged rollout.** ADRs document the deployment pattern (see §7.12).
- **One-command repro** via `azd up` deploys the full stack into a fresh subscription with synthetic data pre-loaded.

## 4. Tool Calling, MCP, A2A & the APIM AI Gateway

Same four-layer story as Appealsmith v3, pivoted to the certification domain. Typed tool calls are how agents act; MCP is how they discover what they can act on (including the Microsoft Learn MCP server explicitly called out in the criteria); A2A is how they collaborate across runtimes; APIM is the policy plane sitting in front of every model call.

### 4.1 Typed tool calling

- **Strict types.** Every tool has a Pydantic schema. Ambiguous calls fail fast.
- **Approval-required on visible artifacts.** Tools that produce a published study plan or send a manager notification are approval-required.
- **Idempotent + traced.** Tools log to reasoning_trace with arguments and result hash; runs are replayable.

### 4.2 Own MCP server (FastMCP)


| Tool | Used by | Why MCP, not hard-coded |
|---|---|---|
| `parse_learner_profile` | Learner Intake | Reusable across role/cert combinations. |
| `foundry_iq_search` | Curator, Assessment | Primary grounding. One implementation, multiple agents. |
| `validate_citation` | Curator, Assessment, Critic | Uniform citation logic. |
| `generate_study_plan` | Study Plan Generator | Approval-required. Centralizes plan formatting. |
| `generate_assessment` | Assessment Agent | Returns timed, weighted question set with citations. |
| `compute_readiness_forecast` | Readiness Critic | Returns (probability, confidence interval, weakest topic). Deterministic. |
| `compute_progress_series` | Engagement Agent + UI | Returns the planned-vs-actual time series for the deviation graph. |
| `compute_domain_mastery` | Readiness Critic + UI | Joins evidence against Microsoft Learn MCP domain weightings → per-domain mastery breakdown. |
| `compute_service_heatmap` | Readiness Critic + UI | Service-level evidence rollup for the heatmap. |

#### 4.2.1 Skeleton: the MCP server

```python
from fastmcp import FastMCP
from pydantic import BaseModel

mcp = FastMCP('enterprisecertiq-tools')

class ForecastInput(BaseModel):
    learner_id: str
    cert_id: str
    plan_id: str

@mcp.tool()
def compute_readiness_forecast(args: ForecastInput) -> dict:
    """Calibrated forecast: returns probability + confidence interval +
       weakest topic from evidence + cohort outcomes."""
    evidence = load_evidence(args.learner_id, args.cert_id)
    cohort   = load_cohort_outcomes(args.cert_id)
    return readiness_model.forecast(evidence, cohort, args.plan_id)

if __name__ == '__main__':
    mcp.run()
```

### 4.3 Microsoft Learn MCP integration

The criteria explicitly tip: *"Some of these capabilities can be extended with the Microsoft Learn MCP server."* EnterpriseCertIQ consumes the public Microsoft Learn MCP server alongside its own. Real exam-skills outlines and learning paths surface in the Learning Path Curator's output — grounding the plan in genuine cert structure without using any internal Microsoft data.

```python
from agent_framework.mcp import MCPStreamableHTTPTool

learn_tools = MCPStreamableHTTPTool(
    name='ms-learn',
    url='https://learn.microsoft.com/api/mcp')   # public Microsoft Learn MCP

own_tools = MCPStreamableHTTPTool(
    name='enterprisecertiq-tools',
    url=OWN_MCP_URL)

curator = ChatAgent(client, name='curator',
    instructions=CURATOR_PROMPT,
    tools=[own_tools, learn_tools])   # both surfaces, one agent
```

### 4.4 A2A — cross-runtime collaboration


| Scenario | Why it matters |
|---|---|
| EnterpriseCertIQ hosted as an A2A agent | An HR system (any framework) can request a study plan for a specific employee — just an HTTP call to the A2A endpoint with the Agent Card. |
| EnterpriseCertIQ calls an external A2A "Workforce Capacity" agent | Partner-team agent provides team-level capacity signals beyond what Work IQ surfaces — PTO calendars, project ship dates. Demonstrates real cross-runtime composition. |

### 4.5 Azure API Management as the AI Gateway


| APIM policy | What it does for EnterpriseCertIQ |
|---|---|
| `llm-token-limit` | Per-consumer (per-agent counter-key) TPM ceiling. Protects against runaway Critic loops. |
| `llm-semantic-cache-lookup + -store` | Vector-similarity cache via Managed Redis. |
| `llm-content-safety` | Inline content-safety check on prompts and completions. |
| `emit-token-metric` | Tokens per call to App Insights, tagged by subscription, agent, operation. |
| Backend load-balancing | Multiple Foundry / AOAI deployments behind one backend. |

### 4.6 Model Backend Flexibility — Foundry Local + Foundry Cloud

**Why this matters.** The Reasoning track's starter kit explicitly warns: *"Free Azure subscription can have important constraints — limited model access, tight rate limits, regional restrictions."* Iterating prompts and the workflow graph against cloud models burns credits and hits rate limits exactly when you most need to iterate fast (days 4–7). EnterpriseCertIQ is built to **develop entirely on Foundry Local** — free, no rate limits, runs on a laptop — and **swap to Foundry Cloud for the final demo** via a single config flag.

#### 4.6.1 Model choice per environment


| Phase | Backend | Model(s) |
|---|---|---|
| **Dev (days 1–8)** | Foundry Local | Phi-4-mini-reasoning (Microsoft, MIT, 2.15 GB NPU / 2.47–3.15 GB GPU / 4.52 GB CPU) for reasoning agents (Critic, Retrospective). Qwen2.5-coder (Apache 2.0) for tool-calling agents (Curator, Plan Generator) — Foundry Local tags it as chat+tools while Phi-4-mini-reasoning is chat-only. Verify on day 1 with a smoke test. |
| **Final demo (days 9–10)** | Foundry Cloud (via APIM) | GPT-class deployment (or Claude Opus 4.7 in the Foundry catalog) for best reasoning quality. APIM gateway stays in front. |
| *Stretch* | *Foundry Cloud* | *Gemma 4 26B or 31B — available in the Microsoft Foundry catalog via Hugging Face. **Not** yet in Foundry Local as of writing (open issue microsoft/Foundry-Local #589). Don't make Gemma 4 the only path.* |

#### 4.6.2 Single config flag, two endpoints

Same agent code runs against both backends. The chat client is parameterized so swapping is a config change, not a code change.

```python
# env-driven backend selection
# .env (dev):   MODEL_BACKEND=foundry_local
# .env (demo):  MODEL_BACKEND=foundry_cloud

from agent_framework.openai import AzureOpenAIChatClient

if os.getenv('MODEL_BACKEND') == 'foundry_local':
    client = AzureOpenAIChatClient(
        endpoint='http://localhost:5273/v1',     # Foundry Local default
        deployment='phi-4-mini-reasoning-generic-gpu',
        api_key='not-required')
else:  # foundry_cloud
    client = AzureOpenAIChatClient(
        endpoint=APIM_ENDPOINT,                  # APIM → Foundry Cloud
        deployment='enterprisecertiq-gpt',
        default_headers={'Ocp-Apim-Subscription-Key': APIM_KEY})

# Same agents, same workflow, same MCP wiring — just different client.
```

#### 4.6.3 Per-agent model routing (optional)

For finer control during dev: route reasoning-heavy agents to Phi-4-mini-reasoning and tool-calling agents to Qwen2.5-coder, both running in Foundry Local. Same pattern — different client per agent.

```python
phi_client  = local_client('phi-4-mini-reasoning-generic-gpu')   # reasoning
qwen_client = local_client('qwen2.5-coder-0.5b-instruct-generic-gpu')  # tools

critic     = ChatAgent(phi_client,  name='readiness_critic', ...)
curator    = ChatAgent(qwen_client, name='curator',         tools=[...])
planner    = ChatAgent(qwen_client, name='plan_generator',  tools=[...])
```

> ⚠️ **Honest caveats on Foundry Local**
> 
> **Phi-4-mini-reasoning is `chat`-tagged only** in the current Foundry Local catalog; reliable function-calling needs Qwen2.5-coder or a verification on day 1.
> 
> **Smaller models = different behavior.** Phi-4-mini-reasoning (3.8B) reasons well but is not GPT-class. Build the eval suite (§11) on both backends to catch this.
> 
> **Test the cloud swap before day 9.** Run the full demo once on cloud on day 7 or 8 to verify no surprises.

## 5. The Multi-Agent Reasoning Design


### 5.1 Orchestration pattern choice

Same hybrid as v3: **sequential spine + concurrent fan-out + bounded critique loop**. Deliberately fixed and legible — the Reasoning score rewards visible auditable steps, not dynamic-planner cleverness.

| Stage | Pattern | Rationale |
|---|---|---|
| Intake → Curator | Sequential | Each step strictly depends on the previous. |
| Curator (per cert objective) | Concurrent | Multiple cert objectives researched in parallel. |
| Study Plan ↔ Critic | Critique / evaluator loop | Plan proposed; Critic attacks; Plan revised. Bounded N=2 rounds. |
| → Engagement + Assessment | Sequential | Engagement schedules; Assessment evaluates readiness. |
| Manager Insights | Aggregator | Reads structured outputs across team learners. |
| Retrospective (conditional) | Triggered on failure | Investigates root cause; feeds next plan generation. |

### 5.2 The six agents + the retrospective


| Agent | Responsibility | Built-in guardrail |
|---|---|---|
| **1 · Learner Intake** | Parse learner profile + cert target + work context. Output: structured LearnerProfile + CertObjective. | Refuses on missing critical fields; flags rather than invents. |
| **2 · Learning Path Curator** | Map cert target to skill topics; retrieve approved content; surface Microsoft Learn paths. | "No governing source found" returned explicitly. Citation-or-drop on every topic. |
| **3 · Study Plan Generator** | Convert topics into a capacity-aware weekly schedule; allocate study hours; sequence by prerequisite + difficulty. | Plan must fit within learner's available focus hours (Work IQ); overruns surfaced, not hidden. |
| **4 · Engagement Agent** | Schedule reminders adapted to focus windows; trigger re-plan when actual progress deviates from planned trajectory. | Never auto-schedules over user calendar without approval. |
| **5 · Readiness Critic** | Attack the plan: where will this learner most likely fail? Generate assessment questions; compute calibrated readiness forecast. | Honest uncertainty: emits confidence interval; never claims pass probability without evidence. |
| **6 · Manager Insights** | Aggregate team-level readiness; surface capacity conflicts; recommend peer-learning pairs. | No individual scoring exposed that could affect employment decisions. |
| **Retrospective** *(conditional)* | Triggered when a learner fails. Investigates: retrieval quality? plan quality? engagement signals? real skill gap? Writes a postmortem. | Meta-reasoning about the system's own performance — not the learner's. |

> 💡 **Reasoning trail = highest-leverage demo asset**
> Persist every agent's input, intermediate conclusion, tool calls (arguments + result hashes), and Critic objections to Cosmos DB. Render them in the live panel. 25% of the score is "decomposition, planning, and effective agent collaboration" — most teams hide their chain-of-thought; **showing** it is free points.

## 6. Creative Features

Ten features for v1.2 — seven core (in the demo video) and three documented/feature-flagged. Cut list in §15 specifies which are negotiable if the calendar tightens.

### 6.1 Critic-vs-Plan visualization — hero feature

**What it is.** As the Study Plan Generator produces a candidate plan and the Readiness Critic attacks it, the UI renders each plan element as a card and each Critic objection as a 🔴 red sticky note pinned to its target. On the next critique round, resolved objections turn 🟢 green; unresolved ones turn 🟡 amber; plan elements with no surviving support are removed.

**Why it wins.** Most agents hide their reasoning. Showing the Critic literally arguing with the Plan Generator is the single most demo-worthy feature in this product. It hits Reasoning (25%) and UX (15%) at the same time, and makes the audit trail visible rather than asserted.

### 6.2 Planned-vs-actual progress deviation graph

**What it is.** A dual-line chart over the study plan timeline. One line is the **planned trajectory** (cumulative topics mastered per week per the plan). The second is the **actual trajectory** (live, based on assessment scores + engagement signals). The gap between lines IS the deviation. Color bands mark "ahead / on track / at risk / off track." When the gap crosses a threshold, an arrow marks where Engagement Agent re-planning was triggered.

**Why it wins.** This is the visual that ties all six agents together in one image. Judges see **multi-step reasoning playing out over time** — not just at the moment of plan generation. It tells the story words can't.

#### 6.2.1 Data shape (Cosmos `progress_series` container)

```json
{
  "id": "series_L-1004_AZ-204",
  "learner_id": "L-1004",
  "plan_id": "plan_2026_06_12_a3",
  "weeks": [
    { "week": 1, "planned_topics": 4, "actual_topics": 4, "status": "on_track"  },
    { "week": 2, "planned_topics": 8, "actual_topics": 5, "status": "at_risk",
      "signal": "focus_hours_below_plan" },
    { "week": 3, "planned_topics": 12, "actual_topics": 9, "status": "off_track",
      "intervention": { "agent": "engagement", "action": "replan",
        "reason": "3-topic gap exceeds 2-topic threshold" } },
    { "week": 4, "planned_topics": 14, "actual_topics": 13, "status": "on_track",
      "note": "replan recovered trajectory" }
  ]
}
```
Render with Plotly or Recharts in the React dashboard.

### 6.3 Exam-day rehearsal

**What it is.** One-click full timed mock exam. Assessment Agent generates a question set with the same time pressure, question mix, and section weights as the real cert exam, sourced from the Microsoft Learn MCP exam-skills outline. Readiness Critic produces a forecast: "You'd score X on this, weakest area Y."

**Why it wins.** Concrete demo of the whole reasoning chain in under 60 seconds.

### 6.4 Failure-mode retrospective

**What it is.** When a learner fails a mock or real exam, a Retrospective agent investigates **the system's own performance**: was retrieval quality low? Was the plan off-target? Did engagement signals show low actual study hours? Or is the gap a real skill issue? It writes a one-page postmortem that feeds the next plan generation.

**Why it wins.** Meta-reasoning about the system's own failures is rare in AI demos and credible. It demonstrates the "self-reflection and iteration" pattern the criteria explicitly call out.

### 6.5 Confidence-aware question generation

**What it is.** Assessment Agent doesn't generate uniform questions. For topics the system has high confidence the learner knows, fewer/easier questions; for low-confidence topics, more/harder questions. Item-response-theory thinking applied to an AI agent.

**Why it wins.** This is the kind of sophistication that separates a "GPT wrapper" from a thought-through reasoning system.

### 6.6 Peer-learning matchmaker

**What it is.** Manager Insights surfaces peer-learning pairs based on complementary strengths and weaknesses across the team. "L-1004 is strong on networking where L-1007 is weak; L-1007 is strong on security where L-1004 is weak. Suggested study partners." Stub the actual messaging — the recommendation is the demo moment.

**Why it wins.** Real-world value (peer learning is well-evidenced) shown in 10 seconds.

### 6.7 Honest readiness reporting

**What it is.** Readiness Critic outputs three numbers, not one: estimated pass probability, confidence interval, and minimum study hours to close the gap. Plus an explicit "insufficient evidence to forecast" output when warranted.

**Why it wins.** Calibrated uncertainty in an enterprise AI agent is rare.

### 6.8 Domain Mastery Breakdown

**What it is.** After every mock exam (and incrementally during the study path), the Readiness Critic outputs a per-domain mastery breakdown — horizontal bars showing the learner's estimated mastery percentage for each official exam domain, with confidence intervals.

**Why it wins.** The criteria explicitly call out: "Score or interpret readiness based on known certification criteria." Real Microsoft cert exams (AZ-204, DP-203, AZ-400) have published domain weightings. By anchoring the readiness breakdown to those real weights, the system's output is **verifiably accurate against published cert structure**, not made up. Hits Accuracy & Relevance (25%) directly.

**Implementation note.** Microsoft Learn MCP surfaces the exam objectives and domain weightings. The Readiness Critic calls `compute_domain_mastery(learner_id, cert_id)` which joins accumulated evidence against the published domain structure.

#### 6.8.1 Data shape (Cosmos `mastery_grid` container)

```json
{
  "id": "mastery_L-1004_AZ-204",
  "learner_id": "L-1004",
  "cert_id": "AZ-204",
  "updated_at": "2026-06-12T18:04:11Z",
  "domains": [
    { "domain_id": "D1", "name": "Develop Azure compute solutions",
      "weight_pct": 25, "mastery_pct": 78, "confidence": 0.82,
      "evidence_count": 14 },
    { "domain_id": "D2", "name": "Develop for Azure storage",
      "weight_pct": 15, "mastery_pct": 54, "confidence": 0.68,
      "evidence_count": 8 },
    { "domain_id": "D3", "name": "Implement Azure security",
      "weight_pct": 20, "mastery_pct": 41, "confidence": 0.45,
      "evidence_count": 4, "flag": "low_evidence" },
    { "domain_id": "D4", "name": "Monitor and optimize solutions",
      "weight_pct": 15, "mastery_pct": 67, "confidence": 0.71,
      "evidence_count": 9 },
    { "domain_id": "D5", "name": "Connect to and consume services",
      "weight_pct": 25, "mastery_pct": 73, "confidence": 0.79,
      "evidence_count": 12 }
  ]
}
```

### 6.9 Service-level Performance Heatmap

**What it is.** Within each cert domain, finer-grained breakdown by the specific Azure services or topic areas that comprise the domain. Rendered as a 2D heatmap: rows are domains, columns are services/sub-topics, cells colored red (weak)/amber (developing)/green (strong) based on accumulated evidence.

**Why it wins.** This is the visual that turns "you're weak on storage" (unactionable) into "you're weak on Blob Storage lifecycle policies and on Queue Storage triggers — specifically these two" (actionable).

### 6.10 Pass-threshold Awareness

**What it is.** Every Microsoft cert exam has a published passing score (typically 700/1000). The Readiness Critic overlays this threshold on the readiness forecast — not just "you're at 65%" but "you're projected to score 685, 15 points below the 700 pass threshold; gap is concentrated in services X and Y."

**Why it wins.** Closes the loop from probability (abstract) to pass/fail (concrete). By citing the actual passing score from the Microsoft Learn MCP source, the system's forecast becomes **verifiable against the public cert page** — judges can fact-check it themselves.

### 6.11 Future-flagged (not in demo)

- **Cohort pattern learning** — "people who scored low on networking in week 2 tend to fail." Requires synthetic cohort > 10 learners to demo convincingly; stretch goal.
- **Multi-language plan render** — study plans in learner's preferred language. Build cost is modest; ship if days 7–9 allow.

> ⚠️ **Honest scope note (updated for v1.2)**
> This is **ten** features now. Building all ten at full polish in 10 days is not realistic. The **must-ship seven** are: 6.1 Critic-vs-Plan, 6.2 deviation graph, 6.3 exam rehearsal, 6.7 honest readiness, plus the three readiness breakdowns (6.8 domain mastery, 6.9 service heatmap, 6.10 pass-threshold). The **ship-if-possible three** are 6.4 retrospective, 6.5 confidence-aware questions, 6.6 peer matchmaker. §15 makes the cut sequence explicit.

## 7. Engineering Best Practices

Domain-agnostic practices that earn the 40–45% of score on Accuracy + Reliability.

- **7.1 Prompt versioning + eval-gated promotion.** Every prompt in `/prompts/<agent>/vN.md`. CI promotes only if groundedness + citation-coverage don't regress.
- **7.2 Structured outputs everywhere.** Pydantic schemas on every agent. No free-text outputs that aren't parsed.
- **7.3 Span-anchored citations.** Stored as `{doc_id, span_id, char_start, char_end}` — survives reformatting; powers click-to-source.
- **7.4 Idempotency + temperature 0 on Critic.** Same input → same output for validator agents. Bounded loops everywhere.
- **7.5 Calibrated confidence.** Brier score on the golden set; honest probability outputs.
- **7.6 Per-agent token budgets at APIM.** Catches Critic loop blowups before the global ceiling.
- **7.7 Graceful degradation + killswitch.** Circuit breakers around APIM, IQ, MCP. Read-only flag forces draft-only mode.
- **7.8 PII redaction BEFORE cache key.** Otherwise you cache PII. Easy mistake.
- **7.9 Regression test for every red-team finding.** Each fix becomes a permanent eval. Ratchet, not a one-time scan.
- **7.10 Pre-flight check on uploads.** Refuse to index documents that aren't cert content; refusal-to-process is a feature.
- **7.11 Baseline no-op evaluator.** Trivial agent that just echoes the cert objective. If real EnterpriseCertIQ doesn't beat it on every metric, something is broken.
- **7.12 ADRs in the repo.** Short markdown decision records.
- **7.13 One-command repro.** `azd up` deploys APIM, Foundry, Cosmos, App Insights, container, all wired and pre-loaded with synthetic data.
- **7.14 AI-disclosure pattern.** The Reasoning track criteria explicitly require: *"Be transparent that users are interacting with AI."* Every generated artifact (study plan, mock exam, retrospective postmortem, readiness forecast) carries a visible "AI-generated; verify before action" banner. The Manager Insights view explicitly labels recommendations as AI-derived. Demo video calls this out on camera.
- **7.15 Bias audit — must-ship, runs in CI.** The criteria explicitly require: *"Test for bias and uneven outcomes across scenarios."* A custom evaluator on every generated assessment question scans for: gendered/racial stereotypes, role assumptions (e.g. presuming the learner is a junior IC), culturally-narrow examples (e.g. only US holidays/contexts), and ability assumptions. Runs offline in CI on every prompt change. Findings logged to `eval_results`. Not on camera — but a single line in the demo video calls it out: "every generated question passes a bias check before reaching the learner."

## 8. Implementation Skeleton

Illustrative; verify exact signatures against current docs. Install with `pip install agent-framework agent-framework-a2a fastmcp`.

### 8.1 Agent definitions (six + retrospective)

```python
from agent_framework import ChatAgent
from agent_framework.openai import AzureOpenAIChatClient
from agent_framework.mcp import MCPStreamableHTTPTool

client = AzureOpenAIChatClient(
    endpoint=APIM_ENDPOINT, api_version=API_VERSION,
    deployment='enterprisecertiq-gpt',
    default_headers={'Ocp-Apim-Subscription-Key': APIM_KEY})

own_tools   = MCPStreamableHTTPTool(name='enterprisecertiq-tools', url=OWN_MCP_URL)
learn_tools = MCPStreamableHTTPTool(name='ms-learn',
                                    url='https://learn.microsoft.com/api/mcp')

intake   = ChatAgent(client, name='learner_intake',  instructions=INTAKE_PROMPT,  tools=[own_tools], response_format=LearnerProfile)
curator  = ChatAgent(client, name='curator',         instructions=CURATOR_PROMPT, tools=[own_tools, learn_tools])
planner  = ChatAgent(client, name='plan_generator',  instructions=PLAN_PROMPT,    tools=[own_tools])
engager  = ChatAgent(client, name='engagement',      instructions=ENGAGE_PROMPT,  tools=[own_tools])
critic   = ChatAgent(client, name='readiness_critic',instructions=CRITIC_PROMPT,  tools=[own_tools])
manager  = ChatAgent(client, name='manager_insights',instructions=MGMT_PROMPT,    tools=[own_tools])
retro    = ChatAgent(client, name='retrospective',   instructions=RETRO_PROMPT,   tools=[own_tools])
```

### 8.2 Workflow graph

```python
from agent_framework import WorkflowBuilder, ConcurrentBuilder

curator_fanout = ConcurrentBuilder().participants([curator]).build()

workflow = (
  WorkflowBuilder()
    .set_start(intake)
    .add_edge(intake, curator_fanout)
    .add_edge(curator_fanout, planner)
    .add_edge(planner, critic)
    .add_edge(critic, planner, condition=needs_revision, max_loops=2)
    .add_edge(critic, engager,  condition=plan_clean)
    .add_edge(engager, manager)
    .add_edge(manager, retro, condition=any_recent_failure)
    .with_checkpointing(cosmos_checkpoint_store)
    .build())
```

### 8.3 Middleware = global guardrails

```python
async def pii_redaction_mw(context, next):
    context.messages = redact_pii(context.messages)   # before cache key (7.8)
    await next(context)

async def safety_mw(context, next):
    await next(context)
    if flagged(context.result):  context.result = SAFE_REFUSAL

async def citation_gate_mw(context, next):
    await next(context)
    context.result = drop_uncited_claims(context.result)

async def fairness_mw(context, next):
    await next(context)
    if context.agent.name in ('plan_generator', 'critic'):
        context.result = fairness_audit(context.result)   # 7.15 bias check

workflow.use(pii_redaction_mw).use(safety_mw).use(citation_gate_mw).use(fairness_mw)
```

## 9. Cosmos DB Data Model

One Cosmos account (Core/NoSQL). JSON fits structured agent outputs directly.

| Container | Partition key | What it stores |
|---|---|---|
| `study_plans` | `/learner_id` | One document per generated plan: status, doc refs, final draft, approval state. |
| `reasoning_trace` | `/run_id` | Append-only events: each agent input, conclusion, MCP tool calls with args + result hash, Critic objections, timestamps. Powers the live panel. |
| `learner_memory` | `/learner_id` | Per-learner memory: prior cert attempts, preferred study slots, weakest topics. |
| `progress_series` | `/learner_id` | Time series powering the planned-vs-actual deviation graph (6.2). |
| `mastery_grid` | `/learner_id` | Domain × service mastery matrix powering 6.8 and 6.9. |
| `cache` | `/cache_key` | In-app cache complementing the APIM semantic cache. |
| `eval_results` | `/suite_id` | Stored evaluator scores per run (groundedness, citation coverage, bias audit, forecast calibration). |
| `a2a_audit` | `/caller_id` | Inbound A2A requests + outbound A2A calls. Trust-boundary audit log. |
| `team_capacity` | `/team_id` | Synthetic team Work IQ aggregates for the Manager Insights heatmap. |

## 10. Observability

Two signal sources flow into the same App Insights workspace and the Foundry monitoring dashboard:

- **Agent Framework OTel traces:** one span per agent invocation, per MCP tool call, per A2A call. The trace tree mirrors the workflow.
- **APIM emit-token-metric:** prompt/completion/total tokens per call, tagged by subscription, agent, operation.
- **Continuous evaluation:** sample demo traffic; live groundedness + safety scores.

> 💡 **Demo move**
> Foundry monitoring dashboard on a second screen during the live demo. "Here are the traces for that run, here are the groundedness scores, here's the red-team result, here's the live token chart from APIM — all real, all live."

## 11. Evaluation Strategy

Foundry Evaluation SDK offline (CI gate) and continuously (sampled live).

| Evaluator | Measures | Why critical |
|---|---|---|
| Groundedness | Every assessment question / plan recommendation supported by retrieved source | Whole product. #1 gate. |
| Relevance / Coherence | Plan addresses the actual cert objectives | Accuracy score. |
| Retrieval quality | IQ fetched the right material | Bad retrieval = bad plan + bad questions. |
| Tool-call correctness | Right tool, right args, valid result | Multiple MCP tools — essential. Custom evaluator. |
| Content safety | Harmful / unsafe output | Continuous evaluator + APIM content-safety policy. |
| **Custom: citation coverage %** | % of assertions with valid citation | Numeric enforcement of citation-or-drop. Target ≥ 95%. |
| **Custom: forecast calibration** | Brier score on readiness forecasts | Backs up 6.7 honest reporting with a number. |
| **Custom: bias audit** | Question set scanned for stereotypes, role assumptions, cultural narrowness, ability assumptions | RAI requirement (criteria line 481). Built and running in CI per 7.15. |

## 12. Red Teaming & Safety

AI Red Teaming Agent (PyRIT-based) in CI and once more right before demo.

### 12.1 Attack scenarios


| Attack vector | What we verify EnterpriseCertIQ does |
|---|---|
| Prompt injection in indexed cert content | Treated as untrusted data, never as instructions. |
| Malicious A2A caller | Crafted output that tries to bypass citation gate or approval gate is rejected. |
| Fabrication pressure | "Make up a topic that isn't in the cert" → citation-or-drop prevents it. |
| Bias probe | Adversarial prompts trying to elicit biased question generation → fairness middleware catches. |
| Confidence manipulation | "Tell me I'll definitely pass" → honest reporting holds, returns calibrated estimate or insufficient evidence. |
| Token-bomb | Adversarial prompt drives a loop → APIM token-limit hard-stops. |
| PII leakage | Attempts to surface other learners' data → permission-aware IQ + PII middleware block. |

### 12.2 Hard safety invariants

- **No personal employment decisions.** Manager Insights never exposes individual scores in a way that could affect employment. Privacy by design.
- **Citation-or-drop.** Uncited assertions removed, never guessed.
- **Honest uncertainty.** Insufficient evidence → explicit insufficient evidence; not a fabricated number.
- **AI disclosure.** Every generated artifact labelled as AI-derived (per 7.14).
- **Gateway-enforced safety.** APIM content-safety + token limits apply to every path, including A2A callers.

## 13. Synthetic Data & Test Scenarios

**All data is synthetic.** Identifiers follow the criteria's recommended patterns (L-1001, EMP-001, TEAM-A). No real names, no real org data, no PII.

**How the synthetic data is generated.** The criteria explicitly point to **Microsoft Foundry's synthetic data generation feature (Preview)** as a recommended tool. EnterpriseCertIQ uses it to bootstrap the 5 demo scenarios + the larger eval corpus (synthetic learner profiles, prior assessment histories, team capacity signals, cohort outcomes). Hand-authored seed templates feed Foundry's generator; outputs are validated against the synthetic-data guardrails (clearly fabricated IDs, no real names, no real document titles) before they land in the demo set. Using Microsoft's own tool here is a free credibility signal — the data isn't just synthetic, it's synthetic in the way the criteria recommend.

### 13.1 Scenario catalog


| Case | Learner / setup | Why it's a good demo / eval case |
|---|---|---|
| **L1** | L-1004, Cloud Engineer, AZ-204, on-time | Clean win path. Lead the demo here. |
| **L2** | L-1005, DevOps Engineer, AZ-400, tight schedule | Engagement triggers re-plan. Deviation graph lights up. |
| **L3** | L-1006, Data Engineer, DP-203, prior failed attempt | Recovery plan; retrospective postmortem on prior failure. |
| **L4** | L-1007, Cloud Engineer, AZ-204, insufficient evidence | Forecast returns insufficient evidence; honest refusal. |
| **L5** | TEAM-A (5 learners, 3 cert tracks) | Manager Insights heatmap; peer matchmaking; capacity conflict on week 3. |

### 13.2 Sample synthetic learner profile (L-1004)

```json
{
  "learner_id": "L-1004",
  "role": "Cloud Engineer",
  "team_id": "TEAM-A",
  "cert_target": "AZ-204",
  "deadline": "2026-08-15",
  "prior_attempts": [],
  "work_iq_signals": {
    "meeting_hours_per_week": 22,
    "focus_hours_per_week": 10,
    "preferred_learning_slot": "Morning",
    "upcoming_milestones": ["sprint_review_2026-07-10"]
  },
  "prior_assessment_evidence": { "compute": 0.72, "networking": 0.41,
                                 "storage": 0.68, "security": 0.55 }
}
```

### 13.3 Expected golden output (L-1004 plan critique)

```
CRITIC OBJECTIONS:
  [O1] Plan allocates 4h to networking; prior evidence shows 0.41 mastery.
       Recommend doubling to 8h.                ▲ red, citation: plan#wk2
  [O2] Plan week 3 collides with sprint_review_2026-07-10
       (Work IQ signal). Recommend shift to week 4.       ▲ red
  [O3] Sequencing puts security before networking; prerequisite
       graph shows networking is needed first.            ▲ red

  After revision round 1: O1 resolved (8h allocated). ✓ green
                          O2 resolved (shifted).      ✓ green
                          O3 partially resolved.      ⚠ amber

FORECAST: pass probability 0.62, CI ±0.12, weakest area: networking.
          minimum additional study hours to reach 0.75: 6.
```

## 14. 10-Day Build Plan


| Days | Milestone |
|---|---|
| **1–2** | Public GitHub repo with `/prompts/`, `/docs/adr/`, azd-up scaffolding; Foundry project + Cosmos + APIM + Managed Redis provisioned; M365 Developer Program tenant set up. Install Foundry Local; download Phi-4-mini-reasoning and Qwen2.5-coder; smoke-test both for chat and tool-calling. `MODEL_BACKEND` flag wired. Architecture diagram drafted; 5 synthetic scenarios written (using Foundry synthetic data gen); own MCP server scaffold with one tool. Microsoft Learn MCP connectivity smoke-tested. |
| **3** | Stand up APIM AI Gateway policies (token-limit per-agent counter, content-safety, emit-token-metric, semantic-cache); agent client pointed at APIM; PII redaction middleware in place before cache key. |
| **4** | Learner Intake + Curator working end-to-end on L1 via own MCP + Learn MCP; Foundry IQ returning span-anchored citations; pre-flight check on uploads. |
| **5** | Study Plan Generator + Readiness Critic critique loop; `validate_citation` typed tool; citation-or-drop middleware; Cosmos `reasoning_trace` persistence; CRITIC-vs-PLAN visualization (6.1) reading from reasoning_trace — hero feature lands. |
| **6** | Engagement Agent + `progress_series` (6.2 deviation graph); Work IQ integration; React dashboard with split-screen and click-to-source citations; AI-disclosure banner on every artifact (7.14). |
| **7** | Manager Insights + peer matchmaker (6.6); exam-day rehearsal (6.3); honest readiness reporting (6.7); APIM semantic cache enabled and verified; bias audit evaluator wired in CI (7.15). |
| **8** | Three new readiness features land: Domain Mastery Breakdown (6.8), Service-level Heatmap (6.9), Pass-threshold Awareness (6.10) — with Microsoft Learn MCP as the source of cert structure. A2A wrap (A2AExecutor); Hosted Agents deployment (container → ACR → Foundry Agent Service); structured outputs on every agent; calibrated-confidence Brier score in eval dashboard; baseline no-op evaluator (7.11) passing. **First full cloud-swap test:** flip `MODEL_BACKEND` to `foundry_cloud` and verify the demo runs end-to-end. |
| **9** | Failure-mode retrospective agent (6.4); confidence-aware question generation (6.5); AI Red Teaming Agent scan + fix findings (each becomes a regression test, 7.9); killswitch wired and tested; polish UX; rehearse 5-minute demo; warm caches. |
| **10** | Final red-team pass; record demo (≤5 min, YouTube/Vimeo) on cloud backend, covering L1/L2/L3/L5, the deviation graph, the three readiness breakdowns, the Critic-vs-Plan visualization, the HITL approval moment, and the retrospective. Write project description with explicit scenario-alignment statement; finalize architecture diagram + ADRs; submit before 11:59 PM PT June 14. |

## 15. Scope Discipline & Cut List

Honest reality: EnterpriseCertIQ bundles a lot. The cut sequence below is ordered — cut from the top of the list first if the calendar tightens.

### 15.1 Cut order if days 7–9 run tight

1. **First to go:** Multi-language plan render (listed as future-flagged in 6.11). Nice-to-have; doesn't change the core narrative.
2. **Second:** Confidence-aware questions (6.5). Replace with uniform-difficulty questions; lose some originality points but plan/critique loop unaffected.
3. **Third:** Failure-mode retrospective (6.4). Replace with a static "prior attempt analysis" output in the Critic. Lose the meta-reasoning angle but plan still complete.
4. **Fourth:** A2A outbound call to Workforce Capacity. Keep A2A **inbound** (EnterpriseCertIQ hosted as A2A) but drop outbound. Lose composition story.
5. **Fifth:** Peer matchmaker (6.6). Replace with team risk heatmap only. Lose a 10-second demo moment.
6. **Last resort (avoid if possible):** Service-level heatmap (6.9). Replace with domain breakdown only (keep 6.8 and 6.10). Loses granularity but the actionable-readiness story still holds.

### 15.2 Never cut

- **Six core agents + workflow.** This IS the scenario alignment.
- **Foundry IQ + Work IQ.** Two IQ layers is the credibility floor.
- **MCP own server + Microsoft Learn MCP.** The Learn MCP integration is explicitly criteria-aligned and now also powers the readiness breakdowns (6.8, 6.10).
- **APIM AI Gateway with token-limit + content-safety + emit-token-metric.** The production-grade story.
- **Citation-or-drop + structured outputs + span-anchored citations.** The reliability story.
- **Critic-vs-Plan visualization (6.1) + deviation graph (6.2) + exam rehearsal (6.3) + honest readiness (6.7).** The demo arc.
- **Domain Mastery Breakdown (6.8) + Pass-threshold Awareness (6.10).** These anchor readiness to real cert structure via Microsoft Learn MCP.
- **AI-disclosure pattern (7.14) + bias audit in CI (7.15) + HITL approval gate.** All three are explicit RAI requirements from the criteria.
- **Foundry Local + Cloud flexibility (4.6).** Keep `MODEL_BACKEND` config flag working in both directions.
- **Hosted Agents deployment.** Highly-valued by the criteria.
- **One red-team scan + offline eval gate.** The safety story.

### 15.3 Submission must-haves (the rules)

- Working multi-agent system aligned to the scenario
- ≤ 5-minute demo video on YouTube or Vimeo
- Project description (problem, features, tech, safety, explicit scenario-alignment statement)
- Public GitHub repo with ADRs, one-command repro, synthetic-data disclaimer in README
- Architecture diagram showing Agent Framework + MCP + Microsoft Learn MCP + A2A + APIM AI Gateway + Foundry + IQ layers + Cosmos + Hosted Agents
- Synthetic-data disclaimer and clearly fabricated identifiers (L-1001, EMP-001, TEAM-A) everywhere

## 16. Future Work (honestly disclosed, not built)

Listed so a judge skimming the doc sees thought-through roadmap, not feature bloat. None of these are in the demo.

- **Fabric IQ semantic ontology.** Model relationships between employee, role, certification, skill gap, pass threshold, study plan. Sketched approach: a Fabric workspace with a OneLake-backed ontology, queried from the Manager Insights agent for workforce-readiness analytics. Out of scope for 10 days because doing it half-built would break the demo.
- **Cohort pattern learning.** Once enough synthetic outcomes exist, surface patterns: "learners with low networking scores in week 2 tend to fail." Requires > 10 synthetic learner runs to demo convincingly.
- **Multi-language plan render.** Same arguments, different language. Build cost modest; ship if days 7–9 allow.
- **Calendar-aware engagement integration.** Production version would write to actual M365 calendar; demo version stops at suggesting times.

---

*Prepared by Claude · EnterpriseCertIQ v1.2 is the on-scenario pivot of Appealsmith v3, built specifically for the official Reasoning Agents track Core Challenge Scenario after Microsoft confirmed on Discord that submissions must be based on the official scenarios. Architectural choices, engineering practices, and the core multi-agent design pattern carry over from v3. Domain layer (insurance appeals → enterprise learning) is new. Technical claims grounded in Microsoft's Agent Framework 1.0, A2A v1, Foundry, Foundry IQ, Work IQ, Observability, Evaluation SDK, AI Red Teaming Agent, Microsoft Learn MCP, and APIM AI Gateway documentation as of May 26, 2026. API names and policy XML are illustrative — verify exact signatures against current docs during the build. All learner, team, and certification data is synthetic; use no real PII in a public demo or repo.*