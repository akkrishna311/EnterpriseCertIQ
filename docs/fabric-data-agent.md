# Fabric IQ — build the Ontology + Data Agent (tailored to our tables)

Detailed, copy-paste runbook for Step 5, grounded in the current Microsoft docs:
- Ontology: https://learn.microsoft.com/fabric/iq/ontology/tutorial-1-create-ontology
- Data agent: https://learn.microsoft.com/fabric/data-science/how-to-create-data-agent

Assumes Step 1–4 are done (workspace + Lakehouse `enterprisecertiq` with the 11 Delta tables).

## 0. Enable the gating tenant settings (admin, once)
Admin portal → **Tenant settings**:
- **Fabric data agent** / **Copilot → Standalone Copilot experience** = On
- **Cross-geo processing for AI** and **Cross-geo storing for AI** = On (per your data residency)
Without these, "+ New item → Fabric data agent" won't work.

---

## Part A — Fabric Data Agent (do this first; the fast win)

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
