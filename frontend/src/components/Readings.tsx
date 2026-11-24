import { useEffect, useRef } from "react";

import type { Meta } from "../api/types";
import { ExternalIcon } from "./icons";

/** The full list of readings: what the assistant can and cannot answer from. */
export function Readings({ meta, onClose }: { meta: Meta; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const topics = [...new Set(meta.sources.map((source) => source.topic))];

  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal();
  }, []);

  return (
    <dialog ref={dialog} className="readings" aria-labelledby="readings-heading" onClose={onClose}>
      <div className="readings-top">
        <h2 id="readings-heading">The readings</h2>
        <button type="button" className="ghost-button" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="readings-body">
        <p>
          ClaimCheck answers only from these {meta.sources.length} articles. Each link opens the
          exact version that was used.
        </p>
        <div className="readings-topics">
          {topics.map((topic) => {
            const sources = meta.sources.filter((source) => source.topic === topic);
            return (
              <section key={topic}>
                <h3>
                  {topic}
                  <span aria-hidden="true">{sources.length}</span>
                </h3>
                <ul>
                  {sources.map((source) => (
                    <li key={source.id}>
                      <a href={source.url} target="_blank" rel="noreferrer">
                        {source.title}
                        <ExternalIcon />
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
        <p className="readings-licence">
          Text by Wikipedia contributors, used under{" "}
          <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.
        </p>
      </div>
    </dialog>
  );
}
