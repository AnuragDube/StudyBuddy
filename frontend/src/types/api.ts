export type Difficulty = "low" | "medium" | "high";
export type PlanStatus = "active" | "completed" | "archived";
export type SessionStatus = "pending" | "completed" | "missed";
export type WeekdayShort = "Mon" | "Tue" | "Wed" | "Thu" | "Fri" | "Sat" | "Sun";

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  environment: string;
  ai_provider: string;
  ai_configured: boolean;
}

export interface UserSettings {
  id: number;
  daily_study_minutes: number;
  preferred_study_days: WeekdayShort[];
  max_session_minutes: number;
  updated_at: string;
}

export interface UserSettingsUpdate {
  daily_study_minutes?: number;
  preferred_study_days?: WeekdayShort[];
  max_session_minutes?: number;
}

export interface Topic {
  id: number;
  plan_id: number;
  name: string;
  unit: string | null;
  subtopics: string[];
  difficulty: Difficulty;
  priority: number;
  estimated_minutes: number;
  order_index: number;
  is_completed: boolean;
}

export interface TopicCreate {
  name: string;
  unit?: string | null;
  subtopics?: string[];
  difficulty?: Difficulty;
  priority?: number;
  estimated_minutes?: number;
  order_index?: number;
}

export interface PlanSummary {
  id: number;
  subject_name: string;
  exam_date: string;
  color: string | null;
  status: PlanStatus;
  topic_count: number;
  completed_topic_count: number;
  total_estimated_minutes: number;
  progress_percent: number;
  created_at: string;
  updated_at: string;
}

export interface PlanDetail extends PlanSummary {
  syllabus_raw_text: string;
  topics: Topic[];
}

export interface PlanCreate {
  subject_name: string;
  exam_date: string;
  syllabus_raw_text?: string;
  color?: string | null;
  topics?: TopicCreate[];
}

export interface PlanUpdate {
  subject_name?: string;
  exam_date?: string;
  color?: string | null;
  status?: PlanStatus;
}

export interface StudySession {
  id: number;
  plan_id: number;
  topic_id: number;
  subject_name: string;
  plan_color: string | null;
  topic_name: string;
  difficulty: Difficulty;
  priority: number;
  scheduled_date: string;
  start_offset_minutes: number;
  duration_minutes: number;
  status: SessionStatus;
  completed_at: string | null;
}

export interface PlanFeasibility {
  plan_id: number;
  subject_name: string;
  exam_date: string;
  required_minutes: number;
  scheduled_minutes: number;
  deficit_minutes: number;
  is_feasible: boolean;
}

export interface ScheduleReport {
  is_feasible: boolean;
  total_required_minutes: number;
  total_scheduled_minutes: number;
  total_available_minutes: number;
  deficit_minutes: number;
  warnings: string[];
  suggestions: string[];
  per_plan: PlanFeasibility[];
  sessions: StudySession[];
}

export interface SessionUpdateResponse {
  session: StudySession;
  topic_completed: boolean;
  schedule: ScheduleReport;
}
