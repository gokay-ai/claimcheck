import type { Claim, OperatingPoint, Verdict } from "../api/types";

/** A claim is marked when its check score reaches the threshold. */
export function isMarked(claim: Claim, threshold: number): boolean {
  return claim.risk >= threshold;
}

/** The measured operating point closest to a threshold. */
export function pointAt(points: OperatingPoint[], threshold: number): OperatingPoint | null {
  let best: OperatingPoint | null = null;
  for (const point of points) {
    if (!best || Math.abs(point.threshold - threshold) < Math.abs(best.threshold - threshold)) {
      best = point;
    }
  }
  return best;
}

export function percent(rate: number): string {
  return `${Math.round(rate * 100)}%`;
}

/** "about 1 in 5", for rates a reader should grasp without arithmetic. */
export function oneIn(rate: number): string {
  if (rate <= 0) return "none";
  if (rate >= 0.95) return "nearly all";
  if (rate > 0.5) return `about ${Math.round(rate * 10)} in 10`;
  return `about 1 in ${Math.round(1 / rate)}`;
}

export interface VerdictCounts {
  total: number;
  supported: number;
  silent: number;
  contradicted: number;
}

export function countVerdicts(verdicts: Verdict[]): VerdictCounts {
  return {
    total: verdicts.length,
    supported: verdicts.filter((verdict) => verdict === "supported").length,
    silent: verdicts.filter((verdict) => verdict === "not_mentioned").length,
    contradicted: verdicts.filter((verdict) => verdict === "contradicted").length,
  };
}

function times(count: number): string {
  return count === 1 ? "once" : `${count} times`;
}

/** What re-asking the question showed about a claim, as a sentence. */
export function describeVerdicts(verdicts: Verdict[]): string {
  const counts = countVerdicts(verdicts);
  if (counts.total === 0) {
    return "The question could not be re-asked, so there is no second opinion on this claim.";
  }
  if (counts.supported === counts.total) {
    return `Asked again ${times(counts.total)}, the model made this claim every time.`;
  }
  const parts: string[] = [];
  if (counts.supported > 0) parts.push(`made this claim ${times(counts.supported)}`);
  if (counts.silent > 0) parts.push(`left it out ${times(counts.silent)}`);
  if (counts.contradicted > 0) parts.push(`contradicted it ${times(counts.contradicted)}`);
  const last = parts.pop() ?? "";
  const list = parts.length > 0 ? `${parts.join(", ")} and ${last}` : last;
  return `Asked again ${times(counts.total)}, the model ${list}.`;
}

const COMMON = new Set(
  (
    "about above after again also another because been before being between both could does " +
    "doing down during each from further have having here into itself just more most only " +
    "other over same should some such than that their them then there these they this those " +
    "through under until very were what when where which while will with would your"
  ).split(" "),
);

function stem(word: string): string {
  for (const suffix of ["ing", "ed", "es", "s"]) {
    if (word.endsWith(suffix) && word.length - suffix.length >= 4) {
      return word.slice(0, -suffix.length);
    }
  }
  return word;
}

function contentStems(text: string): Set<string> {
  const stems = new Set<string>();
  for (const word of text.toLowerCase().match(/[a-z0-9]+/g) ?? []) {
    if ((word.length >= 4 || /\d/.test(word)) && !COMMON.has(word)) stems.add(stem(word));
  }
  return stems;
}

export interface Segment {
  text: string;
  shared: boolean;
}

/**
 * Split a passage into runs of text, flagging the words it shares with a claim.
 * Showing the overlap lets a reader compare the two without rereading both.
 */
export function sharedSegments(claim: string, passage: string): Segment[] {
  const wanted = contentStems(claim);
  const segments: Segment[] = [];
  for (const piece of passage.split(/([A-Za-z0-9]+)/)) {
    if (!piece) continue;
    const word = piece.toLowerCase();
    const shared =
      /^[a-z0-9]+$/.test(word) && (word.length >= 4 || /\d/.test(word)) && wanted.has(stem(word));
    const previous = segments[segments.length - 1];
    if (previous && previous.shared === shared) {
      previous.text += piece;
    } else {
      segments.push({ text: piece, shared });
    }
  }
  return segments;
}
