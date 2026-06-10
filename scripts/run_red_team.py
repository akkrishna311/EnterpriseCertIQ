#!/usr/bin/env python3
"""Run the adversarial red-team suite and print the scorecard (N/N held, ASR%)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.middleware.red_team import run_red_team  # noqa: E402


def main() -> int:
    r = run_red_team()
    print(f"Adversarial red-team — {r['held_ratio']} held  |  attack success rate {r['attack_success_rate'] * 100:.1f}%")
    for x in r["results"]:
        print(f"  [{'HELD' if x['held'] else 'LEAK'}] {x['label']:24} -> {x['category'] or '—'}")
    return 0 if r["held"] == r["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
