"""
Run Azure AI Foundry evaluations and (optionally) publish results to the Foundry portal.

Satisfies the hackathon "show evaluation results in Foundry" requirement. Uses the
`azure-ai-evaluation` SDK with LLM-judge evaluators (Groundedness, Relevance, Coherence,
Fluency) over an eval dataset of grounded agent responses.

IMPORTANT — judge model:
  The evaluator SDK sends `max_tokens`, which gpt-5 / o-series deployments reject. So the
  EVAL JUDGE must be a gpt-4.x deployment. This script forces the judge to
  `AZURE_EVAL_JUDGE_DEPLOYMENT` (default "gpt-4.1"), independent of the agents' models.

Usage:
    # local scoring only (prints metrics, writes eval_results.json):
    python scripts/run_foundry_eval.py

    # also publish to the Foundry project portal (needs `az login`):
    python scripts/run_foundry_eval.py --upload

Config (from .env / environment):
    AZURE_OPENAI_ENDPOINT          https://<res>.openai.azure.com/openai/v1
    AZURE_AI_API_KEY               <key>
    AZURE_AI_PROJECT_ENDPOINT      https://<res>.services.ai.azure.com/api/projects/<proj>
    AZURE_EVAL_JUDGE_DEPLOYMENT    gpt-4.1   (optional; must accept max_tokens)
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings


def _judge_model_config() -> dict:
    s = get_settings()
    # azure-ai-evaluation wants the resource base (no /openai/v1) + api-version.
    base = (s.azure_openai_endpoint or "").split("/openai/")[0]
    if not base:
        # derive from the services endpoint host as a fallback
        base = s.azure_ai_project_endpoint.split("/api/")[0].replace(
            ".services.ai.azure.com", ".openai.azure.com")
    judge = os.environ.get("AZURE_EVAL_JUDGE_DEPLOYMENT", "gpt-4.1")
    return {
        "azure_endpoint": base,
        "api_key": s.azure_ai_api_key,
        "azure_deployment": judge,
        "api_version": s.azure_ai_api_version,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["quality", "agent"], default="quality",
                    help="quality = groundedness/relevance/coherence/fluency; "
                         "agent = intent resolution / tool-call accuracy / task adherence")
    ap.add_argument("--dataset", default=None)
    ap.add_argument("--upload", action="store_true",
                    help="Publish results to the Foundry project portal (needs az login).")
    ap.add_argument("--output", default="eval_results.json")
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    if args.dataset is None:
        args.dataset = str(root / ("backend/data/eval/agent_eval_dataset.jsonl"
                                   if args.mode == "agent" else "backend/data/eval/eval_dataset.jsonl"))

    s = get_settings()
    if not s.azure_ai_api_key:
        print("ERROR: AZURE_AI_API_KEY not set."); return 1

    try:
        from azure.ai.evaluation import (
            evaluate, GroundednessEvaluator, RelevanceEvaluator,
            CoherenceEvaluator, FluencyEvaluator,
            IntentResolutionEvaluator, ToolCallAccuracyEvaluator, TaskAdherenceEvaluator,
        )
    except ImportError:
        print("ERROR: pip install azure-ai-evaluation"); return 1

    model_config = _judge_model_config()
    print(f"Mode: {args.mode} | Judge model: {model_config['azure_deployment']} @ {model_config['azure_endpoint']}")
    print(f"Dataset: {args.dataset}\n")

    if args.mode == "agent":
        # Multi-agent quality: did agents resolve intent, call the right tools, stay on task?
        evaluators = {
            "intent_resolution": IntentResolutionEvaluator(model_config),
            "tool_call_accuracy": ToolCallAccuracyEvaluator(model_config),
            "task_adherence": TaskAdherenceEvaluator(model_config),
        }
    else:
        evaluators = {
            "groundedness": GroundednessEvaluator(model_config),
            "relevance": RelevanceEvaluator(model_config),
            "coherence": CoherenceEvaluator(model_config),
            "fluency": FluencyEvaluator(model_config),
        }

    kwargs = dict(
        data=args.dataset,
        evaluators=evaluators,
        output_path=args.output,
    )
    if args.upload:
        # New Foundry projects accept the project endpoint string here. Upload uses
        # DefaultAzureCredential (az login / managed identity).
        kwargs["azure_ai_project"] = s.azure_ai_project_endpoint
        print("Uploading results to Foundry project (requires az login)...\n")

    result = evaluate(**kwargs)

    metrics = result.get("metrics", {})
    print("\n=== Evaluation metrics (means) ===")
    for k, v in sorted(metrics.items()):
        print(f"  {k}: {v}")
    url = result.get("studio_url")
    if url:
        print(f"\nFoundry portal: {url}")
    print(f"\nFull results written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
