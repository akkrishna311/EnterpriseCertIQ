# EnterpriseCertIQ: Local to Azure AI Foundry Migration Guide

## Purpose

This document explains how to move EnterpriseCertIQ from the current local-first developer setup to an Azure-backed architecture using:

- Azure AI Foundry for model inference
- Foundry IQ for grounded enterprise retrieval
- Work IQ for real work-context signals
- Fabric IQ for semantic and business meaning
- Azure-native storage, telemetry, and evaluation

This is not a generic cloud checklist. It is a one-to-one mapping from what this repo does today to the equivalent Azure target state.

## Executive Summary

The repo is already partially prepared for Azure.

- Azure AI Foundry model switching already exists in configuration and in the client factory.
- Foundry IQ has a local mode and an Azure mode, but the Azure retrieval path should be hardened before demo day.
- Work IQ is currently synthetic only. You need a real Azure or Microsoft 365-backed adapter to claim a cloud Work IQ story.
- Fabric IQ is not implemented today. It should be treated as a new semantic layer to add, not as a simple config flip.
- Cosmos DB, Azure evaluation, and Application Insights are already accounted for in the codebase, but they need real Azure resources and environment values.

If your goal is the fastest credible migration path, do the work in this order:

1. Move model inference to Azure AI Foundry.
2. Move grounding to Foundry IQ in Azure.
3. Turn on Application Insights and Azure evaluation.
4. Move persisted state from local JSON to Cosmos DB.
5. Replace synthetic Work IQ with tenant-backed or service-backed work signals.
6. Add a Fabric IQ semantic layer for role, certification, skill, readiness, and manager analytics.

## Current State in This Repo

### Already Azure-aware

| Area | Current State | Azure Readiness |
|---|---|---|
| Model backend | Config supports `foundry_local` and `azure_foundry` | Ready to switch via env |
| Model client | Local uses OpenAI-compatible endpoint, cloud uses `azure-ai-inference` adapter | Implemented |
| Groundedness eval | Local heuristic, Azure path uses `azure-ai-evaluation` | Implemented |
| Telemetry | Local console exporter, Azure Monitor exporter path exists | Implemented |
| Storage | Local JSON and Cosmos abstraction both exist | Implemented, needs resource setup |
| Foundry IQ | Local search implemented, Azure search path exists | Partial |

### Not yet truly cloud-ready

| Area | Current State | What is Missing |
|---|---|---|
| Work IQ | Synthetic data from `backend/data/synthetic/learners.json` | Real Microsoft 365 or Azure-backed context adapter |
| Fabric IQ | Local in-memory ontology implemented (`backend/iq/fabric_iq.py`), used by Critic + Manager | Bind to a Microsoft Fabric semantic model / OneLake (`FABRIC_IQ_ENDPOINT`) |
| Hosted Azure deployment | Local startup flow is strongest path today | Containerized Azure deployment and final smoke test |
| Search ingestion pipeline | Local markdown/json files are read directly | Search indexing pipeline into Azure resources |

## One-to-One Mapping: Local to Cloud

### Runtime and configuration mapping

| Local today | Azure target | Notes |
|---|---|---|
| `MODEL_BACKEND=foundry_local` | `MODEL_BACKEND=azure_foundry` | Main switch for cloud inference |
| `FOUNDRY_LOCAL_ENDPOINT=http://localhost:5273/v1` | `AZURE_AI_PROJECT_ENDPOINT=https://<hub>.api.azureml.ms` | Endpoint moves from laptop to Azure AI Foundry project |
| `FOUNDRY_LOCAL_MODEL_ALIAS` | `AZURE_AI_MODEL_DEPLOYMENT` | Replace local alias with Azure deployment name |
| `FOUNDRY_LOCAL_REASONING_ALIAS` | `AZURE_AI_REASONING_DEPLOYMENT` | Keep separate reasoning model if needed |
| `STORAGE_BACKEND=local` | `STORAGE_BACKEND=cosmos` | Optional at first, recommended for final demo |
| `FOUNDRY_IQ_ENDPOINT=local` | `FOUNDRY_IQ_ENDPOINT=<Azure search or project endpoint>` | Grounding moves from local files to Azure knowledge base |
| `ENABLE_TELEMETRY=false` | `ENABLE_TELEMETRY=true` | Required for Azure proof and observability |
| local JSON files | Cosmos DB containers | State, traces, plans, assessments, interventions |

### Data source mapping

| Local data source | Current purpose | Azure target |
|---|---|---|
| `backend/data/documents/*.md` | Foundry IQ grounding corpus | Azure AI Search or Foundry IQ knowledge sources over Blob, SharePoint, or OneLake |
| `backend/data/synthetic/cert_structures.json` | Cert structure, domains, pass thresholds | Azure AI Search index for retrieval, and optionally Fabric semantic tables for structured analytics |
| `backend/data/synthetic/learners.json` | Learner profile + work signals | Split across profile store, Work IQ sources, and optionally Fabric semantic model |
| `backend/data/synthetic/teams.json` | Team membership and manager mapping | Microsoft 365 group/team source or synthetic profile store in Cosmos/Fabric |
| `backend/data/store/*.json` | App state and workflow outputs | Cosmos DB |

### Code path mapping

| Local code path | What it does now | Cloud target state |
|---|---|---|
| `config/settings.py` | Local/cloud env toggle | Keep as control plane for the migration |
| `backend/core/client.py` | Local model client or Azure inference client | Already correct; validate real deployment names |
| `backend/iq/foundry_iq.py` | Local keyword retrieval over files | Replace file-based retrieval with Azure search-backed retrieval |
| `backend/iq/work_iq.py` | Synthetic work context | Add real adapter using Graph/Work IQ signals or Azure service data |
| `backend/storage/store.py` | Local JSON or Cosmos | Switch to Cosmos for workflow state |
| `backend/evals/groundedness.py` | Heuristic or Azure evaluator | Keep both; use Azure evaluator in cloud runs |
| `backend/core/telemetry.py` | Console or Azure Monitor exporter | Turn on App Insights in Azure |

## What Each Microsoft Layer Means in This App

### 1. Azure AI Foundry

This is the model execution layer.

In EnterpriseCertIQ it powers:

- the six-agent workflow
- the manager what-if simulator narrative outputs
- critic and retrospective reasoning
- structured tool-calling across agents

Your local equivalent today is Foundry Local at `http://localhost:5273/v1`.

Your Azure target is the AI Foundry project endpoint configured through:

- `AZURE_AI_PROJECT_ENDPOINT`
- `AZURE_AI_MODEL_DEPLOYMENT`
- `AZURE_AI_REASONING_DEPLOYMENT`

### 2. Foundry IQ

This is the grounding layer.

In EnterpriseCertIQ it powers:

- learning path curation
- certification guidance retrieval
- grounded question generation
- citation validation

Your local equivalent today is file search over:

- `backend/data/documents/`
- `backend/data/synthetic/cert_structures.json`

Your Azure target is a proper knowledge base indexed in Azure AI Search or the Foundry IQ knowledge plane.

### 3. Work IQ

This is the work-context layer.

In EnterpriseCertIQ it powers:

- available study windows
- meeting load and capacity risk
- engagement timing
- manager capacity and risk analytics
- peer session timing suggestions

Your local equivalent today is synthetic `work_iq_signals` embedded in learner JSON.

Your Azure target is a real adapter that reads Microsoft 365 work context or enterprise work systems and converts that data into the same shape expected by the agents.

### 4. Fabric IQ

This is the semantic layer.

In EnterpriseCertIQ it should power:

- role-to-certification mappings
- skill-domain relationships
- thresholds and business rules
- readiness semantics
- manager analytics over cohorts, gaps, trends, and interventions

**Update:** Fabric IQ now has a local runtime — `backend/iq/fabric_iq.py` builds an
in-memory ontology from the synthetic datasets and is consumed at runtime by the
Readiness Critic (leverage-weighted objections) and Manager Insights (team skill-gap
meaning, cohort benchmarks, intervention effectiveness). The remaining Azure work is to
bind the same `FabricIQClient` contract to a Microsoft Fabric semantic model / OneLake
when `FABRIC_IQ_ENDPOINT` is set, instead of reading local JSON.

## Recommended Migration Phases

## Phase 1: Move Model Inference to Azure AI Foundry

### Goal

Keep the app behavior the same while moving only the model calls from local to Azure.

### Why do this first

This is the smallest cloud migration with the highest credibility gain. The repo already supports it.

### What to provision

1. Azure AI Foundry project
2. One default model deployment
3. Optionally one reasoning-specific deployment

### Repo changes

No major code changes should be required.

You mainly need:

1. `pip install -r requirements.azure.txt`
2. a populated `.env.azure` or `.env.local`
3. real deployment names for the two Azure model variables

### Environment mapping

```dotenv
MODEL_BACKEND=azure_foundry
AZURE_AI_PROJECT_ENDPOINT=https://your-hub.api.azureml.ms
AZURE_AI_API_KEY=...
AZURE_AI_MODEL_DEPLOYMENT=gpt-4o
AZURE_AI_REASONING_DEPLOYMENT=gpt-4o
AZURE_USE_MANAGED_IDENTITY=false
```

### Validation

1. `/health` reports `backend: azure_foundry`
2. a workflow run completes end to end
3. tool-calling still works
4. the critic still returns structured outputs

## Phase 2: Move Grounding from Local Documents to Foundry IQ in Azure

### Goal

Replace file-based retrieval with Azure-backed grounded retrieval.

### Local to cloud mapping

| Local | Azure |
|---|---|
| `backend/data/documents/cert_guide.md` | Blob, SharePoint, or OneLake source indexed into AI Search |
| `backend/data/documents/team_report.md` | Same as above |
| `backend/data/synthetic/cert_structures.json` | Search index and optionally Fabric tables |

### Recommended target architecture

1. Store the approved learning corpus in one Azure source:
   - Azure Blob Storage for the simplest start
   - SharePoint if you want a stronger enterprise content story
   - OneLake if you want alignment with Fabric from the beginning
2. Create one Azure AI Search index for retrieval.
3. Point `FOUNDRY_IQ_ENDPOINT` and `FOUNDRY_IQ_INDEX_NAME` at that cloud resource.

### Code impact

`backend/iq/foundry_iq.py` already has an Azure branch, but it should be tightened.

Recommended hardening:

1. Use `azure-search-documents` or `azure-ai-projects` directly instead of a hand-built HTTP call.
2. Remove silent local fallback during final demo mode so Azure failures are visible.
3. Preserve the existing `SearchResult` shape so the rest of the app does not change.

### Validation

1. Curator agent returns citations from Azure-indexed docs.
2. `validate_citation` still succeeds.
3. The mock exam generator uses Azure-grounded content.
4. No retrieval depends on local markdown files anymore.

## Phase 3: Move App State from Local JSON to Cosmos DB

### Goal

Persist workflow traces and business state in Azure rather than flat files.

### Local to cloud mapping

| Local JSON store | Cosmos container |
|---|---|
| `study_plans.json` | `study_plans` |
| `reasoning_trace.json` | `reasoning_trace` |
| `assessments.json` | `assessments` |
| `mastery_grid.json` | `mastery_grid` |
| `progress_series.json` | `progress_series` |
| `peer_learning_sessions.json` | `peer_learning_sessions` |
| `manager_interventions.json` | `manager_interventions` |

### Code impact

Very low. `backend/storage/store.py` already abstracts local and Cosmos modes.

### Environment mapping

```dotenv
STORAGE_BACKEND=cosmos
COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443/
COSMOS_KEY=...
COSMOS_DATABASE=enterprisecertiq
```

### Validation

1. workflow traces persist and reload correctly
2. assessments survive app restarts
3. manager interventions and peer sessions persist in Azure

## Phase 4: Replace Synthetic Work IQ with Real Work Context

### Goal

Stop reading work signals only from `learners.json` and start deriving them from real enterprise work systems.

### What the repo does today

`backend/iq/work_iq.py` simply reads the learner profile, then derives:

- meeting hours per week
- focus hours per week
- preferred learning slot
- milestone pressure
- recommended study slots
- capacity risk

That logic is useful and should stay. What must change is the source of the input signals.

### Recommended source mapping

| Current field in local learner JSON | Azure or Microsoft 365 target source |
|---|---|
| `learner_id` | Entra ID user id or synthetic identity key |
| `team_id` | Microsoft 365 group, Teams team, or synthetic team table |
| `role` | HR system, Fabric dimension table, or synthetic profile store |
| `deadline` | App-owned schedule record in Cosmos/Fabric |
| `meeting_hours_per_week` | Graph calendar aggregation |
| `focus_hours_per_week` | Derived metric from work telemetry or internal logic |
| `preferred_learning_slot` | User preferences store or inferred usage pattern |
| `upcoming_milestones` | Planner, Azure DevOps, Jira, or synthetic workload feed |
| `available_study_hours_per_week` | Derived field computed by Work IQ adapter |

### Practical implementation recommendation

Create a second adapter in `backend/iq/work_iq.py` or a sibling module with this contract:

```python
class AzureWorkIQClient:
    async def get_work_context(self, learner: LearnerProfile) -> WorkContext:
        ...

    async def get_team_context(self, team_id: str, learners: list[LearnerProfile]) -> dict:
        ...
```

The key design rule is this:

- do not change the `WorkContext` output shape
- only change where the underlying signals come from

That lets the Engagement Agent, Manager Insights, and readiness logic continue to work.

### Minimum viable cloud Work IQ story

If you do not have access to a real Microsoft 365 tenant, use this fallback approach:

1. keep learner identity and certification profile in Cosmos or Fabric
2. import synthetic but cloud-hosted calendar/workload signals into Cosmos
3. have `AzureWorkIQClient` read those signals from Azure instead of local JSON

This is still better than local files because the app becomes cloud-backed even if the data remains synthetic.

## Phase 5: Add Fabric IQ as the Semantic Layer

### Goal

Give the app a business meaning layer instead of relying only on heuristics and raw JSON.

### Why this matters

Foundry IQ answers "what approved content exists?"

Work IQ answers "what is happening in a person's work context?"

Fabric IQ should answer "what do these entities, rules, relationships, and metrics mean for enterprise learning decisions?"

### What to model semantically

Recommended entities:

- Learner
- Team
- Manager
- Role
- Certification
- Skill Domain
- Study Plan
- Assessment Attempt
- Readiness Forecast
- Intervention
- Peer Session

Recommended relationships:

- learner belongs to team
- learner has role
- role recommends certification
- certification contains skill domains
- assessment measures skill domain
- intervention targets learner
- peer session improves weak domain
- readiness forecast depends on evidence and work context

### Recommended Azure implementation

Use Microsoft Fabric for the semantic foundation:

1. OneLake or Lakehouse for synthetic and app-produced datasets
2. Fabric Warehouse or Lakehouse tables for normalized learner, assessment, and intervention data
3. Semantic model or ontology layer for business relationships and metrics
4. A query layer consumed by the backend for manager insights and critic reasoning

### Local to cloud mapping for Fabric IQ

| Current local structure | Fabric target |
|---|---|
| `cert_structures.json` | Certification and skill-domain dimension tables |
| `learners.json` | Learner, team, role, target-cert dimensions |
| `cohort_outcomes.json` | Historical benchmark fact table |
| `assessments` store | Assessment fact table |
| `progress_series` store | Progress fact table |
| `manager_interventions` store | Intervention fact table |

### Repo change recommendation

Add a dedicated module such as:

- `backend/iq/fabric_iq.py`

That module should expose functions like:

- `get_role_certification_map(role_id)`
- `get_domain_thresholds(cert_id)`
- `get_team_skill_gap_summary(team_id)`
- `get_intervention_effectiveness(team_id)`

### Where Fabric IQ should be used in this app

1. Manager Insights: semantic team skill gap analysis
2. Readiness Critic: role-aware reasoning and threshold semantics
3. Assessment generation: better domain weighting and scenario balance
4. What-if simulator: cohort-based intervention effect estimates

## Phase 6: Turn On Azure Evaluation and Observability

### Goal

Make the cloud system measurable and demo-ready.

### What already exists

- `backend/evals/groundedness.py` can use `azure-ai-evaluation`
- `backend/core/telemetry.py` can export to Application Insights

### Environment mapping

```dotenv
ENABLE_TELEMETRY=true
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
```

### Validation

1. Application Insights shows workflow spans
2. agent spans include run id and cert id
3. groundedness evaluations use the Azure evaluator in cloud mode

## Phase 7: Deploy the App in Azure

### Practical recommendation

For this codebase, the easiest deployment path is:

1. Backend to Azure Container Apps or App Service
2. Frontend to Azure Static Web Apps, App Service, or Container Apps
3. Cosmos DB for persistence
4. Azure AI Foundry for models
5. Azure AI Search for Foundry IQ
6. Application Insights for telemetry

### Important distinction

Using Azure AI Foundry for models does not automatically mean the entire application is running as a Hosted Agent in Azure AI Foundry Agent Service.

Right now this repo is a FastAPI application with a React frontend and an agent runtime inside the backend. That is fine. You can migrate inference and IQ layers first, then decide whether Hosted Agent Service is necessary.

## Recommended Detailed Rollout Plan

### Step 1: Create Azure environment

Provision:

1. Azure AI Foundry project
2. one default model deployment
3. one reasoning deployment if needed
4. Azure AI Search
5. Cosmos DB
6. Application Insights
7. storage account or OneLake-backed ingestion source

### Step 2: Install Azure packages locally

```bash
source .venv/bin/activate
pip install -r requirements.azure.txt
```

### Step 3: Create `.env.azure`

Start from `.env.example` and populate the Azure fields.

Recommended first cloud test:

```dotenv
MODEL_BACKEND=azure_foundry
STORAGE_BACKEND=local
FOUNDRY_IQ_ENDPOINT=local
ENABLE_TELEMETRY=false
```

That isolates model switching first.

### Step 4: Switch Foundry IQ to Azure

After model inference works, change:

```dotenv
FOUNDRY_IQ_ENDPOINT=https://<your-search-or-project-endpoint>
FOUNDRY_IQ_INDEX_NAME=cert-knowledge-base
```

### Step 5: Switch storage to Cosmos

After retrieval works, move state to Cosmos.

### Step 6: Add Azure Work IQ adapter

Only after inference, retrieval, and persistence are stable.

### Step 7: Add Fabric IQ semantic layer

Treat this as a feature addition, not as environment setup.

## Suggested Local-to-Cloud Milestones

| Milestone | What changes | Risk |
|---|---|---|
| M1 | Model backend only | Low |
| M2 | Foundry IQ in Azure | Medium |
| M3 | Cosmos storage | Low |
| M4 | App Insights + Azure eval | Low |
| M5 | Work IQ adapter | Medium |
| M6 | Fabric IQ semantic layer | High |

## Minimal Cost Path vs Full Cloud Path

### Minimal cost but credible

Use Azure only for:

1. Azure AI Foundry model deployments
2. Foundry IQ grounding
3. Application Insights
4. Azure evaluation

Keep these temporarily local or synthetic:

1. state storage
2. Work IQ signals
3. Fabric IQ semantic model

### Full Microsoft story

Use Azure for:

1. model inference
2. grounding
3. persistence
4. telemetry
5. evaluation
6. work-context layer
7. semantic layer

## Final Recommendation for This Repo

If you want the most effective next steps from where the code is today:

1. Switch the model backend to Azure AI Foundry first.
2. Move Foundry IQ to Azure Search or Foundry-backed retrieval second.
3. Turn on Application Insights and Azure evaluation third.
4. Switch persistent state to Cosmos fourth.
5. Build an Azure-backed Work IQ adapter fifth.
6. Build Fabric IQ as a semantic service sixth.

That order preserves velocity and maps cleanly onto the architecture that already exists in the repo.

## Acceptance Checklist

You can say the app has moved from local-first to Azure-backed when all of the following are true:

- model calls use Azure AI Foundry instead of Foundry Local
- grounding comes from Azure-indexed sources instead of local files
- workflow state persists in Cosmos instead of local JSON
- telemetry appears in Application Insights
- groundedness eval uses Azure evaluation in cloud mode
- Work IQ signals come from Azure or Microsoft 365-backed sources
- Fabric IQ exposes semantic relationships and is used by at least one runtime path

Until the last two are complete, it is accurate to say:

- Azure AI Foundry is active
- Foundry IQ is active
- Work IQ is still synthetic or partially cloud-backed
- Fabric IQ is planned or in progress

That is the honest and technically accurate migration story for this codebase.