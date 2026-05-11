"""Programmatic driver for the `context-graph-apply` Claude Code skill.

Mirrors the pattern in `mining-agent/src/runner.py`: spawn a Claude
Agent SDK session in this repo, the skill at `.claude/skills/context-graph-apply/`
auto-loads, the agent reads a mining report, and writes a variant config
bundle to `experiments/variants/<variant_id>/`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import (  # type: ignore[import-not-found]
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MINING_DIR = REPO_ROOT / ".context-graph-mining"
VARIANTS_DIR = REPO_ROOT / "experiments" / "variants"

ALLOWED_TOOLS = ["Skill", "Read", "Grep", "Glob", "Bash", "Write"]

SYSTEM_PROMPT = (
    "You are a procurement-agent variant builder. Run the context-graph-apply "
    "skill. The skill is purely additive — write only files under "
    "experiments/variants/<id>/. Never modify procurement-agent source. "
    "Refuse if the variant directory already exists; do not overwrite."
)


@dataclass
class ApplyResult:
    variant_id: str
    variant_dir: Path
    report_path: Path
    final_message: str
    session_id: str | None
    cost_usd: float | None
    num_turns: int | None
    dry_run: bool


def find_latest_report(mining_dir: Path = MINING_DIR) -> Path:
    """Most recent `report-*.md` under the mining output directory."""
    candidates = sorted(mining_dir.glob("report-*.md"))
    if not candidates:
        raise FileNotFoundError(
            f"No mining reports found in {mining_dir}. "
            "Run `mining-agent` first."
        )
    return candidates[-1]


def _build_prompt(*, variant_id: str, report_path: Path, dry_run: bool) -> str:
    parts = [
        "Run the context-graph-apply skill.",
        f"Mining report path: {report_path}",
        f"Variant id to write: {variant_id}",
    ]
    if dry_run:
        parts.append(
            "Dry-run mode — produce the bundle in your final message but do "
            "not write any files."
        )
    parts.append(
        "In your final message, return: variant id, the path written (or "
        '"dry-run" if no write), and a one-line summary of changes per surface.'
    )
    return "\n".join(parts)


async def run_apply(
    *,
    variant_id: str,
    repo_path: Path = REPO_ROOT,
    report_path: Path | None = None,
    dry_run: bool = False,
    stream_to: object = sys.stdout,
) -> ApplyResult:
    """Invoke the apply skill and capture the result."""
    resolved_report = report_path or find_latest_report(repo_path / ".context-graph-mining")
    variant_dir = repo_path / "experiments" / "variants" / variant_id

    if not dry_run and variant_dir.exists():
        raise FileExistsError(
            f"Variant directory {variant_dir} already exists. "
            "Delete it explicitly or pick a different --variant id."
        )

    options = ClaudeAgentOptions(
        cwd=str(repo_path),
        setting_sources=["user", "project"],
        allowed_tools=ALLOWED_TOOLS,
        permission_mode="acceptEdits",
        system_prompt=SYSTEM_PROMPT,
    )

    final_message = ""
    session_id: str | None = None
    cost_usd: float | None = None
    num_turns: int | None = None

    async for message in query(
        prompt=_build_prompt(
            variant_id=variant_id, report_path=resolved_report, dry_run=dry_run
        ),
        options=options,
    ):
        if isinstance(message, AssistantMessage):
            for block in getattr(message, "content", []) or []:
                text = getattr(block, "text", None)
                if text and stream_to is not None:
                    print(text, file=stream_to, flush=True)
        elif isinstance(message, ResultMessage):
            final_message = getattr(message, "result", "") or ""
            session_id = getattr(message, "session_id", None)
            cost_usd = getattr(message, "total_cost_usd", None)
            num_turns = getattr(message, "num_turns", None)
        elif isinstance(message, SystemMessage):
            sub = getattr(message, "subtype", None)
            sid = getattr(message, "session_id", None)
            if sub == "init" and sid:
                session_id = sid

    return ApplyResult(
        variant_id=variant_id,
        variant_dir=variant_dir,
        report_path=resolved_report,
        final_message=final_message,
        session_id=session_id,
        cost_usd=cost_usd,
        num_turns=num_turns,
        dry_run=dry_run,
    )
