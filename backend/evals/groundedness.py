"""
Groundedness evaluator — checks that factual assertions in agent output
are supported by retrieved citations.

Two modes:
  heuristic  (local / default)
      Regex-based citation-coverage score.  Fast, zero cloud dependency.
      Used when no model_config is supplied or when azure-ai-evaluation
      SDK call fails.

  azure_ai_evaluation  (Azure mode)
      Uses azure.ai.evaluation.GroundednessEvaluator as an LLM judge.
      Requires a model_config dict pointing at an Azure OpenAI deployment.
      Score is on a 1-5 scale normalised to 0.0-1.0.
      Activated automatically in Azure mode via get_eval_model_config().

Typical call:
    from backend.evals.groundedness import evaluate_async, get_eval_model_config
    result = await evaluate_async(text, context=context_doc,
                                  model_config=get_eval_model_config())
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GroundednessResult:
    score: float           # 0.0 – 1.0
    citation_count: int
    assertion_count: int
    uncited_assertions: list[str]
    passed: bool           # True if score >= threshold
    evaluator: str = "heuristic"   # "heuristic" | "azure_ai_evaluation"
    details: dict = field(default_factory=dict)


# ── Heuristic evaluator ────────────────────────────────────────────────────

def _heuristic_evaluate(text: str, threshold: float) -> GroundednessResult:
    sentences = [s.strip() for s in re.split(r"[.!?]", text) if len(s.strip()) > 20]
    cited = [
        s for s in sentences
        if "citation" in s.lower()
        or "source:" in s.lower()
        or "[doc" in s.lower()
        or "excerpt" in s.lower()
        or "ms_learn_url" in s.lower()
    ]
    total = len(sentences)
    count_cited = len(cited)
    score = count_cited / max(total, 1)
    uncited = [s for s in sentences if s not in cited]

    return GroundednessResult(
        score=round(score, 3),
        citation_count=count_cited,
        assertion_count=total,
        uncited_assertions=uncited[:5],
        passed=score >= threshold,
        evaluator="heuristic",
    )


# ── azure-ai-evaluation SDK evaluator ─────────────────────────────────────

async def _azure_evaluate(
    text: str,
    context: str,
    threshold: float,
    model_config: dict,
) -> GroundednessResult:
    """
    Call GroundednessEvaluator from azure-ai-evaluation SDK.
    The evaluator is synchronous; we run it in a thread pool.
    Falls back to heuristic on any error.
    """
    import asyncio

    def _run_sync() -> dict:
        from azure.ai.evaluation import GroundednessEvaluator
        evaluator = GroundednessEvaluator(model_config=model_config)
        return evaluator(response=text, context=context or text)

    try:
        result: dict = await asyncio.to_thread(_run_sync)
        # SDK returns "groundedness" on a 1–5 scale
        raw_score = result.get("groundedness", 0)
        normalized = max(0.0, min(1.0, (float(raw_score) - 1) / 4))
        return GroundednessResult(
            score=round(normalized, 3),
            citation_count=0,
            assertion_count=0,
            uncited_assertions=[],
            passed=normalized >= threshold,
            evaluator="azure_ai_evaluation",
            details=result,
        )
    except Exception as e:
        logger.warning(
            "azure-ai-evaluation GroundednessEvaluator failed, falling back to heuristic: %s", e
        )
        return _heuristic_evaluate(text, threshold)


# ── Public API ─────────────────────────────────────────────────────────────

def evaluate(
    text: str,
    threshold: float = 0.90,
    context: str = "",
    model_config: Optional[dict] = None,
) -> GroundednessResult:
    """
    Sync entry point.  Always uses heuristic when called synchronously
    because the azure-ai-evaluation SDK is blocking-sync and should run in
    a thread.  Use evaluate_async() from async contexts to get SDK evaluation.
    """
    return _heuristic_evaluate(text, threshold)


async def evaluate_async(
    text: str,
    threshold: float = 0.90,
    context: str = "",
    model_config: Optional[dict] = None,
) -> GroundednessResult:
    """
    Async entry point — preferred in async route handlers or workflow stages.
    Uses azure-ai-evaluation SDK when model_config is provided (Azure mode).
    """
    if model_config:
        return await _azure_evaluate(text, context, threshold, model_config)
    return _heuristic_evaluate(text, threshold)


def get_eval_model_config() -> Optional[dict]:
    """
    Return a model_config dict for azure-ai-evaluation when running in Azure mode.
    Returns None in local mode so callers fall back to the heuristic evaluator.
    """
    try:
        from config.settings import get_settings, ModelBackend
        s = get_settings()
        # azure-ai-evaluation's GroundednessEvaluator sends `max_tokens` internally,
        # which gpt-5 / o-series deployments reject. Use the heuristic evaluator for
        # those (returning None falls back) rather than spamming 400s.
        _dep = (s.azure_ai_model_deployment or "").lower()
        if _dep.startswith(("gpt-5", "o1", "o3", "o4")):
            return None
        if s.model_backend == ModelBackend.AZURE_FOUNDRY:
            # azure-ai-evaluation needs the Azure OpenAI *resource base*
            # (https://<res>.openai.azure.com), not the /openai/v1 surface or the
            # projects endpoint. Derive it from azure_openai_endpoint when set.
            base = (s.azure_openai_endpoint or "").split("/openai/")[0]
            azure_endpoint = base or s.azure_ai_project_endpoint
            if azure_endpoint:
                return {
                    "azure_endpoint": azure_endpoint,
                    "api_key": s.azure_ai_api_key or None,
                    "azure_deployment": s.azure_ai_model_deployment,
                    "api_version": s.azure_ai_api_version,
                }
    except Exception:
        pass
    return None
