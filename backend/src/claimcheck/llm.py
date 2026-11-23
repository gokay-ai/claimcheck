"""A thin client for an OpenAI-compatible chat endpoint (OpenRouter by default).

The pipeline depends on the `ModelClient` protocol, not on this class, so tests
and the recorded demo run without a network.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

Message = dict[str, str]


class ModelUnavailable(Exception):
    """The model endpoint failed, timed out or returned something unusable."""


@dataclass(frozen=True)
class TokenProbability:
    token: str
    probability: float


@dataclass(frozen=True)
class Completion:
    text: str
    tokens: list[TokenProbability] = field(default_factory=list)


class ModelClient(Protocol):
    async def complete(
        self,
        *,
        model: str,
        messages: list[Message],
        temperature: float,
        max_tokens: int,
        token_probabilities: bool = False,
    ) -> Completion: ...

    async def complete_json(
        self,
        *,
        model: str,
        messages: list[Message],
        schema_name: str,
        schema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any]: ...


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=api_base.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}", "X-Title": "ClaimCheck"},
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def complete(
        self,
        *,
        model: str,
        messages: list[Message],
        temperature: float,
        max_tokens: int,
        token_probabilities: bool = False,
    ) -> Completion:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if token_probabilities:
            body["logprobs"] = True
            # Without this the router may pick a provider that silently drops
            # log-probabilities, and the token signal would vanish.
            body["provider"] = {"require_parameters": True}
        choice = await self._post(body)
        text = choice.get("message", {}).get("content")
        if not isinstance(text, str) or not text.strip():
            raise ModelUnavailable("The model returned an empty answer.")
        tokens: list[TokenProbability] = []
        if token_probabilities:
            entries = (choice.get("logprobs") or {}).get("content") or []
            tokens = [
                TokenProbability(entry["token"], math.exp(min(entry["logprob"], 0.0)))
                for entry in entries
            ]
            if not tokens:
                raise ModelUnavailable("The model returned no token probabilities.")
        return Completion(text, tokens)

    async def complete_json(
        self,
        *,
        model: str,
        messages: list[Message],
        schema_name: str,
        schema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        }
        choice = await self._post(body)
        try:
            parsed = json.loads(choice["message"]["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ModelUnavailable("The model returned malformed JSON.") from error
        if not isinstance(parsed, dict):
            raise ModelUnavailable("The model returned JSON of the wrong shape.")
        return parsed

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for _attempt in range(2):  # one retry covers a transient upstream fault
            try:
                response = await self._http.post("/chat/completions", json=body)
            except httpx.HTTPError as error:
                last_error = error
                continue
            if response.status_code >= 500 or response.status_code == 429:
                last_error = ModelUnavailable(f"Upstream status {response.status_code}")
                continue
            if response.status_code >= 400:
                raise ModelUnavailable(f"Upstream rejected the request ({response.status_code}).")
            payload = response.json()
            choices = payload.get("choices") if isinstance(payload, dict) else None
            if not choices:
                last_error = ModelUnavailable("Upstream returned no choices.")
                continue
            choice: dict[str, Any] = choices[0]
            return choice
        raise ModelUnavailable("The model endpoint did not respond.") from last_error
