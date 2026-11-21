"""Reproducible LLM benchmarking harness for Study Buddy research evaluation.

Compares configured LLM providers (e.g., Groq ``openai/gpt-oss-20b`` vs.
Google Gemini ``gemini-2.5-flash-lite``) on:
1. Strict JSON schema adherence (%)
2. Syllabus concept recall / coverage (%)
3. End-to-end latency (ms) and token usage
4. Downstream deterministic scheduler constraint compliance (zero cap/overlap violations)

Usage::

    python -m benchmarks.run_benchmark --providers groq gemini
    python -m benchmarks.run_benchmark --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.db.models import Difficulty
from app.schemas.ai import ExtractedTopic, SyllabusExtraction
from app.services.ai_service import (
    AIServiceError,
    ExtractionResult,
    ProviderName,
    extract_topics_from_syllabus,
)
from app.services.scheduler_service import TopicTask, compute_schedule

SYLLABI_DIR = Path(__file__).resolve().parent / "sample_syllabi"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


@dataclass
class RunMetrics:
    provider: str
    model: str
    syllabus_file: str
    subject: str
    schema_valid: bool
    topic_count: int
    total_estimated_minutes: int
    concept_recall: float
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    schedule_feasible: bool
    schedule_constraint_violations: int
    error: str | None = None


def compute_concept_recall(extraction: SyllabusExtraction, expected_concepts: list[str]) -> float:
    """Fraction of reference concepts appearing in extracted topics/subtopics."""
    if not expected_concepts:
        return 1.0
    haystack = " ".join(
        f"{t.name} {t.unit or ''} {' '.join(t.subtopics)} {t.rationale}"
        for t in extraction.topics
    ).casefold()
    hits = sum(1 for concept in expected_concepts if concept.casefold() in haystack)
    return round(hits / len(expected_concepts), 4)


def verify_scheduler_constraints(
    extraction: SyllabusExtraction,
    subject: str,
    *,
    daily_cap: int = 240,
    horizon_days: int = 14,
) -> tuple[bool, int]:
    """Run extracted topics through the deterministic scheduler and count violations."""
    start = date(2026, 11, 23)
    exam = start + timedelta(days=horizon_days)
    tasks = [
        TopicTask(
            topic_id=idx + 1,
            plan_id=1,
            subject_name=subject,
            topic_name=t.name,
            exam_date=exam,
            priority=t.priority,
            difficulty=t.difficulty,
            remaining_minutes=t.estimated_minutes,
            order_index=idx,
        )
        for idx, t in enumerate(extraction.topics)
    ]
    report = compute_schedule(
        tasks,
        daily_study_minutes=daily_cap,
        max_session_minutes=60,
        start_date=start,
    )

    violations = 0
    by_day = defaultdict(list)
    for s in report.sessions:
        if s.scheduled_date >= exam:
            violations += 1
        by_day[s.scheduled_date].append(s)

    for blocks in by_day.values():
        blocks.sort(key=lambda b: b.start_offset_minutes)
        prev_end = 0
        total = 0
        for b in blocks:
            if b.start_offset_minutes < prev_end:
                violations += 1
            prev_end = b.start_offset_minutes + b.duration_minutes
            total += b.duration_minutes
        if total > daily_cap:
            violations += 1

    return report.is_feasible, violations


def _dry_run_extract(provider: str, syllabus_text: str, subject: str) -> ExtractionResult:
    """Deterministic offline extraction for testing the benchmark harness without API keys."""
    lines = [ln.strip() for ln in syllabus_text.splitlines() if ln.strip().startswith("Unit ")]
    topics: list[ExtractedTopic] = []
    for idx, line in enumerate(lines):
        head, _, body = line.partition(":")
        subtopics = [s.strip(" .") for s in body.split(",") if s.strip()]
        topics.append(
            ExtractedTopic(
                name=head.strip(),
                unit=f"Unit {idx + 1}",
                subtopics=subtopics[:10],
                difficulty=Difficulty.high if idx % 2 else Difficulty.medium,
                priority=5 if idx < 2 else 4,
                estimated_minutes=120 + idx * 30,
                rationale="Dry-run deterministic extraction for harness verification.",
            )
        )
    extraction = SyllabusExtraction(subject_title=subject, topics=topics, notes="dry-run")
    return ExtractionResult(
        extraction=extraction,
        provider=provider,
        model=f"{provider}/dry-run",
        latency_ms=12.5 if provider == "groq" else 18.0,
        raw_json=extraction.model_dump_json(),
        prompt_tokens=180,
        completion_tokens=120,
        total_tokens=300,
    )


def run_benchmark(
    providers: list[ProviderName],
    *,
    dry_run: bool = False,
    output_dir: Path | None = None,
) -> list[RunMetrics]:
    """Execute the benchmark suite across all sample syllabi and requested providers."""
    ground_truth = json.loads((SYLLABI_DIR / "ground_truth.json").read_text(encoding="utf-8"))
    settings = get_settings()
    results: list[RunMetrics] = []

    for filename, meta in ground_truth.items():
        syllabus_text = (SYLLABI_DIR / filename).read_text(encoding="utf-8")
        subject = meta["subject"]
        expected = meta["expected_concepts"]

        for provider in providers:
            try:
                if dry_run:
                    res = _dry_run_extract(provider, syllabus_text, subject)
                else:
                    res = extract_topics_from_syllabus(
                        syllabus_text,
                        subject_hint=subject,
                        provider=provider,
                        settings=settings,
                        allow_fallback=False,
                    )
                recall = compute_concept_recall(res.extraction, expected)
                feasible, violations = verify_scheduler_constraints(res.extraction, subject)
                results.append(
                    RunMetrics(
                        provider=res.provider,
                        model=res.model,
                        syllabus_file=filename,
                        subject=subject,
                        schema_valid=True,
                        topic_count=len(res.extraction.topics),
                        total_estimated_minutes=res.extraction.total_minutes,
                        concept_recall=recall,
                        latency_ms=res.latency_ms,
                        prompt_tokens=res.prompt_tokens,
                        completion_tokens=res.completion_tokens,
                        total_tokens=res.total_tokens,
                        schedule_feasible=feasible,
                        schedule_constraint_violations=violations,
                    )
                )
            except AIServiceError as exc:
                results.append(
                    RunMetrics(
                        provider=provider,
                        model=settings.groq_model if provider == "groq" else settings.gemini_model,
                        syllabus_file=filename,
                        subject=subject,
                        schema_valid=False,
                        topic_count=0,
                        total_estimated_minutes=0,
                        concept_recall=0.0,
                        latency_ms=0.0,
                        prompt_tokens=None,
                        completion_tokens=None,
                        total_tokens=None,
                        schedule_feasible=False,
                        schedule_constraint_violations=0,
                        error=str(exc),
                    )
                )

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_path = output_dir / f"benchmark_{stamp}.json"
        md_path = output_dir / f"benchmark_{stamp}.md"
        json_path.write_text(
            json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8"
        )
        md_path.write_text(format_markdown_report(results), encoding="utf-8")

    return results


def format_markdown_report(results: list[RunMetrics]) -> str:
    lines = [
        "# Study Buddy LLM Benchmark Report",
        "",
        "| Provider | Model | Subject | Schema Valid | Topics | Recall | Latency (ms) | Tokens | Violations |",
        "| --- | --- | --- | :---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in results:
        lines.append(
            f"| {r.provider} | `{r.model}` | {r.subject} | "
            f"{'YES' if r.schema_valid else 'NO'} | {r.topic_count} | "
            f"{r.concept_recall * 100:.1f}% | {r.latency_ms:.1f} | "
            f"{r.total_tokens if r.total_tokens is not None else '—'} | "
            f"{r.schedule_constraint_violations} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Study Buddy LLM syllabus benchmark.")
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=["groq", "gemini"],
        default=["groq", "gemini"],
        help="LLM providers to evaluate.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run offline deterministic simulation without calling external APIs.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save JSON and Markdown reports to backend/benchmarks/results/.",
    )
    args = parser.parse_args()

    results = run_benchmark(
        args.providers,
        dry_run=args.dry_run,
        output_dir=RESULTS_DIR if args.save else None,
    )
    print(format_markdown_report(results))


if __name__ == "__main__":
    main()
