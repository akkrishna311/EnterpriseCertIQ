# Enterprise Agents Hackathon — Competitive Analysis
**Date:** June 10, 2026 | **Track:** Battle #3 — Enterprise Agents for Microsoft 365 Copilot | **Status:** COMPLETE

---

## EVALUATION CRITERIA

| Criterion | Type | Notes |
|-----------|------|-------|
| Microsoft 365 Copilot Chat Agent | **REQUIRED** | Must be hosted in M365 Copilot Chat |
| Microsoft IQ Integration | **REQUIRED** | At least one of Foundry IQ / Work IQ / Fabric IQ |
| Agent Type (DA / CEA / Copilot Studio) | Quality | Depth of M365 integration |
| MCP Apps | **BONUS (Higher Rating)** | Packages MCP into M365 Copilot extensibility |
| External MCP Server (Read/Write) | Optional | Real enterprise system integration |
| OAuth Security for MCP | Optional | Proper Entra ID / OAuth 2.0 |

---

## SCOPE
- Total EA projects: **128** (matched challenge description)
- Deep-analysed: **18** (visited page + GitHub)
- Ruled out (not M365/Copilot focused): **~40**

## DISQUALIFICATION CRITERIA
The #1 requirement is agent hosted IN Microsoft 365 Copilot Chat.
Projects using standalone apps (FastAPI+React) without M365 Copilot Chat do NOT meet core requirement.
Projects using Gemini / mock M365 data without real Graph integration are heavily penalized.

---

## RANKED PROJECT ANALYSIS

---

### RANK 1: Sutradhara - Autonomous Account Lifecycle Agent
**ID:** 123490 | **Developer:** Ganesh Giridhar Kankatala (solo) | **Date:** June 8, 2026

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123490

**GitHub:** https://github.com/Ganesh2006646/Agent-League-Hackathon---microsoft (8 commits, active)

**Tagline:** Enterprise-grade autonomous agent for policy-driven student account provisioning and IT compliance management.

**Summary:** Turns student account restoration from 24-48 hour ticket queue into sub-5-minute AI-orchestrated service.

**Tech Stack:**
- Microsoft Copilot Studio (Declarative Agent - real declarativeAgent.json manifest)
- Foundry IQ (5 RIT Policy documents in /policies folder)
- Microsoft Graph API (User.ReadWrite.All + Sites.ReadWrite.All + Mail.Send)
- SharePoint Lists (FinanceLedger, HoldRegistry, AuditLog)
- Microsoft Teams + Adaptive Cards (approval-card, status-notification, anomaly-alert)
- Microsoft Entra ID OAuth (app registration, admin consent)
- Node.js / Express backend on Azure App Service
- Plugin architecture with OpenAPI specs (graph-account-api.yaml, sharepoint-finance-api.yaml)

**Microsoft IQ:** Foundry IQ (5 policy docs), Microsoft Graph (Work IQ proxy)

**M365 Copilot Chat:** YES - Real DA manifest + Teams App Package
**MCP Apps:** YES - Plugin architecture with 3 OpenAPI specs
**External MCP/Read-Write:** YES - Finance API (read) + MS Graph account management (write)
**OAuth:** YES - Full Entra ID with admin consent

**Key Differentiators:**
- Real declarative agent manifest with Teams App Package
- Full SharePoint audit trail with policy citations
- Human-in-the-loop via Teams Adaptive Cards (IT approval)
- 5 policy documents as Foundry IQ knowledge base
- 6 demo scenarios (happy path, partial payment, expired hold, active investigation, hardship, security anomaly)
- KPIs: <5 min vs 24-48 hours, 100% policy-cited, 90%+ autonomous resolution
- Full Azure deployment guide (App Service + SharePoint provisioning + Teams sideloading)

| Criterion | Score | Rationale |
|-----------|-------|----------|
| Accuracy & Relevance (25%) | 24/25 | Real M365 + Foundry IQ + all requirements met |
| Reasoning & Multi-step Thinking (25%) | 23/25 | Policy-driven multi-step verification chain |
| Creativity & Originality (15%) | 13/15 | Education IT + policy-grounded service + hardship policy |
| User Experience & Presentation (15%) | 13/15 | 6 demo scenarios, Teams Adaptive Cards, dashboard |
| Reliability & Safety (20%) | 19/20 | Entra OAuth, HITL, audit trail, anomaly detection |
| **TOTAL** | **92/100** | TOP COMPETITOR |

---

### RANK 2: SkillForge Copilot Agent
**ID:** 123776 | **Developer:** Carlos Garcia Miguel (solo) | **Date:** June 9, 2026 | **Likes:** 1 | **Bookmarks:** 1

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123776
**GitHub:** https://github.com/carlgar512/SkillForge-Copilot-Agent
**Demo Video:** YES

**Tagline:** A Copilot Studio enterprise agent for manager-ready certification readiness briefings.

**Summary:** Real Copilot Studio agent with 9 screenshots proving implementation, demo video, 5 conversation topics, 5 knowledge sources, all 3 IQ patterns, and Responsible AI boundaries.

**Tech Stack:** Microsoft Copilot Studio, 5 synthetic knowledge docs, Mermaid architecture diagrams

**Microsoft IQ:**
- Foundry IQ-style: approved synthetic knowledge docs as ground truth
- Work IQ-style: workload + weekly learning capacity context
- Fabric IQ-style: team/learner/cert/skill/threshold semantic relationships

**M365 Copilot Chat:** YES - Native Copilot Studio agent
**MCP Apps:** NO
**External MCP:** NO
**OAuth:** NO

**Key Differentiators:**
- 9 screenshots proving actual Copilot Studio implementation
- 5 purpose-built conversation topics (not generic chatbot)
- Responsible AI boundary - explicitly refuses employment/promotion decisions
- Full documentation: agent-instructions.md, topics/, knowledge/, diagrams/
- Demo video showing actual agent behavior
- Mermaid diagrams (architecture, conversation flow, RA boundary, knowledge map)
- Same developer as SkillForge IQ (Reasoning Agents) - cross-challenge commitment

| Criterion | Score | Rationale |
|-----------|-------|----------|
| Accuracy & Relevance (25%) | 22/25 | Real Copilot Studio. All 3 IQ patterns. No external system integration. |
| Reasoning & Multi-step Thinking (25%) | 20/25 | 5 topics with multi-step flows. Good but no external data. |
| Creativity & Originality (15%) | 12/15 | Manager cert briefings focused; RA boundary thoughtful |
| User Experience & Presentation (15%) | 14/15 | Best-documented: 9 screenshots + demo video + diagrams |
| Reliability & Safety (20%) | 17/20 | RA boundaries coded, synthetic data only |
| **TOTAL** | **85/100** | STRONG COMPETITOR |

---

### RANK 3: Council Assist - Enterprise Knowledge Agent for Local Government
**ID:** 123165 | **Developer:** Christopher Ekorhi + 3 (TEAM OF 4) | **Date:** June 4, 2026 | **Likes:** 2

**Platform:** https://innovationstudio.microsoft.com/hackathons/Agents-League-Hackathon/project/123165
**GitHub:** NONE | **Demo Video:** YES

**Tagline:** AI-powered M365 Copilot agent for council officers to find policies, draft responses, escalate cases via Work IQ.

**Summary:** Work IQ with MCP tools (Work IQ User MCP + Work IQ Copilot MCP), 14 SharePoint policy docs, Power Automate escalation, Teams, Entra ID. Largest team in challenge.

**Microsoft IQ:** Work IQ (primary + MCP tools)
**MCP Apps:** YES - Work IQ User MCP + Work IQ Copilot MCP
**OAuth:** YES - Entra ID

**Key Differentiators:**
- Largest team (4 people)
- Work IQ MCP tools connected (Work IQ User MCP + Copilot MCP)
- Local government social impact scenario
- HHSRS Category 1 escalation detection
- 2 likes (second highest)

| Criterion | Score | Rationale |
|-----------|-------|----------|
| Accuracy & Relevance (25%) | 22/25 | Real Copilot + Work IQ + MCP tools. No GitHub. |
| Reasoning & Multi-step Thinking (25%) | 20/25 | Multi-doc reasoning, escalation detection |
| Creativity & Originality (15%) | 12/15 | Local government vertical is underserved |
| User Experience & Presentation (15%) | 13/15 | Demo video + Teams integration |
| Reliability & Safety (20%) | 15/20 | Entra ID, Work IQ citations, no code to verify |
| **TOTAL** | **82/100** | STRONG COMPETITOR |

---

### RANK 4: Metric Narrator *(M365 Chat requirement risk)*
**ID:** 123620 | **Developer:** Krrish Yaduka | **Date:** June 9, 2026

**GitHub:** https://github.com/krrish2803/Metric-Narrator

**CRITICAL NOTE:** This is a standalone FastAPI + React app that sends TO Teams, not hosted IN M365 Copilot Chat. May fail the #1 requirement.

**Summary:** Power BI anomaly detection with 5-node LangGraph pipeline (Detect->Contextualize->Blast Radius->Narrate->Route). All 3 IQ layers. Exceptional code quality.

**Microsoft IQ:** Fabric IQ (ontology) + Foundry IQ (root cause) + Work IQ (Teams delivery)

| Criterion | Score | Rationale |
|-----------|-------|----------|
| Accuracy & Relevance (25%) | 16/25 | Fails M365 Copilot Chat requirement (standalone app) |
| Reasoning & Multi-step Thinking (25%) | 22/25 | Excellent LangGraph pipeline with financial math |
| Creativity & Originality (15%) | 13/15 | Power BI + financial blast radius + proactive delivery |
| User Experience & Presentation (15%) | 13/15 | Best code quality, live demo, architecture diagrams |
| Reliability & Safety (20%) | 15/20 | Well-coded, Teams webhook (not Copilot) |
| **TOTAL (adjusted)** | **79/100** | Score adjusted for M365 requirement risk |

---

### RANK 5: Burnout Radar
**ID:** 123343 | **Developer:** Avriy Divine Mercado | **Date:** June 5, 2026
**GitHub:** https://github.com/Divinely06/burnout-radar | **Demo Video:** YES

**Summary:** Power Automate + Microsoft Graph + AI Builder. Privacy-first (metadata only). Work IQ + Foundry IQ. Weekly burnout risk Teams/email.

| **TOTAL** | **77/100** | STRONG COMPETITOR |

---

### RANK 6: Continuum
**ID:** 123762 | **Developer:** Adrian Issac | **Date:** June 9, 2026
**GitHub:** https://github.com/S-kkipie/Continuum (Spec 0 - walking skeleton)

**Summary:** All 3 IQ layers, Next.js + FastAPI + Turborepo + Bicep + Microsoft Agent Framework. BUT Spec 0 only (early implementation).

| **TOTAL** | **75/100** | PROMISING BUT INCOMPLETE |

---

### RANK 7: Onboarding Buddy
**ID:** 123366 | **Team of 3** | **Likes:** 3 (HIGHEST) | **Date:** June 6, 2026
**GitHub:** NONE

**Summary:** Work IQ onboarding agent. Most popular (3 likes). No code/GitHub. Strong concept.

| **TOTAL** | **68/100** | POPULAR BUT UNVERIFIABLE |

---

### RANK 8: DealPilot M365 Agent
**ID:** 123145 | Renu Vishwakarma | **Date:** June 4, 2026 | **Likes:** 1
**GitHub:** NONE

**Summary:** 3 DA agents + orchestrator + Graph API + MCP CRM server + Entra OAuth. Excellent design concept but no code.

| **TOTAL** | **72/100** | STRONG CONCEPT, NO CODE |

---

### RANK 9: CrisisOps IQ (123547) - Score: 72/100
GitHub: https://github.com/Dr-Ahmed-Abdelsalam/crisisops-iq | Foundry IQ + crisis management.

### RANK 10: DevPulse (123456) - Score: 71/100
GitHub: https://github.com/aparajithashree919/devpulse | Copilot Studio + Foundry+Work IQ + demo video.

---

## COMPETITIVE SUMMARY TABLE

| Rank | Project | ID | GitHub | IQ Layer | MCP | OAuth | Score |
|------|---------|-----|--------|----------|-----|-------|-------|
| 1 | Sutradhara | 123490 | YES | Foundry IQ | YES | YES | **92/100** |
| 2 | SkillForge Copilot Agent | 123776 | YES | All 3* | NO | NO | **85/100** |
| 3 | Council Assist | 123165 | NO | Work IQ+MCP | YES | YES | **82/100** |
| 4 | Metric Narrator | 123620 | YES | All 3 | NO | NO | **79*** |
| 5 | Burnout Radar | 123343 | YES | Work+Foundry | NO | NO | **77/100** |
| 6 | Continuum | 123762 | YES | All 3 planned | NO | YES | **75/100** |
| 7 | Onboarding Buddy | 123366 | NO | Work IQ | NO | NO | **68/100** |
| 8 | DealPilot M365 | 123145 | NO | SharePoint | YES | YES | **72/100** |
| 9 | CrisisOps IQ | 123547 | YES | Foundry IQ | NO | NO | **72/100** |
| 10 | DevPulse | 123456 | YES | Foundry+Work | NO | NO | **71/100** |

*All 3 = IQ design patterns; Metric Narrator* = strong code but M365 Chat requirement risk

---

## KEY FINDINGS

### Strongest Competitor
**Sutradhara (ID 123490)** is the clear frontrunner with real Declarative Agent manifest, real Graph API, real SharePoint, Foundry IQ, MCP plugins, and Entra OAuth all verified in GitHub.

### Second Strongest
**SkillForge Copilot Agent (ID 123776)** is most polished with real Copilot Studio screenshots, demo video, and Responsible AI boundaries. Same developer as SkillForge IQ (Reasoning Agents).

### Watch List
- **Onboarding Buddy (123366)** — 3 likes (most popular), team of 3, strong use case. Could be further developed.
- **Council Assist (123165)** — 2 likes, team of 4, Work IQ MCP tools, public sector impact.

### Common EA Weaknesses
1. Most projects are standalone apps NOT hosted in M365 Copilot Chat
2. Many use non-Microsoft AI (Gemini, OpenAI without Azure)
3. Most implement only 1 IQ layer
4. Only Sutradhara has real OAuth + real MCP architecture
5. Very few have verified demo videos in Copilot Chat

---

*Analysis completed: June 10, 2026 | Total EA projects: 128*
