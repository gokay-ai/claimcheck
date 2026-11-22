"""Tokenising for retrieval and splitting an answer into claims."""

from __future__ import annotations

import re
from dataclasses import dataclass

WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")

STOPWORDS = frozenset(
    """
    a about above after again all also am an and any are as at be because been before being
    below between both but by can could did do does doing down during each few for from further
    had has have having he her here hers him his how i if in into is it its itself just me more
    most my no nor not now of off on once only or other our ours out over own same she should so
    some such than that the their theirs them then there these they this those through to too
    under until up very was we were what when where which while who whom why will with would you
    your yours according called describe explain give mean means say says tell
    """.split()
)

# Light suffix stripping, so "thresholds" finds "threshold" and "chunking"
# finds "chunks". A full stemmer is not worth a dependency for one corpus.
SUFFIXES = ("ing", "ed", "es", "s")


def stem(word: str) -> str:
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def terms(text: str) -> list[str]:
    """Content terms of a text: lower-cased, stop words removed, lightly stemmed."""
    normalised = text.lower().replace("’", "'")
    return [stem(word) for word in WORD.findall(normalised) if word not in STOPWORDS]


@dataclass(frozen=True)
class Span:
    text: str
    start: int
    end: int


# Abbreviations whose full stop does not end a sentence.
ABBREVIATIONS = frozenset(
    {"e.g", "i.e", "etc", "vs", "cf", "al", "dr", "mr", "mrs", "ms", "prof", "fig", "no", "approx"}
)
BOUNDARY = re.compile(r"[.!?]+[\"')\]]*(?=\s+|$)")


def split_claims(answer: str) -> list[Span]:
    """Split an answer into sentences, each treated as one claim.

    The answer prompt asks for one checkable statement per sentence, so a
    sentence is the unit a student would check. Offsets index into `answer`, so
    token probabilities can be mapped onto each claim.
    """
    spans: list[Span] = []
    start = 0
    for match in BOUNDARY.finditer(answer):
        before = answer[start : match.start()]
        last_word = before.split()[-1].lower().rstrip(".") if before.split() else ""
        if last_word in ABBREVIATIONS:
            continue
        # A single capital before the stop is an initial, as in "G. A. Miller".
        if len(last_word) == 1 and before.rstrip()[-1:].isupper():
            continue
        _append(spans, answer, start, match.end())
        start = match.end()
    _append(spans, answer, start, len(answer))
    return spans


def _append(spans: list[Span], answer: str, start: int, end: int) -> None:
    segment = answer[start:end]
    stripped = segment.strip()
    if not any(ch.isalnum() for ch in stripped):
        return
    lead = len(segment) - len(segment.lstrip())
    spans.append(Span(stripped, start + lead, start + lead + len(stripped)))
