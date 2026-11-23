"""Turn labelled runs into measures, a review sheet and the app's calibration file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..schemas import Calibration, OperatingPoint
from ..signals import SIGNALS
from .metrics import auc, auc_interval, rates_at, roc
from .runner import ClaimLabel, Condition, Question, Run, dump

# Thresholds offered by the interface's control.
THRESHOLD_GRID = [round(0.05 * step, 2) for step in range(1, 20)]


@dataclass(frozen=True)
class Item:
    """One labelled claim with every candidate score."""

    question_id: str
    condition: Condition
    claim_id: int
    text: str
    wrong: bool
    scores: dict[str, float]
    evidence: str


def collect(runs: list[Run], labels: list[ClaimLabel]) -> tuple[list[Item], dict[str, int]]:
    """Join runs to labels, keeping only claims the article settles with a real quote."""
    by_key = {(label.question_id, label.condition, label.claim_id): label for label in labels}
    counts = {"claims": 0, "unlabelled": 0, "unverifiable": 0, "quote_not_found": 0}
    items: list[Item] = []
    for run in runs:
        for claim in run.claims:
            counts["claims"] += 1
            label = by_key.get((run.question_id, run.condition, claim.id))
            if label is None:
                counts["unlabelled"] += 1
                continue
            if label.label == "unverifiable":
                counts["unverifiable"] += 1
                continue
            if not label.evidence_found:
                counts["quote_not_found"] += 1
                continue
            scores = {name: score(claim.signals) for name, score in SIGNALS.items()}
            if any(value is None for value in scores.values()):
                continue
            items.append(
                Item(
                    run.question_id,
                    run.condition,
                    claim.id,
                    claim.text,
                    label.label == "incorrect",
                    {name: float(value or 0.0) for name, value in scores.items()},
                    label.evidence,
                )
            )
    return items, counts


def measure(items: list[Item]) -> dict[str, Any]:
    wrong = [item.wrong for item in items]
    result: dict[str, Any] = {
        "claims": len(items),
        "wrong_claims": sum(wrong),
        "signals": {},
    }
    for name in SIGNALS:
        scores = [item.scores[name] for item in items]
        interval = auc_interval(scores, wrong)
        result["signals"][name] = {
            "auc": _round(auc(scores, wrong)),
            "auc_95_interval": [_round(interval[0]), _round(interval[1])] if interval else None,
            "roc": [
                {"hit_rate": _round(p.hit_rate), "false_alarm_rate": _round(p.false_alarm_rate)}
                for p in roc(scores, wrong)
            ],
        }
    return result


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def summarise(runs: list[Run], labels: list[ClaimLabel]) -> tuple[dict[str, Any], list[Item]]:
    items, counts = collect(runs, labels)
    summary: dict[str, Any] = {
        "questions": len({run.question_id for run in runs}),
        "runs": len(runs),
        "runs_declined": sum(1 for run in runs if not run.answered),
        "labelling": counts,
        "pooled": measure(items),
    }
    for condition in ("readings", "memory"):
        summary[condition] = measure([item for item in items if item.condition == condition])
    return summary, items


def choose_threshold(points: list[OperatingPoint]) -> float:
    """The default mark: the least eager threshold that still catches 3 in 4 wrong claims.

    A missed wrong claim costs more than a needless check, so the rule fixes a
    floor on hits first and then keeps false alarms as low as that floor allows.
    If no threshold reaches the floor, the one with the best hit rate is used.
    """
    reaching = [point for point in points if point.hit_rate >= 0.75]
    if reaching:
        return max(reaching, key=lambda point: point.threshold).threshold
    return max(points, key=lambda point: (point.hit_rate, point.threshold)).threshold


def calibration(items: list[Item], signal: str, basis: str) -> Calibration:
    scores = [item.scores[signal] for item in items]
    wrong = [item.wrong for item in items]
    points = [
        OperatingPoint(
            threshold=rates.threshold,
            hit_rate=round(rates.hit_rate, 3),
            false_alarm_rate=round(rates.false_alarm_rate, 3),
        )
        for rates in (rates_at(scores, wrong, threshold) for threshold in THRESHOLD_GRID)
    ]
    value = auc(scores, wrong)
    return Calibration(
        signal=signal,
        default_threshold=choose_threshold(points),
        points=points,
        claims=len(items),
        wrong_claims=sum(wrong),
        auc=None if value is None else round(value, 3),
        basis=basis,
    )


def review_sheet(items: list[Item], questions: list[Question], runs: list[Run]) -> str:
    """Every claim labelled wrong, with its quoted evidence, for checking by hand."""
    question_text = {question.id: question.question for question in questions}
    answer_text = {(run.question_id, run.condition): run.answer for run in runs}
    lines = [
        "# Claims labelled incorrect",
        "",
        "Each claim below was labelled incorrect by the labelling model. The quote is the",
        "evidence it gave, and the quote was found in the article by a string search.",
        "Read each pair and note any label you disagree with.",
        "",
    ]
    for number, item in enumerate((i for i in items if i.wrong), start=1):
        lines += [
            f"## {number}. {item.question_id} ({item.condition})",
            "",
            f"- Question: {question_text.get(item.question_id, '')}",
            f"- Claim: {item.text}",
            f"- Article says: “{item.evidence}”",
            f"- Full answer: {answer_text.get((item.question_id, item.condition), '')}",
            "",
        ]
    return "\n".join(lines)


def table(summary: dict[str, Any]) -> str:
    lines = [
        "| Data | Claims | Wrong | Signal | AUC | 95% interval |",
        "|---|---|---|---|---|---|",
    ]
    for name in ("readings", "memory", "pooled"):
        block = summary[name]
        for signal, values in block["signals"].items():
            interval = values["auc_95_interval"]
            shown = f"{interval[0]:.2f} to {interval[1]:.2f}" if interval else "n/a"
            value = "n/a" if values["auc"] is None else f"{values['auc']:.2f}"
            lines.append(
                f"| {name} | {block['claims']} | {block['wrong_claims']} | {signal} "
                f"| {value} | {shown} |"
            )
    return "\n".join(lines)


def plot(summary: dict[str, Any], path: Path) -> bool:
    """Draw the ROC curves. Returns False when matplotlib is not installed."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False
    figure, axes = plt.subplots(1, 2, figsize=(9, 4.2), sharey=True)
    for axis, name in zip(axes, ("readings", "memory"), strict=True):
        block = summary[name]
        for signal, values in block["signals"].items():
            xs = [point["false_alarm_rate"] for point in values["roc"]]
            ys = [point["hit_rate"] for point in values["roc"]]
            label = signal if values["auc"] is None else f"{signal} (AUC {values['auc']:.2f})"
            axis.plot(xs, ys, marker="o", markersize=3, linewidth=1.5, label=label)
        axis.plot([0, 1], [0, 1], linestyle="--", color="grey", linewidth=1)
        axis.set_title(f"{name}: {block['wrong_claims']} wrong of {block['claims']} claims")
        axis.set_xlabel("False-alarm rate (correct claims marked)")
        axis.legend(loc="lower right", fontsize=8)
    axes[0].set_ylabel("Hit rate (wrong claims marked)")
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)
    return True


def write_report(
    out_dir: Path,
    questions: list[Question],
    runs: list[Run],
    labels: list[ClaimLabel],
) -> tuple[dict[str, Any], list[Item]]:
    summary, items = summarise(runs, labels)
    dump(out_dir / "summary.json", summary)
    (out_dir / "summary.md").write_text(table(summary) + "\n", encoding="utf-8")
    (out_dir / "label_review.md").write_text(
        review_sheet(items, questions, runs) + "\n", encoding="utf-8"
    )
    plot(summary, out_dir / "roc.png")
    return summary, items
