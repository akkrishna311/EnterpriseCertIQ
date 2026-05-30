from __future__ import annotations

from pydantic import BaseModel, Field


class ServiceCell(BaseModel):
    service_id: str
    service_name: str
    mastery_pct: float = Field(..., ge=0, le=100)
    evidence_count: int = 0
    status: str = "unknown"  # strong | developing | weak | unknown

    def model_post_init(self, __context):
        if self.evidence_count < 3:
            self.status = "unknown"
        elif self.mastery_pct >= 75:
            self.status = "strong"
        elif self.mastery_pct >= 55:
            self.status = "developing"
        else:
            self.status = "weak"


class DomainMastery(BaseModel):
    domain_id: str
    name: str
    weight_pct: float
    mastery_pct: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    evidence_count: int = 0
    flag: str = ""  # "low_evidence" | ""
    services: list[ServiceCell] = []

    def model_post_init(self, __context):
        if self.evidence_count < 4:
            self.flag = "low_evidence"


class MasteryGrid(BaseModel):
    mastery_id: str
    learner_id: str
    cert_id: str
    updated_at: str
    domains: list[DomainMastery]
    pass_threshold: int = 700

    @property
    def weighted_mastery(self) -> float:
        if not self.domains:
            return 0.0
        return sum(d.mastery_pct * d.weight_pct / 100 for d in self.domains)


class ServiceHeatmap(BaseModel):
    learner_id: str
    cert_id: str
    updated_at: str
    rows: list[DomainMastery]
