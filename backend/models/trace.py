from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class TraceEventType(str, Enum):
    AGENT_START = "agent_start"
    AGENT_COMPLETE = "agent_complete"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    CRITIC_OBJECTION = "critic_objection"
    CRITIC_RESOLVE = "critic_resolve"
    WORKFLOW_START = "workflow_start"
    WORKFLOW_COMPLETE = "workflow_complete"
    HITL_REQUEST = "hitl_request"
    HITL_APPROVED = "hitl_approved"
    HITL_REJECTED = "hitl_rejected"
    READINESS_LOOPBACK = "readiness_loopback"   # Assessment failed → loop back to prep
    READINESS_ADVANCE = "readiness_advance"     # Assessment passed → recommend next cert
    ERROR = "error"


class CriticObjection(BaseModel):
    objection_id: str
    plan_element_id: str
    severity: str  # red | amber | green
    description: str
    recommendation: str
    citation: str = ""
    resolved: bool = False
    resolution_note: str = ""


class TraceEvent(BaseModel):
    event_id: str
    run_id: str
    timestamp: str
    event_type: TraceEventType
    agent_name: str
    data: dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[int] = None
    objections: list[CriticObjection] = Field(default_factory=list)


class ReasoningTrace(BaseModel):
    run_id: str
    learner_id: str
    cert_id: str
    started_at: str
    completed_at: str = ""
    events: list[TraceEvent] = Field(default_factory=list)
    final_status: str = "pending"  # pending | success | failed | hitl_pending

    def add_event(self, event: TraceEvent) -> None:
        self.events.append(event)

    def get_agent_events(self, agent_name: str) -> list[TraceEvent]:
        return [e for e in self.events if e.agent_name == agent_name]
