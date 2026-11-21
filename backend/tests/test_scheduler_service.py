"""Unit and database tests for the deterministic multi-subject scheduler."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.crud import get_or_create_settings
from app.db.models import (
    Difficulty,
    PlanStatus,
    SessionStatus,
    StudyPlan,
    StudySession,
    Topic,
)
from app.services.scheduler_service import (
    TopicTask,
    compute_schedule,
    recalculate_global_schedule,
)


def _assert_non_overlapping_and_within_cap(sessions, daily_cap: int) -> None:
    by_day = defaultdict(list)
    for s in sessions:
        by_day[s.scheduled_date].append(s)

    for day, blocks in by_day.items():
        blocks.sort(key=lambda b: b.start_offset_minutes)
        total = 0
        prev_end = 0
        for b in blocks:
            assert b.duration_minutes > 0
            assert b.start_offset_minutes >= prev_end, f"Overlap detected on {day}"
            prev_end = b.start_offset_minutes + b.duration_minutes
            total += b.duration_minutes
        assert total <= daily_cap, f"Daily cap exceeded on {day}: {total} > {daily_cap}"


def test_empty_tasks_returns_feasible_empty_report() -> None:
    report = compute_schedule([], daily_study_minutes=120, start_date=date(2026, 11, 23))
    assert report.is_feasible is True
    assert report.total_required_minutes == 0
    assert report.deficit_minutes == 0
    assert report.sessions == []


def test_single_subject_respects_daily_cap_chunk_size_and_exam_date() -> None:
    start = date(2026, 11, 23)  # Monday
    exam = date(2026, 11, 26)  # Thursday -> 3 study days (Mon, Tue, Wed)
    tasks = [
        TopicTask(
            topic_id=1,
            plan_id=1,
            subject_name="Algorithms",
            topic_name="Graphs",
            exam_date=exam,
            priority=5,
            difficulty=Difficulty.high,
            remaining_minutes=150,
            order_index=0,
        )
    ]

    report = compute_schedule(
        tasks,
        daily_study_minutes=120,
        max_session_minutes=60,
        start_date=start,
    )

    assert report.is_feasible is True
    assert report.total_required_minutes == 150
    assert report.total_scheduled_minutes == 150
    assert report.deficit_minutes == 0
    assert all(s.scheduled_date < exam for s in report.sessions)
    assert all(s.duration_minutes <= 60 for s in report.sessions)
    _assert_non_overlapping_and_within_cap(report.sessions, daily_cap=120)


def test_multi_subject_shared_capacity_and_edf_priority() -> None:
    start = date(2026, 11, 23)  # Monday
    tasks = [
        TopicTask(
            topic_id=10,
            plan_id=2,
            subject_name="History",
            topic_name="Modern Era",
            exam_date=start + timedelta(days=5),
            priority=5,
            difficulty=Difficulty.medium,
            remaining_minutes=120,
        ),
        TopicTask(
            topic_id=11,
            plan_id=1,
            subject_name="Calculus",
            topic_name="Integrals",
            exam_date=start + timedelta(days=2),
            priority=4,
            difficulty=Difficulty.high,
            remaining_minutes=120,
        ),
    ]

    report = compute_schedule(
        tasks,
        daily_study_minutes=120,
        max_session_minutes=60,
        start_date=start,
    )

    assert report.is_feasible is True
    _assert_non_overlapping_and_within_cap(report.sessions, daily_cap=120)
    # Calculus (earlier exam) should be scheduled on Day 0 before History on Day 1.
    day0_plans = {s.plan_id for s in report.sessions if s.scheduled_date == start}
    assert day0_plans == {1}


def test_respects_preferred_study_days() -> None:
    start = date(2026, 11, 27)  # Friday
    exam = date(2026, 12, 2)  # Wednesday
    tasks = [
        TopicTask(
            topic_id=1,
            plan_id=1,
            subject_name="Physics",
            topic_name="Optics",
            exam_date=exam,
            priority=3,
            difficulty=Difficulty.medium,
            remaining_minutes=180,
        )
    ]

    report = compute_schedule(
        tasks,
        daily_study_minutes=90,
        preferred_study_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
        max_session_minutes=45,
        start_date=start,
    )

    assert report.is_feasible is True
    # Saturday (28) and Sunday (29) must not have sessions.
    scheduled_weekdays = {s.scheduled_date.weekday() for s in report.sessions}
    assert 5 not in scheduled_weekdays
    assert 6 not in scheduled_weekdays


def test_infeasible_workload_returns_deficit_warnings_and_suggestions() -> None:
    start = date(2026, 11, 23)
    exam = start + timedelta(days=2)  # 2 days * 120 min = 240 min capacity
    tasks = [
        TopicTask(
            topic_id=1,
            plan_id=1,
            subject_name="OS",
            topic_name="Virtual Memory",
            exam_date=exam,
            priority=5,
            difficulty=Difficulty.high,
            remaining_minutes=360,
        )
    ]

    report = compute_schedule(
        tasks,
        daily_study_minutes=120,
        preferred_study_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
        max_session_minutes=60,
        start_date=start,
    )

    assert report.is_feasible is False
    assert report.total_scheduled_minutes == 240
    assert report.deficit_minutes == 120
    assert len(report.warnings) >= 2
    assert len(report.suggestions) >= 2
    _assert_non_overlapping_and_within_cap(report.sessions, daily_cap=120)


def test_recalculate_global_schedule_persists_and_handles_missed_and_archived(
    db: Session,
) -> None:
    start = date(2026, 11, 23)
    settings = get_or_create_settings(db)
    settings.daily_study_minutes = 120
    settings.max_session_minutes = 60
    db.commit()

    active_plan = StudyPlan(
        subject_name="Databases",
        exam_date=start + timedelta(days=4),
        status=PlanStatus.active,
    )
    archived_plan = StudyPlan(
        subject_name="Old Course",
        exam_date=start + timedelta(days=4),
        status=PlanStatus.archived,
    )
    db.add_all([active_plan, archived_plan])
    db.flush()

    topic_active = Topic(
        plan_id=active_plan.id,
        name="Normalization",
        difficulty=Difficulty.medium,
        priority=5,
        estimated_minutes=120,
        order_index=0,
    )
    topic_archived = Topic(
        plan_id=archived_plan.id,
        name="Legacy Topic",
        difficulty=Difficulty.low,
        priority=1,
        estimated_minutes=60,
        order_index=0,
    )
    db.add_all([topic_active, topic_archived])
    db.flush()

    # 30 min completed today + 60 min missed earlier + stale pending session on archived plan
    db.add_all(
        [
            StudySession(
                plan_id=active_plan.id,
                topic_id=topic_active.id,
                scheduled_date=start,
                start_offset_minutes=0,
                duration_minutes=30,
                status=SessionStatus.completed,
            ),
            StudySession(
                plan_id=active_plan.id,
                topic_id=topic_active.id,
                scheduled_date=start - timedelta(days=1),
                start_offset_minutes=0,
                duration_minutes=60,
                status=SessionStatus.missed,
            ),
            StudySession(
                plan_id=archived_plan.id,
                topic_id=topic_archived.id,
                scheduled_date=start,
                start_offset_minutes=0,
                duration_minutes=60,
                status=SessionStatus.pending,
            ),
        ]
    )
    db.commit()

    report = recalculate_global_schedule(db, start_date=start)

    # 120 estimated - 30 completed = 90 remaining (missed 60 is rescheduled, not deducted).
    assert report.is_feasible is True
    assert report.total_required_minutes == 90
    assert report.total_scheduled_minutes == 90

    pending_sessions = list(
        db.scalars(
            select(StudySession).where(StudySession.status == SessionStatus.pending)
        ).all()
    )
    assert sum(s.duration_minutes for s in pending_sessions) == 90
    # Archived plan's stale pending session was removed.
    assert all(s.plan_id == active_plan.id for s in pending_sessions)
    # Today already had 30 min completed, so new sessions on `start` begin at offset >= 30.
    today_pending = [s for s in pending_sessions if s.scheduled_date == start]
    assert all(s.start_offset_minutes >= 30 for s in today_pending)
    assert sum(s.duration_minutes for s in today_pending) <= 90
