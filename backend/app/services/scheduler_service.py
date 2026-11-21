"""Deterministic multi-subject shared-capacity study scheduler.

Strictly separates deterministic scheduling math from LLM reasoning:
* Enforces shared daily study capacity across ALL active subjects.
* Enforces preferred study days and exam deadlines (never schedules on or after
  an exam date).
* Guarantees non-overlapping sessions via ``start_offset_minutes``.
* Detects mathematically infeasible workloads and returns structured warnings
  and actionable suggestions.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.crud import get_or_create_settings
from app.db.models import (
    DEFAULT_STUDY_DAYS,
    Difficulty,
    PlanStatus,
    SessionStatus,
    StudyPlan,
    StudySession,
)

WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DIFFICULTY_WEIGHT: dict[Difficulty, int] = {
    Difficulty.high: 3,
    Difficulty.medium: 2,
    Difficulty.low: 1,
}


@dataclass(frozen=True)
class TopicTask:
    """Normalized incomplete topic ready for deterministic scheduling."""

    topic_id: int
    plan_id: int
    subject_name: str
    topic_name: str
    exam_date: date
    priority: int
    difficulty: Difficulty
    remaining_minutes: int
    order_index: int = 0


@dataclass(frozen=True)
class ScheduledBlock:
    """A concrete, non-overlapping study session block."""

    plan_id: int
    topic_id: int
    scheduled_date: date
    start_offset_minutes: int
    duration_minutes: int


@dataclass(frozen=True)
class PlanFeasibility:
    """Per-subject feasibility breakdown."""

    plan_id: int
    subject_name: str
    exam_date: date
    required_minutes: int
    scheduled_minutes: int
    deficit_minutes: int
    is_feasible: bool


@dataclass(frozen=True)
class ScheduleReport:
    """Full output of a global schedule computation."""

    is_feasible: bool
    total_required_minutes: int
    total_scheduled_minutes: int
    total_available_minutes: int
    deficit_minutes: int
    sessions: list[ScheduledBlock] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    per_plan: list[PlanFeasibility] = field(default_factory=list)


def _eligible_study_days(
    start_date: date,
    end_exclusive: date,
    preferred_days: set[str],
) -> list[date]:
    """Return all dates ``d`` with ``start_date <= d < end_exclusive`` on preferred weekdays."""
    if end_exclusive <= start_date or not preferred_days:
        return []
    days: list[date] = []
    cur = start_date
    while cur < end_exclusive:
        if WEEKDAY_NAMES[cur.weekday()] in preferred_days:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def compute_schedule(
    tasks: list[TopicTask],
    *,
    daily_study_minutes: int,
    preferred_study_days: list[str] | None = None,
    max_session_minutes: int = 60,
    start_date: date | None = None,
    already_used_minutes_by_date: dict[date, int] | None = None,
) -> ScheduleReport:
    """Deterministically allocate study blocks across shared daily capacity.

    Uses Earliest Deadline First (EDF) ordering broken by priority, difficulty,
    syllabus order, and topic ID. Never exceeds ``daily_study_minutes`` on any
    date and never schedules on or past a subject's ``exam_date``.
    """
    today = start_date or date.today()
    preferred_set = set(preferred_study_days or DEFAULT_STUDY_DAYS)
    max_block = max(15, min(max_session_minutes, daily_study_minutes))

    active_tasks = [t for t in tasks if t.remaining_minutes > 0]
    if not active_tasks:
        return ScheduleReport(
            is_feasible=True,
            total_required_minutes=0,
            total_scheduled_minutes=0,
            total_available_minutes=0,
            deficit_minutes=0,
            sessions=[],
            warnings=[],
            suggestions=[],
            per_plan=[],
        )

    # Sort deterministically: Earliest Deadline First, then priority, difficulty, syllabus order.
    ordered_tasks = sorted(
        active_tasks,
        key=lambda t: (
            t.exam_date,
            -t.priority,
            -DIFFICULTY_WEIGHT.get(t.difficulty, 2),
            t.order_index,
            t.topic_id,
        ),
    )

    max_exam_date = max(t.exam_date for t in ordered_tasks)
    horizon_days = _eligible_study_days(today, max_exam_date, preferred_set)

    used_by_day: dict[date, int] = {}
    for d in horizon_days:
        pre_used = (already_used_minutes_by_date or {}).get(d, 0)
        used_by_day[d] = min(daily_study_minutes, max(0, pre_used))

    total_available_minutes = sum(
        max(0, daily_study_minutes - used_by_day[d]) for d in horizon_days
    )

    sessions: list[ScheduledBlock] = []
    plan_required: dict[int, int] = defaultdict(int)
    plan_scheduled: dict[int, int] = defaultdict(int)
    plan_meta: dict[int, tuple[str, date]] = {}

    for task in ordered_tasks:
        plan_required[task.plan_id] += task.remaining_minutes
        plan_meta[task.plan_id] = (task.subject_name, task.exam_date)

        remaining = task.remaining_minutes
        for d in horizon_days:
            if d >= task.exam_date or remaining <= 0:
                break
            available = daily_study_minutes - used_by_day[d]
            if available <= 0:
                continue

            while remaining > 0 and available > 0:
                chunk = min(remaining, max_block, available)
                sessions.append(
                    ScheduledBlock(
                        plan_id=task.plan_id,
                        topic_id=task.topic_id,
                        scheduled_date=d,
                        start_offset_minutes=used_by_day[d],
                        duration_minutes=chunk,
                    )
                )
                used_by_day[d] += chunk
                available -= chunk
                remaining -= chunk
                plan_scheduled[task.plan_id] += chunk

    # Sort sessions chronologically for clean presentation.
    sessions.sort(key=lambda s: (s.scheduled_date, s.start_offset_minutes, s.plan_id, s.topic_id))

    per_plan: list[PlanFeasibility] = []
    warnings: list[str] = []
    suggestions: list[str] = []

    for plan_id, (subject_name, exam_date) in sorted(
        plan_meta.items(), key=lambda item: (item[1][1], item[0])
    ):
        req = plan_required[plan_id]
        sched = plan_scheduled[plan_id]
        deficit = max(0, req - sched)
        per_plan.append(
            PlanFeasibility(
                plan_id=plan_id,
                subject_name=subject_name,
                exam_date=exam_date,
                required_minutes=req,
                scheduled_minutes=sched,
                deficit_minutes=deficit,
                is_feasible=(deficit == 0),
            )
        )
        if deficit > 0:
            if exam_date <= today:
                warnings.append(
                    f"'{subject_name}' exam date ({exam_date.isoformat()}) has no remaining study days before it ({deficit} min unscheduled)."
                )
            else:
                warnings.append(
                    f"'{subject_name}' (exam {exam_date.isoformat()}) is short by {deficit} minutes ({deficit / 60:.1f} hrs)."
                )

    total_required = sum(plan_required.values())
    total_scheduled = sum(plan_scheduled.values())
    total_deficit = max(0, total_required - total_scheduled)
    is_feasible = total_deficit == 0

    if not is_feasible:
        warnings.insert(
            0,
            f"Combined workload exceeds shared study capacity by {total_deficit} minutes ({total_deficit / 60:.1f} hrs).",
        )
        if horizon_days:
            extra_per_day = math.ceil(total_deficit / len(horizon_days))
            suggestions.append(
                f"Increase daily study capacity by at least {extra_per_day} minutes/day (to {daily_study_minutes + extra_per_day} min/day)."
            )
        if len(preferred_set) < 7:
            suggestions.append(
                "Add more preferred study days to increase total available hours before exams."
            )
        suggestions.append(
            "Consider trimming lower-priority topics or archiving a less urgent subject plan."
        )

    return ScheduleReport(
        is_feasible=is_feasible,
        total_required_minutes=total_required,
        total_scheduled_minutes=total_scheduled,
        total_available_minutes=total_available_minutes,
        deficit_minutes=total_deficit,
        sessions=sessions,
        warnings=warnings,
        suggestions=suggestions,
        per_plan=per_plan,
    )


def recalculate_global_schedule(
    db: Session,
    *,
    start_date: date | None = None,
) -> ScheduleReport:
    """Rebuild all pending study sessions across active plans using shared capacity.

    Preserves historical ``completed`` and ``missed`` sessions. Any unfinished
    minutes from ``missed`` sessions are naturally folded back into the topic's
    remaining workload and rescheduled within shared capacity.
    """
    today = start_date or date.today()
    settings = get_or_create_settings(db)

    active_plans = list(
        db.scalars(
            select(StudyPlan)
            .where(StudyPlan.status == PlanStatus.active)
            .options(selectinload(StudyPlan.topics))
            .order_by(StudyPlan.exam_date.asc(), StudyPlan.id.asc())
        ).all()
    )

    # Clear all existing pending sessions so archived/deleted plans don't linger.
    db.execute(delete(StudySession).where(StudySession.status == SessionStatus.pending))

    # Sum completed minutes per topic so we only schedule what remains.
    completed_by_topic: dict[int, int] = dict(
        db.execute(
            select(
                StudySession.topic_id,
                func.coalesce(func.sum(StudySession.duration_minutes), 0),
            )
            .where(StudySession.status == SessionStatus.completed)
            .group_by(StudySession.topic_id)
        ).all()
    )

    # Account for completed sessions on today or future dates so daily cap is respected.
    completed_by_date: dict[date, int] = dict(
        db.execute(
            select(
                StudySession.scheduled_date,
                func.coalesce(func.sum(StudySession.duration_minutes), 0),
            )
            .where(
                StudySession.status == SessionStatus.completed,
                StudySession.scheduled_date >= today,
            )
            .group_by(StudySession.scheduled_date)
        ).all()
    )

    tasks: list[TopicTask] = []
    for plan in active_plans:
        for topic in plan.topics:
            if topic.is_completed:
                continue
            done_mins = completed_by_topic.get(topic.id, 0)
            remaining = max(0, topic.estimated_minutes - done_mins)
            if remaining <= 0:
                continue
            tasks.append(
                TopicTask(
                    topic_id=topic.id,
                    plan_id=plan.id,
                    subject_name=plan.subject_name,
                    topic_name=topic.name,
                    exam_date=plan.exam_date,
                    priority=topic.priority,
                    difficulty=topic.difficulty,
                    remaining_minutes=remaining,
                    order_index=topic.order_index,
                )
            )

    report = compute_schedule(
        tasks,
        daily_study_minutes=settings.daily_study_minutes,
        preferred_study_days=settings.preferred_study_days,
        max_session_minutes=settings.max_session_minutes,
        start_date=today,
        already_used_minutes_by_date=completed_by_date,
    )

    for block in report.sessions:
        db.add(
            StudySession(
                plan_id=block.plan_id,
                topic_id=block.topic_id,
                scheduled_date=block.scheduled_date,
                start_offset_minutes=block.start_offset_minutes,
                duration_minutes=block.duration_minutes,
                status=SessionStatus.pending,
            )
        )

    db.commit()
    return report
