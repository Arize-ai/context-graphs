"""Tests for apply_runner — exercises the prompt builder and report
discovery without invoking the Claude Agent SDK against the real API."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.apply_runner import (
    ALLOWED_TOOLS,
    SYSTEM_PROMPT,
    _build_prompt,
    find_latest_report,
)


def test_allowed_tools_are_read_plus_write() -> None:
    assert "Skill" in ALLOWED_TOOLS
    assert "Write" in ALLOWED_TOOLS
    assert "Read" in ALLOWED_TOOLS


def test_system_prompt_forbids_source_modification() -> None:
    assert "experiments/variants" in SYSTEM_PROMPT
    assert "Never modify procurement-agent source" in SYSTEM_PROMPT


def test_prompt_includes_skill_invocation_and_paths(tmp_path: Path) -> None:
    report = tmp_path / "report-x.md"
    report.write_text("dummy", encoding="utf-8")
    prompt = _build_prompt(
        variant_id="cycle-1-A", report_path=report, dry_run=False
    )
    assert "context-graph-apply" in prompt
    assert "cycle-1-A" in prompt
    assert str(report) in prompt
    assert "Dry-run" not in prompt


def test_prompt_marks_dry_run(tmp_path: Path) -> None:
    report = tmp_path / "r.md"
    report.write_text("d", encoding="utf-8")
    prompt = _build_prompt(
        variant_id="cycle-1-B", report_path=report, dry_run=True
    )
    assert "Dry-run" in prompt
    assert "do not write any files" in prompt


def test_find_latest_report_picks_most_recent(tmp_path: Path) -> None:
    (tmp_path / "report-20260101T000000Z.md").write_text("a")
    (tmp_path / "report-20260507T230152Z.md").write_text("b")
    (tmp_path / "report-20260301T000000Z.md").write_text("c")
    latest = find_latest_report(tmp_path)
    assert latest.name == "report-20260507T230152Z.md"


def test_find_latest_report_ignores_non_matching(tmp_path: Path) -> None:
    (tmp_path / "report-20260101T000000Z.md").write_text("a")
    (tmp_path / "scratch.md").write_text("noise")
    (tmp_path / "report.md").write_text("noise")  # no timestamp pattern
    latest = find_latest_report(tmp_path)
    # Both report-*.md entries match the glob; lexicographically the timestamped
    # one sorts after "report.md" because the dash precedes characters lower.
    # We only assert that we got a `report-*.md`-shaped file.
    assert latest.name.startswith("report-")


def test_find_latest_report_raises_when_empty(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No mining reports"):
        find_latest_report(tmp_path)
