# ADR-001: Foundry Local First, Azure Second

**Date:** 2026-05-30  
**Status:** Accepted

## Context

The Reasoning Agents criteria starter kit explicitly warns:
> "Free Azure subscription can have important constraints — limited model access, tight rate limits, regional restrictions."

Developing and iterating prompts + the workflow graph against cloud models burns rate-limit quota exactly when fast iteration is needed (days 1–8 of a 10-day build window).

## Decision

Use **Foundry Local** during development via a single `MODEL_BACKEND` config flag. The same agent code runs against both backends — the `AsyncOpenAI` client is parameterised so switching is a config change, not a code change.

```
MODEL_BACKEND=foundry_local   → http://localhost:5273/v1  (free, no rate limits)
MODEL_BACKEND=azure_foundry   → APIM Gateway → Azure OpenAI  (demo/prod)
```

## Consequences

- **Good:** zero cloud cost during development; no rate-limit interruptions.
- **Good:** allows full offline workflow iteration before Azure is configured.
- **Risk:** smaller local models (Phi-4-mini, Qwen2.5) behave differently from GPT-class. The eval suite runs on both backends to catch divergence before demo day.
- **Mitigation:** a mandatory full cloud-swap test before the final demo recording.
