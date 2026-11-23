"""Signal-detection measures for a marking rule of the form `score >= threshold`.

A wrong claim that is marked is a hit; a correct claim that is marked is a
false alarm.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Rates:
    threshold: float
    hit_rate: float
    false_alarm_rate: float


def rates_at(scores: list[float], wrong: list[bool], threshold: float) -> Rates:
    marked_wrong = sum(1 for s, w in zip(scores, wrong, strict=True) if w and s >= threshold)
    marked_right = sum(1 for s, w in zip(scores, wrong, strict=True) if not w and s >= threshold)
    total_wrong = sum(wrong)
    total_right = len(wrong) - total_wrong
    return Rates(
        threshold,
        marked_wrong / total_wrong if total_wrong else 0.0,
        marked_right / total_right if total_right else 0.0,
    )


def roc(scores: list[float], wrong: list[bool]) -> list[Rates]:
    """One point per distinct score, from marking nothing to marking everything."""
    thresholds = sorted(set(scores), reverse=True)
    points = [Rates(float("inf"), 0.0, 0.0)]
    points += [rates_at(scores, wrong, threshold) for threshold in thresholds]
    return points


def auc(scores: list[float], wrong: list[bool]) -> float | None:
    """Probability that a wrong claim scores above a correct one (ties count half)."""
    wrong_scores = [s for s, w in zip(scores, wrong, strict=True) if w]
    right_scores = [s for s, w in zip(scores, wrong, strict=True) if not w]
    if not wrong_scores or not right_scores:
        return None
    wins = 0.0
    for high in wrong_scores:
        for low in right_scores:
            wins += 1.0 if high > low else 0.5 if high == low else 0.0
    return wins / (len(wrong_scores) * len(right_scores))


def auc_interval(
    scores: list[float], wrong: list[bool], *, resamples: int = 2000, seed: int = 7
) -> tuple[float, float] | None:
    """95% bootstrap interval for the AUC, resampling claims with replacement."""
    generator = random.Random(seed)
    indices = range(len(scores))
    values: list[float] = []
    for _ in range(resamples):
        draw = [generator.choice(indices) for _ in indices]
        value = auc([scores[i] for i in draw], [wrong[i] for i in draw])
        if value is not None:
            values.append(value)
    if len(values) < resamples // 2:
        return None
    values.sort()
    return values[int(0.025 * len(values))], values[int(0.975 * len(values)) - 1]
