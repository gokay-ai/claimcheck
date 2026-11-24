# 5. Mark on a combined score, with a default set by cost

**Status:** accepted, to be revisited with a larger evaluation

## Context

Two signals were proposed in the literature review: token probability and agreement across re-asked answers. The pilot ([evaluation.md](../evaluation.md)) scored each one and their mean.

| Data | Token probability | Re-ask disagreement | Combined |
|---|---|---|---|
| Readings (4 wrong of 134) | 0.80 | 0.63 | 0.80 |
| Memory (31 wrong of 127) | 0.50 | 0.75 | 0.72 |
| Pooled | 0.64 | 0.73 | 0.76 |

## Decision

- Mark on the mean of the two signals. It is the best or near-best in every row, and it does not depend on which condition a question resembles.
- Set the default threshold at 0.35, the least eager setting that still catches three in four wrong claims (80% caught, 38% of correct claims also marked).
- Let the student move the threshold and show the measured rates at every setting.

## Why not disagreement alone

It was better in the memory condition, but at 0.35 it caught only 43% of wrong claims. With four re-asks it takes few distinct values, so its threshold cannot be set finely.

## Consequences

- About 4 in 10 correct claims are marked at the default. That many false alarms risks students ignoring the marks, which is why the rates are shown and the threshold is theirs to move.
- The readings row has 4 wrong claims. The choice between signals could change with more data from that condition.
