import type {
  HealthResponse,
  PlanCreate,
  PlanDetail,
  PlanStatus,
  PlanSummary,
  PlanUpdate,
  ScheduleReport,
  SessionStatus,
  SessionUpdateResponse,
  Topic,
  TopicCreate,
  UserSettings,
  UserSettingsUpdate,
} from "../types/api";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      } else if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
        detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
      }
    } catch {
      // ignore JSON parse failure
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const api = {
  getHealth: () => request<HealthResponse>("/api/health"),

  getSettings: () => request<UserSettings>("/api/settings"),

  updateSettings: (payload: UserSettingsUpdate) =>
    request<UserSettings>("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  listPlans: (status?: PlanStatus) =>
    request<PlanSummary[]>(status ? `/api/plans?status=${status}` : "/api/plans"),

  getPlan: (planId: number) => request<PlanDetail>(`/api/plans/${planId}`),

  createPlan: (payload: PlanCreate) =>
    request<PlanDetail>("/api/plans", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  updatePlan: (planId: number, payload: PlanUpdate) =>
    request<PlanDetail>(`/api/plans/${planId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  deletePlan: (planId: number) =>
    request<void>(`/api/plans/${planId}`, { method: "DELETE" }),

  addTopic: (planId: number, payload: TopicCreate) =>
    request<Topic>(`/api/plans/${planId}/topics`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  deleteTopic: (planId: number, topicId: number) =>
    request<void>(`/api/plans/${planId}/topics/${topicId}`, { method: "DELETE" }),

  extractSyllabusForPlan: (
    planId: number,
    opts: { file?: File | null; rawText?: string; provider?: "groq" | "gemini" }
  ) => {
    const form = new FormData();
    if (opts.file) form.append("file", opts.file);
    if (opts.rawText && opts.rawText.trim()) form.append("raw_text", opts.rawText.trim());
    if (opts.provider) form.append("provider", opts.provider);
    return request<PlanDetail>(`/api/plans/${planId}/extract-syllabus`, {
      method: "POST",
      body: form,
    });
  },

  getSchedule: (planId?: number) =>
    request<ScheduleReport>(planId ? `/api/schedule?plan_id=${planId}` : "/api/schedule"),

  recalculateSchedule: () =>
    request<ScheduleReport>("/api/schedule/recalculate", { method: "POST" }),

  updateSessionStatus: (sessionId: number, status: SessionStatus) =>
    request<SessionUpdateResponse>(`/api/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }),
};
