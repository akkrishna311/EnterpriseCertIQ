"""Tests for the grounded audio study briefing (script, SSML, synthesis guard, endpoint)."""
import pytest

from backend.agents.fallbacks import build_fallback
from backend.audio import podcast
from backend.models import PodcastScript
from backend.main import _generate_audio_script


def _ctx():
    from backend.main import _load_learner
    learner = _load_learner("L-1004")
    return {"learner_obj": learner, "learner_id": "L-1004", "cert_id": "AZ-204"}


@pytest.mark.asyncio
async def test_fallback_script_is_valid_and_grounded():
    raw = await build_fallback("audio_curriculum", _ctx())
    script = PodcastScript.model_validate(raw)          # schema-valid
    assert script.cert_id == "AZ-204"
    assert len(script.turns) >= 6
    # two-host dialogue actually alternates speakers
    speakers = {t.speaker for t in script.turns}
    assert speakers == {"host_a", "host_b"}
    assert script.citations  # grounded references present


def test_build_ssml_has_two_voices_and_escapes(monkeypatch):
    from config.settings import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "audio_voice_host_a", "en-US-AvaNeural")
    monkeypatch.setattr(s, "audio_voice_host_b", "en-US-AndrewNeural")
    script = PodcastScript(
        cert_id="AZ-204",
        turns=[
            {"speaker": "host_a", "text": "Welcome to AZ-204 & friends"},
            {"speaker": "host_b", "text": "Where do I start?"},
        ],
    )
    ssml = podcast.build_ssml(script)
    assert ssml.startswith("<speak")
    assert "en-US-AvaNeural" in ssml and "en-US-AndrewNeural" in ssml
    assert "&amp;" in ssml          # "&" was XML-escaped
    assert ssml.count("<voice") == 2


def test_is_configured_false_by_default(monkeypatch):
    # Simulate no speech credentials — .env.local may have them set, so we clear them.
    from config.settings import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "speech_key", "")
    monkeypatch.setattr(s, "speech_region", "")
    assert podcast.is_configured() is False


@pytest.mark.asyncio
async def test_synthesize_raises_when_not_configured(monkeypatch):
    from config.settings import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "speech_key", "")
    monkeypatch.setattr(s, "speech_region", "")
    script = PodcastScript(cert_id="AZ-204",
                           turns=[{"speaker": "host_a", "text": "hi"}])
    with pytest.raises(podcast.AudioNotConfigured):
        await podcast.synthesize_ssml(podcast.build_ssml(script))


@pytest.mark.asyncio
async def test_generate_audio_script_endpoint_path(monkeypatch):
    """Force deterministic mode → full grounded script with no model/credentials."""
    monkeypatch.setenv("AGENT_FALLBACK_MODE", "force")
    from config.settings import get_settings
    get_settings.cache_clear()
    try:
        script = await _generate_audio_script("L-1004", "AZ-204")
        PodcastScript.model_validate(script)
        assert script["cert_id"] == "AZ-204"
        assert len(script["turns"]) >= 6
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_concept_fallback_deep_teaches_focus():
    from backend.iq.fabric_iq import get_fabric_iq
    domain = next(d for d in get_fabric_iq().get_domain_thresholds("AZ-204")
                  if d["domain_id"] == "D3")  # Implement Azure security
    ctx = {**_ctx(), "mode": "concept", "focus_domain": domain, "is_weakest": False,
           "domains": get_fabric_iq().get_domain_thresholds("AZ-204"), "excerpts": []}
    raw = await build_fallback("audio_curriculum", ctx)
    script = PodcastScript.model_validate(raw)
    assert "Deep Dive" in script.title
    assert domain["name"] in script.title
    # a deep-dive should include a self-check prompt
    assert any("self-check" in t.text.lower() or "pause" in t.text.lower() for t in script.turns)


@pytest.mark.asyncio
async def test_default_focus_targets_weakest(monkeypatch):
    monkeypatch.setenv("AGENT_FALLBACK_MODE", "force")
    from config.settings import get_settings
    get_settings.cache_clear()
    try:
        # L-1004 has prior evidence → a real weakest domain is selected.
        script = await _generate_audio_script("L-1004", "AZ-204")
        assert script["mode"] == "concept"
        assert script["is_weakest"] is True
        assert script["focus"]  # a concrete domain name
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_learner_choice_focus(monkeypatch):
    monkeypatch.setenv("AGENT_FALLBACK_MODE", "force")
    from config.settings import get_settings
    get_settings.cache_clear()
    try:
        script = await _generate_audio_script("L-1004", "AZ-204", focus="storage")
        assert script["mode"] == "concept"
        assert "storage" in script["focus"].lower()
        assert script["is_weakest"] is False
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_overview_focus_mode(monkeypatch):
    monkeypatch.setenv("AGENT_FALLBACK_MODE", "force")
    from config.settings import get_settings
    get_settings.cache_clear()
    try:
        script = await _generate_audio_script("L-1004", "AZ-204", focus="overview")
        assert script["mode"] == "overview"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_audio_concepts_endpoint_flags_weakest():
    from backend.main import audio_concepts
    out = await audio_concepts("L-1004", "AZ-204")
    assert out["cert_id"] == "AZ-204"
    assert len(out["concepts"]) == 5
    weakest = [c for c in out["concepts"] if c["is_weakest"]]
    assert len(weakest) == 1
    assert weakest[0]["domain_id"] == out["weakest_domain_id"]
