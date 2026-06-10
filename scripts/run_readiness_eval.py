#!/usr/bin/env python3
"""Print the calibrated readiness-model headline metrics and write a report.

Usage:  python scripts/run_readiness_eval.py [--output readiness_eval.json]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.evals.readiness_model import evaluate_readiness_model


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="readiness_eval.json")
    args = ap.parse_args()

    m = evaluate_readiness_model()
    print("Calibrated certification-readiness model — P(pass)")
    print(f"  dataset:        {m['n']} synthetic learners (base pass rate {m['base_rate']})")
    print(f"  features:       {', '.join(m['features'])}")
    print(f"  AUC (in-sample): {m['auc_in_sample']}   Brier: {m['brier_in_sample']}")
    print(f"  AUC (LOO CV):    {m['auc_loo']}   Brier: {m['brier_loo']}   <- headline")
    print("  abstains with INSUFFICIENT when evidence is missing.")
    Path(args.output).write_text(json.dumps(m, indent=2), encoding="utf-8")
    print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
