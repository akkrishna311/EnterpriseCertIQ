# EnterpriseCertIQ — Demo Walkthrough (Detailed)

Full screen-by-screen breakdown of the demo, including UI details, agent/tool mappings, and technical implementation notes. For the concise version see the `## Demo Walkthrough` section in [README.md](../README.md).

Demo subject: **L-1004** — Cloud Engineer · AZ-204 · TEAM-A Platform Engineering · Deadline 2026-08-15

---

## Screen 1 — Journey Trace (pipeline idle)

**Tab:** Journey Trace (active)

Before clicking `Build My Plan`, all 9 agent nodes are rendered in their pending/idle state in the DAG view. The SSE event stream panel on the right is empty. The dependency order is visible to judges without running anything.

**Sidebar (persistent across all Learner tabs):**

| Field | Value |
|---|---|
| Learner | L-1004 — Cloud Engineer |
| Cert | AZ-204 |
| Team | TEAM-A |
| Deadline | 2026-08-15 |
| Latest mock | — (no attempts yet) |
| Weakest topic | — (not yet assessed) |

**Suggested Next Step card:** "Start by building your personalised study plan." → `Build My Plan` (blue button).

**Top-right indicator:** `Synthetic data only · Microsoft Agents League 2026` — confirms all data is synthetic.

**Technical note:** The DAG is rendered from the agent pipeline definition in `backend/agents/workflow.py`. Node order reflects the actual execution dependency graph, not a static mockup.

---

## Screen 2 — Journey Trace (pipeline complete)

**Tab:** Journey Trace

After clicking `Build My Plan`, the 9-agent pipeline executes and all nodes turn green. Each node shows:
- Agent name
- Status: `done`
- Elapsed time per agent

**Agent execution order (with SSE events):**

| # | Agent | Role |
|---|---|---|
| 1 | Orchestrator | Routes session, manages handoffs |
| 2 | Learner Intake | Parses learner profile + Work IQ signals |
| 3 | Learning Path Curator | Retrieves cited content via Foundry IQ (VECTOR_SEMANTIC_HYBRID) + MS Learn MCP |
| 4 | Study Plan Generator | Builds capacity-aware weekly plan via LRA |
| 5 | Readiness Critic | Attacks the plan, produces calibrated P(pass) |
| 6a | Engagement Agent ∥ | Schedules reminders (parallel with 6b) |
| 6b | Assessment Agent ∥ | Runs readiness forecast (parallel with 6a) |
| 7 | Manager Insights | Team-level risk, ROI, interventions |
| 8 | Retrospective *(conditional)* | Fires only when `has_prior_failures = true` |

**Parallelism:** Stages 6a and 6b run via `asyncio.gather()` — visible in the timeline as overlapping elapsed times.

**Right panel — SSE event stream:**
Live events from each agent appear line-by-line as the pipeline runs. Events are persisted to storage and replayed on page reload — the stream is not lost if the browser is refreshed mid-run.

**Technical note:** SSE events are streamed via `/api/pipeline/run` endpoint; persisted to `backend/data/store/traces/`. The Foundry Hosted Agent is the registered top-level entry — all 9 agents are registered as Azure AI Foundry Agent threads.

---

## Screen 3 — Study Plan

**Tab:** Study Plan (badge shows `1` — one draft plan pending approval)

**Plan header:**
- Learner: L-1004 · AZ-204 · Cloud Engineer
- Status banner: `Draft — pending approval`
- Total: 25 hours · 6 weeks · Deadline 2026-08-15

**Weekly breakdown table:**

Each row shows: week number, topics covered, hours allocated, domain tags. Hours per week are distributed using the **Largest Remainder Algorithm (LRA)**:

1. Domain weights are read from Fabric IQ (`get_domain_thresholds`)
2. Total study hours are split proportionally by weight × mastery gap (leverage)
3. Fractional hours are rounded using LRA to ensure integer values sum exactly to the total
4. LRA runs on every plan generation regardless of model output (canonicalization step in `workflow.py`)

This prevents rounding drift where "6.4h + 4.3h + 3.6h" quietly becomes 15h instead of 14h.

**Plan ID:** `plan_L-1004_AZ-204_fc37622c` — exposed in the UI for auditability and used as the key for `/api/plans/approve`.

**Agent:** Study Plan Generator (Planner)

---

## Screen 4 — Plan Review (Critic objections)

**Tab:** Plan Review (badge shows `5` — five open objections)

**Objection format (each Critic objection):**

```
fabric_iq: D{n} weight X% — minimum mastery 70%
[objection text citing the specific domain gap]
leverage: domain_weight × mastery_gap
```

Objections are ranked by **leverage** — the product of exam domain weight and mastery gap. A domain worth 25% of the exam where the learner has 10% mastery has higher leverage than a domain worth 10% where the learner has 60% mastery.

**Critic loop (bounded 2-round):**
1. Critic produces objections
2. Planner revises the plan to address them
3. Critic re-evaluates the revised plan
4. After 2 rounds, the loop exits — remaining objections are logged but the loop does not retry
5. If objections remain after 2 rounds, the plan is surfaced as-is with open objections visible

**Tab badge:** Shows count of open objections remaining after the Critic loop. Judges can see exactly how many issues were found and which were resolved.

**Agents:** Readiness Critic → Study Plan Generator (Planner)

---

## Screen 5 — Progress

**Tab:** Progress

**Content:**
- Week-by-week study timeline with completion status per week
- Each week row is expandable to show topic detail
- Capacity warning banner appears when Work IQ signals detect high meeting load (e.g., >20h/wk meetings)
- Recommended study slots shown per week, derived from free-time gaps in the learner's work calendar

**Work IQ integration:**
- Meeting hours and focus hours are read from `backend/data/synthetic/learners.json` (synthetic) or Microsoft Graph API (`WORK_IQ_SOURCE=graph`)
- Recommended study slots are scheduled to avoid meeting-dense periods
- The Engagement Agent adapts slot timing to the learner's work pattern — not just the total hours

**Agent:** Engagement Agent

---

## Screen 6 — Exam Readiness (two scrolls)

**Tab:** Exam Readiness

### Readiness decision banner (top, amber)

```
Readiness decision: NOT READY — continue prep
Below threshold (559/700). Looping back to strengthen: networking.
```

This is the output of `_readiness_from_forecast()` — a pure deterministic function in `workflow.py`. It converts the calibrated P(pass) to a binary control signal. The text "Looping back to strengthen: networking" is the control signal that would trigger a replan loop in a continuous learning cycle.

### Left panel — Exam Readiness Forecast

Driven by the `compute_readiness_forecast` MCP tool, called by the Readiness Critic and Assessment Agent.

| Field | Description |
|---|---|
| P(pass) gauge | Circular gauge showing calibrated pass probability |
| Estimated score | Projected exam score on 1000-point scale |
| Pass threshold | 700 (from Fabric IQ cert ontology) |
| Points needed | Gap to passing threshold |
| Confidence interval | Lower and upper bound of the probability estimate |
| Calibrated P(pass) | Point estimate with verdict label |
| Model citation | `"logistic model · LOO AUC ≈ 0.80 · abstains when thin"` |
| Weakest area | Domain with highest leverage gap |
| Min. additional study hours | Hours needed to reach 75% pass probability |

**Model implementation (`readiness_model.py`):**
- Logistic regression, pure numpy, seeded (reproducible)
- Trained on n=102 synthetic learner records
- LOO (Leave-One-Out) cross-validation AUC ≈ 0.80
- Brier score 0.183 (well-calibrated)
- Abstains (returns `INSUFFICIENT`) when evidence is thin — does not fabricate a forecast
- This is not an LLM probability estimate — it is a statistical model with inspectable quality metrics

### Right panel — Domain Mastery Breakdown

Driven by the `compute_domain_mastery` MCP tool.

Horizontal bar chart for all 5 AZ-204 domains. Dashed vertical line at 75% = pass threshold from `Fabric IQ get_domain_thresholds`. Bars in red are below threshold; green are above.

| Domain | Exam weight | Mastery |
|---|---|---|
| Develop Azure compute solutions | 25% | 22% |
| Develop for Azure storage | 15% | 22% |
| Implement Azure security | 20% | 22% |
| Monitor, troubleshoot, and optimize Azure solutions | 15% | 22% |
| Connect to and consume Azure services and third-party services | 25% | 22% |

### Service Confidence Heatmap (scroll 1 + 2)

Driven by the `compute_service_heatmap` MCP tool.

Legend: `Strong (≥75%)` · `Developing (55–74%)` · `Weak (<55%)` · `Insufficient data`

Drills from domain level → individual Azure service, exposing intra-domain variation:

| Domain (weight) | Services and mastery |
|---|---|
| Compute (25%) | Azure Functions 17% · App Service 22% · Container Instances 27% · Container Apps 32% |
| Storage (15%) | Blob Storage 17% · Cosmos DB 22% · Table Storage 27% · Queue Storage 32% |
| Security (20%) | Key Vault 17% · Active Directory 22% · Managed Identity 27% · RBAC 32% |
| Monitor (15%) | Azure Monitor 17% · Application Insights 22% · Log Analytics 27% · Cache for Redis 32% |
| Connect (25%) | API Management 17% · Event Grid 22% · Service Bus 27% · Event Hub 32% |

This level of granularity enables targeted remediation: not "security is weak" but "Key Vault is weaker than RBAC within security."

### Trust & Safety cards (bottom of Exam Readiness page)

Three metric cards shown at the bottom of the same tab:

| Card | What it shows |
|---|---|
| **Calibrated readiness** | LOO AUC, Brier score, n=102 — the forecasting model's own quality metrics, inspectable without running the model |
| **Adversarial red-team** | 16/16 attacks held, ASR 0% — full case list in `eval/redteam.json` |
| **Content Safety** | Current mode: Regex fallback (active when `AZURE_CONTENT_SAFETY_KEY` not set); live API mode when key is configured |

**Agents/tools:** Readiness Critic + Assessment Agent (evidence), `readiness_model.py` (forecast), Fabric IQ `get_readiness_semantics` (domain weights + mastery grounding)

---

## Screen 7 — Practice Exam (two states)

**Tab:** Practice Exam

### State 1 — Pre-generation

Main content area shows: `"Pick a difficulty and click 'Generate Practice Exam' in the sidebar."`

**Sidebar difficulty selector:**
- Four options: `Mixed` (default, highlighted blue) · `Easy` · `Medium` · `Hard`
- Button: `Generate Mixed Practice Exam`

The sidebar also shows current learner signal (mock score, attempts, weakest topic) — the Engagement Agent uses this to weight question distribution toward the weakest domain when generating Mixed difficulty exams.

### State 2 — Post-generation

**Header:** `AZ-204 — Practice Exam · 20 questions · 40 min · answered 0/20`

**AI-generated banner:** Always shown — `"AI-generated — Review before acting on this information."`

**Submit button:** Disabled (`Submit (0/20)`) until all 20 questions are answered. Progress bar shown: `"Answer all 20 questions before submitting. Current progress: 0/20."`

**Question structure (consistent across all 20 questions):**

1. **`[Synthetic]` prefix** — explicit label that this is AI-generated, not a real Microsoft exam question
2. **Inline approved source citation:**
   ```
   Approved source (AZ-204: Developing Solutions for Microsoft Azure):
   "Role: Cloud Engineer. Passing score: 700. Recommended study hours: 20.
   Domains: Develop Azure compute solutions (25%) — Azure Functions, Azure App Service, ..."
   ```
   The Fabric IQ / MS Learn grounding source is embedded directly in the question text — not hidden.
3. **Per-question difficulty tag:** `Easy` / `Medium` / `Hard` (colour-coded)
4. **Domain · Service footer:** e.g., `"Develop Azure compute solutions · Azure Functions"` — maps back to the service heatmap

**Mixed difficulty distribution:** In Mixed mode, questions span Easy / Medium / Hard, weighted so the weakest-mastery domains receive proportionally more questions and harder difficulty variants.

**Agent:** Engagement Agent — question generation via `MS_LEARN_MCP_URL` (Microsoft Learn MCP) + Fabric IQ grounding

---

## Screen 8 — Audio Briefing

**Tab:** Audio Briefing

**Card header:** `Learning Podcast` — tags: `grounded · cited · two-host`

**Teach me dropdown:** `"My weakest area (recommended)"` (default selection, fire emoji). Topic is selected automatically from the service heatmap — the lowest-mastery, highest-exam-weight domain. The learner does not need to self-identify their gap.

**Generated episode:**
- Title: `"AZ-204 [learner name]: Implementing Azure Security"`
- Yellow label: `"Targeting your weakest, highest-leverage area."` — explains the auto-selection rationale

**Audio player:** Standard HTML5 player with play/pause, volume, and options. Azure Cognitive Services TTS synthesises two distinct voices (Coach and Learner roles) — not a single narrator.

**Transcript — two-host Coach/Learner dialogue (sample turns):**

> **Coach:** "Welcome to our focused study session for the AZ-204 exam. Today, we're tackling one of the most important and sometimes tricky areas: implementing Azure security..."
>
> **Learner:** "I know security is a big deal, but what does 'implement Azure security' actually mean for the AZ-204 exam?"
>
> **Coach:** "For AZ-204, implementing Azure security means understanding how to protect your cloud solutions using Azure's built-in services... Azure Key Vault, Azure Active Directory, Managed Identity, and RBAC..."
>
> **Learner:** "Can we walk through a scenario where all these services come together?"
>
> **Coach:** "Imagine you're deploying an Azure Function. You use Managed Identity for the function, which authenticates it with Azure Active Directory. You store the database credentials in Azure Key Vault. RBAC makes sure only the function's identity can read those secrets..."

**Sources footer (full citation exposed at bottom of page):**
```
Sources: AZ-204: Developing Solutions for Microsoft Azure: Role: Cloud Engineer.
Passing score: 700. Recommended study hours: 20.
Domains: Develop Azure compute solutions (25%) — Azure Functions, Azure App Service,
Azure Container Instances, Azure Container Apps | Develop for Az · AZ-204: [domain] by Domain
```

**Agent mapping:**
- **Engagement Agent** — generates the two-host dialogue script via MS Learn MCP + Fabric IQ, formats as pedagogical Coach/Learner exchange grounded in the learner's actual mastery gaps
- **Azure AI Speech** (`SPEECH_KEY` + `SPEECH_REGION` in `.env.local`) — TTS synthesis with two distinct voice profiles

---

## Screen 9 — Safety & RAI

**Tab:** Safety & RAI

**Top banner:**
> `"EnterpriseCertIQ applies Responsible AI controls at every stage. All outputs are AI-generated and require human review before use in employment or performance decisions."`

Status chips: `Backend: azure_foundry` · `Content Safety threshold: 2`

### 7 RAI control cards (2-column grid)

| Control | Tag | Implementation detail |
|---|---|---|
| **Content Safety** | `Regex Fallback` | Regex guardrail scanning for jailbreak, self-harm, violence patterns. Categories: Hate · SelfHarm · Sexual · Violence. Falls back to regex when `AZURE_CONTENT_SAFETY_KEY` not set; live Azure Content Safety API when key is configured. |
| **PII Redaction** | `Domain Aware` | Unconditional redaction of emails and phone numbers. Conditional redaction of names — uses a cert/role domain vocabulary so technical terms like "Azure Active Directory" or "Managed Identity" are preserved rather than redacted. |
| **Citation Gate** | `Pipeline Check` | Flags agent outputs that lack citation markers. Applied specifically to Curator, Assessment, and Critic agents — the three agents that are required to cite Fabric IQ sources. Non-cited outputs are flagged before reaching the frontend. |
| **Bias Audit** | `Regex Scan` | Scans all agent outputs for gendered pronouns and role-stereotype patterns. Findings are logged to Application Insights. Does not block output (audit mode). |
| **Groundedness Evaluation** | `Azure AI Evaluation` | LLM-as-judge via `azure-ai-evaluation` SDK `GroundednessEvaluator`. Checks whether agent claims are supported by the retrieved context chunks. Run ID is exposed for traceability. |
| **HITL Approval Gate** | `Human In The Loop` | Study plans remain in `draft` status at the data level until a human calls `/api/plans/approve`. Not a UI-only gate — the plan object itself has a `status` field that blocks publishing. |
| **Foundry Agent Orchestration** | `Azure AI Foundry Agent Service` | All workflow runs are registered and tracked as Azure AI Foundry Agent threads. Full auditability in the Foundry portal — run IDs are exposed in the UI. |

### Run Evaluations section

Identified by a Run ID (UUID format) — each pipeline execution produces its own evaluation record.

**Groundedness Score panel:**
- Evaluated using Azure AI Evaluation SDK LLM-as-judge (`GroundednessEvaluator`)
- Shows: citation count found, assertion count checked, overall status verdict (`Review` / `Pass` / `Fail`)
- Status `Review` means the run needs human inspection before being treated as ground truth

**Agent Quality Rubrics panel — 3 agents, named pass/fail checks:**

`plan_generator` rubric:
- P1: Valid StudyPlan schema keys present
- P2: Plan spans at least one week
- P3: Total planned hours > 0
- P4: Every week carries at least one topic (no empty weeks)
- P5: Plan starts as draft (HITL gate enforced at creation)

`engagement` rubric:
- E1: Recommended study slots present in output
- E2: Capacity risk flagging is valid (meets threshold logic)
- E3: Does not auto-write calendar — disclosure requirement (engagement agent must not silently book calendar entries on behalf of the learner)

`manager_insights` rubric:
- M1: Readiness distribution present in team summary
- M2: Has at least one actionable manager action
- M3: No individual exam score leaked in summary text (privacy guard — team summary must not expose per-learner scores)
- M4: Peer pairs (if any) name both sides of the pairing fairly

---

## Screen 10 — Manager → Overview (two scrolls)

**View:** Manager tab, Overview sub-tab

### Header

- **Manager Insights** — Team Command Center
- Team: `TEAM-A — Platform Engineering · 3 members · avg latest 20%`
- Sub-tabs: `Overview` · `Approvals & Actions 1` · `Capacity & Simulator` · `Peer Learning`
- `Copy handoff brief` — generates a manager-ready team summary for Sprint Review, 1:1s, or escalation
- Team selector dropdown: `TEAM-A — Platform Engineering`

**AI banner (stronger than Learner view):**
> `"AI-generated — AI-generated team insights; verify before use in performance or HR decisions."`

The explicit "performance or HR decisions" call-out is intentional — this view is used by managers making workforce decisions.

### Manager Briefing card

Status chips: `On track 0` · `At risk 2` · `Insufficient evidence 1`

**ROI — Cost of Delay box:**

```
$3,000 / mo  ← monthly_delay_cost_usd = at_risk_headcount × cert_market_value_uplift / 12
```

- 2 learners below AZ-204 pass threshold
- AZ-204 annual market uplift: $18,000/yr
- Monthly cost of delay: $3,000/mo (2 learners × $18,000 / 12)

This calculation is produced by the Manager Insights Agent and uses cert market value data from Fabric IQ.

### Three-column action grid

**MANAGER ACTIONS** — prescriptive, named to specific learner IDs:
1. "Protect one recurring study block for high-risk learners before the next certification checkpoint."
2. "Queue a remediation mock exam for L-1004 after targeted review."
3. "Schedule L-1005 to coach L-1004 on exam rehearsal this week."

**RISK AREAS** — amber diagnostic cards, team-level patterns:
1. "High meeting load is affecting 1 learner(s)."
2. "1 learner(s) still need a fresh mock exam signal."
3. "Latest mock attempts are below threshold for L-1004."
4. "Top priority gap for TEAM-A: 'Develop Azure compute solutions' (team avg 0%, affects 1 of 3 members), weighing on AZ-204 Develop Azure compute solutions (25%)."

**PEER PAIR SIGNALS** — bidirectional (both directions shown explicitly):
- "L-1005 can help L-1004 on Exam Rehearsal."
- "L-1004 can help L-1005 on Exam Rehearsal."

### 9 team metric tiles

| Metric | Value |
|---|---|
| Team members | 3 |
| Avg meeting hrs/wk | 20.7h |
| High capacity risk | 1 |
| Needs action now | 2 (amber, clickable — expands Needs Action Now panel) |
| Avg latest mock score | 20% |
| Passing learners | 0 |
| Below threshold | 1 |
| Improving learners | 0 |
| No mock attempts | 2 |

### Needs Action Now panel (expanded via metric tile click)

"Learners flagged by workload risk, recent mock performance, or both."

| Learner | Cert/Role | Severity | Reason |
|---|---|---|---|
| L-1004 | AZ-204 · Cloud Engineer | `High` | Latest mock below threshold |
| L-1005 | AZ-400 · DevOps Engineer | `Watch` | High capacity risk |

Each card: `Pin intervention` · `Open Readiness` · `Open Progress` · `Open Mock Exam` — manager navigates directly from the summary to any learner view.

### Certification Momentum cards

Per-learner attempt trend, verdict, exam detail:

| Learner | Cert | Attempts | Latest result | Verdict | Date |
|---|---|---|---|---|---|
| L-1004 | AZ-204 · Cloud Engineer | 1 | 200/1000 · Mixed · 20q | `REVIEW` | 2026-06-14 |
| L-1005 | AZ-400 · DevOps Engineer | 0 | No mock exams yet | — | — |
| L-1007 | AZ-204 · Cloud Engineer | 0 | No mock exams yet | — | — |

L-1004 shows mini sparkline trend over attempts. Learners with 0 attempts show: `"Use the Learner view to create the first assessment trail."` with `Open Mock Exam` and `Open Reasoning` buttons.

### Team Certification Targets (bottom)

- Cert targets: `AZ-204` · `AZ-400`
- Team goal: `"All members hold at least one Azure certification by Q3 2026"`

**Agents:** Manager Insights Agent; Assessment Agent (momentum data); Retrospective Agent (risk pattern analysis)

**Privacy note:** Individual exam scores are never shown in the team summary — enforced by M3 rubric in the Agent Quality Rubrics evaluator.

---

## Screen 11 — Manager → Approvals & Actions

**View:** Manager tab, Approvals & Actions sub-tab (badge: 1)

**Plans Pending Your Approval card:**
> `"Review AI-generated study plans before they go live for your team members."`

Badge: `1 pending`

**Draft plan card:**

| Field | Value |
|---|---|
| Learner | L-1004 — AZ-204 |
| Status | `Draft` |
| Plan ID | `plan_L-1004_AZ-204_fc37622c` |
| Total hours | 25h |
| Duration | 6 weeks |
| Deadline | 2026-08-15 |

**Action buttons:**
- `✓ Approve & Publish` (amber) — calls `/api/plans/approve` with the plan ID; promotes status from `draft` to `published`
- `Review Plan` (outline) — opens the full study plan tab for inspection before approving

**Important:** The `draft` status is enforced at the data level in `backend/data/store/plans/`. The UI button is not the gate — the API endpoint is. A manager who bypasses the UI would still need to call the API.

**Footer:** `"Team work context derived from synthetic Work IQ signals"` — this footnote appears on all Manager sub-tabs.

---

## Screen 12 — Manager → Capacity & Simulator (two scrolls)

**View:** Manager tab, Capacity & Simulator sub-tab

### Counterfactual Readiness Simulator

Card title: `Counterfactual Readiness Simulator` — tagged `Standout reasoning`

> `"Test a concrete manager action before committing to it. The simulator estimates workload relief, study-time gain, and target-learner exam movement."`

**Input fields:**

| Field | Value in demo |
|---|---|
| Target learner | L-1004 |
| Peer mentor | No peer mentor |
| Protected focus hours | 2 |
| Reduced meeting hours | 2 |
| Review hours / week | 3 |
| Additional field | 1 |

Caption: `"The estimate blends current evidence, workload signals, and the likely lift from focused remediation."`

`Run what-if` button (blue) → triggers the simulation.

### Projected outcome

Summary: `"If the manager protects time for L-1004, the projected score moves from 241 to 282 against a threshold of 700."`

Four outcome metrics (before → after):

| Metric | Before | After | Delta |
|---|---|---|---|
| Target score movement | 241 | 282 | (threshold 700) |
| Readiness movement | 0 on-track | 0 on-track | +0 |
| At-risk movement | 2 at-risk | 2 at-risk | +0 |
| Capacity pressure | 1 at risk | 1 at risk | +0 |

### Reasoning Assumptions (explicit chain of logic)

The simulator shows its work:
1. "Protected 2.0 meeting hour(s) per week for L-1004, converting part of that load into study time."
2. "Added 2.0 protected focus hour(s) per week for L-1004."
3. "Targeted review improves L-1004 on Develop Azure compute solutions after 3.0 hour(s) of remediation."

### Recommendation

> `"This intervention helps but does not fully de-risk L-1004; keep remediation focused on Develop Azure compute solutions and schedule another mock exam."`

Context details shown alongside:
- Weakest topic: `Develop Azure Compute Solutions`
- Meeting load: `20h / week`
- Available study hours: `6.7h / week`
- Focus time: `12h / week`

### Capacity conflicts flagged (red alert banner, scroll 2)

> `"L-1005 has high meeting loads (>25h/wk). Consider schedule adjustments before certification deadlines."`

### Team Members — Work Context cards

Per-learner work signal from Work IQ:

| Learner | Capacity risk | Meeting hrs/wk | Focus hrs/wk | Recommended study slots |
|---|---|---|---|---|
| L-1004 | ⚠️ medium | 22h | 10h | Tuesday 08:00-09:30 · Thursday 08:00-09:30 |
| L-1005 | 🔴 high | 28h | 8h | Tuesday 14:00-15:30 · Thursday 14:00-15:30 |
| L-1007 | ✅ low | 12h | 6h | Tuesday 19:00-20:30 · Thursday 19:00-20:30 |

Footer: `"Team work context derived from synthetic Work IQ signals"`

**`Standout reasoning` tag:** Indicates the Capacity & Simulator uses the o-series reasoning model path within the Manager Insights Agent — the simulator's projection is produced by a reasoning model, not just a formula, which is why the Reasoning Assumptions are shown explicitly.

---

## Screen 13 — Manager → Peer Learning

**View:** Manager tab, Peer Learning sub-tab

**Peer Learning Opportunities card**

### Example pairing: Pair L-1007 with L-1004

| Field | Value |
|---|---|
| Match type | `Same-cert mentor match` |
| Shared cert target | AZ-204 |
| Focus domain | Develop Azure compute solutions |
| Why this pair | L-1007 is currently stronger in develop azure compute solutions than L-1004 |
| Suggested session | Tuesday 08:00-09:30 |

**Mentor strength:** `L-1007 · 50%` — "Strongest relevant domain coverage for this pairing."

**Learner gap:** `L-1004 · 22%` — "Current weakest same-cert domain to target first."

**Action buttons on pairing card:**
- `Same-cert mentor match` (active/selected state)
- `Pin session` — saves the peer session to the intervention queue for follow-up

**Quick-navigation links:**
- `Open Mentor Readiness` — opens L-1007's Exam Readiness tab
- `Open Learner Progress` — opens L-1004's Progress tab
- `Open Next Mock Exam` — opens L-1004's Practice Exam tab

**Pairing logic:**
- Matched within same-cert cohort (both targeting AZ-204) — cross-cert pairings are not surfaced
- Domain complementarity: mentor's highest-mastery domain matches the learner's lowest-mastery domain
- Session time derived from Work IQ availability overlap between both learners' recommended study slots

**Agent:** Manager Insights Agent — domain mastery differentials sourced from Assessment Agent output; session scheduling from Work IQ signals

**Footer:** `"Team work context derived from synthetic Work IQ signals"`

---

## Summary — Agent-to-Screen Mapping

| Agent | Screens where it is the primary driver |
|---|---|
| Orchestrator | Screen 2 (pipeline DAG) |
| Learner Intake | Screen 2 (first node in pipeline) |
| Learning Path Curator | Screen 2 (Foundry IQ retrieval) |
| Study Plan Generator | Screens 3, 4 (plan + Critic revision) |
| Readiness Critic | Screens 4, 6 (objections + P(pass)) |
| Engagement Agent | Screens 5, 7, 8 (Progress, Practice Exam, Audio Briefing) |
| Assessment Agent | Screens 6, 10 (Exam Readiness forecast input, Momentum cards) |
| Manager Insights | Screens 10, 11, 12, 13 (all Manager sub-tabs) |
| Retrospective | Screen 2 (conditional, fires on prior failures) |

## Summary — MCP Tool-to-Screen Mapping

| MCP Tool | Screen |
|---|---|
| `compute_readiness_forecast` | Screen 6 — P(pass) gauge, estimated score, confidence interval |
| `compute_domain_mastery` | Screen 6 — Domain Mastery Breakdown chart |
| `compute_service_heatmap` | Screen 6 — Service Confidence Heatmap |
| `foundry_iq_search` | Screen 3 — Fabric IQ grounding for plan topics |
| `get_domain_thresholds` | Screens 3, 6 — 75% threshold line, domain weights |
| `get_readiness_semantics` | Screen 6 — weighted mastery calculation |
| MS Learn MCP (`microsoft_docs_*`) | Screens 7, 8 — Practice Exam question grounding, podcast script |
