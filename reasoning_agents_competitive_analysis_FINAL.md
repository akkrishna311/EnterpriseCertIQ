# Reasoning Agents Hackathon — Enterprise Learning System Competitive Analysis
**Date:** June 10, 2026 | **By:** EnterpriseCertIQ Team | **Status:** COMPLETE

---

## EVALUATION CRITERIA
| Criterion | Weight | Max Points |
|-----------|--------|------------|
| Accuracy & Relevance | 25% | 25 |
| Reasoning & Multi-step Thinking | 25% | 25 |
| Creativity & Originality | 15% | 15 |
| User Experience & Presentation | 15% | 15 |
| Reliability & Safety | 20% | 20 |
| **TOTAL** | 100% | **100** |

---

## CORE CHALLENGE — ENTERPRISE LEARNING SYSTEM
The Reasoning Agents challenge requires a **multi-agent enterprise learning system** capable of:
- Mapping certification requirements to organisational roles
- Generating team-level and role-based study plans
- Providing grounded practice questions from approved knowledge sources
- Adapting learning schedules to real work context and team capacity
- Surfacing manager-level insights across team readiness and risk

**Required Microsoft IQ Layers (at least one):**
- **Work IQ** — work context/calendar signals for scheduling
- **Foundry IQ** — grounded knowledge retrieval with citations
- **Fabric IQ** — semantic business understanding (role→cert→skill ontology)

---

## SCOPE
- Total projects in challenge: **319** (Reasoning Agents filter)
- Projects related to Enterprise Learning System: **~50**
- Projects deep-analysed (visited page + GitHub): **22**
- Projects RULED OUT (wrong domain): **~270**

---

## FILTERED PROJECTS — NOT MATCHING CORE CHALLENGE
> These projects were ruled out as they do not address the Enterprise Learning System scenario

| Project | Domain | Reason |
|---------|--------|--------|
| TransitIQ | Smart Transit | Route/delay prediction |
| SENTINEL Kubernetes | SRE/IT Ops | Incident diagnosis |
| AegisIQ, VulnChain IQ | Cybersecurity | Threat/vulnerability triage |
| FinSight Assurance | Finance | Financial reporting |
| MedReason AI | Healthcare | Claim validation |
| Agent For Finance Report | Finance | Financial reporting |
| Trade Spend Optimization | Retail | Spend optimization |
| Shadow Intel | Cybersecurity | Threat intelligence |
| AutoGenesis | Code Gen | Self-evolving AI platform |
| CareerPilot AI variants | Career Only | No enterprise cert management |
| Sidekick Grief Co-Pilot | Mental Health | Grief support |
| MindPulseAI | Workplace Wellness | Not certification focused |
| StockSense AI | Finance | Stock market |
| ScamShield AI | Cybersecurity | Scam detection |
| Ghost Access Hunter | Identity Security | Access management |
| AI Engineering Squad | Software Dev | Code generation |
| JUEGO DEL CUADRADO | Gaming | N/A |
| DisasterResponseAI | Crisis Management | Emergency coordination |
| Serenity Workplace Copilot | Wellness | Workplace wellness |
| Real-Time Communication Coach | Communication | Not enterprise cert |
| *~250 others* | Various | Not enterprise learning |

---

## TOP COMPETITORS — DETAILED ANALYSIS

---

### 🏆 RANK 1: CertForge - Multi-Agent Certification Intelligence on Microsoft Foundry
**ID:** 123856 | **Developer:** Paramjeet Singh (solo) | **Date:** June 9, 2026

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123856
**GitHub:** https://github.com/Paramjeet-singh-neu/CertForge---Reasoning-Agents-Microsoft-Agents-League-

**Tagline:** "An 8-agent enterprise learning system... grounded in all three Microsoft IQ layers and deployed as a Hosted Agent on Foundry Agent Service."

**Description Summary:**
CertForge is a self-improving multi-agent enterprise certification-intelligence system. It plans, argues, predicts, loops, and learns. 8 specialized agents + manager synthesizer. LIVE deployed as Hosted Agent on Foundry Agent Service (Canada Central, gpt-oss-120b).

**Agents:**
1. Orchestrator (planner, loop control, procedural memory)
2. Learning Path Curator (Foundry IQ + MS Learn MCP server)
3. Study Plan Generator (Fabric IQ semantic scheduling)
4. Engagement Agent (Work IQ study windows, capacity risk)
5. Pattern Analyst (deterministic historical outcome analysis)
6. Assessment Agent (self-reflection, Foundry IQ grounded)
7. Readiness Critic (adversarial evidence-based challenger)
8. Outcome Predictor (3 scenarios + live what-if)
9. Manager Insights (team risk heatmap)

**Microsoft IQ:**
- ✅ Foundry IQ — Azure AI Search KB (certforge-kb) + MCP agentic retrieval
- ✅ Fabric IQ — semantic_model.json: role→cert→skills→threshold→prerequisites
- ✅ Work IQ — work_signals.json: meeting/focus hours, preferred slots

**Tech Stack:** Foundry Agent Service (gpt-oss-120b + text-embedding-3-small), Azure AI Search, MS Learn MCP, Python, Streamlit (4-view), OpenTelemetry/App Insights, 17 tests

**Key Differentiators:**
- 🚀 **LIVE Hosted Agent** on Foundry Agent Service (Canada Central, managed identity)
- 🧠 **Procedural memory** — learns from previous learner patterns
- 🔄 **Feedback loop** — re-plans and re-assesses up to 3 times
- ⚖️ **Readiness Critic** — adversarial evidence-based challenger
- 🔮 **What-if simulator** — live pass-probability adjustment
- 🛡️ **Adversarial safety suite** — Discover→Protect→Govern (6/6 attacks handled)
- 📊 **LOO evaluation** — 93% accuracy, Precision 1.00, Recall 0.89, F1 0.94
- 🔗 **MS Learn MCP server** integration (real learn.microsoft.com URLs)

**GitHub Quality:** EXCEPTIONAL — real Foundry deployment, evaluation harness, guardrails, telemetry, comprehensive README with deployment instructions

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Accuracy & Relevance (25%) | 24/25 | Real Foundry deployment, all 3 IQ layers. All 9 agents. Complete scenario. |
| Reasoning & Multi-step Thinking (25%) | 24/25 | Feedback loops, adversarial debate, self-reflection, what-if — exceptional |
| Creativity & Originality (15%) | 13/15 | Procedural memory + adversarial critic + what-if simulator are genuinely novel |
| User Experience & Presentation (15%) | 13/15 | 4-view Streamlit dashboard, excellent README, deployment story clearly documented |
| Reliability & Safety (20%) | 19/20 | 93% LOO, 17 tests, adversarial safety suite, guardrails, OpenTelemetry |
| **TOTAL** | **93/100** | ⭐⭐⭐⭐⭐ |

---

### 🥈 RANK 2: PassProof
**ID:** 123866 | **Developer:** Eric Guimarães (solo) | **Date:** June 9, 2026

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123866
**GitHub:** https://github.com/mifegui/passproof

**Tagline:** "PassProof tells an engineering manager the one thing learning dashboards can't: who will actually pass their certification exam, who won't..."

**Description Summary:**
Certification readiness as a calibrated probability. Logistic P(pass) fit on synthetic exam outcomes. AUC 0.703 out-of-sample. INSUFFICIENT abstention when data is too thin. PassProof is also an MCP tool (assess_readiness). Real Foundry IQ verified live (5/5 grounded resources). 473 tests.

**Agents (5):**
1. Learning Path Curator (Foundry IQ + MS Learn MCP)
2. Study Plan Generator (Fabric IQ semantic, capacity-aware)
3. Engagement Agent (Work IQ signals)
4. Assessment Agent (Azure AI Content Safety gated, Critic/Verifier)
5. Manager Insights (team readiness roll-up)

**Microsoft IQ:**
- ✅ Foundry IQ — Azure AI Search Knowledge Base, VERIFIED LIVE (5/5 cited resources)
- ✅ Fabric IQ — semantic/ontology.py: Role↔Cert↔Skill↔threshold↔hours
- ✅ Work IQ — work signals (meeting/focus hours, preferred learning slot)

**Tech Stack:** Microsoft Foundry (gpt-4o), LangGraph StateGraph, Azure AI Search, Azure AI Content Safety, MCP server, Python, Vanilla HTML/JS/CSS, OpenTelemetry

**Key Differentiators:**
- 📊 **Calibrated P(pass)** — logistic model, not just quiz scores (AUC 0.703 LOO)
- 🔮 **Abstention** — "INSUFFICIENT" when data too thin (honest uncertainty)
- 🛠️ **PassProof as MCP tool** — any MCP client can call assess_readiness
- 🎬 **3 runtime modes** — Offline/Replay/Live (reliable demo)
- 📋 **473 tests** with no credentials needed
- 🔍 **Audit trail** — full decision chain inspectable
- 🏠 **Offline-first** design (no Azure credentials needed for demo)
- ⚡ **Fastest path to gate** — exact logistic counterfactuals

**GitHub Quality:** EXCEPTIONAL — calibrated statistical model, 473 tests, MCP server, replay system, real Foundry verification

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Accuracy & Relevance (25%) | 23/25 | Real Foundry IQ verified. All 3 IQ layers. All 5 agents. Complete scenario. |
| Reasoning & Multi-step Thinking (25%) | 23/25 | Statistical calibration + abstention + MCP + multi-step pipeline |
| Creativity & Originality (15%) | 14/15 | Calibrated probability + abstention + MCP tool exposure = highly original |
| User Experience & Presentation (15%) | 12/15 | Clean vanilla HTML; 11 screenshots/video; reliable demo design |
| Reliability & Safety (20%) | 18/20 | 473 tests, Content Safety gate, audit trail, offline-first design |
| **TOTAL** | **90/100** | ⭐⭐⭐⭐⭐ |

---

### 🥉 RANK 3: CertifyAI — Multi-Agent Enterprise Learning System
**ID:** 123892 | **Developer:** Bimal Singh (solo) | **Date:** June 10, 2026

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123892
**GitHub:** https://github.com/starkk242/agents-league-reasoning-agent

**Tagline:** "5-agent AI system using Microsoft Foundry, Foundry IQ, Work IQ & Fabric IQ to manage enterprise team certifications..."

**Description Summary:**
Real Azure Foundry + GPT-4o (live demo run evidence). All 3 IQ layers with semantic graph (fabric_iq_model.json). 5 evaluation test scenarios. Hosted agent endpoint. Adaptive escalation loop (2 fails or 14 days inactive → manager alert).

**Agents (5):**
1. LearningPathCuratorAgent (Foundry IQ + Fabric IQ)
2. StudyPlanGeneratorAgent (Fabric IQ semantic graph + Work IQ)
3. EngagementAgent (Work IQ + adaptive escalation)
4. AssessmentAgent (Foundry IQ grounded questions)
5. ManagerInsightsAgent (team analytics dashboard)

**Microsoft IQ:**
- ✅ Foundry IQ — citation-based knowledge retrieval
- ✅ Fabric IQ — semantic graph (fabric_iq_model.json) with prerequisites, role-cert fit scores
- ✅ Work IQ — meeting/focus hours, preferred slots (work_iq_signals.py)

**Tech Stack:** Azure AI Foundry, Python, Azure AI Agents SDK, GPT-4o (East US 2), OpenTelemetry, Azure Monitor, hosted_agent.py

**Key Differentiators:**
- ⚡ **Adaptive escalation** — manager alert after 2 fails or 14 days inactive
- 📊 **Semantic graph** in fabric_iq_model.json (proper Fabric IQ modeling)
- 🔄 **PASS/FAIL routing** — loop back for remediation
- 🧪 **5 automated test scenarios** covering edge cases
- 🚀 **Hosted Agent endpoint** (hosted_agent.py)
- 📡 Live demo run with timing evidence (19.6s, 24.1s per agent run)

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Accuracy & Relevance (25%) | 23/25 | Real Foundry + GPT-4o. All 3 IQ layers. All 5 agents. Live run evidence. |
| Reasoning & Multi-step Thinking (25%) | 22/25 | 5 agents + feedback loop + adaptive escalation. Solid execution. |
| Creativity & Originality (15%) | 11/15 | Adaptive escalation novel; clean solid baseline otherwise |
| User Experience & Presentation (15%) | 12/15 | Good README, architecture diagram, live demo evidence |
| Reliability & Safety (20%) | 17/20 | 5 test scenarios, input validation, OpenTelemetry |
| **TOTAL** | **85/100** | ⭐⭐⭐⭐ |

---

### RANK 4: Inclusive Certification Coach
**ID:** 123869 | **Developer:** Gaurav Patwardhan (solo) | **Date:** June 9, 2026

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123869
**GitHub:** https://github.com/gauravpatwardhan7-web/inclusive-certification-coach

**Tagline:** "...grounded in Microsoft Foundry IQ with cited sources, driven by a visible step-by-step reasoning trace, and designed accessibility-first"

**Description Summary:**
Uses o4-mini reasoning model with visible reasoning traces. Accessibility Narrator (text-to-speech). 4 evaluation suites, 27 assertions passing. Real Azure AI Foundry. Accommodation-aware scheduling.

**Agents (5 + accessibility layer):**
Learning Path Curator, Study Plan Generator, Assessment Agent, Orchestrator (o4-mini), Manager Insights + Accessibility Narrator

**Microsoft IQ:** ✅ Foundry IQ (Azure AI Search), ❌ Work IQ, ❌ Fabric IQ

**Key Differentiators:**
- ♿ **Accessibility-first** — Narrator rewrites output for speech (Web Speech API)
- 🧠 **o4-mini** reasoning model with visible step-by-step traces
- 📊 **27 evaluation assertions** (4 evaluation suites, all passing)
- 🕒 **Accommodation-aware** — 25-min focus blocks, breaks, checkpoints

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Accuracy & Relevance (25%) | 20/25 | Real Foundry. Missing Work IQ + Fabric IQ. |
| Reasoning & Multi-step Thinking (25%) | 21/25 | o4-mini visible reasoning traces are impressive |
| Creativity & Originality (15%) | 14/15 | Accessibility-first is genuinely unique |
| User Experience & Presentation (15%) | 13/15 | Streamlit + speech = strong accessibility UX story |
| Reliability & Safety (20%) | 15/20 | 27 eval assertions, cited sources, accommodation patterns |
| **TOTAL** | **83/100** | ⭐⭐⭐⭐ |

---

### RANK 5: CertOps AI
**ID:** 123430 | **Developer:** ARUN PRASATH GAJAPATHI (solo) | **Date:** June 7, 2026

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123430
**GitHub:** https://github.com/arungajapathi-hash/CertOps-AI

**Tagline:** "Self-Learning Certification Readiness Intelligence Platform — Diagnose certification failure before it happens. Learn from every outcome."

**Description Summary:**
Debate-driven multi-agent evaluation. Readiness Council (5 agents: Optimist, Skeptic, Advocate, Historian, Risk Analyst) + Critic + Assessment + Socratic Coach + Reflection + Reputation Engine. Uses Azure AI Foundry + Foundry IQ. Work IQ and Fabric IQ in roadmap.

**Agents:** Full council of 10 specialized agents including unique Reputation Engine

**Microsoft IQ:** ✅ Foundry IQ, ❌ Work IQ (roadmap), ❌ Fabric IQ (roadmap)

**Key Differentiators:**
- ⚖️ **Readiness Council** — 5 debate agents with independent perspectives
- 📈 **Reputation Engine** — agent accuracy tracked and improves over time
- 🎓 **Socratic Coaching** — guided questioning (not just answer reveal)
- 🔄 **Reflection Engine** — compares prediction vs actual outcome

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Accuracy & Relevance (25%) | 20/25 | Good scenario alignment but missing Work IQ/Fabric IQ |
| Reasoning & Multi-step Thinking (25%) | 22/25 | Debate-driven evaluation is exceptional reasoning pattern |
| Creativity & Originality (15%) | 14/15 | Reputation Engine + Socratic Coach + Council = most creative overall |
| User Experience & Presentation (15%) | 12/15 | Good Streamlit UI with debate visualisation |
| Reliability & Safety (20%) | 14/20 | Missing 2 IQ layers, no formal eval harness shown |
| **TOTAL** | **82/100** | ⭐⭐⭐⭐ |

---

### RANK 6: CertPathAI — No GitHub, Best Description
**ID:** 123637 | **Developer:** Nikhil Budhiraja (solo) | **Date:** June 9, 2026

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123637
**GitHub:** ❌ NOT PROVIDED

**Tagline:** "A 6-agent reasoning system built on Microsoft Foundry that profiles learners, curates grounded study paths... powered by Foundry IQ, Fabric IQ, and Work IQ signals."

**Description Summary:**
Best-written project description. 6 agents with Learner Profiler extra. Largest Remainder Algorithm for study scheduling. 3-tier LLM fallback. All 3 IQ layers. Full telemetry. Guardrail pipeline on all outputs.

**Key Differentiators:**
- 🧮 **Largest Remainder Algorithm** — prevents domain starvation in study plans
- 🔄 **3-tier LLM fallback** (Foundry → mock → cached responses)
- 🛡️ **Guardrail pipeline** on ALL agent outputs
- 🤝 **Human confirmation** required for GO exam decisions

> ⚠️ NO GITHUB — Cannot verify implementation. This is a significant weakness.

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Accuracy & Relevance (25%) | 22/25 | Best-described scenario. All IQ layers. |
| Reasoning & Multi-step Thinking (25%) | 22/25 | Exceptional design: LRA algorithm + multi-tier fallback |
| Creativity & Originality (15%) | 13/15 | Algorithmic scheduling approach is unique |
| User Experience & Presentation (15%) | 10/15 | Good description but NO demo, NO repo |
| Reliability & Safety (20%) | 14/20 | Great safety design but UNVERIFIABLE without code |
| **TOTAL** | **81/100** | ⭐⭐⭐⭐ (with major caveat — no code) |

---

### RANK 7: CertForge AI (Full-Stack) by Mahammad Aftab
**ID:** 123350 | **Developer:** Mahammad Aftab (solo) | **Date:** June 6, 2026

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123350
**GitHub:** https://github.com/mahammadaftab/CertForge-AI

**Tagline:** "An AI-powered multi-agent platform... using Microsoft Foundry IQ, Work IQ, and Fabric IQ."

**Description Summary:**
Most professional full-stack (Next.js 15 + TypeScript + FastAPI + PostgreSQL + Docker). 7 agents. Uses LangGraph/LangChain (not MS Agent Framework). IQ layer claims not fully verifiable.

**Key Differentiators:**
- 🚀 **Production full-stack**: Next.js 15 + TypeScript + FastAPI + PostgreSQL
- 🐳 **Docker** for deployment
- ✅ **Verification Agent** (extra validation layer)
- 📈 **Readiness Prediction Agent** (exam success probability)

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Accuracy & Relevance (25%) | 21/25 | Full scenario. 7 agents. LangChain not MS Agent Framework |
| Reasoning & Multi-step Thinking (25%) | 20/25 | 7 agents with verification + prediction steps |
| Creativity & Originality (15%) | 12/15 | Verification Agent + Prediction Agent add value |
| User Experience & Presentation (15%) | 13/15 | Full-stack Next.js frontend most polished among all |
| Reliability & Safety (20%) | 14/20 | Docker/production-ready but IQ unverified |
| **TOTAL** | **80/100** | ⭐⭐⭐⭐ |

---

### RANK 8: DataDojo IQ
**ID:** 123433 | **Developer:** Rishitha Chowdary Cherukuri (solo) | **Date:** June 7, 2026

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123433
**GitHub:** https://github.com/rishitha-21bce7023/DataDojo-IQ
**Live App:** https://datadojo-iq-foundry.streamlit.app/

**Tagline:** "Multi agent readiness for enterprise Data Engineering teams"

**Description Summary:**
Real Microsoft Foundry via Azure AI Projects SDK (not simulated). Actual vector index with knowledge files. LIVE Streamlit app. 7 agents. Specialised to Data Engineering (not general enterprise certs).

**Key Differentiators:**
- 🔌 **REAL Foundry SDK** — Azure AI Projects SDK (not simulated)
- 🌐 **Live demo app** at streamlit.app URL
- ⚙️ **Config Practice Evaluator** — unique pipeline config practice
- 📚 **5 knowledge base files** (learning guide, pipeline rules, etc.)

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Accuracy & Relevance (25%) | 20/25 | Real Foundry but only Foundry IQ. Data Engineering niche = partial match |
| Reasoning & Multi-step Thinking (25%) | 20/25 | 7 agents, good flow, config practice unique |
| Creativity & Originality (15%) | 11/15 | DataOps focus + Config Practice Evaluator are creative |
| User Experience & Presentation (15%) | 13/15 | Live demo app is excellent differentiator |
| Reliability & Safety (20%) | 15/20 | Real Foundry connection, proper synthetic data |
| **TOTAL** | **79/100** | ⭐⭐⭐⭐ |

---

### RANK 9: Learning-agent-System
**ID:** 123148 | **Developer:** Karthik Aarupalli + 2 (team of 3) | **Date:** June 4, 2026

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123148
**GitHub:** https://github.com/KARTHIK-2004-AI/learning-agent-system/

**Tagline:** "Multi-agent AI system for enterprise certification management — Microsoft Foundry Reasoning Agents Challenge"

**Description Summary:**
Only ACTIVE TEAM (3 members + GitHub engagement). All 5 agents in separate Python files. All 3 IQ layers represented (simulated via JSON). Flask web UI. Clear README. Uses GitHub Models (GPT-4o Azure-hosted) not native Foundry Agent Service.

**Key Differentiators:**
- 👥 **Team of 3** — only project with active team collaboration
- 🏗️ **Separate agent files** — clean architecture
- 💬 **3 GitHub comments** — active community engagement

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| Accuracy & Relevance (25%) | 21/25 | Perfect scenario match but using GitHub Models not native Foundry |
| Reasoning & Multi-step Thinking (25%) | 20/25 | All 5 agents, clear reasoning patterns documented |
| Creativity & Originality (15%) | 10/15 | Standard approach, well executed |
| User Experience & Presentation (15%) | 11/15 | Flask UI, good README |
| Reliability & Safety (20%) | 14/20 | Simulated IQ layers, no formal eval harness |
| **TOTAL** | **76/100** | ⭐⭐⭐⭐ |

---

### RANK 10: Daily Nixtio (Grounded Learning Workspace)
**ID:** 123174 | **Developer:** Ananya Srivastava (solo) | **Date:** June 4, 2026

**GitHub:** https://github.com/ananyaSrivastavaa9/enterprise-learning-agents

Foundry IQ + 3-layer pipeline + premium glassmorphic UI. Missing Work IQ and Fabric IQ. **Score: 74/100** ⭐⭐⭐

---

## OTHER NOTABLE PROJECTS (No GitHub / Incomplete)

| Project | ID | IQ Layers | Differentiator | Status |
|---------|-----|-----------|----------------|--------|
| CertPath | 123150 | All 3 | Perfect description, all 5 agents | NO GITHUB |
| ASTRA | 123176 | All 3 | Treats calendars as "telemetry" | NO GITHUB |
| CertWay | 123166 | Foundry | All 5 agents, MS Foundry | NO GITHUB |
| SCIS | 123184 | Foundry | AI/Legal compliance cert | NO GITHUB |
| SkillForge | 123703 | All 3 | Generator→Verifier assessment | NO GITHUB |
| Crucible-IQ | 123697 | All 3 | Adversarial cert arena | NO GITHUB |
| CertSense AI | 123188 | Foundry | Verbal explanation analysis | NO GITHUB |
| KatsSmartOps LearnAI | 123807 | All 3 | IT Ops→Learning angle | NO GITHUB |
| SkillForge IQ | 123644 | MS IQ | 9 screenshots, 1 bookmark | NO DESC |
| ASCENT | 123801 | All 3 | Team of 2, license only repo | EMPTY REPO |

---

## PROJECTS WITH NOTABLE ISSUES

| Project | ID | Issue |
|---------|-----|-------|
| Learning-agent-System (123273) | Aarush | Uses GROK AI not MS Foundry — fails core requirement |
| OrbitIQ | 123638 | GitHub uses Gemini API, not MS Foundry — major discrepancy |
| Apex-Orchestrator | 123672 | Claims IQ layers but code is Streamlit+JSON, no real Foundry |

---

## YOUR PROJECT: EnterpriseCertIQ

**ID:** 123528 | **URL:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123528
**Developer:** Kalyana Amudalapalli | **Created:** June 8, 2026

**Current State:**
- ✅ Keywords: Work IQ, Foundry IQ, Fabric IQ (all 3 listed)
- ❌ Tagline: TBD
- ❌ Description: TBD
- ❌ GitHub: None
- ❌ Likes: 0 | Bookmarks: 0

### Gap Analysis vs Top Competitors

| Factor | CertForge (93) | PassProof (90) | CertifyAI (85) | YOU (TBD) |
|--------|---------|---------|---------|---------|
| Real Foundry | ✅ | ✅ | ✅ | ❓ |
| All 3 IQ Layers | ✅ | ✅ | ✅ | Keywords only |
| GitHub Repo | ✅ | ✅ | ✅ | ❌ |
| Evaluation Harness | ✅ (93%) | ✅ (473 tests) | ✅ (5 scenarios) | ❌ |
| Deployed Agent | ✅ | ✅ | ✅ | ❌ |
| Working Demo | ✅ | ✅ | ✅ | ❌ |
| Unique Differentiator | Procedural Memory | Calibrated P(pass) | Escalation Loop | ❓ |

### Immediate Actions Required

**Priority 1 — TODAY:**
1. Write compelling tagline and description (even a draft)
2. List your agent architecture (5 agents minimum)
3. Explain how you use each IQ layer

**Priority 2 — This Week:**
4. Create GitHub repository with working code
5. Implement at least Foundry IQ (real Azure AI Search)
6. Add at least 3 test scenarios

**Priority 3 — Before Deadline (June 14):**
7. Create Streamlit or similar UI
8. Add OpenTelemetry telemetry
9. Write evaluation harness
10. Add a unique differentiator (see below)

### Potential Differentiators (Not Taken by Top 3)
- **Teams Bot Integration** — Engagement Agent as a real Teams bot
- **Multi-tenant architecture** — for consultancies managing multiple client orgs
- **Dynamic difficulty adjustment** — ML model adjusting question difficulty in real-time
- **Calendar API integration** — real Microsoft Graph API for Work IQ (not just synthetic)
- **Certification cost ROI tracking** — manager-level financial insights on cert investment

---

## COMPETITIVE RANKINGS SUMMARY

| Rank | Project | ID | Has GitHub | All 3 IQ | Foundry Live | Score |
|------|---------|-----|-----------|----------|------------|-------|
| 1 | CertForge (Paramjeet) | 123856 | ✅ | ✅ | ✅ LIVE | **93/100** |
| 2 | PassProof | 123866 | ✅ | ✅ | ✅ Verified | **90/100** |
| 3 | CertifyAI | 123892 | ✅ | ✅ | ✅ Live run | **85/100** |
| 4 | Inclusive Cert Coach | 123869 | ✅ | ❌ (1) | ✅ | **83/100** |
| 5 | CertOps AI | 123430 | ✅ | ❌ (1) | ✅ | **82/100** |
| 6 | CertPathAI | 123637 | ❌ | ✅ | Described | **81/100** |
| 7 | CertForge AI (Mahammad) | 123350 | ✅ | ✅* | LangChain | **80/100** |
| 8 | DataDojo IQ | 123433 | ✅ | ❌ (1) | ✅ Real SDK | **79/100** |
| 9 | Learning-agent-System | 123148 | ✅ | ✅* | GitHub Models | **76/100** |
| 10 | Daily Nixtio | 123174 | ✅ | ❌ (1) | Foundry IQ | **74/100** |
| - | **EnterpriseCertIQ (YOU)** | 123528 | ❌ | Keywords | ❓ | **TBD** |

*IQ layers partially or conceptually implemented

---

## ANALYSIS NOTES

**What separates the top 3:**
1. **Real Azure Foundry deployment** (not simulated)
2. **Formal evaluation harness** with metrics
3. **All 3 IQ layers** properly integrated (not just claimed)
4. **Hosted Agent deployment** (CertForge is the only truly live one)
5. **Unique differentiator** beyond baseline scenario

**Most common weaknesses in the field:**
- Only 1 IQ layer despite claiming all 3
- No GitHub / unverifiable code
- Simulated IQ layers via JSON files
- No evaluation metrics
- No testing framework

**Key insight for EnterpriseCertIQ:**
The competition is strong but achievable. CertForge (123856) is the clear frontrunner. Focus on matching their real Foundry integration and adding a unique differentiator that none of the top 3 have. Even getting to 80+ points would put you in the top 10.

---

*Analysis completed: June 10, 2026*
*Projects analysed: 22 deep + 30 shallow*
*Total projects reviewed: 319 (Reasoning Agents challenge)*
