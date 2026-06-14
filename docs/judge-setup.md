# EnterpriseCertIQ — Judge Setup Guide

This guide walks competition judges through deploying EnterpriseCertIQ on their own Azure AI Foundry subscription and running the full agent pipeline end-to-end.

---

## Prerequisites

| Requirement | Version / Notes |
|---|---|
| Python | 3.11 or 3.12 (3.13 works but use 3.12 for best compatibility) |
| Azure CLI | `az --version` ≥ 2.60 |
| Azure subscription | Any subscription with Azure AI Foundry access |
| `az login` | Must be logged in before running any scripts |
| Git | To clone the repo |

---

## Step 1 — Clone and create virtual environment

```powershell
git clone <repo-url>
cd EnterpriseCertIQ
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate          # Mac/Linux
```

Install dependencies:

```powershell
pip install -r requirements.txt
pip install "azure-ai-projects>=2.2.0" "azure-identity>=1.19.0" "azure-keyvault-secrets>=4.8.0"
```

---

## Step 2 — Create an Azure AI Foundry project

1. Go to [ai.azure.com](https://ai.azure.com) → **Create project**
2. Choose **East US** region (required for the Responses API agent endpoint)
3. Deploy a model: **gpt-4.1** (or gpt-4o) — note the deployment name
4. From **Settings → Project details**, copy the **Project endpoint**:
   `https://<hub>.services.ai.azure.com/api/projects/<project>`

---

## Step 3 — Configure `.env.local`

Copy the template and fill in your values:

```powershell
copy .env.example .env.local     # Windows
# cp .env.example .env.local     # Mac/Linux
```

Edit `.env.local`:

```env
MODEL_BACKEND=azure_foundry

AZURE_AI_PROJECT_ENDPOINT=https://<your-hub>.services.ai.azure.com/api/projects/<your-project>
AZURE_OPENAI_ENDPOINT=https://<your-hub>.openai.azure.com/openai/v1
AZURE_AI_API_KEY=<your-project-api-key>
AZURE_AI_MODEL_DEPLOYMENT=gpt-4.1
AZURE_AI_REASONING_DEPLOYMENT=gpt-4.1

FOUNDRY_IQ_ENDPOINT=https://<your-search-service>.search.windows.net
FOUNDRY_IQ_INDEX_NAME=cert-knowledge-base
AZURE_SEARCH_KEY=<your-search-admin-key>
FOUNDRY_SEARCH_CONNECTION_NAME=<search-connection-name-from-foundry-portal>

FOUNDRY_USE_RESPONSES_API=true

ENABLE_TELEMETRY=false
```

> **Note:** `FOUNDRY_USE_RESPONSES_API=true` routes the curator, readiness-critic, and assessment agents through the registered Foundry agents (with Knowledge Base retrieval). The other 6 agents use the Azure OpenAI endpoint directly.

---

## Step 4 — Set up Foundry IQ Knowledge Base (Azure AI Search)

The app uses an Azure AI Search index named `cert-knowledge-base` as its grounding knowledge base.

1. Create an **Azure AI Search** resource in your subscription
2. Create an index named `cert-knowledge-base` (or use the provided import scripts in `scripts/`)
3. In Foundry portal → **Settings → Connections**, add your Search resource as a connection
4. Copy the connection name into `FOUNDRY_SEARCH_CONNECTION_NAME` in `.env.local`
5. In Foundry portal → **Knowledge bases**, create a knowledge base pointing to the index

---

## Step 5 — Register agents, skills, and toolbox

Run the three registration scripts **in order**. Each step depends on the previous.

```powershell
# Log in to Azure
az login

# Step A: Register the 3 governance skills in Foundry
python scripts/register_skills.py

# Step B: Register the governance Toolbox (bundles the 3 skills for portal visibility)
python scripts/register_toolbox.py

# Step C: Register all 9 agents with KB connections and governance instructions
python scripts/register_agents_cloud_shell.py
```

After Step C, open the Foundry portal to verify:
- **Build → Skills**: `eciq-readiness-rubric`, `eciq-citation-policy`, `eciq-safety-escalation`
- **Build → Tools**: `eciq-governance-toolbox` (bundles all 3 skills)
- **Agents**: 9 agents, each with KB MCPTool connections and governance instructions embedded

---

## Step 6 — Start the backend

```powershell
.venv\Scripts\uvicorn backend.main:app --reload --port 8000
```

Check the health endpoint:
```
GET http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "backend": "azure_foundry",
  "foundry_agents": "native",
  "foundry_responses_api": "enabled"
}
```

---

## Step 7 — Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## Optional: Azure Key Vault for secret management

If you want secrets managed by Azure Key Vault instead of `.env.local`:

1. Create a Key Vault in your subscription
2. Grant your user the **Key Vault Secrets Officer** role on the vault:
   ```powershell
   az role assignment create \
     --role "Key Vault Secrets Officer" \
     --assignee <your-object-id> \
     --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<vault-name>
   ```
3. Add secrets (Key Vault uses hyphens, not underscores):
   ```powershell
   az keyvault secret set --vault-name <vault> --name "azure-ai-api-key"            --value "<value>"
   az keyvault secret set --vault-name <vault> --name "azure-search-key"            --value "<value>"
   az keyvault secret set --vault-name <vault> --name "speech-key"                  --value "<value>"
   az keyvault secret set --vault-name <vault> --name "appinsights-connection-string" --value "<value>"
   ```
4. Add to `.env.local`:
   ```env
   AZURE_KEY_VAULT_URL=https://<vault-name>.vault.azure.net/
   ```

The backend loads all secrets from Key Vault at startup and overrides the `.env.local` values automatically.

---

## Architecture: How the Foundry agents work

```
User request
    │
    ▼
Backend (FastAPI) ──► WorkflowOrchestrator
                            │
              ┌─────────────┼─────────────┐
              │             │             │
        Curator        Critic      Assessment
        (Responses    (Responses   (Responses
         API)          API)         API)
              │
   ┌──────────┴──────────┐
   │ Foundry Agent       │
   │ - Instructions      │
   │   (+ skill governa- │
   │    nce injected)    │
   │ - KB MCPTool ───────┼──► Foundry IQ Knowledge Base
   │   (cert or Fabric)  │    (Azure AI Search / Fabric IQ)
   └─────────────────────┘

Other 6 agents (orchestrator, intake, planner,
engagement, manager, retrospective):
   Direct Azure OpenAI call via AZURE_OPENAI_ENDPOINT
   (governance instructions injected, no KB retrieval needed)
```

**Skill governance** is embedded directly into each agent's `instructions` field — no runtime dependency on the Toolbox MCP connection. The Toolbox (`Build → Tools` in portal) serves as a central governance registry for visibility and CI/CD updates.

---

## Known Limitations (Preview)

### 1. Toolbox MCPTool fails during Responses API server-side execution
**Issue:** When a Foundry Prompt Agent is invoked via the Responses API, it uses the **agent's own managed identity** to call outbound MCP servers. The Toolbox consumer endpoint requires `Foundry-Features: Toolboxes=V1Preview` header AND the agent's managed identity must have the **Foundry User** role assigned at project scope. Without this RBAC assignment, the Toolbox call returns 401.

**Workaround (applied):** Skill governance content is injected directly into each agent's `instructions` field via `_with_skills()` in `register_agents_cloud_shell.py`. The Toolbox exists as a portal-visible registry (`Build → Tools`) but is not wired as an MCPTool at runtime.

**If you want to enable the Toolbox at runtime:** Assign the **Foundry User** role to each agent's managed identity at the project scope, then set `"toolbox": True` in `register_agents_cloud_shell.py` and re-run it.

### 2. Skills API `default_version` promotion not available in preview
**Issue:** The `POST .../skills/{name}/versions` API creates new skill versions successfully, but there is no programmatic endpoint to promote a version to `default_version` in the current preview. The first version created is automatically the default.

**Workaround:** For fresh judge installs, the first version registered is automatically `default_version` — no action needed. To promote a later version, use: Foundry portal → **Build → Skills → \<skill\> → Set as default**.

### 3. Hosted Agent containers require East US 2 or Sweden Central
**Issue:** `HostedAgentDefinition` (Docker container-based agents) is a preview feature only available in the **East US 2** and **Sweden Central** regions. East US is not supported.

**Workaround:** This submission uses `PromptAgentDefinition` (the Responses API path), which works in **East US**. Container-based hosting is not required for the competition judging criteria.

### 4. `azure-ai-projects` SDK v2.x requires `allow_preview=True` for agent endpoint
**Issue:** Calling `AIProjectClient.get_openai_client(agent_name=...)` raises an error unless `allow_preview=True` is passed to the `AIProjectClient` constructor. This feature is explicitly marked as preview.

**Workaround (applied):** `AIProjectClient(..., allow_preview=True)` is set in `backend/core/foundry_grounded_agent.py`.

### 5. API key authentication rejected for agent-specific endpoints
**Issue:** The Foundry agent endpoint (`{project_endpoint}/agents/{name}/endpoint/...`) requires a **real Entra Bearer token** (DefaultAzureCredential / managed identity). Project API keys work for direct OpenAI endpoints only, not for agent-scoped endpoints.

**Workaround (applied):** `DefaultAzureCredential` (via `az login` locally, managed identity in Azure) is used for all agent calls. API keys are only used for the direct `AZURE_OPENAI_ENDPOINT` path.

---

## Verification checklist for judges

After completing setup, verify each item:

- [ ] `GET /health` returns `"foundry_agents": "native"` and `"foundry_responses_api": "enabled"`
- [ ] Foundry portal → Agents: 9 agents visible with KB connections on curator, critic, assessment, retrospective, and study-plan agents
- [ ] Foundry portal → Build → Skills: 3 skills registered
- [ ] Foundry portal → Build → Tools: `eciq-governance-toolbox` visible with 3 skills
- [ ] Run a workflow: select a learner → click **Run** → SSE stream shows 7+ stages completing
- [ ] Curator agent response includes `【source】` citation markers (KB retrieval confirmed)
- [ ] Plan Review tab shows critic objections with severity ratings
- [ ] Assessment tab generates practice questions with source citations
- [ ] Manager tab shows team readiness distribution and ROI cost-of-delay

---

*Generated for EnterpriseCertIQ competition submission — June 2026*
