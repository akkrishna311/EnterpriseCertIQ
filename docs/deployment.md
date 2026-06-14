# Deployment Guide — EnterpriseCertIQ on Azure

Get a **live, public, judge-clickable** deployment. The app containerises into two
images (backend FastAPI + frontend nginx/SPA) and runs on **Azure Container Apps**, with
Azure AI Foundry for models. This mirrors the live-demo edge that wins demo rooms.

> The fastest credible path is **backend + frontend on Container Apps + Azure AI Foundry
> models**. Storage stays local JSON unless you want Cosmos; IQ layers run as documented.

## 0. Local container smoke test (do this first)

```bash
# Backend
docker build -t enterprisecertiq-backend .
docker run --rm -p 8000:8000 --env-file .env.local \
  -e MODEL_BACKEND=azure_foundry enterprisecertiq-backend
curl -s localhost:8000/health | python3 -m json.tool   # check iq_layers, content_safety, llm_cache

# Frontend (point at the backend)
docker build -t enterprisecertiq-frontend ./frontend
docker run --rm -p 5173:80 -e BACKEND_URL=http://host.docker.internal:8000 enterprisecertiq-frontend
open http://localhost:5173
```

## 1. Provision Azure resources

```bash
RG=rg_genai
LOC=eastus2
az acr create -g $RG -n eciqregistry --sku Basic --location $LOC --admin-enabled true
az acr login -n eciqregistry

# Container Apps environment
az extension add --name containerapp --upgrade
az containerapp env create -g $RG -n eciq-env -l $LOC
```

Provision (per the migration guide) as needed:
- **Azure AI Foundry** project + a `gpt-4o` deployment → model inference
- **Azure AI Search** + index → Foundry IQ grounding
- **Azure AI Content Safety** resource → live RAI guardrail
- **Application Insights** → telemetry
- (optional) **Cosmos DB** → persistence
- (optional) **Microsoft Fabric** workspace → Fabric IQ semantic model

## 2. Build & push images

```bash
az acr build -r eciqregistry -t enterprisecertiq-backend:latest .
az acr build -r eciqregistry -t enterprisecertiq-frontend:latest ./frontend
```

## 3. Deploy the backend

```bash
az containerapp create -g $RG -n eciq-backend \
  --environment eciq-env \
  --image $ACR.azurecr.io/enterprisecertiq-backend:latest \
  --registry-server $ACR.azurecr.io \
  --target-port 8000 --ingress external \
  --min-replicas 1 --max-replicas 2 \
  --secrets azure-key=<AZURE_AI_API_KEY> search-key=<AZURE_SEARCH_KEY> \
            cs-key=<AZURE_CONTENT_SAFETY_KEY> appi=<APPINSIGHTS_CONN_STRING> \
  --env-vars \
    MODEL_BACKEND=azure_foundry \
    AZURE_AI_PROJECT_ENDPOINT=https://<your-hub>.services.ai.azure.com/api/projects/<your-project> \
    AZURE_AI_API_KEY=secretref:azure-key \
    AZURE_AI_MODEL_DEPLOYMENT=gpt-4o \
    AZURE_AI_REASONING_DEPLOYMENT=gpt-4o \
    FOUNDRY_IQ_ENDPOINT=https://<search>.search.windows.net \
    FOUNDRY_IQ_INDEX_NAME=cert-knowledge-base \
    AZURE_SEARCH_KEY=secretref:search-key \
    FABRIC_IQ_ENDPOINT=local \
    AZURE_CONTENT_SAFETY_ENDPOINT=https://<cs>.cognitiveservices.azure.com \
    AZURE_CONTENT_SAFETY_KEY=secretref:cs-key \
    ENABLE_TELEMETRY=true \
    APPLICATIONINSIGHTS_CONNECTION_STRING=secretref:appi \
    ENABLE_LLM_CACHE=true

BACKEND_URL=$(az containerapp show -g $RG -n eciq-backend \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "Backend: https://$BACKEND_URL"
```

Verify: `curl -s https://$BACKEND_URL/health` → `backend: azure_foundry`, `content_safety: azure`.

## 4. Deploy the frontend

```bash
az containerapp create -g $RG -n eciq-frontend \
  --environment eciq-env \
  --image $ACR.azurecr.io/enterprisecertiq-frontend:latest \
  --registry-server $ACR.azurecr.io \
  --target-port 80 --ingress external \
  --min-replicas 1 --max-replicas 2 \
  --env-vars BACKEND_URL=https://$BACKEND_URL

FRONTEND_URL=$(az containerapp show -g $RG -n eciq-frontend \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "Live app: https://$FRONTEND_URL"
```

The nginx template proxies `/api` and `/health` to `$BACKEND_URL` (SSE buffering off,
so the live reasoning stream works through the proxy).

## 5. Post-deploy verification (show a judge)

1. `https://$FRONTEND_URL` loads the dashboard.
2. Run a workflow for **L-1004** → live reasoning trace streams (SSE through nginx).
3. `/health` shows `iq_layers` (foundry_iq/work_iq/fabric_iq), `content_safety: azure`,
   and `llm_cache` hit-rate climbing on a repeat run.
4. Download a **Learner Readiness PDF** and a **Manager Handoff Brief PDF**.
5. Application Insights → Transaction search shows `workflow.run` + `agent.*` spans.

## Cost control

- `--min-replicas 1` keeps it warm for demos; set to 0 to scale-to-zero between demos.
- The **LLM response cache** means repeat demo runs cost ~0 tokens.
- Keep `FABRIC_IQ_ENDPOINT=local` and storage local to avoid extra spend; everything still
  runs. Flip to cloud per the migration guide when you want the full Azure story.

## 6. Foundry Agent Service — Hosted Agent deployment

Deploy EnterpriseCertIQ as a **Hosted Agent** in Foundry Agent Service so the pipeline
runs as a managed agent endpoint rather than a self-hosted container app.

This satisfies the "Hosted Agents in Foundry Agent Service" recommendation and gives you:
- A dedicated Microsoft Entra-managed agent identity
- Platform-managed scaling, session state, and lifecycle
- Agents visible and traceable in the Azure AI Foundry portal

### Prerequisites

```bash
# Ensure azure-ai-projects SDK is installed
pip install azure-ai-projects
```

### Step 1: Build and push to Azure Container Registry

```bash
# Build the backend image (same Dockerfile, same image)
az acr build -r $ACR -t enterprisecertiq-hosted-agent:latest .
```

### Step 2: Register agent definitions in Foundry

At startup (when `MODEL_BACKEND=azure_foundry`), EnterpriseCertIQ automatically calls
`register_all_agents()` from `backend/core/foundry_orchestration.py`, which registers
all 8 pipeline agents in Foundry Agent Service using the `azure-ai-projects` SDK:

```
eciq-orchestrator      eciq-learner-intake      eciq-learning-path-curator
eciq-study-plan-generator  eciq-readiness-critic  eciq-engagement-agent
eciq-assessment-agent  eciq-manager-insights  eciq-retrospective
```

Each workflow run creates a Foundry Agent thread visible in the portal at:
**AI Foundry → Your Project → Agents → Threads**

### Step 3: Deploy as a Hosted Agent (Container Apps-based)

```bash
# Create a Foundry-managed Container Apps job for the backend
az containerapp job create \
  --name eciq-hosted-agent \
  --resource-group $RG \
  --environment eciq-env \
  --image $ACR.azurecr.io/enterprisecertiq-hosted-agent:latest \
  --registry-server $ACR.azurecr.io \
  --trigger-type Manual \
  --replica-timeout 600 \
  --env-vars \
    MODEL_BACKEND=azure_foundry \
    AZURE_AI_PROJECT_ENDPOINT=https://<your-hub>.services.ai.azure.com/api/projects/<your-project> \
    AZURE_AI_MODEL_DEPLOYMENT=gpt-4o \
    AGENT_FALLBACK_MODE=auto \
    ENABLE_TELEMETRY=true \
    APPLICATIONINSIGHTS_CONNECTION_STRING=secretref:appi
```

### Step 4: Verify agent registration

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

client = AIProjectClient(
    endpoint="https://<hub>.api.azureml.ms",
    credential=DefaultAzureCredential(),
)
agents = list(client.agents.list_agents())
print([a.name for a in agents])
# ['eciq-orchestrator', 'eciq-learning-path-curator', ...]
```

### What judges see in the portal

1. **Agents tab** — 8 named EnterpriseCertIQ agents with descriptions and instructions
2. **Threads tab** — one thread per workflow run, with structured messages from each stage
3. **Traces tab** — OpenTelemetry spans from each `agent.*` and `workflow.run` scope

## Alternative: frontend on Azure Static Web Apps

You can host the SPA on **Static Web Apps** instead of a frontend container — build with
`npm run build` and deploy `frontend/dist`, then add a route rule proxying `/api/*` to the
backend Container App. Container Apps for both is simpler because the nginx proxy already
handles SSE.
