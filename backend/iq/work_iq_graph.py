"""
Work IQ — real Microsoft 365 source via Microsoft Graph (Calendars.Read).

Why Graph and not the Work IQ service directly:
  Work IQ (workiq.svc.cloud.microsoft) requires an M365 Copilot add-on license
  (~$30/user/mo) plus limited-preview enrolment, returns natural language (not
  structured signals), and is delegated-only. Microsoft Graph `Calendars.Read`
  delivers the SAME WorkIQSignals fields (meeting load, focus time, busy periods)
  from the real M365 calendar on ANY M365 license — provable and demo-friendly.

This adapter keeps the EXACT `WorkContext` output shape used by the synthetic
`WorkIQClient`, so the Engagement Agent, Manager Insights, and readiness logic are
unchanged — only the *source* of the signals differs. On any failure (no token, no
mailbox mapping, Graph error) it raises `WorkIQGraphError`; the selector in
`work_iq.get_work_iq()` then falls back to the synthetic client.

Auth: paste `GRAPH_ACCESS_TOKEN`, or use device-code flow once via
`scripts/graph_device_login.py` (token cache persisted) — see docs/work-iq-graph.md.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.models.learner import LearnerProfile, WorkIQSignals
from backend.iq.work_iq import (
    WorkContext, _assess_capacity_risk, _recommend_slots, _identify_busy_periods,
)
from config.settings import get_settings

logger = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"
_SCOPES = ["Calendars.Read"]
# Event showAs values that count as "unavailable for study".
_BUSY = {"busy", "oof", "workingElsewhere", "tentative"}


class WorkIQGraphError(RuntimeError):
    pass


def _resolve_upn(learner_id: str) -> str:
    s = get_settings()
    if s.graph_learner_upn_map:
        try:
            mapping = json.loads(s.graph_learner_upn_map)
            if learner_id in mapping:
                return mapping[learner_id]
        except Exception:
            logger.warning("GRAPH_LEARNER_UPN_MAP is not valid JSON; using default UPN")
    return s.graph_default_upn or "me"


def _get_token() -> str:
    """Return a Graph access token: env token first, else device-code credential."""
    s = get_settings()
    if s.graph_access_token:
        return s.graph_access_token
    if not (s.graph_tenant_id and s.graph_client_id):
        raise WorkIQGraphError(
            "No GRAPH_ACCESS_TOKEN and no GRAPH_TENANT_ID/GRAPH_CLIENT_ID for device-code auth"
        )
    try:
        from azure.identity import DeviceCodeCredential, TokenCachePersistenceOptions
        cred = DeviceCodeCredential(
            tenant_id=s.graph_tenant_id,
            client_id=s.graph_client_id,
            cache_persistence_options=TokenCachePersistenceOptions(name="enterprisecertiq-graph"),
        )
        token = cred.get_token(*[f"https://graph.microsoft.com/{sc}" for sc in _SCOPES]
                               or ["https://graph.microsoft.com/.default"])
        return token.token
    except Exception as e:  # pragma: no cover - requires interactive/cloud
        raise WorkIQGraphError(f"Device-code auth failed: {e}") from e


def _calendar_view(upn: str, token: str, days: int = 7) -> list[dict]:
    import httpx

    now = datetime.now(timezone.utc)
    start = now.isoformat()
    end = (now + timedelta(days=days)).isoformat()
    path = "/me/calendarView" if upn == "me" else f"/users/{upn}/calendarView"
    try:
        with httpx.Client(timeout=15) as c:
            r = c.get(
                f"{GRAPH}{path}",
                params={"startDateTime": start, "endDateTime": end,
                        "$select": "subject,start,end,showAs", "$top": "200"},
                headers={"Authorization": f"Bearer {token}",
                         "Prefer": 'outlook.timezone="UTC"'},
            )
            r.raise_for_status()
            return r.json().get("value", [])
    except Exception as e:
        raise WorkIQGraphError(f"Graph calendarView failed for {upn}: {e}") from e


def _signals_from_events(events: list[dict], existing: WorkIQSignals) -> WorkIQSignals:
    """Map raw calendar events → WorkIQSignals (same shape the agents already use)."""
    meeting_hours = 0.0
    busy_titles: list[str] = []
    for ev in events:
        if (ev.get("showAs") or "busy") not in _BUSY:
            continue
        try:
            s = datetime.fromisoformat(ev["start"]["dateTime"][:19])
            e = datetime.fromisoformat(ev["end"]["dateTime"][:19])
            hrs = max(0.0, (e - s).total_seconds() / 3600)
        except Exception:
            continue
        meeting_hours += hrs
        if ev.get("subject"):
            busy_titles.append(ev["subject"])

    meeting_hours = round(meeting_hours, 1)
    # Focus time = standard 40h work week minus meeting load, floored at 0.
    focus_hours = round(max(0.0, 40.0 - meeting_hours), 1)
    # Available study = a conservative slice of focus time.
    available = round(min(focus_hours, max(2.0, focus_hours * 0.4)), 1)
    return WorkIQSignals(
        meeting_hours_per_week=meeting_hours,
        focus_hours_per_week=focus_hours,
        preferred_learning_slot=existing.preferred_learning_slot,
        upcoming_milestones=busy_titles[:3] or existing.upcoming_milestones,
        available_study_hours_per_week=available,
    )


class GraphWorkIQClient:
    """Microsoft Graph-backed Work IQ — same contract as the synthetic client."""

    async def get_work_context(self, learner: LearnerProfile) -> WorkContext:
        upn = _resolve_upn(learner.learner_id)
        token = _get_token()
        events = _calendar_view(upn, token)
        signals = _signals_from_events(events, learner.work_iq_signals)
        wc = WorkContext(
            employee_id=learner.learner_id,
            signals=signals,
            busy_periods=_identify_busy_periods(signals),
            recommended_slots=_recommend_slots(signals),
            capacity_risk=_assess_capacity_risk(signals),
        )
        # Override the disclosure so the source is honest + provable.
        wc.to_dict_source = "Microsoft 365 calendar via Microsoft Graph (Calendars.Read)"
        return wc

    async def get_team_context(self, team_id: str, learners: list[LearnerProfile]) -> dict:
        members = []
        for learner in learners:
            wc = await self.get_work_context(learner)
            d = wc.to_dict()
            d["ai_disclosure"] = "Team work context from Microsoft 365 calendar via Microsoft Graph"
            members.append(d)
        avg_meetings = (sum(m["meeting_hours_pw"] for m in members) / len(members)) if members else 0
        return {
            "team_id": team_id,
            "member_count": len(learners),
            "average_meeting_hours_pw": round(avg_meetings, 1),
            "high_capacity_risk_members": [m["employee_id"] for m in members
                                           if m["capacity_risk"] == "high"],
            "members": members,
            "ai_disclosure": "Team work context from Microsoft 365 calendar via Microsoft Graph",
        }
