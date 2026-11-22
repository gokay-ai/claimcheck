"""Lexical retrieval over the bundled readings.

BM25 is enough for a few hundred passages and keeps retrieval deterministic,
inspectable and free of an embedding service. Similarity is not relevance, so
the index also reports how much of a query the best passage covers; the
pipeline uses that to decline instead of answering from an unrelated passage.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .schemas import Passage, Source
from .text import terms

K1 = 1.5
B = 0.75


@dataclass(frozen=True)
class Hit:
    passage: Passage
    score: float
    # Share of the query's inverse-document-frequency weight found in the passage.
    coverage: float


class Corpus:
    def __init__(self, sources: list[Source], passages: list[Passage]) -> None:
        self.sources = sources
        self.passages = passages
        self._by_id = {passage.id: passage for passage in passages}
        self._term_counts = [
            Counter(terms(f"{p.source_title} {p.section} {p.text}")) for p in passages
        ]
        self._lengths = [sum(counts.values()) for counts in self._term_counts]
        self._average_length = sum(self._lengths) / max(len(self._lengths), 1)
        document_frequency: Counter[str] = Counter()
        for counts in self._term_counts:
            document_frequency.update(counts.keys())
        total = len(passages)
        self._idf = {
            term: math.log(1 + (total - df + 0.5) / (df + 0.5))
            for term, df in document_frequency.items()
        }
        # A term the readings never use still counts against coverage.
        self._unseen_idf = math.log(1 + (total + 0.5) / 0.5)

    @classmethod
    def load(cls, directory: Path) -> Corpus:
        sources = [
            Source.model_validate(item)
            for item in json.loads((directory / "sources.json").read_text(encoding="utf-8"))
        ]
        with (directory / "passages.jsonl").open(encoding="utf-8") as handle:
            passages = [Passage.model_validate_json(line) for line in handle if line.strip()]
        return cls(sources, passages)

    def get(self, passage_id: str) -> Passage:
        return self._by_id[passage_id]

    def search(self, query: str, limit: int, within: list[str] | None = None) -> list[Hit]:
        """Rank passages for a query, best first.

        `within` restricts the search to the given passage ids.
        """
        query_terms = list(dict.fromkeys(terms(query)))
        if not query_terms:
            return []
        weights = {term: self._idf.get(term, self._unseen_idf) for term in query_terms}
        total_weight = sum(weights.values())
        allowed = set(within) if within is not None else None

        hits: list[Hit] = []
        for index, passage in enumerate(self.passages):
            if allowed is not None and passage.id not in allowed:
                continue
            counts = self._term_counts[index]
            score = 0.0
            covered = 0.0
            for term in query_terms:
                frequency = counts.get(term, 0)
                if not frequency:
                    continue
                covered += weights[term]
                norm = 1 - B + B * self._lengths[index] / self._average_length
                score += weights[term] * frequency * (K1 + 1) / (frequency + K1 * norm)
            if score > 0:
                hits.append(Hit(passage, score, covered / total_weight))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:limit]
