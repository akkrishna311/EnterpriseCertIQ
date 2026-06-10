# Fabric IQ data — mirror the local ontology in Azure

How to recreate the **same** semantic data we run locally (`backend/data/synthetic/*.json`)
inside **Microsoft Fabric IQ**, and how to keep it in sync.

**Source of truth stays the JSON files.** `scripts/export_fabric_tables.py` flattens them into
OneLake-ready relational CSVs under `backend/data/fabric_export/`. Edit JSON → re-run the
script → reload the CSVs. That's the whole maintenance loop.

```bash
python scripts/export_fabric_tables.py     # → backend/data/fabric_export/*.csv
```

## The tables (one per ontology entity / relationship)

| CSV | Ontology meaning | Key columns |
|---|---|---|
| `certifications.csv` | **Certification** entity | cert_id, cert_name, role, passing_score |
| `cert_domains.csv` | **SkillDomain** + `Certification —has→ SkillDomain` | cert_id, domain_id, name, **weight_pct**, **minimum_mastery** |
| `cert_domain_services.csv` | services bound to each domain | cert_id, domain_id, service |
| `cert_advancement.csv` | `Certification —advances_to→ Certification` | cert_id, next_cert_id |
| `learners.csv` | **Learner** (+ role, team, target) | learner_id, role, team_id, cert_target, deadline |
| `learner_evidence.csv` | **Evidence** `Learner —has→ Evidence` | learner_id, skill_key, score |
| `learner_work_signals.csv` | Work IQ context per learner | learner_id, meeting_hours_pw, focus_hours_pw, … |
| `teams.csv` | **Team** (+ manager, goal) | team_id, team_name, manager_id |
| `team_members.csv` | `Learner —belongs_to→ Team` | team_id, learner_id |
| `team_cert_targets.csv` | `Team —targets→ Certification` | team_id, cert_id |
| `cohort_outcomes.csv` | **Cohort** (benchmarks / intervention effectiveness) | cert_id, practice_score_avg, hours_studied, exam_outcome |

These columns map 1:1 to what `backend/iq/fabric_iq.py` computes locally — e.g.
`get_domain_thresholds` reads `weight_pct` + `minimum_mastery` straight from `cert_domains`.

## Step 1 — Land the tables in OneLake
1. In your Fabric workspace, create a **Lakehouse** (e.g. `enterprisecertiq`).
2. **Upload** `backend/data/fabric_export/*.csv` → **Files**, then **Load to Tables** (or use a
   notebook / Dataflow Gen2). You now have 11 Delta tables in OneLake.
   - Parquet/Delta is preferred for scale, but CSV → Load to Tables is fine for this size.

## Step 2 — Build the Ontology (Fabric IQ) on top
Create an **Ontology** item and define entity types bound to the tables:

| Entity type | Bound to | Properties |
|---|---|---|
| Certification | `certifications` | cert_id (key), cert_name, role, passing_score |
| SkillDomain | `cert_domains` | domain_id (key), name, weight_pct, minimum_mastery |
| Learner | `learners` | learner_id (key), role, deadline |
| Team | `teams` | team_id (key), team_name, manager_id |
| Cohort | `cohort_outcomes` | role, cert_id, practice_score_avg, exam_outcome |

Relationships (data-bound to the join tables):
- `Certification —has→ SkillDomain` (via `cert_domains.cert_id`)
- `Certification —advances_to→ Certification` (via `cert_advancement`)
- `Learner —targets→ Certification` (via `learners.cert_target`)
- `Learner —belongs_to→ Team` (via `team_members`)
- `Learner —has→ Evidence` (via `learner_evidence`)
- `Team —targets→ Certification` (via `team_cert_targets`)

This is the same entity/relationship model `FabricIQClient.describe_ontology()` returns
locally — now backed by OneLake.

## Step 3 — (Optional) semantic-model measures
Build a **Power BI semantic model** over the Lakehouse with measures that match our local
computations, so Fabric IQ can answer analytics questions:
- **Domain leverage** = `weight_pct / 100`
- **Domain gap** = `max(0, minimum_mastery − avg(evidence.score))`
- **Priority gap** = `gap × leverage`  (drives the critic's highest-leverage objection)
- **Weighted mastery** = `Σ(avg_mastery × leverage) / Σ(leverage)`

## Step 4 — Create a Fabric Data Agent
Add a **Fabric data agent** over the Lakehouse/semantic model. That endpoint is what our
backend calls — `FabricIQClient._query_fabric()` (already implemented) POSTs the NL/intent
query to it. Set `FABRIC_IQ_ENDPOINT` + `FABRIC_IQ_WORKSPACE` + `FABRIC_TENANT_ID/CLIENT_ID/
CLIENT_SECRET` and the backend connects automatically (else stays local).

## Keeping Azure in sync with local — pick one
| Approach | How | When |
|---|---|---|
| **Manual re-load** | edit JSON → `export_fabric_tables.py` → re-upload CSVs → *Load to Tables (overwrite)* | demo / low-change (simplest) |
| **Dataflow Gen2** | point a Dataflow at the `fabric_export/` files (OneDrive/Blob/Git) on a schedule | hands-off refresh |
| **Pipeline + Git** | commit `fabric_export/` to a repo; a Fabric **Data pipeline** pulls + overwrites tables on a trigger | repeatable / CI |
| **OneLake = source of truth** | stop syncing from JSON; edit the Delta tables directly in Fabric and let local read from Azure via `FABRIC_IQ_ENDPOINT` | once you go Azure-first |

For the hackathon, **manual re-load** is enough: the export script makes JSON→CSV one command,
and "Load to Tables (overwrite)" makes the reload one click — so Azure always mirrors local.
