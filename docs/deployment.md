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
RG=enterprisecertiq-rg
LOC=eastus
az group create -n $RG -l $LOC

# Container registry
ACR=ecirq$RANDOM
az acr create -g $RG -n $ACR --sku Basic --admin-enabled true
az acr login -n $ACR

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
az acr build -r $ACR -t enterprisecertiq-backend:latest .
az acr build -r $ACR -t enterprisecertiq-frontend:latest ./frontend
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
    AZURE_AI_PROJECT_ENDPOINT=https://<hub>.api.azureml.ms \
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

## Alternative: frontend on Azure Static Web Apps

You can host the SPA on **Static Web Apps** instead of a frontend container — build with
`npm run build` and deploy `frontend/dist`, then add a route rule proxying `/api/*` to the
backend Container App. Container Apps for both is simpler because the nginx proxy already
handles SSE.
