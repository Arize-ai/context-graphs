---
name: context-graph-apply
description: "INVOKE THIS SKILL when translating a context-graph-mining report into an experiment variant for the procurement-agent. Reads the report's proposed diffs and writes a variant config bundle to `experiments/variants/<id>/` (manifest.yaml + system_prompt.txt + optional vendors.json + departments.json). Does NOT modify procurement-agent source — runtime parameterization means the variant is purely additive config. Use after `context-graph-mining` produces a report; output feeds `procurement-experiment run-experiment`."
---

# Context Graph Apply

This skill translates a `context-graph-mining` report into a runnable experiment variant for the procurement-agent. It writes a config bundle that the agent loads at startup when `EXPERIMENT_VARIANT=<id>` is set — no source code is modified.

## When to use

After `context-graph-mining` produces a report identifying clusters and proposed changes, invoke this skill to:

- **Variant A** (prompt-only): write a system-prompt fragment that adds reviewer-cited context to the agent's instructions.
- **Variant B** (prompt + structured metadata): write the prompt fragment plus enriched `vendors.json` / `departments.json` overlays that the agent reads through `lookup_vendor` and `lookup_department`.

Both are committable to the repo; downstream callers run with `EXPERIMENT_VARIANT=cycle-N-A` or `=cycle-N-B`.

## What you have access to

- The mining report (path passed by the caller — typically the most recent report in `.context-graph-mining/`).
- The procurement-agent source: `src/models.py` (Vendor, Department fields), `src/agent/tools.py` (lookup_vendor, lookup_department surfacing), `src/variants.py` (overlay load mechanics).
- An `experiments/variants/` directory where the output bundle is written.

## Runtime hook contract (what variants can change)

The procurement-agent supports four overlay surfaces. Stay within these:

| Surface | File | Schema |
|---|---|---|
| System-prompt fragment | `system_prompt.txt` | Plain text appended to the evaluator's baseline system prompt. |
| Vendor metadata | `vendors.json` | `{"VendorName": {"cost_overrun_factor": float, "relationship_credit": str, "deprecating_in_favor_of": str|null}}`. Partial — omit fields you don't change. |
| Department behavior | `departments.json` | `{"DeptName": {"behavior_notes": list[str]}}`. Each note is one short reviewer-cited pattern. |
| Manifest | `manifest.yaml` | Human-facing record of what was applied + evidence. Required. |

If the mining report proposes something that doesn't fit these surfaces (e.g., a brand-new entity type, a new tool), **do not invent files** — flag it in the manifest's `out_of_scope` list and stop. The user will extend the agent's hook surface in code, then re-run.

## Workflow

### Phase 1 — Parse the mining report

Read the report at the path the caller supplied. Identify:

- **Cluster table** (Section 2 in the standard report shape): each row is `(cluster_id, vendor / department / pattern, agent recommendation, reviewer decision, evidence sessions)`.
- **Precedent extraction** (Section 3): which tribal-knowledge themes are encoded vs not.
- **Proposed diffs** (Section 4): each proposal targets specific source files. Translate each into the appropriate overlay surface (see the mapping table above).

Skip clusters marked "weak signal" or with fewer than 5 evidence sessions.

### Phase 2 — Build the variant

For variant A (`cycle-N-A`): produce only `system_prompt.txt` and `manifest.yaml`. The prompt fragment should:

- Tell the agent that reviewers cite institutional knowledge that matters.
- List the top 3-5 patterns from the report's Section 3 with one-line summaries.
- Be terse — under 400 words.

For variant B (`cycle-N-B`): produce `system_prompt.txt`, `vendors.json`, `departments.json`, `manifest.yaml`. The vendor and department overlays should encode the report's structural proposals as data:

- Translate "DataStream's quotes inflate ~40%" → `{"DataStream Analytics": {"cost_overrun_factor": 1.4}}`.
- Translate "Marketing panic-buys single-campaign tools" → `{"Marketing": {"behavior_notes": ["Tends to panic-buy single-campaign tools — require sustained-use justification"]}}`.
- Translate "CloudBase being consolidated to Vertex" → `{"CloudBase Inc": {"deprecating_in_favor_of": "Vertex Solutions"}}`.

Cite each overlay entry in the manifest with at least 3 evidence sessions from the report.

### Phase 3 — Write `manifest.yaml`

Schema:

```yaml
variant_id: cycle-N-{A|B}
source_report: path/to/report-<ts>.md
generated_at: ISO-8601 timestamp
applied_changes:
  - cluster: cluster-A-creativehub-marketing
    surface: system_prompt | vendors | departments
    summary: one-line description
    evidence_sessions: [PR-001, PR-042, PR-056]
    expected_effect: e.g. "reduce CreativeHub × Marketing approve→reject overrides"
out_of_scope:
  - finding: ...
    reason: requires new agent capability not in current hook surface
```

### Phase 4 — Validate

Before writing files, check:

1. Every applied change cites ≥ 3 distinct session IDs.
2. No `vendors.json` or `departments.json` key references a vendor/department that doesn't exist in `procurement-agent/src/seed_data.py` (or warn explicitly in the manifest if introducing a new entity).
3. `system_prompt.txt`, if present, is under 400 words.
4. JSON files parse and conform to the schemas above.

If validation fails, abort with a clear message — do not write a partial bundle.

### Phase 5 — Output

Write the bundle to `experiments/variants/<variant_id>/`. The directory must not already exist (refuse to overwrite — the caller can delete it explicitly).

Return a one-paragraph summary in the final message:

- Variant id and path.
- Number of changes applied per surface.
- Anything in `out_of_scope`.
- The Bash command to start an experiment-side agent with this variant: `EXPERIMENT_VARIANT=<id> uv run uvicorn src.main:app --port 8001`.

## Modes

- **Default**: write the bundle to disk.
- **`--dry-run`** (requested by the caller): produce the bundle in-memory and return its contents in the final message — no files written.

## Constraints

- **No source modification** — the procurement-agent code is invariant. Variants are config only.
- **Schema fidelity** — write only files in the surfaces table. Anything else gets flagged as out-of-scope.
- **Evidence required** — every change cites ≥3 sessions or it doesn't ship.
- **Idempotency by absence** — refuse to overwrite an existing variant directory. The caller deletes and re-runs if they want a clean rebuild.

## Related skills

- `context-graph-mining` — produces the input report.
- `arize-experiment` — runs the variant against the dataset (next stage in the loop).
