"""Smoke tests for the mining runner.

These do not invoke the Claude Agent SDK against the real API — they
verify that argument plumbing and the prompt builder behave correctly.
"""

from __future__ import annotations

from pathlib import Path

from src.runner import (
    ALLOWED_TOOLS,
    DEFAULT_OUTPUT_DIR,
    REPO_ROOT,
    SYSTEM_PROMPT,
    _build_prompt,
)


def test_repo_root_resolves_to_content_harness() -> None:
    assert REPO_ROOT.name == "content-harness"
    assert (REPO_ROOT / ".claude" / "skills" / "context-graph-mining" / "SKILL.md").exists()


def test_default_output_dir_under_repo() -> None:
    assert DEFAULT_OUTPUT_DIR == REPO_ROOT / ".context-graph-mining"


def test_allowed_tools_include_skill_and_read() -> None:
    assert "Skill" in ALLOWED_TOOLS
    assert "Read" in ALLOWED_TOOLS
    assert "Grep" in ALLOWED_TOOLS


def test_system_prompt_mentions_skill_and_evidence() -> None:
    assert "context-graph-mining" in SYSTEM_PROMPT
    assert "session" in SYSTEM_PROMPT.lower()


def test_build_prompt_embeds_project_and_path() -> None:
    out = Path("/tmp/report-fake.md")
    prompt = _build_prompt("procurement-agent", out)
    assert "procurement-agent" in prompt
    assert str(out) in prompt
    assert "context-graph-mining" in prompt
