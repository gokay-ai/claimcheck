# 3. Retrieve with BM25 and decline when coverage is low

**Status:** accepted

## Context

Retrieval always returns its closest passages, even for a question the readings do not cover. An answer written from unrelated passages would look as fluent as any other.

## Decision

Rank the 434 passages with BM25. Before any model call, require that the best passage holds at least half of the question's term weight; otherwise decline and say what the readings do cover. The answer prompt can also decline with `NOT_COVERED`.

## Consequences

- Retrieval is deterministic, needs no embedding service and can be inspected by hand.
- Declining costs no model call.
- The check is lexical, so a question phrased in words the readings do not use can be declined wrongly. In the pilot, 5 of 49 answerable questions were declined. The threshold of 0.5 was set on a handful of test questions and has not been tuned.
