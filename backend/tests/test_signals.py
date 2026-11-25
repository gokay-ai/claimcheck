import pytest

from claimcheck.llm import TokenProbability
from claimcheck.schemas import ClaimSignals
from claimcheck.signals import (
    SIGNALS,
    build_signals,
    disagreement,
    locate_tokens,
    risk,
    token_signals,
)
from claimcheck.text import split_claims

ANSWER = "Miller wrote it in 1956. The limit is nine items."
TOKENS = [
    TokenProbability("Miller", 0.95),
    TokenProbability(" wrote", 0.8),
    TokenProbability(" it", 0.9),
    TokenProbability(" in", 0.9),
    TokenProbability(" 19", 0.9),
    TokenProbability("56", 0.6),
    TokenProbability(".", 0.2),
    TokenProbability(" The", 0.7),
    TokenProbability(" limit", 0.9),
    TokenProbability(" is", 0.9),
    TokenProbability(" nine", 0.1),
    TokenProbability(" items", 0.9),
    TokenProbability(".", 0.99),
]


def test_tokens_are_placed_on_the_claim_they_belong_to() -> None:
    first, second = split_claims(ANSWER)
    located = locate_tokens(ANSWER, TOKENS)
    assert len(located) == len(TOKENS)

    minimum, mean, weakest = token_signals(ANSWER, first, located)
    # The full stop scored 0.2 but carries no fact, so "56" decides the claim.
    assert minimum == pytest.approx(0.6)
    assert weakest == "1956"
    assert mean is not None and 0.6 < mean < 0.95

    minimum, _, weakest = token_signals(ANSWER, second, located)
    assert minimum == pytest.approx(0.1)
    assert weakest == "nine"


def test_tokens_survive_a_trimmed_answer_and_unknown_tokens() -> None:
    tokens = [TokenProbability("\n", 0.5), TokenProbability("ZZZ", 0.5), *TOKENS]
    assert len(locate_tokens(ANSWER, tokens)) == len(TOKENS)


def test_a_claim_without_tokens_has_no_token_signal() -> None:
    claim = split_claims(ANSWER)[0]
    assert token_signals(ANSWER, claim, []) == (None, None, None)


def test_disagreement_weights_contradiction_above_silence() -> None:
    assert disagreement([]) is None
    assert disagreement(["supported", "supported"]) == 0.0
    assert disagreement(["not_mentioned", "supported"]) == 0.25
    assert disagreement(["contradicted", "supported"]) == 0.5


def test_risk_combines_both_signals_and_stays_in_range() -> None:
    second = split_claims(ANSWER)[1]
    signals = build_signals(
        ANSWER, second, locate_tokens(ANSWER, TOKENS), ["contradicted", "supported"]
    )
    assert risk(signals, "token_min") == pytest.approx(0.9)
    assert risk(signals, "disagreement") == pytest.approx(0.5)
    assert risk(signals, "combined") == pytest.approx(0.7)
    assert risk(ClaimSignals()) == 1.0  # nobody examined it, so it must not look clean
    assert set(SIGNALS) == {"token_min", "token_mean", "disagreement", "combined"}
