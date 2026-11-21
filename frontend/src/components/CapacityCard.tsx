import React, { useEffect, useState } from "react";
import { Clock3, LoaderCircle, Save, SlidersHorizontal } from "lucide-react";
import type { UserSettings, UserSettingsUpdate, WeekdayShort } from "../types/api";

const ALL_DAYS: WeekdayShort[] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface CapacityCardProps {
  settings: UserSettings | null;
  saving: boolean;
  onSave: (update: UserSettingsUpdate) => Promise<void>;
}

export const CapacityCard: React.FC<CapacityCardProps> = ({
  settings,
  saving,
  onSave,
}) => {
  const [dailyMinutes, setDailyMinutes] = useState<number>(240);
  const [maxSession, setMaxSession] = useState<number>(60);
  const [days, setDays] = useState<WeekdayShort[]>([...ALL_DAYS]);

  useEffect(() => {
    if (settings) {
      setDailyMinutes(settings.daily_study_minutes);
      setMaxSession(settings.max_session_minutes);
      setDays(settings.preferred_study_days);
    }
  }, [settings]);

  function toggleDay(day: WeekdayShort) {
    setDays((prev) => {
      if (prev.includes(day)) {
        return prev.length > 1 ? prev.filter((d) => d !== day) : prev;
      }
      return ALL_DAYS.filter((d) => prev.includes(d) || d === day);
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await onSave({
      daily_study_minutes: dailyMinutes,
      max_session_minutes: Math.min(maxSession, dailyMinutes),
      preferred_study_days: days,
    });
  }

  return (
    <form className="section-card" onSubmit={handleSubmit}>
      <div className="section-heading">
        <div>
          <div className="eyebrow small-eyebrow">
            <SlidersHorizontal size={12} /> SHARED CAPACITY
          </div>
          <h2>Combined Daily Study Limit</h2>
          <p>
            All active subject plans share this single daily capacity and weekday
            availability. Saving automatically recalculates your global schedule.
          </p>
        </div>
        <div className="heading-icon">
          <Clock3 size={18} />
        </div>
      </div>

      <div className="form-grid">
        <div className="field">
          <label className="field-label">
            Daily study budget (all subjects combined)
            <b>
              {dailyMinutes} min ({(dailyMinutes / 60).toFixed(1)} hrs/day)
            </b>
          </label>
          <input
            type="range"
            min={30}
            max={720}
            step={15}
            value={dailyMinutes}
            onChange={(e) => setDailyMinutes(Number(e.target.value))}
          />
          <div className="range-labels">
            <span>30m</span>
            <span>4h</span>
            <span>8h</span>
            <span>12h</span>
          </div>
        </div>

        <div className="field">
          <label className="field-label">
            Max focus block length
            <b>{maxSession} min</b>
          </label>
          <input
            type="range"
            min={15}
            max={180}
            step={15}
            value={maxSession}
            onChange={(e) => setMaxSession(Number(e.target.value))}
          />
          <div className="range-labels">
            <span>15m</span>
            <span>60m</span>
            <span>120m</span>
            <span>180m</span>
          </div>
        </div>
      </div>

      <div className="days-field">
        <div className="field-label">
          Preferred study days <span>{days.length} days / week</span>
        </div>
        <div className="day-chips">
          {ALL_DAYS.map((day) => (
            <button
              key={day}
              type="button"
              className={days.includes(day) ? "selected" : ""}
              onClick={() => toggleDay(day)}
            >
              {day}
            </button>
          ))}
        </div>
      </div>

      <div className="generate-row">
        <div className="ai-note">
          <Clock3 size={16} />
          <div>
            <b>Deterministic enforcement</b>
            <span>
              The Python scheduler guarantees sessions never exceed {dailyMinutes}{" "}
              min/day or overlap.
            </span>
          </div>
        </div>
        <div className="generate-actions">
          <button type="submit" className="primary-btn" disabled={saving}>
            {saving ? <LoaderCircle size={15} className="spin" /> : <Save size={15} />}
            {saving ? "Recalculating…" : "Save & Recalculate"}
          </button>
        </div>
      </div>
    </form>
  );
};
