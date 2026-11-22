"""The data that crosses the API boundary.

The frontend's types in `frontend/src/api/types.ts` mirror these models.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Stage = Literal["retrieving", "answering", "checking"]
Verdict = Literal["supported", "contradicted", "not_mentioned"]


class Passage(BaseModel):
    id: str
    source_id: str
    source_title: str
    section: str
    text: str
    url: str


class Source(BaseModel):
    id: str
    title: str
    topic: str
    url: str
    publisher: str
    licence: str
    licence_url: str
    passages: int


class ClaimSignals(BaseModel):
    """Raw evidence about one claim, kept so the interface can explain a mark."""

    # Lowest probability the model gave to any token it wrote in the claim.
    min_token_probability: float | None = None
    # Geometric mean of the claim's token probabilities.
    mean_token_probability: float | None = None
    # The token that was least expected, shown as the reason for a mark.
    weakest_token: str | None = None
    # One verdict per re-asked answer.
    sample_verdicts: list[Verdict] = Field(default_factory=list)
    # Share of re-asked answers that did not back the claim (0 to 1).
    disagreement: float | None = None


class ClaimSupport(BaseModel):
    """The reading passage closest to a claim, shown so checking is cheap."""

    passage_id: str
    # Share of the claim's term weight found in the passage (0 to 1).
    overlap: float


class Claim(BaseModel):
    id: int
    text: str
    start: int
    end: int
    signals: ClaimSignals
    # Combined score from 0 to 1. Higher means more reason to check.
    risk: float
    support: ClaimSupport | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


class AskResult(BaseModel):
    id: str
    question: str
    mode: Literal["live", "replay"]
    status: Literal["answered", "not_covered"]
    answer: str = ""
    claims: list[Claim] = Field(default_factory=list)
    # Passages given to the model, plus any passage a claim points to.
    passages: list[Passage] = Field(default_factory=list)
    # Ids of the passages that were in the model's context.
    context_passage_ids: list[str] = Field(default_factory=list)
    model: str = ""
    samples: int = 0


class OperatingPoint(BaseModel):
    """What one threshold did on the pilot evaluation set."""

    threshold: float
    hit_rate: float
    false_alarm_rate: float


class Calibration(BaseModel):
    """Measured behaviour of the marking rule, shown beside the threshold control."""

    signal: str
    default_threshold: float
    points: list[OperatingPoint]
    claims: int
    wrong_claims: int
    auc: float | None = None
    # Where the numbers come from, in a phrase the interface can show.
    basis: str


class Example(BaseModel):
    question: str
    topic: str


class Meta(BaseModel):
    version: str
    mode: Literal["live", "replay"]
    model: str
    samples: int
    sources: list[Source]
    examples: list[Example]
    calibration: Calibration
    max_question_chars: int


class StageEvent(BaseModel):
    type: Literal["stage"] = "stage"
    stage: Stage


class ResultEvent(BaseModel):
    type: Literal["result"] = "result"
    result: AskResult


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: Literal["rate_limited", "model_unavailable", "not_recorded", "invalid_question"]
    message: str
    retry_after_seconds: int | None = None
