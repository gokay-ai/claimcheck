# 6. Ship a recorded demo that needs no key

**Status:** accepted

## Context

A reviewer must be able to run the system without the author's model key, and keys must never be committed. Browser tests also need results that do not change between runs.

## Decision

With no key set, the API replays recorded results for 7 example questions. Each recording is the unedited output of a live run, written by `scripts/record_replay.py`. The interface labels the mode ("Recorded demo", "Recorded answer") and says that other questions need the live version.

## Consequences

- The interaction can be inspected and tested with no account, cost or network.
- The examples were chosen to show a range of outcomes, including an answer with an error the marks miss, so they are illustrations and not a sample.
- The stage timing in the recorded demo is simulated (0.5 s per step); live timing is about 4 s in total.
