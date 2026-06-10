# Fabric IQ — build the Ontology + Data Agent (tailored to our tables)

Detailed, copy-paste runbook for Step 5, grounded in the current Microsoft docs:
- Ontology: https://learn.microsoft.com/fabric/iq/ontology/tutorial-1-create-ontology
- Data agent: https://learn.microsoft.com/fabric/data-science/how-to-create-data-agent

Assumes Step 1–4 are done (workspace + Lakehouse `enterprisecertiq` with the 11 Delta tables).

## ⚠️ Correct integration path (read first)

Two facts from the Foundry/Fabric docs decide the architecture:
1. **Reading OneLake tables via the SQL endpoint is NOT "using Fabric IQ"** — Fabric IQ means
   hitting the semantic layers (ontology/NL2Ontology, data agent, or Power BI semantic model).
   So the `FABRIC_SQL_*` path in `fabric_iq.py` is a **Lakehouse data fallback, not a Fabric IQ
   integration** — don't claim Fabric IQ for it.
2. **Fabric IQ is user-delegated (OBO) auth ONLY — service principals are explicitly NOT
   supported.** Audience `https://analysis.windows.net/powerbi/api`; ontology scopes
   `Item.Execute.All` + `Item.Read.All`; data-agent scope `DataAgent.Execute.All`. Therefore a
   headless backend SPN (`get_service_credential("fabric")`) **cannot** call Fabric IQ.

**=> The integration path is a Foundry agent with the Fabric IQ (OneLake Catalog) tool pointed
at your Ontology, running OBO the signed-in user** — not a backend SPN call.

**Prereqs — a BYO Entra app** (the connection authenticates with this; OBO uses it at runtime):
- Register (or reuse) an Entra app. Grant **delegated** Fabric permissions
  `https://analysis.windows.net/powerbi/api/Item.Execute.All` + `Item.Read.All`, grant admin
  consent. Note its **client ID + client secret**.
- From the Ontology's URL in the Fabric portal, note its **workspace_id** and **artifact_id** (GUIDs).

**Steps:**
1. **Foundry → Management center → Connected resources → + Connection → Microsoft Fabric (Fabric
   IQ)** → enter **client ID, client secret, workspace_id, artifact_id**.
2. **Foundry → Build → <agent> → Tools → + → Fabric IQ (OneLake Catalog)** → pick that connection
   → select your **Ontology** item (this enables the NL2Ontology layer, not raw-table grounding).
3. **Test in the agent playground** (you're signed in → OBO works): e.g. *"For learner L-1004
   targeting AZ-204, which high-leverage domain is weakest?"* → answered via NL2Ontology. That
   live answer is the defensible **"uses Fabric IQ"** proof — and it answers the open Trial/SKU
   question: if it returns, your Trial runs it; if it errors on license/SKU, spin a short-lived F2.

**Optional — web app calls Fabric IQ (OBO):** the browser signs the user in with Entra (MSAL),
the backend forwards `Authorization: Bearer {user_token}` when calling the agent endpoint, and the
Agent Service exchanges it for the Fabric audience (`https://analysis.windows.net/powerbi/api`).
**Service principals are not allowed** — user-delegated only. For the hackathon, the playground
demo (step 3) already counts as "uses Fabric IQ"; the web-app OBO is polish.

**App integration — IMPLEMENTED (backend):** `POST /api/fabric-iq/ask` (in `backend/main.py`)
forwards the caller's `Authorization: Bearer <user_token>` to the Foundry agent via
`backend/core/fabric_iq_agent.py` → `responses.create(extra_body={agent_reference})` (OBO; no SPN).
Setup to go live:
1. `pip install -r requirements.azure.txt`  (azure-ai-projects **>=2.1.0**, needed for `get_openai_client`/`responses`)
2. `FABRIC_IQ_AGENT_NAME=<your Foundry agent with the Fabric IQ tool>`
3. Test without a frontend yet — mint a user token from the CLI and curl:
   ```bash
   TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
   curl -s localhost:8000/api/fabric-iq/ask -H "Authorization: Bearer $TOKEN" \
        -H 'content-type: application/json' \
        -d '{"question":"For learner L-1004 targeting AZ-204, which high-leverage domain is weakest?"}'
   ```
**Still TODO (frontend):** add MSAL sign-in (`@azure/msal-browser`) so the browser obtains the
user's token (scope for the Foundry/AI audience) and sends it as the `Bearer` header to
`/api/fabric-iq/ask`. Until then, use the CLI-token curl above to validate end-to-end.

---


## 0. Enable the gating tenant settings (admin, once)
Admin portal → **Tenant settings**:
- **Fabric data agent** / **Copilot → Standalone Copilot experience** = On
- **Cross-geo processing for AI** and **Cross-geo storing for AI** = On (per your data residency)
Without these, "+ New item → Fabric data agent" won't work.

---

## No paid SKU? Use the Lakehouse SQL endpoint instead of the data agent

The **Fabric data agent needs a paid F2+ capacity** — the **Trial doesn't qualify**. You don't
need it: the app's semantic methods need the *data*, not an LLM agent, and every Lakehouse has a
**SQL analytics endpoint** that works on the Trial. The backend already supports this path
(`FabricIQClient._query_fabric_sql`, tried *before* the data agent):

1. Lakehouse → **Settings → SQL analytics endpoint** → copy the **server** (e.g.
   `<id>.datawarehouse.fabric.microsoft.com`) and note the **database** = lakehouse name.
2. Set env:
   ```
   FABRIC_SQL_ENDPOINT=<id>.datawarehouse.fabric.microsoft.com
   FABRIC_SQL_DATABASE=enterprisecertiq
   FABRIC_TENANT_ID/CLIENT_ID/CLIENT_SECRET=...   # SPN with Viewer on the workspace/SQL endpoint
   ```
   (`pip install pyodbc` + the system **ODBC Driver 18 for SQL Server**.)
3. `get_domain_thresholds` now runs `SELECT … FROM cert_domains WHERE cert_id = ?` against live
   OneLake data — genuine Fabric IQ grounding, on the Trial SKU. `/health` shows
   `fabric_iq: azure-sql`. Falls back to local on any failure.

Keep your **Ontology** (Part B) — it's the semantic layer and powers NL2Ontology later, either
on a paid F2+ capacity or via the Foundry `fabric_iq_preview` tool (Foundry's agent runtime,
which may sidestep the Fabric data-agent SKU). The data agent below is optional.

## Part A — Fabric Data Agent (optional; needs paid F2+)

### A1. Create it
Workspace → **+ New item** → search **Fabric data agent** → name it `enterprisecertiq-agent`.

### A2. Add the Lakehouse as a data source
The OneLake catalog opens → select the **`enterprisecertiq` Lakehouse** → **Add**.
In the left **Explorer**, tick the tables the agent may use (tick all 11; the key ones are
`certifications`, `cert_domains`, `cert_domain_services`, `learners`, `learner_evidence`,
`teams`, `team_members`, `cohort_outcomes`).

### A3. Data agent instructions (paste this)
Open **Data agent instructions** and paste:

> This agent answers questions about Microsoft certification readiness for an enterprise
> learning program. Data lives in the `enterprisecertiq` lakehouse.
> - `certifications` — one row per certification (cert_id, cert_name, role, passing_score).
> - `cert_domains` — weighted exam domains per certification (cert_id, domain_id, name,
>   weight_pct, minimum_mastery). weight_pct is the domain's share of the exam; higher
>   weight = higher leverage on the outcome.
> - `cert_domain_services` — Azure services taught in each domain.
> - `learners` / `learner_evidence` — learners (learner_id, role, team_id, cert_target) and
>   their per-skill assessment scores (skill_key, score 0–1).
> - `teams` / `team_members` / `team_cert_targets` — team rollups.
> - `cohort_outcomes` — historical pass/fail benchmarks (cert_id, practice_score_avg,
>   hours_studied, exam_outcome).
> Definitions: "leverage" = weight_pct / 100. "domain gap" = max(0, minimum_mastery −
> average evidence score for that domain). "priority gap" = gap × leverage (rank weaknesses
> by this). Treat a learner with no evidence rows for a domain as "insufficient evidence,"
> never as ready. Always weight domain importance by weight_pct.

### A4. Example queries (few-shot — add under Example queries → the lakehouse source)
These teach the agent our schema (valid SQL over the Delta tables):

```
Q: What are the weighted domains and minimum mastery for AZ-204, highest weight first?
SQL: SELECT name, weight_pct, minimum_mastery FROM cert_domains
     WHERE cert_id = 'AZ-204' ORDER BY weight_pct DESC;
```
```
Q: For learner L-1004, show the average evidence score per AZ-204 domain and the gap to minimum mastery.
SQL: SELECT d.name, d.weight_pct, d.minimum_mastery, AVG(e.score) AS avg_score,
            GREATEST(0, d.minimum_mastery - AVG(e.score)) AS gap
     FROM cert_domains d
     LEFT JOIN learner_evidence e ON e.skill_key = d.domain_id AND e.learner_id = 'L-1004'
     WHERE d.cert_id = 'AZ-204' GROUP BY d.name, d.weight_pct, d.minimum_mastery
     ORDER BY d.weight_pct DESC;
```
```
Q: Which team members in TEAM-A are targeting AZ-204?
SQL: SELECT m.learner_id, l.cert_target FROM team_members m
     JOIN learners l ON l.learner_id = m.learner_id
     WHERE m.team_id = 'TEAM-A' AND l.cert_target = 'AZ-204';
```
```
Q: What is the historical pass rate for AZ-204 in the cohort?
SQL: SELECT cert_id,
            AVG(CASE WHEN exam_outcome = 'Pass' THEN 1.0 ELSE 0 END) AS pass_rate
     FROM cohort_outcomes WHERE cert_id = 'AZ-204' GROUP BY cert_id;
```

### A5. Test → Publish
Use the built-in chat to ask the example questions; refine instructions/examples until answers
are right. Then **Publish** → copy the **published URL** (that's the endpoint our backend uses).

---

## Part B — Ontology (the Fabric IQ semantic layer; enrichment)

You can **(B-easy)** generate it from a Power BI semantic model, or **(B-manual)** build from
OneLake. Manual is more control; generate is faster if you already model relationships in a
semantic model.

### B1. Create the ontology item
**+ New item** → **Ontology (preview)** → name `EnterpriseCertIQ_Ontology` (underscores, no
spaces/dashes) → **Create**.

### B2. Entity types + data bindings (manual route)
For each, **Add entity type** → name → **Add Entity Type**; then **… → Bind data → Add data
binding > Lakehouse table** → pick the table → set the **entity type key**:

| Entity type | Bind table | Entity key | Notable properties |
|---|---|---|---|
| Certification | `certifications` | `cert_id` | cert_name, role, passing_score |
| SkillDomain | `cert_domains` | **`cert_id` + `domain_id`** (multi-key) | name, weight_pct, minimum_mastery |
| Learner | `learners` | `learner_id` | role, cert_target, team_id |
| Team | `teams` | `team_id` | team_name, manager_id |
| Cohort | `cohort_outcomes` | `learner_id` + `cert_id` | practice_score_avg, exam_outcome |

(Optional) Evidence ← `learner_evidence`, key `learner_id` + `skill_key`.

### B3. Relationship types (Add relationship → name, Origin, Target → set Mapping table + matched columns)

| Relationship | Origin → Target | Mapping table | Matched origin col | Matched target col |
|---|---|---|---|---|
| has | Certification → SkillDomain | `cert_domains` | cert_id | cert_id (+domain_id) |
| advances_to | Certification → Certification | `cert_advancement` | cert_id | next_cert_id |
| targets | Learner → Certification | `learners` | learner_id | cert_target |
| belongs_to | Learner → Team | `team_members` | learner_id | team_id |
| team_targets | Team → Certification | `team_cert_targets` | team_id | cert_id |

This is the same model `FabricIQClient.describe_ontology()` returns locally — now backed by OneLake.

### B4. Add the ontology to the data agent
Back in the data agent → Explorer → **+ Data source** → select `EnterpriseCertIQ_Ontology`.
Now the agent can answer business-term questions via **NL2Ontology** (e.g. "which high-leverage
domain is learner L-1004 weakest in?") on top of the raw-table SQL path.

---

## Part C — Wire it to the backend
Once the data agent is published:
```
FABRIC_IQ_ENDPOINT=<published data-agent URL or workspace API base>
FABRIC_IQ_WORKSPACE=<workspace name or GUID>
FABRIC_TENANT_ID=...        # SPN that can call Fabric APIs + has workspace access
FABRIC_CLIENT_ID=...
FABRIC_CLIENT_SECRET=...
```
`FabricIQClient._query_fabric()` will then call the agent; on any failure it falls back to the
local ontology, so nothing breaks during setup. Confirm the exact request path/payload of your
published agent and adjust `_query_fabric` / `_coerce_thresholds` in `backend/iq/fabric_iq.py`
to match its response.
