"""Tests for the Hosted Agent entrypoint (FastAPI fallback contract, no live model)."""
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    # Force the deterministic fallback so the pipeline runs without a live model.
    os.environ["AGENT_FALLBACK_MODE"] = "force"
    from hosted.main import app
    return TestClient(app)


def test_readiness_path(client):
    r = client.get("/readiness")
    assert r.status_code == 200
    assert r.json().get("status") == "ready"


def test_responses_runs_pipeline_and_returns_text(client):
    r = client.post("/responses", json={"input": "How ready is L-1004 for AZ-204?"})
    assert r.status_code == 200
    text = r.json()["output_text"]
    assert "L-1004" in text and "readiness" in text.lower()
