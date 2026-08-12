import type { Review, SampleApplicant, UnderwriteResponse } from "./types";

const BASE = "/api";

/** Fetch curated sample applicants for testing. */
export async function fetchSamples(): Promise<SampleApplicant[]> {
  const resp = await fetch(`${BASE}/samples`);
  if (!resp.ok) throw new Error(`Fetch samples failed (${resp.status})`);
  return resp.json();
}

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

/** List reviews (optionally pending only). */
export async function listReviews(pendingOnly = false): Promise<Review[]> {
  const resp = await fetch(`${BASE}/reviews?pending_only=${pendingOnly}`);
  if (!resp.ok) throw new Error(`List reviews failed (${resp.status})`);
  return resp.json();
}

/** Approve or decline a review. */
export async function resolveReview(
  id: number,
  status: "approved" | "declined",
  reviewerNote?: string
): Promise<Review> {
  const resp = await fetch(`${BASE}/reviews/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, reviewer_note: reviewerNote }),
  });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(`Resolve review failed (${resp.status}): ${detail}`);
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
