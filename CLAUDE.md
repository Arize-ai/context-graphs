# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository is a working demo of **context graphs** — structured, queryable records of how an organization actually makes decisions, captured automatically through AI agent runs and human reviews. The README is the user-facing intro; this file captures the deeper detail.

A procurement agent evaluates purchase requests against policy. A simulated human reviewer (Vera Fye, a finance manager with 12 years of institutional knowledge that policy doesn't capture) overrides when needed. Every override produces both a traced agent run and a human-review annotation in [Arize AX](https://arize.com/). A mining agent reads those traces, identifies patterns, and proposes runtime config changes that move the agent closer to how the org actually decides — without ever modifying the agent's source code.

## Architecture

Three independent components at the repo root, plus two Claude Code skills shared with the project:

```
procurement-agent/        # FastAPI agent + Next.js UI + seed scripts
reviewer-agent/           # Vera Fye simulator (Python CLI)
mining-agent/             # Mining + apply + cycle orchestration (Claude Agent SDK)
.claude/skills/           # context-graph-mining + context-graph-apply
```

The split is deliberate: the agent runs synchronously when a request arrives, the human reviewer reviews asynchronously, and the mining agent reads traces hours/days later. Conflating them would break the demo's narrative about decision traces accumulating with deferred human signal.

### Procurement agent (`procurement-agent/`)

Python + FastAPI backend managed with **uv**. SQLite for reference data, request state, agent assessments, and (eventually-attached) human reviews. Runs on `localhost:8000`.

- **Data models** (`src/models.py`): `Department`, `Vendor`, `Policy`, `PurchaseRequest`, `EvaluatorAssessment`, `ReviewDecision`, `AssessmentRecord`, with enums for status/urgency/etc. Inert default fields on `Vendor` (`cost_overrun_factor`, `relationship_credit`, `deprecating_in_favor_of`) and `Department` (`behavior_notes`) — populated only when a variant overlay is loaded.
- **Database** (`src/database.py`): tables for departments, vendors, policies, purchase_requests, assessments, reviews. Reviews join assessments by `session_id` (one review per session). The DB path is derived from `EXPERIMENT_VARIANT` (baseline → `data/procurement.db`; variant → `data/procurement-<variant_id>.db`) so a variant agent never writes into the canonical baseline DB. Same env var flips the Arize project name.
- **Agent pipeline** (`src/agent/`): a LangChain agent built with `langchain.agents.create_agent`. Tools: `check_policy`, `lookup_vendor`, `check_budget`, plus `lookup_department` (only registered when a variant is active). Returns a structured `EvaluatorAssessment` via `response_format`. When a `HumanOverride` is supplied, its decision and reasoning are appended to the user message so the override flows into the agent's input — and therefore into the Arize trace.
- **Variant loading** (`src/variants.py`): reads `EXPERIMENT_VARIANT` env var, loads `experiments/variants/<id>/{system_prompt.txt,vendors.json,departments.json}`. Overlays applied at lookup time — DB stays clean, env var flips behavior.
- **Tracing** (`src/instrumentation.py`): Arize AX via OpenInference's LangChain instrumentor. Tags each trace with `session.id = request.id` so all runs against the same purchase request group into one Arize session. Project name derived from `EXPERIMENT_VARIANT` — unset = `procurement-agent` (baseline); set = `procurement-agent-<variant_id>`. Each cycle/variant lives in its own project so cycle-N+1 mining can target a single project directly without per-attribute filters.
- **Seed data** (`src/seed_data.py`): 5 departments, 9 vendors, 5 policies. Purchase requests are seeded via the API — see `scripts/seed_requests.py` below.

**Request lifecycle.** `POST /api/requests` is an auto-process endpoint: it inserts the request, runs the agent inline, and persists the assessment before responding. There is no separate "submit, then click Process" step — every created request lands in one of the three decision tabs (Approved / Rejected / Flagged) immediately. A human reviewer can subsequently override via `POST /api/requests/{id}/override`, which re-runs the agent with the override text as additional context (visible in Arize) and attaches a `ReviewDecision` to the new assessment.

Endpoints:

| Method + path | Purpose |
|---|---|
| `GET /api/requests` | List all purchase requests |
| `GET /api/requests/{id}` | Get one request |
| `POST /api/requests` | Create a request and **auto-process it** through the agent. Returns the request in `completed` state with an assessment already persisted. On agent failure: 500, request left at `pending`, no assessment. |
| `GET /api/departments` | List departments (for the UI form) |
| `GET /api/vendors` | List vendors (for the UI form) |
| `POST /api/requests/{id}/process` | Re-run the evaluator agent on an existing request. Returns a fresh `AssessmentRecord` with `review=null`. |
| `POST /api/requests/{id}/override` | Re-run the agent with a human override applied. Body: `{decision, reasoning, precedent_applied?, conditions?, confidence?}`. Returns a new `AssessmentRecord` with the reviewer's `ReviewDecision` already attached. Used by both the UI's override form and the `reviewer-agent` CLI — Vera's reviews flow through here so they get traced. Annotations on the override root span are pushed via `apply_override_annotation` in `src/annotations.py`. |
| `GET /api/requests/{id}/assessments` | All assessments for one request (newest first), reviews joined when present |
| `GET /api/assessments` | All assessments across the store. Pass `?unreviewed=true` to filter to assessments without a review attached. |
| `POST /api/assessments/{session_id}/review` | Legacy direct-attach: stores a `ReviewDecision` against an existing assessment **without** re-running the agent (no Arize trace). Kept for any consumer that wants pure data attachment. |

#### UI (`procurement-agent/ui/`)

Next.js 16 + TypeScript + Tailwind CSS v4. Single-page client component (sidebar list + detail pane + slide-over for new requests). API base URL via `NEXT_PUBLIC_API_URL` env var (defaults to `http://localhost:8000`). Renders the decision timeline; each assessment shows the agent's recommendation and either Vera's review or "Awaiting human review."

⚠️ This is a breaking version of Next.js — read `procurement-agent/ui/node_modules/next/dist/docs/` before writing code; do not trust training data.

#### Scripts (`procurement-agent/scripts/`)

The 30 curated + 100 procedurally-generated demo purchase requests live under `synthetic_data.py`, decoupled from the agent. The companion `seed_requests.py` POSTs them all through the API in parallel (10 concurrent, deterministic order, ~2 min wall time). Each script run is one LLM call per request, so it costs real OpenAI tokens (~$0.65 per pass).

### Reviewer agent (`reviewer-agent/`)

Standalone Python CLI that simulates **Vera Fye**, a finance manager with 12 years of institutional knowledge. Talks to `procurement-agent` over HTTP only — no shared code or DB.

Vera's decisions are sent through `POST /api/requests/{id}/override` rather than the legacy attach-review endpoint, so each Vera review re-runs the agent with her decision + reasoning + precedent + conditions as additional input. That run is captured in Arize and tagged with `session.id = request.id`, so every Vera review produces a traced agent run.

The reviewer is idempotent: it only acts when the LATEST assessment for a request is unreviewed (or carries a `flag-for-review` reviewer decision — see `_needs_review`). Re-running on a request Vera has already overridden is a no-op.

```bash
uv run python -m src PR-001                    # review one request
uv run python -m src PR-001 PR-002             # multiple
uv run python -m src --all                     # every request whose latest assessment is unreviewed
uv run python -m src --all --parallel 10       # 10 concurrent workers (~10× faster)
```

Configurable via `PROCUREMENT_AGENT_URL`, `OPENAI_API_KEY`. System prompt at `src/reviewer.py` encodes Vera's institutional knowledge and (since cycle 4) requires canonical-tag `precedent_applied` for every override.

### Mining agent (`mining-agent/`)

Three subcommands, all wrappers around Claude Code skills via the Claude Agent SDK:

```bash
uv run python -m src                                   # mine (default action)
uv run python -m src mine --project <name> --quiet     # mine a specific Arize project
uv run python -m src apply --cycle N --variant A|B     # translate report → variant config
uv run python -m src run-cycle --cycle N --variant A|B # spawn variant agent + seed + reviewer
```

- **`mine`** (`src/runner.py`): spawns a Claude Agent SDK session whose `cwd` is this repo, so the `.claude/skills/context-graph-mining/SKILL.md` skill auto-loads. The skill reads Arize traces + the procurement-agent codebase and writes a markdown report to `.context-graph-mining/report-<timestamp>.md` describing rule-reality gaps, precedent extraction, and proposed diffs. Read-only — never modifies source.
- **`apply`** (`src/apply_runner.py`): spawns a similar SDK session that loads `.claude/skills/context-graph-apply/SKILL.md`. The skill reads the latest (or specified) mining report and writes a variant config bundle to `experiments/variants/cycle-N-X/`: `manifest.yaml` + `system_prompt.txt` (variant A) or those plus `vendors.json` + `departments.json` (variant B). Refuses to overwrite an existing variant directory.
- **`run-cycle`** (`src/run_cycle.py` + `variant_server.py`): full cycle orchestrator. (1) bootstraps a per-variant SQLite DB via `procurement-agent`'s seed; (2) spawns the variant procurement-agent on port 8001 with `EXPERIMENT_VARIANT=cycle-N-X` set (its traces land in Arize project `procurement-agent-cycle-N-X`); (3) shells out to `procurement-agent/scripts/seed_requests.py`; (4) shells out to `reviewer-agent --all --parallel 10` against the variant; (5) tears down. After it returns, the cycle's traces + override annotations are in Arize for the next mining pass.

The mining + apply skills also work in interactive Claude Code (invoke directly without the SDK runner) — the runner is just an automation layer.

**Why not Arize datasets/experiments?** Vera *is* the judge — every cycle re-runs the reviewer against the variant's outputs, producing override traces with annotations that already encode the agreement signal. Mining computes the agreement rate from those annotations directly; a separate dataset/experiment scaffolding would compute the same thing twice. Per-variant projects + per-variant reviewer runs are the storytelling unit.

## Commands

### Repo root

```bash
npm run dev       # launches procurement-agent (port 8000) + UI (port 3000) together
```

The reviewer and mining agents are intentionally not in `npm run dev` — they're invoked manually as separate stages of the loop.

### Procurement agent (from `procurement-agent/`)

```bash
uv sync                                            # install deps
uv run python -m src.seed_data                     # seed reference data (departments / vendors / policies). Wipes any existing DB.
uv run uvicorn src.main:app --reload --port 8000   # run API
uv run pytest                                      # 127 tests
```

### Procurement agent UI (from `procurement-agent/ui/`)

```bash
npm install       # install deps
npm run dev       # dev server on localhost:3000
npm run build     # production build
```

### Synthetic seed (from `procurement-agent/scripts/`)

```bash
uv sync
uv run python seed_requests.py                     # 130 requests, 10 in parallel, ~2 min
```

Override via env vars: `PROCUREMENT_AGENT_URL` (default `http://localhost:8000`), `SEED_PARALLELISM` (default 10), `SEED_TIMEOUT_SECONDS` (default 180).

### Reviewer agent (from `reviewer-agent/`)

```bash
uv sync                                            # install deps
uv run python -m src --all --parallel 10           # all unreviewed, 10 concurrent
uv run pytest                                      # 8 tests
```

### Mining agent (from `mining-agent/`)

```bash
uv sync                                            # install deps (claude-agent-sdk + httpx + pydantic)
uv run python -m src                               # mine the baseline procurement-agent project
uv run python -m src --project procurement-agent-cycle-1-B
uv run python -m src apply --cycle 1 --variant A   # write experiments/variants/cycle-1-A/
uv run python -m src apply --cycle 1 --variant B
uv run python -m src run-cycle --cycle 1 --variant A
uv run python -m src run-cycle --cycle 1 --variant B
uv run pytest                                      # 21 tests
```

## Variants — runtime parameterization, not source edits

The procurement-agent supports an `EXPERIMENT_VARIANT` env var that selects a config bundle from `experiments/variants/<id>/`. With no variant set, behavior is byte-identical to baseline (the new fields default to inert values, the `lookup_department` tool isn't registered, the system prompt has no `extra_context` appended). Setting it to e.g. `cycle-1-B` flips both the DB path and the Arize project name and loads:

- `system_prompt.txt` — text appended to the evaluator's baseline system prompt
- `vendors.json` — `{"VendorName": {"cost_overrun_factor": 1.4, "relationship_credit": "...", "deprecating_in_favor_of": "..."}}` overlay
- `departments.json` — `{"DeptName": {"behavior_notes": [...]}}` overlay
- `manifest.yaml` — human-facing record of what was applied + evidence sessions

The mining-agent's `apply` subcommand generates these bundles from a mining report. Variants are committable as repo state — anyone can clone, set `EXPERIMENT_VARIANT=cycle-3-A`, and reproduce the variant agent's behavior.

