# Reviewer Agent

A standalone CLI tool that simulates **Vera Fye**, a finance manager with years of institutional knowledge, attaching human review decisions to procurement-agent assessments.

This is intentionally a separate app from `procurement-agent`. The agent runs the evaluator and produces an assessment when a request comes in. Some time later — possibly hours or days, mirroring how human review actually happens in an organization — this tool is invoked to attach Vera's decision to that assessment.

The tool talks to the procurement-agent's HTTP API. It does not share code, a database, or a process with the agent.

## Usage

```bash
# Review the latest unreviewed assessment for one or more requests
uv run python -m src PR-001
uv run python -m src PR-001 PR-002 PR-005

# Review every unreviewed assessment in the store
uv run python -m src --all

# 10 concurrent workers — ~10× faster than sequential
uv run python -m src --all --parallel 10

# Point at a different agent host
PROCUREMENT_AGENT_URL=http://localhost:8001 uv run python -m src --all
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `PROCUREMENT_AGENT_URL` | `http://localhost:8000` | Base URL for the procurement-agent API |
| `ANTHROPIC_API_KEY` | — | Required. Anthropic client uses this. |

## How it relates to the demo

The procurement system has three independent components:

- `procurement-agent/` — FastAPI agent + Next.js UI + synthetic seed scripts
- `reviewer-agent/` — this app, simulates async human feedback
- `mining-agent/` — reads accumulated traces + annotations, identifies patterns where the agent diverges from the human, proposes runtime config changes

Together they illustrate how the gap between agent recommendations and human decisions is captured as a structured trace — the substrate of a context graph the mining agent can read.
