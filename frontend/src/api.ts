import type { UnderwriteResponse } from "./types";

const BASE = "/api";

/** Run the underwriting graph on a transcript. */
export async function runUnderwrite(transcript: string): Promise<UnderwriteResponse> {
  const resp = await fetch(`${BASE}/underwrite`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript }),
  });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(`Underwrite failed (${resp.status}): ${detail}`);
  }
  return resp.json();
}

/** Transcribe an audio blob (live voice intake). */
export async function transcribeAudio(blob: Blob): Promise<{ transcript: string }> {
  const form = new FormData();
  form.append("file", blob, "recording.wav");
  const resp = await fetch(`${BASE}/transcribe`, {
    method: "POST",
    body: form,
  });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(`Transcription failed (${resp.status}): ${detail}`);
  }
  return resp.json();
}

/** Health check. */
export async function health(): Promise<{ status: string }> {
  const resp = await fetch(`${BASE}/health`);
  if (!resp.ok) throw new Error(`Health check failed (${resp.status})`);
  return resp.json();
}
