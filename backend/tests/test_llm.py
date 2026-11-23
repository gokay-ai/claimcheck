import json
import math

import httpx
import pytest

from claimcheck.llm import ModelUnavailable, OpenRouterClient

MESSAGES = [{"role": "user", "content": "hello"}]


def client_for(handler: httpx.MockTransport) -> OpenRouterClient:
    return OpenRouterClient(
        api_base="https://example.test/v1", api_key="k", timeout=5, transport=handler
    )


def reply(content: str, logprobs: list[dict[str, object]] | None = None) -> httpx.Response:
    choice: dict[str, object] = {"message": {"content": content}}
    if logprobs is not None:
        choice["logprobs"] = {"content": logprobs}
    return httpx.Response(200, json={"choices": [choice]})


async def test_token_probabilities_are_requested_and_converted() -> None:
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        assert request.headers["authorization"] == "Bearer k"
        return reply(
            "Hi.", [{"token": "Hi", "logprob": math.log(0.5)}, {"token": ".", "logprob": 0}]
        )

    client = client_for(httpx.MockTransport(handler))
    completion = await client.complete(
        model="m", messages=MESSAGES, temperature=0.2, max_tokens=10, token_probabilities=True
    )
    assert completion.text == "Hi."
    assert [token.probability for token in completion.tokens] == pytest.approx([0.5, 1.0])
    assert seen[0]["logprobs"] is True
    assert seen[0]["provider"] == {"require_parameters": True}


async def test_missing_token_probabilities_are_an_error() -> None:
    client = client_for(httpx.MockTransport(lambda request: reply("Hi.")))
    with pytest.raises(ModelUnavailable):
        await client.complete(
            model="m", messages=MESSAGES, temperature=0.2, max_tokens=10, token_probabilities=True
        )


async def test_a_reply_that_is_not_json_fails_the_call() -> None:
    client = client_for(httpx.MockTransport(lambda request: reply("not json")))
    with pytest.raises(ModelUnavailable):
        await client.complete_json(
            model="m", messages=MESSAGES, schema_name="s", schema={"type": "object"}, max_tokens=10
        )


async def test_one_upstream_fault_is_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503) if calls == 1 else reply('{"ok": true}')

    client = client_for(httpx.MockTransport(handler))
    payload = await client.complete_json(
        model="m", messages=MESSAGES, schema_name="s", schema={"type": "object"}, max_tokens=10
    )
    assert payload == {"ok": True}
    assert calls == 2


async def test_a_rejected_request_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401)

    client = client_for(httpx.MockTransport(handler))
    with pytest.raises(ModelUnavailable):
        await client.complete(model="m", messages=MESSAGES, temperature=0, max_tokens=10)
    assert calls == 1
