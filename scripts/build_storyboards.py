#!/usr/bin/env python3
"""Compose the storyboard frames into figures for the report.

The frames are screenshots saved by the browser tests (`make screenshots`).
This script lays them out with a short label each. A storyboard is written as
one HTML file per row of frames (docs/storyboards/storyboard-a-1.html, ...), so
that every rendered figure fits on a page at full width.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "storyboards"


@dataclass(frozen=True)
class Frame:
    actor: str  # "Student" or "System"
    label: str
    image: str
    wide: bool = False


STORYBOARDS: dict[str, tuple[str, list[Frame]]] = {
    "a": (
        "Storyboard A: checking a marked claim",
        [
            Frame("Student", "Picks an example question", "a1-ask", wide=True),
            Frame("System", "Shows its three steps while it works", "a2-progress", wide=True),
            Frame("System", "Answer appears with one claim marked CHECK", "a3-answer"),
            Frame("Student", "Selects the claim: reasons and the passage appear", "a4-check"),
            Frame("Student", "Compares the two, then records that they match", "a5-record"),
            Frame("System", "Shows the finding on the claim; it can be undone", "a6-checked"),
        ],
    ),
    "b": (
        "Storyboard B: marking more, and an error the marks missed",
        [
            Frame("System", "Default setting: 1 of 4 claims marked, rates shown", "b1-answer"),
            Frame("Student", "Moves the control to Mark more: 3 of 4 marked", "b2-mark-more"),
            Frame(
                "Student", "Opens the unmarked claim; the passage hedges it", "b3-unmarked-claim"
            ),
            Frame(
                "Student", "Records that it does not match; claim struck through", "b4-corrected"
            ),
        ],
    ),
    "c": (
        "Storyboard C: a question outside the readings",
        [
            Frame("Student", "Types a question the readings do not cover", "c1-typed", wide=True),
            Frame("System", "Declines, says why, and offers questions", "c2-declined", wide=True),
            Frame("Student", "Opens the list of readings", "c3-readings"),
            Frame("Student", "Picks a suggested question and gets an answer", "c4-recovered"),
        ],
    ),
}

STYLE = """
* { box-sizing: border-box; }
body { margin: 0; padding: 20px; width: 1400px; background: #ffffff; color: #1b2430;
  font-family: system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
h1 { margin: 0 0 20px; font-size: 30px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; align-items: start; }
.frame { border: 2px solid #c9c6bc; border-radius: 12px; overflow: hidden; background: #f5f4ef; }
.wide { grid-column: 1 / -1; }
.head { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: #ffffff;
  border-bottom: 2px solid #c9c6bc; font-size: 23px; }
.number { width: 38px; height: 38px; flex: none; border-radius: 50%; background: #1b2430;
  color: #ffffff; display: grid; place-items: center; font-weight: 700; }
.actor { flex: none; padding: 3px 12px; border-radius: 999px; font-weight: 700; font-size: 20px; }
.student { background: #dbe8f8; color: #173a66; border: 2px solid #1f3a5f; }
.system { background: #fff0c4; color: #6e3c06; border: 2px solid #8a4b08; }
img { display: block; width: 100%; }
"""


def rows(frames: list[Frame]) -> list[list[tuple[int, Frame]]]:
    """Group frames into rows: a wide frame alone, other frames in pairs."""
    grouped: list[list[tuple[int, Frame]]] = []
    for number, frame in enumerate(frames, start=1):
        last = grouped[-1] if grouped else None
        if not frame.wide and last and len(last) == 1 and not last[0][1].wide:
            last.append((number, frame))
        else:
            grouped.append([(number, frame)])
    return grouped


def page(title: str | None, row: list[tuple[int, Frame]]) -> str:
    cells = []
    for number, frame in row:
        classes = "frame wide" if frame.wide else "frame"
        cells.append(
            f'<section class="{classes}"><div class="head"><span class="number">{number}</span>'
            f'<span class="actor {frame.actor.lower()}">{frame.actor}</span>'
            f"<span>{escape(frame.label)}</span></div>"
            f'<img src="{frame.image}.png" alt=""></section>'
        )
    heading = f"<h1>{escape(title)}</h1>" if title else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Storyboard</title>'
        f"<style>{STYLE}</style></head><body>{heading}"
        f'<div class="grid">{"".join(cells)}</div></body></html>\n'
    )


def main() -> None:
    for key, (title, frames) in STORYBOARDS.items():
        missing = [f.image for f in frames if not (OUT / f"{f.image}.png").exists()]
        if missing:
            raise SystemExit(f"Missing frames {missing}: run `make screenshots` first.")
        for index, row in enumerate(rows(frames), start=1):
            target = OUT / f"storyboard-{key}-{index}.html"
            target.write_text(page(title if index == 1 else None, row), encoding="utf-8")
            print(f"wrote {target.name}")


if __name__ == "__main__":
    main()
