"""Run one cycle of the self-improvement loop end-to-end.

A cycle = (apply already done) → run agent on the deterministic 130
inputs → run reviewer (Vera) → done. The variant agent's traces and
Vera's annotated overrides land in the per-variant Arize project. The
mining agent reads that project for the next cycle.

This module orchestrates three subprocess invocations in order:

  1. variant_server context manager — spawns the variant procurement-agent
     on the chosen port (own DB, own Arize project).
  2. procurement-agent/scripts/seed_requests.py — POSTs the 130 deterministic
     curated + generated requests through the variant agent.
  3. reviewer-agent's `--all` mode — runs Vera against every unreviewed
     assessment via the variant agent's `/override` endpoint.

After this returns, the cycle's data is fully captured in Arize project
`procurement-agent-cycle-N-X`. Mining is invoked separately.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.variant_server import variant_server


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "procurement-agent" / "scripts"
REVIEWER_DIR = REPO_ROOT / "reviewer-agent"
LOGS_DIR = REPO_ROOT / ".context-graph-mining"


@dataclass
class CycleResult:
    variant_id: str
    cycle: int
    project_name: str
    seed_returncode: int
    review_returncode: int
    agent_log: Path


def _stream_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    label: str,
) -> int:
    """Run a subprocess and stream its combined stdout to our stdout, prefixed."""
    print(f"\n=== {label} ===", flush=True)
    print(f"$ (cd {cwd}; {' '.join(cmd)})", flush=True)
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="", flush=True)
    proc.wait()
    return proc.returncode


def run_cycle(
    *,
    cycle: int,
    variant: str,
    port: int = 8001,
    force_reseed: bool = True,
    skip_seed: bool = False,
    skip_review: bool = False,
    review_parallel: int = 10,
) -> CycleResult:
    """Execute one full cycle for the given (cycle, variant) pair.

    `review_parallel` controls Vera's concurrent worker count. The reviewer
    is idempotent and the agent handles concurrent overrides fine, so 10
    is a safe default that drops the review phase from ~26 min to ~3 min.
    """
    variant_id = f"cycle-{cycle}-{variant}"
    project_name = f"procurement-agent-{variant_id}"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"agent-{variant_id}.log"

    base_env = {**os.environ}

    seed_returncode = 0
    review_returncode = 0

    with variant_server(
        variant_id, port=port, force_reseed=force_reseed, log_to=log_path
    ) as base_url:
        agent_env = {**base_env, "PROCUREMENT_AGENT_URL": base_url}

        if not skip_seed:
            seed_returncode = _stream_subprocess(
                ["uv", "run", "python", "seed_requests.py"],
                cwd=SCRIPTS_DIR,
                env=agent_env,
                label=f"seed_requests → {base_url}",
            )

        if not skip_review:
            review_returncode = _stream_subprocess(
                [
                    "uv", "run", "python", "-m", "src",
                    "--all", "--parallel", str(review_parallel),
                ],
                cwd=REVIEWER_DIR,
                env=agent_env,
                label=f"reviewer (Vera, parallel={review_parallel}) → {base_url}",
            )

    return CycleResult(
        variant_id=variant_id,
        cycle=cycle,
        project_name=project_name,
        seed_returncode=seed_returncode,
        review_returncode=review_returncode,
        agent_log=log_path,
    )
