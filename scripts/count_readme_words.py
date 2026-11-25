#!/usr/bin/env python3
"""Count the README's prose words and keep the figure near its top current.

    python3 scripts/count_readme_words.py            # print the count
    python3 scripts/count_readme_words.py --update   # also rewrite the line in README.md

Code blocks, inline code, commands, image references and link targets are not
counted; link text and table text are.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"
LINE = re.compile(r"\*\*README prose word count: \d+\*\*")


def prose_words(text: str) -> int:
    text = LINE.sub(" ", text)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\|[-| :]+\|$", " ", text, flags=re.M)
    text = re.sub(r"[|#*>]", " ", text)
    return sum(1 for token in text.split() if re.search(r"[A-Za-z0-9]", token))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--update", action="store_true", help="rewrite the count in README.md")
    args = parser.parse_args()
    text = README.read_text(encoding="utf-8")
    count = prose_words(text)
    print(count)
    if args.update:
        README.write_text(
            LINE.sub(f"**README prose word count: {count}**", text), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
