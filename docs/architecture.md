# Live Underwriter — Architecture

## Unified AI Decision Platform

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

## Underwriting Graph

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

## Collections Graph

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

## Key Components

### 1. LangGraph State Machine
- Typed Pydantic state schema for type safety
- Conditional edges (gates) for branching logic
- Node-level error isolation
- Built-in support for human-in-the-loop breakpoints

### 2. Audit Trail & Explainability
Every agent node appends an `AuditEntry` with:
- Stage name and timestamp
- Decision rationale (human-readable)
- Confidence score (0.0-1.0)
- Input snapshot for traceability
- Outcome (ok/warn/error)

### 3. Compliance Layer
- **SCRA**: Servicemembers Civil Relief Act protections
- **Reg F**: Debt collection communication limits
- **UDAAP**: Fairness checks
- **State-specific rules**: 50-state regulatory patchwork
- **Jurisdiction detection**: Automatic from transcript/address

### 4. Human-in-the-Loop
- Flagged cases create review records in the DB
- CLI mode: Interactive reviewer prompts
- API mode: `requires_review` status with resolve endpoint
- Full audit trail of reviewer decisions

### 5. Synthetic Data Generator
- 20+ realistic applicants with risk profiles
- Supporting documents (bank statements, tax returns, IDs)
- Fraud scenarios with velocity signals and keyword flags
- Reproducible via seeded RNG

## Tech Stack

| Component | Technology |
|-----------|------------|
| State machine | LangGraph |
| State schema | Pydantic v2 |
| LLM interface | LangChain + OpenAI-compatible |
| API server | FastAPI + Uvicorn |
| Database | SQLite (repository pattern) |
| Frontend | React + TypeScript + Vite |
| Voice (optional) | faster-whisper + Kokoro |
| PDF extraction | pypdf |
