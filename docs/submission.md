# EnterpriseCertIQ — submission copy (paste into Innovation Studio)

## Tagline
A 9-agent reasoning system on Microsoft Foundry that turns certification readiness into a
**calibrated, grounded, manager-ready decision** — and teaches the weakest concept back as a
NotebookLM-style audio podcast.

## Short description (~120 words)
EnterpriseCertIQ is a multi-agent enterprise learning system built on Microsoft Foundry. Nine
specialized agents — intake, learning-path curator, study-plan generator, **adversarial
readiness critic**, engagement, assessment, manager insights, retrospective, and an orchestrator
— plan, argue, predict, and loop. It grounds every claim in **Foundry IQ** (real Azure AI Search,
cited), reasons over a **Fabric IQ** role→cert→skill→threshold ontology (plus a live Microsoft
Fabric IQ ontology tool), and adapts schedules to **Work IQ** capacity signals. Readiness is a
**calibrated P(pass)** (leave-one-out AUC ≈ 0.80) that abstains as *INSUFFICIENT* when evidence is
thin. A React workspace shows the live reasoning trace, a what-if simulator, an HITL exam gate —
and a two-voice **audio podcast** that coaches the learner's weakest domain. App Insights tracing,
azure-ai-evaluation agent scorers, and Azure Content Safety throughout.

## The 9 agents
intake · learning-path curator · study-plan generator · readiness critic (adversarial) ·
engagement · assessment · manager insights · retrospective · orchestrator (loop control)

## How each Microsoft IQ layer is used (honest)
- **Foundry IQ — real.** Azure AI Search index (`cert-knowledge-base`) queried live; the curator
  and assessment agents return **cited** excerpts (verified: real BM25 relevance + source URLs).
- **Fabric IQ — semantic ontology + live product.** A role→cert→skill→weight→threshold ontology
  drives readiness, the critic's leverage-weighted objections, and team skill-gap analysis
  (local + Lakehouse SQL). **Plus** a real Microsoft **Fabric IQ ontology tool** wired into a
  Foundry agent (OBO) for NL2Ontology queries.
- **Work IQ — capacity signals.** Meeting/focus hours + preferred slots drive scheduling and
  reminder timing; a Microsoft Graph (`Calendars.Read`) path is built for the real-calendar upgrade.

## Differentiators (what others don't have)
- 🎙️ **NotebookLM-style two-voice audio podcast** that teaches the weakest concept — unique in the field.
- 📊 **Calibrated P(pass)** with **INSUFFICIENT abstention** — honest uncertainty, LOO AUC ≈ 0.80.
- ⚖️ **Adversarial critic → replan loop** with leverage-weighted objections.
- 🔮 **Manager what-if simulator** + HITL exam gate + live reasoning trace.
- 🛡️ Azure Content Safety, LLM response cache, App Insights tracing, graceful local↔cloud fallback.

## Metrics & quality
- Calibrated readiness model: **LOO AUC 0.802, Brier 0.183** over 102 synthetic learners
  (`python scripts/run_readiness_eval.py`).
- **azure-ai-evaluation**: groundedness/relevance/coherence/fluency + **agent evaluators**
  (Intent Resolution, Tool Call Accuracy, Task Adherence) — `scripts/run_foundry_eval.py`.
- **85 automated tests**; App Insights telemetry (workflow→agent→tool spans).

## Stack
Microsoft Foundry (Agent Service / Azure OpenAI gpt-4.1), Azure AI Search (Foundry IQ),
Microsoft Fabric IQ ontology, azure-ai-projects, azure-ai-evaluation, Azure AI Content Safety,
FastMCP + MS Learn MCP, FastAPI + React/Vite, OpenTelemetry → Application Insights.
