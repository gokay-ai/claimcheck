#!/usr/bin/env python3
"""Build the bundled reading corpus from English Wikipedia.

Each article is fetched as plain text through the MediaWiki API, split into
passages by section, and written with its provenance (title, section, revision
id and a permanent link). Provenance is stored here, at indexing time, because
it cannot be recovered once a passage has been cut out of its page.

Usage:
    python3 scripts/build_corpus.py            # fetch and rebuild the corpus
    python3 scripts/build_corpus.py --check    # verify the corpus on disk

Only the standard library is used, so the script runs without the backend
environment.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "claimcheck-corpus-builder/0.1 (university coursework project)"
LICENCE = "CC BY-SA 4.0"
LICENCE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"

OUT_DIR = Path(__file__).resolve().parent.parent / "backend/src/claimcheck/data/corpus"

# The readings cover the human-factors concepts a student meets when studying
# interactive systems: perception and attention, memory, action and decision.
ARTICLES: list[tuple[str, str]] = [
    ("Detection theory", "Perception and attention"),
    ("Inattentional blindness", "Perception and attention"),
    ("Change blindness", "Perception and attention"),
    ("Broadbent's filter model of attention", "Perception and attention"),
    ("Alarm fatigue", "Perception and attention"),
    ("Working memory", "Memory and mental models"),
    ("Short-term memory", "Memory and mental models"),
    ("Chunking (psychology)", "Memory and mental models"),
    ("The Magical Number Seven, Plus or Minus Two", "Memory and mental models"),
    ("Atkinson–Shiffrin memory model", "Memory and mental models"),
    ("Forgetting curve", "Memory and mental models"),
    ("Cognitive load", "Memory and mental models"),
    ("Mental model", "Memory and mental models"),
    ("Affordance", "Action and decision"),
    ("Fitts's law", "Action and decision"),
    ("Hick's law", "Action and decision"),
    ("Automation bias", "Action and decision"),
    ("Anchoring effect", "Action and decision"),
    ("Bounded rationality", "Action and decision"),
]

# Sections that hold no prose worth retrieving.
SKIPPED_SECTIONS = {
    "see also",
    "references",
    "external links",
    "further reading",
    "notes",
    "citations",
    "bibliography",
    "footnotes",
    "sources",
    "works cited",
}

MIN_WORDS = 25
TARGET_WORDS = 150
MAX_WORDS = 230

HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$")


def fetch(title: str) -> dict:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
        "prop": "extracts|revisions",
        "explaintext": "1",
        "exsectionformat": "wiki",
        "rvprop": "ids|timestamp",
        "titles": title,
    }
    request = urllib.request.Request(
        f"{API}?{urllib.parse.urlencode(params)}", headers={"User-Agent": USER_AGENT}
    )
    payload = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 4:
                raise
            # The API asks clients to slow down; honour its hint when it gives one.
            wait = int(error.headers.get("Retry-After") or 0) or 5 * (attempt + 1)
            print(f"  rate limited, waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
    assert payload is not None
    page = payload["query"]["pages"][0]
    if page.get("missing") or not page.get("extract"):
        raise RuntimeError(f"No article text for {title!r}")
    return page


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower().replace("–", "-").replace("'", ""))
    return slug.strip("-")


def clean(text: str) -> str:
    # Plain-text extracts keep stray layout whitespace and maths markup.
    text = re.sub(r"\{\\displaystyle[^\n]*", " ", text)
    text = re.sub(r"[ \t    ]+", " ", text)
    return text.strip()


def is_prose(paragraph: str) -> bool:
    """Keep sentences; drop formula debris and one-line list fragments."""
    words = paragraph.split()
    if len(words) < 8:
        return False
    letters = sum(ch.isalpha() for ch in paragraph)
    return letters / max(len(paragraph), 1) > 0.6


def split_sections(extract: str) -> list[tuple[str, list[str]]]:
    """Return (section path, paragraphs) pairs in reading order."""
    sections: list[tuple[str, list[str]]] = []
    trail: list[str] = []
    current: list[str] = []
    skipping = False

    def flush() -> None:
        if current and not skipping:
            sections.append((" › ".join(trail) or "Introduction", list(current)))
        current.clear()

    for raw_line in extract.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = HEADING.match(line)
        if heading:
            flush()
            depth = len(heading.group(1)) - 2
            trail[depth:] = [heading.group(2)]
            skipping = trail[0].lower() in SKIPPED_SECTIONS
            continue
        paragraph = clean(line)
        if is_prose(paragraph):
            current.append(paragraph)
    flush()
    return sections


def split_long(paragraph: str) -> list[str]:
    """Break a paragraph that exceeds MAX_WORDS at sentence boundaries."""
    if len(paragraph.split()) <= MAX_WORDS:
        return [paragraph]
    pieces: list[str] = []
    buffer: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", paragraph):
        if buffer and len(" ".join(buffer + [sentence]).split()) > TARGET_WORDS:
            pieces.append(" ".join(buffer))
            buffer = []
        buffer.append(sentence)
    if buffer:
        pieces.append(" ".join(buffer))
    return pieces


def pack(paragraphs: list[str]) -> list[str]:
    """Group consecutive paragraphs into passages of about TARGET_WORDS."""
    passages: list[str] = []
    buffer: list[str] = []
    count = 0
    for paragraph in (piece for p in paragraphs for piece in split_long(p)):
        words = len(paragraph.split())
        if buffer and count + words > MAX_WORDS:
            passages.append(" ".join(buffer))
            buffer, count = [], 0
        buffer.append(paragraph)
        count += words
        if count >= TARGET_WORDS:
            passages.append(" ".join(buffer))
            buffer, count = [], 0
    if buffer:
        tail = " ".join(buffer)
        if passages and count < MIN_WORDS:
            passages[-1] = f"{passages[-1]} {tail}"
        else:
            passages.append(tail)
    return passages


def build() -> tuple[list[dict], list[dict]]:
    sources: list[dict] = []
    passages: list[dict] = []
    for title, topic in ARTICLES:
        page = fetch(title)
        revision = page["revisions"][0]
        source_id = slugify(page["title"])
        page_path = urllib.parse.quote(page["title"].replace(" ", "_"))
        permalink = (
            f"https://en.wikipedia.org/w/index.php?title={page_path}&oldid={revision['revid']}"
        )
        count = 0
        for section, paragraphs in split_sections(page["extract"]):
            for text in pack(paragraphs):
                if len(text.split()) < MIN_WORDS:
                    continue
                count += 1
                passages.append(
                    {
                        "id": f"{source_id}-{count:02d}",
                        "source_id": source_id,
                        "source_title": page["title"],
                        "section": section,
                        "text": text,
                        "url": permalink,
                    }
                )
        sources.append(
            {
                "id": source_id,
                "title": page["title"],
                "topic": topic,
                "url": permalink,
                "revision_id": revision["revid"],
                "revision_timestamp": revision["timestamp"],
                "publisher": "Wikipedia contributors",
                "licence": LICENCE,
                "licence_url": LICENCE_URL,
                "passages": count,
            }
        )
        print(f"{page['title']:48s} rev {revision['revid']}  {count:3d} passages")
        time.sleep(2)  # stay well inside the API's rate etiquette
    return sources, passages


def write(sources: list[dict], passages: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "sources.json").write_text(
        json.dumps(sources, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with (OUT_DIR / "passages.jsonl").open("w", encoding="utf-8") as handle:
        for passage in passages:
            handle.write(json.dumps(passage, ensure_ascii=False) + "\n")


def check() -> int:
    sources = json.loads((OUT_DIR / "sources.json").read_text(encoding="utf-8"))
    lines = (OUT_DIR / "passages.jsonl").read_text(encoding="utf-8").splitlines()
    passages = [json.loads(line) for line in lines]
    known = {source["id"] for source in sources}
    orphans = [p["id"] for p in passages if p["source_id"] not in known]
    words = sum(len(p["text"].split()) for p in passages)
    print(f"{len(sources)} sources, {len(passages)} passages, {words} words")
    if orphans:
        print(f"passages without a source: {orphans}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify the corpus on disk")
    args = parser.parse_args()
    if args.check:
        return check()
    sources, passages = build()
    write(sources, passages)
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
