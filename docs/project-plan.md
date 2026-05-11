# Project Plan: Context Graphs Demo

This plan supersedes `agent-team.md` (the old implementation plan was deleted). It reflects the current state of the codebase and the updated direction for Systems A and B.

---

## Current State

### What's Built

**Procurement Agent API** (`procurement-agent/`)
- Python + FastAPI + uv, SQLite database
- Pydantic models: `Department`, `Vendor`, `Policy`, `PurchaseRequest`, `PurchaseRequestCreate`
- Full CRUD: list/get/create purchase requests, list departments and vendors
- Seed data: 5 departments, 9 vendors, 5 policies, 30 purchase requests with timestamps spread across multiple days
- 51 passing tests (unit + integration)

**Procurement UI** (`procurement-ui/`)
- Next.js + TypeScript + Tailwind CSS
- Sidebar list with sort (amount, urgency, status, created, updated)
- Detail pane with info cards, justification, decision timeline placeholder
- Slide-over panel for new request submission
- Connects to FastAPI backend at localhost:8000

**Top-level** (`package.json`)
- `npm run dev` launches both API (port 8000) and UI (port 3000) via concurrently

---

## What Remains

### Phase 1: Procurement Agent (System A) — Agent Integration

Build the AI agent pipeline that evaluates and reviews purchase requests, producing decision traces.

#### 1a. CrewAI Agents & Tools

- **Procurement Evaluator Agent** — evaluates requests against policy using 5 tools:
  - `check_policy`, `check_budget`, `lookup_vendor`, `check_history`, `detect_duplicates`
  - Produces a structured `EvaluatorAssessment`
- **Human Reviewer Simulator (Vera Fye)** — applies institutional knowledge that diverges from policy
  - System prompt encodes vendor relationships, department dynamics, seasonal knowledge, precedent reasoning (all from `demo-spec.md`)
  - Produces a `ReviewDecision` including override flag, reasoning, precedent cited, conditions
- **Process endpoint** — `POST /api/requests/{id}/process` runs evaluator → reviewer pipeline, returns full decision trace

#### 1b. Arize AX Tracing & Annotations

- Instrument CrewAI + LLM calls with OpenTelemetry → Arize AX
- Write reviewer decisions as Arize annotations on the evaluator's trace span
- **Configurable reasoning capture**: support two tracing modes:
  - **Structured-only mode**: captures the agent's final structured output (assessment, decision, rules applied) but excludes the LLM's chain-of-thought reasoning
  - **Full reasoning mode**: captures everything including the LLM's intermediate reasoning steps, tool call rationale, and deliberation
  - Controlled by a config flag (e.g., `CAPTURE_REASONING=true|false`) so we can run the same 30 requests under both modes and compare
  - This directly feeds the blog post question: *does including LLM reasoning in traces make the mining agent better or worse?* Too much context could overwhelm pattern detection, or irrelevant reasoning artifacts could introduce noise

#### 1c. Trace-Reading API

- `GET /api/traces` — list decision traces from Arize
- `GET /api/traces/{id}` — single trace with annotations
- `POST /api/traces/{id}/outcome` — record outcome as annotation
- `GET /api/graph/*` — entity extraction, relationship mapping, stats

#### 1d. UI Updates

- Wire the decision timeline in the detail pane to show: context gathered → agent recommendation → reviewer decision → override highlighting
- Add "Process" button per request and batch processing controls
- Graph visualization panel (entity nodes, connections, stats overlay)

---

### Phase 2: Context Graph Mining (System B) — Claude Code Skill

**Key design change**: the mining agent is not a standalone web app. It is a **skill inside an existing coding harness** (Claude Code). This means the mining agent can not only analyze traces but also directly propose and make code changes to the procurement agent.

#### 2a. Mining Agent as Claude Code Skill

- Build as a Claude Code agent skill (in `.claude/skills/` or equivalent)
- The skill has access to:
  - **Arize AX traces** from the procurement agent (read-only) — the context graph
  - **The procurement agent codebase** — can read source files, understand the agent's prompts, tools, and decision logic
  - **Arize datasets & experiments** — can create experiments to test proposed changes
- Domain-agnostic: discovers what entities, rules, and patterns exist by inspecting trace structure, not from hardcoded procurement knowledge

#### 2b. Mining Agent Tools (Arize-backed)

Same analytical tools as the original spec, but implemented against Arize AX:
- `query_traces` — filter traces by entity, override status, decision, rule, date range
- `find_patterns` — group by dimension, compute metrics (override rate, outcome accuracy, etc.)
- `compare_rules_to_practice` — per-rule compliance vs. override analysis
- `get_outcomes` — outcome metrics with per-trace detail
- `get_entity_profile` — assemble entity profile from all traces
- `suggest_automation` — identify automatable decision patterns with confidence scores

#### 2c. The Self-Improving Code Cycle

This is the central concept for the blog post. Context graphs don't just capture knowledge — they enable a system where agent code improves itself through a measurable, auditable cycle. The mining agent is the mechanism that closes the loop.

**The cycle has five stages:**

```
    ┌──────────────────────────────────────────────────────┐
    │                                                      │
    ▼                                                      │
┌────────┐    ┌────────┐    ┌────────┐    ┌────────┐    ┌──┴─────┐
│  RUN   │───▶│ TRACE  │───▶│ MINE   │───▶│ CHANGE │───▶│ VERIFY │
│        │    │        │    │        │    │        │    │        │
│ Agent  │    │ Capture│    │ Find   │    │ Modify │    │ Run    │
│ handles│    │ every  │    │ where  │    │ agent  │    │ against│
│ real   │    │ decision│   │ agent  │    │ code   │    │ dataset│
│ work   │    │ as a   │    │ gets it│    │ based  │    │ in an  │
│        │    │ trace  │    │ wrong  │    │ on     │    │ experi-│
│        │    │        │    │        │    │ findings│   │ ment   │
└────────┘    └────────┘    └────────┘    └────────┘    └────────┘
    ▲                                                      │
    │              (accept changes, re-run)                 │
    └──────────────────────────────────────────────────────┘
```

**Stage 1: RUN** — the procurement agent processes requests normally. The evaluator agent assesses against policy, the reviewer simulator applies institutional knowledge. This is the production workload.

**Stage 2: TRACE** — every decision is captured as a structured trace in Arize AX. The trace records inputs, context gathered, agent recommendation, reviewer decision, override reasoning, and eventually the real-world outcome. These traces accumulate into the context graph. Importantly, the traces are captured in the normal flow of work — no extra effort from anyone.

**Stage 3: MINE** — the mining agent (Claude Code skill) reads the accumulated traces and identifies patterns where the agent gets it wrong:
- "DataStream Analytics quotes overrun by 30-40%, but the evaluator doesn't flag this"
- "FreshStack has been approved 3 times for Customer Success — should be on the approved list"
- "Marketing urgency claims are unreliable but treated the same as other departments"
- "Vertex Solutions requests from Security are always approved — this could be automated"

The mining agent doesn't just report these findings. Because it runs inside Claude Code with access to the procurement agent's codebase, it understands *where in the code* the behavior originates — which prompt, which tool, which policy rule.

**Stage 4: CHANGE** — the mining agent proposes concrete code modifications:
- Add a cost overrun warning to `lookup_vendor` when the vendor has a history of overruns (addresses DataStream pattern)
- Update the evaluator system prompt to weight urgency claims differently by department (addresses Marketing skepticism)
- Add FreshStack to the approved vendor data for Customer Success (addresses repeated overrides)
- Add an auto-approval path for Vertex Solutions + Security under $50K (addresses automatable pattern)

These aren't vague suggestions — they're actual code diffs against the procurement agent's source files.

**Stage 5: VERIFY** — before applying any changes, validate them experimentally:
1. Export the existing decision traces into an Arize dataset. Each entry is an input (purchase request + gathered context) paired with the ground truth (what the reviewer actually decided). This is the benchmark.
2. Apply the proposed code changes to a copy of the procurement agent.
3. Run the modified agent against every input in the dataset as an Arize experiment.
4. Compare: does the modified evaluator now agree with the reviewer more often? Are there regressions — cases that used to be correct but now aren't? Measure override rate reduction, false positive/negative changes, reasoning alignment.
5. Present the experiment results alongside the code diffs. The user decides whether to accept.

**Then the cycle repeats.** The improved agent handles new requests, those produce new traces, the mining agent finds new patterns (or confirms the changes helped), and the code improves again. Each iteration:
- Reduces the gap between agent recommendations and reviewer decisions
- Captures new institutional knowledge that emerged since the last cycle
- Has a measurable, auditable trail — every change is linked to the traces that motivated it and the experiment that validated it

**What makes this self-improving rather than just iterative:**
- The agent doesn't need a developer to notice that DataStream quotes overrun. The traces capture the pattern automatically. The mining agent identifies it automatically. The code change is proposed automatically. The validation runs automatically. The only human step is the accept/reject decision.
- The knowledge compounds. After cycle 1, the agent handles DataStream correctly. Cycle 2 might discover that the cost overrun pattern also applies to a different vendor category. Cycle 3 might find that the auto-approval rules from cycle 1 are now confident enough to expand to more vendor/department combinations.
- The traces from the improved agent are richer — because the agent now makes better initial assessments, the reviewer's overrides shift to more nuanced cases, which teaches the mining agent more subtle patterns.

**Guardrails on self-improvement:**
- Human approval gate: the mining agent proposes, the developer accepts. No automatic code deployment.
- Experiment validation: every proposed change must pass the dataset benchmark before it's offered to the developer. Changes that introduce regressions are flagged and require justification.
- Audit trail: every code change links back to (a) the traces that motivated it, (b) the mining agent's analysis, and (c) the experiment results. This is fully traceable.
- The cycle is pull-based, not push-based: the developer invokes the mining skill when they want to check for improvements. It doesn't run unsupervised.

#### 2d. Reasoning Trace Comparison

Run the full self-improving cycle (2c) twice — once with structured-only traces, once with full reasoning traces — to answer the blog post question:

- **With reasoning**: the mining agent can see *why* the LLM made each choice, not just what it chose. Does this help it propose better improvements? Or does the extra verbosity and potential for hallucinated reasoning introduce noise?
- **Without reasoning**: the mining agent only sees structured inputs/outputs. Is the signal cleaner? Does it miss nuances that reasoning would have revealed?
- Compare experiment results side by side. This becomes a key finding in the blog post.

#### 2e. Multi-Cycle Demo

To demonstrate compounding improvement, run at least two full cycles:

- **Cycle 1**: Process all 30 requests → capture traces → mine patterns → propose changes (e.g., DataStream cost warning, FreshStack vendor status) → validate via experiment → accept changes
- **Cycle 2**: Re-process the 30 requests with the improved agent → capture new traces → mine again → the mining agent should find:
  - The DataStream and FreshStack patterns are resolved (confirming cycle 1 worked)
  - New, more subtle patterns are now visible because the obvious ones are gone
  - Some original overrides are now agreements (measuring the improvement)
- This demonstrates that the cycle actually compounds — it's not a one-shot improvement but a genuine feedback loop

---

### Phase 3: Blog Post & Talk

#### Blog Post Updates

Add sections covering the new material:

- **Section 3 (Demo) addition**: walk through the improvement loop — show how the mining agent goes from "identify pattern" to "propose code change" to "validate with experiment" to "apply improvement"
- **Section 4 (Future) addition**: discuss whether context graph mining agents should be standalone apps or skills within existing development tools. The Claude Code integration demonstrates that the mining agent is most powerful when it can act on its findings, not just report them.
- **New subsection: The reasoning question** — do LLM reasoning traces help or hurt? Present the experimental comparison. This is a genuinely open question with implications for trace schema design: should the standard trace format include reasoning by default, or is it an optional high-fidelity mode?
- **New subsection: The experiment-driven improvement loop** — capture inputs → run experiments → measure → apply. This is the "closing the loop" story made concrete with Arize datasets and experiments, not just theoretical.

#### Talk

Reusable deck for Dev Rel team covering the same narrative arc.

---

## Open Questions for the Blog Post

1. **Does reasoning in traces help the mining agent?** The mining agent might do better with just structured decisions (cleaner signal, less noise) or it might do better with full reasoning (richer context, can identify *why* patterns exist). The experiment will answer this. Both outcomes are interesting for the post.

2. **Is the mining agent an agent or a skill?** A standalone agent with its own UI is a cleaner demo separation. A skill inside Claude Code is more powerful because it can read code, propose changes, and run experiments. The answer might be "both" — the analytical capability is agent-like, but the action capability requires a coding harness. This tension is worth exploring in the post.

3. **How do you validate mining agent suggestions?** The dataset → experiment loop gives a concrete answer: capture the current behavior as a dataset, apply the suggested change, re-run, compare. This is reproducible and measurable, not just "the agent said it would be better."

4. **How many cycles before diminishing returns?** The self-improving cycle should show clear gains in cycle 1 (the obvious patterns), smaller but meaningful gains in cycle 2 (subtler patterns now visible), and potentially plateau by cycle 3. Where the plateau lands tells you something about the ceiling of trace-driven improvement vs. the need for new data or new types of decisions.

5. **What's the boundary between self-improvement and drift?** If the agent keeps changing its own behavior based on traces, how do you ensure it doesn't drift away from organizational intent? The human approval gate is the answer in the demo, but the blog should discuss what this looks like at scale — versioned policies, change review boards, automated regression detection.

6. **Can the cycle run continuously?** The demo is pull-based (developer invokes the mining skill). Could it be a scheduled process — mine traces nightly, propose changes as PRs, auto-validate against the dataset? What changes when you move from "developer-triggered improvement" to "continuous self-improvement with human review"?

---

## Technical Architecture — The Self-Improving Code Cycle

```
                    THE SELF-IMPROVING CODE CYCLE
                    ─────────────────────────────

    ┌──────────────────────────────────────────────────────────┐
    │                                                          │
    │  ① RUN                              ⑤ VERIFY             │
    │  Agent handles requests             Run modified agent    │
    │  ┌──────────────────────┐           against dataset in   │
    │  │ Procurement Agent     │           Arize experiment     │
    │  │ (System A)            │                 │              │
    │  │                       │                 │  accept?     │
    │  │ FastAPI + CrewAI      │◄────────────────┘              │
    │  │ Evaluator + Reviewer  │   apply changes               │
    │  └──────────┬────────────┘                               │
    │             │                                             │
    │             │ ② TRACE                                     │
    │             │ Every decision captured                     │
    │             ▼                                             │
    │  ┌──────────────────────────────────────────────────┐    │
    │  │ Arize AX                                          │    │
    │  │                                                    │    │
    │  │ Decision Traces ──▶ Datasets ──▶ Experiments       │    │
    │  │ (with/without          (ground       (validate      │    │
    │  │  reasoning)             truth)        changes)      │    │
    │  └──────────┬────────────────────────────────────────┘    │
    │             │                                             │
    │             │ ③ MINE                                      │
    │             │ Find where agent gets it wrong              │
    │             ▼                                             │
    │  ┌──────────────────────────────────────────────────┐    │
    │  │ Claude Code + Mining Agent Skill                   │    │
    │  │                                                    │    │
    │  │ - Read traces: find patterns, overrides, gaps      │    │
    │  │ - Read codebase: understand agent's logic          │    │
    │  │ - ④ CHANGE: propose code diffs                     │    │
    │  │ - ⑤ VERIFY: run experiments against dataset     ───┘    │
    │  └───────────────────────────────────────────────────┘    │
    │                                                          │
    │  Each cycle: agent improves → traces shift to subtler    │
    │  cases → mining finds deeper patterns → cycle compounds  │
    └──────────────────────────────────────────────────────────┘
```

---

## Implementation Order

```
Phase 1 — Procurement agent pipeline (in progress)
  ├── 1a. CrewAI agents + tools
  ├── 1b. Arize tracing with configurable reasoning capture
  ├── 1c. Trace-reading API endpoints
  └── 1d. UI: decision timeline, process controls, graph viz

Phase 2 — Mining agent as Claude Code skill
  ├── 2a. Skill scaffolding with Arize trace access + codebase access
  ├── 2b. Analytical tools (query, patterns, rules, outcomes)
  ├── 2c. Self-improving code cycle: run → trace → mine → change → verify → repeat
  ├── 2d. Run comparison: structured-only vs. full-reasoning traces
  └── 2e. Multi-cycle demo (at least 2 full cycles to show compounding)

Phase 3 — Content
  ├── Blog post (updated outline with new sections)
  └── Talk deck
```
