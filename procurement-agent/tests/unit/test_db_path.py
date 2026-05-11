"""Tests for `database.resolve_db_path`.

The resolver is the contract for per-variant DB isolation: a variant
agent must never write into the canonical baseline DB. Pairs with
`instrumentation.resolve_project_name` so one env var flips both.
"""

from __future__ import annotations

import pytest

from src.database import DEFAULT_DB_PATH, resolve_db_path


class TestResolveDbPath:
    def test_unset_returns_baseline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EXPERIMENT_VARIANT", raising=False)
        assert resolve_db_path() == DEFAULT_DB_PATH

    def test_empty_string_returns_baseline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EXPERIMENT_VARIANT", "")
        assert resolve_db_path() == DEFAULT_DB_PATH

    def test_whitespace_returns_baseline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EXPERIMENT_VARIANT", "   ")
        assert resolve_db_path() == DEFAULT_DB_PATH

    def test_cycle_1_a_writes_distinct_db(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EXPERIMENT_VARIANT", "cycle-1-A")
        path = resolve_db_path()
        assert path != DEFAULT_DB_PATH
        assert path.parent == DEFAULT_DB_PATH.parent
        assert path.name == "procurement-cycle-1-A.db"

    def test_cycle_2_b(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EXPERIMENT_VARIANT", "cycle-2-B")
        assert resolve_db_path().name == "procurement-cycle-2-B.db"

    def test_db_path_and_project_name_pair_up(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """One env var must flip both DB path and Arize project together — the
        whole point of the variant mechanism."""
        from src.instrumentation import resolve_project_name

        monkeypatch.setenv("EXPERIMENT_VARIANT", "cycle-3-A")
        assert resolve_db_path().name == "procurement-cycle-3-A.db"
        assert resolve_project_name() == "procurement-agent-cycle-3-A"
