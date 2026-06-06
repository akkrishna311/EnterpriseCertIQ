"""Tests for the Fabric IQ semantic layer and its wiring into the MCP tool."""
import json

import pytest

from backend.iq.fabric_iq import get_fabric_iq
from backend.mcp_server.server import fabric_iq_semantics, FabricIQInput


def test_role_certification_map_has_advancement():
    fiq = get_fabric_iq()
    m = fiq.get_role_certification_map("Cloud Engineer")
    assert m["primary_certification"] == "AZ-204"
    assert m["next_certification"] == "AZ-305"
    assert fiq.get_next_certification("AZ-204") == "AZ-305"


def test_domain_thresholds_carry_leverage_and_priority():
    domains = get_fabric_iq().get_domain_thresholds("AZ-204")
    assert len(domains) == 5
    d1 = next(d for d in domains if d["domain_id"] == "D1")
    assert d1["weight_pct"] == 25
    assert d1["leverage"] == 0.25
    assert d1["priority"] == "high"
    assert 0 < d1["minimum_mastery"] <= 1


def test_readiness_semantics_flags_highest_leverage_gap():
    # Low networking/security, strong compute — gap should be weighted by leverage.
    evidence = {"compute": 0.8, "networking": 0.3, "storage": 0.7,
                "security": 0.4, "monitoring": 0.6}
    sem = get_fabric_iq().get_readiness_semantics("AZ-204", evidence)
    assert sem["insufficient_evidence"] is False
    assert 0 <= sem["weighted_mastery"] <= 1
    assert sem["highest_leverage_gap"] is not None
    # Every scored domain reports a numeric gap.
    scored = [d for d in sem["domains"] if d["avg_mastery"] is not None]
    assert scored and all(d["gap"] is not None for d in scored)


def test_readiness_semantics_insufficient_evidence():
    sem = get_fabric_iq().get_readiness_semantics("AZ-204", {})
    assert sem["insufficient_evidence"] is True


def test_cohort_benchmark_and_intervention_effect():
    fiq = get_fabric_iq()
    bench = fiq.get_cohort_benchmark("AZ-204")
    assert bench["sample_size"] > 0
    assert 0 <= bench["pass_rate"] <= 1
    eff = fiq.get_intervention_effectiveness("AZ-204")
    assert eff["baseline_pass_rate"] is not None
    assert "recommended_lever" in eff


def test_team_skill_gap_summary_ranks_systemic_gaps():
    evidence_by_learner = {
        "L-1004": {"compute": 0.72, "networking": 0.41, "security": 0.55},
        "L-1007": {"compute": 0.60, "networking": 0.38, "security": 0.50},
    }
    member_certs = {"L-1004": "AZ-204", "L-1007": "AZ-204"}
    summary = get_fabric_iq().get_team_skill_gap_summary(
        "TEAM-A", evidence_by_learner, member_certs, team_size=2
    )
    assert summary["top_priority_gaps"]
    # Gaps are ordered by priority_gap descending.
    pgs = [g["priority_gap"] for g in summary["top_priority_gaps"]]
    assert pgs == sorted(pgs, reverse=True)
    # Coverage reflects how many of the 2 members fall short on each gap.
    assert all(0 < g["coverage"] <= 1 for g in summary["top_priority_gaps"])
    assert "TEAM-A" in summary["narrative"]


@pytest.mark.asyncio
async def test_fabric_iq_mcp_tool_dispatch():
    res = await fabric_iq_semantics.fn(FabricIQInput(
        query_type="domain_thresholds", cert_id="AZ-204"
    ))
    assert res["query_type"] == "domain_thresholds"
    assert len(res["domains"]) == 5

    res2 = await fabric_iq_semantics.fn(FabricIQInput(
        query_type="readiness_semantics", cert_id="AZ-204",
        evidence_json=json.dumps({"compute": 0.8, "networking": 0.3}),
    ))
    assert res2["query_type"] == "readiness_semantics"
    assert "domains" in res2

    res3 = await fabric_iq_semantics.fn(FabricIQInput(query_type="ontology"))
    assert "entities" in res3 and "relationships" in res3
