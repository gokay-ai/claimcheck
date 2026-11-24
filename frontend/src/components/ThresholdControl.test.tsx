import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Calibration } from "../api/types";
import { ThresholdControl } from "./ThresholdControl";

const calibration: Calibration = {
  signal: "combined",
  default_threshold: 0.35,
  claims: 261,
  wrong_claims: 35,
  auc: 0.76,
  basis: "pilot test",
  points: [
    { threshold: 0.2, hit_rate: 0.971, false_alarm_rate: 0.81 },
    { threshold: 0.35, hit_rate: 0.8, false_alarm_rate: 0.381 },
    { threshold: 0.5, hit_rate: 0.429, false_alarm_rate: 0.088 },
  ],
};

describe("ThresholdControl", () => {
  it("states what the current setting cost in the pilot test", () => {
    render(<ThresholdControl calibration={calibration} threshold={0.35} onChange={vi.fn()} />);
    expect(screen.getByTestId("threshold-effect")).toHaveTextContent(
      "caught 80% of wrong claims in the pilot test and also marked 38% of correct ones",
    );
    expect(screen.getByRole("button", { name: "Reset to default" })).toBeDisabled();
  });

  it("lowers the threshold when the slider moves towards marking more", () => {
    const onChange = vi.fn();
    render(<ThresholdControl calibration={calibration} threshold={0.35} onChange={onChange} />);
    const slider = screen.getByRole("slider", { name: "How much to mark" });
    expect(slider).toHaveAttribute("aria-valuetext", "Marks claims that score 0.35 or more");
    fireEvent.change(slider, { target: { value: "50" } });
    expect(onChange).toHaveBeenCalledWith(0.2);
  });

  it("offers a way back to the default", () => {
    const onChange = vi.fn();
    render(<ThresholdControl calibration={calibration} threshold={0.2} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Reset to default" }));
    expect(onChange).toHaveBeenCalledWith(0.35);
  });
});
