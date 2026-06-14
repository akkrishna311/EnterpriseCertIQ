from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PodcastTurn(BaseModel):
    """A single spoken turn in the two-host audio briefing."""
    speaker: Literal["host_a", "host_b"] = "host_a"
    text: str = ""


class PodcastScript(BaseModel):
    """Grounded two-host audio study briefing.

    The script is generated only from approved certification content; `citations`
    lists the source titles/spans it was grounded in so the transcript can show
    provenance alongside the audio.
    """
    title: str = ""
    cert_id: str = ""
    learner_id: str = ""
    mode: str = ""              # "concept" | "overview"
    focus: str = ""            # the concept taught (domain name) or "overview"
    is_weakest: bool = False   # True when focus was auto-selected as the weakest area
    turns: list[PodcastTurn] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    ai_disclosure: str = (
        "AI-generated audio briefing grounded in approved certification content; "
        "synthetic data only — verify against the official exam guide"
    )
