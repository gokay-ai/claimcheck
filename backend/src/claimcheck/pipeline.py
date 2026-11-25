"""One question, start to finish: retrieve, answer, split into claims, score.

The pipeline is a fixed sequence of model calls, not an agent. Nothing it does
has a side effect outside the response, so no step needs confirmation.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from importlib import resources
from typing import Any, get_args

from .config import Settings
from .llm import Completion, Message, ModelClient, ModelUnavailable
from .retrieval import Corpus, Hit
from .schemas import (
    AskResult,
    Claim,
    ClaimSupport,
    Passage,
    ResultEvent,
    StageEvent,
    Verdict,
)
from .signals import DEFAULT_SIGNAL, build_signals, locate_tokens, risk, scored
from .text import Span, split_claims

NOT_COVERED = "NOT_COVERED"

# A claim points to a passage only when the passage shares enough of its terms.
SUPPORT_IN_CONTEXT = 0.5
SUPPORT_ELSEWHERE = 0.4

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "integer"},
                    "verdict": {"type": "string", "enum": list(get_args(Verdict))},
                },
                "required": ["statement", "verdict"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}

Event = StageEvent | ResultEvent


def load_prompt(name: str) -> str:
    return resources.files("claimcheck.prompts").joinpath(f"{name}.md").read_text("utf-8").strip()


def format_passages(passages: list[Passage]) -> str:
    return "\n\n".join(
        f"[{index}] {passage.source_title}: {passage.section}\n{passage.text}"
        for index, passage in enumerate(passages, start=1)
    )


def answer_messages(question: str, passages: list[Passage]) -> list[Message]:
    return [
        {"role": "system", "content": load_prompt("answer")},
        {
            "role": "user",
            "content": f"Reading passages:\n\n{format_passages(passages)}\n\nQuestion: {question}",
        },
    ]


def memory_messages(question: str) -> list[Message]:
    """The closed-book variant, used only by the evaluation."""
    return [
        {"role": "system", "content": load_prompt("answer_from_memory")},
        {"role": "user", "content": f"Question: {question}"},
    ]


class Pipeline:
    def __init__(self, settings: Settings, corpus: Corpus, client: ModelClient) -> None:
        self.settings = settings
        self.corpus = corpus
        self.client = client

    async def run(self, question: str) -> AsyncIterator[Event]:
        """Answer a question from the readings, reporting each stage as it starts."""
        yield StageEvent(stage="retrieving")
        hits = self.corpus.search(question, self.settings.passages_per_answer)
        if not self.covered(hits):
            yield ResultEvent(result=self._not_covered(question))
            return

        yield StageEvent(stage="answering")
        context = [hit.passage for hit in hits]
        messages = answer_messages(question, context)
        answer, samples = await self.generate(messages)
        if answer.text.strip().upper().startswith(NOT_COVERED):
            yield ResultEvent(result=self._not_covered(question))
            return

        yield StageEvent(stage="checking")
        claims = await self.score(answer, samples)
        result = AskResult(
            id=uuid.uuid4().hex[:12],
            question=question,
            mode="live",
            status="answered",
            answer=answer.text,
            claims=claims,
            context_passage_ids=[passage.id for passage in context],
            model=self.settings.model,
            samples=len(samples),
        )
        result.passages = self._attach_support(result.claims, context)
        yield ResultEvent(result=result)

    def covered(self, hits: list[Hit]) -> bool:
        """Whether any retrieved passage shares enough of the question to answer from."""
        if not hits:
            return False
        return max(hit.coverage for hit in hits) >= self.settings.coverage_threshold

    async def generate(self, messages: list[Message]) -> tuple[Completion, list[str]]:
        """Write the answer once with token probabilities and re-ask it for samples.

        A failed sample only weakens the disagreement signal, so it is dropped;
        a failed answer cannot be recovered from and is raised.
        """
        answer_call = self.client.complete(
            model=self.settings.model,
            messages=messages,
            temperature=self.settings.answer_temperature,
            max_tokens=400,
            token_probabilities=True,
        )
        sample_calls = [
            self.client.complete(
                model=self.settings.model,
                messages=messages,
                temperature=self.settings.sample_temperature,
                max_tokens=400,
            )
            for _ in range(self.settings.samples)
        ]
        answer, *sampled = await asyncio.gather(answer_call, *sample_calls, return_exceptions=True)
        if isinstance(answer, BaseException):
            raise answer
        samples = [item.text.strip() for item in sampled if isinstance(item, Completion)]
        return Completion(answer.text.strip(), answer.tokens), samples

    async def score(self, answer: Completion, samples: list[str]) -> list[Claim]:
        spans = split_claims(answer.text)
        located = locate_tokens(answer.text, answer.tokens)
        verdicts = await self._judge(spans, samples)
        claims: list[Claim] = []
        for index, span in enumerate(spans):
            signals = build_signals(answer.text, span, located, verdicts[index])
            claims.append(
                Claim(
                    id=index + 1,
                    text=span.text,
                    start=span.start,
                    end=span.end,
                    signals=signals,
                    risk=risk(signals, DEFAULT_SIGNAL),
                )
            )
        if claims and not any(scored(claim.signals) for claim in claims):
            # Some models list log-probabilities but return none that match the
            # answer. With no verdicts either, nothing here was examined.
            raise ModelUnavailable("Neither signal could be computed for the answer.")
        return claims

    async def _judge(self, spans: list[Span], samples: list[str]) -> list[list[Verdict]]:
        """For each claim, one verdict per sample that could be judged."""
        if not spans or not samples:
            return [[] for _ in spans]
        results = await asyncio.gather(
            *(self._judge_sample(spans, sample) for sample in samples), return_exceptions=True
        )
        per_claim: list[list[Verdict]] = [[] for _ in spans]
        for result in results:
            if isinstance(result, BaseException):
                continue
            for index, verdict in enumerate(result):
                if verdict is not None:
                    per_claim[index].append(verdict)
        return per_claim

    async def _judge_sample(self, spans: list[Span], sample: str) -> list[Verdict | None]:
        if sample.upper().startswith(NOT_COVERED):
            # A re-asked answer that declines backs none of the claims.
            return ["not_mentioned" for _ in spans]
        statements = "\n".join(f"{index}. {span.text}" for index, span in enumerate(spans, start=1))
        payload = await self.client.complete_json(
            model=self.settings.judge_model,
            messages=[
                {"role": "system", "content": load_prompt("judge")},
                {
                    "role": "user",
                    "content": f"Reference text:\n{sample}\n\nStatements:\n{statements}",
                },
            ],
            schema_name="verdicts",
            schema=JUDGE_SCHEMA,
            max_tokens=300,
        )
        # The schema fixes the shape of the reply, not its sense: a verdict for
        # a statement that does not exist is ignored, a missing one stays None.
        verdicts: list[Verdict | None] = [None for _ in spans]
        allowed = set(get_args(Verdict))
        entries = payload.get("verdicts")
        if not isinstance(entries, list):
            raise ModelUnavailable("The judge returned no verdicts.")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            number, verdict = entry.get("statement"), entry.get("verdict")
            if isinstance(number, int) and 1 <= number <= len(spans) and verdict in allowed:
                verdicts[number - 1] = verdict
        return verdicts

    def _attach_support(self, claims: list[Claim], context: list[Passage]) -> list[Passage]:
        """Point each claim at its closest passage and return every passage shown."""
        shown = {passage.id: passage for passage in context}
        context_ids = list(shown)
        for claim in claims:
            hit = self._closest(claim.text, context_ids)
            if hit is None:
                continue
            claim.support = ClaimSupport(passage_id=hit.passage.id, overlap=round(hit.coverage, 3))
            shown.setdefault(hit.passage.id, hit.passage)
        return list(shown.values())

    def _closest(self, claim: str, context_ids: list[str]) -> Hit | None:
        in_context = self.corpus.search(claim, 1, within=context_ids)
        if in_context and in_context[0].coverage >= SUPPORT_IN_CONTEXT:
            return in_context[0]
        anywhere = self.corpus.search(claim, 1)
        if anywhere and anywhere[0].coverage >= SUPPORT_ELSEWHERE:
            return anywhere[0]
        return None

    def _not_covered(self, question: str) -> AskResult:
        return AskResult(
            id=uuid.uuid4().hex[:12],
            question=question,
            mode="live",
            status="not_covered",
            model=self.settings.model,
        )
