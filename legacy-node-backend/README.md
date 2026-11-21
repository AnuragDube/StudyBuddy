# Legacy Node.js / Express Backend (ARCHIVED)

> **Deprecated.** This is the original prototype backend of Study Buddy. It has been superseded by the
> FastAPI backend in [`../backend`](../backend). It is kept only for reference and historical comparison.
> It is not used by the current frontend and receives no further updates.

It exposed three endpoints that called Google Gemini directly and relied on the LLM to enforce dates and daily limits:

- `GET /api/status`
- `POST /api/generate-plan`
- `POST /api/reschedule`

In the new architecture, the LLM only extracts topics, and a deterministic Python scheduler enforces deadlines and
the shared daily study limit.

## Running (reference only)

```bash
cd legacy-node-backend
npm install
cp .env.example .env   # add GEMINI_API_KEY
npm start              # http://localhost:3001
```
