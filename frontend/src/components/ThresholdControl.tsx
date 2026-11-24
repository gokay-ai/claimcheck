import type { CSSProperties } from "react";

import type { Calibration } from "../api/types";
import { percent, pointAt } from "../lib/marking";

interface Props {
  calibration: Calibration;
  threshold: number;
  onChange: (threshold: number) => void;
}

/**
 * Lets the student move the marking threshold and shows what each setting cost
 * in the pilot test. A threshold trades missed errors for needless checks; the
 * control makes that trade visible instead of fixing it out of sight.
 */
export function ThresholdControl({ calibration, threshold, onChange }: Props) {
  const thresholds = calibration.points.map((point) => point.threshold);
  const lowest = Math.min(...thresholds);
  const highest = Math.max(...thresholds);
  const point = pointAt(calibration.points, threshold);
  const isDefault = Math.abs(threshold - calibration.default_threshold) < 0.001;

  // The slider runs from "mark fewer" to "mark more", the reverse of the threshold.
  const position = Math.round((highest + lowest - threshold) * 100);
  const span = highest - lowest || 1;
  const scale = {
    "--fill": (highest - threshold) / span,
    "--default": (highest - calibration.default_threshold) / span,
  } as CSSProperties;

  return (
    <div className="threshold">
      <div className="threshold-head">
        <label htmlFor="threshold">How much to mark</label>
        <button
          type="button"
          className="link-button"
          disabled={isDefault}
          onClick={() => onChange(calibration.default_threshold)}
        >
          Reset to default
        </button>
      </div>
      <div className="threshold-slider">
        <span aria-hidden="true">Mark fewer</span>
        <div className="range" style={scale}>
          <input
            id="threshold"
            type="range"
            min={Math.round(lowest * 100)}
            max={Math.round(highest * 100)}
            step={5}
            value={position}
            aria-valuetext={`Marks claims that score ${threshold.toFixed(2)} or more`}
            onChange={(event) => {
              const next =
                (Math.round((highest + lowest) * 100) - Number(event.target.value)) / 100;
              onChange(Math.round(next * 100) / 100);
            }}
          />
          <span className="range-default" aria-hidden="true">
            default
          </span>
        </div>
        <span aria-hidden="true">Mark more</span>
      </div>
      {point && (
        <>
          {/* The same two rates as the sentence below, drawn so that their
              moving together can be seen while the slider is dragged. */}
          <div className="tradeoff" aria-hidden="true">
            <Rate kind="hit" label="Wrong claims caught" value={point.hit_rate} />
            <Rate kind="alarm" label="Correct claims also marked" value={point.false_alarm_rate} />
          </div>
          <p className="threshold-effect" data-testid="threshold-effect">
            At this setting, the marks caught <strong>{percent(point.hit_rate)}</strong> of wrong
            claims in the pilot test and also marked{" "}
            <strong>{percent(point.false_alarm_rate)}</strong> of correct ones.
          </p>
        </>
      )}
      <details className="threshold-basis">
        <summary>Where these numbers come from</summary>
        <p>
          A {calibration.basis}: {calibration.claims} claims, of which {calibration.wrong_claims}{" "}
          were wrong when compared with the readings. The labels were made by a second model and
          have not all been checked by hand, so treat the percentages as rough.
        </p>
      </details>
    </div>
  );
}

function Rate({ kind, label, value }: { kind: "hit" | "alarm"; label: string; value: number }) {
  return (
    <div className={`bar-row bar-${kind}`}>
      <span>{label}</span>
      <span className="bar-track">
        <span className="bar-fill" style={{ "--v": value } as CSSProperties} />
      </span>
      <span className="bar-value">{percent(value)}</span>
    </div>
  );
}
