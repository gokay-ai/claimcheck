import type { CSSProperties } from "react";

import type { Stage } from "../api/types";
import { CheckIcon } from "./icons";

const ORDER: Stage[] = ["retrieving", "answering", "checking"];

interface Props {
  stage: Stage | null;
  samples: number;
  question: string;
}

/**
 * Shows the three steps as they happen. The answer is held back until the
 * checks are done, so the first thing a student reads already carries its marks.
 */
export function Progress({ stage, samples, question }: Props) {
  const labels: Record<Stage, string> = {
    retrieving: "Finding passages in the readings",
    answering: "Writing an answer from those passages",
    checking: `Asking again ${samples} times to see which claims hold up`,
  };
  const current = stage ? ORDER.indexOf(stage) : -1;

  return (
    <section className="card progress" aria-label="Working on your question">
      <p className="progress-question">“{question}”</p>
      <ol role="status" aria-live="polite" className="steps">
        {ORDER.map((step, index) => {
          const state = index < current ? "done" : index === current ? "current" : "pending";
          return (
            <li key={step} className={`step step-${state}`}>
              <span className="step-node" aria-hidden="true">
                {state === "done" ? <CheckIcon /> : index + 1}
              </span>
              <span className="step-body">
                {labels[step]}
                {state === "current" && <span className="visually-hidden"> (in progress)</span>}
                {state === "done" && <span className="visually-hidden"> (done)</span>}
                {state === "current" && step === "checking" && (
                  <span className="reasks" aria-hidden="true">
                    {Array.from({ length: samples }, (_, sample) => (
                      <span key={sample} style={{ "--i": sample } as CSSProperties} />
                    ))}
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ol>
      <div className="held">
        <div className="held-lines" aria-hidden="true">
          <span className="skeleton" style={{ width: "94%" }} />
          <span className="skeleton" style={{ width: "81%" }} />
          <span className="skeleton" style={{ width: "62%" }} />
        </div>
        <p className="held-note">
          The answer is shown once it has been checked, so its marks are there from the first
          reading.
        </p>
      </div>
    </section>
  );
}
