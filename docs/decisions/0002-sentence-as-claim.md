# 2. Treat each sentence as one claim

**Status:** accepted

## Context

The literature review argued for marking claims, not tokens: people check claims, and token-level highlights fell on wording that was often fine (Vasconcelos et al., 2025). A claim could be extracted by another model call or taken to be a sentence.

## Decision

The answer prompt asks for one checkable fact per sentence, and a deterministic splitter turns each sentence into a claim with exact offsets.

## Consequences

- Token probabilities map onto claims exactly, and the same split is used by the app and the evaluation.
- No extra model call, so no second place for invented content.
- A sentence can still hold two facts. Then the mark covers both, and a student has to work out which part is doubtful.
