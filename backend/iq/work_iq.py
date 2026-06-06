"""
Work IQ integration — work-context signals for personalised scheduling.

Local mode: reads from synthetic work_signals.json + learner profile
Azure mode: would call Microsoft Graph / Work IQ APIs (requires M365 tenant)

Returns structured work-context signals for the Engagement Agent.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from backend.models.learner import LearnerProfile, WorkIQSignals
from config.settings import get_settings

logger = logging.getLogger(__name__)


class WorkContext:
    def __init__(
        self,
        employee_id: str,
        signals: WorkIQSignals,
        busy_periods: list[str],
        recommended_slots: list[str],
        capacity_risk: str,
    ):
        self.employee_id = employee_id
        self.signals = signals
        self.busy_periods = busy_periods
        self.recommended_slots = recommended_slots
        self.capacity_risk = capacity_risk  # low | medium | high

    def to_dict(self) -> dict:
        return {
            "employee_id": self.employee_id,
            "meeting_hours_pw": self.signals.meeting_hours_per_week,
            "focus_hours_pw": self.signals.focus_hours_per_week,
            "preferred_slot": self.signals.preferred_learning_slot,
            "upcoming_milestones": self.signals.upcoming_milestones,
            "available_study_hours_pw": self.signals.available_study_hours_per_week,
            "busy_periods": self.busy_periods,
            "recommended_slots": self.recommended_slots,
            "capacity_risk": self.capacity_risk,
            "ai_disclosure": "Work context derived from synthetic Work IQ signals",
        }


def _assess_capacity_risk(signals: WorkIQSignals) -> str:
    if signals.meeting_hours_per_week > 25:
        return "high"
    if signals.meeting_hours_per_week > 18:
        return "medium"
    return "low"


def _recommend_slots(signals: WorkIQSignals) -> list[str]:
    slot = signals.preferred_learning_slot
    if slot == "Morning":
        return ["Tuesday 08:00-09:30", "Thursday 08:00-09:30", "Saturday 09:00-11:00"]
    if slot == "Afternoon":
        return ["Tuesday 14:00-15:30", "Thursday 14:00-15:30", "Saturday 14:00-16:00"]
    return ["Tuesday 19:00-20:30", "Thursday 19:00-20:30", "Sunday 10:00-12:00"]


def _identify_busy_periods(signals: WorkIQSignals) -> list[str]:
    return [f"Blocked: {m}" for m in signals.upcoming_milestones]


class WorkIQClient:
    def __init__(self):
        self.s = get_settings()

    async def get_work_context(self, learner: LearnerProfile) -> WorkContext:
        signals = learner.work_iq_signals
        return WorkContext(
            employee_id=learner.learner_id,
            signals=signals,
            busy_periods=_identify_busy_periods(signals),
            recommended_slots=_recommend_slots(signals),
            capacity_risk=_assess_capacity_risk(signals),
        )

    async def get_team_context(self, team_id: str, learners: list[LearnerProfile]) -> dict:
        members = []
        for l in learners:
            wc = await self.get_work_context(l)
            members.append(wc.to_dict())

        avg_meetings = sum(l.work_iq_signals.meeting_hours_per_week for l in learners) / max(len(learners), 1)
        at_risk = [l.learner_id for l in learners if _assess_capacity_risk(l.work_iq_signals) == "high"]

        return {
            "team_id": team_id,
            "member_count": len(learners),
            "average_meeting_hours_pw": round(avg_meetings, 1),
            "high_capacity_risk_members": at_risk,
            "members": members,
            "ai_disclosure": "Team work context derived from synthetic Work IQ signals",
        }


class _ResilientGraphWorkIQ:
    """Graph-backed Work IQ that degrades to synthetic per-call on any failure.

    Keeps demos and CI safe: if a token/mailbox is missing or Graph errors, each
    call quietly returns the synthetic signal instead of breaking the pipeline.
    """

    def __init__(self):
        from backend.iq.work_iq_graph import GraphWorkIQClient
        self._graph = GraphWorkIQClient()
        self._synthetic = WorkIQClient()

    async def get_work_context(self, learner: LearnerProfile) -> "WorkContext":
        from backend.iq.work_iq_graph import WorkIQGraphError
        try:
            return await self._graph.get_work_context(learner)
        except WorkIQGraphError as e:
            logger.warning("Work IQ Graph fallback → synthetic for %s: %s", learner.learner_id, e)
            return await self._synthetic.get_work_context(learner)

    async def get_team_context(self, team_id: str, learners: list[LearnerProfile]) -> dict:
        from backend.iq.work_iq_graph import WorkIQGraphError
        try:
            return await self._graph.get_team_context(team_id, learners)
        except WorkIQGraphError as e:
            logger.warning("Work IQ Graph team fallback → synthetic for %s: %s", team_id, e)
            return await self._synthetic.get_team_context(team_id, learners)


_client = None


def get_work_iq():
    """Return the active Work IQ client (synthetic by default, Graph when configured)."""
    global _client
    if _client is None:
        if get_settings().work_iq_source == "graph":
            logger.info("Work IQ source: Microsoft Graph (Calendars.Read), synthetic fallback")
            _client = _ResilientGraphWorkIQ()
        else:
            _client = WorkIQClient()
    return _client
