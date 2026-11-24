import { useCallback, useEffect, useRef, useState } from "react";

import { ask, fetchMeta } from "./api/client";
import type { AskError, AskResult, Meta, Stage } from "./api/types";
import { AnswerCard } from "./components/AnswerCard";
import { AskForm } from "./components/AskForm";
import { CheckPanel } from "./components/CheckPanel";
import { BookIcon, Logo } from "./components/icons";
import { ErrorNotice, NotCovered } from "./components/Notices";
import { Progress } from "./components/Progress";
import { Readings } from "./components/Readings";
import { isMarked } from "./lib/marking";

export type Check = "matches" | "differs";

type Phase =
  | { kind: "idle" }
  | { kind: "asking"; question: string; stage: Stage | null }
  | { kind: "answered"; result: AskResult }
  | { kind: "not_covered"; question: string }
  | { kind: "error"; question: string; error: AskError };

const NETWORK_ERROR: AskError = {
  code: "network",
  message: "ClaimCheck could not reach its server. Nothing was answered.",
};

export function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaFailed, setMetaFailed] = useState(false);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [draft, setDraft] = useState("");
  const [threshold, setThreshold] = useState(0.35);
  const [selected, setSelected] = useState<number | null>(null);
  const [checks, setChecks] = useState<Record<number, Check>>({});
  const [showReadings, setShowReadings] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const request = useRef<AbortController | null>(null);
  const resultHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchMeta(controller.signal)
      .then((loaded) => {
        setMeta(loaded);
        setThreshold(loaded.calibration.default_threshold);
      })
      .catch(() => {
        if (!controller.signal.aborted) setMetaFailed(true);
      });
    return () => controller.abort();
  }, []);

  const submit = useCallback(
    async (question: string) => {
      request.current?.abort();
      const controller = new AbortController();
      request.current = controller;
      // The box keeps showing the question that the answer below belongs to.
      setDraft(question);
      setSelected(null);
      setChecks({});
      setPhase({ kind: "asking", question, stage: null });
      setAnnouncement("");
      let settled = false;
      try {
        await ask(
          question,
          (event) => {
            if (controller.signal.aborted) return;
            if (event.type === "stage") {
              setPhase({ kind: "asking", question, stage: event.stage });
            } else if (event.type === "result") {
              settled = true;
              if (event.result.status === "not_covered") {
                setPhase({ kind: "not_covered", question });
                setAnnouncement("The readings do not cover this question. Nothing was answered.");
              } else {
                const marked = event.result.claims.filter((claim) =>
                  isMarked(claim, threshold),
                ).length;
                setPhase({ kind: "answered", result: event.result });
                setAnnouncement(
                  `Answer ready. ${marked} of ${event.result.claims.length} claims marked to check.`,
                );
              }
            } else {
              settled = true;
              setPhase({ kind: "error", question, error: event });
              setAnnouncement(event.message);
            }
          },
          controller.signal,
        );
        if (!settled && !controller.signal.aborted) {
          setPhase({ kind: "error", question, error: NETWORK_ERROR });
        }
      } catch {
        if (!controller.signal.aborted) {
          setPhase({ kind: "error", question, error: NETWORK_ERROR });
          setAnnouncement(NETWORK_ERROR.message);
        }
      }
    },
    [threshold],
  );

  // Move focus to the outcome, so keyboard and screen-reader users land on it.
  const outcome = phase.kind === "answered" ? phase.result.id : phase.kind;
  useEffect(() => {
    if (phase.kind !== "idle" && phase.kind !== "asking") resultHeading.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [outcome]);


  const setCheck = (claimId: number, check: Check | null) => {
    setChecks((current) => {
      const others = Object.entries(current).filter(([id]) => Number(id) !== claimId);
      const next: Record<number, Check> = Object.fromEntries(others);
      if (check !== null) next[claimId] = check;
      return next;
    });
  };

  if (metaFailed) {
    return (
      <div className="page">
        <Header mode={null} onReadings={null} />
        <main className="column">
          <ErrorNotice
            headingRef={resultHeading}
            error={NETWORK_ERROR}
            onRetry={() => window.location.reload()}
            retryLabel="Reload the page"
          />
        </main>
      </div>
    );
  }

  const result = phase.kind === "answered" ? phase.result : null;
  const selectedClaim = result?.claims.find((claim) => claim.id === selected) ?? null;

  return (
    <div className="page">
      <Header mode={meta} onReadings={meta ? () => setShowReadings(true) : null} />
      <main className="column">
        <AskForm
          meta={meta}
          busy={phase.kind === "asking"}
          compact={phase.kind !== "idle"}
          offerExamples={phase.kind === "error" && phase.error.code === "not_recorded"}
          question={draft}
          onQuestion={setDraft}
          onAsk={submit}
        />

        <p className="visually-hidden" role="status" aria-live="polite">
          {announcement}
        </p>

        {phase.kind === "asking" && (
          <Progress stage={phase.stage} samples={meta?.samples ?? 4} question={phase.question} />
        )}

        {phase.kind === "not_covered" && meta && (
          <NotCovered
            headingRef={resultHeading}
            question={phase.question}
            meta={meta}
            onAsk={submit}
            onReadings={() => setShowReadings(true)}
          />
        )}

        {phase.kind === "error" && (
          <ErrorNotice
            headingRef={resultHeading}
            error={phase.error}
            onRetry={phase.error.code === "not_recorded" ? null : () => submit(phase.question)}
            retryLabel="Ask again"
          />
        )}

        {result && meta && (
          <div className="result">
            <AnswerCard
              key={result.id}
              headingRef={resultHeading}
              result={result}
              calibration={meta.calibration}
              threshold={threshold}
              onThreshold={setThreshold}
              selected={selected}
              onSelect={setSelected}
              checks={checks}
            />
            <CheckPanel
              result={result}
              claim={selectedClaim}
              threshold={threshold}
              check={selectedClaim ? (checks[selectedClaim.id] ?? null) : null}
              onCheck={(check) => selectedClaim && setCheck(selectedClaim.id, check)}
              onClose={() => setSelected(null)}
            />
          </div>
        )}
      </main>

      <footer className="footer">
        <div className="column footer-row">
          <p>
            ClaimCheck is a coursework prototype. Questions are not stored, and your checks stay in
            this browser tab.
          </p>
          <p>
            Readings are Wikipedia articles, used under{" "}
            <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.
          </p>
        </div>
      </footer>

      {showReadings && meta && <Readings meta={meta} onClose={() => setShowReadings(false)} />}
    </div>
  );
}

function Header({ mode, onReadings }: { mode: Meta | null; onReadings: (() => void) | null }) {
  return (
    <header className="header">
      <div className="column header-row">
        <p className="wordmark">
          <Logo />
          ClaimCheck
        </p>
        <div className="header-side">
          {mode && (
            <span className={`badge badge-${mode.mode}`}>
              <span className="badge-dot" aria-hidden="true" />
              {mode.mode === "live" ? "Live model" : "Recorded demo"}
            </span>
          )}
          {onReadings && (
            <button type="button" className="ghost-button" onClick={onReadings}>
              <BookIcon />
              {mode ? (
                <span>
                  {mode.sources.length}
                  <span className="narrow-hidden"> readings</span>
                </span>
              ) : (
                "Readings"
              )}
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
