from __future__ import annotations

from typing import Any

import pytest

from claimcheck.config import Settings
from claimcheck.llm import Completion, Message, ModelUnavailable, TokenProbability
from claimcheck.retrieval import Corpus


class FakeClient:
    """A scripted model: one fixed answer, fixed samples and a verdict per sample."""

    def __init__(
        self,
        answer: str,
        samples: list[str] | None = None,
        verdicts: list[list[str]] | None = None,
        fail_answer: bool = False,
        fail_judge: bool = False,
        tokens: list[TokenProbability] | None = None,
    ) -> None:
        self.answer = answer
        self.samples = samples if samples is not None else [answer]
        self.verdicts = verdicts
        self.fail_answer = fail_answer
        self.fail_judge = fail_judge
        self.tokens = tokens
        self.judged = 0
        self.sampled = 0

    async def complete(
        self,
        *,
        model: str,
        messages: list[Message],
        temperature: float,
        max_tokens: int,
        token_probabilities: bool = False,
    ) -> Completion:
        if token_probabilities:
            if self.fail_answer:
                raise ModelUnavailable("down")
            if self.tokens is not None:
                return Completion(self.answer, self.tokens)
            tokens = [TokenProbability(f" {word}", 0.9) for word in self.answer.split()]
            tokens[0] = TokenProbability(self.answer.split()[0], 0.9)
            return Completion(self.answer, tokens)
        index = self.sampled
        self.sampled += 1
        if index >= len(self.samples):
            raise ModelUnavailable("sample failed")
        return Completion(self.samples[index])

    async def complete_json(
        self,
        *,
        model: str,
        messages: list[Message],
        schema_name: str,
        schema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any]:
        index = self.judged
        self.judged += 1
        if self.fail_judge:
            raise ModelUnavailable("judge failed")
        if self.verdicts is None:
            statements = messages[-1]["content"].split("Statements:\n")[1].splitlines()
            return {
                "verdicts": [
                    {"statement": n, "verdict": "supported"} for n in range(1, len(statements) + 1)
                ]
            }
        return {
            "verdicts": [
                {"statement": n, "verdict": verdict}
                for n, verdict in enumerate(self.verdicts[index], start=1)
            ]
        }


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(mode="replay", api_key="", _env_file=None)  # type: ignore[call-arg]


@pytest.fixture(scope="session")
def corpus(settings: Settings) -> Corpus:
    return Corpus.load(settings.data_dir / "corpus")
