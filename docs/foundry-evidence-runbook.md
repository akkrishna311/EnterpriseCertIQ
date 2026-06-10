# Foundry "evidence" runbook — make the agents + traces visible for judges

The top projects score on a **visible, real Foundry footprint**: agents in the portal, a traced
run, and (CertForge) a hosted endpoint. You don't need a hosted container — registered agents +
a portal trace + an evaluation run already evidence "real Foundry." This is the ~15-minute path.

## 0. Prereqs
- `az login` (your user; needs **Foundry User** or **Project Manager** on the `aipoc` project).
- Confirm the project region is in the Responses-API list (e.g. East US 2 / Sweden Central).
- `pip install -r requirements.azure.txt` (installs azure-ai-projects ≥ 2.1.0).

## 1. Register the 8 agents (portal-visible)
```bash
az login
./start.sh --no-setup --skip-model      # lifespan calls register_all_agents()
```
- `/health` → `foundry_agents: native` (v2) or `mirror` (v1). Either registers the agents.
- **Screenshot:** AI Foundry → **aipoc → Agents** showing `eciq-orchestrator`,
  `eciq-learner-intake`, `eciq-learning-path-curator`, `eciq-readiness-critic`, … (9 agents).

## 2. Capture a traced run
1. Portal: **Agents → Traces → Connect** → select your Application Insights
   (`InstrumentationKey=84673b88…`). Grant the project identity **Log Analytics Reader** on it.
2. Run a workflow (UI **Build My Plan**, or `POST /api/workflow/run`).
3. **Screenshot:** the **Tracing** tab / App Insights **Transaction search** showing the
   `workflow.run → agent.* → model.call / tool.call` span tree.

## 3. Evidence the Foundry IQ grounding (already real)
```bash
python - <<'PY'
import asyncio; from backend.iq.foundry_iq import get_foundry_iq
r = asyncio.run(get_foundry_iq()._search_azure("AZ-204 compute Azure Functions", 3))
[print(x.doc_id, round(x.score,2), x.source_url) for x in r]
PY
```
- **Screenshot:** BM25 scores (7–9) + real `learn.microsoft.com` source URLs = live Azure AI Search.

## 4. Publish the evaluation results
```bash
python scripts/run_readiness_eval.py            # LOO AUC 0.80 headline → readiness_eval.json
python scripts/run_foundry_eval.py --upload      # groundedness + agent evaluators → Foundry Evaluation tab
```
- **Screenshot:** the **Evaluation** tab in the portal + the `run_readiness_eval` output.

## 5. (Optional stretch) Fabric IQ live in the playground
- Foundry → Build → agent → Tools → **Fabric IQ (OneLake Catalog)** → your Ontology → ask a
  readiness question → **screenshot** the cited answer. (Needs the BYO-app connection + admin consent,
  or Managed OAuth — see docs/fabric-data-agent.md.)

## What to attach to the submission
1. Agents-tab screenshot (9 agents)  2. Tracing screenshot  3. Foundry IQ scores+URLs
4. Evaluation tab + readiness AUC  5. (optional) Fabric IQ playground answer
→ That set matches/【exceeds】 the evidence the top-3 projects show.
