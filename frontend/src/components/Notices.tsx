import type { CSSProperties, RefObject } from "react";

import type { AskError, Meta } from "../api/types";
import { AlertIcon, ArrowRightIcon, BookIcon, CompassIcon } from "./icons";

interface NotCoveredProps {
  headingRef: RefObject<HTMLHeadingElement | null>;
  question: string;
  meta: Meta;
  onAsk: (question: string) => void;
  onReadings: () => void;
}

/** The decline turn: say what was not done, why, and what can be asked instead. */
export function NotCovered({ headingRef, question, meta, onAsk, onReadings }: NotCoveredProps) {
  const topics = [...new Set(meta.sources.map((source) => source.topic))];
  const suggestions = meta.examples.filter((example) => topics.includes(example.topic)).slice(0, 3);

  return (
    <section className="card notice" aria-labelledby="notice-heading">
      <span className="notice-icon" aria-hidden="true">
        <CompassIcon />
      </span>
      <div className="notice-body">
        <h2 id="notice-heading" ref={headingRef} tabIndex={-1}>
          The readings do not cover this
        </h2>
        <p>
          ClaimCheck answers only from its {meta.sources.length} readings, and none of them answers
          “{question}”. It has not answered from memory, because there would be no passage to check
          the answer against.
        </p>
        <p>The readings cover {joinTopics(topics)}. You could ask:</p>
        <ul className="suggestions">
          {suggestions.map((example, index) => (
            <li key={example.question} style={{ "--i": index } as CSSProperties}>
              <button type="button" className="chip" onClick={() => onAsk(example.question)}>
                {example.question}
                <ArrowRightIcon />
              </button>
            </li>
          ))}
        </ul>
        <button type="button" className="ghost-button" onClick={onReadings}>
          <BookIcon />
          See all {meta.sources.length} readings
        </button>
      </div>
    </section>
  );
}

function joinTopics(topics: string[]): string {
  const lowered = topics.map((topic) => topic.toLowerCase());
  const last = lowered.pop();
  return lowered.length > 0 ? `${lowered.join(", ")} and ${last}` : (last ?? "");
}

interface ErrorProps {
  headingRef: RefObject<HTMLHeadingElement | null>;
  error: AskError;
  onRetry: (() => void) | null;
  retryLabel: string;
}

const TITLES: Record<AskError["code"], string> = {
  rate_limited: "The demo has reached its limit for now",
  model_unavailable: "The model gave no answer that could be scored",
  not_recorded: "That question is not in the recorded demo",
  invalid_question: "That question cannot be asked",
  network: "ClaimCheck could not reach its server",
};

function waitText(seconds: number): string {
  if (seconds < 90) return "about a minute";
  if (seconds < 3600) return `about ${Math.round(seconds / 60)} minutes`;
  return `about ${Math.round(seconds / 3600)} hours`;
}

export function ErrorNotice({ headingRef, error, onRetry, retryLabel }: ErrorProps) {
  return (
    <section className="card notice notice-error" aria-labelledby="notice-heading">
      <span className="notice-icon" aria-hidden="true">
        <AlertIcon />
      </span>
      <div className="notice-body">
        <h2 id="notice-heading" ref={headingRef} tabIndex={-1}>
          {TITLES[error.code]}
        </h2>
        <p>{error.message}</p>
        {error.code === "rate_limited" && (
          <p>
            The demo shares one model key, so questions are limited.
            {error.retry_after_seconds
              ? ` You can ask again in ${waitText(error.retry_after_seconds)}.`
              : ""}
          </p>
        )}
        {error.code === "not_recorded" && <p>Choose one of the example questions above.</p>}
        {onRetry && error.code !== "rate_limited" && (
          <button type="button" className="primary" onClick={onRetry}>
            {retryLabel}
          </button>
        )}
      </div>
    </section>
  );
}
