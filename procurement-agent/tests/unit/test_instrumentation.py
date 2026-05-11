"""Tests for src/instrumentation.setup_tracing.

Network-level behavior (registering with Arize) is not exercised here —
those paths are gated on env vars that the suite-wide conftest clears, so
these tests cover the no-op skip path and idempotency only. End-to-end
trace export is verified manually against a live Arize space.
"""

import pytest

import src.instrumentation as instr


@pytest.fixture(autouse=True)
def reset_instrumented():
    instr._INSTRUMENTED = False
    yield
    instr._INSTRUMENTED = False


def test_skips_when_api_key_missing(monkeypatch, capsys):
    monkeypatch.delenv("ARIZE_API_KEY", raising=False)
    monkeypatch.setenv("ARIZE_SPACE_ID", "fake-space")
    instr.setup_tracing()
    err = capsys.readouterr().err
    assert "skipping" in err.lower()
    assert instr._INSTRUMENTED is False


def test_skips_when_space_id_missing(monkeypatch, capsys):
    monkeypatch.setenv("ARIZE_API_KEY", "fake-key")
    monkeypatch.delenv("ARIZE_SPACE_ID", raising=False)
    instr.setup_tracing()
    err = capsys.readouterr().err
    assert "skipping" in err.lower()
    assert instr._INSTRUMENTED is False


def test_idempotent_when_already_instrumented(monkeypatch):
    """Calling setup_tracing twice is a no-op on the second call."""
    monkeypatch.delenv("ARIZE_API_KEY", raising=False)
    instr._INSTRUMENTED = True  # pretend we've already set up
    # Should return immediately without printing anything or raising
    instr.setup_tracing()
    assert instr._INSTRUMENTED is True


class TestResolveProjectName:
    """Project name derivation from EXPERIMENT_VARIANT — the contract for
    per-variant trace separation in Arize."""

    def test_unset_returns_baseline(self, monkeypatch):
        monkeypatch.delenv("EXPERIMENT_VARIANT", raising=False)
        assert instr.resolve_project_name() == "procurement-agent"

    def test_empty_string_returns_baseline(self, monkeypatch):
        monkeypatch.setenv("EXPERIMENT_VARIANT", "")
        assert instr.resolve_project_name() == "procurement-agent"

    def test_whitespace_returns_baseline(self, monkeypatch):
        monkeypatch.setenv("EXPERIMENT_VARIANT", "   ")
        assert instr.resolve_project_name() == "procurement-agent"

    def test_cycle_1_a_appends(self, monkeypatch):
        monkeypatch.setenv("EXPERIMENT_VARIANT", "cycle-1-A")
        assert instr.resolve_project_name() == "procurement-agent-cycle-1-A"

    def test_cycle_2_b_appends(self, monkeypatch):
        monkeypatch.setenv("EXPERIMENT_VARIANT", "cycle-2-B")
        assert instr.resolve_project_name() == "procurement-agent-cycle-2-B"

    def test_arbitrary_variant_id_appends_verbatim(self, monkeypatch):
        monkeypatch.setenv("EXPERIMENT_VARIANT", "experimental-feature-flag")
        assert (
            instr.resolve_project_name()
            == "procurement-agent-experimental-feature-flag"
        )
