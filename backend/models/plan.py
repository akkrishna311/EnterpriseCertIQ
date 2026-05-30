from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PlanStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class Citation(BaseModel):
    doc_id: str
    title: str
    span_id: str
    excerpt: str
    source_url: str = ""


class StudyTopic(BaseModel):
    topic_id: str
    title: str
    domain: str
    hours_allocated: float
    difficulty: str = "Medium"  # Easy | Medium | Hard
    prerequisites: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    ms_learn_url: str = ""


class StudyWeek(BaseModel):
    week: int
    topics: list[StudyTopic]
    planned_hours: float
    cumulative_planned_topics: int = 0
    notes: str = ""


class ProgressPoint(BaseModel):
    week: int
    planned_topics: int
    actual_topics: int
    status: str  # ahead | on_track | at_risk | off_track
    signal: str = ""
    intervention: Optional[dict] = None
    note: str = ""


class StudyPlan(BaseModel):
    plan_id: str
    learner_id: str
    cert_id: str
    created_at: str
    status: PlanStatus = PlanStatus.DRAFT
    deadline: str
    total_planned_hours: float
    weeks: list[StudyWeek]
    progress_series: list[ProgressPoint] = Field(default_factory=list)
    approved_by: str = ""
    approved_at: str = ""
    revision_count: int = 0
    ai_disclosure: str = "AI-generated; review before publishing"
