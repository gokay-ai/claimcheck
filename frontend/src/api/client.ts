import type { AskEvent, Meta } from "./types";

export async function fetchMeta(signal?: AbortSignal): Promise<Meta> {
  const response = await fetch("/api/meta", { signal });
  if (!response.ok) {
    throw new Error(`The server answered ${response.status}.`);
  }
  return (await response.json()) as Meta;
}

function parseEvent(line: string): AskEvent | null {
  try {
    const value: unknown = JSON.parse(line);
    if (typeof value === "object" && value !== null && "type" in value) {
      return value as AskEvent;
    }
  } catch {
    // A line that is not JSON is dropped; the stream ends with a result or an error.
  }
  return null;
}

/**
 * Ask a question and report each event as the server writes it.
 *
 * The server streams one JSON object per line, so the progress display can
 * follow the work instead of waiting for the finished answer.
 */
export async function ask(
  question: string,
  onEvent: (event: AskEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal,
    });
  } catch (error) {
    if (signal?.aborted) return;
    throw error;
  }
  if (!response.ok || !response.body) {
    throw new Error(`The server answered ${response.status}.`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const event = line.trim() ? parseEvent(line) : null;
      if (event) onEvent(event);
    }
    if (done) break;
  }
  const last = buffer.trim() ? parseEvent(buffer) : null;
  if (last) onEvent(last);
}
