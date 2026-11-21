import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  Clock3,
  GraduationCap,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import { api, ApiError } from "./api/client";
import { CapacityCard } from "./components/CapacityCard";
import { ScheduleView } from "./components/ScheduleView";
import { SubjectsView } from "./components/SubjectsView";
import type {
  Difficulty,
  HealthResponse,
  PlanDetail,
  PlanSummary,
  ScheduleReport,
  SessionStatus,
  UserSettings,
  UserSettingsUpdate,
} from "./types/api";

type TabId = "schedule" | "subjects" | "capacity";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabId>("schedule");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<PlanDetail | null>(null);
  const [schedule, setSchedule] = useState<ScheduleReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refreshAll = useCallback(async (keepPlanId?: number) => {
    const [h, s, p, sc] = await Promise.all([
      api.getHealth(),
      api.getSettings(),
      api.listPlans(),
      api.getSchedule(),
    ]);
    setHealth(h);
    setSettings(s);
    setPlans(p);
    setSchedule(sc);

    const targetId = keepPlanId ?? selectedPlan?.id;
    if (targetId && p.some((item) => item.id === targetId)) {
      const detail = await api.getPlan(targetId);
      setSelectedPlan(detail);
    } else if (p.length > 0 && !targetId) {
      setSelectedPlan(await api.getPlan(p[0].id));
    } else if (!p.some((item) => item.id === targetId)) {
      setSelectedPlan(null);
    }
  }, [selectedPlan?.id]);

  useEffect(() => {
    refreshAll().catch((err) => {
      setError(
        err instanceof Error
          ? `Could not connect to FastAPI backend: ${err.message}`
          : "Could not connect to FastAPI backend."
      );
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runAction(fn: () => Promise<void>, successMessage?: string) {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await fn();
      if (successMessage) setNotice(successMessage);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveSettings(update: UserSettingsUpdate) {
    await runAction(async () => {
      const updated = await api.updateSettings(update);
      setSettings(updated);
      setSchedule(await api.getSchedule());
    }, "Shared study capacity saved and global schedule recalculated.");
  }

  async function handleCreatePlan(payload: {
    subject_name: string;
    exam_date: string;
    color: string;
    file?: File | null;
    rawText?: string;
    extractWithAI: boolean;
  }) {
    await runAction(async () => {
      const created = await api.createPlan({
        subject_name: payload.subject_name,
        exam_date: payload.exam_date,
        color: payload.color,
      });

      if (payload.extractWithAI && (payload.file || payload.rawText?.trim())) {
        await api.extractSyllabusForPlan(created.id, {
          file: payload.file,
          rawText: payload.rawText,
        });
      }
      await refreshAll(created.id);
      setActiveTab("schedule");
    }, `Added subject "${payload.subject_name}" and updated global schedule.`);
  }

  async function handleSelectPlan(planId: number) {
    await runAction(async () => {
      setSelectedPlan(await api.getPlan(planId));
    });
  }

  async function handleArchiveToggle(plan: PlanSummary) {
    const nextStatus = plan.status === "archived" ? "active" : "archived";
    await runAction(async () => {
      await api.updatePlan(plan.id, { status: nextStatus });
      await refreshAll(plan.id);
    }, `"${plan.subject_name}" marked ${nextStatus}. Schedule recalculated.`);
  }

  async function handleDeletePlan(planId: number) {
    await runAction(async () => {
      await api.deletePlan(planId);
      await refreshAll();
    }, "Subject plan deleted and global schedule recalculated.");
  }

  async function handleAddManualTopic(
    planId: number,
    topic: {
      name: string;
      difficulty: Difficulty;
      priority: number;
      estimated_minutes: number;
    }
  ) {
    await runAction(async () => {
      await api.addTopic(planId, topic);
      await refreshAll(planId);
    }, `Added topic "${topic.name}" and recalculated schedule.`);
  }

  async function handleDeleteTopic(planId: number, topicId: number) {
    await runAction(async () => {
      await api.deleteTopic(planId, topicId);
      await refreshAll(planId);
    }, "Topic removed and schedule recalculated.");
  }

  async function handleRecalculate() {
    await runAction(async () => {
      setSchedule(await api.recalculateSchedule());
    }, "Global schedule recalculated.");
  }

  async function handleUpdateSession(sessionId: number, status: SessionStatus) {
    await runAction(async () => {
      const res = await api.updateSessionStatus(sessionId, status);
      setSchedule(res.schedule);
      setPlans(await api.listPlans());
      if (selectedPlan) {
        setSelectedPlan(await api.getPlan(selectedPlan.id));
      }
    }, `Session marked ${status} and schedule updated.`);
  }

  const activePlansCount = plans.filter((p) => p.status === "active").length;
  const totalSessions = schedule?.sessions.length ?? 0;
  const completedSessions =
    schedule?.sessions.filter((s) => s.status === "completed").length ?? 0;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <GraduationCap size={20} />
          </div>
          <div>
            <b>Study Buddy</b>
            <span>MULTI-SUBJECT AI PLANNER</span>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>
        <button
          type="button"
          className={`nav-item ${activeTab === "schedule" ? "active" : ""}`}
          onClick={() => setActiveTab("schedule")}
        >
          <CalendarDays size={16} /> Global Schedule
        </button>
        <button
          type="button"
          className={`nav-item ${activeTab === "subjects" ? "active" : ""}`}
          onClick={() => setActiveTab("subjects")}
        >
          <BookOpen size={16} /> Subjects & Syllabi
        </button>
        <button
          type="button"
          className={`nav-item ${activeTab === "capacity" ? "active" : ""}`}
          onClick={() => setActiveTab("capacity")}
        >
          <SlidersHorizontal size={16} /> Shared Capacity
        </button>

        <div className="sidebar-bottom">
          <div className="coach-card">
            <div className="coach-icon">
              <Sparkles size={15} />
            </div>
            <b>Hybrid AI + Math</b>
            <p>
              LLMs extract syllabus topics; deterministic Python enforces shared
              daily limits & exam deadlines.
            </p>
          </div>

          <div className={`ai-status ${health?.ai_configured ? "online" : ""}`}>
            <span className="status-dot" />
            <span>
              {health
                ? `API v${health.version} · ${health.ai_provider.toUpperCase()} ${
                    health.ai_configured ? "Ready" : "(No Key)"
                  }`
                : "Connecting to FastAPI…"}
            </span>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            Study Buddy <span>/</span>{" "}
            <b>
              {activeTab === "schedule"
                ? "Global Schedule"
                : activeTab === "subjects"
                ? "Subjects & Syllabi"
                : "Shared Capacity"}
            </b>
          </div>
          <div className="topbar-right">
            <div className="today-label">
              <Clock3 size={14} />
              <span>
                {settings
                  ? `${(settings.daily_study_minutes / 60).toFixed(1)}h / day shared cap`
                  : "Loading…"}
              </span>
            </div>
            <div className="avatar">SB</div>
          </div>
        </header>

        <div className="page-content">
          <div className="quick-stats">
            <div className="quick-stat">
              <div className="quick-icon violet">
                <BookOpen size={18} />
              </div>
              <div>
                <span>ACTIVE SUBJECTS</span>
                <b>
                  {activePlansCount} <small>of {plans.length} plans</small>
                </b>
              </div>
            </div>

            <div className="quick-stat">
              <div className="quick-icon blue">
                <Clock3 size={18} />
              </div>
              <div>
                <span>SHARED DAILY CAP</span>
                <b>
                  {settings ? `${settings.daily_study_minutes}m` : "—"}{" "}
                  <small>
                    {settings ? `${settings.preferred_study_days.length} days/wk` : ""}
                  </small>
                </b>
              </div>
            </div>

            <div className="quick-stat">
              <div className="quick-icon green">
                {schedule && !schedule.is_feasible ? (
                  <AlertTriangle size={18} />
                ) : (
                  <CheckCircle2 size={18} />
                )}
              </div>
              <div>
                <span>TIMETABLE STATUS</span>
                <b>
                  {schedule
                    ? schedule.is_feasible
                      ? "Feasible"
                      : `-${schedule.deficit_minutes}m`
                    : "—"}{" "}
                  <small>
                    {completedSessions}/{totalSessions} sessions
                  </small>
                </b>
              </div>
            </div>
          </div>

          {error && (
            <div className="error-banner" role="alert">
              <AlertTriangle size={15} /> {error}
            </div>
          )}
          {notice && (
            <div className="success-banner" role="status">
              <CheckCircle2 size={15} /> {notice}
            </div>
          )}

          <div style={{ marginTop: 18 }}>
            {activeTab === "schedule" && (
              <ScheduleView
                schedule={schedule}
                plans={plans}
                busy={busy}
                onRecalculate={handleRecalculate}
                onUpdateSession={handleUpdateSession}
              />
            )}
            {activeTab === "subjects" && (
              <SubjectsView
                plans={plans}
                selectedPlan={selectedPlan}
                busy={busy}
                onSelectPlan={handleSelectPlan}
                onCreatePlan={handleCreatePlan}
                onArchiveToggle={handleArchiveToggle}
                onDeletePlan={handleDeletePlan}
                onAddManualTopic={handleAddManualTopic}
                onDeleteTopic={handleDeleteTopic}
              />
            )}
            {activeTab === "capacity" && (
              <CapacityCard
                settings={settings}
                saving={busy}
                onSave={handleSaveSettings}
              />
            )}
          </div>
        </div>
      </main>
    </div>
  );
};
