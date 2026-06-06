# Testing Guide: Local-First → Azure (Foundry IQ · Work IQ · Fabric IQ)

A hands-on, command-by-command guide to take EnterpriseCertIQ from the fully-local
synthetic setup to a real Azure-backed deployment, and to **prove** each Microsoft IQ
layer is actually live (not simulated). Each phase ends with a *verification* you can show
a judge.

> **Golden rule:** change **one layer at a time** and verify before moving on. The repo is
> built so each switch is a config change, not a rewrite.

Legend for current code readiness:
- 🟢 **Runnable today** — code path exists; you only provision + set env.
- 🟡 **Adapter needed** — a small, well-scoped code addition is required (contract already defined).

---

## Phase 0 — Local baseline (all synthetic, zero cloud cost) 🟢

This is your control. Everything works offline with Foundry Local + the in-memory IQ layers.

```bash
cd enterprisecertiq
cp .env.example .env.local        # if not already present
```

`.env.local` (local defaults):
```dotenv
MODEL_BACKEND=foundry_local
FOUNDRY_LOCAL_ENDPOINT=http://localhost:5273/v1
FOUNDRY_LOCAL_MODEL_ALIAS=qwen2.5-7b
STORAGE_BACKEND=local
FOUNDRY_IQ_ENDPOINT=local
FABRIC_IQ_ENDPOINT=local
ENABLE_TELEMETRY=false
```

Run and test:
```bash
./start.sh                         # first run installs deps + downloads model
source .venv/bin/activate
pytest -q                          # 29 tests should pass
```

**Verify each IQ layer locally:**
```bash
# Foundry IQ (grounded retrieval over local docs)
curl -s localhost:8000/api/cert-structures/AZ-204 | head -c 200

# Fabric IQ (semantic ontology) — via the manager insights payload
curl -s localhost:8000/api/manager/TEAM-A/insights | python3 -m json.tool | grep -A3 fabric_iq

# Work IQ (work-context signals) — embedded in the same payload
curl -s localhost:8000/api/manager/TEAM-A/insights | python3 -m json.tool | grep -i capacity
```

Run a full workflow and watch all agents (incl. the Fabric-aware Critic) in the UI at
**http://localhost:5173**, or:
```bash
curl -s -X POST localhost:8000/api/workflow/run \
  -H 'content-type: application/json' \
  -d '{"learner_id":"L-1004"}' | python3 -m json.tool
```

✅ **Baseline proven** when: 29 tests pass, the manager payload contains a `fabric_iq`
block, and a workflow run completes with a critic objection that references domain leverage.

---

## Phase 1 — Move model inference to Azure AI Foundry 🟢

The highest-credibility, lowest-effort switch. Only the *model calls* move to Azure.

### Provision
1. Create an **Azure AI Foundry** project (portal: ai.azure.com → New project).
2. Deploy a model (e.g. `gpt-4o`) — note the **deployment name**.
3. Copy the **project endpoint** (Settings → Project details).

```bash
source .venv/bin/activate
pip install -r requirements.azure.txt
```

### Configure — create `.env.azure` (loaded automatically; see `config/settings.py`)
```dotenv
MODEL_BACKEND=azure_foundry
AZURE_AI_PROJECT_ENDPOINT=https://<your-hub>.api.azureml.ms
AZURE_AI_API_KEY=<key>                 # or leave empty + AZURE_USE_MANAGED_IDENTITY=true
AZURE_AI_MODEL_DEPLOYMENT=gpt-4o
AZURE_AI_REASONING_DEPLOYMENT=gpt-4o
# keep everything else local for now:
STORAGE_BACKEND=local
FOUNDRY_IQ_ENDPOINT=local
FABRIC_IQ_ENDPOINT=local
ENABLE_TELEMETRY=false
```

> `.env.local` overrides `.env.azure` (load order in `settings.py`). For a clean Azure test,
> either delete/rename `.env.local` or set `MODEL_BACKEND=azure_foundry` in it.

### Run + verify
```bash
./start.sh --no-setup --skip-model     # no local model needed in Azure mode
curl -s localhost:8000/health          # expect backend: azure_foundry
```
Run a workflow (as in Phase 0) and confirm:
- it completes end-to-end,
- tool-calling still works (curator calls `foundry_iq_search`, critic calls `fabric_iq_semantics`),
- the critic returns structured JSON.

✅ **Proven** when `/health` reports `azure_foundry` and a full run succeeds against the cloud model.

---

## Phase 2 — Foundry IQ: real grounded retrieval on Azure AI Search 🟢

Replace local keyword search with an Azure AI Search index. The Azure branch already exists
in `backend/iq/foundry_iq.py` (`_search_azure`).

### Provision
```bash
# Create a search service
az search service create -g <rg> -n <search-name> --sku basic -l <region>

# Get the admin key + endpoint
az search admin-key show -g <rg> --service-name <search-name>
# endpoint = https://<search-name>.search.windows.net
```

### Ingest the synthetic corpus
Create one index (fields: `id`, `title`, `content`, `source_url`) and upload the approved
docs so retrieval is grounded in *indexed* content, not local files:
- `backend/data/documents/cert_guide.md`
- `backend/data/documents/team_report.md`
- `backend/data/synthetic/cert_structures.json` (one doc per cert/domain)

Easiest path: portal → **Import data** → upload the markdown/JSON to a Blob container →
index it; or use the `azure-search-documents` SDK to push documents. Name the index to match
`FOUNDRY_IQ_INDEX_NAME`.

### Configure
```dotenv
FOUNDRY_IQ_ENDPOINT=https://<search-name>.search.windows.net
FOUNDRY_IQ_INDEX_NAME=cert-knowledge-base
AZURE_AI_API_KEY=<search-admin-key-OR-reuse-foundry-key>
```
> Note: `_search_azure` currently authenticates with `azure_ai_api_key` as the Search
> `api-key` header. Use the Search admin key here, or harden the client to take a dedicated
> `AZURE_SEARCH_KEY` (recommended — see migration doc Phase 2 hardening).

### Verify it's *really* Azure
```bash
# Ask the curator to ground a topic, then confirm citations carry a source_url
curl -s -X POST localhost:8000/api/workflow/run -H 'content-type: application/json' \
  -d '{"learner_id":"L-1004"}' | python3 -m json.tool | grep -i source_url
```
Then temporarily point `FOUNDRY_IQ_ENDPOINT` at a **wrong** index name — retrieval should
degrade/fail (proving it's hitting Azure, not local files). Restore afterwards.

✅ **Proven** when curator/assessment citations resolve to Azure-indexed documents
(`source_url` populated) and `validate_citation` succeeds against them.

---

## Phase 3 — Work IQ: real work-context signals 🟡

Today `backend/iq/work_iq.py` derives signals (meeting load, focus hours, capacity risk,
study slots) from synthetic `learners.json`. The **logic stays**; only the **source** changes.

### Option A — Minimum viable cloud Work IQ (no M365 tenant required) 🟡
1. Put the synthetic work signals in Cosmos (Phase 5) or a Blob/table.
2. Add an `AzureWorkIQClient` alongside `WorkIQClient` with the **same `WorkContext` shape**:
   ```python
   class AzureWorkIQClient:
       async def get_work_context(self, learner) -> WorkContext: ...
       async def get_team_context(self, team_id, learners) -> dict: ...
   ```
3. Select it in `get_work_iq()` when an Azure source is configured.

This is "cloud-backed but synthetic" — honest and demoable.

### Option B — Real Microsoft 365 signals (needs a tenant) 🟡
Use **Microsoft Graph** to derive the same fields:
- `meeting_hours_per_week` → aggregate `/me/calendarView` over a week.
- `focus_hours_per_week` → Graph **Insights**/Viva or a derived metric.
- `preferred_learning_slot`, `upcoming_milestones` → user prefs / Planner / DevOps.

Register an Entra app, grant `Calendars.Read`, acquire a token, and populate `WorkIQSignals`
from Graph responses inside `AzureWorkIQClient`.

### Verify
```bash
curl -s localhost:8000/api/manager/TEAM-A/insights | python3 -m json.tool | grep -i ai_disclosure
# Should read "...derived from Microsoft 365 / Azure work signals" once the adapter is live,
# instead of "...synthetic Work IQ signals".
```

✅ **Proven** when the Engagement Agent's recommended slots and the manager's capacity-risk
flags change in response to *cloud-sourced* signals, with the disclosure string updated.

> **Honest framing for judges:** until Option A or B ships, state plainly that "Work IQ is
> synthetic." The `WorkContext` contract is the integration seam — agents don't change.

---

## Phase 4 — Fabric IQ: real semantic model on Microsoft Fabric 🟡

Today `backend/iq/fabric_iq.py` builds the ontology in-memory from the synthetic JSON and is
already used by the Critic + Manager + the `fabric_iq_semantics` MCP tool. To make it
*cloud Fabric*, bind the **same `FabricIQClient` method contract** to a Fabric semantic model.

### Provision
1. Create a **Microsoft Fabric** workspace (Lakehouse or Warehouse).
2. Load the synthetic data as tables in **OneLake**:
   | Local file | Fabric table |
   |---|---|
   | `cert_structures.json` | `dim_certification`, `dim_skill_domain` (weight, min_mastery) |
   | `learners.json` | `dim_learner`, `dim_role` |
   | `cohort_outcomes.json` | `fact_cohort_outcome` |
   | `assessments` store | `fact_assessment` |
   | `manager_interventions` store | `fact_intervention` |
3. Build a **semantic model** capturing the relationships in `describe_ontology()`
   (learner→team, role→cert, cert→domain, domain→weight/threshold, advances_to, etc.).

### Configure
```dotenv
FABRIC_IQ_ENDPOINT=https://<fabric-sql-endpoint-or-onelake>
FABRIC_IQ_WORKSPACE=<workspace-name>
```

### Adapter (the only code change)
In `fabric_iq.py`, branch on `self.s.fabric_iq_endpoint != "local"` inside each query method
(mirror the Foundry IQ local/Azure split). Keep the **return shapes identical** so the Critic,
Manager, and MCP tool are unchanged. Suggested queries to push down to Fabric SQL:
- `get_domain_thresholds(cert_id)` → `SELECT … FROM dim_skill_domain WHERE cert_id=…`
- `get_cohort_benchmark(cert_id)` → aggregate `fact_cohort_outcome`
- `get_team_skill_gap_summary(...)` → join `fact_assessment` × `dim_skill_domain`
- `get_intervention_effectiveness(...)` → `fact_intervention` × outcomes

### Verify it's *really* Fabric
```bash
# domain thresholds should now come from the semantic model
curl -s -X POST localhost:8001/...  # or via the agent trace: critic's fabric_iq_semantics call
# Easiest: hit the manager insights endpoint and confirm cohort_benchmarks sample_size
# matches the Fabric fact table row count, not the 7 local cohort rows.
curl -s localhost:8000/api/manager/TEAM-A/insights \
  | python3 -m json.tool | grep -A2 sample_size
```
Add a row to `fact_cohort_outcome` in Fabric and confirm `sample_size`/`pass_rate` shifts
without touching local JSON.

✅ **Proven** when Fabric IQ outputs change in response to Fabric table edits and the
`ai_disclosure` reflects the Fabric source.

---

## Phase 5 — Persistence (Cosmos), Telemetry (App Insights), Eval 🟢

All three code paths already exist.

### Cosmos DB
```bash
az cosmosdb create -g <rg> -n <cosmos-name>
az cosmosdb keys list -g <rg> -n <cosmos-name> --type keys
```
```dotenv
STORAGE_BACKEND=cosmos
COSMOS_ENDPOINT=https://<cosmos-name>.documents.azure.com:443/
COSMOS_KEY=<key>
COSMOS_DATABASE=enterprisecertiq
```
Verify: run a workflow, restart the backend, reload the trace — it persists from Cosmos.

### Application Insights + Azure groundedness eval
```dotenv
ENABLE_TELEMETRY=true
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
```
Verify: run a workflow, then in the Azure portal → Application Insights → **Transaction
search**, confirm `workflow.run` and `agent.<name>` spans appear with `run_id` + `cert_id`.
Groundedness eval auto-uses `azure-ai-evaluation` in Azure mode (`backend/evals/groundedness.py`).

---

## Phase 6 — Host the app on Azure 🟡

```text
Backend  → Azure Container Apps (or App Service)
Frontend → Azure Static Web Apps
Models   → Azure AI Foundry      (Phase 1)
Grounding→ Azure AI Search        (Phase 2)
Semantic → Microsoft Fabric       (Phase 4)
State    → Cosmos DB              (Phase 5)
Telemetry→ Application Insights    (Phase 5)
```
Containerise the FastAPI backend, push to ACR, deploy to Container Apps; build the Vite
frontend and deploy to Static Web Apps with the backend URL as its API base.

---

## One-glance switch matrix

| Layer | Local setting | Azure setting | Code today |
|---|---|---|---|
| Model | `MODEL_BACKEND=foundry_local` | `MODEL_BACKEND=azure_foundry` | 🟢 |
| Foundry IQ | `FOUNDRY_IQ_ENDPOINT=local` | `=https://<search>.search.windows.net` | 🟢 |
| Work IQ | synthetic `learners.json` | `AzureWorkIQClient` (Graph/Cosmos) | 🟡 adapter |
| Fabric IQ | `FABRIC_IQ_ENDPOINT=local` | `=<Fabric/OneLake endpoint>` | 🟡 adapter |
| Storage | `STORAGE_BACKEND=local` | `=cosmos` | 🟢 |
| Telemetry | `ENABLE_TELEMETRY=false` | `=true` + conn string | 🟢 |

## Minimum credible Azure demo (lowest cost)
1. Phase 1 (model) + Phase 2 (Foundry IQ) + Phase 5 (App Insights + eval).
2. Keep Work IQ synthetic and Fabric IQ local — but **say so honestly**.
3. That already gives: real Foundry models, real grounded retrieval with citations,
   real telemetry, real evaluation, all 3 IQ layers present (1 cloud + 2 local-but-real).

## Full Microsoft story
Add Phase 3 (Work IQ adapter) + Phase 4 (Fabric semantic model) + Phase 6 (hosting).
At that point all three IQ layers are cloud-backed and the app runs entirely on Azure.
