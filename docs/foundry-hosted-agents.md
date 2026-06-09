# Foundry Agent Service — Agents, Tracing & Evaluations

The authoritative runbook for the Foundry side of EnterpriseCertIQ, based on the Foundry
docs (answers A–E). Covers what's **already implemented in code** and the **manual Azure
steps** you run (they need `az login` + RBAC, which can't be done from the build sandbox).

## TL;DR recommendation

**Use the ephemeral agent pattern, not a hosted container.** Per the docs, a Hosted Agent
container is **not required** to "use Foundry" — calling the Agent Service SDK from our
existing app (agents + threads + tools + tracing + evals) satisfies the criteria, works in
our region, and is far less effort. Hosted-container deployment is preview and region-limited
(East US 2 / Sweden Central) — keep it as an optional stretch (recipe at the bottom).

## RBAC (do this first)

| Need | Role | Scope |
|---|---|---|
| Create/list/run agents, view evals & traces | **Foundry User** (min) | project or resource |
| Deploy hosted agents, manage eval templates, assign agent identity roles | **Foundry Project Manager** | project |

Local dev: `az login` with one of the above is enough (`DefaultAzureCredential`). In Azure,
the app's managed identity needs the same role.

## Region gate (check this)

Agents only work where the **Azure OpenAI Responses API** is available. Confirm the
`agenticaifoundrypoc` project's region supports it. Hosted *containers* specifically require
**East US 2 or Sweden Central**.

## What's implemented in code (done)

| Piece | Where | Status |
|---|---|---|
| Token-only auth for the agents plane | `foundry_orchestration._get_project_client` → `DefaultAzureCredential` (API keys rejected per docs) | ✅ fixed |
| Agent registration + thread per run | `FoundrySession` / `register_all_agents` (8 named agents + orchestrator) | ✅ (create-or-`update_agent`; SDK 1.1.0 has no `create_version`) |
| Model field = **deployment name** | `gpt-4.1` (fast) / `gpt-5.4-mini` (reasoning) | ✅ |
| GenAI/agent tracing | `telemetry.instrument_foundry_agents()` → `AIAgentsInstrumentor().instrument()` + `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true` | ✅ |
| Per-call + agent + model + tool spans → App Insights | OTel + Azure Monitor exporter | ✅ verified |
| Foundry evaluations | `scripts/run_foundry_eval.py` (`azure_ai_project=<project endpoint>`) | ✅ runs; `--upload` publishes |

## Step 1 — Register the agents (portal-visible)

```bash
az login                       # Foundry User or Project Manager
# start the backend in azure mode; on startup register_all_agents() creates/updates
# the 8 agents + orchestrator in the project (no-op without auth)
./start.sh --no-setup --skip-model
```
Then: **AI Foundry → aipoc → Agents** shows `eciq-orchestrator`, `eciq-learner-intake`,
`eciq-learning-path-curator`, … Each workflow run creates a **thread** under that agent.

## Step 2 — Tracing in the portal

1. Portal: **AI Foundry → aipoc → Agents → Traces → Connect** → select your Application
   Insights (`84673b88…`).
2. Grant the **project managed identity** `Log Analytics Reader` on that App Insights resource
   **and** its linked Log Analytics workspace.
3. Code already calls `AIAgentsInstrumentor().instrument()` + sets
   `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true`, and includes the agent reference on runs.
4. Run a workflow → traces appear under the **Tracing** tab (and in App Insights →
   Transaction search / Application map).

## Step 3 — Evaluations in the portal

```bash
az login                       # Foundry User (view) / Project Manager (templates)
python scripts/run_foundry_eval.py --upload
```
- Judge is forced to **gpt-4.1** (gpt-5/o reject the evaluator's `max_tokens`).
- `azure_ai_project` = the **project endpoint string** (new project type; the
  `{subscription_id,...}` dict form is only for legacy hub projects).
- `evaluate(data=<jsonl>)` uploads the dataset inline; results appear under the
  **Evaluation** tab. (Optionally pre-upload the JSONL as a versioned Data asset.)

## MCP tools with Foundry agents (when you want server-side tool calls)

Foundry agents can call our MCP server natively, but `server_url` must be **public HTTPS** —
localhost is unreachable from Foundry. Options:
- **Now (no public URL):** keep tool execution client-side (our orchestrator runs the tools);
  agents/threads still show in the portal.
- **Later:** host the FastMCP server publicly, then register it as an MCP tool with
  `server_url` + `server_label` (unauthenticated → no `project_connection_id` needed; add one
  only if you put auth in front of it).

## Optional stretch — Hosted Agent container (preview)

Only if you want the pipeline to run *as a managed Foundry endpoint*:
1. Implement the Foundry runtime: `pip install azure-ai-agentserver-responses` (conversational)
   or `azure-ai-agentserver-invocations` (generic). These serve on **port 8088** and provide
   `/readiness` automatically — wrap our pipeline as the handler.
2. Build x86_64/linux/amd64 image → push to **ACR** (must stay publicly reachable).
3. Create an **agent version** (SDK/REST) registering the image URL + size
   (0.5 vCPU/1 GiB · 1/2 · 2/4) + env vars. Foundry pulls it, provisions compute, assigns a
   **system-assigned managed identity**, and exposes a stable endpoint.
4. Secrets via project connections: `${{connections.<name>.credentials.key}}` → injected as
   env vars (don't hard-code).
5. Versions are **immutable**; **scale-to-zero** after 15 min idle (state persisted 30 days).
6. Regions: **East US 2 / Sweden Central** only (preview).

## Native v2.x path (when/if you upgrade the SDK)

Confirmed from the docs (Q1–Q12). This is the "full Foundry-native" upgrade — **optional**;
the 1.x register-and-mirror path above already satisfies the criteria.

**SDK upgrade required** (`azure-ai-projects`):
- **2.0.0+** for A2A + MCP tools; **2.1.0+** for Hosted Agents + `create_version`.
- v2 **absorbs** `azure-ai-agents`/`azure-ai-inference`/`azure-ai-ml` into the unified project client.
- Breaking: **Hubs→Projects**, **Threads/Runs→Conversations/Responses**, `create_agent()`→
  `create_version()`, and tracing uses **`AIProjectInstrumentor`** (not our current
  `AIAgentsInstrumentor`).

**Tools — our local executors stay (Q1).** The Responses API supports **client-side function
tools**: the response returns a `function_call` item → our code executes it → we append a
`function_call_output` item and call `responses.create()` again. So we do **not** have to
publicly host the MCP server to ground via Foundry agents.

**Responses API shape (Q3):**
```python
client = project_client.get_openai_client()
resp = client.responses.create(model="gpt-4.1", input=..., tools=[...],
                               conversation=conversation_id, stream=False,
                               extra_body={"agent_reference": {"name": a.name, "id": a.id,
                                                               "type": "agent_reference"}})
# loop: for item in resp.output: if function_call → execute locally → append
#       function_call_output to the conversation → responses.create() again
```
- State = **Conversations + Responses** (not threads/runs). Streaming via `stream=True`.
- **Trace correlation (Q6):** pass `agent_reference` in `extra_body`; call
  `AIProjectInstrumentor().instrument()`.

**MCP tool (Q7), when the server is publicly hosted:**
```python
MCPTool(server_label="enterprisecertiq", server_url="https://<host>/mcp",
        require_approval="never")          # project_connection_id only if authed
# schemas auto-discovered via tools/list; filter with allowed_tools=[...]
```

**A2A orchestration (Q4/Q5):**
- `A2APreviewTool(name=..., description=..., project_connection_id=...)` — sub-agents are
  referenced by a **Project Connection ID** pointing to the target agent's endpoint, so each
  sub-agent must be **separately registered/hosted** first.
- Works in **both** ephemeral and hosted patterns. (Legacy "Connected Agents" is gone.)

**Hosted container (Q10–Q12), only if pursued:**
- Handler: `azure-ai-agentserver-responses`, register a `@app.response_handler` taking
  `(request, context, cancellation_signal)`, return `TextResponse` or `ResponseEventStream`;
  serves on **8088** with `/readiness` auto-provided.
- Deploy: `project.agents.create_version(agent_name, definition=HostedAgentDefinition(
  image=..., cpu=..., memory=..., container_protocol_versions=[...], environment_variables={...}))`.
- Secrets via **project connections** (`category RemoteTool`/`RemoteA2A`):
  `${{connections.<name>.credentials.<field>}}` placeholders in `environment_variables` resolve
  to env vars at sandbox start.

**Continuous evaluation (Q8):** beyond batch `evaluate()`, Foundry supports **evaluation rules**
(Python SDK) that auto-run evaluators when an agent response completes — wire after the upgrade
for live agent-quality dashboards.

## Honest status for the submission

- "Uses Microsoft Foundry": ✅ via the Agent Service SDK (agents + threads) + Azure OpenAI
  inference + Foundry IQ grounding.
- Tracing in portal: ✅ once App Insights is connected (Step 2) — code side done.
- Evaluations in portal: ✅ via `--upload` (Step 3) — code side done.
- Hosted Agent container: optional/preview — recipe above; not required by the criteria.
