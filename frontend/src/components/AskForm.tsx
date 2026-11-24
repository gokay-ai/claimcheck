import { useState, type CSSProperties, type FormEvent } from "react";

import type { Meta } from "../api/types";
import { ArrowRightIcon, ChevronDownIcon, SearchIcon, SpinnerIcon } from "./icons";

interface Props {
  meta: Meta | null;
  busy: boolean;
  /** Once a question has been asked, the introduction and examples fold away to keep the answer in view. */
  compact: boolean;
  /** Open the examples even when compact, for when the next step is to pick one. */
  offerExamples: boolean;
  question: string;
  onQuestion: (question: string) => void;
  onAsk: (question: string) => void;
}

export function AskForm({
  meta,
  busy,
  compact,
  offerExamples,
  question,
  onQuestion,
  onAsk,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const replay = meta?.mode === "replay";
  const examples = meta?.examples ?? [];
  const topics = [...new Set(examples.map((example) => example.topic))];
  const examplesOpen = !compact || expanded || offerExamples;

  const ask = (text: string) => {
    setExpanded(false);
    onAsk(text);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = question.trim();
    if (trimmed && !busy) ask(trimmed);
  };

  return (
    <section
      className={`ask ${compact ? "ask-compact" : "ask-hero"}`}
      aria-labelledby="ask-heading"
    >
      <div className="ask-top">
        {/* Folded by height, not removed, so the page keeps its main heading. */}
        <div className="collapse" data-open={!compact}>
          <div>
            <div className="ask-intro">
              <p className="eyebrow">
                Study assistant{meta ? ` · ${meta.sources.length} readings` : ""}
              </p>
              <h1 id="ask-heading" className="hero-title">
                Which claims should you <span className="hero-mark">check</span>?
              </h1>
              <p className="lede">
                Ask about the readings. ClaimCheck answers from them and marks the claims with the
                most reason for doubt, so you know where to look first.
              </p>
            </div>
          </div>
        </div>

        <form onSubmit={submit} className="ask-form">
          <label htmlFor="question" className="visually-hidden">
            Your question
          </label>
          <div className="ask-field">
            <SearchIcon />
            <input
              id="question"
              type="text"
              value={question}
              maxLength={meta?.max_question_chars ?? 300}
              onChange={(event) => onQuestion(event.target.value)}
              placeholder={
                replay
                  ? "Choose an example question below"
                  : "For example: what is automation bias?"
              }
              autoComplete="off"
              enterKeyHint="search"
            />
            <button
              type="submit"
              className="primary ask-button"
              disabled={busy || !question.trim()}
            >
              {busy ? (
                <>
                  <SpinnerIcon />
                  Working…
                </>
              ) : (
                <>
                  Ask
                  <ArrowRightIcon />
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {examples.length > 0 && (
        <div className="ask-more">
          {compact && !offerExamples && (
            <button
              type="button"
              className="examples-toggle"
              aria-expanded={expanded}
              aria-controls="examples"
              onClick={() => setExpanded((open) => !open)}
            >
              Example questions
              <ChevronDownIcon />
            </button>
          )}
          <div
            id="examples"
            className="collapse collapse-hides"
            data-open={examplesOpen}
            inert={!examplesOpen}
          >
            <div>
              <section aria-label="Example questions" className="card examples-wrap">
                {replay && (
                  <p className="hint">
                    This is the recorded demo. It replays real answers to the questions below, so it
                    needs no model key; other questions need the live version.
                  </p>
                )}
                {/* Offering questions to pick from spares the student from guessing what
                    the readings cover; a blank box alone would leave that to recall. */}
                <div className="examples">
                  {topics.map((topic) => (
                    <div key={topic} className="example-group">
                      <p className="eyebrow">{topic}</p>
                      <ul>
                        {examples
                          .filter((example) => example.topic === topic)
                          .map((example) => (
                            <li
                              key={example.question}
                              style={{ "--i": examples.indexOf(example) } as CSSProperties}
                            >
                              <button
                                type="button"
                                className="chip"
                                disabled={busy}
                                onClick={() => ask(example.question)}
                              >
                                {example.question}
                                <ArrowRightIcon />
                              </button>
                            </li>
                          ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
