import pytest

from claimcheck.evaluation.metrics import auc, auc_interval, rates_at, roc
from claimcheck.evaluation.report import choose_threshold, collect
from claimcheck.evaluation.runner import ClaimLabel, Run, RunClaim, quote_in
from claimcheck.schemas import ClaimSignals, OperatingPoint

SCORES = [0.9, 0.8, 0.4, 0.3, 0.1]
WRONG = [True, False, True, False, False]


def test_rates_count_marked_wrong_and_marked_right_claims() -> None:
    rates = rates_at(SCORES, WRONG, 0.4)
    assert rates.hit_rate == 1.0
    assert rates.false_alarm_rate == pytest.approx(1 / 3)
    assert rates_at(SCORES, WRONG, 0.85).hit_rate == 0.5


def test_auc_is_the_chance_a_wrong_claim_outscores_a_right_one() -> None:
    assert auc(SCORES, WRONG) == pytest.approx(5 / 6)
    assert auc([0.5, 0.5], [True, False]) == 0.5
    assert auc([0.1, 0.2], [False, False]) is None


def test_roc_runs_from_marking_nothing_to_marking_everything() -> None:
    points = roc(SCORES, WRONG)
    assert (points[0].hit_rate, points[0].false_alarm_rate) == (0.0, 0.0)
    assert (points[-1].hit_rate, points[-1].false_alarm_rate) == (1.0, 1.0)


def test_the_bootstrap_interval_brackets_the_estimate() -> None:
    interval = auc_interval(SCORES * 6, WRONG * 6, resamples=200)
    assert interval is not None
    assert interval[0] <= 5 / 6 <= interval[1]


def test_quotes_are_matched_loosely_but_must_exist() -> None:
    article = "The fire killed 5 people.  A contributing factor was a “slow initial response”."
    assert quote_in(article, 'a "slow initial response"')
    assert not quote_in(article, "killed 6 people")
    assert not quote_in(article, "")


def test_only_claims_settled_by_a_found_quote_are_measured() -> None:
    signals = ClaimSignals(min_token_probability=0.5, mean_token_probability=0.8, disagreement=0.25)
    run = Run(
        question_id="q",
        condition="memory",
        answered=True,
        claims=[RunClaim(id=n, text=f"claim {n}", signals=signals) for n in (1, 2, 3, 4)],
    )
    labels = [
        ClaimLabel(
            question_id="q",
            condition="memory",
            claim_id=1,
            label="incorrect",
            evidence="x",
            evidence_found=True,
        ),
        ClaimLabel(
            question_id="q",
            condition="memory",
            claim_id=2,
            label="correct",
            evidence="x",
            evidence_found=False,
        ),
        ClaimLabel(question_id="q", condition="memory", claim_id=3, label="unverifiable"),
    ]
    items, counts = collect([run], labels)
    assert [(item.claim_id, item.wrong) for item in items] == [(1, True)]
    assert counts == {"claims": 4, "unlabelled": 1, "unverifiable": 1, "quote_not_found": 1}


def test_the_default_threshold_keeps_three_in_four_hits_with_fewest_false_alarms() -> None:
    points = [
        OperatingPoint(threshold=0.2, hit_rate=0.95, false_alarm_rate=0.8),
        OperatingPoint(threshold=0.35, hit_rate=0.8, false_alarm_rate=0.4),
        OperatingPoint(threshold=0.5, hit_rate=0.4, false_alarm_rate=0.1),
    ]
    assert choose_threshold(points) == 0.35
    assert choose_threshold(points[2:]) == 0.5
