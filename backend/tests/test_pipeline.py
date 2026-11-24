import pytest

from claimcheck.config import Settings
from claimcheck.llm import ModelUnavailable, TokenProbability
from claimcheck.pipeline import Pipeline
from claimcheck.retrieval import Corpus
from claimcheck.schemas import AskResult, ResultEvent, StageEvent

from .conftest import FakeClient

QUESTION = "How many items can short-term memory hold?"
ANSWER = "Short-term memory holds 3 to 5 items. That figure replaced the older limit of 7 items."


async def run(pipeline: Pipeline, question: str) -> tuple[list[str], AskResult]:
    stages: list[str] = []
    result: AskResult | None = None
    async for event in pipeline.run(question):
        if isinstance(event, StageEvent):
            stages.append(event.stage)
        elif isinstance(event, ResultEvent):
            result = event.result
    assert result is not None
    return stages, result


async def test_an_answer_is_split_scored_and_tied_to_passages(
    settings: Settings, corpus: Corpus
) -> None:
    client = FakeClient(
        ANSWER,
        samples=["s1", "s2", "s3", "s4"],
        verdicts=[["supported", "contradicted"]] * 2 + [["supported", "supported"]] * 2,
    )
    stages, result = await run(Pipeline(settings, corpus, client), QUESTION)

    assert stages == ["retrieving", "answering", "checking"]
    assert result.status == "answered"
    assert result.samples == 4
    assert [claim.text for claim in result.claims] == [
        "Short-term memory holds 3 to 5 items.",
        "That figure replaced the older limit of 7 items.",
    ]
    first, second = result.claims
    assert first.signals.disagreement == 0.0
    assert second.signals.disagreement == 0.5
    assert second.risk > first.risk
    assert result.answer[second.start : second.end] == second.text

    shown = {passage.id for passage in result.passages}
    assert set(result.context_passage_ids) <= shown
    assert first.support is not None and first.support.passage_id in shown


async def test_a_question_outside_the_readings_is_declined_without_a_model_call(
    settings: Settings, corpus: Corpus
) -> None:
    client = FakeClient(ANSWER)
    stages, result = await run(
        Pipeline(settings, corpus, client), "What is the capital of Australia?"
    )
    assert stages == ["retrieving"]
    assert result.status == "not_covered"
    assert result.claims == []
    assert client.sampled == 0


async def test_the_model_can_decline_when_the_passages_do_not_answer(
    settings: Settings, corpus: Corpus
) -> None:
    _, result = await run(Pipeline(settings, corpus, FakeClient("NOT_COVERED")), QUESTION)
    assert result.status == "not_covered"


async def test_failed_samples_weaken_the_signal_but_do_not_fail_the_answer(
    settings: Settings, corpus: Corpus
) -> None:
    client = FakeClient(ANSWER, samples=["only one sample"])
    _, result = await run(Pipeline(settings, corpus, client), QUESTION)
    assert result.status == "answered"
    assert result.samples == 1
    assert all(len(claim.signals.sample_verdicts) == 1 for claim in result.claims)


async def test_verdicts_for_unknown_statements_are_ignored(
    settings: Settings, corpus: Corpus
) -> None:
    client = FakeClient(ANSWER, samples=["s1"], verdicts=[["supported", "supported", "bogus"]])
    _, result = await run(Pipeline(settings, corpus, client), QUESTION)
    assert [claim.signals.sample_verdicts for claim in result.claims] == [
        ["supported"],
        ["supported"],
    ]


async def test_a_failed_answer_is_raised(settings: Settings, corpus: Corpus) -> None:
    pipeline = Pipeline(settings, corpus, FakeClient(ANSWER, fail_answer=True))
    with pytest.raises(ModelUnavailable):
        await run(pipeline, QUESTION)


async def test_a_failed_judge_leaves_the_answer_without_a_second_opinion(
    settings: Settings, corpus: Corpus
) -> None:
    client = FakeClient(ANSWER, samples=["s1", "s2"], fail_judge=True)
    _, result = await run(Pipeline(settings, corpus, client), QUESTION)
    assert result.status == "answered"
    assert all(claim.signals.sample_verdicts == [] for claim in result.claims)
    assert all(claim.signals.disagreement is None for claim in result.claims)


