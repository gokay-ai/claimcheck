"""Claim-level signals: how much reason there is to check each claim.

Two signals are computed, both proposed in the literature review this project
follows from:

* token probability, how expected the model found its own wording;
* sample disagreement, how often re-asked answers fail to back the claim.

The raw values are kept on each claim so the interface can explain a mark and
the evaluation can score every candidate signal from one run.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable

from .llm import TokenProbability
from .schemas import ClaimSignals, Verdict
from .text import Span

# How strongly each verdict counts against a claim (after Manakul et al., 2023).
VERDICT_WEIGHT: dict[Verdict, float] = {
    "supported": 0.0,
    "not_mentioned": 0.5,
    "contradicted": 1.0,
}

WORD_AROUND = re.compile(r"[\w'’-]+")


def locate_tokens(answer: str, tokens: list[TokenProbability]) -> list[tuple[int, int, float]]:
    """Return (start, end, probability) for each token that can be found in order.

    Tokens normally concatenate to the answer, but the answer may have been
    trimmed and a token can be a partial character, so each one is searched for
    from the current position and skipped when it is not there.
    """
    located: list[tuple[int, int, float]] = []
    cursor = 0
    for token in tokens:
        if not token.token:
            continue
        index = answer.find(token.token, cursor)
        if index == -1:
            stripped = token.token.strip()
            index = answer.find(stripped, cursor) if stripped else -1
            if index == -1 or index - cursor > 2:
                continue
            located.append((index, index + len(stripped), token.probability))
            cursor = index + len(stripped)
            continue
        if index - cursor > 2:
            continue
        located.append((index, index + len(token.token), token.probability))
        cursor = index + len(token.token)
    return located


def token_signals(
    answer: str, claim: Span, located: list[tuple[int, int, float]]
) -> tuple[float | None, float | None, str | None]:
    """Minimum and geometric-mean token probability for a claim, and its weakest word."""
    inside = [
        (start, end, probability)
        for start, end, probability in located
        if claim.start <= start < claim.end and answer[start:end].strip()
    ]
    # Punctuation carries no fact, so it should not decide a claim's score.
    worded = [item for item in inside if any(ch.isalnum() for ch in answer[item[0] : item[1]])]
    if not worded:
        return None, None, None
    weakest = min(worded, key=lambda item: item[2])
    log_sum = sum(math.log(max(probability, 1e-9)) for _, _, probability in worded)
    mean = math.exp(log_sum / len(worded))
    return weakest[2], mean, _word_at(answer, weakest[0], weakest[1])


def _word_at(answer: str, start: int, end: int) -> str:
    """Widen a token to the whole word it sits in, so it reads as a word."""
    for match in WORD_AROUND.finditer(answer):
        if match.start() <= start < match.end() or match.start() < end <= match.end():
            return match.group()
    return answer[start:end].strip()


def disagreement(verdicts: list[Verdict]) -> float | None:
    if not verdicts:
        return None
    return sum(VERDICT_WEIGHT[verdict] for verdict in verdicts) / len(verdicts)


def build_signals(
    answer: str,
    claim: Span,
    located: list[tuple[int, int, float]],
    verdicts: list[Verdict],
) -> ClaimSignals:
    minimum, mean, weakest = token_signals(answer, claim, located)
    return ClaimSignals(
        min_token_probability=minimum,
        mean_token_probability=mean,
        weakest_token=weakest,
        sample_verdicts=verdicts,
        disagreement=disagreement(verdicts),
    )


# Candidate ways to turn the raw signals into one 0-to-1 risk score.
# Mark on token probability, as the highlighting studies did.


def _token_min(signals: ClaimSignals) -> float | None:
    if signals.min_token_probability is None:
        return None
    return 1.0 - signals.min_token_probability


def _token_mean(signals: ClaimSignals) -> float | None:
    if signals.mean_token_probability is None:
        return None
    return 1.0 - signals.mean_token_probability


def _disagreement(signals: ClaimSignals) -> float | None:
    return signals.disagreement


def _combined(signals: ClaimSignals) -> float | None:
    parts = [value for value in (_token_min(signals), _disagreement(signals)) if value is not None]
    if not parts:
        return None
    return sum(parts) / len(parts)


SIGNALS: dict[str, Callable[[ClaimSignals], float | None]] = {
    "token_min": _token_min,
    "token_mean": _token_mean,
    "disagreement": _disagreement,
    "combined": _combined,
}

DEFAULT_SIGNAL = "token_min"


def scored(signals: ClaimSignals, signal: str = DEFAULT_SIGNAL) -> bool:
    """Whether a claim has any evidence behind its score."""
    return SIGNALS[signal](signals) is not None


def risk(signals: ClaimSignals, signal: str = DEFAULT_SIGNAL) -> float:
    """Risk score for a claim.

    A claim with no evidence scores 0, so it is left unmarked.
    """
    value = SIGNALS[signal](signals)
    return 0.0 if value is None else round(min(max(value, 0.0), 1.0), 4)
