import React, { useMemo, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  Check,
  Clock3,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  XCircle,
} from "lucide-react";
import type {
  PlanSummary,
  ScheduleReport,
  SessionStatus,
  StudySession,
} from "../types/api";

function formatDayLabel(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function formatOffsetRange(startOffset: number, duration: number): string {
  const fmt = (mins: number) => {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `+${h}h ${m.toString().padStart(2, "0")}m`;
  };
  return `${fmt(startOffset)} – ${fmt(startOffset + duration)}`;
}

interface ScheduleViewProps {
  schedule: ScheduleReport | null;
  plans: PlanSummary[];
  busy: boolean;
  onRecalculate: () => Promise<void>;
  onUpdateSession: (sessionId: number, status: SessionStatus) => Promise<void>;
}

export const ScheduleView: React.FC<ScheduleViewProps> = ({
  schedule,
  plans,
  busy,
  onRecalculate,
  onUpdateSession,
}) => {
  const [selectedPlanId, setSelectedPlanId] = useState<number | "all">("all");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const activePlans = useMemo(
    () => plans.filter((p) => p.status === "active"),
    [plans]
  );

  const filteredSessions = useMemo(() => {
    const all = schedule?.sessions ?? [];
    if (selectedPlanId === "all") return all;
    return all.filter((s) => s.plan_id === selectedPlanId);
  }, [schedule, selectedPlanId]);

  const activePlanFeasibility = useMemo(() => {
    if (selectedPlanId === "all" || !schedule) return null;
    return schedule.per_plan.find((p) => p.plan_id === selectedPlanId) ?? null;
  }, [schedule, selectedPlanId]);

  const groupedDays = useMemo(() => {
    const map = new Map<string, StudySession[]>();
    for (const s of filteredSessions) {
      const list = map.get(s.scheduled_date) ?? [];
      list.push(s);
      map.set(s.scheduled_date, list);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [filteredSessions]);

  const activeDay = useMemo(() => {
    if (!groupedDays.length) return null;
    if (selectedDate) {
      const found = groupedDays.find(([d]) => d === selectedDate);
      if (found) return found;
    }
    return groupedDays[0];
  }, [groupedDays, selectedDate]);

  if (!schedule) {
    return (
      <div className="empty-state">
        <LoaderCircle size={24} className="spin" />
        <h3>Loading global schedule…</h3>
      </div>
    );
  }

  return (
    <div>
      {!schedule.is_feasible && (
        <div className="overload-banner" role="alert">
          <div className="overload-header">
            <AlertTriangle size={18} />
            <b>
              Schedule Overload Warning — Short by {schedule.deficit_minutes} min (
              {(schedule.deficit_minutes / 60).toFixed(1)} hrs)
            </b>
          </div>
          <ul>
            {schedule.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
          {schedule.suggestions.length > 0 && (
            <div className="overload-suggestions">
              <b>Suggested fixes:</b>
              <ul>
                {schedule.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="section-card">
        <div className="section-heading">
          <div>
            <div className="eyebrow small-eyebrow">
              <CalendarDays size={12} />{" "}
              {activePlanFeasibility
                ? `SUBJECT SCHEDULE · EXAM ${activePlanFeasibility.exam_date}`
                : "UNIFIED MULTI-SUBJECT TIMETABLE"}
            </div>
            <h2>
              {activePlanFeasibility
                ? activePlanFeasibility.subject_name
                : "Shared-Capacity Schedule"}
            </h2>
            <p>
              {activePlanFeasibility ? (
                <>
                  Required: {(activePlanFeasibility.required_minutes / 60).toFixed(1)}h ·
                  Scheduled: {(activePlanFeasibility.scheduled_minutes / 60).toFixed(1)}h
                  {activePlanFeasibility.deficit_minutes > 0
                    ? ` · Deficit: ${(activePlanFeasibility.deficit_minutes / 60).toFixed(1)}h`
                    : " · On track"}
                </>
              ) : (
                <>
                  Required: {(schedule.total_required_minutes / 60).toFixed(1)}h ·
                  Scheduled: {(schedule.total_scheduled_minutes / 60).toFixed(1)}h ·
                  Available: {(schedule.total_available_minutes / 60).toFixed(1)}h
                </>
              )}
            </p>
          </div>
          <button
            type="button"
            className="secondary-btn"
            onClick={onRecalculate}
            disabled={busy}
          >
            <RefreshCw size={14} className={busy ? "spin" : ""} /> Recalculate
          </button>
        </div>

        {activePlans.length > 0 && (
          <div className="subject-filter-bar" role="tablist" aria-label="Filter schedule by subject">
            <button
              type="button"
              role="tab"
              aria-selected={selectedPlanId === "all"}
              className={`filter-pill ${selectedPlanId === "all" ? "active" : ""}`}
              onClick={() => {
                setSelectedPlanId("all");
                setSelectedDate(null);
              }}
            >
              All Subjects
              <span className="filter-count">{schedule.sessions.length}</span>
            </button>
            {activePlans.map((plan) => {
              const count = schedule.sessions.filter((s) => s.plan_id === plan.id).length;
              return (
                <button
                  key={plan.id}
                  type="button"
                  role="tab"
                  aria-selected={selectedPlanId === plan.id}
                  className={`filter-pill ${selectedPlanId === plan.id ? "active" : ""}`}
                  onClick={() => {
                    setSelectedPlanId(plan.id);
                    setSelectedDate(null);
                  }}
                >
                  <span
                    className="subject-dot"
                    style={{ backgroundColor: plan.color || "#6d5ce8" }}
                  />
                  {plan.subject_name}
                  <span className="filter-count">{count}</span>
                </button>
              );
            })}
          </div>
        )}

        {groupedDays.length === 0 ? (
          <div className="empty-state">
            <CalendarDays size={28} />
            <h3>No scheduled sessions yet</h3>
            <p>
              Add a subject plan with topics under the Subjects tab to generate your
              shared timetable.
            </p>
          </div>
        ) : (
          <div className="schedule-layout">
            <div className="day-list">
              <div className="list-title">STUDY DAYS ({groupedDays.length})</div>
              {groupedDays.map(([dayIso, daySessions]) => {
                const totalMins = daySessions.reduce(
                  (acc, s) => acc + s.duration_minutes,
                  0
                );
                const doneCount = daySessions.filter(
                  (s) => s.status === "completed"
                ).length;
                const isSelected = activeDay?.[0] === dayIso;
                return (
                  <button
                    key={dayIso}
                    type="button"
                    className={`day-option ${isSelected ? "selected" : ""}`}
                    onClick={() => setSelectedDate(dayIso)}
                  >
                    <div className="day-date">{formatDayLabel(dayIso)}</div>
                    <b>
                      {daySessions.length} session
                      {daySessions.length === 1 ? "" : "s"}
                    </b>
                    <small>
                      {totalMins} min · {doneCount}/{daySessions.length} done
                    </small>
                  </button>
                );
              })}
            </div>

            {activeDay && (
              <div className="day-detail">
                <div className="day-detail-top">
                  <div>
                    <div className="day-kicker">{activeDay[0]}</div>
                    <h3>{formatDayLabel(activeDay[0])}</h3>
                    <p>
                      Mark sessions completed or missed—remaining work automatically
                      rebalances across your shared capacity.
                    </p>
                  </div>
                  <div className="day-duration">
                    <Clock3 size={14} />
                    {activeDay[1].reduce((a, b) => a + b.duration_minutes, 0)} min
                  </div>
                </div>

                <div className="task-list">
                  {activeDay[1].map((session) => (
                    <div
                      key={session.id}
                      className={`session-row status-${session.status}`}
                    >
                      <span
                        className="subject-bar"
                        style={{ backgroundColor: session.plan_color || "#6d5ce8" }}
                      />
                      <div className="task-main">
                        <div className="session-title-line">
                          <b>{session.topic_name}</b>
                          <span className="subject-chip">{session.subject_name}</span>
                        </div>
                        <small>
                          Slot {formatOffsetRange(session.start_offset_minutes, session.duration_minutes)}{" "}
                          · {session.duration_minutes} min · Priority {session.priority}/5
                        </small>
                        <div className="session-tags">
                          <span className={`priority ${session.difficulty}`}>
                            {session.difficulty}
                          </span>
                          <span className={`status-pill ${session.status}`}>
                            {session.status}
                          </span>
                        </div>
                      </div>

                      <div className="session-actions">
                        {session.status !== "completed" && (
                          <button
                            type="button"
                            className="mini-btn success"
                            disabled={busy}
                            onClick={() => onUpdateSession(session.id, "completed")}
                          >
                            <Check size={12} /> Complete
                          </button>
                        )}
                        {session.status !== "missed" && (
                          <button
                            type="button"
                            className="mini-btn danger"
                            disabled={busy}
                            onClick={() => onUpdateSession(session.id, "missed")}
                          >
                            <XCircle size={12} /> Missed
                          </button>
                        )}
                        {session.status !== "pending" && (
                          <button
                            type="button"
                            className="mini-btn"
                            disabled={busy}
                            onClick={() => onUpdateSession(session.id, "pending")}
                          >
                            <RotateCcw size={12} /> Reset
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
