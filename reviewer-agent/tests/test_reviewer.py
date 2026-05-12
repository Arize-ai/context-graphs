"""Tests for the institutional-knowledge loader + system-prompt assembly.

These don't hit Anthropic — they only exercise the file-loading and
prompt-templating logic. Vera's actual LLM call is exercised end-to-end
by the procurement-agent integration runs, not here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src import reviewer as rev_mod


def test_default_knowledge_file_exists() -> None:
    """The canonical institutional-knowledge.md ships with the app."""
    assert rev_mod.DEFAULT_KNOWLEDGE_PATH.is_file()


def test_system_prompt_includes_knowledge_content() -> None:
    """The assembled SYSTEM_PROMPT must contain the canonical rule names so
    the LLM actually sees the institutional knowledge at call time."""
    for needle in (
        "Vertex Solutions",
        "CloudBase",
        "DataStream",
        "Insight Partners",
        "Engineering",
        "Marketing",
        "Customer Success",
    ):
        assert needle in rev_mod.SYSTEM_PROMPT, f"missing: {needle}"


def test_system_prompt_preserves_persona_and_guidelines() -> None:
    """The persona, decision guidelines, and required-structure block stay
    in code — only the knowledge content is templated in."""
    assert "You are Vera Fye" in rev_mod.SYSTEM_PROMPT
    assert "DECISION GUIDELINES" in rev_mod.SYSTEM_PROMPT
    assert "precedent_applied" in rev_mod.SYSTEM_PROMPT
    assert "vertex-march-outage-goodwill" in rev_mod.SYSTEM_PROMPT


def test_loader_reads_explicit_path(tmp_path: Path) -> None:
    """Test fixture override — _load_knowledge accepts an explicit path."""
    custom = tmp_path / "knowledge.md"
    custom.write_text("# Custom\n\n- A custom rule\n", encoding="utf-8")
    content = rev_mod._load_knowledge(custom)
    assert "Custom" in content
    assert "A custom rule" in content


def test_loader_raises_on_missing_file(tmp_path: Path) -> None:
    """A missing knowledge file should fail loudly, not silently fall back."""
    missing = tmp_path / "nope.md"
    with pytest.raises(FileNotFoundError, match="institutional knowledge"):
        rev_mod._load_knowledge(missing)


def test_loader_honors_env_var(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """REVIEWER_KNOWLEDGE_PATH should override the default."""
    custom = tmp_path / "env-knowledge.md"
    custom.write_text("- env-supplied rule\n", encoding="utf-8")
    monkeypatch.setenv("REVIEWER_KNOWLEDGE_PATH", str(custom))
    content = rev_mod._load_knowledge()
    assert "env-supplied rule" in content


def test_build_system_prompt_interpolates_knowledge() -> None:
    """The template's {knowledge} slot must be replaced with the loaded text."""
    prompt = rev_mod._build_system_prompt("- a single rule\n- a second rule")
    assert "a single rule" in prompt
    assert "a second rule" in prompt
    # Persona and guidelines bracket the knowledge block.
    assert prompt.index("You are Vera Fye") < prompt.index("a single rule")
    assert prompt.index("a single rule") < prompt.index("DECISION GUIDELINES")
