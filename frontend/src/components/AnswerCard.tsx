import { useEffect, useState, type CSSProperties, type RefObject } from "react";

import type { Check } from "../App";
import type { AskResult, Calibration, Claim } from "../api/types";
import { isMarked, oneIn, pointAt } from "../lib/marking";
import { CheckIcon, ChevronRightIcon, CrossIcon, InfoIcon } from "./icons";
import { ThresholdControl } from "./ThresholdControl";

// Long enough for the last claim of an answer to finish arriving.
const ENTRANCE_MS = 1100;

interface Props {
  headingRef: RefObject<HTMLHeadingElement | null>;
  result: AskResult;
  calibration: Calibration;
  threshold: number;
  onThreshold: (threshold: number) => void;
  selected: number | null;
  onSelect: (claimId: number) => void;
  checks: Record<number, Check>;
}

export function AnswerCard({
  headingRef,
  result,
  calibration,
  threshold,
  onThreshold,
  selected,
  onSelect,
  checks,
}: Props) {
  const marked = result.claims.filter((claim) => isMarked(claim, threshold));
  const checkedMarked = marked.filter((claim) => checks[claim.id]).length;
  const point = pointAt(calibration.points, threshold);
  const missRate = point ? 1 - point.hit_rate : null;

  // Claims arrive one after another. Once they are in, a change of threshold
  // must re-mark them at once, so the staggered delay is dropped.
  const [entered, setEntered] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setEntered(true), ENTRANCE_MS);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <section className="card answer" aria-labelledby="answer-heading">
      <div className="answer-top">
        <h2 id="answer-heading" ref={headingRef} tabIndex={-1}>
          Answer
        </h2>
        <span className="answer-source">
          {result.mode === "replay" ? "Recorded answer" : "Live answer"} · written from{" "}
          {result.context_passage_ids.length} passages
        </span>
      </div>

      <div className="answer-summary-row">
        <MarkRing marked={marked.length} checked={checkedMarked} />
        <p className="answer-summary" data-testid="summary">
          <strong>
            {marked.length} of {result.claims.length} claims marked to check.
          </strong>{" "}
          {marked.length > 0 && checkedMarked > 0 && (
            <span>
              You have checked {checkedMarked} of {marked.length}.{" "}
            </span>
          )}
          Select any claim to see why, and the passage to check it against.
        </p>
      </div>

      <ol className={entered ? "claims claims-entered" : "claims"}>
        {result.claims.map((claim, index) => (
          <li key={claim.id} style={{ "--i": index } as CSSProperties}>
            <ClaimRow
              claim={claim}
              marked={isMarked(claim, threshold)}
              selected={selected === claim.id}
              check={checks[claim.id] ?? null}
              onSelect={() => onSelect(claim.id)}
            />
          </li>
        ))}
      </ol>

      <p className="caution">
        <InfoIcon />
        <span>
          <strong>Unmarked does not mean correct.</strong>{" "}
          {missRate !== null && missRate > 0
            ? `At this setting the marks missed ${oneIn(missRate)} wrong claims in the pilot test.`
            : "The marks point to where checking is most likely to pay off."}
        </span>
      </p>

      <ThresholdControl calibration={calibration} threshold={threshold} onChange={onThreshold} />
    </section>
  );
}

/**
 * How many marked claims are still to check, inside a ring that fills as they
 * are checked. The sentence beside it says the same in words.
 */
function MarkRing({ marked, checked }: { marked: number; checked: number }) {
  const left = marked - checked;
  const done = marked > 0 && left === 0;
  const state = marked === 0 ? "ring ring-none" : done ? "ring ring-done" : "ring";
  const share = marked === 0 ? 0 : checked / marked;

  return (
    <div className={state} aria-hidden="true" style={{ "--done": share } as CSSProperties}>
      <svg viewBox="0 0 36 36" fill="none" strokeWidth={3.5} strokeLinecap="round">
        <circle className="ring-track" cx="18" cy="18" r="15" />
        <circle className="ring-value" cx="18" cy="18" r="15" pathLength={1} />
      </svg>
      <span key={done ? "done" : left} className="ring-label">
        {done ? <CheckIcon /> : left}
      </span>
    </div>
  );
}

interface RowProps {
  claim: Claim;
  marked: boolean;
  selected: boolean;
  check: Check | null;
  onSelect: () => void;
}

function ClaimRow({ claim, marked, selected, check, onSelect }: RowProps) {
  const classes = ["claim"];
  if (marked) classes.push("claim-marked");
  if (selected) classes.push("claim-selected");
  if (check) classes.push(`claim-${check}`);

  return (
    <button
      type="button"
      className={classes.join(" ")}
      aria-pressed={selected}
      data-testid={`claim-${claim.id}`}
      data-marked={marked}
      onClick={onSelect}
    >
      <span className="claim-num" aria-hidden="true">
        {claim.id}
      </span>
      <span className="claim-main">
        {check === "matches" && (
          <span className="tag tag-ok">
            <CheckIcon />
            Checked
          </span>
        )}
        {check === "differs" && (
          <span className="tag tag-bad">
            <CrossIcon />
            Does not match
          </span>
        )}
        {!check && marked && <span className="tag tag-check">Check</span>}
        {!check && !marked && <span className="visually-hidden">Not marked</span>}
        <span className="claim-text">{claim.text}</span>
      </span>
      <ChevronRightIcon className="claim-go" />
    </button>
  );
}
