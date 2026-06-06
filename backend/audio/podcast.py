"""
Audio study briefing — two-host SSML + Azure AI Speech synthesis (REST).

Turns a grounded `PodcastScript` into an MP3 using Azure AI Speech. We call the
Speech REST API with httpx (no heavy native SDK dependency), so the rest of the app
and CI stay light. Synthesis is opt-in: with no `SPEECH_KEY`/`SPEECH_REGION` the
transcript still works and `synthesize_script` raises `AudioNotConfigured` (the
endpoint then returns a clear 503 instead of breaking).

Two distinct neural voices (host A / host B) are emitted in a single SSML document,
so one API call returns the whole dialogue — no manual audio stitching.

Demo cache: generated MP3s for demo learners are cached under
backend/data/store/audio_cache/ for instant, zero-cost repeat playback.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from xml.sax.saxutils import escape

from config.settings import get_settings
from backend.models.audio import PodcastScript

logger = logging.getLogger(__name__)

# 24kHz mono MP3 — small, good enough for spoken voice.
_OUTPUT_FORMAT = "audio-24khz-48kbitrate-mono-mp3"
_DEMO_IDS = {"L-1004", "L-1005", "L-1006", "L-1007", "L-1008", "L-1013", "L-1014", "L-1015"}


class AudioNotConfigured(RuntimeError):
    """Raised when Azure Speech credentials are absent."""


def is_configured() -> bool:
    s = get_settings()
    return bool(s.enable_audio and s.speech_key and s.speech_region)


def build_ssml(script: PodcastScript) -> str:
    """Render a two-voice SSML document from the script's turns."""
    s = get_settings()
    voice_for = {"host_a": s.audio_voice_host_a, "host_b": s.audio_voice_host_b}
    parts = [
        f'<speak version="1.0" '
        f'xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{s.audio_locale}">'
    ]
    for turn in script.turns:
        text = escape((turn.text or "").strip())
        if not text:
            continue
        voice = voice_for.get(turn.speaker, s.audio_voice_host_a)
        # Slightly slower than default for study clarity; brief pause between turns.
        parts.append(
            f'<voice name="{voice}"><prosody rate="-5%">{text}</prosody>'
            f'<break time="350ms"/></voice>'
        )
    parts.append("</speak>")
    return "".join(parts)


async def _issue_token() -> str:
    import httpx
    s = get_settings()
    url = f"https://{s.speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, headers={"Ocp-Apim-Subscription-Key": s.speech_key})
        r.raise_for_status()
        return r.text


async def synthesize_ssml(ssml: str) -> bytes:
    """Synthesize SSML → MP3 bytes via Azure Speech REST. Raises AudioNotConfigured."""
    if not is_configured():
        raise AudioNotConfigured("Set SPEECH_KEY and SPEECH_REGION to enable audio synthesis")
    import httpx
    s = get_settings()
    token = await _issue_token()
    url = f"https://{s.speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": _OUTPUT_FORMAT,
        "User-Agent": "enterprisecertiq",
    }
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(url, headers=headers, content=ssml.encode("utf-8"))
        r.raise_for_status()
        return r.content


def _cache_dir() -> Path:
    d = Path(get_settings().store_dir) / "audio_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def synthesize_script(script: PodcastScript, cache_key: str = "") -> bytes:
    """Synthesize a script to MP3, serving demo learners from cache when possible."""
    is_demo = cache_key in _DEMO_IDS
    ssml = build_ssml(script)
    if is_demo:
        digest = hashlib.sha256((cache_key + "|" + ssml).encode()).hexdigest()[:16]
        path = _cache_dir() / f"{digest}.mp3"
        if path.exists():
            return path.read_bytes()
        audio = await synthesize_ssml(ssml)
        path.write_bytes(audio)
        return audio
    return await synthesize_ssml(ssml)
