"""Command line for the pilot evaluation.

    claimcheck-eval questions   write the question set from the readings
    claimcheck-eval run         answer every question in both conditions
    claimcheck-eval label       label every claim against its article
    claimcheck-eval report      compute the measures and the app's calibration

Each step appends to a file under the evaluation directory and skips work that
is already there, so an interrupted step can simply be run again.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from ..config import Settings
from ..llm import OpenRouterClient
from ..retrieval import Corpus
from ..signals import DEFAULT_SIGNAL, SIGNALS
from . import report, runner

QUESTION_MODEL = "anthropic/claude-haiku-5.5"
LABEL_MODEL = "anthropic/claude-sonnet-5.5"

BASIS = {
    "pooled": "pilot test, answers written with and without the readings",
    "readings": "pilot test, answers written from the readings",
    "memory": "pilot test, answers written without the readings",
}


def default_dir() -> Path:
    for candidate in (Path.cwd() / "evaluation", Path.cwd().parent / "evaluation"):
        if candidate.is_dir():
            return candidate
    return Path.cwd() / "evaluation"


async def main_async(args: argparse.Namespace) -> int:
    settings = Settings()
    corpus = Corpus.load(settings.data_dir / "corpus")
    directory: Path = args.dir
    questions_path = directory / "questions.jsonl"
    runs_path = directory / "results" / "runs.jsonl"
    labels_path = directory / "results" / "labels.jsonl"

    if args.command == "report":
        questions = runner.read_jsonl(questions_path, runner.Question)
        runs = runner.read_jsonl(runs_path, runner.Run)
        labels = runner.read_jsonl(labels_path, runner.ClaimLabel)
        summary, items = report.write_report(directory / "results", questions, runs, labels)
        print(report.table(summary))
        if args.calibrate:
            chosen = [i for i in items if args.data == "pooled" or i.condition == args.data]
            calibration = report.calibration(chosen, args.signal, BASIS[args.data])
            target = settings.data_dir / "calibration.json"
            target.write_text(calibration.model_dump_json(indent=2) + "\n", encoding="utf-8")
            print(f"\nwrote {target} (default threshold {calibration.default_threshold})")
        return 0

    if not settings.api_key:
        print("Set OPENROUTER_API_KEY to run the model-backed steps.")
        return 2
    client = OpenRouterClient(api_base=settings.api_base, api_key=settings.api_key, timeout=90.0)
    try:
        questions = await runner.write_questions(
            corpus, client, args.question_model, questions_path, args.count, args.seed
        )
        print(f"{len(questions)} questions")
        if args.command == "questions":
            return 0
        runs = await runner.run_questions(settings, corpus, client, questions, runs_path)
        print(f"{len(runs)} runs, {sum(len(run.claims) for run in runs)} claims")
        if args.command == "run":
            return 0
        labels = await runner.label_runs(
            corpus, client, args.label_model, questions, runs, labels_path
        )
        print(f"{len(labels)} labels")
        return 0
    finally:
        await client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="claimcheck-eval", description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["questions", "run", "label", "report"])
    parser.add_argument("--dir", type=Path, default=default_dir(), help="evaluation directory")
    parser.add_argument("--count", type=int, default=60, help="questions to write")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--question-model", default=QUESTION_MODEL)
    parser.add_argument("--label-model", default=LABEL_MODEL)
    parser.add_argument("--calibrate", action="store_true", help="write the app's calibration")
    parser.add_argument("--signal", choices=sorted(SIGNALS), default=DEFAULT_SIGNAL)
    parser.add_argument("--data", choices=sorted(BASIS), default="pooled")
    raise SystemExit(asyncio.run(main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
