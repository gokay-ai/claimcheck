// Mirrors backend/src/claimcheck/schemas.py.

export type Stage = "retrieving" | "answering" | "checking";
export type Verdict = "supported" | "contradicted" | "not_mentioned";
export type Mode = "live" | "replay";

export interface Passage {
  id: string;
  source_id: string;
  source_title: string;
  section: string;
  text: string;
  url: string;
}

export interface Source {
  id: string;
  title: string;
  topic: string;
  url: string;
  publisher: string;
  licence: string;
  licence_url: string;
  passages: number;
}

export interface ClaimSignals {
  min_token_probability: number | null;
  mean_token_probability: number | null;
  weakest_token: string | null;
  sample_verdicts: Verdict[];
  disagreement: number | null;
}

export interface ClaimSupport {
  passage_id: string;
  overlap: number;
}

export interface Claim {
  id: number;
  text: string;
  start: number;
  end: number;
  signals: ClaimSignals;
  risk: number;
  support: ClaimSupport | null;
}

export interface AskResult {
  id: string;
  question: string;
  mode: Mode;
  status: "answered" | "not_covered";
  answer: string;
  claims: Claim[];
  passages: Passage[];
  context_passage_ids: string[];
  model: string;
  samples: number;
}

export interface OperatingPoint {
  threshold: number;
  hit_rate: number;
  false_alarm_rate: number;
}

export interface Calibration {
  signal: string;
  default_threshold: number;
  points: OperatingPoint[];
  claims: number;
  wrong_claims: number;
  auc: number | null;
  basis: string;
}

export interface Example {
  question: string;
  topic: string;
}

export interface Meta {
  version: string;
  mode: Mode;
  model: string;
  samples: number;
  sources: Source[];
  examples: Example[];
  calibration: Calibration;
  max_question_chars: number;
}

export type ErrorCode =
  "rate_limited" | "model_unavailable" | "not_recorded" | "invalid_question" | "network";

export interface AskError {
  code: ErrorCode;
  message: string;
  retry_after_seconds?: number | null;
}

export type AskEvent =
  | { type: "stage"; stage: Stage }
  | { type: "result"; result: AskResult }
  | ({ type: "error" } & AskError);
