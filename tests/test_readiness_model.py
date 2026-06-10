"""Tests for the calibrated readiness model (deterministic, seeded)."""
from backend.evals.readiness_model import evaluate_readiness_model, predict_pass_probability


def test_headline_metrics_are_sane_and_stable():
    m = evaluate_readiness_model()
    assert m["n"] >= 90
    # Calibrated, not perfect: LOO AUC should beat chance and be below 1.0.
    assert 0.65 <= m["auc_loo"] <= 0.95
    assert 0.05 <= m["brier_loo"] <= 0.30
    assert set(m["features"]) == {"practice_score", "hours_studied", "meeting_hours_pw"}


def test_probability_is_monotonic_in_practice_and_capacity():
    strong = predict_pass_probability(practice_score=88, hours_studied=30, meeting_hours_pw=8)
    weak = predict_pass_probability(practice_score=45, hours_studied=6, meeting_hours_pw=34)
    assert strong["pass_probability"] > weak["pass_probability"]
    assert strong["verdict"] == "likely_pass"
    assert weak["verdict"] == "at_risk"


def test_abstains_on_missing_evidence():
    out = predict_pass_probability(practice_score=None, hours_studied=10, meeting_hours_pw=10)
    assert out["insufficient_evidence"] is True
