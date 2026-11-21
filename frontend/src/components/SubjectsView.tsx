import React, { useState } from "react";
import {
  Archive,
  BookOpen,
  CalendarDays,
  FileUp,
  LoaderCircle,
  Plus,
  RotateCcw,
  Sparkles,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import type { Difficulty, PlanDetail, PlanSummary } from "../types/api";

const SUBJECT_COLORS = ["#6d5ce8", "#2563eb", "#059669", "#d97706", "#db2777", "#0891b2"];

const SAMPLE_SYLLABUS = `Natural Language Processing — Semester VII
Unit I — Word Level Analysis: Morphology, stemming, lemmatization, tokenization, regular expressions, finite state transducers, n-gram language models.
Unit II — Syntactic Analysis: Part-of-Speech tagging, HMM, Conditional Random Fields, Context-Free Grammars, CKY and Earley parsing, PCFG.
Unit III — Semantic Analysis: Lexical semantics, WordNet, Word Sense Disambiguation, distributional similarity.
Unit IV — Deep Learning for NLP: Word embeddings, RNNs, LSTMs, Attention, Transformers, Sentiment Analysis.`;

function defaultExamDate(): string {
  const d = new Date();
  d.setDate(d.getDate() + 14);
  return d.toISOString().slice(0, 10);
}

interface SubjectsViewProps {
  plans: PlanSummary[];
  selectedPlan: PlanDetail | null;
  busy: boolean;
  onSelectPlan: (planId: number) => Promise<void>;
  onCreatePlan: (payload: {
    subject_name: string;
    exam_date: string;
    color: string;
    file?: File | null;
    rawText?: string;
    extractWithAI: boolean;
  }) => Promise<void>;
  onArchiveToggle: (plan: PlanSummary) => Promise<void>;
  onDeletePlan: (planId: number) => Promise<void>;
  onAddManualTopic: (
    planId: number,
    topic: { name: string; difficulty: Difficulty; priority: number; estimated_minutes: number }
  ) => Promise<void>;
  onDeleteTopic: (planId: number, topicId: number) => Promise<void>;
}

export const SubjectsView: React.FC<SubjectsViewProps> = ({
  plans,
  selectedPlan,
  busy,
  onSelectPlan,
  onCreatePlan,
  onArchiveToggle,
  onDeletePlan,
  onAddManualTopic,
  onDeleteTopic,
}) => {
  const [subjectName, setSubjectName] = useState("");
  const [examDate, setExamDate] = useState(defaultExamDate());
  const [color, setColor] = useState(SUBJECT_COLORS[0]);
  const [file, setFile] = useState<File | null>(null);
  const [rawText, setRawText] = useState("");

  // Manual topic quick-add for selected plan
  const [topicName, setTopicName] = useState("");
  const [topicDifficulty, setTopicDifficulty] = useState<Difficulty>("medium");
  const [topicPriority, setTopicPriority] = useState(3);
  const [topicMinutes, setTopicMinutes] = useState(60);

  async function handleCreateSubmit(e: React.FormEvent, extractWithAI: boolean) {
    e.preventDefault();
    if (!subjectName.trim()) return;
    await onCreatePlan({
      subject_name: subjectName.trim(),
      exam_date: examDate,
      color,
      file,
      rawText,
      extractWithAI,
    });
    setSubjectName("");
    setFile(null);
    setRawText("");
  }

  async function handleAddTopic(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedPlan || !topicName.trim()) return;
    await onAddManualTopic(selectedPlan.id, {
      name: topicName.trim(),
      difficulty: topicDifficulty,
      priority: topicPriority,
      estimated_minutes: topicMinutes,
    });
    setTopicName("");
  }

  return (
    <div>
      <form
        className="section-card"
        onSubmit={(e) => handleCreateSubmit(e, Boolean(file || rawText.trim()))}
      >
        <div className="section-heading">
          <div>
            <div className="eyebrow small-eyebrow">
              <Sparkles size={12} /> NEW SUBJECT PLAN
            </div>
            <h2>Add Subject & Extract Syllabus</h2>
            <p>
              Upload a PDF/TXT syllabus (parsed on the backend with PyMuPDF) or
              paste text. The AI extracts topics, difficulty, and study minutes,
              and the deterministic scheduler allocates time within your shared
              daily capacity.
            </p>
          </div>
          <div className="heading-icon">
            <BookOpen size={18} />
          </div>
        </div>

        <div className="form-grid">
          <div className="field">
            <label className="field-label">Subject name</label>
            <input
              type="text"
              required
              placeholder="e.g. Natural Language Processing"
              value={subjectName}
              onChange={(e) => setSubjectName(e.target.value)}
            />
          </div>
          <div className="field">
            <label className="field-label">Exam date</label>
            <input
              type="date"
              required
              value={examDate}
              onChange={(e) => setExamDate(e.target.value)}
            />
          </div>
        </div>

        <div className="days-field">
          <div className="field-label">Subject color tag</div>
          <div className="color-swatches">
            {SUBJECT_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                className={`color-swatch ${color === c ? "active" : ""}`}
                style={{ backgroundColor: c }}
                onClick={() => setColor(c)}
                aria-label={`Select color ${c}`}
              />
            ))}
          </div>
        </div>

        <div className="days-field">
          <div className="field-label">
            Syllabus PDF / TXT or raw text <span>Optional — can add topics manually</span>
          </div>
          <div className="upload-panel">
            <label className="upload-drop">
              <input
                type="file"
                accept=".pdf,.txt,.md"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              <div className="upload-icon">
                <UploadCloud size={18} />
              </div>
              <b>Click to upload PDF or TXT syllabus</b>
              <span>Extracted server-side via PyMuPDF (max 10 MB)</span>
            </label>

            {file && (
              <div className="file-chip">
                <FileUp size={16} />
                <div>
                  <b>{file.name}</b>
                  <small>{(file.size / 1024).toFixed(1)} KB</small>
                </div>
                <button type="button" onClick={() => setFile(null)} aria-label="Remove file">
                  <X size={14} />
                </button>
              </div>
            )}

            <div className="or-divider">OR PASTE SYLLABUS TEXT</div>
            <textarea
              placeholder="Paste course units, chapters, and topics here…"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
            <div className="textarea-footer">
              <span>{rawText.length} characters</span>
              <button
                type="button"
                className="text-btn"
                onClick={() => {
                  setSubjectName((prev) => prev || "Natural Language Processing");
                  setRawText(SAMPLE_SYLLABUS);
                }}
              >
                Load sample syllabus
              </button>
            </div>
          </div>
        </div>

        <div className="generate-row">
          <div className="ai-note">
            <Sparkles size={16} />
            <div>
              <b>AI Extraction + Deterministic Scheduling</b>
              <span>
                Groq GPT-OSS 20B extracts topics; Python enforces your shared daily cap.
              </span>
            </div>
          </div>
          <div className="generate-actions">
            <button
              type="button"
              className="secondary-btn"
              disabled={busy || !subjectName.trim()}
              onClick={(e) => handleCreateSubmit(e, false)}
            >
              <Plus size={14} /> Create Empty Plan
            </button>
            <button
              type="submit"
              className="primary-btn"
              disabled={busy || !subjectName.trim() || (!file && !rawText.trim())}
            >
              {busy ? <LoaderCircle size={15} className="spin" /> : <Sparkles size={15} />}
              {busy ? "Extracting & Scheduling…" : "Extract with AI & Schedule"}
            </button>
          </div>
        </div>
      </form>

      <div className="section-card">
        <div className="section-heading">
          <div>
            <div className="eyebrow small-eyebrow">
              <CalendarDays size={12} /> SUBJECT PLANS ({plans.length})
            </div>
            <h2>Manage Your Subjects</h2>
          </div>
        </div>

        {plans.length === 0 ? (
          <div className="empty-state">
            <BookOpen size={28} />
            <h3>No subject plans yet</h3>
            <p>Create your first subject plan above to start building your shared timetable.</p>
          </div>
        ) : (
          <div className="plans-grid">
            {plans.map((p) => (
              <div
                key={p.id}
                className={`plan-card ${selectedPlan?.id === p.id ? "selected" : ""} ${
                  p.status === "archived" ? "archived" : ""
                }`}
                onClick={() => onSelectPlan(p.id)}
              >
                <div className="plan-card-top">
                  <span
                    className="subject-dot"
                    style={{ backgroundColor: p.color || "#6d5ce8" }}
                  />
                  <b>{p.subject_name}</b>
                  <span className={`status-pill ${p.status}`}>{p.status}</span>
                </div>
                <div className="plan-card-meta">
                  <span>Exam: {p.exam_date}</span>
                  <span>
                    {p.completed_topic_count}/{p.topic_count} topics ·{" "}
                    {(p.total_estimated_minutes / 60).toFixed(1)}h
                  </span>
                </div>
                <div className="progress-track">
                  <div style={{ width: `${p.progress_percent}%` }} />
                </div>
                <div className="plan-card-actions" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className="mini-btn"
                    onClick={() => onArchiveToggle(p)}
                    disabled={busy}
                  >
                    {p.status === "archived" ? (
                      <>
                        <RotateCcw size={12} /> Restore
                      </>
                    ) : (
                      <>
                        <Archive size={12} /> Archive
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    className="mini-btn danger"
                    onClick={() => onDeletePlan(p.id)}
                    disabled={busy}
                  >
                    <Trash2 size={12} /> Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedPlan && (
        <div className="section-card">
          <div className="section-heading">
            <div>
              <div className="eyebrow small-eyebrow">TOPICS IN SUBJECT</div>
              <h2>{selectedPlan.subject_name}</h2>
              <p>
                Exam on {selectedPlan.exam_date} · {selectedPlan.topics.length} topics ·{" "}
                {(selectedPlan.total_estimated_minutes / 60).toFixed(1)} total hours
              </p>
            </div>
          </div>

          <form className="inline-topic-form" onSubmit={handleAddTopic}>
            <input
              type="text"
              placeholder="Add a topic manually…"
              value={topicName}
              onChange={(e) => setTopicName(e.target.value)}
              required
            />
            <select
              value={topicDifficulty}
              onChange={(e) => setTopicDifficulty(e.target.value as Difficulty)}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
            <select
              value={topicPriority}
              onChange={(e) => setTopicPriority(Number(e.target.value))}
            >
              {[5, 4, 3, 2, 1].map((p) => (
                <option key={p} value={p}>
                  Priority {p}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={15}
              max={600}
              step={15}
              value={topicMinutes}
              onChange={(e) => setTopicMinutes(Number(e.target.value))}
              aria-label="Estimated minutes"
            />
            <button type="submit" className="primary-btn" disabled={busy}>
              <Plus size={14} /> Add
            </button>
          </form>

          {selectedPlan.topics.length === 0 ? (
            <p className="muted">No topics yet. Add one above or extract from a syllabus.</p>
          ) : (
            <div>
              {selectedPlan.topics.map((t) => (
                <div key={t.id} className="topic-row">
                  <div>
                    <b>
                      {t.unit ? `${t.unit}: ` : ""}
                      {t.name} {t.is_completed ? "✓" : ""}
                    </b>
                    <small>
                      {t.estimated_minutes} min · Priority {t.priority}/5
                      {t.subtopics.length > 0 ? ` · ${t.subtopics.join(", ")}` : ""}
                    </small>
                  </div>
                  <div className="topic-row-right">
                    <span className={`priority ${t.difficulty}`}>{t.difficulty}</span>
                    <button
                      type="button"
                      className="mini-btn danger"
                      onClick={() => onDeleteTopic(selectedPlan.id, t.id)}
                      disabled={busy}
                      aria-label={`Delete ${t.name}`}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
