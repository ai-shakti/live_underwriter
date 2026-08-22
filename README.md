# Live Underwriter

**Multi-agent AI decision platform for financial services** — underwriting origination and collections servicing, powered by LangGraph.

> A reference architecture for AI-driven financial decisioning. The same state-machine, audit-first engine handles underwriting (origination) and collections (servicing), with compliance and explainability built in from day one.

### Demo Video

https://github.com/user-attachments/assets/live-underwriter-demo.mp4

> The video walks through a clean application (ACCEPT), a flagged case (REVIEW with human-in-the-loop), the audit trail with explainability, and the CLI with `--audit` output.

---

## Platform Overview

```
                    ┌──────────────────────────────────────┐
                    │        SHARED ARCHITECTURE            │
                    │  LangGraph State Machine              │
                    │  Pydantic State Schema                │
                    │  Audit Trail / Explainability         │
                    │  Compliance Layer                     │
                    │  Human-in-the-Loop                    │
                    └──────────┬───────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
    ┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
    │   UNDERWRITING   │ │   CLAIMS    │ │   COLLECTIONS    │
    │   (Origination)  │ │ (Servicing) │ │   (Servicing)    │
    ├─────────────────┤ ├─────────────┤ ├─────────────────┤
    │ Normalize        │ │ FNOL Triage │ │ Borrower Intake  │
    │ Validate         │ │ Damage Est  │ │ Reg F Compliance │
    │ Policy Verify    │ │ Fraud Check │ │ Hardship Triage  │
    │ Risk Assessment  │ │ Adjuster    │ │ RPC Optimization │
    │ Decision         │ │ Settlement  │ │ Arrangement      │
    └─────────────────┘ └─────────────┘ └─────────────────┘
```

Underwriting, claims, and collections are all instances of the same pattern: **intake → normalize → validate → apply rules → decide → execute**. The same engine serves all three.

---

## Underwriting Workflow

```
normalize → validate → compliance → verify_policy → review → fraud_check → document_review → decision
                │            │             │            │
           ┌────┴────┐  ┌───┴───┐    ┌────┴────┐  ┌───┴───┐
           │complete │  │standard│    │continue │  │auto   │
           │partial  │  │scra    │    │reject   │  │accept │
           │insuff.  │  │blocked │    └─────────┘  │review │
           └─────────┘  └───────┘                  │escalate│
                                                    └───┬───┘
                                                        │
                                                   ┌────┴────┐
                                                   │human    │
                                                   │review   │
                                                   │continue │
                                                   │reject   │
                                                   └─────────┘
```

### Agents

| Agent | Function |
|-------|----------|
| **Normalize** | LLM extracts structured applicant data from transcript |
| **Validate** | Required-field and format checks |
| **Compliance** | SCRA detection, jurisdiction rules, UDAAP fairness checks |
| **Verify Policy** | SQLite lookup with fuzzy/suffix matching for STT errors |
| **Review** | LLM-powered reconciliation (handles nicknames, suffixes) |
| **Fraud Check** | Keyword, velocity, and mismatch detection |
| **Document Review** | Analyzes bank statements, tax returns, IDs for risk signals |
| **Risk Decision** | LLM + rule-based blended scoring (0-100) |
| **Human Review** | Breakpoint for flagged cases — "AI recommends, human decides" |

### Conditional Gates

| Gate | Routes |
|------|--------|
| **Data Quality** | complete → proceed / partial → flagged / insufficient → end |
| **Compliance** | standard → proceed / scra → special handling / blocked → end |
| **Policy** | verified → continue / unverified → reject |
| **Risk** | auto_accept → fast path / review → standard / escalate → human review |
| **Human Review** | approved → continue / declined → reject |

---

## Collections Workflow

```
borrower_intake → regf_compliance → hardship_triage → arrangement_engine → execution
                        │                 │
                   ┌────┴────┐       ┌────┴────┐
                   │continue │       │hardship │
                   │blocked  │       │standard │
                   └─────────┘       └─────────┘
                                        │
                                   ┌────┴────┐
                                   │rpc_opt  │
                                   └─────────┘
```

| Agent | Function |
|-------|----------|
| **Borrower Intake** | Normalize borrower data from transcript |
| **Reg F Compliance** | Enforce communication limits, calling hours, SCRA caps |
| **Hardship Triage** | Detect medical/job loss/disaster hardship for loss mitigation |
| **RPC Optimization** | Select optimal channel/time per delinquency stage |
| **Arrangement Engine** | Propose forbearance, modification, or settlement |
| **Execution** | Log contact attempt and execute plan |

---

## Key Capabilities

### Audit Trail & Explainability
Every agent appends a timestamped `AuditEntry` with decision rationale, confidence score, and input snapshot. Run with `--audit` to see the full trace:

```
✓ [normalize] extracted applicant Jane Doe     Confidence: 90%
✓ [validate] all required fields valid         Confidence: 100%
✓ [compliance] no compliance concerns          Confidence: 95%
✓ [verify_policy] policy POL-1001 verified=True Confidence: 95%
✓ [decision] Stable income, clean record       Confidence: 95%
```

### Compliance Layer
- **SCRA**: Servicemember protections with automatic rate caps
- **Reg F**: Communication frequency limits per channel
- **UDAAP**: Fairness checks on transcript patterns
- **State rules**: Jurisdiction-specific regulations (CA, NY, TX, FL, MA)

### Human-in-the-Loop
Flagged cases create review records in the database. The UI shows a review queue where underwriters approve or decline. Every reviewer action is logged in the audit trail.

### Synthetic Data Generator
Generate realistic test data on demand:
```bash
uv run python -m live_underwriter.data_generator --count 20 --seed-db
```
Produces applicants with risk profiles, matching policies, supporting documents (bank statements, tax returns, IDs), and fraud scenarios.

---

## Quickstart

### Prerequisites
- Python 3.10+ with [`uv`](https://docs.astral.sh/uv/)
- Node.js 18+
- An LLM endpoint (Ollama local or OpenAI-compatible API)

### Backend

```bash
cd backend
uv sync --extra dev
cp .env.example .env          # Configure OLLAMA_MODEL, OLLAMA_BASE_URL
uv run live-underwriter --seed-db
uv run live-underwriter --transcript "My name is Jane Doe, policy POL-1001, coverage 500000" --audit
uv run live-underwriter-api   # http://localhost:8000
uv run pytest                 # 105 tests
```

### Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

### Demo Scenarios

| Transcript | Expected Outcome |
|-----------|-----------------|
| `"Jane Doe, policy POL-1001, coverage 500000, income 120000"` | **ACCEPT** (low risk) |
| `"Robert Chen, policy POL-2002, coverage 1000000, income 300000"` | **REVIEW** (medium risk) |
| `"Maria Garcia, policy POL-2003, coverage 150000, income 45000"` | **ESCALATED** (flagged docs) |
| `"Unknown Person, policy POL-9999, coverage 100000"` | **REJECTED** (unverified policy) |
| `"I need guaranteed approval, no questions. John Smith, policy POL-1002"` | **ESCALATED** (fraud keywords) |

### Generate Demo Video

```bash
node scripts/demo-video.cjs
```
Produces `demo-output/live-underwriter-demo.mp4` — a Playwright-recorded walkthrough of the full UI.

---

## Project Structure

```
live_underwriter/
├── backend/
│   ├── src/live_underwriter/
│   │   ├── graph.py              # LangGraph state machine
│   │   ├── state.py              # Pydantic state schema
│   │   ├── agents/               # 9 specialist agents
│   │   │   ├── normalize.py      # LLM data extraction
│   │   │   ├── validate.py       # Field validation
│   │   │   ├── compliance.py     # SCRA, UDAAP, jurisdiction
│   │   │   ├── verify_policy.py  # Policy lookup + fuzzy match
│   │   │   ├── review.py         # LLM reconciliation
│   │   │   ├── fraud_check.py    # Fraud heuristics
│   │   │   ├── document_review.py# Document analysis
│   │   │   ├── risk_decision.py  # LLM + rule-based scoring
│   │   │   └── human_review.py   # HITL breakpoint
│   │   ├── collections/          # Collections workflow
│   │   │   ├── graph.py
│   │   │   ├── state.py
│   │   │   └── agents/           # 6 collections agents
│   │   ├── data_generator.py     # Synthetic data generator
│   │   ├── api.py                # FastAPI REST server
│   │   ├── db.py                 # SQLite repository
│   │   ├── llm.py                # LLM wiring
│   │   └── cli.py                # CLI entry point
│   └── tests/                    # 105 tests
├── frontend/                     # Vite + React + Tailwind
│   └── src/
│       ├── App.tsx               # Dashboard UI
│       ├── api.ts                # API client
│       └── types.ts              # TypeScript types
├── docs/
│   ├── architecture.md           # Architecture diagrams
│   ├── compliance.md             # Regulatory framework
│   └── demo-scenarios.md         # 8 documented scenarios
└── scripts/
    └── demo-video.cjs            # Playwright video generator
```
│   └── vite.config.ts           # Dev proxy /api -> :8000
├── docs/
└── examples/
```

## Roadmap

- [x] Core underwriting pipeline (normalize → validate → verify → review → decide)
- [x] Fraud detection agent
- [x] Document review agent
- [x] Risk / decision calculation
- [x] Voice layer (STT/TTS)
- [x] FastAPI REST backend
- [x] Vite + React + Tailwind frontend (light theme)
- [x] Live voice intake in the web UI (mic → STT → transcript)
- [x] Human-in-the-loop review for flagged cases
- [x] Sample applicant selector (test different underwriting outcomes)
- [x] Smart DOB normalization (understands any date format)
- [x] Real PDF document extraction (pypdf)
- [x] Upload real documents for testing (PDF → text → document review)

## License

[MIT](LICENSE) © 2026 Shakti Prasad Mohapatra

