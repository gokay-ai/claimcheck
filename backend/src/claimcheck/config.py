"""Runtime settings, read from the environment.

Every value has a default that lets the recorded demo run with no setup; only a
live model needs a key, and the key is never read from anywhere but the
environment.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR = Path(__file__).resolve().parent / "data"


class Settings(BaseSettings):
    # The .env file sits at the repository root; the API is started from backend/.
    model_config = SettingsConfigDict(
        env_prefix="CLAIMCHECK_",
        env_file=("../.env", ".env"),
        extra="ignore",
        populate_by_name=True,
    )

    # "auto" answers live when a key is present and replays recordings otherwise.
    mode: Literal["auto", "live", "replay"] = "auto"

    api_base: str = "https://openrouter.ai/api/v1"
    api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    # The answer model must return token log-probabilities.
    model: str = "openai/gpt-4o-mini"
    judge_model: str = "openai/gpt-4o-mini"

    # Retrieval.
    passages_per_answer: int = 4
    # Share of the question's term weight that the best passage must cover.
    # Below it the readings are treated as not covering the question.
    coverage_threshold: float = 0.5

    # Signals.
    samples: int = 4
    sample_temperature: float = 1.0
    answer_temperature: float = 0.2
    request_timeout_seconds: float = 45.0

    # Protection for a public demo that spends from one key.
    rate_limit_per_client: int = 8
    rate_limit_window_seconds: int = 600
    daily_request_cap: int = 400
    trust_proxy_headers: bool = False

    max_question_chars: int = 300
    static_dir: Path | None = None
    data_dir: Path = DATA_DIR

    @property
    def live(self) -> bool:
        if self.mode == "replay":
            return False
        return bool(self.api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
