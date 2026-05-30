from __future__ import annotations

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class WorkIQSignals(BaseModel):
    meeting_hours_per_week: float = Field(..., ge=0, le=80)
    focus_hours_per_week: float = Field(..., ge=0, le=80)
    preferred_learning_slot: str = "Morning"  # Morning | Afternoon | Evening
    upcoming_milestones: list[str] = Field(default_factory=list)
    available_study_hours_per_week: float = Field(default=0.0)

    def model_post_init(self, __context):
        if self.available_study_hours_per_week == 0.0:
            self.available_study_hours_per_week = max(
                self.focus_hours_per_week * 0.4, 2.0
            )


class PriorAttempt(BaseModel):
    date: str
    score: Optional[int] = None
    outcome: str  # "Pass" | "Fail" | "Withdrawn"
    weak_areas: list[str] = Field(default_factory=list)


class PriorAssessmentEvidence(BaseModel):
    compute: float = Field(default=0.5, ge=0, le=1)
    networking: float = Field(default=0.5, ge=0, le=1)
    storage: float = Field(default=0.5, ge=0, le=1)
    security: float = Field(default=0.5, ge=0, le=1)
    monitoring: float = Field(default=0.5, ge=0, le=1)
    cicd: float = Field(default=0.5, ge=0, le=1)
    data: float = Field(default=0.5, ge=0, le=1)


class CertObjective(BaseModel):
    cert_id: str
    cert_name: str
    role: str
    target_date: str
    recommended_study_hours: int
    passing_score: int = 700
    domains: list[str] = Field(default_factory=list)


class LearnerProfile(BaseModel):
    learner_id: str
    role: str
    team_id: str
    cert_target: str
    deadline: str
    prior_attempts: list[PriorAttempt] = Field(default_factory=list)
    work_iq_signals: WorkIQSignals
    prior_assessment_evidence: Optional[PriorAssessmentEvidence] = None
    display_name: str = ""  # synthetic only, never real name

    @property
    def has_prior_failures(self) -> bool:
        return any(a.outcome == "Fail" for a in self.prior_attempts)
