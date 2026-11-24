import json

from fastapi.testclient import TestClient

from claimcheck.api import create_app
from claimcheck.config import Settings
from claimcheck.replay import ReplayStore
from claimcheck.retrieval import Corpus

from .conftest import FakeClient

ANSWER = "Short-term memory holds 3 to 5 items. That figure replaced the older limit of 7 items."


def events(client: TestClient, question: str) -> list[dict[str, object]]:
    response = client.post("/api/ask", json={"question": question})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line]


def replay_client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings, replay_stage_seconds=0))


def live_client(**overrides: object) -> tuple[TestClient, FakeClient]:
    settings = Settings(mode="live", api_key="", _env_file=None, **overrides)  # type: ignore[arg-type, call-arg]
    model = FakeClient(ANSWER, samples=["s1", "s2", "s3", "s4"] * 5)
    return TestClient(create_app(settings, client=model, replay_stage_seconds=0)), model


def test_every_example_has_a_recording_that_points_at_real_passages(
    settings: Settings, corpus: Corpus
) -> None:
    store = ReplayStore.load(settings.data_dir)
    assert store.missing() == []
    for example in store.examples:
        recording = store.find(example.question)
        assert recording is not None and recording.mode == "replay"
        shown = {passage.id for passage in recording.passages}
        for passage in recording.passages:
            assert corpus.get(passage.id).text == passage.text
        for claim in recording.claims:
            assert recording.answer[claim.start : claim.end] == claim.text
            assert claim.support is None or claim.support.passage_id in shown


def test_meta_describes_the_demo(settings: Settings) -> None:
    meta = replay_client(settings).get("/api/meta").json()
    assert meta["mode"] == "replay"
    assert len(meta["sources"]) == 19
    assert len(meta["examples"]) == 7
    calibration = meta["calibration"]
    thresholds = [point["threshold"] for point in calibration["points"]]
    assert calibration["default_threshold"] in thresholds
    assert calibration["wrong_claims"] > 0


def test_a_recorded_question_replays_its_stages_and_result(settings: Settings) -> None:
    received = events(replay_client(settings), "how many items can short-term memory hold")
    assert [event["type"] for event in received] == ["stage", "stage", "stage", "result"]
    result = received[-1]["result"]
    assert isinstance(result, dict)
    assert result["mode"] == "replay" and result["status"] == "answered"


def test_replay_declines_a_question_outside_the_readings(settings: Settings) -> None:
    received = events(replay_client(settings), "What is the capital of Australia?")
    assert [event["type"] for event in received] == ["stage", "result"]


def test_replay_says_so_when_a_question_was_not_recorded(settings: Settings) -> None:
    received = events(replay_client(settings), "What is cognitive load?")
    assert received == [
        {
            "type": "error",
            "code": "not_recorded",
            "message": received[0]["message"],
            "retry_after_seconds": None,
        }
    ]


def test_a_live_question_runs_the_pipeline() -> None:
    client, _ = live_client()
    received = events(client, "How many items can short-term memory hold?")
    assert [event["type"] for event in received] == ["stage", "stage", "stage", "result"]
    result = received[-1]["result"]
    assert isinstance(result, dict) and result["mode"] == "live"
    assert client.get("/api/health").json() == {"status": "ok", "mode": "live"}


def test_live_requests_are_rate_limited_per_client() -> None:
    client, _ = live_client(rate_limit_per_client=1)
    question = "How many items can short-term memory hold?"
    assert events(client, question)[-1]["type"] == "result"
    blocked = events(client, question)
    assert blocked[0]["code"] == "rate_limited"
    assert isinstance(blocked[0]["retry_after_seconds"], int)


def test_a_model_failure_is_reported_as_an_event() -> None:
    settings = Settings(mode="live", api_key="", _env_file=None)  # type: ignore[call-arg]
    app = create_app(settings, client=FakeClient(ANSWER, fail_answer=True))
    received = events(TestClient(app), "How many items can short-term memory hold?")
    assert received[-1]["code"] == "model_unavailable"


def test_an_overlong_question_is_rejected(settings: Settings) -> None:
    received = events(replay_client(settings), "why " * 200)
    assert received[0]["code"] == "invalid_question"
