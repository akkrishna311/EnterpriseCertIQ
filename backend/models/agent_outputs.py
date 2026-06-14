from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, RootModel, field_validator, model_validator

from .plan import Citation


def _clean_text(value: Any, fallback: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -")
    return text or fallback


def _collapse_repeated_segments(value: Any, fallback: str) -> str:
    text = _clean_text(value, fallback)
    parts = [part.strip() for part in re.split(r"\s+[—-]\s+", text) if part.strip()]
    if not parts:
        return text[:160]

    collapsed: list[str] = []
    for part in parts:
        if collapsed and part.casefold() == collapsed[-1].casefold():
            continue
        collapsed.append(part)

    normalized = " — ".join(collapsed)
    if len(normalized) > 160:
        clipped = normalized[:157].rstrip()
        if " " in clipped:
            clipped = clipped.rsplit(" ", 1)[0]
        normalized = f"{clipped}..."
    return normalized


class CuratedTopic(BaseModel):
    title: str
    domain: str
    hours: float = Field(default=2.0, ge=0.5, le=12.0)
    priority: Literal["high", "medium", "low"] = "medium"
    citations: list[Citation] = Field(default_factory=list)
    ms_learn_url: str = ""

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: Any) -> str:
        return _collapse_repeated_segments(value, "Untitled topic")

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_domain(cls, value: Any) -> str:
        return _collapse_repeated_segments(value, "General")


class CuratedTopicList(RootModel[list[CuratedTopic]]):
    @model_validator(mode="after")
    def dedupe_topics(self) -> "CuratedTopicList":
        deduped: list[CuratedTopic] = []
        seen: dict[tuple[str, str], CuratedTopic] = {}

        for topic in self.root:
            key = (topic.title.casefold(), topic.domain.casefold())
            existing = seen.get(key)
            if existing:
                existing.hours = max(existing.hours, topic.hours)
                if existing.priority != "high" and topic.priority == "high":
                    existing.priority = "high"
                if topic.ms_learn_url and not existing.ms_learn_url:
                    existing.ms_learn_url = topic.ms_learn_url

                existing_spans = {citation.span_id for citation in existing.citations}
                for citation in topic.citations:
                    if citation.span_id not in existing_spans:
                        existing.citations.append(citation)
                        existing_spans.add(citation.span_id)
                continue

            seen[key] = topic
            deduped.append(topic)

        self.root = deduped[:8]
        return self


class CriticObjectionOutput(BaseModel):
    objection_id: str = ""
    plan_element_id: str = ""
    severity: Literal["red", "amber"] = "amber"
    description: str = ""
    recommendation: str = ""
    citation: str = ""


class CriticOutput(BaseModel):
    objections: list[CriticObjectionOutput] = Field(default_factory=list)
    forecast: dict[str, Any] = Field(default_factory=dict)
    domain_mastery: dict[str, Any] = Field(default_factory=dict)
    overall_risk: str = "medium"
    ai_disclosure: str = "AI-generated readiness assessment"


class EngagementOutput(BaseModel):
    employee_id: str = ""
    recommended_study_slots: list[str] = Field(default_factory=list)
    blocked_periods: list[str] = Field(default_factory=list)
    engagement_strategy: str = ""
    deviation_threshold_topics: int = 2
    replan_trigger: bool = False
    capacity_risk: str = "medium"
    ai_disclosure: str = "AI-generated engagement schedule; does not write to calendar"


class PeerLearningPair(BaseModel):
    learner_a: str
    strength: str
    learner_b: str
    gap: str


class ManagerInsightsOutput(BaseModel):
    team_id: str
    summary: str
    readiness_distribution: dict[str, int] = Field(default_factory=dict)
    capacity_conflicts: list[str] = Field(default_factory=list)
    risk_areas: list[str] = Field(default_factory=list)
    peer_learning_pairs: list[PeerLearningPair] = Field(default_factory=list)
    manager_actions: list[str] = Field(default_factory=list)
    ai_disclosure: str = "AI-generated team insights; verify before use in performance decisions"


class SampleQuestion(BaseModel):
    """A grounded, cited practice question surfaced by the Assessment Agent."""
    question_text: str = ""
    domain: str = ""
    citation: str = ""  # source title + span/excerpt the question is grounded in


class AssessmentOutput(BaseModel):
    """Readiness evaluation from the Assessment Agent.

    Drives the workflow's pass/fail loop-back: `recommendation` decides whether
    the learner advances to the next certification or loops back into prep.
    `booking_verdict` surfaces the 3-tier exam-booking decision (GO / CONDITIONAL_GO / NOT_YET)
    used by manager dashboards.
    """
    learner_id: str = ""
    cert_id: str = ""
    readiness_verdict: Literal["ready", "not_ready", "insufficient_evidence"] = "not_ready"
    booking_verdict: Literal["GO", "CONDITIONAL_GO", "NOT_YET"] = "NOT_YET"
    pass_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_exam_score: int = 0
    pass_threshold: int = 700
    weak_areas: list[str] = Field(default_factory=list)
    sample_questions: list[SampleQuestion] = Field(default_factory=list)
    recommendation: Literal["advance", "remediate", "gather_evidence"] = "remediate"
    next_step: str = ""  # e.g. "Recommend AZ-305 as the next certification"
    rationale: str = ""
    ai_disclosure: str = "AI-generated readiness assessment; not an official exam result"