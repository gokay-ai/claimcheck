# 1. Use Wikipedia articles as the readings

**Status:** accepted

## Context

The assistant answers from "course readings", so it needs a corpus that can be published with the code. Lecture slides cannot be made public. OpenStax *Psychology 2e* was the first choice, but its licence page now forbids use of the text in generative AI systems without written permission.

## Decision

Use 19 English Wikipedia articles on perception, memory and action, the human-factors concepts of the module. Each passage keeps its article, section and a permanent link to the exact revision.

## Consequences

- The corpus is redistributable under CC BY-SA 4.0, with attribution in `data/corpus/README.md`.
- Wikipedia is not a course text: articles vary in quality and sometimes hedge ("some consultants claim"). One recorded answer loses such a hedge, which the storyboards use as an example of a missed error.
- Swapping the corpus means editing one list in `scripts/build_corpus.py`.
