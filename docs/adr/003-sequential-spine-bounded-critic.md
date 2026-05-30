# ADR-003: Sequential Spine + Bounded Critic Loop

**Date:** 2026-05-30  
**Status:** Accepted

## Context

The Reasoning Agents criteria reward "decomposition, planning, and effective agent collaboration" (25% of score). Two patterns are available:

- **Dynamic planner** — an LLM decides the next agent at runtime. Flexible but opaque.
- **Fixed graph with bounded loops** — an explicit DAG with one bounded critique loop. Legible and auditable.

## Decision

Use a **fixed sequential spine with one bounded Critic loop (max 2 rounds)**:

```
Intake → Curator → Planner → [Critic → Planner (if red objections)] → Engagement → Manager
                                └── max 2 rounds ──────────────────┘
                                                    ↓ conditional
                                               Retrospective
```

The Critic loop is bounded at `max_critique_rounds=2` to prevent runaway token spend. Each loop round is checkpointed to storage.

## Consequences

- **Good:** the reasoning trail is explicit — every step, every objection, every revision is persisted and rendered in the live panel.
- **Good:** bounded loops prevent runaway costs regardless of model behaviour.
- **Good:** judges can audit the full reasoning chain, not just the final output. This directly scores the Reasoning & Multi-step Thinking criterion (25%).
- **Trade-off:** a dynamic planner could handle unexpected cases more gracefully. Accepted — legibility > flexibility for a demo system.
