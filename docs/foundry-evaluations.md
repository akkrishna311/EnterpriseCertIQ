# Azure AI Foundry Evaluations

How EnterpriseCertIQ produces **evaluation results visible in the Foundry portal** — the
hackathon "show evaluation results in Foundry" requirement.

## What it is

We run the `azure-ai-evaluation` SDK with LLM-judge evaluators over a dataset of grounded
agent responses, then publish the run to the Foundry project so it appears under
**AI Foundry → your project → Evaluation**.

Evaluators used (1–5 scale):
- **Groundedness** — is the answer supported by the retrieved context (Foundry IQ)?
- **Relevance** — does it address the learner's question?
- **Coherence** — is it logically structured?
- **Fluency** — language quality.

## ✅ Already verified locally

`python scripts/run_foundry_eval.py` produced (gpt-4.1 judge, 6-row dataset):

| Metric | Mean (of 5) |
|---|---|
| groundedness | 4.17 |
| relevance | 4.50 |
| coherence | 3.67 |
| fluency | 2.17 |

Files:
- `backend/data/eval/eval_dataset.jsonl` — `query` / `response` / `context` / `ground_truth`
  rows (grounded agent answers across AZ-204, AI-102, DP-203, AI-900).
- `scripts/run_foundry_eval.py` — runs the evaluators and (with `--upload`) publishes to Foundry.

## What's needed to show results IN the Foundry portal

### 1. A gpt-4.x judge deployment (NOT gpt-5/o-series)
The evaluator SDK sends `max_tokens`, which gpt-5.4-mini / o-series reject. The script forces
the judge to `AZURE_EVAL_JUDGE_DEPLOYMENT` (default **`gpt-4.1`**) — independent of the agent
models. `gpt-4.1` is deployed on your resource, so this is already satisfied.

### 2. Azure auth for the upload
Publishing to the portal uses `DefaultAzureCredential`:
```bash
az login    # the only thing missing in this environment
```
(In Azure/Container Apps a managed identity covers this — no `az login` needed.)

### 3. The project endpoint (already in .env)
`AZURE_AI_PROJECT_ENDPOINT=https://agenticaifoundrypoc.services.ai.azure.com/api/projects/aipoc`
is passed as `azure_ai_project` so results upload to that project.

### 4. Run it with `--upload`
```bash
source .venv/bin/activate
az login
python scripts/run_foundry_eval.py --upload
# prints a "Foundry portal:" studio URL when the upload succeeds
```

### What judges then see in the portal
**AI Foundry → aipoc → Evaluation** → a named run with per-metric scores (groundedness,
relevance, coherence, fluency), per-row detail, and the dataset. Pair this with the **Tracing**
tab (App Insights, see below) for the full observability story.

## Agent-specific evaluators (multi-agent quality)

In addition to the quality metrics above, run the **agent evaluators** — they measure how well
a *multi-agent* system behaves, which is exactly our scenario:

```bash
python scripts/run_foundry_eval.py --mode agent            # local scores
python scripts/run_foundry_eval.py --mode agent --upload   # publish to Foundry
```

| Evaluator | Measures | Inputs (dataset columns) |
|---|---|---|
| **Intent Resolution** | Did the agent understand + resolve the user's intent? | `query`, `response` |
| **Tool Call Accuracy** | Right tools, right arguments? | `query`, `response`, `tool_calls`, `tool_definitions` |
| **Task Adherence** | Did it stay on the assigned task? | `query`, `response`, `tool_definitions` |

Dataset: `backend/data/eval/agent_eval_dataset.jsonl` (real agent responses + tool-call traces
for curator/assessment/critic/engagement). Judge = gpt-4.1. Verified producing scores locally.
These are the metrics that best show tool grounding + specialised-agent quality to judges.

## Optional: evaluate live agent output
The committed dataset is representative grounded output. To evaluate *fresh* agent responses,
regenerate the dataset from a workflow run (curator/assessment responses + their Foundry IQ
context) and point `--dataset` at it. The schema is the same four columns.

## Relationship to the in-app evaluator
`backend/evals/groundedness.py` runs a lightweight groundedness check *inline* on every
curator/critic output (heuristic locally; it auto-skips the Azure LLM judge for gpt-5/o
deployments to avoid the `max_tokens` issue). The Foundry evaluation here is the **formal,
portal-visible** batch evaluation for the submission.

## Telemetry (companion to evaluations)

App Insights tracing is live (`ENABLE_TELEMETRY=true` + connection string). Every run emits:
- `workflow.run` (top span) → `agent.<name>` → `model.call` / `tool.call` child spans
- one **request** span per HTTP API call (FastAPI auto-instrumentation)

See them in **Application Insights → Transaction search / Application map**, or linked under the
Foundry project's **Tracing** tab. Verified: spans transmit successfully
(`Transmission succeeded: Items accepted`).
