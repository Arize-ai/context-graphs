"""Spawn a procurement-agent subprocess for an experiment variant.

Usage:

    with variant_server("cycle-1-A", port=8001) as base_url:
        # base_url is http://localhost:8001
        # The agent has EXPERIMENT_VARIANT=cycle-1-A set, so:
        #   - it loads experiments/variants/cycle-1-A/ at startup
        #   - it writes to data/procurement-cycle-1-A.db
        #   - its traces go to Arize project procurement-agent-cycle-1-A
        ...
    # On exit the subprocess is terminated.

Bootstrapping: the variant DB is seeded with reference data on entry if it
doesn't already exist. The agent's own startup code creates table schema; we
just need to populate departments / vendors / policies before it serves.
"""

from __future__ import annotations

import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = REPO_ROOT / "procurement-agent"


def _variant_db_path(variant_id: str) -> Path:
    return AGENT_DIR / "data" / f"procurement-{variant_id}.db"


def bootstrap_variant_db(variant_id: str, *, force: bool = False) -> Path:
    """Ensure the variant DB exists with reference data seeded.

    Idempotent unless `force=True` is passed (in which case the DB is wiped
    and re-seeded). Always called before spawning the agent.
    """
    db_path = _variant_db_path(variant_id)
    if db_path.exists() and not force:
        return db_path

    env = {**os.environ, "EXPERIMENT_VARIANT": variant_id}
    proc = subprocess.run(
        ["uv", "run", "python", "-m", "src.seed_data"],
        cwd=str(AGENT_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"seed_data failed for variant {variant_id}:\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    return db_path


def _wait_for_ready(base_url: str, timeout: float = 30.0) -> None:
    """Poll a known endpoint until the agent answers 200, or time out."""
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/api/requests", timeout=2.0)
            if r.status_code == 200:
                return
        except Exception as e:  # noqa: BLE001 — broad on purpose; we retry
            last_err = e
        time.sleep(0.3)
    raise TimeoutError(
        f"Agent at {base_url} did not become ready within {timeout}s "
        f"(last error: {last_err})"
    )


@contextmanager
def variant_server(
    variant_id: str,
    *,
    port: int = 8001,
    bootstrap: bool = True,
    force_reseed: bool = False,
    log_to: Path | None = None,
    ready_timeout: float = 60.0,
) -> Iterator[str]:
    """Yield the base URL of a running variant agent. Subprocess killed on exit.

    Always pipes child stdout/stderr to a file handle (either `log_to` or
    /dev/null) — never `subprocess.PIPE` — so the subprocess can't deadlock
    on a full pipe buffer if it logs verbosely.
    """
    if bootstrap:
        bootstrap_variant_db(variant_id, force=force_reseed)

    env = {**os.environ, "EXPERIMENT_VARIANT": variant_id}
    log_handle = (log_to.open("w", encoding="utf-8") if log_to else open(os.devnull, "w"))

    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "src.main:app", "--port", str(port)],
        cwd=str(AGENT_DIR),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://localhost:{port}"

    try:
        _wait_for_ready(base_url, timeout=ready_timeout)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log_handle.close()


__all__ = [
    "bootstrap_variant_db",
    "variant_server",
]
