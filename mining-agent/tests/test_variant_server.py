"""Tests for variant_server.

The bootstrap shell-out and uvicorn subprocess are mocked so the suite
doesn't touch the filesystem, network, or actually spawn a server.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from src import variant_server as vs


class TestBootstrapVariantDb:
    def test_skips_when_db_exists(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Re-point the agent dir so the fake DB lives under tmp_path
        monkeypatch.setattr(vs, "AGENT_DIR", tmp_path)
        (tmp_path / "data").mkdir()
        db = tmp_path / "data" / "procurement-cycle-1-A.db"
        db.write_text("ignored", encoding="utf-8")

        called: list[Any] = []

        def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            called.append((args, kwargs))
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        monkeypatch.setattr(vs.subprocess, "run", fake_run)
        result = vs.bootstrap_variant_db("cycle-1-A")
        assert result == db
        assert called == []  # subprocess.run should not have been called

    def test_runs_seed_when_db_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(vs, "AGENT_DIR", tmp_path)
        (tmp_path / "data").mkdir()

        captured: dict[str, Any] = {}

        def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            captured["args"] = args
            captured["env"] = kwargs.get("env", {})
            captured["cwd"] = kwargs.get("cwd")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(vs.subprocess, "run", fake_run)
        vs.bootstrap_variant_db("cycle-1-B")

        assert captured["args"] == ["uv", "run", "python", "-m", "src.seed_data"]
        assert captured["env"]["EXPERIMENT_VARIANT"] == "cycle-1-B"
        assert captured["cwd"] == str(tmp_path)

    def test_force_reseeds_even_when_db_exists(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(vs, "AGENT_DIR", tmp_path)
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "procurement-cycle-1-A.db").write_text("x")

        called: list[Any] = []

        def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            called.append(args)
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(vs.subprocess, "run", fake_run)
        vs.bootstrap_variant_db("cycle-1-A", force=True)
        assert len(called) == 1

    def test_failed_seed_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(vs, "AGENT_DIR", tmp_path)
        (tmp_path / "data").mkdir()

        def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=[], returncode=1, stdout="oops", stderr="bad seed"
            )

        monkeypatch.setattr(vs.subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="seed_data failed"):
            vs.bootstrap_variant_db("cycle-1-A")
