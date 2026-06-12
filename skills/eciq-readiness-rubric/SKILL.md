---
name: eciq-readiness-rubric
description: Scoring rubric for certification readiness — domain weights, mastery thresholds, pass criteria, and objection severity rules shared by readiness-critic and assessment agents.
---

# EnterpriseCertIQ Readiness Rubric

## Purpose

This skill defines the **single source of truth** for how readiness is scored across the
EnterpriseCertIQ agent pipeline. The readiness-critic and assessment agents both load
this skill so that domain weights, mastery thresholds, severity rules, and pass criteria
are always in sync — updating this skill propagates to both agents without a redeploy.

---

## Domain Weighting Rules

When evaluating a learner against any certification:

1. Pull domain weights from the `fabric_iq_semantics` tool (`query_type: domain_thresholds`)
   or from the `cert_structures` Knowledge Base.
2. The **leverage score** for a domain = `weight_pct × (minimum_mastery − observed_mastery)`.
   Prioritise objections on the highest leverage score, not the lowest raw mastery.
3. Never assume uniform weights across domains. Every certification has a distinct
   weight distribution that must be retrieved, not guessed.

### AZ-204 Reference Distribution (illustrative)
| Domain | Weight | Minimum Mastery |
|---|---|---|
| Develop Azure compute solutions | 25% | 70% |
| Connect to and consume Azure services | 25% | 70% |
| Implement Azure security | 20% | 70% |
| Monitor, troubleshoot, and optimise | 15% | 70% |
| Develop for Azure storage | 15% | 70% |

---

## Mastery Threshold Rules

- **Minimum mastery** for any domain is 0.70 (70%) unless overridden by `fabric_iq_semantics`.
- A learner whose evidence shows mastery **below 0.70** on a domain weighted ≥ 20% **must**
  receive a `red` severity objection.
- A gap of 0.05–0.10 below minimum mastery on any domain → `amber` severity.
- Do **not** raise an objection where the gap is ≤ 0.05 — this is within calibration tolerance.

---

## Pass Probability Calibration

- Use `compute_readiness_forecast` to obtain the calibrated `pass_probability`.
- Never manually compute pass probability from raw mastery scores — the forecast tool
  applies cohort benchmarking and evidence sufficiency checks.
- If `insufficient_evidence: true` is returned, **always** set the verdict to
  `insufficient_evidence` and recommend `gather_evidence`. Never fabricate a score.
- Thresholds for verdict mapping:
  - `pass_probability ≥ 0.75` and `estimated_exam_score ≥ pass_threshold` → `ready`
  - Otherwise → `not_ready`

---

## Objection Format

Every objection must include all four fields. Omit none:

```json
{
  "objection_id": "O1",
  "plan_element_id": "<week or topic id>",
  "severity": "red | amber",
  "description": "<domain> mastery <observed>% vs target <minimum>% (<weight>% of exam).",
  "recommendation": "Specific, actionable remediation step.",
  "citation": "Source document and domain ID"
}
```

- Maximum **5 objections** per response. Surface the highest-leverage ones.
- If there are no `red` objections, return an empty `objections` list — do not fabricate risk.

---

## Employment Decision Guardrail

Readiness scores and objections are **diagnostic only**. They must never be presented in
a way that could influence employment decisions (hiring, performance ratings, promotion,
termination). Every response carrying a readiness verdict must include the field:

```json
"ai_disclosure": "AI-generated readiness assessment — for learning guidance only, not employment decisions."
```

---

## Determinism Requirement

The readiness-critic operates at temperature 0. Given identical inputs, it must produce
identical objections. Do not introduce randomisation into objection ordering or phrasing.

---

## Citation Requirement

Every objection and sample question must reference a source. Acceptable citation formats:
- `cert_guide: <domain name> — <excerpt>`
- `cert_structures: <domain_id> weight <pct>%`
- `foundry_iq_search: <doc_id> — <span excerpt>`

If no source supports a claim, write `"No governing source found"` in the citation field.
Do **not** omit the citation field.
