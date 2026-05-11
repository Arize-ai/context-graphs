"""Programmatic driver for the `context-graph-mining` Claude Code skill.

Spawns a Claude Agent SDK session whose `cwd` is the content-harness repo,
which makes `.claude/skills/context-graph-mining/SKILL.md` discoverable.
The agent loops with read + Bash access until it produces the mining report
described by the skill, then we capture the final assistant message.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from claude_agent_sdk import (  # type: ignore[import-not-found]
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    query,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / ".context-graph-mining"

ALLOWED_TOOLS = ["Skill", "Read", "Grep", "Glob", "Bash", "Write"]

SYSTEM_PROMPT = (
    "You are a procurement decision analyst running the context-graph-mining "
    "skill. Follow the skill instructions exactly. Do not modify the "
    "procurement-agent source code — your only filesystem write should be the "
    "report file under .context-graph-mining/. Cite Arize session IDs as "
    "evidence for every proposal."
)


@dataclass
class MiningResult:
    """Outcome of a single mining run."""

    report_path: Path
    final_message: str
    session_id: str | None
    cost_usd: float | None
    num_turns: int | None


def _build_prompt(arize_project: str, output_path: Path) -> str:
    return (
        f"Run the context-graph-mining skill against this repository. "
        f"Mine the Arize project named '{arize_project}'. "
        f"Save the resulting markdown report to {output_path}. "
        f"In your final message, return a one-paragraph summary of what was "
        f"found and the path to the saved report."
    )


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


async def run_mining(
    *,
    repo_path: Path = REPO_ROOT,
    arize_project: str = "procurement-agent",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    stream_to: object = sys.stdout,
) -> MiningResult:
    """Run the mining skill and return the captured report metadata.

    `stream_to` receives a live-ish view of the agent's text output as it
    arrives (pass `None` to suppress).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"report-{_timestamp()}.md"

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
        prompt=_build_prompt(arize_project, report_path),
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

    return MiningResult(
        report_path=report_path,
        final_message=final_message,
        session_id=session_id,
        cost_usd=cost_usd,
        num_turns=num_turns,
    )
