# Study Buddy Planner — PS 90

A local-first study planner that turns syllabus text into a dated study schedule, tracks completed sessions, and can reschedule unfinished tasks. The frontend is React + Vite; the backend is Node/Express. Live plan generation and AI rescheduling use the Google Gemini API.

## Features

- Upload text-based PDF and TXT syllabi, or paste syllabus text.
- Extract PDF text in the browser using PDF.js.
- Configure exam date, daily study hours, preferred study days, and difficult topics.
- Generate a day-by-day study plan using Gemini.
- Track task completion and topic priorities; progress is saved in browser local storage.
- Ask Gemini to reschedule unfinished tasks.
- Clearly labelled local demo mode works without an API key.
- API key is kept on the server and is never sent to the browser.

## Requirements

- Node.js 20 or newer (Node 18.18+ may also work if `fetch` is available).
- A Google Gemini API key for live AI generation. Get one from https://aistudio.google.com/app/apikey.

## Run locally in VS Code

1. Extract the ZIP and open the `study-buddy-planner` folder in VS Code.
2. Open a terminal in that folder and install dependencies:

   ```bash
   npm install
   ```

3. Copy `.env.example` to `.env`.
   - Windows PowerShell: `Copy-Item .env.example .env`
   - macOS/Linux: `cp .env.example .env`

4. Open `.env` and set your API key:

   ```env
   GEMINI_API_KEY=put_your_real_key_here
   GEMINI_MODEL=gemini-3.8-flash
   PORT=3001
   ```

5. Start the app:

   ```bash
   npm run dev
   ```

6. Open http://localhost:5173.

The Vite frontend runs on port 5173 and proxies `/api` requests to the local Express backend on port 3001. Keep the terminal open while using the app.

## Try without an API key

Click **Try demo** to create a clearly labelled local sample schedule. Demo mode does not call an AI model. The **Generate with AI** and **Reschedule unfinished** actions require a configured Gemini API key.

## GitHub safety

- Never commit `.env` or paste your API key into source code.
- `.gitignore` excludes `.env`.
- Commit `.env.example`, not your real `.env`.
- If a key is ever committed or shared, revoke it and create a new one.

## Project structure

```text
study-buddy-planner/
├── server/
│   └── index.js       # Gemini API calls and validation
├── src/
│   ├── main.jsx       # Planner UI, PDF upload, progress and rescheduling
│   └── styles.css     # Responsive styles
├── .env.example
├── .gitignore
├── index.html
├── package.json
└── vite.config.js
```

## Important notes

- PDF text extraction works for PDFs containing selectable text. Scanned/image-only PDFs need OCR; the app will report when no readable text is found.
- Plans are generated from the syllabus text and user preferences. Review the result before relying on it for exam preparation.
- User progress is stored in local browser storage on the device and browser where the app is running.

## Publish this local repository to GitHub

The downloaded project is a Git-ready source tree. Create a new empty repository on GitHub named `study-buddy-planner` (do not initialize it with a README or license), then run these commands in the extracted project folder:

```bash
git remote add origin https://github.com/AnuragDube/study-buddy-planner.git
git branch -M main
git push -u origin main
```

If you create the repository under a different owner/name, replace the URL above. Keep `.env` untracked; verify with `git status` before pushing.
