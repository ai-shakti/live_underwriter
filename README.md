# Live Underwriter

**AI underwriting analyst agent team** — live, voice-driven risk assessment, policy verification, and decisioning.

> Automate the work of an underwriting analyst: gather applicant information, verify policy/account details, assess risk, and make accept/decline decisions — all through natural voice interaction.

## Why Live Underwriter?

Underwriting is a high-volume, decision-heavy job. `live_underwriter` turns it into an **agent team** that:

- 🎙️ **Talks to applicants** — live voice intake (speech-to-text) and voice responses (text-to-speech)
- 🔍 **Normalizes & validates** applicant data before any decision
- ✅ **Verifies** policy/account details against records
- 🧠 **Assesses risk** — fraud detection, document review, and payout/decision calculation
- 🤝 **Coordinates** multiple specialist agents through a stateful LangGraph workflow

## Architecture

```mermaid
flowchart TD
    A[User Voice Input] --> B[STT: Speech-to-Text]
    B --> C[1. Normalization]
    C --> D[2. Validation]
    D --> E[3. Verify Account/Policy]
    E --> F{Policy Exists?}
    F -- No --> G[Reject / Escalate]
    F -- Yes --> H[4. Review & Verify]
    H --> I[5. Submit Decision]
    I --> J[Fraud Detection]
    J --> K[Document Review]
    K --> L[Risk / Payout Calculation]
    L --> M[6. Decision]
    M --> N[TTS: Text-to-Speech]
    N --> O[Voice Response to User]
```

### Agent Team

| Agent | Role |
|-------|------|
| **Voice Intake** | STT → text, TTS → voice response |
| **Normalization** | Clean & standardize applicant data |
| **Validation** | Check data completeness & format |
| **Policy Verification** | Verify account/policy exists |
| **Review** | Review & verify applicant details |
| **Fraud Detection** | Flag suspicious applications |
| **Document Review** | Analyze supporting documents |
| **Risk / Decision** | Calculate risk & underwriting decision |

### How the agents spawn and analyze

The workflow is a **LangGraph state machine**. Each agent is a node that reads
the shared `UnderwritingState`, does its analysis, and writes back a partial
update. The graph routes between nodes based on the state — so agents "spawn"
sequentially, each building on the previous one's output.

```mermaid
flowchart TD
    subgraph Intake
        A[User Input<br/>transcript / voice] --> B[STT<br/>faster-whisper]
        B --> C[Normalize Agent<br/>LLM extracts structured data<br/>+ DOB normalization]
    end

    subgraph Core Analysis
        C --> D[Validate Agent<br/>required fields + format checks]
        D --> E[Verify Policy Agent<br/>SQLite lookup + fuzzy/suffix match]
        E --> F{Policy verified?}
        F -- No --> G[Reject / END]
        F -- Yes --> H[Review Agent<br/>reconcile applicant vs policy]
    end

    subgraph Risk Analysis
        H --> I[Fraud Check Agent<br/>keywords + velocity + mismatches]
        I --> J[Document Review Agent<br/>analyze bank statements / tax returns]
        J --> K[Risk Decision Agent<br/>score 0-100 -> accept/decline/review]
    end

    subgraph Human Oversight
        K --> L{Flagged?<br/>high risk / review / flags}
        L -- Yes --> M[Create Review Record]
        M --> N[Human Review Queue<br/>approve / decline]
        L -- No --> O[Final Decision]
        N --> O
    end

    O --> P[TTS<br/>Kokoro speaks decision]
```

**How analysis flows through the state:**

| Step | Agent | Reads from state | Writes to state |
|------|-------|------------------|-----------------|
| 1 | **Normalize** | `transcript` | `applicant` (structured) |
| 2 | **Validate** | `applicant` | audit trail (errors) |
| 3 | **Verify Policy** | `applicant.policy_number` | `policy` (verified?) |
| 4 | **Review** | `applicant`, `policy` | audit trail (mismatches) |
| 5 | **Fraud Check** | `transcript`, `applicant` | `risk.flags` |
| 6 | **Document Review** | `applicant` → DB docs | `risk.flags` |
| 7 | **Risk Decision** | `applicant`, `policy`, `risk` | `risk`, `decision` |
| 8 | **Human Review** | `risk` (if flagged) | review record |

Each agent is **stateless and composable** — it only transforms the shared
state, so the graph can be re-wired, agents added/removed, or the flow branched
without touching the other agents.

## Quickstart

> This project uses [`uv`](https://docs.astral.sh/uv/) for the backend and
> [`npm`](https://www.npmjs.com/) for the frontend.

### Backend (Python / LangGraph / FastAPI)

```bash
cd backend
uv sync --extra dev

# Configure the LLM (Ollama / OpenAI-compatible). Copy the template:
cp .env.example .env
#   Then edit .env — set OLLAMA_MODEL (e.g. qwen2.5, qwen3, llama3.1),
#   OLLAMA_BASE_URL, and OLLAMA_API_KEY. See .env.example for all options.

# Run the CLI
uv run live-underwriter --seed-db
uv run live-underwriter --transcript "My name is Jane Doe, policy POL-1001, coverage 500000"

# Run the API server (http://localhost:8000)
uv run live-underwriter-api
# or: uv run python -m uvicorn live_underwriter.api:app --reload

# Run tests
uv run python -m pytest
```

### Frontend (Vite + React + Tailwind, light theme)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
npm run build      # production build
```

### Live voice intake

The web UI has a **Record voice** button that captures audio from your
microphone, sends it to `POST /api/transcribe` (faster-whisper), and fills the
transcript box. To enable it, install the voice extras:

```bash
cd backend
uv sync --extra voice   # installs faster-whisper + kokoro
```

### Testing with sample applicants

The web UI has a **Sample applicant** dropdown with 6 curated test cases, each
with a distinct underwriting outcome (accept, review, flagged docs, reject).
Pick one to auto-fill the transcript, then run the workflow.

### Upload real documents

You can upload **real PDF documents** (bank statements, tax returns, W-2s) to
test the document review agent. Uploaded documents are extracted (via pypdf)
and analyzed alongside the applicant's seeded documents for risk signals like
overdrafts, delinquent accounts, or defaults.

### Human-in-the-loop review

When the AI flags a case (high risk, "review" decision, or document/fraud
flags), it automatically creates a **review record**. The **Human review queue**
panel in the UI lets an underwriter **approve or decline** each flagged case.

> **Note for pyenv users:** if `uv run pytest` resolves to the wrong Python
> (a pyenv shim conflict), invoke pytest as a module instead:
> `uv run python -m pytest`.

## Project Structure

```
live_underwriter/
├── backend/                     # Python / LangGraph / FastAPI
│   ├── src/live_underwriter/
│   │   ├── graph.py             # LangGraph state machine
│   │   ├── state.py             # Underwriting state schema
│   │   ├── agents/              # Specialist agents
│   │   ├── tools/               # Underwriting tools (STT/TTS/PDF)
│   │   ├── api.py               # FastAPI REST server
│   │   ├── api_server.py        # uvicorn entry point
│   │   ├── db.py                # SQLite repository + seed
│   │   ├── llm.py               # Ollama LLM wiring
│   │   ├── dates.py             # Smart DOB normalization
│   │   ├── samples.py           # Curated test applicants
│   │   └── cli.py               # CLI entry point
│   └── tests/
├── frontend/                    # Vite + React + Tailwind (light theme)
│   ├── src/
│   │   ├── App.tsx              # Main dashboard UI
│   │   ├── api.ts               # Backend API client
│   │   ├── types.ts             # Shared response types
│   │   └── index.css            # Tailwind + light theme
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

