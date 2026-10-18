import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import * as pdfjsLib from "pdfjs-dist";
import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import {
  ArrowRight, BookOpen, BrainCircuit, CalendarDays, Check, CheckCircle2,
  ChevronDown, CircleHelp, Clock3, FileText, FileUp, Flame, GraduationCap,
  LayoutDashboard, LoaderCircle, RefreshCw, Sparkles, Target, Trash2,
  UploadCloud, WandSparkles, X
} from "lucide-react";
import "./styles.css";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;

const STORAGE_KEY = "study-buddy-planner-v1";
const sampleSyllabus = `Natural Language Processing — Semester VII
Unit I — Introduction and word level analysis (9 Hours)
History, generic NLP system, levels and stages, ambiguity and challenges, words, corpora, morphology analysis, inflectional and derivational morphology, stemming, lemmatization, normalization, tokenization, bag of words, regular expression, finite automata, finite state transducers (FST), n grams language model.
Unit II — Syntactic analysis (9 Hours)
Part of Speech (POS) tagging: rule based and stochastic tagging, stop words, sequence labelling: HMM, Conditional Random Field (CRF), Context Free Grammars (CFG), top down, Earley and CKY parsing, PCFG, TF-IDF, information extraction, relation extraction.
Unit III — Semantic Analysis (9 Hours)
Semantic grammars, lexical semantics, homonymy, polysemy, synonymy, hyponymy, WordNet, word similarity, Word Sense Disambiguation (WSD), information retrieval.
Unit IV — Discourse and Pragmatic Analysis (9 Hours)
Discourse, cohesion, discourse structure, adjacency pairs, implicature, cooperative principle, conversational analysis, context, speech acts, deixis, positive and negative face, pragmatic markers.
Unit V — Machine Learning in NLP (9 Hours)
Supervised and unsupervised ML, ML on natural language sentences, hybrid ML systems for NLP, deep learning for NLP, sentiment analysis, prediction of next word.`;

const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const fmtDate = (date) => new Date(`${date}T12:00:00`).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
const todayISO = () => new Date().toISOString().slice(0, 10);
const defaultExam = () => { const d = new Date(); d.setDate(d.getDate() + 14); return d.toISOString().slice(0, 10); };

function makeDemoPlan(syllabus, examDate, dailyHours, studyDays) {
  const lines = syllabus.split(/\n|[.;]/).map(s => s.trim()).filter(s => s.length > 5);
  const topics = [...new Set(lines.filter(s => !/^(natural language processing|semester|unit\s+[ivx\d]+|course code)/i.test(s)).map(s => s.replace(/^[-•\d.)\s]+/, "").trim()).filter(s => s.length > 5))].slice(0, 30);
  const allTopics = topics.length ? topics : ["Read the syllabus", "Make topic notes", "Practice questions", "Revise key concepts"];
  const start = new Date(`${todayISO()}T12:00:00`);
  const end = new Date(`${examDate}T12:00:00`);
  const days = [];
  let idx = 0;
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const date = d.toISOString().slice(0, 10);
    const dayName = weekdays[(d.getDay() + 6) % 7];
    if (studyDays.length && !studyDays.includes(dayName)) continue;
    const chosen = allTopics.slice(idx, idx + 2);
    if (!chosen.length && days.length) {
      days.push({ date, title: "Revision & practice", summary: "Revisit earlier topics and test recall.", tasks: [{ id: `demo-${date}-rev`, title: "Review notes and answer practice questions", topic: "Revision", minutes: Math.min(45, dailyHours * 60), type: "revision", reason: "Reinforce what you have learned." }] });
    } else {
      const tasks = chosen.map((topic, j) => ({ id: `demo-${date}-${idx}-${j}`, title: `Study and summarize: ${topic}`, topic, minutes: Math.max(25, Math.floor(dailyHours * 60 / Math.max(chosen.length, 1))), type: "learn", reason: "Demo-mode topic allocation; AI is not being called." }));
      if (tasks.length && dailyHours >= 1) tasks.push({ id: `demo-${date}-practice`, title: "Active recall and practice questions", topic: chosen[0], minutes: Math.min(25, Math.floor(dailyHours * 15)), type: "practice", reason: "Practice helps check understanding." });
      days.push({ date, title: chosen[0] ? `Focus: ${chosen[0]}` : "Catch-up & revision", summary: "Demo schedule based on syllabus text; not AI-generated.", tasks });
      idx += chosen.length;
    }
  }
  if (!days.length) days.push({ date: todayISO(), title: "Set up your plan", summary: "No selected study days fall before your exam date.", tasks: [] });
  return { planTitle: "Your syllabus study plan (Demo)", overview: "This is a local demo schedule created without an AI API call. Add a Gemini API key to generate a personalized plan using a real AI model.", topics: allTopics.map((name, i) => ({ name, unit: "", priority: i < 5 ? "High" : "Medium", reason: "Priority estimated by simple demo ordering, not AI." })), days, studyTips: ["Use active recall instead of rereading only.", "Take short breaks between focused sessions.", "Review difficult topics again after a day or two."], ai: { provider: "Local demo", mode: "demo" } };
}

function App() {
  const [activeTab, setActiveTab] = useState("planner");
  const [syllabus, setSyllabus] = useState("");
  const [examDate, setExamDate] = useState(defaultExam());
  const [dailyHours, setDailyHours] = useState(3);
  const [studyDays, setStudyDays] = useState(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]);
  const [confidence, setConfidence] = useState("");
  const [fileName, setFileName] = useState("");
  const [fileStatus, setFileStatus] = useState("");
  const [fileError, setFileError] = useState("");
  const [loading, setLoading] = useState(false);
  const [rescheduling, setRescheduling] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [aiStatus, setAiStatus] = useState({ aiConfigured: false, provider: "Google Gemini", model: "gemini-2.5-flash" });
  const [plan, setPlan] = useState(null);
  const [doneTasks, setDoneTasks] = useState({});
  const [selectedDay, setSelectedDay] = useState(0);
  const [showSetup, setShowSetup] = useState(true);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
      if (saved) {
        setSyllabus(saved.syllabus || "");
        setExamDate(saved.examDate || defaultExam());
        setDailyHours(saved.dailyHours || 3);
        setStudyDays(saved.studyDays || weekdays);
        setConfidence(saved.confidence || "");
        setPlan(saved.plan || null);
        setDoneTasks(saved.doneTasks || {});
        setShowSetup(!saved.plan);
      }
    } catch {}
    fetch("/api/status").then(r => r.json()).then(setAiStatus).catch(() => {});
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ syllabus, examDate, dailyHours, studyDays, confidence, plan, doneTasks }));
  }, [syllabus, examDate, dailyHours, studyDays, confidence, plan, doneTasks]);

  const allTasks = useMemo(() => (plan?.days || []).flatMap(d => d.tasks || []), [plan]);
  const completedCount = allTasks.filter(t => doneTasks[t.id]).length;
  const progress = allTasks.length ? Math.round(completedCount / allTasks.length * 100) : 0;
  const daysLeft = Math.max(0, Math.ceil((new Date(`${examDate}T12:00:00`) - new Date(`${todayISO()}T12:00:00`)) / 86400000));
  const currentDay = plan?.days?.[Math.min(selectedDay, Math.max(0, plan.days.length - 1))];

  async function readFile(file) {
    setFileError(""); setFileStatus("Reading file…");
    if (!file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    try {
      let text = "";
      if (ext === "txt") {
        text = await file.text();
      } else if (ext === "pdf" || file.type === "application/pdf") {
        const buffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: buffer }).promise;
        const pages = [];
        for (let i = 1; i <= pdf.numPages; i++) {
          const page = await pdf.getPage(i);
          const content = await page.getTextContent();
          pages.push(content.items.map(item => item.str || "").join(" "));
        }
        text = pages.join("\n");
      } else {
        throw new Error("Please upload a PDF or TXT file.");
      }
      text = text.replace(/[ \t]+\n/g, "\n").trim();
      if (text.length < 20) throw new Error("No readable text found. This may be a scanned PDF; paste the syllabus text instead.");
      setSyllabus(text); setFileName(file.name); setFileStatus(`${text.length.toLocaleString()} characters extracted`); setNotice("Syllabus text extracted and added to the planner.");
    } catch (e) {
      setFileError(e.message || "Could not read that file."); setFileStatus(""); setFileName("");
    }
  }

  async function generatePlan(useDemo = false) {
    setError(""); setNotice("");
    if (syllabus.trim().length < 20) { setError("Paste or upload your syllabus first."); return; }
    if (!examDate) { setError("Choose your exam date."); return; }
    setLoading(true);
    try {
      let result;
      if (useDemo) {
        await new Promise(resolve => setTimeout(resolve, 350));
        result = makeDemoPlan(syllabus, examDate, Number(dailyHours), studyDays);
      } else {
        const response = await fetch("/api/generate-plan", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ syllabus, examDate, dailyHours: Number(dailyHours), studyDays, confidence, startDate: todayISO() })
        });
        result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not generate your plan.");
      }
      setPlan(result); setDoneTasks({}); setSelectedDay(0); setShowSetup(false); setActiveTab("planner");
      setNotice(useDemo ? "Demo plan created locally. No AI API was called." : "Your plan was generated by the live Gemini AI model.");
    } catch (e) {
      setError(e.message || "Something went wrong.");
    } finally { setLoading(false); }
  }

  async function reschedule() {
    if (!plan) return;
    const unfinished = allTasks.filter(t => !doneTasks[t.id]);
    if (!unfinished.length) { setNotice("Everything is complete — nothing to reschedule."); return; }
    setError(""); setNotice(""); setRescheduling(true);
    try {
      const response = await fetch("/api/reschedule", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan, unfinished, newExamDate: examDate, dailyHours: Number(dailyHours) })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Could not reschedule.");
      setPlan({ ...plan, days: result.days, overview: `${plan.overview || ""}\n\nReschedule: ${result.message || "Unfinished tasks reorganized."}` });
      setDoneTasks({}); setSelectedDay(0); setNotice(result.message || "Unfinished tasks have been rescheduled.");
    } catch (e) { setError(e.message || "Rescheduling failed."); }
    finally { setRescheduling(false); }
  }

  function toggleTask(id) { setDoneTasks(prev => ({ ...prev, [id]: !prev[id] })); }
  function resetPlan() { setPlan(null); setDoneTasks({}); setShowSetup(true); setError(""); setNotice(""); }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><BrainCircuit size={22}/></div><div><b>study buddy</b><span>YOUR PERSONAL STUDY COACH</span></div></div>
        <div className="nav-label">WORKSPACE</div>
        <button className={`nav-item ${activeTab === "planner" ? "active" : ""}`} onClick={() => setActiveTab("planner")}><LayoutDashboard size={18}/> Study planner</button>
        <button className={`nav-item ${activeTab === "progress" ? "active" : ""}`} onClick={() => setActiveTab("progress")}><Target size={18}/> My progress</button>
        <button className={`nav-item ${activeTab === "settings" ? "active" : ""}`} onClick={() => setActiveTab("settings")}><CircleHelp size={18}/> How it works</button>
        <div className="sidebar-bottom">
          <div className="coach-card"><div className="coach-icon"><Sparkles size={17}/></div><b>A little every day.</b><p>Small, focused sessions add up to big results.</p></div>
          <div className={`ai-status ${aiStatus.aiConfigured ? "online" : "offline"}`}><span className="status-dot"/><span>{aiStatus.aiConfigured ? "Gemini AI connected" : "AI key not configured"}</span></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <b>{activeTab === "planner" ? "Study planner" : activeTab === "progress" ? "My progress" : "How it works"}</b></div><div className="topbar-right"><span className="today-label"><CalendarDays size={15}/>{new Date().toLocaleDateString("en-IN",{day:"numeric",month:"short",year:"numeric"})}</span><div className="avatar">S</div></div></header>

        {activeTab === "settings" ? <section className="page-content">
          <div className="eyebrow"><Sparkles size={15}/> ABOUT STUDY BUDDY</div><h1>How your study coach works</h1><p className="lead">Turn your syllabus into a realistic plan, then adjust it as you go.</p>
          <div className="info-grid">
            <article className="info-card"><div className="step-icon purple"><FileUp/></div><h3>1. Add your syllabus</h3><p>Upload a text-based PDF or TXT file, or paste the syllabus directly. PDF text is extracted in your browser.</p></article>
            <article className="info-card"><div className="step-icon blue"><BrainCircuit/></div><h3>2. Generate with AI</h3><p>With a Gemini API key configured, the backend asks Gemini to prioritize topics and create a dated schedule. Demo mode is rule-based and is clearly labelled.</p></article>
            <article className="info-card"><div className="step-icon green"><CheckCircle2/></div><h3>3. Track and adapt</h3><p>Tick off sessions as you complete them. Progress is stored in this browser. Use smart rescheduling to ask AI to reorganize unfinished tasks.</p></article>
          </div>
          <div className="notice-box"><b>Privacy note</b><p>Your syllabus is sent to Google Gemini only when you generate or reschedule using live AI. Your API key stays in the local backend environment and is never included in browser code.</p></div>
          <div className="notice-box"><b>AI configuration</b><p>{aiStatus.aiConfigured ? `Live AI is configured (${aiStatus.provider}, ${aiStatus.model}).` : "Live AI is not configured yet. Copy .env.example to .env, add GEMINI_API_KEY, and restart the server."}</p></div>
        </section> : activeTab === "progress" ? <section className="page-content">
          <div className="eyebrow"><Target size={15}/> YOUR MOMENTUM</div><h1>Progress at a glance</h1><p className="lead">Every completed session is a step closer to exam day.</p>
          {!plan ? <div className="empty-state"><BookOpen size={34}/><h3>Your progress starts with a plan</h3><p>Create a study plan to see your completed sessions here.</p><button className="primary-btn" onClick={() => {setActiveTab("planner");setShowSetup(true)}}>Create a plan <ArrowRight size={16}/></button></div> :
          <><div className="stats-grid"><div className="stat-card"><span>Tasks completed</span><strong>{completedCount}<small> / {allTasks.length}</small></strong><div className="progress-track"><div style={{width:`${progress}%`}}/></div></div><div className="stat-card"><span>Overall progress</span><strong>{progress}%</strong><div className="progress-track"><div style={{width:`${progress}%`}}/></div></div><div className="stat-card"><span>Days to exam</span><strong>{daysLeft}</strong><small>days remaining</small></div></div><div className="section-card"><h3>Topic priorities</h3>{(plan.topics || []).map((topic,i)=><div className="topic-row" key={`${topic.name}-${i}`}><div><b>{topic.name}</b><small>{topic.reason}</small></div><span className={`priority ${String(topic.priority||"Medium").toLowerCase()}`}>{topic.priority || "Medium"}</span></div>)}</div></>}
        </section> : <section className="page-content">
          <div className="hero-row"><div><div className="eyebrow"><Sparkles size={15}/> YOUR PERSONAL STUDY COACH</div><h1>Make your next exam<br/><span>your best one yet.</span></h1><p className="lead">A focused plan, built around your syllabus and your schedule.</p></div><div className="hero-art"><div className="art-orbit orbit-one"/><div className="art-orbit orbit-two"/><div className="art-book"><GraduationCap size={48}/></div><div className="float-pill pill-one"><Check size={14}/> One step at a time</div><div className="float-pill pill-two"><Flame size={14}/> Build your streak</div></div></div>

          <div className="quick-stats">
            <div className="quick-stat"><div className="quick-icon violet"><CalendarDays size={18}/></div><div><span>EXAM COUNTDOWN</span><b>{plan ? daysLeft : "—"} <small>{plan ? "days left" : "Set your exam date"}</small></b></div></div>
            <div className="quick-stat"><div className="quick-icon blue"><Clock3 size={18}/></div><div><span>DAILY STUDY GOAL</span><b>{dailyHours} <small>hours / day</small></b></div></div>
            <div className="quick-stat"><div className="quick-icon green"><CheckCircle2 size={18}/></div><div><span>YOUR PROGRESS</span><b>{plan ? `${progress}%` : "Ready when you are"} <small>{plan ? `${completedCount} tasks done` : "Let's get started"}</small></b></div></div>
          </div>

          {showSetup || !plan ? <div className="section-card setup-card">
            <div className="section-heading"><div><div className="eyebrow small-eyebrow">LET'S GET ORGANIZED</div><h2>Build your study plan</h2><p>Tell us what you're studying and when your exam is.</p></div><div className="heading-icon"><WandSparkles size={21}/></div></div>
            <label className="field-label">Your syllabus <span>Required</span></label>
            <div className="upload-panel">
              <label className="upload-drop"><input type="file" accept=".pdf,.txt,application/pdf,text/plain" onChange={e => readFile(e.target.files?.[0])}/><div className="upload-icon"><UploadCloud size={23}/></div><b>Click to upload your syllabus</b><span>PDF or TXT · text-based PDF recommended</span></label>
              {fileName && <div className="file-chip"><FileText size={16}/><div><b>{fileName}</b><small>{fileStatus}</small></div><button title="Remove uploaded file" onClick={() => {setFileName("");setFileStatus("");setFileError("")}}><X size={16}/></button></div>}
              {fileStatus && !fileName && <div className="file-status">{fileStatus}</div>}
              {fileError && <div className="inline-error">{fileError}</div>}
              <div className="or-divider"><span>OR PASTE YOUR SYLLABUS</span></div>
              <textarea value={syllabus} onChange={e=>{setSyllabus(e.target.value);setFileError("");}} placeholder="Paste your syllabus here… include units, topics, and subtopics for the best plan." rows={6}/>
              <div className="textarea-footer"><span>{syllabus.length.toLocaleString()} characters</span><button className="text-btn" onClick={()=>{setSyllabus(sampleSyllabus);setFileName("");setFileStatus("");setFileError("");}}>Use sample syllabus</button></div>
            </div>
            <div className="form-grid">
              <div className="field"><label className="field-label">Exam date</label><input type="date" min={todayISO()} value={examDate} onChange={e=>setExamDate(e.target.value)}/></div>
              <div className="field"><label className="field-label">Daily study time <b>{dailyHours} hours</b></label><input type="range" min="1" max="8" value={dailyHours} onChange={e=>setDailyHours(Number(e.target.value))}/><div className="range-labels"><span>1 hour</span><span>8 hours</span></div></div>
            </div>
            <div className="field days-field"><label className="field-label">Which days can you study?</label><div className="day-chips">{weekdays.map(day=><button key={day} className={studyDays.includes(day)?"selected":""} onClick={()=>setStudyDays(prev=>prev.includes(day)?prev.filter(x=>x!==day):[...prev,day])}>{day.slice(0,3)}</button>)}</div></div>
            <div className="field"><label className="field-label">Topics you find difficult <span>Optional</span></label><input value={confidence} onChange={e=>setConfidence(e.target.value)} placeholder="e.g. Unit 3, parsing, formulas, long-answer questions"/></div>
            {error && <div className="error-banner"><X size={17}/>{error}</div>}{notice && <div className="success-banner"><CheckCircle2 size={17}/>{notice}</div>}
            <div className="generate-row"><div className="ai-note"><BrainCircuit size={18}/><div><b>{aiStatus.aiConfigured ? "AI is ready to help" : "Set up AI for personalized plans"}</b><span>{aiStatus.aiConfigured ? "Powered by Google Gemini" : "Demo mode is available without an API key"}</span></div></div><div className="generate-actions"><button className="secondary-btn" disabled={loading} onClick={()=>generatePlan(true)}>Try demo</button><button className="primary-btn" disabled={loading} onClick={()=>generatePlan(false)}>{loading ? <><LoaderCircle className="spin" size={17}/> Generating…</> : <><Sparkles size={17}/> Generate with AI</>}</button></div></div>
          </div> : <div className="section-card plan-card">
            <div className="section-heading"><div><div className="eyebrow small-eyebrow">YOUR PLAN IS READY</div><h2>{plan.planTitle || "Your study schedule"}</h2><p>{plan.overview}</p></div><div className="heading-icon"><CheckCircle2 size={21}/></div></div>
            <div className="plan-meta"><span className={`mode-badge ${plan.ai?.mode === "live" ? "live" : "demo"}`}><span className="status-dot"/>{plan.ai?.mode === "live" ? `AI-generated · ${plan.ai.model || "Gemini"}` : "Demo mode · no AI call"}</span><span><Target size={15}/>{plan.topics?.length || 0} topics detected</span><span><CalendarDays size={15}/>{plan.days?.length || 0} study days</span></div>
            <div className="plan-progress"><div><b>Overall progress</b><span>{completedCount} of {allTasks.length} tasks completed</span></div><strong>{progress}%</strong><div className="progress-track"><div style={{width:`${progress}%`}}/></div></div>
            <div className="schedule-layout"><div className="day-list"><div className="list-title">YOUR SCHEDULE</div>{plan.days.map((day,i)=><button key={`${day.date}-${i}`} className={`day-option ${selectedDay===i?"selected":""}`} onClick={()=>setSelectedDay(i)}><div className="day-date">{fmtDate(day.date)}</div><b>{day.title}</b><small>{(day.tasks||[]).filter(t=>doneTasks[t.id]).length}/{(day.tasks||[]).length} tasks done</small></button>)}</div>
              <div className="day-detail">{currentDay ? <><div className="day-detail-top"><div><span className="day-kicker">{fmtDate(currentDay.date)}</span><h3>{currentDay.title}</h3><p>{currentDay.summary}</p></div><span className="day-duration"><Clock3 size={15}/>{Math.round((currentDay.tasks||[]).reduce((s,t)=>s+t.minutes,0)/60*10)/10}h</span></div><div className="task-list">{(currentDay.tasks||[]).map(task=><label className={`task-item ${doneTasks[task.id]?"is-done":""}`} key={task.id}><input type="checkbox" checked={Boolean(doneTasks[task.id])} onChange={()=>toggleTask(task.id)}/><span className="custom-check"><Check size={13}/></span><div className="task-main"><b>{task.title}</b><small>{task.topic}{task.reason?` · ${task.reason}`:""}</small><span className={`task-type ${task.type}`}>{task.type}</span></div><span className="task-minutes">{task.minutes} min</span></label>)}</div>{!currentDay.tasks?.length&&<p className="muted">No tasks scheduled for this day.</p>}</> : <p>No schedule days found.</p>}</div></div>
            {plan.studyTips?.length>0&&<div className="tips-strip"><div className="tips-icon"><Sparkles size={17}/></div><div><b>Study smarter</b><p>{plan.studyTips[0]}</p></div></div>}
            {error && <div className="error-banner">{error}</div>}{notice && <div className="success-banner"><CheckCircle2 size={17}/>{notice}</div>}
            <div className="plan-actions"><button className="secondary-btn" onClick={resetPlan}>Edit inputs</button><button className="secondary-btn" disabled={rescheduling} onClick={reschedule}>{rescheduling?<LoaderCircle className="spin" size={16}/>:<RefreshCw size={16}/>} Reschedule unfinished</button><button className="primary-btn" onClick={()=>{setShowSetup(true);window.scrollTo({top:0,behavior:"smooth"})}}>Create new plan <ArrowRight size={16}/></button></div>
          </div>}
          <div className="footer-note"><span><ShieldCheckIcon/> Your progress is saved in this browser.</span><span>Built to help you learn, not just plan.</span></div>
        </section>}
      </main>
    </div>
  );
}

function ShieldCheckIcon() { return <CheckCircle2 size={14}/>; }

createRoot(document.getElementById("root")).render(<App />);
