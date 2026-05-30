# LLM Handoff

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