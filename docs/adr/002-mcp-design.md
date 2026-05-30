# ADR-002: Two-MCP Design (Own Server + Microsoft Learn)

**Date:** 2026-05-30  
**Status:** Accepted

## Context

Agents need two categories of tools:
1. **Internal tools** — plan generation, readiness forecast, IQ search, citation validation. These are domain-specific and must be controlled precisely.
2. **Public documentation tools** — Microsoft Learn exam objectives, official learning paths. These ground the system in real cert structure.

## Decision

Run **two MCP servers** simultaneously:

| Server | URL | Tools |
|---|---|---|
| Own FastMCP server | `http://localhost:8001` | 9 typed tools (parse_learner_profile, foundry_iq_search, generate_study_plan, compute_readiness_forecast, …) |
| Microsoft Learn MCP | `https://learn.microsoft.com/api/mcp` | microsoft_docs_search, microsoft_docs_fetch, microsoft_code_sample_search |

Agents that need both surfaces (Curator, Readiness Critic) get both tool sets. Agents that only need internal tools (Planner, Engagement) get the own server only.

For local development, own-MCP tool executors are called **directly as Python functions** (bypassing HTTP) to eliminate the round-trip. The tool schemas remain identical so swapping to HTTP transport requires no agent code changes.

## Consequences

- **Good:** own tools remain fully typed and testable in isolation.
- **Good:** Microsoft Learn MCP requires no auth and is free — zero config.
- **Risk:** Microsoft Learn MCP is a remote server; network latency adds ~300ms per tool call. Mitigated by the APIM semantic cache on Azure path.
- **Risk:** Microsoft Learn MCP tool list is dynamic (documented as subject to change). The agent framework calls `list_tools` on each init rather than hard-coding tool names.
