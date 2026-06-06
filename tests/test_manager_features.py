from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.storage.store import AppStorage, LocalJSONStore


@pytest.fixture()
def client(tmp_path: Path):
    storage = AppStorage()
    storage._store = LocalJSONStore(tmp_path / "store")
    original_storage = main.storage
    main.storage = storage
    try:
        yield TestClient(main.app)
    finally:
        main.storage = original_storage


def test_manager_insights_returns_richer_payload(client: TestClient):
    response = client.get("/api/manager/TEAM-A/insights")
    assert response.status_code == 200

    payload = response.json()
    assert "summary" in payload
    assert set(payload["readiness_distribution"].keys()) == {"on_track", "at_risk", "insufficient_evidence"}
    assert isinstance(payload["risk_areas"], list)
    assert isinstance(payload["manager_actions"], list)
    assert isinstance(payload["peer_learning_pairs"], list)


def test_peer_session_crud_preserves_created_at(client: TestClient):
    payload = {
        "id": "session-1",
        "mentor_id": "L-1007",
        "learner_id": "L-1004",
        "cert_id": "AZ-204",
        "focus_domain": "Develop Azure compute solutions",
        "suggested_slot": "Tuesday 08:00-09:30",
        "rationale": "Same-cert coaching",
        "owner_id": "EMP-001",
        "status": "planned",
        "manager_note": "Initial pairing",
    }

    created = client.post("/api/manager/TEAM-A/peer-sessions", json=payload)
    assert created.status_code == 200
    created_at = created.json()["created_at"]

    updated = client.post("/api/manager/TEAM-A/peer-sessions", json={
        **payload,
        "status": "in_progress",
        "manager_note": "Session booked",
    })
    assert updated.status_code == 200
    assert updated.json()["created_at"] == created_at
    assert updated.json()["status"] == "in_progress"

    listed = client.get("/api/manager/TEAM-A/peer-sessions")
    assert listed.status_code == 200
    assert listed.json()[0]["manager_note"] == "Session booked"

    deleted = client.delete("/api/manager/TEAM-A/peer-sessions/session-1")
    assert deleted.status_code == 200
    assert client.get("/api/manager/TEAM-A/peer-sessions").json() == []


def test_manager_intervention_crud(client: TestClient):
    payload = {
        "id": "intervention:L-1005",
        "learner_id": "L-1005",
        "priority": "critical",
        "reasons": ["High capacity risk", "Latest mock below threshold"],
        "owner_id": "EMP-001",
        "status": "planned",
        "manager_note": "Protect study block",
    }

    created = client.post("/api/manager/TEAM-A/interventions", json=payload)
    assert created.status_code == 200
    created_at = created.json()["created_at"]

    updated = client.post("/api/manager/TEAM-A/interventions", json={
        **payload,
        "status": "completed",
        "manager_note": "Escalated with manager",
    })
    assert updated.status_code == 200
    assert updated.json()["created_at"] == created_at
    assert updated.json()["status"] == "completed"

    listed = client.get("/api/manager/TEAM-A/interventions")
    assert listed.status_code == 200
    assert listed.json()[0]["reasons"] == payload["reasons"]

    deleted = client.delete("/api/manager/TEAM-A/interventions/intervention:L-1005")
    assert deleted.status_code == 200
    assert client.get("/api/manager/TEAM-A/interventions").json() == []


def test_manager_what_if_projects_improvement(client: TestClient):
    response = client.post("/api/manager/TEAM-B/what-if", json={
        "target_learner_id": "L-1006",
        "protected_focus_hours": 2,
        "reduced_meeting_hours": 3,
        "targeted_review_hours": 4,
        "peer_mentor_id": "L-1008",
        "peer_session_count": 2,
    })
    assert response.status_code == 200

    payload = response.json()
    assert "scenario_summary" in payload
    assert payload["baseline"]["target_learner"]["learner_id"] == "L-1006"
    assert payload["projected"]["target_learner"]["estimated_exam_score"] >= payload["baseline"]["target_learner"]["estimated_exam_score"]
    assert isinstance(payload["assumptions"], list) and payload["assumptions"]
    assert "recommended_action" in payload