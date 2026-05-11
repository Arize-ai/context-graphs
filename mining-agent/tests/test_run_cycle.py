"""Tests for the run_cycle orchestrator.

The variant_server context manager + the seed/reviewer subprocess invocations
are mocked so the suite never spawns an actual agent or hits the network.
"""

from __future__ import annotations

import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pytest

from src import run_cycle as rc_mod


@contextmanager
def _fake_variant_server(*args: Any, **kwargs: Any) -> Iterator[str]:
    yield "http://localhost:8001"


def _make_proc(returncode: int = 0, stdout_lines: list[str] | None = None):
    class _Proc:
        def __init__(self) -> None:
            self.returncode = returncode
            self.stdout = iter(stdout_lines or [])

        def wait(self) -> None:
            return None

    return _Proc()


class TestRunCycle:
    def test_runs_seed_and_review_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, Any]] = []

        def fake_popen(cmd: list[str], **kwargs: Any) -> Any:
            calls.append({"cmd": cmd, "cwd": kwargs.get("cwd")})
            return _make_proc(returncode=0)

        monkeypatch.setattr(rc_mod, "variant_server", _fake_variant_server)
        monkeypatch.setattr(rc_mod.subprocess, "Popen", fake_popen)

        result = rc_mod.run_cycle(cycle=1, variant="A")

        assert result.variant_id == "cycle-1-A"
        assert result.project_name == "procurement-agent-cycle-1-A"
        assert result.seed_returncode == 0
        assert result.review_returncode == 0

        # seed_requests first, then reviewer
        assert "seed_requests.py" in " ".join(calls[0]["cmd"])
        assert calls[0]["cwd"].endswith("/procurement-agent/scripts")
        assert "src" in calls[1]["cmd"] and "--all" in calls[1]["cmd"]
        assert calls[1]["cwd"].endswith("/reviewer-agent")

    def test_skip_seed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def fake_popen(cmd: list[str], **kwargs: Any) -> Any:
            calls.append(cmd)
            return _make_proc()

        monkeypatch.setattr(rc_mod, "variant_server", _fake_variant_server)
        monkeypatch.setattr(rc_mod.subprocess, "Popen", fake_popen)

        rc_mod.run_cycle(cycle=1, variant="A", skip_seed=True)

        # Only the reviewer should run
        assert len(calls) == 1
        assert "src" in calls[0] and "--all" in calls[0]

    def test_skip_review(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[list[str]] = []

        def fake_popen(cmd: list[str], **kwargs: Any) -> Any:
            calls.append(cmd)
            return _make_proc()

        monkeypatch.setattr(rc_mod, "variant_server", _fake_variant_server)
        monkeypatch.setattr(rc_mod.subprocess, "Popen", fake_popen)

        rc_mod.run_cycle(cycle=1, variant="B", skip_review=True)

        assert len(calls) == 1
        assert "seed_requests.py" in " ".join(calls[0])

    def test_propagates_seed_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        first_call: list[bool] = []

        def fake_popen(cmd: list[str], **kwargs: Any) -> Any:
            if not first_call:
                first_call.append(True)
                return _make_proc(returncode=2)
            return _make_proc(returncode=0)

        monkeypatch.setattr(rc_mod, "variant_server", _fake_variant_server)
        monkeypatch.setattr(rc_mod.subprocess, "Popen", fake_popen)

        result = rc_mod.run_cycle(cycle=1, variant="A")
        assert result.seed_returncode == 2
        assert result.review_returncode == 0

    def test_passes_url_via_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured_envs: list[dict[str, str]] = []

        def fake_popen(cmd: list[str], **kwargs: Any) -> Any:
            captured_envs.append(dict(kwargs["env"]))
            return _make_proc()

        monkeypatch.setattr(rc_mod, "variant_server", _fake_variant_server)
        monkeypatch.setattr(rc_mod.subprocess, "Popen", fake_popen)

        rc_mod.run_cycle(cycle=1, variant="A")

        for env in captured_envs:
            assert env["PROCUREMENT_AGENT_URL"] == "http://localhost:8001"
