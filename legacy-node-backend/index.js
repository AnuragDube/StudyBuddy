import "dotenv/config";
import express from "express";
import cors from "cors";

const app = express();
const PORT = Number(process.env.PORT || 3001);
const MODEL = process.env.GEMINI_MODEL || "gemini-3.8-flash";

app.use(cors());
app.use(express.json({ limit: "2mb" }));

app.get("/api/status", (_req, res) => {
  res.json({
    aiConfigured: Boolean(process.env.GEMINI_API_KEY),
    provider: "Google Gemini",
    model: MODEL
  });
});

async function askGemini(prompt) {
  const key = process.env.GEMINI_API_KEY;
  if (!key) {
    const error = new Error("AI is not configured. Add GEMINI_API_KEY to your .env file, then restart the app.");
    error.status = 503;
    throw error;
  }

  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(MODEL)}:generateContent`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": key },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: prompt }] }],
        generationConfig: {
          temperature: 0.25,
          responseMimeType: "application/json"
        }
      })
    }
  );

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data?.error?.message || `Gemini API request failed (${response.status}).`;
    const error = new Error(message);
    error.status = response.status === 429 ? 429 : 502;
    throw error;
  }

  const raw = data?.candidates?.[0]?.content?.parts?.map(p => p.text || "").join("").trim();
  if (!raw) {
    const error = new Error("The AI returned an empty response. Try again or shorten the syllabus.");
    error.status = 502;
    throw error;
  }

  try {
    return JSON.parse(raw.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, ""));
  } catch {
    const error = new Error("The AI response was not valid JSON. Please try generating the plan again.");
    error.status = 502;
    throw error;
  }
}

function validatePlan(plan) {
  if (!plan || !Array.isArray(plan.days) || plan.days.length === 0) {
    throw Object.assign(new Error("The AI did not return a usable schedule."), { status: 502 });
  }
  plan.days = plan.days.map((day, i) => ({
    date: String(day.date || ""),
    title: String(day.title || `Study day ${i + 1}`),
    summary: String(day.summary || ""),
    tasks: Array.isArray(day.tasks) ? day.tasks.map((task, j) => ({
      id: String(task.id || `${i}-${j}-${Math.random().toString(36).slice(2, 8)}`),
      title: String(task.title || "Study topic"),
      topic: String(task.topic || task.title || "Study topic"),
      minutes: Math.max(10, Math.min(240, Number(task.minutes) || 30)),
      type: ["learn", "practice", "revision", "break"].includes(task.type) ? task.type : "learn",
      reason: String(task.reason || "")
    })) : []
  }));
  return plan;
}

app.post("/api/generate-plan", async (req, res) => {
  try {
    const { syllabus, examDate, dailyHours, studyDays, confidence, startDate } = req.body || {};
    if (typeof syllabus !== "string" || syllabus.trim().length < 20) {
      return res.status(400).json({ error: "Please paste or upload a syllabus with enough readable text." });
    }
    if (!examDate || !dailyHours) {
      return res.status(400).json({ error: "Add an exam date and daily study hours." });
    }

    const prompt = `
You are Study Buddy, an expert study-planning assistant. Create a realistic, personalized schedule using ONLY topics supported by the syllabus. Do not invent syllabus units. You may create practice and revision activities based on the extracted topics.

Return valid JSON only with this shape:
{
  "planTitle": "short title",
  "overview": "2-3 sentence explanation",
  "topics": [{"name":"topic name","unit":"unit if stated, otherwise empty","priority":"High|Medium|Low","reason":"brief rationale"}],
  "days": [
    {"date":"YYYY-MM-DD","title":"short day title","summary":"short daily focus",
     "tasks":[{"id":"unique-id","title":"actionable task","topic":"topic name","minutes":45,"type":"learn|practice|revision|break","reason":"brief reason"}]}
  ],
  "studyTips": ["tip 1","tip 2","tip 3"]
}
Rules:
- Plan starts on ${startDate || new Date().toISOString().slice(0,10)} and ends no later than exam date ${examDate}.
- Exam date is ${examDate}; schedule a light review the day before and no heavy new topics on exam day. If there is insufficient time, prioritize and say so in overview.
- User can study about ${dailyHours} hours/day. Keep total task minutes per day at or below ${Number(dailyHours) * 60}; allow small flexibility only if required.
- Preferred study days: ${Array.isArray(studyDays) && studyDays.length ? studyDays.join(", ") : "all days"}.
- Confidence/difficulty notes: ${confidence || "not provided"}.
- Extract syllabus topics, split large topics into manageable sessions, prioritize difficult/foundational topics, and include practice and spaced revision.
- Aim for 1-5 tasks per study day; use specific actions, realistic durations, and the user's preferred study days.
- If a preferred study day is skipped, use it as rest/catch-up only if useful; do not overload the following day.
- Include an exam countdown context in the overview.
- Keep output concise and strictly valid JSON. Do not wrap in Markdown.
SYLLABUS:
${syllabus.slice(0, 30000)}
`;
    const result = validatePlan(await askGemini(prompt));
    res.json({ ...result, ai: { provider: "Google Gemini", model: MODEL, mode: "live" } });
  } catch (error) {
    res.status(error.status || 500).json({ error: error.message || "Could not generate a study plan." });
  }
});

app.post("/api/reschedule", async (req, res) => {
  try {
    const { plan, unfinished, newExamDate, dailyHours } = req.body || {};
    if (!plan || !Array.isArray(unfinished) || unfinished.length === 0) {
      return res.status(400).json({ error: "There are no unfinished tasks to reschedule." });
    }
    const prompt = `
Return JSON only: {"message":"short explanation","days":[{"date":"YYYY-MM-DD","title":"title","summary":"summary","tasks":[{"id":"unique-id","title":"task","topic":"topic","minutes":30,"type":"learn|practice|revision|break","reason":"why"}]}]}.
You are rescheduling an existing study plan. Preserve the original topic names; do not invent syllabus topics. Redistribute only these unfinished tasks across the remaining days through ${newExamDate}, with a daily cap of ${Number(dailyHours) * 60} minutes. Prioritize high priority items and include a short final revision. Do not create dates after the exam date. Keep a realistic workload. Existing plan context: ${JSON.stringify(plan).slice(0, 10000)}. Unfinished tasks: ${JSON.stringify(unfinished).slice(0, 12000)}.
`;
    const result = await askGemini(prompt);
    if (!Array.isArray(result.days)) throw Object.assign(new Error("The AI did not return a valid rescheduled plan."), { status: 502 });
    res.json({
      message: String(result.message || "Your unfinished tasks have been reorganized."),
      days: result.days.map((day, i) => ({
        date: String(day.date || ""),
        title: String(day.title || `Catch-up day ${i + 1}`),
        summary: String(day.summary || ""),
        tasks: Array.isArray(day.tasks) ? day.tasks.map((task, j) => ({
          id: String(task.id || `rescheduled-${i}-${j}-${Date.now()}`),
          title: String(task.title || "Review unfinished topic"),
          topic: String(task.topic || task.title || "Review unfinished topic"),
          minutes: Math.max(10, Math.min(240, Number(task.minutes) || 30)),
          type: ["learn", "practice", "revision", "break"].includes(task.type) ? task.type : "learn",
          reason: String(task.reason || "")
        })) : []
      })),
      ai: { provider: "Google Gemini", model: MODEL, mode: "live" }
    });
  } catch (error) {
    res.status(error.status || 500).json({ error: error.message || "Could not reschedule the plan." });
  }
});

app.listen(PORT, () => {
  console.log(`Study Buddy API running at http://localhost:${PORT}`);
  console.log(process.env.GEMINI_API_KEY ? `AI enabled (${MODEL})` : "AI key missing — live generation disabled until .env is configured.");
});
