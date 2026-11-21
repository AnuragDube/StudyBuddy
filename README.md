# Study Buddy — Multi-Subject AI Study Planner

A full-stack, multi-subject AI study planner with **shared daily workload management**, built with **Python (FastAPI)**, **SQLite + SQLAlchemy + Alembic**, **PyMuPDF**, **Groq (`openai/gpt-oss-20b`) / Google Gemini (`google-genai`)**, and **React + TypeScript (Vite)**.

---

## Core Architectural Principle

Study Buddy strictly separates **probabilistic LLM reasoning** from **deterministic scheduling math**:

1. **LLM Syllabus Extraction (`backend/app/services/ai_service.py`)**: Reads unstructured syllabus PDF/TXT text (extracted server-side via PyMuPDF) and returns strict JSON validated by Pydantic (`SyllabusExtraction`), estimating topic structure, subtopics, difficulty (`low` / `medium` / `high`), priority (`1–5`), and required study minutes.
2. **Deterministic Python Scheduler (`backend/app/services/scheduler_service.py`)**: Collects all active subject plans and incomplete topics, orders them via **Earliest Deadline First (EDF)** broken by priority, difficulty, and syllabus order, and allocates non-overlapping study blocks (`start_offset_minutes`, `duration_minutes`) within **one shared daily capacity** and preferred weekdays.
3. **Feasibility & Overload Detection**: If combined multi-subject workload mathematically exceeds available study time before exam dates, the scheduler returns `is_feasible: false`, exact `deficit_minutes`, per-subject breakdowns, and actionable suggestions rather than generating an impossible timetable.

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend API | Python 3.12+, FastAPI, Uvicorn, Pydantic v2, pydantic-settings |
| Database & Migrations | SQLite, SQLAlchemy 2.0 ORM, Alembic |
| PDF Extraction | PyMuPDF (`fitz`) on the backend |
| AI Providers | Groq API (`openai/gpt-oss-20b`, strict JSON Schema) + Google Gen AI SDK (`google-genai`, automatic fallback & benchmarking) |
| Frontend | React 18, TypeScript 5, Vite 6, Lucide Icons |
| Testing | Pytest + FastAPI `TestClient` (54 automated unit, migration, API, and edge-case tests) |

---

## Project Structure

```text
study-buddy-planner/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point, CORS, request logging, routers
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings (.env handling)
│   │   │   └── logging.py           # Structured logging
│   │   ├── db/
│   │   │   ├── database.py          # SQLite + SQLAlchemy engine & session
│   │   │   ├── models.py            # UserSettings, StudyPlan, Topic, StudySession
│   │   │   ├── crud.py              # CRUD & progress aggregation helpers
│   │   │   └── init_db.py           # Programmatic Alembic migration runner
│   │   ├── schemas/                 # Pydantic request/response & strict AI JSON schemas
│   │   ├── api/routes/              # health, settings, plans, syllabus, schedule, sessions
│   │   └── services/
│   │       ├── pdf_service.py       # PyMuPDF PDF/TXT text extraction
│   │       ├── ai_service.py        # Provider-independent Groq/Gemini extraction
│   │       └── scheduler_service.py # Deterministic shared-capacity EDF scheduler
│   ├── benchmarks/                  # Research paper LLM evaluation harness & sample syllabi
│   ├── tests/                       # Pytest test suite (54 tests)
│   ├── alembic/                     # Database migrations
│   ├── requirements.txt
│   └── .env.example
├── frontend/                        # React + TypeScript + Vite SPA
│   ├── src/
│   │   ├── api/client.ts            # Typed REST client for FastAPI
│   │   ├── types/api.ts             # TypeScript contracts matching Pydantic schemas
│   │   ├── components/              # ScheduleView, SubjectsView, CapacityCard
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── tsconfig.json
│   └── vite.config.ts               # Proxies /api -> http://localhost:8000
├── legacy-node-backend/             # Archived original Node.js/Express prototype
└── README.md
```

---

## Local Setup & Execution

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env and add GROQ_API_KEY (and optionally GEMINI_API_KEY)

# Run database migrations (also runs automatically on startup when AUTO_MIGRATE=true)
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --port 8000
```

Interactive API documentation (Swagger UI) is available at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

### 2. Frontend (React + TypeScript + Vite)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite automatically proxies `/api/*` requests to `http://localhost:8000`.

To typecheck and build for production:

```bash
npm run build
```

---

## Key REST API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Service health & AI provider configuration status |
| `GET` / `PUT` | `/api/settings` | Read or update shared daily study capacity & preferred days (auto-recalculates schedule) |
| `GET` / `POST` | `/api/plans` | List or create independent subject plans |
| `GET` / `PATCH` / `DELETE` | `/api/plans/{plan_id}` | Inspect, update/archive, or delete a subject plan (auto-recalculates schedule) |
| `POST` / `PUT` / `PATCH` / `DELETE` | `/api/plans/{plan_id}/topics` | Manage topics inside a subject plan |
| `POST` | `/api/syllabus/extract` | Upload a PDF/TXT or paste text to extract structured topics via LLM |
| `POST` | `/api/plans/{plan_id}/extract-syllabus` | Extract topics from syllabus, attach to plan, and recalculate global schedule |
| `GET` / `POST` | `/api/schedule`, `/api/schedule/recalculate` | Retrieve or force-recalculate the unified multi-subject timetable & feasibility report |
| `PATCH` | `/api/sessions/{session_id}` | Mark a study session `completed`, `missed`, or `pending` and dynamically rebalance remaining work |

---

## Running Automated Tests

```bash
cd backend
pytest -v
```

All **54 tests** run against an isolated in-memory SQLite database with mocked LLM calls (no external API keys or network required):
- Health & OpenAPI schema checks
- Alembic upgrade/downgrade migration tests
- PyMuPDF PDF/TXT extraction & malformed file handling
- Strict JSON Schema & Groq/Gemini provider fallback tests
- Deterministic scheduler unit & multi-subject shared-capacity tests
- End-to-end API, session completion/missed rescheduling, and overload edge-case tests
- LLM benchmark harness verification

---

## Research Paper LLM Benchmarking Harness

To compare LLM providers (e.g., Groq `openai/gpt-oss-20b` vs. Google Gemini `gemini-3.5-flash-lite`) on **strict schema adherence**, **concept recall**, **latency**, **token usage**, and **downstream scheduler constraint compliance**:

```bash
cd backend

# Offline dry-run (verifies harness & metrics without API calls)
python -m benchmarks.run_benchmark --dry-run

# Live comparison across Groq & Gemini (requires API keys in .env)
python -m benchmarks.run_benchmark --providers groq gemini --save
```

When `--save` is passed, timestamped JSON and Markdown tables are written to `backend/benchmarks/results/`.
