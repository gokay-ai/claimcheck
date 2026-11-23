"""The three model-backed steps of the pilot: write questions, answer, label."""

from __future__ import annotations

import asyncio
import json
import random
import re
from collections.abc import Awaitable, Callable, Iterable
from functools import partial
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from ..config import Settings
from ..llm import ModelClient, ModelUnavailable
from ..pipeline import Pipeline, answer_messages, load_prompt, memory_messages
from ..retrieval import Corpus
from ..schemas import ClaimSignals

Condition = Literal["readings", "memory"]
Label = Literal["correct", "incorrect", "unverifiable"]

CONDITIONS: tuple[Condition, ...] = ("readings", "memory")
CONCURRENCY = 6


QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"question": {"type": "string"}},
    "required": ["question"],
    "additionalProperties": False,
}


LABEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "integer"},
                    "label": {"type": "string", "enum": ["correct", "incorrect", "unverifiable"]},
                    "evidence": {"type": "string"},
                },
                "required": ["statement", "label", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["labels"],
    "additionalProperties": False,
}


class Question(BaseModel):
    id: str
    question: str
    source_id: str
    passage_id: str


class RunClaim(BaseModel):
    id: int
    text: str
    signals: ClaimSignals


class Run(BaseModel):
    question_id: str
    condition: Condition
    answered: bool
    answer: str = ""
    claims: list[RunClaim] = []
    context_passage_ids: list[str] = []
    samples: int = 0


class ClaimLabel(BaseModel):
    question_id: str
    condition: Condition
    claim_id: int
    label: Label
    evidence: str = ""
    # Whether the quoted evidence really appears in the article. A label whose
    # quote cannot be found is not trusted.
    evidence_found: bool = False


def read_jsonl[T: BaseModel](path: Path, model: type[T]) -> list[T]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [model.model_validate_json(line) for line in handle if line.strip()]


def append_jsonl(path: Path, item: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(item.model_dump_json() + "\n")


async def gather_limited[T](
    jobs: Iterable[Callable[[], Awaitable[T]]], limit: int = CONCURRENCY
) -> list[T | BaseException]:
    semaphore = asyncio.Semaphore(limit)

    async def guarded(job: Callable[[], Awaitable[T]]) -> T:
        async with semaphore:
            return await job()

    return await asyncio.gather(*(guarded(job) for job in jobs), return_exceptions=True)


async def write_questions(
    corpus: Corpus, client: ModelClient, model: str, path: Path, count: int, seed: int
) -> list[Question]:
    """Draw passages evenly across the readings and ask for one question on each."""
    existing = read_jsonl(path, Question)
    if existing:
        return existing
    generator = random.Random(seed)
    by_source: dict[str, list[str]] = {}
    for passage in corpus.passages:
        by_source.setdefault(passage.source_id, []).append(passage.id)
    for ids in by_source.values():
        generator.shuffle(ids)
    # Round-robin over the sources, so a long article does not dominate.
    chosen: list[str] = []
    while len(chosen) < count and any(by_source.values()):
        for ids in by_source.values():
            if ids and len(chosen) < count:
                chosen.append(ids.pop())

    async def draft(passage_id: str) -> Question | None:
        passage = corpus.get(passage_id)
        payload = await client.complete_json(
            model=model,
            messages=[
                {"role": "system", "content": load_prompt("eval_question")},
                {
                    "role": "user",
                    "content": f"Article: {passage.source_title}\n\nPassage:\n{passage.text}",
                },
            ],
            schema_name="question",
            schema=QUESTION_SCHEMA,
            max_tokens=200,
        )
        text = str(payload.get("question", "")).strip()
        if not text:
            return None
        return Question(
            id=passage_id, question=text, source_id=passage.source_id, passage_id=passage_id
        )

    drafted = await gather_limited([partial(draft, p) for p in chosen])
    questions = [item for item in drafted if isinstance(item, Question)]
    failures = [item for item in drafted if isinstance(item, BaseException)]
    if failures:
        print(f"{len(failures)} question drafts failed: {failures[0]!r}")
    for question in questions:
        append_jsonl(path, question)
    return questions


async def run_questions(
    settings: Settings,
    corpus: Corpus,
    client: ModelClient,
    questions: list[Question],
    path: Path,
) -> list[Run]:
    """Answer every question in both conditions and score every claim."""
    pipeline = Pipeline(settings, corpus, client)
    done = {(run.question_id, run.condition) for run in read_jsonl(path, Run)}

    async def one(question: Question, condition: Condition) -> None:
        context_ids: list[str] = []
        if condition == "readings":
            hits = corpus.search(question.question, settings.passages_per_answer)
            if not pipeline.covered(hits):
                append_jsonl(
                    path, Run(question_id=question.id, condition=condition, answered=False)
                )
                return
            context = [hit.passage for hit in hits]
            context_ids = [passage.id for passage in context]
            messages = answer_messages(question.question, context)
        else:
            messages = memory_messages(question.question)
        answer, samples = await pipeline.generate(messages)
        if answer.text.upper().startswith("NOT_COVERED"):
            append_jsonl(path, Run(question_id=question.id, condition=condition, answered=False))
            return
        claims = await pipeline.score(answer, samples)
        append_jsonl(
            path,
            Run(
                question_id=question.id,
                condition=condition,
                answered=True,
                answer=answer.text,
                claims=[RunClaim(id=c.id, text=c.text, signals=c.signals) for c in claims],
                context_passage_ids=context_ids,
                samples=len(samples),
            ),
        )

    jobs = [partial(one, q, c) for q in questions for c in CONDITIONS if (q.id, c) not in done]
    failures = [r for r in await gather_limited(jobs) if isinstance(r, BaseException)]
    if failures:
        print(f"{len(failures)} runs failed and can be retried: {failures[0]!r}")
    return read_jsonl(path, Run)


def _plain(text: str) -> str:
    text = text.lower().translate(str.maketrans("‘’“”–—", "''\"\"--"))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def quote_in(article: str, quote: str) -> bool:
    """Whether a quote appears in the article, ignoring case, spacing and punctuation."""
    plain = _plain(quote)
    return bool(plain) and plain in _plain(article)


async def label_runs(
    corpus: Corpus,
    client: ModelClient,
    model: str,
    questions: list[Question],
    runs: list[Run],
    path: Path,
) -> list[ClaimLabel]:
    """Label every claim against the full article its question was written from."""
    source_of = {question.id: question.source_id for question in questions}
    articles: dict[str, str] = {}
    for passage in corpus.passages:
        articles[passage.source_id] = (
            f"{articles.get(passage.source_id, '')}\n\n{passage.section}\n{passage.text}".strip()
        )
    done = {(label.question_id, label.condition) for label in read_jsonl(path, ClaimLabel)}

    async def one(run: Run) -> None:
        article = articles[source_of[run.question_id]]
        statements = "\n".join(f"{claim.id}. {claim.text}" for claim in run.claims)
        payload = await client.complete_json(
            model=model,
            messages=[
                {"role": "system", "content": load_prompt("eval_label")},
                {
                    "role": "user",
                    "content": f"Reference article:\n{article}\n\nStatements:\n{statements}",
                },
            ],
            schema_name="labels",
            schema=LABEL_SCHEMA,
            max_tokens=1200,
        )
        entries = payload.get("labels")
        if not isinstance(entries, list):
            raise ModelUnavailable("The labeller returned no labels.")
        by_number = {entry.get("statement"): entry for entry in entries if isinstance(entry, dict)}
        if any(claim.id not in by_number for claim in run.claims):
            raise ModelUnavailable("The labeller skipped a statement.")
        for claim in run.claims:
            entry = by_number[claim.id]
            evidence = str(entry.get("evidence", "")).strip()
            append_jsonl(
                path,
                ClaimLabel(
                    question_id=run.question_id,
                    condition=run.condition,
                    claim_id=claim.id,
                    label=entry["label"],
                    evidence=evidence,
                    evidence_found=quote_in(article, evidence),
                ),
            )

    jobs = [
        partial(one, r)
        for r in runs
        if r.answered and r.claims and (r.question_id, r.condition) not in done
    ]
    failures = [r for r in await gather_limited(jobs) if isinstance(r, BaseException)]
    if failures:
        print(f"{len(failures)} labelling calls failed and can be retried: {failures[0]!r}")
    return read_jsonl(path, ClaimLabel)


def dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
