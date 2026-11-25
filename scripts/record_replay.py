#!/usr/bin/env python3
"""Record the example questions with a live model, for the replay demo.

Each recording is the result exactly as the pipeline returned it. Run from the
backend environment with a model key set:

    cd backend && uv run python ../scripts/record_replay.py
"""

from __future__ import annotations

import asyncio
import json
import sys

from claimcheck.config import Settings
from claimcheck.llm import OpenRouterClient
from claimcheck.pipeline import Pipeline
from claimcheck.replay import normalise
from claimcheck.retrieval import Corpus
from claimcheck.schemas import Example, ResultEvent


async def main() -> int:
    settings = Settings()
    if not settings.api_key:
        print("Set OPENROUTER_API_KEY to record.", file=sys.stderr)
        return 2
    corpus = Corpus.load(settings.data_dir / "corpus")
    examples = [
        Example.model_validate(item)
        for item in json.loads((settings.data_dir / "examples.json").read_text(encoding="utf-8"))
    ]
    out_dir = settings.data_dir / "replay"
    out_dir.mkdir(exist_ok=True)
    for stale in out_dir.glob("*.json"):
        stale.unlink()
    client = OpenRouterClient(
        api_base=settings.api_base,
        api_key=settings.api_key,
        timeout=settings.request_timeout_seconds,
    )
    try:
        pipeline = Pipeline(settings, corpus, client)
        for example in examples:
            async for event in pipeline.run(example.question):
                if isinstance(event, ResultEvent):
                    name = normalise(example.question).replace(" ", "-")[:60]
                    path = out_dir / f"{name}.json"
                    path.write_text(event.result.model_dump_json(indent=2) + "\n", encoding="utf-8")
                    risks = ", ".join(f"{claim.risk:.2f}" for claim in event.result.claims)
                    print(f"{event.result.status:12s} {example.question}  [{risks}]")
    finally:
        await client.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
