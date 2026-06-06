# Judge Q&A Playbook — EnterpriseCertIQ

A demo script + anticipated judge questions with crisp, evidence-backed answers. Map every
claim to a file or a clickable artifact.

## 90-second demo script

1. **Open the dashboard** → pick learner **L-1004 (Cloud Engineer, AZ-204)**.
2. **Run workflow** → narrate the live reasoning stream (SSE): Intake → Curator (cites
   Foundry IQ + MS Learn) → Planner → **Critic attacks the plan** (leverage-weighted via
   Fabric IQ) → revision → Engagement (Work IQ slots) → Assessment (cited questions) →
   Manager Insights. Point out the **HITL approval gate** — the plan stays `draft`.
3. **Approve the plan** at the gate → show it flips to published.
4. **Manager view (TEAM-A)** → readiness distribution, Fabric IQ top skill gap, what-if
   simulator (protect focus hours → projected readiness delta), peer-learning + intervention
   queues.
5. **Download the Manager Handoff Brief PDF** and a **Learner Readiness PDF**.
6. **/health** → show all 3 IQ layers, `content_safety: azure`, and the **LLM cache
   hit-rate** climbing when you re-run the same learner (instant, ~0 tokens).

## Scoring-criteria cheat sheet

| Criterion | Lead with | Evidence |
|---|---|---|
| Accuracy & Relevance | All 5 baseline agents + manager insights + grounded cited questions | `backend/agents/factory.py`, Foundry IQ citations in trace |
| Reasoning & Multi-step | 8 LLM agents, critic→revision loop, readiness loop-back, retrospective | `backend/core/workflow.py` |
| Reliability & Safety | HITL gate, Azure Content Safety, PII/citation gate, 51 tests, rubric evals, LLM cache | `middleware/`, `evals/agent_rubrics.py`, `tests/` |
| Creativity | What-if simulator, retrospective meta-agent, all-3-IQ each on a runtime path | `main.py` what-if, `iq/fabric_iq.py` |
| UX & Presentation | Live deploy, SSE reasoning stream, PDF exports, charts | `docs/deployment.md`, frontend components |

## Anticipated questions

**Q: Which Microsoft IQ layers do you use?**
All three, each on a real runtime path. Foundry IQ = grounded cited retrieval
(`iq/foundry_iq.py`); Work IQ = work-context signals driving engagement/manager
(`iq/work_iq.py`); Fabric IQ = semantic ontology (roles/certs/weighted domains/thresholds/
cohort) used by the Critic and Manager (`iq/fabric_iq.py`, MCP tool `fabric_iq_semantics`).

**Q: Is this real Microsoft Foundry or simulated?**
Real. `core/client.py` uses Foundry Local SDK in dev and the `azure-ai-inference` Azure AI
Foundry path in cloud (managed identity supported). Switch is one env var. Foundry IQ has a
real Azure AI Search branch; deployment guide wires it.

**Q: How do you prevent hallucinated / unsafe output?**
Layered: PII redaction, citation-or-flag gate, **live Azure AI Content Safety**
(`middleware/content_safety.py`, severity ≥ threshold → BLOCK, regex fallback offline),
bias audit, and honest `insufficient_evidence` instead of a fabricated forecast.

**Q: How is this more than a prompt chain?**
Genuine multi-agent orchestration with a **Critic/Verifier loop** (red/amber objections →
bounded re-plan), a deterministic readiness gate separated from the LLM verdict
(`_readiness_from_forecast`), a conditional **retrospective** meta-agent on prior failures,
and a **HITL approval gate**. Control flow is in `core/workflow.py`.

**Q: What's your evaluation / testing story?**
51 automated tests, zero credentials. Includes **rubric-based agent-quality evals**
(`evals/agent_rubrics.py` + `tests/test_agent_rubrics.py`, per-agent E-checks, 0.8 pass
threshold) and a groundedness evaluator (heuristic local / `azure-ai-evaluation` in cloud).

**Q: Observability?**
OpenTelemetry spans (`workflow.run`, `agent.*`) → console locally, Application Insights in
Azure. Live SSE reasoning trace in the UI; persisted traces survive reload. `/health`
surfaces IQ modes, content-safety mode, and LLM cache hit-rate.

**Q: Cost / demo reliability?**
SHA-256 **LLM response cache** — repeat identical (temperature-0) calls skip the model
entirely (instant, deterministic, ~0 tokens). Demo personas + cached PDFs make live demos
bulletproof.

**Q: Privacy?**
Synthetic data only (`L-1001`/`EMP-001`/`TEAM-A`). Manager Insights never exposes individual
exam scores — enforced and unit-tested (rubric check M3).

**Q: Deployment?**
Containerised (backend + frontend Dockerfiles), one-command Azure Container Apps deploy in
`docs/deployment.md`; the nginx proxy keeps SSE streaming working in prod.

## Honest gaps (own them)

- **Fabric IQ Azure binding** — semantic layer runs as a local ontology today; the Azure
  Fabric/OneLake binding is scoped in the migration guide (contract is identical).
- **Work IQ source** — signals are synthetic; the adapter seam (`WorkContext`) is defined for
  a Graph/Cosmos source.
- **Hosted Agent Service** — we run as a FastAPI app with an in-process agent runtime on
  Container Apps, not (yet) as a Foundry Hosted Agent. Inference + IQ are already on Azure.
