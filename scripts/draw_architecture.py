#!/usr/bin/env python3
"""Draw the system diagram as docs/architecture.svg.

The diagram is generated so that it can be corrected in one place when the
system changes. Only the standard library is used.

It is laid out for an upright page: the student's browser down the left and
along the bottom, the pipeline down the middle with one step per row, and the
language model and the stored data on the right.

    python3 scripts/draw_architecture.py
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from itertools import pairwise
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "architecture.svg"
WIDTH, HEIGHT = 1040, 1368

INK = "#1b2430"
MUTED = "#56616f"
LANE_FILL = "#fafaf7"
LANE_STROKE = "#cfccc2"
FILL = {
    "ui": "#e8f0fa",
    "system": "#ffffff",
    "model": "#fff3d1",
    "data": "#eef3ea",
    "planned": "#f4f4f4",
}
STROKE = {
    "ui": "#1f3a5f",
    "system": "#1b2430",
    "model": "#8a4b08",
    "data": "#2f6b3c",
    "planned": "#8a8f98",
}
DASH = {
    "implemented": "",
    "simulated": ' stroke-dasharray="9 5"',
    "planned": ' stroke-dasharray="3 5"',
}

# Three columns of boxes, and the height of a box by its number of lines.
LEFT, CENTRE, RIGHT = 28, 396, 778
LEFT_W, CENTRE_W, RIGHT_W = 226, 220, 236
TALL = {1: 56, 2: 62, 3: 80}


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    lines: tuple[str, ...]
    kind: str = "system"
    status: str = "implemented"  # implemented | simulated | planned
    h: float = 0  # 0 means: as tall as the number of lines needs

    @property
    def height(self) -> float:
        return self.h or TALL[len(self.lines)]

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.height / 2

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def edge(self, side: str, shift: float = 0.0) -> tuple[float, float]:
        if side == "top":
            return self.cx + shift, self.y
        if side == "bottom":
            return self.cx + shift, self.bottom
        if side == "left":
            return self.x, self.cy + shift
        return self.x + self.w, self.cy + shift


def box(b: Box) -> str:
    kind = "planned" if b.status == "planned" else b.kind
    text_colour = MUTED if b.status == "planned" else INK
    parts = [
        f'<rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.height}" rx="9" fill="{FILL[kind]}" '
        f'stroke="{STROKE[kind]}" stroke-width="2"{DASH[b.status]}/>'
    ]
    start = b.cy - (len(b.lines) - 1) * 10
    for index, line in enumerate(b.lines):
        weight = "600" if index == 0 else "400"
        size = 17 if index == 0 else 15.5
        parts.append(
            f'<text x="{b.cx}" y="{start + index * 20}" text-anchor="middle" dominant-baseline="central" '
            f'font-size="{size}" font-weight="{weight}" fill="{text_colour}">{escape(line)}</text>'
        )
    return "\n".join(parts)


def arrow(
    points: list[tuple[float, float]],
    label: str = "",
    *,
    dashed: bool = False,
    colour: str = INK,
    label_at: tuple[float, float] | None = None,
    anchor: str = "middle",
) -> str:
    path = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(points))
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    marker = "arrow-muted" if colour == MUTED else "arrow"
    parts = [
        f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="1.8"{dash} '
        f'marker-end="url(#{marker})"/>'
    ]
    if label:
        if label_at is None:
            (x1, y1), (x2, y2) = points[0], points[1]
            label_at = ((x1 + x2) / 2, (y1 + y2) / 2 - 9)
        parts.append(
            f'<text x="{label_at[0]}" y="{label_at[1]}" text-anchor="{anchor}" font-size="14.5" '
            f'fill="{MUTED}" paint-order="stroke" stroke="#ffffff" stroke-width="4">{escape(label)}</text>'
        )
    return "\n".join(parts)


def _towards(
    start: tuple[float, float], end: tuple[float, float], distance: float
) -> tuple[float, float]:
    """The point a given distance from start, on the way to end."""
    (x, y), (tx, ty) = start, end
    length = ((tx - x) ** 2 + (ty - y) ** 2) ** 0.5
    return x + (tx - x) / length * distance, y + (ty - y) / length * distance


def outline(points: list[tuple[float, float]], radius: float = 14) -> str:
    """A closed shape with rounded corners; the corners may turn either way."""
    commands = []
    count = len(points)
    for index, corner in enumerate(points):
        ax, ay = _towards(corner, points[index - 1], radius)
        bx, by = _towards(corner, points[(index + 1) % count], radius)
        move = "M" if index == 0 else "L"
        commands.append(f"{move}{ax:.1f},{ay:.1f} Q{corner[0]},{corner[1]} {bx:.1f},{by:.1f}")
    return (
        f'<path d="{" ".join(commands)} Z" fill="{LANE_FILL}" stroke="{LANE_STROKE}" '
        'stroke-width="1.5"/>'
    )


def lane(x: float, y: float, w: float, h: float) -> str:
    return outline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


def title(x: float, y: float, name: str, detail: str = "") -> str:
    """A lane's name in capitals, with an optional second line under it."""
    parts = [
        f'<text x="{x}" y="{y}" font-size="14.5" font-weight="700" fill="{MUTED}" '
        f'letter-spacing="0.5">{escape(name.upper())}</text>'
    ]
    if detail:
        parts.append(
            f'<text x="{x}" y="{y + 19}" font-size="14.5" fill="{MUTED}">{escape(detail)}</text>'
        )
    return "\n".join(parts)


def legend(x: float, y: float, name: str, entries: list[tuple[str, str, str]]) -> str:
    """One column of the key: a heading and a swatch with its meaning on each row."""
    parts = [
        f'<text x="{x}" y="{y + 5}" font-size="14.5" font-weight="700" fill="{INK}">{name}</text>'
    ]
    swatch = x + (62 if len(name) > 4 else 46)
    for row, (label, kind, status) in enumerate(entries):
        middle = y + row * 24
        parts.append(
            f'<rect x="{swatch}" y="{middle - 9}" width="34" height="18" rx="4" '
            f'fill="{FILL[kind]}" stroke="{STROKE[kind]}" stroke-width="2"{DASH[status]}/>'
        )
        parts.append(
            f'<text x="{swatch + 43}" y="{middle + 5}" font-size="14.5" fill="{INK}">{label}</text>'
        )
    return "\n".join(parts)


def main() -> None:
    # The pipeline: one step per row, top to bottom.
    step = 88
    rows = [150 + step * index for index in range(9)]
    limit = Box(CENTRE, rows[0], CENTRE_W, ("Rate limit", "per client, per day"))
    retrieve = Box(CENTRE, rows[1], CENTRE_W, ("1 Retrieve", "BM25, top 4 passages"))
    covered = Box(CENTRE, rows[2], CENTRE_W, ("2 Covered?", "coverage ≥ 0.5"))
    write = Box(CENTRE, rows[3], CENTRE_W, ("3 Write answer", "+ re-ask 4 times"))
    split = Box(CENTRE, rows[4], CENTRE_W, ("4 Split", "sentence = claim"))
    judge = Box(CENTRE, rows[5], CENTRE_W, ("5 Judge", "claim vs each re-ask"))
    score = Box(CENTRE, rows[6], CENTRE_W, ("6 Score claims", "check score 0 to 1"))
    match = Box(CENTRE, rows[7], CENTRE_W, ("7 Match passage", "closest reading per claim"))
    stream = Box(CENTRE, rows[8], CENTRE_W, ("8 Stream", "stages, then result"))
    pipeline = [limit, retrieve, covered, write, split, judge, score, match, stream]

    # The student, and the part of the interface used to ask.
    student = Box(LEFT, 10, LEFT_W, ("Student",), "ui", h=52)
    ask = Box(LEFT, limit.y, LEFT_W, ("Ask form", "example questions"), "ui")
    notice = Box(LEFT, covered.y, LEFT_W, ("Decline or error notice", "what to ask instead"), "ui")
    progress = Box(LEFT, stream.y, LEFT_W, ("Progress", "3 visible steps"), "ui")

    # The part of the interface used to read and check, along the bottom.
    band = stream.bottom + 44
    answer = Box(LEFT, band + 52, LEFT_W, ("Answer", "claims marked CHECK"), "ui")
    panel = Box(CENTRE, answer.y, CENTRE_W, ("Check panel", "reasons + closest passage"), "ui")
    finding = Box(RIGHT, answer.y, RIGHT_W, ("Student's finding", "✓ matches · ✕ differs"), "ui")
    threshold = Box(
        LEFT, answer.bottom + 38, LEFT_W, ("Threshold control", "hit and false-alarm rates"), "ui"
    )
    personal = Box(
        RIGHT,
        threshold.y,
        RIGHT_W,
        ("Personal threshold", "tuned by recorded findings"),
        status="planned",
    )
    band_bottom = threshold.bottom + 34

    # Language model: one call writes, four re-ask, and one judges per re-ask.
    model_answer = Box(RIGHT, split.y, RIGHT_W, ("Answer +", "token probabilities"), "model")
    model_samples = Box(RIGHT, judge.y - 2, RIGHT_W, ("4 re-asked answers",), "model", h=42)
    model_verdict = Box(RIGHT, score.y - 18, RIGHT_W, ("Verdict per claim", "JSON schema"), "model")
    model_top, model_bottom = write.y - 14, model_verdict.bottom + 36

    # Stored data, and what is planned beside it.
    own = Box(
        RIGHT,
        limit.y - 18,
        RIGHT_W,
        ("Student's own readings", "upload and index"),
        status="planned",
    )
    readings = Box(
        RIGHT,
        retrieve.cy - 40,
        RIGHT_W,
        ("Readings", "19 articles, 434 passages", "source link per passage"),
        "data",
    )
    support = Box(
        RIGHT,
        model_bottom + 20,
        RIGHT_W,
        ("Passage-support signal", "does the passage entail it?"),
        status="planned",
    )
    recorded = Box(
        RIGHT,
        stream.y + 10,
        RIGHT_W,
        ("Recorded answers", "7 questions, replayed", "when no key is set"),
        "data",
        "simulated",
    )

    # Offline work.
    offline = band_bottom + 16
    calibration = Box(
        LEFT,
        offline + 34,
        LEFT_W,
        ("Calibration", "threshold → hit rate,", "false-alarm rate"),
        "data",
    )
    pilot = Box(
        CENTRE,
        calibration.y,
        260,
        ("Pilot evaluation", "same pipeline, 49 questions", "261 claims labelled by model"),
        "data",
    )
    study = Box(
        RIGHT, calibration.cy - 31, RIGHT_W, ("Reliance study", "with students"), status="planned"
    )
    offline_bottom = calibration.bottom + 16

    boxes = [
        student, ask, notice, progress, answer, panel, finding, threshold, personal,
        *pipeline,
        model_answer, model_samples, model_verdict,
        own, readings, support, recorded,
        calibration, pilot, study,
    ]  # fmt: skip

    right_gap = (limit.x + limit.w + readings.x) / 2  # middle of the space between the columns
    loop = answer.y - 18  # the line a finding takes back to the answer
    arrows = [
        # Asking.
        arrow(
            [student.edge("bottom", 83), ask.edge("top", 83)],
            "question",
            label_at=(student.cx + 73, student.bottom + 20),
            anchor="end",
        ),
        arrow([ask.edge("right"), limit.edge("left")], "POST /api/ask"),
        # The pipeline.
        *(arrow([above.edge("bottom"), below.edge("top")]) for above, below in pairwise(pipeline)),
        arrow([covered.edge("left"), notice.edge("right")], "no: decline"),
        arrow([stream.edge("left"), progress.edge("right")], "NDJSON stream"),
        # Model calls: a dark arrow asks, a grey arrow brings the reply back.
        arrow(
            [write.edge("right"), (model_answer.cx + 68, write.cy), model_answer.edge("top", 68)],
            "prompt + passages",
            label_at=(write.x + write.w + 12, write.cy - 9),
            anchor="start",
        ),
        arrow([model_answer.edge("left"), split.edge("right")], colour=MUTED),
        arrow([model_samples.edge("left"), (judge.x + judge.w, model_samples.cy)], colour=MUTED),
        arrow(
            [
                judge.edge("right", 18),
                (right_gap, judge.cy + 18),
                (right_gap, model_verdict.cy - 9),
                model_verdict.edge("left", -9),
            ],
            "claims",
            label_at=(right_gap - 41, judge.cy + 35),
        ),
        arrow([(model_verdict.x, score.cy), score.edge("right")], colour=MUTED),
        # Data.
        arrow([readings.edge("left"), retrieve.edge("right")], "passages"),
        arrow(
            [(recorded.x, stream.cy + 5), stream.edge("right", 5)],
            "replay",
            dashed=True,
        ),
        # Reading and checking.
        arrow(
            [progress.edge("bottom"), answer.edge("top")],
            "scored",
            label_at=(progress.cx + 10, (progress.bottom + answer.y) / 2 + 5),
            anchor="start",
        ),
        arrow([answer.edge("right"), panel.edge("left")], "select"),
        arrow([panel.edge("right"), finding.edge("left")], "compare"),
        arrow(
            [finding.edge("top"), (finding.cx, loop), (answer.cx + 63, loop), answer.edge("top", 63)],
            "finding shown on the claim; can be undone",
            label_at=((answer.cx + 63 + finding.cx) / 2, loop - 8),
        ),
        arrow(
            [threshold.edge("top"), answer.edge("bottom")],
            "re-marks at once",
            label_at=(threshold.cx + 10, (answer.bottom + threshold.y) / 2 + 5),
            anchor="start",
        ),
        # Offline work sets the rates the control shows.
        arrow([pilot.edge("left"), calibration.edge("right")], "measured"),
        arrow(
            [calibration.edge("top", 63), threshold.edge("bottom", 63)],
            "rates for each threshold",
            label_at=(calibration.cx + 73, threshold.bottom + 23),
            anchor="start",
        ),
    ]  # fmt: skip

    browser_right = ask.x + ask.w + 14
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" '
        'font-family="system-ui, -apple-system, Segoe UI, Helvetica, Arial, sans-serif" role="img" '
        'aria-label="ClaimCheck system diagram">',
        "<defs>"
        f'<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>'
        f'<marker id="arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker>'
        "</defs>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        # The browser is one component: asking down the left, reading along the bottom.
        outline(
            [
                (12, 92),
                (browser_right, 92),
                (browser_right, band),
                (WIDTH - 12, band),
                (WIDTH - 12, band_bottom),
                (12, band_bottom),
            ]
        ),
        title(LEFT, 116, "Student's browser", "web interface (React)"),
        lane(limit.x - 14, 92, limit.w + 28, stream.bottom + 16 - 92),
        title(CENTRE, 116, "ClaimCheck API", "FastAPI: a fixed pipeline, no agent"),
        lane(RIGHT - 14, model_top, RIGHT_W + 28, model_bottom - model_top),
        title(RIGHT, model_top + 25, "Language model"),
        f'<text x="{model_verdict.cx}" y="{model_bottom - 13}" text-anchor="middle" font-size="14.5" '
        f'fill="{MUTED}">OpenRouter, gpt-4o-mini</text>',
        lane(12, offline, WIDTH - 24, offline_bottom - offline),
        title(LEFT, offline + 23, "Offline work"),
        *arrows,
        *(box(b) for b in boxes),
        legend(
            320,
            26,
            "Status",
            [
                ("Implemented", "system", "implemented"),
                ("Simulated (recorded model output)", "data", "simulated"),
                ("Planned", "planned", "planned"),
            ],
        ),
        legend(
            690,
            26,
            "Kind",
            [
                ("Language-model call (AI behaviour)", "model", "implemented"),
                ("Seen or controlled by the student", "ui", "implemented"),
                ("Stored data", "data", "implemented"),
            ],
        ),
        "</svg>",
    ]
    if offline_bottom + 14 != HEIGHT:
        raise SystemExit(f"Set HEIGHT to {offline_bottom + 14:.0f}: the page must fit the diagram.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(svg) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
