import { expect, test, type Locator, type Page } from "@playwright/test";

// Each test is one storyboard from the project report. It checks the
// interaction and, when SCREENSHOTS is set, saves the frames the report uses.
const SHOTS = process.env.SCREENSHOTS ? "../docs/storyboards" : null;

// A tall, fairly narrow window keeps each frame whole and its text large in print.
// A frame is measured and then captured, so nothing may be mid-animation while it
// is measured: with motion reduced, every state appears at once in its final form.
if (SHOTS) {
  test.use({ viewport: { width: 960, height: 1320 }, contextOptions: { reducedMotion: "reduce" } });
}

/** Save one frame: the given part of the page, or the whole window. */
async function frame(page: Page, name: string, part?: Locator, maxHeight?: number, pad = 4) {
  if (!SHOTS) return;
  const path = `${SHOTS}/${name}.png`;
  // The pointer rests wherever the last click was; park it so that no element
  // is drawn in its hover state.
  await page.mouse.move(0, 0);
  if (!part) {
    await page.screenshot({ path, animations: "disabled" });
    return;
  }
  await part.scrollIntoViewIfNeeded();
  const box = await part.boundingBox();
  if (!box) throw new Error(`Nothing to capture for ${name}`);
  const height = maxHeight ? Math.min(box.height, maxHeight) : box.height;
  await page.screenshot({
    path,
    animations: "disabled",
    clip: { x: box.x - pad, y: box.y - pad, width: box.width + 2 * pad, height: height + 2 * pad },
  });
}

test("A: a student checks a marked claim against the reading", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Recorded demo", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "What is automation bias?" })).toBeVisible();
  await frame(page, "a1-ask", page.locator(".ask"));

  await page.getByRole("button", { name: "How many items can short-term memory hold?" }).click();
  await expect(page.getByText("Writing an answer from those passages")).toBeVisible();
  await frame(page, "a2-progress", page.locator(".progress"));

  await expect(page.getByTestId("summary")).toContainText("1 of 3 claims marked to check");
  await expect(page.getByRole("heading", { name: "Answer" })).toBeFocused();
  await expect(page.getByTestId("claim-3")).toHaveAttribute("data-marked", "true");
  await expect(page.getByTestId("claim-1")).toHaveAttribute("data-marked", "false");
  await frame(page, "a3-answer", page.locator(".answer"));

  await page.getByTestId("claim-3").click();
  await expect(page.getByRole("heading", { name: "Why it is marked" })).toBeVisible();
  await expect(page.getByText("left it out 2 times")).toBeVisible();
  await expect(page.getByRole("link", { name: "Short-term memory" })).toHaveAttribute(
    "href",
    /oldid=\d+/,
  );
  await frame(page, "overview");
  await frame(page, "a4-check", page.locator(".panel"), 720);

  await page.getByRole("button", { name: "Matches the reading" }).click();
  await expect(page.getByTestId("claim-3")).toContainText("Checked");
  await expect(page.getByTestId("summary")).toContainText("You have checked 1 of 1");
  // No margin here: the buttons sit over the scrolling passage, which a margin would show.
  await frame(page, "a5-record", page.locator(".verdict"), undefined, 0);
  await frame(page, "a6-checked", page.locator(".answer"), 560);

  // The finding can be undone with the same button.
  await page.getByRole("button", { name: "Matches the reading" }).click();
  await expect(page.getByTestId("claim-3")).not.toContainText("Checked");
});

test("B: marking more, and catching an error the marks missed", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("button", {
      name: "When is the best time to review material so that you remember it?",
    })
    .click();
  await expect(page.getByTestId("summary")).toContainText("1 of 4 claims marked to check");
  await expect(page.getByTestId("threshold-effect")).toContainText("80%");
  await frame(page, "b1-answer", page.locator(".answer"));

  // Three steps towards "Mark more" lowers the threshold from 0.35 to 0.20.
  const slider = page.getByRole("slider", { name: "How much to mark" });
  await slider.focus();
  for (let step = 0; step < 3; step += 1) await slider.press("ArrowRight");
  await expect(page.getByTestId("summary")).toContainText("3 of 4 claims marked to check");
  await expect(page.getByTestId("threshold-effect")).toContainText("97%");
  await expect(page.getByTestId("threshold-effect")).toContainText("81%");
  await frame(page, "b2-mark-more", page.locator(".answer"));

  // The first claim stays unmarked, yet the passage shows it overstates the reading.
  await expect(page.getByTestId("claim-1")).toHaveAttribute("data-marked", "false");
  await page.getByTestId("claim-1").click();
  await expect(page.getByRole("heading", { name: "Why it is not marked" })).toBeVisible();
  await expect(page.getByText("Some learning consultants claim")).toBeVisible();
  await frame(page, "b3-unmarked-claim", page.locator(".panel"), 1010);

  await page.getByRole("button", { name: "Does not match" }).click();
  await expect(page.getByTestId("claim-1")).toContainText("Does not match");
  await frame(page, "b4-corrected", page.locator(".answer"), 560);

  await page.getByRole("button", { name: "Reset to default" }).click();
  await expect(page.getByTestId("summary")).toContainText("1 of 4 claims marked to check");
});

test("C: a question outside the readings is declined", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your question").fill("What is the capital of Australia?");
  await frame(page, "c1-typed", page.locator(".ask-top"));
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("heading", { name: "The readings do not cover this" })).toBeFocused();
  await expect(page.getByText("It has not answered from memory")).toBeVisible();
  await frame(page, "c2-declined", page.locator(".notice"));

  await page.getByRole("button", { name: "See all 19 readings" }).click();
  await expect(page.getByRole("heading", { name: "The readings", exact: true })).toBeVisible();
  await frame(page, "c3-readings", page.locator(".readings"));
  await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();

  await page
    .getByRole("region", { name: "The readings do not cover this" })
    .getByRole("button", { name: "What is inattentional blindness?" })
    .click();
  await expect(page.getByTestId("summary")).toContainText("claims marked to check");
  await frame(page, "c4-recovered", page.locator(".answer"), 520);
});

test("the recorded demo says so when a question was not recorded", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Your question").fill("What is cognitive load?");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "That question is not in the recorded demo" }),
  ).toBeVisible();
});
