---
name: context-graph-mining
description: "INVOKE THIS SKILL when mining the procurement-agent Arize project for patterns in agent decisions vs human overrides, building a context graph, and proposing updates to procurement-agent rules. Use after a batch of reviews has been captured (process.run + override.run spans with annotations) to surface (a) where the agent's recommendations systematically diverge from reviewer overrides, (b) tribal knowledge embedded in reviewer reasoning that should become explicit rules, and (c) concrete code-change proposals against the procurement-agent codebase."
---

# Context Graph Mining

This skill mines a procurement-agent Arize project for decision patterns, builds a context graph view of how the organization actually decides, and proposes concrete updates to the agent's rules and prompts.

## When to use

- After a batch of human overrides has been applied (e.g. Vera Fye reviewing 100+ requests via `procurement-reviewer/`).
- When you want to surface **rule-reality gaps** — where the agent's encoded rules disagree with how the org actually decides.
- When you want concrete diff proposals against `data/policies.json`, `data/vendors.json`, or the evaluator system prompt.

## What you have access to

- The `procurement-agent` Arize project — export traces, spans, and annotations via the `arize-trace` skill or the `arize.exporter.ArizeExportClient` Python SDK.
- The `procurement-agent/` codebase — `src/agent/evaluator.py`, `src/agent/tools.py`, `data/policies.json`, `data/vendors.json`.
- The `procurement-reviewer/src/reviewer.py` system prompt — Vera Fye's institutional knowledge as currently encoded.

## Workflow

### Phase 1 — Discovery

Build the trace inventory.

For each `session.id` (one per purchase request):
- The `process.run` root span — agent's recommendation, confidence, reasoning, and tool calls (`check_policy`, `lookup_vendor`, `check_budget`).
- The `override.run` root span — the agent re-run with Vera's decision injected.
- Annotations on the override root: `Reviewer Decision`, `Reviewer Confidence`, `Reviewer Name` labels and the `annotation.notes` block (reasoning + precedent + conditions).

Use the `arize-trace` skill for shell-level exports. For programmatic export of annotations, use `ArizeExportClient.export_model_to_df` and read the `annotation.<name>.label` and `annotation.notes` columns.

**Sanity check:** confirm `len(sessions)` matches the expected request count and that every override span has a non-null `Reviewer Decision` label.

### Phase 2 — Pattern discovery

Three priority queries surface the actionable patterns:

1. **Rule-reality gap** — every session where `agent.recommendation != reviewer.decision`. Group by `(vendor, department, urgency, amount-band)`. Clusters with N >= 5 examples are candidates.
2. **Precedent reuse** — extract the `precedent` field from `annotation.notes`; cluster by similarity. Frequently-cited precedents are tribal knowledge that should become explicit rules.
3. **Confidence-vs-override correlation** — when `agent.confidence == "high"` but Vera overrides anyway, the agent has confidently wrong heuristics. Highest-priority targets.

Each pattern produces a structured finding:

> *"For requests matching X, the agent recommends Y but reviewers override to Z in N/M cases. Cited reason: '...'."*

Include 2-3 example session IDs as evidence.

### Phase 3 — Proposals

For each finding, read the relevant source and propose a concrete diff:

| Finding type | Lands in |
|---|---|
| New approval rule | `data/policies.json` (and tool logic in `src/agent/tools.py` if behavior changes) |
| Vendor-specific signal | `data/vendors.json` |
| Prompt update | `src/agent/evaluator.py` system prompt |
| New tool | `src/agent/tools.py` + register on the agent |

Output proposals as unified diffs with rationale, not as freeform prose.

### Phase 4 — Validation handoff (out of scope here)

Validation runs as Arize experiments — out of scope for this skill. Just describe the experiment that *would* validate each proposal: input dataset (the captured override traces), metric (agreement-with-reviewer rate), regression check.

## Output

Produce a single markdown report with this structure:

1. **Summary** — sessions analyzed, override rate, top three patterns.
2. **Rule-reality gaps** — table of clusters; for each: evidence (linked Arize sessions), proposed fix, expected effect.
3. **Precedent extraction** — top tribal knowledge found in `annotation.notes`.
4. **Proposed diffs** — unified diffs against the codebase, each with rationale and validation plan.
5. **Open questions** — patterns that need more data or are ambiguous.

Save the report to `.context-graph-mining/report-<timestamp>.md` (gitignored) and return its content as your final response.

## Constraints

- **Read-only** — this skill does not apply diffs. Output is a markdown report; humans or downstream tooling apply changes.
- **Cite evidence** — every proposed change must reference at least 3 distinct Arize sessions. If a cluster has fewer, mark it as "weak signal" rather than a proposal.
- **No fabricated patterns** — if the data does not support a finding, say so.
- **Domain-agnostic in spirit, procurement-specific in this run** — the patterns and entities (vendor, department, policy) are derived from trace structure, not hardcoded.

## Related skills

- `arize-trace` — export traces, spans, sessions.
- `arize-annotation` — read annotation configs and labels.
- `arize-dataset` / `arize-experiment` — for the validation handoff step described in Phase 4.
- `arize-link` — generate clickable links to evidence sessions for the report.
