from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class Citation(BaseModel):
    doc_id: str
    title: str
    excerpt: str
    source_url: str = ""


class Question(BaseModel):
    question_id: str
    domain: str
    sub_topic: str
    difficulty: str  # Easy | Medium | Hard
    question_text: str
    options: list[str]
    correct_index: int
    explanation: str
    citations: list[Citation]
    confidence_weight: float = Field(default=1.0, ge=0.1, le=3.0)


class Assessment(BaseModel):
    assessment_id: str
    learner_id: str
    cert_id: str
    created_at: str
    questions: list[Question]
    time_limit_minutes: int = 180
    ai_disclosure: str = "AI-generated assessment; verify questions against official exam guide"


class DomainScore(BaseModel):
    domain: str
    score_pct: float
    questions_attempted: int
    correct: int


class AssessmentResult(BaseModel):
    assessment_id: str
    learner_id: str
    completed_at: str
    total_score_pct: float
    domain_scores: list[DomainScore]
    pass_threshold: int = 700
    estimated_exam_score: int
    passed: bool


class ReadinessForecast(BaseModel):
    learner_id: str
    cert_id: str
    plan_id: str
    generated_at: str
    pass_probability: float = Field(..., ge=0.0, le=1.0)
    confidence_interval_lower: float
    confidence_interval_upper: float
    estimated_exam_score: Optional[int] = None
    pass_threshold: int = 700
    points_below_threshold: Optional[int] = None
    weakest_topic: str
    minimum_additional_hours: float
    insufficient_evidence: bool = False
    evidence_count: int = 0
    ai_disclosure: str = "AI-generated forecast; not a guarantee of exam outcome"
