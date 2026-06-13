# LLM Handoff

This document is the implementation handoff for another LLM working on EnterpriseCertIQ.
**Read the "Continuation — June 13 2026" section first** (latest state); the original
May 2026 stabilization notes follow below for history.

---

## Continuation — June 13 2026 session (demo-prep: UI redesign, telemetry, competitor features)

### Where things stand
- Branch **`develop`**, working tree clean, everything pushed to `origin/develop`.
- Runtime during this session: **`MODEL_BACKEND=azure_foundry`**, `ENABLE_TELEMETRY=true`,
  App Insights connection string set. (This laptop loses Azure access — the next laptop
  has it. Recreate `.env.local` there; it is gitignored, see "Running on a new machine".)
- App is demo-ready. The owner is recording the demo video.

### What was done this session (all display/UX + targeted fixes — core agent logic unchanged)

1. **Approval flow + state persistence.**
   - `generate_study_plan` (`backend/mcp_server/server.py`) now `save_plan()`s the plan and
     **deletes prior drafts** for the same learner+cert (no stale cards / no approve-cycling).
   - New `GET /api/plan/{plan_id}` and `GET /api/traces/{learner_id}` (`backend/main.py`).
   - `LearnerView.tsx` persists `planId` **and** `runId` in the URL and restores `planData`,
     `events`, and objections after navigation (Manager → Review Plan → back).
   - Approval is a **manager** action (Manager → Approvals & Actions); learner sees read-only
     "awaiting manager approval".

2. **Retrospective now triggers on in-session failed mocks.** `run_workflow` (`backend/main.py`)
   enriches `learner.prior_attempts` with any failed submitted assessments before the pipeline,
   so `has_prior_failures` flips true and Stage 8 runs. (Seed JSON only had prior_attempts for
   L-1006; L-1004's 35% mock now triggers it.)

3. **Plan Review de-duplication.** The critic runs a deliberate loop (round 1 → revise → round 2);
   each round emits a complete `critic_objection` snapshot. `LearnerView.tsx` now shows the
   **latest snapshot** (replace, not accumulate) and rebuilds objections from the trace on restore.
   The double critic in the Journey Trace is expected (the loopback).

4. **Dark "command-center" UI redesign (whole app).**
   - Design tokens + reusable classes in `frontend/src/index.css` (`.panel`, `.pill-*`,
     `.subtab`, `.stat-tile`, `.field-dark`, `.btn-*`); semantic colors in `tailwind.config.js`
     (`surface`, `line`, `ink`, `accent`) and **`borderColor.DEFAULT = var(--line)`** so bare
     `border` is the subtle dark line everywhere.
   - `App.tsx` glassy sticky nav. Manager screen split into **4 in-page tabs**
     (Overview / Approvals & Actions / Capacity & Simulator / Peer Learning) to kill scrolling.
   - Bulk light→dark class conversion across `pages/` + `components/` (ReasoningPanel was already dark).

5. **Legibility fixes** (all were dark-on-dark leftovers): `DomainMasteryChart` axis ticks/labels,
   `ServiceHeatmap` status pills (`text-green-800`/`text-red-800` → emerald/rose-300),
   "Suggested next step" label, default borders.

6. **Surfaced 2 competitor-parity features that were API-only:**
   - **GO / CONDITIONAL_GO / NOT_YET** booking-verdict badge on the Practice Exam result
     (`LearnerView.tsx`, reads `booking_verdict` from `/api/assessment/submit`).
   - **ROI cost-of-delay** tile on the Manager Overview (`ManagerView.tsx`, reads `roi_summary`
     from `/api/manager/{team}/insights`). Types added in `frontend/src/api/client.ts`.

7. **Telemetry: App Insights `operation_Id` == UI run_id.** `backend/core/telemetry.py`
   `workflow_span` seeds the root span's trace-id from the run_id (UUID = 128-bit trace-id, dashes
   stripped); all child agent/model/tool spans inherit it. Search App Insights Transaction Search
   by the Journey Trace id with dashes removed. Falls back to default if run_id isn't a 32-hex UUID.

### The 7 competitor-parity features and where they live (for the demo)
| # | Feature | Code | UI screen |
|---|---------|------|-----------|
| 1 | GO/CONDITIONAL_GO/NOT_YET verdict | `backend/evals/readiness_model.py:booking_verdict` | Learner → Practice Exam result (badge) |
| 2 | Red-team + scorecard evals | `eval/redteam.json`, `eval/scorecard.json` | Learner → Exam Readiness (Trust & Safety) + Safety & RAI |
| 3 | Largest Remainder Algorithm | `backend/mcp_server/server.py:_lra_allocate_hours` | Learner → Study Plan (per-week hours) |
| 4 | Manager alert on consecutive NOT_YET | `backend/main.py` (`trigger: consecutive_not_yet`) | Manager → Approvals & Actions → Intervention Queue |
| 5 | ROI cost-of-delay | `backend/main.py` (`roi_summary`) | Manager → Overview (tile) |
| 6 | `azure.yaml` (azd up) | `azure.yaml` | not a screen — show `azd up` in a terminal |
| 7 | Parallel Engagement + Forecast | `backend/core/workflow.py:402` (`asyncio.gather`) | Journey Trace timing / code |

### Project-specific conventions (must follow)
- **Never commit `.env.local`** (gitignored; holds live `AZURE_AI_API_KEY`, `AZURE_SEARCH_KEY`,
  App Insights connection string).
- **Do not add a `Co-Authored-By: Claude ...` line** to commit messages — commits appear under the
  owner's name only.

### Running on a new machine (Azure path)
1. `git clone <repo> && cd enterprisecertiq && git checkout develop`
2. `cp .env.example .env.local` and fill in the Azure creds (keep `MODEL_BACKEND=azure_foundry`,
   `ENABLE_TELEMETRY=true`, the App Insights connection string). **Never commit it.**
3. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements.azure.txt`
4. `npm install --prefix frontend`
5. Backend: `.venv/bin/uvicorn backend.main:app --reload --port 8000` · Frontend: `npm run dev --prefix frontend` (5173)
6. `backend/data/store/` (plans/traces/assessments) is **gitignored** — the clone starts with an
   empty store. Re-run "Build My Plan" a couple of times to regenerate demo data, or copy the
   folder over manually.
- A convenience script is at `scripts/laptop-setup.sh`.

### Files to read first (this session)
- `backend/main.py` (run_workflow enrichment, plan/trace endpoints, roi_summary, booking_verdict)
- `backend/core/telemetry.py` (run_id → trace-id)
- `backend/mcp_server/server.py` (draft cleanup, LRA)
- `frontend/src/pages/LearnerView.tsx` and `frontend/src/pages/ManagerView.tsx`
- `frontend/src/index.css` + `frontend/tailwind.config.js` (dark design system)

---

## Original handoff (May 2026 stabilization pass)

This document is the implementation handoff for another LLM working on EnterpriseCertIQ after the May 2026 debugging and stabilization pass.

## Current intent

The app is a local-first reasoning-agent demo for the Microsoft Agents League scenario. The current codebase prioritizes:

- Foundry Local for day-to-day iteration.
- Azure Foundry as the later criteria-proof path.
- Visible multi-agent reasoning in the learner UI.
- Structured data handoff between agents instead of relying on free-form prose.
- HITL approval before any plan is treated as publishable.

## Fast local workflow

Use these assumptions unless the user explicitly wants a different environment:

```bash
./start.sh --no-setup --skip-model
```

Operational notes:

- Python 3.11 in `.venv` is the working environment.
- Foundry Local must expose `http://localhost:5273/v1`.
- The Foundry Local SDK must use app name `enterprisecertiq` or the model cache path changes.
- Starting the Foundry Local web service is required. Loading a cached model without the web service will not satisfy backend calls.
- `start.sh` is the preferred launcher because it starts the model service, MCP server, FastAPI backend, and Vite frontend together.

## What changed

### Backend reasoning and workflow

- `backend/core/agent.py`
  - `AGENT_COMPLETE` events now carry richer payloads including rendered content, structured output, warnings, groundedness, and token usage.
  - When structured parsing succeeds, agent content is normalized into canonical JSON for the frontend instead of leaving raw malformed text.
  - If Foundry Local returns malformed text, the agent code can fall back to recent tool payloads when they match the declared response schema.

- `backend/models/agent_outputs.py`
  - Added typed schemas for curator, critic, engagement, and manager outputs.
  - Curated topic normalization and deduplication was added to reduce repeated topics from the model.

- `backend/agents/factory.py`
  - Structured `response_format` is wired into agent creation.
  - Curator, planner, critic, engagement, and manager agents use explicit schemas.
  - Lower temperatures are used for the structured-output-heavy agents.

- `backend/core/workflow.py`
  - Later stages consume structured payloads instead of raw prose whenever possible.
  - Red critic objections are detected structurally.
  - If the planner returns malformed output, the workflow now synthesizes a canonical plan through `generate_study_plan.fn(...)`.
  - The fallback also emits a `tool_result` event so the frontend can still discover `plan_id` and related plan fields.

- `backend/main.py`
  - Assessment generation already uses `generate_assessment.fn(...)`.
  - Post-save progress generation now uses `compute_progress_series.fn(...)` so the UI can receive the `compute_progress_series` tool event.
  - The workflow save path still expects `ctx.outputs["final_plan"]` to be JSON-compatible or already dict-shaped.

- `backend/mcp_server/server.py`
  - `generate_study_plan` returns a canonical `StudyPlan`-shaped object with `plan_id`, `learner_id`, `cert_id`, `created_at`, `deadline`, `weeks`, and `progress_series`.
  - Mock-exam generation was rewritten to vary question stems, services, explanations, and option wording so the exam is less repetitive.
  - A bug where the assessment generator treated a domain object like a string was fixed.

### Frontend behavior

- `frontend/src/components/ReasoningPanel.tsx`
  - The panel surfaces latest per-agent outputs and exposes `view output` and `view tool result` affordances.
  - This panel is the best live source of truth while a run is active.

- `frontend/src/pages/LearnerView.tsx`
  - Workflow event handling is more defensive.
  - Critic objections are deduplicated before rendering.
  - Progress data is populated from the `compute_progress_series` tool result event.

- `frontend/src/components/CriticVsPlanView.tsx`
  - React keys now include index suffixes so duplicate objection IDs do not trigger key warnings.

## Important implementation rules

- FastMCP `FunctionTool` objects are not directly callable from Python. Use `.fn(...)` when calling them inside backend code.
- Foundry Local often ignores strict JSON instructions. Treat structured parsing plus deterministic fallbacks as part of the design, not as a temporary hack.
- The live `Reasoning` tab can be ahead of persisted trace storage. During active runs, `/api/workflow/{run_id}/trace` may return `404` until the workflow completes.

## Validation status

These checks were completed during the stabilization pass:

- Verified: the workflow no longer crashes at planner fallback with `'FunctionTool' object is not callable`.
- Verified: a clean run reached planner completion and emitted a `generate_study_plan` tool result.
- Verified: the learner UI displayed a real plan ID and the HITL approval gate.
- Verified: the mock exam endpoint returned `200` with diversified question text after the assessment fix.
- Verified: touched backend files passed editor error checks.

This item was fixed in code but not fully reverified in a fresh end-to-end browser run after the last patch:

- Pending recheck: `Progress` tab after the `compute_progress_series.fn(...)` fix in `backend/main.py`.

## Known behavior during debugging

- The planner may still log structured-parse warnings if the model returns ad hoc JSON. That is expected when the fallback path takes over.
- If the UI shows a plan ID and approval gate, the planner fallback path worked even if the original model text was malformed.
- If the mock exam fails, inspect `backend/mcp_server/server.py` before looking at the frontend.
- If the workflow halts after planner or after saving the plan, inspect `backend/main.py` and confirm any FastMCP tool call uses `.fn(...)`.

## Recommended manual verification flow

1. Start the stack with `./start.sh --no-setup --skip-model`.
2. Open learner `L-1004`.
3. Run the workflow.
4. In `Reasoning`, confirm the sequence reaches `Study Plan Generator` completion and shows a `generate_study_plan` tool result.
5. Confirm the HITL block shows a `Plan ID` and the publish approval button.
6. Open `Progress` and confirm the chart renders data instead of the placeholder.
7. Open `Mock Exam` and confirm questions are varied across domains and services.
8. Open `Critic vs Plan` and confirm objections render without duplicate-key issues.

## Files another LLM should read first

- `README.md`
- `backend/core/agent.py`
- `backend/core/workflow.py`
- `backend/main.py`
- `backend/mcp_server/server.py`
- `frontend/src/pages/LearnerView.tsx`
- `frontend/src/components/ReasoningPanel.tsx`
- `frontend/src/components/CriticVsPlanView.tsx`

## Design alignment note

The implementation now better matches the design document in these areas:

- Visible sequential reasoning instead of opaque agent execution.
- Explicit HITL approval before publishing plans.
- Grounded question generation and displayed citations.
- Structured critic objections and plan-vs-critic visualization.
- Local-first development path with a clear Azure upgrade path later.

The code still uses pragmatic local fallbacks because Foundry Local is less reliable than hosted structured-output paths.