from claimcheck.config import Settings
from claimcheck.pipeline import Pipeline
from claimcheck.retrieval import Corpus

from .conftest import FakeClient


def test_every_passage_belongs_to_a_listed_source(corpus: Corpus) -> None:
    sources = {source.id for source in corpus.sources}
    assert corpus.passages
    assert all(passage.source_id in sources for passage in corpus.passages)
    assert all("oldid=" in passage.url for passage in corpus.passages)


def test_a_question_finds_its_reading(corpus: Corpus) -> None:
    hits = corpus.search("What is Fitts's law used to predict?", 4)
    assert hits[0].passage.source_id == "fittss-law"
    assert hits[0].coverage > 0.9
    assert [hit.score for hit in hits] == sorted((hit.score for hit in hits), reverse=True)


def test_search_can_be_limited_to_given_passages(corpus: Corpus) -> None:
    hits = corpus.search("short-term memory capacity", 5, within=["fittss-law-01"])
    assert [hit.passage.id for hit in hits] in ([], ["fittss-law-01"])


def test_coverage_separates_questions_inside_and_outside_the_readings(
    corpus: Corpus, settings: Settings
) -> None:
    pipeline = Pipeline(settings, corpus, FakeClient("unused"))
    inside = [
        "How many items can short-term memory hold?",
        "What is automation bias?",
        "What does the forgetting curve show?",
        "How does anchoring affect negotiation?",
    ]
    outside = [
        "What is the capital of Australia?",
        "How do I bake sourdough bread?",
        "Who won the 2018 World Cup?",
    ]
    for question in inside:
        assert pipeline.covered(corpus.search(question, 4)), question
    for question in outside:
        assert not pipeline.covered(corpus.search(question, 4)), question
