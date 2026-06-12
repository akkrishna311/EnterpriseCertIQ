---
name: eciq-citation-policy
description: Citation formatting and grounding requirements for all EnterpriseCertIQ agents — how to cite sources from the Knowledge Base, Fabric IQ, and MS Learn so groundedness evals pass consistently.
---

# EnterpriseCertIQ Citation Policy

## Purpose

Every grounded agent in EnterpriseCertIQ (learning-path-curator, readiness-critic,
assessment) must cite its sources in a consistent, auditable format. This skill defines
that format so the groundedness evaluator (`run_foundry_eval.py`) scores citations
correctly across all agents — updating this skill propagates the standard without
touching individual agent instructions.

---

## When a Citation is Required

A citation is **mandatory** whenever an agent:

1. States a domain weight, mastery threshold, or pass score.
2. Includes a sample practice question.
3. Recommends a specific topic, service, or study resource.
4. Makes a claim about a learner's readiness verdict or pass probability.
5. References a certification objective, exam skill area, or learning path.

If no source supports a claim, the agent **must** write:
`"No governing source found"` in the citation field. Omitting the field is not allowed.

---

## Citation Sources and Identifiers

### Source 1 — AI Search Knowledge Base (`cert-knowledge-base`)

Returned by the `foundry_iq_search` tool. Use this format:

```json
{
  "doc_id": "<document identifier from search result>",
  "title": "<document title>",
  "span_id": "<chunk or section id if available>",
  "excerpt": "<verbatim or near-verbatim excerpt, max 200 chars>",
  "source_url": "<url if present, else empty string>"
}
```

The `excerpt` must be drawn from the retrieved document — **do not paraphrase** the
source text in the excerpt field. Paraphrasing belongs in the `description` or
`rationale` field of the response.

---

### Source 2 — Fabric IQ Semantic Model (`fabric_iq_semantics` / Fabric IQ tool)

Returned by the `fabric_iq_semantics` MCP tool or the server-side Fabric IQ tool.
Use this format:

```json
{
  "doc_id": "fabric_iq",
  "title": "<cert_id> Domain Thresholds — EnterpriseCertIQ Semantic Model",
  "span_id": "<domain_id, e.g. D1>",
  "excerpt": "<domain name> — <weight_pct>% of exam. Minimum mastery: <minimum_mastery>.",
  "source_url": ""
}
```

---

### Source 3 — MS Learn / Microsoft Documentation

When `foundry_iq_search` returns a result with `source_url` pointing to learn.microsoft.com
or docs.microsoft.com, surface it using the same KB citation format above and include the
full URL in `source_url`.

---

### Inline Citation (short form)

For fields that accept a single string (e.g. `"citation"` in objections):

```
<source_type>: <domain or section> — <brief excerpt>
```

Examples:
- `cert_structures: D5 weight 25% — Connect to and consume Azure services`
- `foundry_iq_search: AZ-204 Study Guide — 'Implement message-based solutions using Azure Service Bus'`
- `fabric_iq: D3 weight 20% — minimum mastery 70%`

---

## Groundedness Eval Alignment

The groundedness evaluator checks that every claim in the response can be traced to a
retrieved document. To ensure a passing score:

1. **Retrieve before claiming** — call `foundry_iq_search` or `fabric_iq_semantics`
   before making any domain-specific statement. Do not rely on training-data knowledge alone.
2. **Excerpt verbatim** — use the actual returned text in the excerpt, not a rewrite.
3. **One claim, one citation** — if a single sentence makes two claims from two sources,
   split them into separate citation objects.
4. **No hallucinated URLs** — only include `source_url` when it was returned by the tool.
   Do not construct or guess URLs.

---

## Output Format for Citation Arrays

Wherever the response schema includes a `citations` array, emit objects using the full
citation format (Source 1 format above). In fields that accept only a string (e.g.
`"citation"` in objection objects), use the inline short form.

Agents must never return a citations array that is empty when claims were made.
An empty array signals to the evaluator that the response is ungrounded.

---

## Prohibited Citation Practices

- Do **not** cite a source that was not retrieved in this run.
- Do **not** fabricate document IDs, titles, or excerpt text.
- Do **not** cite Wikipedia, general web search results, or non-Microsoft sources unless
  they are returned directly by `foundry_iq_search`.
- Do **not** use the model's training-data knowledge as a citation — always retrieve.
