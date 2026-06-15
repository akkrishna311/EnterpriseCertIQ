# Demo Walkthrough

The following traces learner **L-1004** (Cloud Engineer, AZ-204, deadline 2026-08-15, TEAM-A — Platform Engineering) through the complete pipeline. See [demo-walkthrough-detailed.md](demo-walkthrough-detailed.md) for a screen-by-screen breakdown with full technical detail.

---

### Screen 1 — Journey Trace (idle)

All 9 agent nodes are visible in the DAG before execution — pending state. The `Build My Plan` button triggers the full pipeline. Judges can inspect the dependency structure without running anything.

---

### Screen 2 — Journey Trace (pipeline complete)

All 9 nodes turn green sequentially after clicking `Build My Plan`. Each node shows status, elapsed time, and live events in the SSE panel on the right. Engagement and Readiness Forecast ran in parallel (`asyncio.gather`).

**Agents:** Orchestrator → Intake → Curator → Planner → Critic → Engagement ∥ Assessment → Manager → Retrospective *(conditional on prior failures)*

The event stream is persisted — it survives page reload.

---

### Screen 3 — Study Plan

Six-week, 25-hour plan with per-week topic allocations and domain tags. Hours are allocated using the **Largest Remainder Algorithm** so integer hours sum exactly to the total without rounding drift. The plan banner shows `Draft — pending approval` until a manager approves via `/api/plans/approve`.

**Agent:** Study Plan Generator (Planner)

---

### Screen 4 — Plan Review (Critic objections)

Objections from the Readiness Critic, each grounded in Fabric IQ:

> *"fabric_iq: D{n} weight X% — minimum mastery 70%"*

Ranked by **leverage** = `domain_weight × mastery_gap`. The Critic runs a bounded 2-round loop — objections → Planner rewrites → Critic re-evaluates — then exits after 2 rounds regardless. Remaining objections are logged. The tab badge shows the open count.

**Agents:** Readiness Critic → Study Plan Generator

---

### Screen 5 — Progress

Week-by-week study timeline with completion status and topic detail. A capacity warning appears when Work IQ signals detect high meeting load. Study slots are scheduled around real work patterns, not just intent.

**Agent:** Engagement Agent

---

### Screen 6 — Exam Readiness

**Readiness decision banner** (deterministic, not LLM): `NOT READY — continue prep. Below threshold. Looping back to strengthen: networking.`

Three MCP tools drive this screen:
- `compute_readiness_forecast` → calibrated P(pass) gauge (logistic regression, LOO AUC ≈ 0.80, abstains when evidence is thin), estimated score, confidence interval, minimum additional study hours
- `compute_domain_mastery` → domain bar chart against the 75% Fabric IQ threshold line
- `compute_service_heatmap` → granular service-level confidence: drills from domain to individual Azure service (e.g., Key Vault 17% vs RBAC 32% within security)

**Trust & Safety cards** (bottom of page): Calibrated readiness (LOO AUC, Brier score, n=102), Adversarial red-team (16/16 held, 0% ASR), Content Safety (Regex fallback or live API).

**Agents:** Readiness Critic + Assessment Agent feed evidence; `readiness_model.py` (logistic regression, pure numpy, seeded) computes P(pass); Fabric IQ `get_readiness_semantics` provides domain weights.

---

### Screen 7 — Practice Exam

Select difficulty (Mixed / Easy / Medium / Hard) and click `Generate Mixed Practice Exam`. The Engagement Agent generates 20 grounded synthetic questions weighted toward the weakest domain.

Each question shows:
- `[Synthetic]` prefix — explicit AI-generated label
- Inline Fabric IQ / MS Learn approved source citation
- Per-question difficulty tag (Easy / Medium / Hard)
- Domain · Service footer tag

Submit is locked until all 20 questions are answered. Every claim is traceable to real Microsoft documentation.

**Agent:** Engagement Agent (MS Learn MCP + Fabric IQ grounding)

---

### Screen 8 — Audio Briefing

A two-host `Learning Podcast` (Coach / Learner) auto-targets the weakest highest-leverage domain. Labeled `grounded · cited · two-host`. The topic selector defaults to `My weakest area (recommended)` — selected from the service heatmap, not self-reported. Full Fabric IQ grounding citation is shown in the sources footer. Azure Cognitive Services TTS synthesises two distinct voices.

**Agent:** Engagement Agent (script generation), Azure AI Speech (TTS synthesis)

---

### Screen 9 — Safety & RAI

Seven RAI controls, each with implementation type:

| Control | Type |
|---|---|
| Content Safety | Regex Fallback / Azure Content Safety API |
| PII Redaction | Domain-aware (preserves technical cert terms) |
| Citation Gate | Pipeline check — Curator, Assessment, Critic agents |
| Bias Audit | Regex scan — logs, does not block |
| Groundedness Evaluation | Azure AI Evaluation SDK LLM-as-judge |
| HITL Approval Gate | `/api/plans/approve` — enforced at data level |
| Foundry Agent Orchestration | All runs registered as Foundry Agent threads |

**Run Evaluations** shows per-run groundedness scores and Agent Quality Rubrics for three agents (`plan_generator`, `engagement`, `manager_insights`), each with named pass/fail checks covering schema validity, HITL enforcement, calendar-write disclosure, and privacy (no individual scores in team summary).

---

### Screen 10 — Manager → Overview

Team-level command centre for TEAM-A. Shifts from individual to aggregate without surfacing individual exam scores in the summary (enforced by M3 rubric).

**ROI Cost of Delay:** `monthly_delay_cost_usd = at_risk_headcount × cert_market_value_uplift / 12` — turns learning gaps into a business-language decision.

Three action columns: **Manager Actions** (prescriptive, named to learner IDs) · **Risk Areas** (team-level diagnostic patterns) · **Peer Pair Signals** (bidirectional — L-1005 can help L-1004; L-1004 can help L-1005).

**Needs Action Now** panel: learners flagged by workload risk or mock performance, each with severity (`High` / `Watch`), reason tag, and 4 one-click actions (Pin intervention, Open Readiness, Open Progress, Open Mock Exam).

**Certification Momentum** cards: per-learner attempt trend, latest score, verdict, exam timestamp. Learners with 0 attempts prompt the manager to create the first assessment trail.

**Agent:** Manager Insights Agent; Assessment Agent (momentum data); Retrospective Agent (risk pattern input)

---

### Screen 11 — Manager → Approvals & Actions

The HITL gate is surfaced here. Draft plans appear with plan ID, learner, cert, total hours, duration, deadline:
- `Approve & Publish` — promotes from `draft` to published (calls `/api/plans/approve`)
- `Review Plan` — opens full study plan before approving

Approval cannot be bypassed — the plan object is `draft` at the data level, not just the UI.

---

### Screen 12 — Manager → Capacity & Simulator

**Counterfactual Readiness Simulator** (tagged `Standout reasoning`):

> *"Test a concrete manager action before committing to it. The simulator estimates workload relief, study-time gain, and target-learner exam movement."*

Inputs: target learner, peer mentor, protected focus hours, reduced meeting hours, review hours/week → `Run what-if`.

Output: score movement (before → after), readiness movement, at-risk movement, capacity pressure — all with explicit **Reasoning Assumptions** (the chain of logic) and a **Recommendation** stating what the intervention cannot fix and what to do next.

**Capacity conflicts flagged** banner alerts when any learner exceeds 25h/wk meeting load.

**Team Members — Work Context** cards: per-learner meeting hours, focus hours, capacity risk (low / medium / high), and recommended study time slots derived from Work IQ signals.

**Agent:** Manager Insights Agent using Work IQ signals; `Standout reasoning` tag indicates the o-series reasoning model path is used for simulation.

---

### Screen 13 — Manager → Peer Learning

Peer pairings matched on domain-level complementarity within same-cert cohorts:

- Match type: `Same-cert mentor match` (shared AZ-204 target)
- Focus domain chosen from learner's weakest area
- Mentor strength (%) vs learner gap (%) shown side-by-side
- Suggested session time derived from Work IQ availability overlap
- `Pin session` saves the pair to the intervention queue

Each card links to: `Open Mentor Readiness`, `Open Learner Progress`, `Open Next Mock Exam`.

**Agent:** Manager Insights Agent (domain-mastery differentials from Assessment Agent)
