#!/usr/bin/env python3
"""Flatten the local Fabric IQ ontology (synthetic JSON) into OneLake-ready relational
CSVs, so the *same* data can live in Microsoft Fabric IQ in Azure.

Run:   python scripts/export_fabric_tables.py
Out:   backend/data/fabric_export/*.csv  (one table per ontology entity / relationship)

Maintaining Azure = source-of-truth stays these JSON files: edit them, re-run this
script, re-upload the CSVs to your OneLake Lakehouse (or point a Dataflow Gen2 / pipeline
at this folder to automate it). See docs/fabric-iq-data.md.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "backend" / "data" / "synthetic"
OUT = ROOT / "backend" / "data" / "fabric_export"

# Certification advancement chain — keep in sync with fabric_iq._ADVANCEMENT
ADVANCEMENT = {
    "AZ-204": "AZ-305", "AZ-400": "AZ-500", "DP-203": "DP-300", "AZ-305": "AZ-400",
    "AI-900": "AI-102", "AI-102": "AZ-305", "DP-100": "DP-203", "SC-100": "", "MS-102": "",
}


def _read(name, default):
    return json.loads((SRC / name).read_text(encoding="utf-8")) if (SRC / name).exists() else default


def _write(name: str, header: list[str], rows: list[list]):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  {name:<28} {len(rows):>3} rows")


def main() -> int:
    certs = _read("cert_structures.json", {})
    learners = _read("learners.json", [])
    teams = _read("teams.json", [])
    cohort = _read("cohort_outcomes.json", [])
    print(f"Exporting Fabric IQ tables → {OUT.relative_to(ROOT)}/")

    # ── Certification entity + SkillDomain + services + advancement ──────
    cert_rows, domain_rows, svc_rows, adv_rows = [], [], [], []
    for cert_id, c in certs.items():
        passing = c.get("passing_score", 700)
        min_mastery = round(passing / 1000, 2)
        cert_rows.append([cert_id, c.get("cert_name", ""), c.get("role", ""),
                          c.get("recommended_study_hours", ""), passing])
        adv_rows.append([cert_id, ADVANCEMENT.get(cert_id, "")])
        for d in c.get("domains", []):
            did = d.get("domain_id", "")
            weight = d.get("weight_pct", 0)
            domain_rows.append([cert_id, did, d.get("name", ""), weight, min_mastery])
            for svc in d.get("services", []):
                svc_rows.append([cert_id, did, svc])
    _write("certifications.csv", ["cert_id", "cert_name", "role", "recommended_study_hours", "passing_score"], cert_rows)
    _write("cert_domains.csv", ["cert_id", "domain_id", "name", "weight_pct", "minimum_mastery"], domain_rows)
    _write("cert_domain_services.csv", ["cert_id", "domain_id", "service"], svc_rows)
    _write("cert_advancement.csv", ["cert_id", "next_cert_id"], adv_rows)

    # ── Learner entity + evidence + work signals ────────────────────────
    learner_rows, evidence_rows, signal_rows = [], [], []
    for l in learners:
        lid = l.get("learner_id", "")
        learner_rows.append([lid, l.get("display_name", ""), l.get("role", ""),
                             l.get("team_id", ""), l.get("cert_target", ""), l.get("deadline", "")])
        for k, v in (l.get("prior_assessment_evidence") or {}).items():
            if isinstance(v, (int, float)):
                evidence_rows.append([lid, k, v])
        sig = l.get("work_iq_signals") or {}
        signal_rows.append([lid, sig.get("meeting_hours_per_week", ""), sig.get("focus_hours_per_week", ""),
                            sig.get("available_study_hours_per_week", ""), sig.get("preferred_learning_slot", "")])
    _write("learners.csv", ["learner_id", "display_name", "role", "team_id", "cert_target", "deadline"], learner_rows)
    _write("learner_evidence.csv", ["learner_id", "skill_key", "score"], evidence_rows)
    _write("learner_work_signals.csv",
           ["learner_id", "meeting_hours_pw", "focus_hours_pw", "available_study_hours_pw", "preferred_slot"], signal_rows)

    # ── Team entity + members + cert targets ────────────────────────────
    team_rows, member_rows, target_rows = [], [], []
    for t in teams:
        tid = t.get("team_id", "")
        team_rows.append([tid, t.get("team_name", ""), t.get("manager_id", ""), t.get("quarter_goal", "")])
        for m in t.get("members", []):
            member_rows.append([tid, m])
        for ct in t.get("cert_targets", []):
            target_rows.append([tid, ct])
    _write("teams.csv", ["team_id", "team_name", "manager_id", "quarter_goal"], team_rows)
    _write("team_members.csv", ["team_id", "learner_id"], member_rows)
    _write("team_cert_targets.csv", ["team_id", "cert_id"], target_rows)

    # ── Cohort outcomes (benchmarks / intervention effectiveness) ───────
    cohort_rows = [[c.get("learner_id", ""), c.get("role", ""), c.get("cert_id", ""),
                    c.get("practice_score_avg", ""), c.get("hours_studied", ""),
                    c.get("meeting_hours_pw", ""), c.get("exam_outcome", "")] for c in cohort]
    _write("cohort_outcomes.csv",
           ["learner_id", "role", "cert_id", "practice_score_avg", "hours_studied", "meeting_hours_pw", "exam_outcome"],
           cohort_rows)

    print("Done. Upload backend/data/fabric_export/*.csv to your OneLake Lakehouse.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
