import { useEffect, useState } from "react";
import {
  runUnderwrite,
  health,
  transcribeAudio,
  listReviews,
  resolveReview,
  fetchSamples,
  uploadDocument,
} from "./api";
import { useRecorder } from "./useRecorder";
import type { Review, SampleApplicant, UnderwriteResponse, UploadedDoc } from "./types";

const DECISION_STYLES: Record<string, string> = {
  accept: "bg-emerald-50 text-emerald-700 border-emerald-200",
  decline: "bg-rose-50 text-rose-700 border-rose-200",
  review: "bg-amber-50 text-amber-700 border-amber-200",
  pending: "bg-slate-50 text-slate-500 border-slate-200",
};

const LEVEL_STYLES: Record<string, string> = {
  low: "text-emerald-600",
  medium: "text-amber-600",
  high: "text-rose-600",
};

const OUTCOME_DOT: Record<string, string> = {
  ok: "bg-emerald-400",
  warn: "bg-amber-400",
  error: "bg-rose-400",
};

export default function App() {
  const [transcript, setTranscript] = useState("");
  const [samples, setSamples] = useState<SampleApplicant[]>([]);
  const [selectedSample, setSelectedSample] = useState<string>("");
  const [result, setResult] = useState<UnderwriteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [uploadedDocs, setUploadedDocs] = useState<UploadedDoc[]>([]);
  const [uploading, setUploading] = useState(false);
  const recorder = useRecorder();

  // Load sample applicants on mount.
  useEffect(() => {
    (async () => {
      try {
        const s = await fetchSamples();
        setSamples(s);
        if (s.length > 0) {
          setSelectedSample(s[0].id);
          setTranscript(s[0].transcript);
        }
      } catch {
        // samples are optional
      }
    })();
  }, []);

  function handleSampleChange(id: string) {
    setSelectedSample(id);
    const sample = samples.find((s) => s.id === id);
    if (sample) setTranscript(sample.transcript);
  }

  async function loadReviews() {
    try {
      const r = await listReviews(true);
      setReviews(r);
    } catch {
      // ignore — reviews are optional
    }
  }

  useEffect(() => {
    loadReviews();
  }, []);

  async function handleResolve(id: number, status: "approved" | "declined") {
    try {
      await resolveReview(id, status);
      await loadReviews();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to resolve review");
    }
  }

  async function checkHealth() {
    try {
      await health();
      setBackendUp(true);
    } catch {
      setBackendUp(false);
    }
  }

  async function handleSubmit() {
    setLoading(true);
    setError(null);
    try {
      const res = await runUnderwrite(transcript, uploadedDocs);
      setResult(res);
      setBackendUp(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      setBackendUp(false);
    } finally {
      setLoading(false);
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const doc = await uploadDocument(file);
      setUploadedDocs((prev) => [...prev, doc]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  function removeDoc(filename: string) {
    setUploadedDocs((prev) => prev.filter((d) => d.filename !== filename));
  }

  async function handleRecordToggle() {
    if (recorder.recording) {
      recorder.stop();
      return;
    }
    await recorder.start();
  }

  // When a recording finishes, transcribe it and fill the transcript box.
  async function handleBlobReady(blob: Blob | null) {
    if (!blob) return;
    setTranscribing(true);
    setError(null);
    try {
      const { transcript } = await transcribeAudio(blob);
      setTranscript(transcript);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Transcription failed");
    } finally {
      setTranscribing(false);
    }
  }

  useEffect(() => {
    if (recorder.blob) {
      handleBlobReady(recorder.blob);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recorder.blob]);

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
              UW
            </div>
            <div>
              <h1 className="text-lg font-semibold text-slate-900">Live Underwriter</h1>
              <p className="text-xs text-slate-500">AI underwriting analyst agent team</p>
            </div>
          </div>
          <button
            onClick={checkHealth}
            className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            <span
              className={`h-2 w-2 rounded-full ${
                backendUp === null ? "bg-slate-300" : backendUp ? "bg-emerald-500" : "bg-rose-500"
              }`}
            />
            {backendUp === null ? "Check backend" : backendUp ? "Backend online" : "Backend offline"}
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {/* Input card */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-1 text-sm font-semibold text-slate-900">Applicant transcript</h2>
          <p className="mb-3 text-xs text-slate-500">
            Pick a sample applicant to test, paste a transcript, or record it live with the mic.
          </p>

          {/* Sample selector */}
          {samples.length > 0 && (
            <div className="mb-3">
              <label className="mb-1 block text-xs font-medium text-slate-600">
                Sample applicant
              </label>
              <select
                value={selectedSample}
                onChange={(e) => handleSampleChange(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white p-2.5 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              >
                {samples.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} — {s.description}
                  </option>
                ))}
              </select>
              {selectedSample && (
                <p className="mt-1 text-xs text-slate-500">
                  Expected outcome:{" "}
                  <span className="font-medium text-slate-700">
                    {samples.find((s) => s.id === selectedSample)?.expected_outcome}
                  </span>
                </p>
              )}
            </div>
          )}

          <textarea
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            rows={4}
            className="w-full rounded-lg border border-slate-300 bg-white p-3 text-sm text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            placeholder="Enter the applicant transcript..."
          />

          {/* Document upload */}
          <div className="mt-3 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3">
            <label className="mb-1 block text-xs font-medium text-slate-600">
              Supporting documents (optional)
            </label>
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileUpload}
              disabled={uploading}
              className="block w-full text-xs text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-600 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white hover:file:bg-indigo-700"
            />
            {uploading && <p className="mt-1 text-xs text-slate-500">Extracting text…</p>}
            {uploadedDocs.length > 0 && (
              <ul className="mt-2 space-y-1">
                {uploadedDocs.map((d) => (
                  <li key={d.filename} className="flex items-center justify-between text-xs text-slate-700">
                    <span className="truncate">📄 {d.filename}</span>
                    <button
                      onClick={() => removeDoc(d.filename)}
                      className="ml-2 text-rose-500 hover:text-rose-700"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              onClick={handleSubmit}
              disabled={loading || !transcript.trim()}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Running workflow…" : "Run underwriting"}
            </button>
            <button
              onClick={handleRecordToggle}
              disabled={transcribing}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
                recorder.recording
                  ? "bg-rose-600 text-white hover:bg-rose-700"
                  : "border border-slate-200 text-slate-600 hover:bg-slate-50"
              }`}
            >
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  recorder.recording ? "animate-pulse bg-white" : "bg-rose-500"
                }`}
              />
              {recorder.recording ? "Stop recording" : transcribing ? "Transcribing…" : "Record voice"}
            </button>
          </div>
          {recorder.error && (
            <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {recorder.error}
            </p>
          )}
          {error && (
            <p className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </p>
          )}
        </section>

        {/* Result */}
        {result && (
          <section className="mt-6 grid gap-6 lg:grid-cols-2">
            {/* Decision card */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-sm font-semibold text-slate-900">Decision</h2>
              <div
                className={`inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-semibold capitalize ${
                  DECISION_STYLES[result.decision ?? "pending"]
                }`}
              >
                {result.decision ?? "pending"}
              </div>
              <div className="mt-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-500">Risk score</span>
                  <span className={`font-semibold ${LEVEL_STYLES[result.risk_level]}`}>
                    {result.risk_score} / 100 ({result.risk_level})
                  </span>
                </div>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-indigo-500"
                    style={{ width: `${result.risk_score}%` }}
                  />
                </div>
              </div>
              <p className="mt-4 text-sm text-slate-600">{result.rationale}</p>

              {result.flags.length > 0 && (
                <div className="mt-4">
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Flags
                  </h3>
                  <ul className="space-y-1">
                    {result.flags.map((f, i) => (
                      <li key={i} className="rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-700">
                        {f}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Applicant + policy card */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-sm font-semibold text-slate-900">Applicant &amp; policy</h2>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <Field label="Name" value={result.applicant.full_name} />
                <Field label="DOB" value={result.applicant.date_of_birth} />
                <Field label="Policy" value={result.applicant.policy_number} />
                <Field label="Coverage" value={fmtMoney(result.applicant.coverage_amount)} />
                <Field label="Income" value={fmtMoney(result.applicant.annual_income)} />
                <Field label="Occupation" value={result.applicant.occupation} />
              </dl>
              {result.policy && (
                <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold text-slate-700">
                    Policy {result.policy.policy_number} — {result.policy.status}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Holder: {result.policy.policy_holder} · Premium: {fmtMoney(result.policy.premium)}
                  </p>
                </div>
              )}
            </div>

            {/* Audit trail */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
              <h2 className="mb-4 text-sm font-semibold text-slate-900">Audit trail</h2>
              <ol className="space-y-2">
                {result.audit_trail.map((entry, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm">
                    <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${OUTCOME_DOT[entry.outcome]}`} />
                    <div>
                      <span className="font-medium capitalize text-slate-800">{entry.stage}</span>
                      <span className="ml-2 text-slate-500">{entry.detail}</span>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </section>
        )}

        {/* Human-in-the-loop review queue */}
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-900">Human review queue</h2>
            <button
              onClick={loadReviews}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
            >
              Refresh
            </button>
          </div>
          {reviews.length === 0 ? (
            <p className="text-sm text-slate-500">No pending reviews. Flagged cases will appear here.</p>
          ) : (
            <ul className="space-y-3">
              {reviews.map((r) => (
                <li key={r.id} className="rounded-lg border border-slate-200 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-slate-800">{r.applicant_name}</p>
                      <p className="text-xs text-slate-500">
                        {r.policy_number ?? "No policy"} · AI: {r.ai_decision} · Risk {r.risk_score} ({r.risk_level})
                      </p>
                    </div>
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                      pending
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-600">{r.rationale}</p>
                  {r.flags.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {r.flags.map((f, i) => (
                        <span key={i} className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-700">
                          {f}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => handleResolve(r.id, "approved")}
                      className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleResolve(r.id, "declined")}
                      className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-700"
                    >
                      Decline
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-800">{value ?? "—"}</dd>
    </div>
  );
}

function fmtMoney(v: number | null): string {
  if (v == null) return "—";
  return `$${v.toLocaleString()}`;
}
