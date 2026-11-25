"""Recorded answers, so the demo runs with no model and no key.

Each recording is the unedited result of a live run (see
`scripts/record_replay.py`). Replayed results are labelled as such in the API
and in the interface.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .schemas import AskResult, Example


def normalise(question: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()


class ReplayStore:
    def __init__(self, examples: list[Example], recordings: dict[str, AskResult]) -> None:
        self.examples = examples
        self._recordings = recordings

    @classmethod
    def load(cls, data_dir: Path) -> ReplayStore:
        examples = [
            Example.model_validate(item)
            for item in json.loads((data_dir / "examples.json").read_text(encoding="utf-8"))
        ]
        recordings: dict[str, AskResult] = {}
        for path in sorted((data_dir / "replay").glob("*.json")):
            result = AskResult.model_validate_json(path.read_text(encoding="utf-8"))
            recordings[normalise(result.question)] = result.model_copy(update={"mode": "replay"})
        return cls(examples, recordings)

    def find(self, question: str) -> AskResult | None:
        return self._recordings.get(normalise(question))

    def missing(self) -> list[str]:
        """Example questions that have no recording."""
        return [e.question for e in self.examples if self.find(e.question) is None]
