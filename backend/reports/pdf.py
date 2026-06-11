"""
PDF report generation (reportlab).

Two report types — both carry the AI-generated disclosure and use synthetic IDs only:

  - Learner Readiness Report   : forecast, domain mastery, weak areas, next step.
  - Manager Handoff Brief      : team readiness distribution, risk areas,
                                 Fabric IQ skill-gap, pinned interventions/peer sessions.

A small demo cache (`backend/data/store/report_cache/`) serves pre-generated PDFs for
demo learners instantly on repeat clicks for a reliable live demo.
Real (non-demo) requests always regenerate.
"""
from __future__ import annotations

import hashlib
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

from config.settings import get_settings

logger = logging.getLogger(__name__)

_DISCLOSURE = "AI-generated report · synthetic data only · verify before any decision"
_BRAND = colors.HexColor("#0f6cbd")  # Microsoft-ish blue


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("ECIQTitle", parent=ss["Title"], textColor=_BRAND, fontSize=20))
    ss.add(ParagraphStyle("ECIQH2", parent=ss["Heading2"], textColor=_BRAND, spaceBefore=14))
    ss.add(ParagraphStyle("ECIQBody", parent=ss["BodyText"], alignment=TA_LEFT, fontSize=10, leading=14))
    ss.add(ParagraphStyle("ECIQSmall", parent=ss["BodyText"], fontSize=8, textColor=colors.grey))
    return ss


def _table(rows: list[list[str]], col_widths=None) -> Table:
    t = Table(rows, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _BRAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef4fb")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _build(elements: list) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm, title="EnterpriseCertIQ Report",
    )
    doc.build(elements)
    return buf.getvalue()


def _fmt(value: Any, default: str = "—") -> str:
    if value is None or value == "":
        return default
    return str(value)


def generate_learner_report(
    learner: dict, forecast: dict, mastery: Optional[dict] = None,
    plan: Optional[dict] = None,
) -> bytes:
    """Learner readiness PDF: forecast + per-domain mastery + recommended next step."""
    ss = _styles()
    el: list = []
    el.append(Paragraph("EnterpriseCertIQ — Learner Readiness Report", ss["ECIQTitle"]))
    el.append(Paragraph(_DISCLOSURE, ss["ECIQSmall"]))
    el.append(Spacer(1, 10))

    el.append(_table([
        ["Field", "Value"],
        ["Learner", _fmt(learner.get("learner_id"))],
        ["Role", _fmt(learner.get("role"))],
        ["Certification target", _fmt(learner.get("cert_target"))],
        ["Deadline", _fmt(learner.get("deadline"))],
        ["Generated", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")],
    ], col_widths=[5 * cm, 10 * cm]))

    el.append(Paragraph("Readiness Forecast", ss["ECIQH2"]))
    if forecast.get("insufficient_evidence"):
        el.append(Paragraph(
            "Insufficient evidence to forecast readiness. Complete at least one "
            "assessment before advancing.", ss["ECIQBody"]))
    else:
        el.append(_table([
            ["Metric", "Value"],
            ["Estimated exam score", f"{_fmt(forecast.get('estimated_exam_score'))} / {_fmt(forecast.get('pass_threshold', 700))}"],
            ["Pass probability", _fmt(forecast.get("pass_probability"))],
            ["Confidence interval", f"{_fmt(forecast.get('confidence_interval_lower'))} – {_fmt(forecast.get('confidence_interval_upper'))}"],
            ["Weakest topic", _fmt(forecast.get("weakest_topic"))],
            ["Min. additional hours", _fmt(forecast.get("minimum_additional_hours"))],
        ], col_widths=[6 * cm, 9 * cm]))

    if mastery and mastery.get("domains"):
        el.append(Paragraph("Domain Mastery", ss["ECIQH2"]))
        rows = [["Domain", "Weight %", "Mastery %", "Evidence", "Flag"]]
        for d in mastery["domains"]:
            rows.append([
                _fmt(d.get("name"))[:42], _fmt(d.get("weight_pct")),
                _fmt(d.get("mastery_pct")), _fmt(d.get("evidence_count")),
                _fmt(d.get("flag"), ""),
            ])
        el.append(_table(rows, col_widths=[7 * cm, 2 * cm, 2.2 * cm, 2 * cm, 2 * cm]))

    if plan and plan.get("weeks"):
        el.append(Paragraph("Study Plan Summary", ss["ECIQH2"]))
        el.append(Paragraph(
            f"{len(plan['weeks'])} weeks · {_fmt(plan.get('total_planned_hours'))} planned hours · "
            f"status: {_fmt(plan.get('status'), 'draft')}.", ss["ECIQBody"]))

    el.append(Spacer(1, 14))
    el.append(Paragraph(_DISCLOSURE, ss["ECIQSmall"]))
    return _build(el)


def generate_manager_brief(team_id: str, insights: dict,
                           interventions: Optional[list] = None,
                           peer_sessions: Optional[list] = None) -> bytes:
    """Manager handoff brief PDF: readiness, risk, Fabric IQ skill gaps, pinned actions."""
    ss = _styles()
    el: list = []
    el.append(Paragraph(f"EnterpriseCertIQ — Manager Handoff Brief · {team_id}", ss["ECIQTitle"]))
    el.append(Paragraph(_DISCLOSURE, ss["ECIQSmall"]))
    el.append(Spacer(1, 10))
    el.append(Paragraph(_fmt(insights.get("summary")), ss["ECIQBody"]))

    dist = insights.get("readiness_distribution", {})
    el.append(Paragraph("Team Readiness Distribution", ss["ECIQH2"]))
    el.append(_table([
        ["On track", "At risk", "Insufficient evidence"],
        [_fmt(dist.get("on_track", 0)), _fmt(dist.get("at_risk", 0)), _fmt(dist.get("insufficient_evidence", 0))],
    ], col_widths=[5 * cm, 5 * cm, 5 * cm]))

    risk = insights.get("risk_areas", [])
    if risk:
        el.append(Paragraph("Risk Areas", ss["ECIQH2"]))
        for r in risk:
            el.append(Paragraph(f"• {_fmt(r)}", ss["ECIQBody"]))

    fabric = insights.get("fabric_iq", {}).get("skill_gap_summary", {})
    gaps = fabric.get("top_priority_gaps", [])
    if gaps:
        el.append(Paragraph("Fabric IQ — Top Priority Skill Gaps", ss["ECIQH2"]))
        rows = [["Skill / Domain", "Team avg", "Members short", "Priority"]]
        for g in gaps:
            rows.append([
                _fmt(g.get("skill"))[:40], f"{int(g.get('team_avg_mastery', 0) * 100)}%",
                _fmt(g.get("members_short")), _fmt(g.get("priority_gap")),
            ])
        el.append(_table(rows, col_widths=[7 * cm, 2.5 * cm, 3 * cm, 2.5 * cm]))

    actions = insights.get("manager_actions", [])
    if actions:
        el.append(Paragraph("Recommended Manager Actions", ss["ECIQH2"]))
        for a in actions:
            el.append(Paragraph(f"• {_fmt(a)}", ss["ECIQBody"]))

    if interventions:
        el.append(Paragraph("Pinned Interventions", ss["ECIQH2"]))
        rows = [["Owner", "Status", "Note"]]
        for i in interventions:
            rows.append([_fmt(i.get("owner_id"), ""), _fmt(i.get("status"), ""), _fmt(i.get("manager_note"), "")[:60]])
        el.append(_table(rows, col_widths=[4 * cm, 3 * cm, 8 * cm]))

    if peer_sessions:
        el.append(Paragraph("Pinned Peer-Learning Sessions", ss["ECIQH2"]))
        rows = [["Mentor", "Learner", "Focus"]]
        for p in peer_sessions:
            rows.append([_fmt(p.get("mentor_id"), ""), _fmt(p.get("learner_id"), ""), _fmt(p.get("focus_domain"), "")[:40]])
        el.append(_table(rows, col_widths=[4 * cm, 4 * cm, 7 * cm]))

    el.append(Spacer(1, 14))
    el.append(Paragraph(_DISCLOSURE, ss["ECIQSmall"]))
    return _build(el)


# ── Demo cache ──────────────────────────────────────────────────────────────

def _cache_dir() -> Path:
    d = Path(get_settings().store_dir) / "report_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


_DEMO_LEARNERS = {"L-1004", "L-1005", "L-1006", "L-1007", "L-1008"}
_DEMO_TEAMS = {"TEAM-A", "TEAM-B"}


def cached_pdf(scenario_key: str, kind: str, generate_fn, *args) -> bytes:
    """Serve a pre-generated PDF for demo personas/teams; regenerate for real users.

    `scenario_key` should be a demo learner/team id; anything else regenerates fresh.
    """
    is_demo = scenario_key in _DEMO_LEARNERS or scenario_key in _DEMO_TEAMS
    if not is_demo:
        return generate_fn(*args)
    safe = hashlib.sha256(f"{scenario_key}:{kind}".encode()).hexdigest()[:16]
    path = _cache_dir() / f"{safe}.pdf"
    if path.exists():
        return path.read_bytes()
    data = generate_fn(*args)
    path.write_bytes(data)
    return data
