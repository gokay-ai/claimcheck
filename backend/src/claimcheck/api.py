"""HTTP API. `/api/ask` streams one JSON object per line as the work proceeds."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .calibration import load_calibration
from .config import Settings, get_settings
from .llm import ModelClient, ModelUnavailable, OpenRouterClient
from .pipeline import Pipeline
from .ratelimit import RateLimiter
from .replay import ReplayStore
from .retrieval import Corpus
from .schemas import AskRequest, ErrorEvent, Meta, ResultEvent, StageEvent

logger = logging.getLogger("claimcheck")

# A recording returns at once; a short pause per stage lets the progress display
# be read as it would be with a live model.
REPLAY_STAGE_SECONDS = 0.5


def _line(event: BaseModel) -> str:
    return event.model_dump_json() + "\n"


def create_app(
    settings: Settings | None = None,
    client: ModelClient | None = None,
    replay_stage_seconds: float = REPLAY_STAGE_SECONDS,
) -> FastAPI:
    settings = settings or get_settings()
    corpus = Corpus.load(settings.data_dir / "corpus")
    replay = ReplayStore.load(settings.data_dir)
    calibration = load_calibration(settings.data_dir)
    limiter = RateLimiter(
        per_client=settings.rate_limit_per_client,
        window_seconds=settings.rate_limit_window_seconds,
        daily_cap=settings.daily_request_cap,
    )
    live = settings.live or (client is not None and settings.mode != "replay")
    owned_client: OpenRouterClient | None = None
    if live and client is None:
        owned_client = OpenRouterClient(
            api_base=settings.api_base,
            api_key=settings.api_key,
            timeout=settings.request_timeout_seconds,
        )
        client = owned_client
    pipeline = Pipeline(settings, corpus, client) if live and client is not None else None
    if settings.mode == "live" and pipeline is None:
        logger.warning("CLAIMCHECK_MODE=live but no API key is set; serving recordings only.")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if owned_client is not None:
            await owned_client.aclose()

    app = FastAPI(title="ClaimCheck", version=__version__, lifespan=lifespan)

    def client_id(request: Request) -> str:
        if settings.trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": "live" if pipeline else "replay"}

    @app.get("/api/meta")
    async def meta() -> Meta:
        return Meta(
            version=__version__,
            mode="live" if pipeline else "replay",
            model=settings.model if pipeline else "",
            samples=settings.samples,
            sources=corpus.sources,
            examples=replay.examples,
            calibration=calibration,
            max_question_chars=settings.max_question_chars,
        )

    async def replay_events(question: str) -> AsyncIterator[str]:
        recorded = replay.find(question)
        if recorded is None:
            yield _line(
                ErrorEvent(
                    code="not_recorded",
                    message=(
                        "This demo is replaying recorded answers, so only the example "
                        "questions are available."
                    ),
                )
            )
            return
        stages: list[StageEvent] = [StageEvent(stage="retrieving")]
        if recorded.status == "answered":
            stages += [StageEvent(stage="answering"), StageEvent(stage="checking")]
        for stage in stages:
            yield _line(stage)
            await asyncio.sleep(replay_stage_seconds)
        yield _line(ResultEvent(result=recorded))

    async def live_events(question: str, request: Request) -> AsyncIterator[str]:
        assert pipeline is not None
        decision = limiter.check(client_id(request))
        if not decision.allowed:
            yield _line(
                ErrorEvent(
                    code="rate_limited",
                    message="This demo has reached its question limit for now.",
                    retry_after_seconds=decision.retry_after_seconds,
                )
            )
            return
        try:
            async for event in pipeline.run(question):
                yield _line(event)
        except ModelUnavailable as error:
            logger.warning("model unavailable: %s", error)
            yield _line(
                ErrorEvent(
                    code="model_unavailable",
                    message="The language model did not return an answer that could be scored.",
                )
            )

    @app.post("/api/ask")
    async def ask(body: AskRequest, request: Request) -> StreamingResponse:
        question = " ".join(body.question.split())
        events: AsyncIterator[str]
        if not question or len(question) > settings.max_question_chars:
            events = _single(
                ErrorEvent(
                    code="invalid_question",
                    message=f"Ask one question of up to {settings.max_question_chars} characters.",
                )
            )
        elif pipeline is None:
            events = replay_events(question)
        else:
            events = live_events(question, request)
        return StreamingResponse(
            events,
            media_type="application/x-ndjson",
            # Proxies must pass each line on as it is written, or the progress
            # display would only update when the answer is already complete.
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    static_dir = settings.static_dir
    if static_dir is not None and static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str) -> FileResponse:
            candidate = (static_dir / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(static_dir.resolve()):
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

    return app


async def _single(event: BaseModel) -> AsyncIterator[str]:
    yield _line(event)


def app_factory() -> FastAPI:
    """Entry point for `uvicorn claimcheck.api:app_factory --factory`."""
    logging.basicConfig(level=logging.INFO)
    return create_app()
