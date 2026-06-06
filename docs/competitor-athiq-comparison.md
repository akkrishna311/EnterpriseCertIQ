# Head-to-Head: EnterpriseCertIQ vs. athiq-ahmed/agentsleague

> Code-verified comparison (not README-only). Competitor cloned and inspected:
> `src/cert_prep/*`, `config.py`, `guardrails.py`, `eval_harness.py`, README + 10 docs.
> Date: 2026-06-06.

## What the competitor is

**"Multi-Cert Preparation System"** — a single-developer (Athiq Ahmed), **production-grade
Streamlit app** for personalised Microsoft cert prep across **9 exam families**. Eight
"agents" in a sequential + concurrent pipeline, **17-rule guardrails**, **352 tests**,
**live deployed** at agentsleague.streamlit.app, with a zero-credential mock mode.

It is a **genuinely strong submission** — easily top-cluster, and not in the original
31-project field analysis. On raw software engineering it is more polished than
EnterpriseCertIQ. But it has two structural gaps against the *challenge criteria*.

## The two facts that decide the ranking (code-verified)

1. **No named Microsoft IQ layer.** `grep` for Foundry IQ / Work IQ / Fabric IQ → **zero
   hits**. It uses Azure AI Foundry *Agent Service* (`azure-ai-projects`), Azure OpenAI,
   Azure Content Safety, and `azure-ai-evaluation` — all real — but **none of the three IQ
   layers**. Azure AI Search is roadmap-only (the "AI Search" hits in code are quiz *question
   text*). **SR-5 ("integrate at least one Microsoft IQ layer") is a mandatory requirement** —
   this is the competitor's single biggest exposure.

2. **Only 1 of 8 "agents" actually uses an LLM.** LLM call sites exist in exactly two files
   (`config.py`, `b0_intake_agent.py`). The other seven "agents" — guardrails, study plan
   (Largest Remainder), learning path (static lookup), progress (formula), assessment (static
   30-Q bank), cert recommendation — are **deterministic rule-based Python**. The README states
   this plainly ("5 remaining agents … zero LLM calls"). It's reliable and testable, but the
   "multi-agent **reasoning**" pillar (25%: decomposition, planning, agent collaboration) is
   thin — most stages are functions, not reasoning agents.

Two further scenario gaps follow from #1/#2:
- **No grounded, cited practice questions from approved sources** — questions are a hardcoded
  bank, not Foundry-IQ-grounded with citations. The scenario explicitly asks for this.
- **No manager/team-readiness surface and no work-signal/capacity-aware scheduling** — it's
  individual-learner only (cohort mode is long-term roadmap). The scenario explicitly asks for
  manager insights and work-context adaptation.

## Where the competitor led — and what we've since closed

> **Update (post-implementation):** the competitor's engineering-polish advantages were the
> factors it actually won a prior league on. We have now implemented the high-value ones.

| Area | Competitor | EnterpriseCertIQ (now) |
|---|---|---|
| **Live hosted demo** | ✅ Public on Streamlit Cloud | ✅ Containerised (Dockerfiles) + one-command Azure Container Apps deploy — `docs/deployment.md` |
| **Azure Content Safety** | ✅ Live API call (severity≥2 = BLOCK) | ✅ **Implemented** — live `text:analyze`, regex fallback (`middleware/content_safety.py`) |
| **LLM response cache** | ✅ SHA-256 keyed | ✅ **Implemented** — `core/llm_cache.py`, hit-rate at `/api/cache/stats` + `/health` |
| **Rubric-based agent evals** | ✅ E1–E7, 80% threshold | ✅ **Implemented** — `evals/agent_rubrics.py` + tests, 0.8 threshold |
| **PDF reports** | ✅ profile + assessment | ✅ **Implemented** — learner readiness + manager brief, demo-cached (`reports/pdf.py`) |
| **Demo reliability** | ✅ mock mode + pre-cached PDFs | ✅ LLM cache (instant repeat runs) + demo-cached PDFs |
| **Test depth** | ✅ 352 tests | ⚠️ **51** (up from 29) — meaningful jump; still fewer in raw count |
| **Judge playbook / docs** | ✅ 10 docs + playbooks | ✅ Added `docs/judge-qna-playbook.md` + `docs/deployment.md` |
| **Cert coverage** | ✅ 9 exam families | ⚠️ ~4 certs (registry is extensible) |
| **3-tier LLM fallback** | ✅ Foundry → OpenAI → deterministic | ⚠️ Foundry Local / Azure switch + deterministic plan canonicalisation (not a full 3-tier) |

Remaining competitor edges: raw **test count** (352 vs 51), **cert breadth** (9 vs 4), and a
full **3-tier LLM fallback**. None are structural; all are incremental.

## Where EnterpriseCertIQ BEATS the competitor (the criteria that weigh most)

| Area | EnterpriseCertIQ | Competitor |
|---|---|---|
| **Mandatory IQ layer (SR-5)** | ✅ **All 3** — Foundry IQ (grounded+cited), Work IQ (work signals), Fabric IQ (semantic ontology) | ❌ **None named** |
| **Genuine multi-agent LLM reasoning** | ✅ 7 LLM agents w/ tool-calling, critic→revision loop, readiness loop-back, conditional retrospective | ⚠️ 1 LLM agent + 7 deterministic functions |
| **Grounded, cited practice questions** | ✅ From Foundry IQ approved content | ❌ Static question bank |
| **Manager/team insights** | ✅ Team readiness, risk, peer-learning + intervention queues, **what-if simulator** | ❌ Individual-only |
| **Work-context / capacity-aware scheduling** | ✅ Work IQ meeting/focus signals → Engagement | ❌ Hours budget only |
| **MCP** | ✅ Dual: own FastMCP (10 tools) + Microsoft Learn MCP wired | ⚠️ Config placeholder, not called |

## Rubric scoring (both are top-tier)

| Criterion | Weight | EnterpriseCertIQ | Competitor | Winner |
|---|---|---|---|---|
| Accuracy & Relevance | 25% | 23 | 19 | **ECIQ** — competitor misses cited-grounding, manager insights, IQ layer |
| Reasoning & Multi-step | 25% | 24 | 18 | **ECIQ** — competitor's pipeline is mostly deterministic |
| Reliability & Safety | 20% | 18 | **19** | **Competitor** — 352 tests + live Content Safety |
| Creativity & Originality | 15% | 12 | 12 | Even |
| UX & Presentation | 15% | 13 | **14** | **Competitor** — live deploy + 10 docs + playbooks |
| **Weighted total** | | **~90** | **~84** | **ECIQ ahead** |

**Why EnterpriseCertIQ ranks ahead despite weaker polish:** its advantages land on the two
heaviest pillars (Accuracy 25% + Reasoning 25% = 50%) **and** on the hard mandatory
requirement (IQ layer) the competitor outright misses — judges can heavily penalise or
disqualify SR-5. The competitor's lead is on Safety/UX, which it can't fully convert while a
mandatory box is unticked and 7/8 agents don't reason.

**But the margin is thin and conditional.** If EnterpriseCertIQ stays local-only with 29
tests, the competitor's live deploy + 352 tests + live Content Safety could win the *room* on
perceived maturity. The ranking holds only if ECIQ closes its two soft gaps.

## What to steal from this competitor (high-value, low-effort)

1. **Deploy live now.** Their biggest edge is a public URL. Streamlit-equivalent for us:
   backend → Azure Container Apps, frontend → Static Web Apps. This is lever #2 from the
   position assessment — the competitor proves judges reward it.
2. **Zero-credential demo path + pre-seeded personas + pre-cached results.** Make `./start.sh`
   demo bulletproof without a warm model; cache a canned run per demo learner.
3. **3-tier fallback** (Foundry → Azure OpenAI → deterministic) for demo resilience.
4. **Wire live Azure AI Content Safety** (they have it; we only planned it) — upgrades RAI from
   regex to a named Azure control.
5. **Expand tests toward rubric-based agent evals** — copy their `test_agent_evals.py` pattern
   (per-agent quality rubric E1–E7 with a pass threshold), not just unit tests.
6. **LLM response cache (SHA-256 keyed)** — cost + latency + demo speed.
7. **PDF report export** (learner + assessment/manager) — they prove its demo value; we already
   capture the trace.
8. **Judge Q&A playbook + drawio architecture diagram** — presentation polish.

## One-line verdict

Both are top-cluster. **EnterpriseCertIQ is ahead on the criteria that decide this challenge
(scenario fit, genuine multi-agent reasoning, and the mandatory all-3 IQ integration), and the
competitor is ahead on deployment maturity, test depth, and live safety tooling.** Close the
deploy + test + Content-Safety gap and EnterpriseCertIQ wins clearly; leave them open and it's
a coin-flip in the demo room.
