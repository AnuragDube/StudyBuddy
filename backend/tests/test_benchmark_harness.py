"""Tests for the research paper LLM benchmarking harness."""

from __future__ import annotations

from pathlib import Path

from benchmarks.run_benchmark import format_markdown_report, run_benchmark


def test_benchmark_harness_dry_run_produces_metrics_and_reports(tmp_path: Path) -> None:
    results = run_benchmark(["groq", "gemini"], dry_run=True, output_dir=tmp_path)

    # 3 sample syllabi * 2 providers = 6 runs
    assert len(results) == 6
    for r in results:
        assert r.schema_valid is True
        assert r.topic_count == 4
        assert r.concept_recall >= 0.7
        assert r.schedule_constraint_violations == 0
        assert r.schedule_feasible is True

    md = format_markdown_report(results)
    assert "# Study Buddy LLM Benchmark Report" in md
    assert "groq" in md and "gemini" in md

    json_files = list(tmp_path.glob("benchmark_*.json"))
    md_files = list(tmp_path.glob("benchmark_*.md"))
    assert len(json_files) == 1
    assert len(md_files) == 1
