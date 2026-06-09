"""Tests for the tiered Foundry runner: Path A (v2 native) → Path B (v1 mirror) → off."""
import pytest

from backend.core import foundry_orchestration as fo
from config.settings import get_settings, ModelBackend


def test_sdk_tier_detects_installed_generation():
    # Something is installed locally (1.x), so not 'off'.
    assert fo._sdk_tier() in {"v1", "v2"}


def test_mode_off_when_not_azure(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "model_backend", ModelBackend.FOUNDRY_LOCAL)
    assert fo.foundry_mode() == "off"


def test_mode_off_when_no_project_endpoint(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "model_backend", ModelBackend.AZURE_FOUNDRY)
    monkeypatch.setattr(s, "azure_ai_project_endpoint", "")
    assert fo.foundry_mode() == "off"


def test_mode_maps_tier_to_native_or_mirror(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "model_backend", ModelBackend.AZURE_FOUNDRY)
    monkeypatch.setattr(s, "azure_ai_project_endpoint", "https://x.services.ai.azure.com/api/projects/p")
    monkeypatch.setattr(fo, "_sdk_tier", lambda: "v2")
    assert fo.foundry_mode() == "native"     # Path A preferred
    monkeypatch.setattr(fo, "_sdk_tier", lambda: "v1")
    assert fo.foundry_mode() == "mirror"     # Path B fallback
    monkeypatch.setattr(fo, "_sdk_tier", lambda: "off")
    assert fo.foundry_mode() == "off"


@pytest.mark.asyncio
async def test_register_all_agents_is_noop_when_off(monkeypatch):
    monkeypatch.setattr(fo, "foundry_mode", lambda: "off")
    assert await fo.register_all_agents() == []


@pytest.mark.asyncio
async def test_register_all_agents_never_raises_without_auth(monkeypatch):
    # azure mode + a v-tier but no az login → must return [] gracefully, not raise.
    s = get_settings()
    monkeypatch.setattr(s, "model_backend", ModelBackend.AZURE_FOUNDRY)
    monkeypatch.setattr(s, "azure_ai_project_endpoint", "https://x.services.ai.azure.com/api/projects/p")
    result = await fo.register_all_agents()
    assert result == []
