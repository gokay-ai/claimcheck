import { describe, expect, it } from "vitest";

import type { Claim, OperatingPoint } from "../api/types";
import {
  countVerdicts,
  describeVerdicts,
  isMarked,
  oneIn,
  percent,
  pointAt,
  sharedSegments,
} from "./marking";

function claim(risk: number): Claim {
  return {
    id: 1,
    text: "A claim.",
    start: 0,
    end: 8,
    risk,
    support: null,
    signals: {
      min_token_probability: null,
      mean_token_probability: null,
      weakest_token: null,
      sample_verdicts: [],
      disagreement: null,
    },
  };
}

const POINTS: OperatingPoint[] = [
  { threshold: 0.2, hit_rate: 0.97, false_alarm_rate: 0.81 },
  { threshold: 0.35, hit_rate: 0.8, false_alarm_rate: 0.38 },
  { threshold: 0.5, hit_rate: 0.43, false_alarm_rate: 0.09 },
];

describe("marking", () => {
  it("marks a claim whose score reaches the threshold", () => {
    expect(isMarked(claim(0.35), 0.35)).toBe(true);
    expect(isMarked(claim(0.34), 0.35)).toBe(false);
  });

  it("finds the measured point nearest to a threshold", () => {
    expect(pointAt(POINTS, 0.35)?.hit_rate).toBe(0.8);
    expect(pointAt(POINTS, 0.46)?.threshold).toBe(0.5);
    expect(pointAt([], 0.35)).toBeNull();
  });

  it("phrases rates for a reader", () => {
    expect(percent(0.381)).toBe("38%");
    expect(oneIn(0.2)).toBe("about 1 in 5");
    expect(oneIn(0.6)).toBe("about 6 in 10");
    expect(oneIn(0)).toBe("none");
  });
});

describe("re-asking", () => {
  it("counts each kind of verdict", () => {
    expect(countVerdicts(["supported", "not_mentioned", "contradicted", "supported"])).toEqual({
      total: 4,
      supported: 2,
      silent: 1,
      contradicted: 1,
    });
  });

  it("describes the verdicts as a sentence", () => {
    expect(describeVerdicts(["supported", "supported"])).toBe(
      "Asked again 2 times, the model made this claim every time.",
    );
    expect(describeVerdicts(["supported", "not_mentioned", "not_mentioned", "contradicted"])).toBe(
      "Asked again 4 times, the model made this claim once, left it out 2 times and contradicted it once.",
    );
    expect(describeVerdicts(["contradicted"])).toBe(
      "Asked again once, the model contradicted it once.",
    );
    expect(describeVerdicts([])).toContain("could not be re-asked");
  });
});

describe("shared words", () => {
  it("flags the passage words that a claim shares, ignoring endings and short words", () => {
    const segments = sharedSegments(
      "Short-term memory holds 3 to 5 items.",
      "The capacity of 7 items has been superseded by 3-5 items in memories.",
    );
    const shared = segments.filter((segment) => segment.shared).map((segment) => segment.text);
    expect(shared).toEqual(["items", "3", "5", "items"]);
    expect(segments.map((segment) => segment.text).join("")).toBe(
      "The capacity of 7 items has been superseded by 3-5 items in memories.",
    );
  });
});
