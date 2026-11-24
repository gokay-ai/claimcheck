import { useEffect, useRef, type CSSProperties } from "react";

import type { Check } from "../App";
import type { AskResult, Claim, Passage, Verdict } from "../api/types";
import { describeVerdicts, isMarked, percent, sharedSegments } from "../lib/marking";
import {
  CheckIcon,
  CrossIcon,
  ExternalIcon,
  MinusIcon,
  PointerIcon,
  RepeatIcon,
  WordIcon,
} from "./icons";

interface Props {
  result: AskResult;
  claim: Claim | null;
  threshold: number;
  check: Check | null;
  onCheck: (check: Check | null) => void;
  onClose: () => void;
}

export function CheckPanel({ result, claim, threshold, check, onCheck, onClose }: Props) {
  const heading = useRef<HTMLHeadingElement>(null);
  const claimId = claim?.id ?? null;

  useEffect(() => {
    if (claimId !== null) heading.current?.focus();
  }, [claimId]);

  if (!claim) {
    return (
      <aside className="card panel panel-empty" aria-label="Check a claim">
        <div className="empty-art" aria-hidden="true">
          <span />
          <span />
          <span />
          <PointerIcon />
        </div>
        <h2>Check a claim</h2>
        <p>
          Select a claim in the answer. You will see why it is or is not marked, and the passage
          from the readings to compare it with.
        </p>
      </aside>
    );
  }

  const marked = isMarked(claim, threshold);
  // A claim with no evidence is scored 1 by the server, so that it is never
  // shown as one that passed its checks.
  const unscored =
    claim.signals.sample_verdicts.length === 0 && claim.signals.min_token_probability === null;
  const passage = claim.support
    ? (result.passages.find((item) => item.id === claim.support?.passage_id) ?? null)
    : null;
  const others = result.passages.filter(
    (item) => result.context_passage_ids.includes(item.id) && item.id !== passage?.id,
  );

  return (
    <aside className="card panel" aria-labelledby="panel-heading">
      <div className="panel-body" key={claim.id}>
        <div className="panel-top">
          <h2 id="panel-heading" ref={heading} tabIndex={-1}>
            Check this claim
          </h2>
          <button type="button" className="link-button" onClick={onClose}>
            Close
          </button>
        </div>
        <blockquote className={marked ? "panel-claim panel-claim-marked" : "panel-claim"}>
          {claim.text}
        </blockquote>

        <section aria-labelledby="why-heading">
          <h3 id="why-heading">{marked ? "Why it is marked" : "Why it is not marked"}</h3>
          <ScoreMeter score={claim.risk} threshold={threshold} marked={marked} />
          <ul className="reasons">
            <li>
              <span className="reason-icon" aria-hidden="true">
                <RepeatIcon />
              </span>
              <div>
                <Votes verdicts={claim.signals.sample_verdicts} />
                <p>
                  {unscored
                    ? "Neither check could be run on this claim, so it is marked for you to check."
                    : describeVerdicts(claim.signals.sample_verdicts)}
                </p>
              </div>
            </li>
            {claim.signals.weakest_token !== null &&
              claim.signals.min_token_probability !== null && (
                <li>
                  <span className="reason-icon" aria-hidden="true">
                    <WordIcon />
                  </span>
                  <p>
                    The word the model least expected to write was “{claim.signals.weakest_token}” (
                    {percent(claim.signals.min_token_probability)} likely). On its own this is weak
                    evidence, so it makes up only half of the score.
                  </p>
                </li>
              )}
          </ul>
          <p className="score">
            Check score <strong>{claim.risk.toFixed(2)}</strong>. Claims are marked at{" "}
            {threshold.toFixed(2)} or more.
          </p>
        </section>

        <section aria-labelledby="passage-heading">
          <h3 id="passage-heading">Closest passage in the readings</h3>
          {passage ? (
            <PassageView passage={passage} claim={claim.text} />
          ) : (
            <p className="no-passage">
              No passage in the readings closely matches this claim. Treat it as unsupported until
              you find a source for it.
            </p>
          )}
          {others.length > 0 && (
            <details className="others">
              <summary>
                {others.length} other {others.length === 1 ? "passage" : "passages"} the answer was
                written from
              </summary>
              {others.map((item) => (
                <PassageView key={item.id} passage={item} claim={claim.text} />
              ))}
            </details>
          )}
        </section>

        <section aria-labelledby="verdict-heading" className="verdict">
          <h3 id="verdict-heading">What did you find?</h3>
          <div className="verdict-buttons" role="group" aria-labelledby="verdict-heading">
            <button
              type="button"
              className={`choice ${check === "matches" ? "choice-ok" : ""}`}
              aria-pressed={check === "matches"}
              onClick={() => onCheck(check === "matches" ? null : "matches")}
            >
              <CheckIcon />
              Matches the reading
            </button>
            <button
              type="button"
              className={`choice ${check === "differs" ? "choice-bad" : ""}`}
              aria-pressed={check === "differs"}
              onClick={() => onCheck(check === "differs" ? null : "differs")}
            >
              <CrossIcon />
              Does not match
            </button>
          </div>
          <p className="verdict-note">
            {check
              ? "Recorded on the answer. Select the same button again to undo."
              : "Your finding is shown on the answer and stays in this browser tab."}
          </p>
        </section>
      </div>
    </aside>
  );
}

/**
 * The check score on a 0-to-1 track, with a tick where marking starts. It is a
 * picture of the sentence under the reasons, which gives the same two numbers.
 */
function ScoreMeter({
  score,
  threshold,
  marked,
}: {
  score: number;
  threshold: number;
  marked: boolean;
}) {
  const scale = { "--score": score, "--threshold": threshold } as CSSProperties;
  return (
    <div className={marked ? "meter meter-marked" : "meter"} style={scale} aria-hidden="true">
      <div className="meter-track">
        <div className="meter-fill" />
        <div className="meter-tick" />
      </div>
      <div className="meter-scale">
        <span>0</span>
        <span className="meter-at">marked from {threshold.toFixed(2)}</span>
        <span>1</span>
      </div>
    </div>
  );
}

const VOTE_ICONS: Record<Verdict, typeof CheckIcon> = {
  supported: CheckIcon,
  not_mentioned: MinusIcon,
  contradicted: CrossIcon,
};

/** One tile per re-asked answer: it made the claim, left it out, or contradicted it. */
function Votes({ verdicts }: { verdicts: Verdict[] }) {
  if (verdicts.length === 0) return null;
  return (
    <div className="votes" aria-hidden="true">
      {verdicts.map((verdict, index) => {
        const VoteIcon = VOTE_ICONS[verdict];
        return (
          <span
            key={index}
            className={`vote vote-${verdict}`}
            style={{ "--i": index } as CSSProperties}
          >
            <VoteIcon />
          </span>
        );
      })}
    </div>
  );
}

function PassageView({ passage, claim }: { passage: Passage; claim: string }) {
  const segments = sharedSegments(claim, passage.text);
  // Each highlighted word waits its turn, counted among the highlighted words only.
  const turns: number[] = [];
  let shared = 0;
  for (const segment of segments) {
    turns.push(shared);
    if (segment.shared) shared += 1;
  }
  return (
    <figure className="passage">
      <blockquote>
        {segments.map((segment, index) =>
          segment.shared ? (
            <mark key={index} style={{ "--i": turns[index] } as CSSProperties}>
              {segment.text}
            </mark>
          ) : (
            <span key={index}>{segment.text}</span>
          ),
        )}
      </blockquote>
      <figcaption>
        <a href={passage.url} target="_blank" rel="noreferrer">
          {passage.source_title}
          <ExternalIcon />
        </a>
        , {passage.section}. Wikipedia, CC BY-SA 4.0. Words shared with the claim are highlighted.
      </figcaption>
    </figure>
  );
}
