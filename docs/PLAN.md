# Live Underwriter — Implementation Plan

> **Status**: Approved — implementation in progress (2026-08-12)
> **Repo**: `live_underwriter` — AI underwriting analyst agent team (LangGraph, voice-driven).

---

## 1. Project Vision

An AI underwriting analyst agent team that takes a **voice-driven** application
(transcript or live audio), normalizes the applicant data, verifies the policy
against records, runs fraud + document checks, and produces a **risk score and
decision** with a full **audit trail** for explainability.

Built fully **local-first**: Ollama LLM, SQLite DB, open-source voice models.
No external API calls; no applicant data leaves the machine.

---

## 2. Underwriting Industry Pain Points (grounded)

1. Manual data entry & re-keying across siloed systems (policy, claims, CRM, bureaus).
2. Long turnaround times (TAT) — days/weeks for complex cases; slow quote-to-bind.
3. Data quality issues — incomplete, inconsistent, unstructured applicant data.
4. Legacy systems / mainframes — hard to integrate, no APIs.
5. Fraud detection is reactive & manual — hard to catch application fraud early.
6. Document review is manual — PDFs, bank statements, tax returns read by humans.
7. Inconsistent decisioning — underwriter judgment varies; no audit trail.
8. Regulatory/compliance burden — must document rationale, fair-lending, explainability.
9. Talent shortage & high cost of senior underwriters; burnout on repetitive work.
10. Risk scoring is siloed — no unified view across fraud, docs, policy, financials.

## 3. Companies Doing Underwriting (real players)

- **ZestyAI** — AI property risk (wildfire, hail, wind, roof age) for P&C underwriting.
- **Shift Technology** — fraud detection + underwriting decisioning for insurers.
- **Planck** — commercial insurance data enrichment/underwriting.
- **Cape Analytics** — geospatial property intelligence.
- **Betterview** — property risk insights.
- **Socotra / Guidewire / Duck Creek** — core underwriting platforms (legacy modernization).
- **Verisk / LexisNexis Risk** — data providers (bureaus, scoring).
- **Carriers**: Allstate, Progressive, Lemonade, Hippo, Kin (insurtechs using AI underwriting).

---

## 4. Scope (3 tiers)

### SHOULD HAVE (MVP — core underwriting workflow)
- Normalization of applicant data (LLM from transcript).
- Validation rules (required fields, format).
- Policy verification against a records source (gate).
- Risk scoring + decision (accept/decline/review) with rationale.
- Audit trail / explainability (why a decision was made).
- CLI single-pass runner + tests.

### COULD HAVE (differentiators)
- Fraud detection heuristics (velocity, mismatches, red flags).
- Document review (extract from PDFs/statements).
- Voice intake (STT) + voice response (TTS).
- Interactive multi-turn clarification loop (ask applicant for missing data).
- Risk level routing (low/med/high → different review paths).

### MAY HAVE (stretch / future)
- Integration with real data providers (Verisk, LexisNexis).
- Fair-lending / bias monitoring.
- Multi-carrier / reinsurance support.
- Dashboard / reporting.
- Deployment (Docker, cloud).

---

## 5. Decided Tech (user, 2026-08-12)

| Concern | Decision |
|---------|----------|
| **MVP scope** | Implement full "Should Have" chain (normalize→validate→verify_policy→decision). |
| **LLM provider** | Ollama via **OpenAI-compatible endpoint**. Keep `langchain-openai`, set `base_url` + `api_key` + `model` from env vars. |
| **STT** | `faster-whisper` (CTranslate2, up to 4× faster, int8 CPU-friendly, VAD filter). Model `small`/`base` for latency, `turbo`/`distil-large-v3` for quality. |
| **TTS** | `Kokoro-82M` (Apache-2.0, 82M params, fast, high quality, MPS GPU accel on Mac). Piper is archived — avoid. |
| **DB** | SQLite (free tier) for all mock data. Swap to real DB later via repository pattern. |
| **Fraud + docs** | Mock with REAL public data (sample bank statements, tax docs, known fraud patterns) stored in SQLite. |

### LLM env-var config (no lock-in)
- `OLLAMA_BASE_URL` — default `http://localhost:11434/v1`
- `OLLAMA_API_KEY` — default `"ollama"` (user has one)
- `OLLAMA_MODEL` — default `qwen2.5` (best for structured JSON extraction; swap to llama3.1/mistral anytime)

---

## 6. Engineering Standards (user requirements)

1. **Docs folder** — all plans/designs live in `docs/`.
2. **Logging everywhere** — use Python `logging` to capture where errors occur. No silent failures.
3. **Test every feature** — each feature ships with tests that prove it works (fail on old code, pass with fix).

---

## 7. Architecture

```
src/live_underwriter/
├── cli.py            # CLI: --transcript, --audio, --version
├── graph.py          # LangGraph StateGraph wiring (DONE — no changes)
├── state.py          # Pydantic schemas (DONE — may extend for audit trail)
├── llm.py            # NEW — ChatOpenAI from env vars (Ollama endpoint)
├── db.py             # NEW — SQLite + repository pattern + seed data
├── logging_conf.py   # NEW — centralized logging setup
├── agents/
│   ├── __init__.py   # 7 node stubs (MAIN implementation target)
│   ├── normalize.py
│   ├── validate.py
│   ├── verify_policy.py
│   ├── review.py
│   ├── fraud_check.py
│   ├── document_review.py
│   └── risk_decision.py
└── tools/
    ├── __init__.py
    ├── stt.py        # NEW — faster-whisper transcription
    └── tts.py        # NEW — Kokoro speech synthesis
```

### LangGraph flow
```
normalize → validate → verify_policy ──(gate)──→ review → fraud_check → document_review → decision → END
                                        └──(reject)──→ END
```

---

## 8. Implementation Phases

### Phase 1 — Foundation (DB + LLM wiring)
- [ ] Add deps to `pyproject.toml`: `faster-whisper`, `kokoro`, `langchain-ollama` (voice extras); keep `sqlite3` (stdlib).
- [ ] Create `logging_conf.py` — centralized `logging` setup (console + rotating file in `logs/`).
- [ ] Create `llm.py` — `ChatOpenAI` from env vars (Ollama endpoint).
- [ ] Create `db.py` — SQLite connection + repository pattern (policies, applicants, fraud rules, documents).
- [ ] Seed SQLite with realistic mock data.
- [ ] **Test**: DB round-trip, LLM config resolution, logging writes to file.

### Phase 2 — Core agents + audit trail
- [ ] `normalize.py` — LLM extracts structured `ApplicantInfo` from transcript.
- [ ] `validate.py` — field-level validation rules (required, format).
- [ ] `verify_policy.py` — policy lookup against SQLite records (gate).
- [ ] `risk_decision.py` — risk scoring + decision with rationale.
- [ ] Extend `state.py` with audit trail (list of `AuditEntry`).
- [ ] **Test**: each agent unit test + full graph end-to-end.

### Phase 3 — Fraud, docs, voice
- [ ] `fraud_check.py` — heuristics (velocity, mismatches, red flags) + LLM checks.
- [ ] `document_review.py` — extract/analyze sample documents from SQLite.
- [ ] `tools/stt.py` — faster-whisper transcription.
- [ ] `tools/tts.py` — Kokoro speech synthesis.
- [ ] Clarification loop (ask applicant for missing data).
- [ ] **Test**: fraud rules, doc extraction, STT/TTS round-trip.

### Phase 4 — Tests + CLI
- [ ] `cli.py` `--audio` mode (record → STT → graph → TTS response).
- [ ] Full test suite (unit + integration).
- [ ] **Test**: CLI transcript + audio paths.

---

## 9. Verification / Definition of Done

- [ ] `uv sync --extra dev` succeeds.
- [ ] `pytest` green (all features tested).
- [ ] `ruff check` clean.
- [ ] `mypy` clean (strict).
- [ ] CLI `--transcript` produces a decision with audit trail.
- [ ] CLI `--audio` records, transcribes, decides, and speaks back.
- [ ] Logs capture every stage + any errors with file/line context.

---

## 10. Out of Scope (this iteration)
- Real data providers (Verisk, LexisNexis) — mocked.
- Fair-lending / bias monitoring.
- Multi-carrier / reinsurance.
- Dashboard / reporting.
- Docker / cloud deployment.
