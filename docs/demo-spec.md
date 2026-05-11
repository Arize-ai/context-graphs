# Procurement Context Graph Demo - Specification

## Overview

A demo consisting of **two independent systems** that illustrate how context graphs capture organizational decision-making and compound over time.

**System A: Procurement Agent System** - A domain-specific agent application with its own web UI. Simulates a procurement approval pipeline where agents evaluate requests, a human reviewer simulator applies institutional judgment, and all decisions are logged as decision traces to a shared context graph store. This represents one of potentially many agent systems an organization runs.

**System B: Context Graph Mining System** - A separate, domain-agnostic application with its own web UI. Connects to a context graph store and analyzes accumulated decision traces from *any* agent system. It knows nothing about procurement specifically - it discovers patterns, identifies policy-reality gaps, and recommends automation by reasoning over the trace structure itself. An organization would point this at traces from procurement, support escalation, hiring, or any other agent system that writes to the shared store.

The two systems share nothing except the context graph store and a common decision trace schema.

---

## System Architecture

```
 SYSTEM A: Procurement Agent                    SYSTEM B: Mining Agent
 ┌─────────────────────────────┐                ┌─────────────────────────────┐
 │    Procurement Web UI       │                │     Mining Console UI       │
 │                             │                │                             │
 │ ┌───────────┐ ┌───────────┐ │                │ ┌─────────────────────────┐ │
 │ │ Request   │ │ Decision  │ │                │ │  Chat Interface         │ │
 │ │ Submission│ │ Review    │ │                │ │                         │ │
 │ │ Panel     │ │ Panel     │ │                │ │  + Evidence Panel       │ │
 │ └─────┬─────┘ └─────┬─────┘ │                │ │  + Visualizations       │ │
 └───────┼─────────────┼───────┘                │ │  + Recommendations      │ │
         │             │                        │ └────────────┬────────────┘ │
         ▼             ▼                        └──────────────┼──────────────┘
 ┌──────────────┐ ┌──────────────┐                             │
 │ Procurement  │ │ Human        │                             ▼
 │ Agent        │ │ Reviewer     │              ┌──────────────────────────────┐
 │              │ │ Simulator    │              │  Mining Agent                │
 │ Tools:       │ │              │              │                              │
 │ -check_policy│ │ Persona +    │              │  Domain-agnostic.            │
 │ -check_budget│ │ org knowledge│              │  Operates on trace structure │
 │ -lookup_vendr│ │ that diverges│              │  not domain semantics.       │
 │ -check_hist  │ │ from policy  │              │                              │
 │ -detect_dupes│ │              │              │  Tools:                      │
 └──────┬───────┘ └──────┬───────┘              │  - query_traces              │
        │                │                      │  - find_patterns             │
        │   writes       │   writes             │  - compare_rules_to_practice │
        ▼                ▼                      │  - get_outcomes              │
 ┌────────────────────────────────┐             │  - get_entity_profile        │
 │                                │  reads      │  - suggest_automation        │
 │    Context Graph Store         │◄────────────│  - list_sources              │
 │    (shared infrastructure)     │             │  - get_schema                │
 │                                │             └──────────────────────────────┘
 │  ┌──────────┐ ┌──────────┐    │
 │  │ Decision │ │ Entities │    │
 │  │ Traces   │ │ & Rels   │    │   Other agent systems (future)
 │  └──────────┘ └──────────┘    │   could also write here:
 │                                │   - Support escalation agents
 │  Source: "procurement"         │   - Hiring pipeline agents
 │  Source: (other agents...)     │   - Incident response agents
 └────────────────────────────────┘
```

### Key Design Principle: Source-Agnostic Mining

The mining agent never assumes it is looking at procurement data. Every trace in the store carries a `source` identifier and self-describing metadata. The mining agent's tools operate on generic trace structure:

- It sees **agents** that made recommendations, **reviewers** that overrode them, **reasoning** that was given, **entities** that were involved, **rules** that were cited, and **outcomes** that resulted.
- It discovers what "vendor" or "department" or "policy" means by inspecting entity types and relationship patterns - not from hardcoded domain knowledge.
- Its prompts and tools use generic vocabulary: "rules" not "policies," "proposals" not "purchase requests," "actors" not "reviewers."

This means the same mining system, without modification, could analyze traces from a support escalation agent, a hiring pipeline, or any other decision-making workflow that writes traces in the shared schema.

---

# SYSTEM A: Procurement Agent System

This is a self-contained domain-specific application. It has its own web UI, its own agents, and its own data (policies, budgets, vendors). It writes decision traces to the shared context graph store but never reads from the mining system.

---

## Agent 1: Procurement Agent

### Role

Evaluates incoming purchase requests against organizational policy and available data. Produces a structured assessment with a recommendation. Does NOT make the final decision.

### Input

A purchase request containing:
- Requester name and department
- Item/service description
- Vendor name
- Amount
- Business justification (free text)
- Urgency level (routine, urgent, emergency)

### Tools

**check_policy**
- Input: request category, amount, vendor
- Behavior: Looks up the applicable procurement policy rules for this type of request. Returns threshold limits, required approval levels, restricted categories, and any special rules.
- Output: Applicable policy rules and whether the request complies

**check_budget**
- Input: department, category, amount
- Behavior: Checks the department's remaining budget for this category in the current quarter.
- Output: Budget remaining, percentage of quarterly allocation used, whether this request would exceed budget

**lookup_vendor**
- Input: vendor name
- Behavior: Looks up vendor in the approved vendor list. Returns vendor status, contract terms, any notes.
- Output: Vendor approval status, existing contract terms, preferred/non-preferred designation, any flags

**check_history**
- Input: department, vendor, category
- Behavior: Returns recent purchase requests from this department for this vendor/category. Includes past decisions and outcomes.
- Output: List of recent related purchases with their decisions and outcomes

**detect_duplicates**
- Input: item/service description, department
- Behavior: Checks whether this request overlaps with existing purchases, active subscriptions, or pending requests.
- Output: Any potential duplicates or overlapping spend, with details

### Processing

The agent:
1. Calls all relevant tools to gather context
2. Evaluates the request against policy
3. Considers budget status, vendor standing, and purchase history
4. Produces a structured assessment

### Output: Structured Assessment

```
{
  "request_id": "PR-0042",
  "policy_compliance": "non-compliant" | "compliant" | "edge-case",
  "policy_details": "Amount exceeds departmental threshold of $5,000 for software purchases",
  "budget_status": "72% of Q2 software budget used, $14,200 remaining",
  "vendor_status": "Approved vendor, preferred contract in place",
  "duplicate_check": "No duplicates found",
  "history_notes": "Department made 3 similar purchases this quarter",
  "recommendation": "approve" | "reject" | "flag-for-review",
  "recommendation_reasoning": "Request complies with policy and budget is available...",
  "confidence": "high" | "medium" | "low",
  "risk_factors": ["approaching quarterly budget limit"]
}
```

---

## Agent 2: Human Reviewer Simulator

### Role

Simulates a finance manager named "Vera Fye" who reviews the procurement agent's assessment and makes the actual decision. Vera has 12 years of organizational experience and carries institutional knowledge that policy doesn't capture.

### Persona & Organizational Knowledge

Vera's system prompt encodes institutional knowledge that diverges from written policy. This is the critical element - the gap between Vera's decisions and policy is what creates valuable decision traces. Vera's knowledge includes:

**Vendor relationships:**
- "Vertex Solutions gave us emergency pricing during the March outage. We owe them goodwill - approve their requests faster and give benefit of the doubt on pricing."
- "CloudBase Inc keeps missing SLA targets but our CTO has a personal relationship with their CEO. Don't reject outright - flag for review instead."
- "DataStream Analytics oversells. Their initial quotes always balloon 40% in implementation. Apply a skepticism factor."

**Department dynamics:**
- "Engineering always sandbaggs their estimates low to get approval, then comes back for more. Add 30% to their quoted amounts mentally."
- "Marketing tends to panic-buy tools they use for one campaign then abandon. Push back on urgency claims."
- "The Customer Success team is understaffed and their requests are usually genuinely urgent. Give them the benefit of the doubt."

**Seasonal/timing knowledge:**
- "Q4 budget requests get scrutinized harder because every department tries to spend remaining budget on nice-to-haves."
- "We're consolidating to single vendors per category this year per the CFO's January directive. Push back on new vendors in categories where we already have a preferred option."
- "Annual renewals with >10% price increase should be flagged - we successfully negotiated down 3 of the last 5."

**Precedent-based reasoning:**
- "Last year we approved an over-budget security tool for the Platform team after the breach. Similar security justifications should get more leeway."
- "We rejected a consulting engagement from Insight Partners in Q1 because they double-billed us in 2024. That still stands."

### Processing

The reviewer agent:
1. Receives the procurement agent's structured assessment
2. Applies institutional knowledge to the assessment
3. Decides: approve, reject, or modify
4. Provides explicit reasoning for the decision, especially when overriding the procurement agent

### Output: Review Decision

```
{
  "request_id": "PR-0042",
  "agent_recommendation": "approve",
  "reviewer_decision": "reject",
  "override": true,
  "reasoning": "Policy says approve, but we're consolidating to single vendors per category this year per CFO directive. We already have a preferred vendor (TechFlow) for this software category. Requester should resubmit using TechFlow.",
  "precedent_applied": "Q2 vendor consolidation directive",
  "conditions": "Resubmit with TechFlow as vendor",
  "confidence": "high"
}
```

---

## Decision Trace Schema (Shared Contract)

This schema is the contract between System A (and any future agent systems) and System B. It is domain-agnostic by design - the structure is the same whether the trace comes from procurement, support escalation, hiring, or incident response. Domain-specific meaning lives in the field *values*, not the field *names*.

Every completed review produces a decision trace that is stored in the context graph.

```
{
  // ── Trace Identity & Source ──
  "trace_id": "DT-0042",
  "timestamp": "2026-04-16T14:32:00Z",
  "source": {
    "system": "procurement-agent",
    "system_description": "Procurement approval pipeline",
    "version": "1.0"
  },

  // ── The Trigger: what initiated this decision ──
  "trigger": {
    "id": "PR-0042",
    "type": "purchase_request",
    "summary": "DataStream Analytics - Enterprise License for Engineering",
    "initiated_by": {
      "entity_id": "person:jamie-kowalski",
      "role": "requester"
    },
    "attributes": {
      "department": "Engineering",
      "vendor": "DataStream Analytics",
      "category": "software",
      "amount": 18500,
      "justification": "Need analytics platform for new observability pipeline",
      "urgency": "routine"
    }
  },

  // ── Context: what was gathered before the decision ──
  "context_gathered": [
    {
      "source_tool": "check_policy",
      "finding": "Compliant - within $25K manager-approval threshold for software",
      "data": { "policy": "software-procurement-v3", "compliance": "compliant", "threshold": 25000 }
    },
    {
      "source_tool": "check_budget",
      "finding": "72% of Q2 software budget used, $14,200 remaining",
      "data": { "budget_remaining": 14200, "percentage_used": 72 }
    },
    {
      "source_tool": "lookup_vendor",
      "finding": "Approved vendor, standard contract in place",
      "data": { "vendor_status": "approved", "contract": "standard" }
    },
    {
      "source_tool": "check_history",
      "finding": "2 prior DataStream purchases this year",
      "data": { "related_traces": ["DT-0004", "DT-0013"] }
    },
    {
      "source_tool": "detect_duplicates",
      "finding": "No duplicates found",
      "data": { "duplicates": [] }
    }
  ],

  // ── Agent Proposal: what the automated system recommended ──
  "proposal": {
    "agent": "procurement-evaluator",
    "decision": "approve",
    "reasoning": "Within policy limits, vendor is approved, budget available",
    "confidence": "high",
    "rules_applied": ["software-procurement-v3", "budget-check-q2"]
  },

  // ── Human Action: what actually happened ──
  "resolution": {
    "actor": {
      "entity_id": "person:dana-chen",
      "role": "finance-manager"
    },
    "decision": "flag-for-review",
    "override": true,
    "reasoning": "DataStream quotes always balloon ~40% in implementation. $18,500 will likely become $25,000+. Need to verify total cost of ownership before approving. Also check if TechFlow's analytics module could serve the same need under our consolidation push.",
    "precedent_cited": ["DT-0004", "DT-0013"],
    "rules_cited": ["vendor-consolidation-q2"],
    "conditions": "Requester must provide total implementation cost estimate and comparison with TechFlow alternative"
  },

  // ── Entities: all actors, objects, and rules involved ──
  "entities": [
    { "id": "vendor:datastream-analytics", "type": "vendor", "role": "subject" },
    { "id": "dept:engineering", "type": "department", "role": "requester_org" },
    { "id": "person:jamie-kowalski", "type": "person", "role": "requester" },
    { "id": "person:dana-chen", "type": "person", "role": "reviewer" },
    { "id": "rule:software-procurement-v3", "type": "rule", "role": "applied" },
    { "id": "rule:vendor-consolidation-q2", "type": "rule", "role": "cited_in_override" }
  ],

  // ── Outcome: what eventually happened (written later) ──
  "outcome": {
    "status": "approved-with-modifications",
    "outcome_date": "2026-05-02T09:15:00Z",
    "attributes": {
      "final_amount": 24200,
      "amount_delta": 5700,
      "amount_delta_percent": 30.8
    },
    "notes": "DataStream implementation cost came in at $24,200 as predicted. TechFlow comparison showed feature gap. Approved at higher amount.",
    "outcome_validates_override": true
  }
}
```

---

---

# Shared Infrastructure: Context Graph Store

The context graph store is the only component shared between System A and System B. System A writes traces. System B reads them. They never communicate directly.

The store must support:
- **Write API**: Used by agent systems (System A) to log decision traces and update outcomes
- **Read API**: Used by the mining system (System B) to query traces, entities, and relationships
- **Schema discovery**: The mining system can discover what entity types, trigger types, rules, and attributes exist without prior knowledge

In the demo, this can be as simple as a JSON file, a SQLite database, or an in-memory store. The abstraction matters more than the implementation.

## Entities

The graph contains the following entity types, each accumulating connections as decisions flow through:

| Entity Type | Key Attributes | Example |
|---|---|---|
| Vendor | name, status, contract terms, flags | DataStream Analytics - approved, cost-overrun flag |
| Department | name, budget allocation, headcount | Engineering - $50K Q2 software budget |
| Person | name, department, role | Jamie Kowalski - Engineering, Senior SRE |
| Policy | name, version, rules, effective date | Software Procurement v3 - max $25K without VP |
| Budget | department, category, quarter, allocated, spent | Engineering/software/Q2 - $50K allocated, $36K spent |
| Request | all request fields | PR-0042 |
| Decision Trace | full trace as above | DT-0042 |

### Relationships

Traces create relationships between entities:

- **vendor ↔ department**: purchase frequency, total spend, approval rate, override rate
- **request ↔ policy**: which policies applied, compliance status
- **decision ↔ precedent**: which past decisions were cited as precedent
- **vendor ↔ outcome**: cost accuracy (quoted vs. actual), satisfaction
- **department ↔ override_pattern**: how often and why decisions for this department get overridden
- **policy ↔ override_rate**: how often this policy's guidance gets overridden (signals policy-reality gap)

### Accumulated Metrics (computed from traces)

As traces accumulate, the graph can compute:
- Per-vendor: approval rate, average override rate, cost accuracy (quoted vs. actual)
- Per-department: budget utilization pattern, override frequency, urgency claim accuracy
- Per-policy: compliance rate, override rate, most common override reasons
- Per-category: spend trends, vendor concentration, exception frequency

---

## Procurement Web UI

### Panel 1: Request Submission

- Form to submit a new purchase request (or button to load from sample data)
- Fields: requester, department, item, vendor, amount, justification, urgency
- "Submit for Review" button triggers the procurement agent

### Panel 2: Decision Review

Shows the full decision flow for each request:

1. **Request details** - the submitted purchase request
2. **Context gathered** - what the procurement agent found (policy, budget, vendor, history, duplicates) - shown as expandable cards
3. **Agent recommendation** - the procurement agent's proposed decision with reasoning
4. **Reviewer decision** - Vera's actual decision with reasoning, with overrides visually highlighted
5. **Decision trace** - the full trace that was logged to the context graph, shown as structured data

Overrides should be visually prominent (color-coded, icon) to make the policy-reality gap immediately visible.

### Panel 3: Context Graph Viewer

A live view of the growing context graph:

- Entity nodes (vendors, departments, people, policies) with connection lines
- Clicking an entity shows all traces involving it
- Stats overlay: total traces, override rate, most-overridden policy
- Timeline view showing how the graph grows as requests are processed

### Flow

1. User clicks "Process Next Request" (or "Process All") to feed sample data through
2. The procurement agent runs, its assessment appears in the review panel
3. The reviewer simulator runs, its decision appears below the assessment
4. The decision trace is logged and the graph view updates
5. Repeat - the graph visibly grows with each request

---

## Sample Data

### Organizational Setup

**Departments:**
- Engineering (50 people, $200K quarterly budget)
- Marketing (25 people, $150K quarterly budget)
- Customer Success (15 people, $75K quarterly budget)
- Sales (30 people, $125K quarterly budget)
- Security (10 people, $100K quarterly budget)

**Approved Vendors (partial list):**
- TechFlow (preferred - software, broad catalog)
- Vertex Solutions (approved - infrastructure, good relationship)
- CloudBase Inc (approved - cloud services, SLA issues noted)
- DataStream Analytics (approved - analytics, cost overrun history)
- Insight Partners (suspended - consulting, billing dispute 2024)
- SecureNet Pro (approved - security tools)
- CreativeHub (approved - marketing/design tools)
- OmniConsult (approved - consulting)
- FreshStack (not on approved list - new vendor)

**Active Policies:**
- Software purchases: up to $5,000 auto-approved, $5K-$25K needs manager, $25K+ needs VP
- Hardware purchases: up to $2,000 auto-approved, above needs manager
- Consulting engagements: all need manager approval, >$50K needs VP
- Vendor consolidation directive (Q2): prefer existing vendors, new vendors need strong justification
- Emergency purchases: can bypass normal approval with post-hoc review within 48 hours

### Sample Purchase Requests (30 requests)

The requests are designed to create a mix of straightforward approvals, policy-compliant rejections, and - most importantly - cases where Vera's institutional knowledge overrides policy. They should be processed in order, as some create precedents that later requests reference.

**Batch 1: Establishing Patterns (Requests 1-10)**

These early requests establish baseline behavior and create the first decision traces.

1. **PR-001**: Engineering requests TechFlow IDE licenses, $3,200, routine. *Expected: Straightforward approve by both agent and reviewer.*
2. **PR-002**: Marketing requests CreativeHub annual renewal, $12,000, routine. *Expected: Agent approves (within policy). Reviewer approves but notes this is the third year and questions whether they're using all seats.*
3. **PR-003**: Sales requests CloudBase Inc expanded storage, $8,500, urgent. *Expected: Agent approves. Reviewer flags - CloudBase has SLA issues, suggests evaluating alternatives before expanding commitment.*
4. **PR-004**: Engineering requests DataStream Analytics add-on module, $6,800, routine. *Expected: Agent approves. Reviewer adds condition - get total implementation cost estimate first (DataStream cost overrun pattern).*
5. **PR-005**: Customer Success requests FreshStack support tool, $4,200, urgent. *Expected: Agent flags - FreshStack not on approved vendor list. Reviewer approves anyway - CS is understaffed, tool addresses critical gap, amount is small.*
6. **PR-006**: Marketing requests OmniConsult brand strategy engagement, $45,000, routine. *Expected: Agent flags for VP approval (>$25K consulting). Reviewer rejects - Marketing had a similar engagement last year that produced a report nobody used.*
7. **PR-007**: Security requests SecureNet Pro vulnerability scanner upgrade, $22,000, urgent. *Expected: Agent approves. Reviewer approves quickly - security requests get leeway since the breach.*
8. **PR-008**: Engineering requests Insight Partners architecture review, $35,000, routine. *Expected: Agent may approve (vendor status may show approved if not updated). Reviewer rejects - Insight Partners double-billed in 2024, still suspended.*
9. **PR-009**: Sales requests TechFlow CRM add-on, $15,000, routine. *Expected: Straightforward approve by both.*
10. **PR-010**: Engineering requests CloudBase Inc dev environments, $19,000, routine. *Expected: Agent approves. Reviewer pushes back - CloudBase SLA issues, and Vertex Solutions offers comparable service with better track record.*

**Batch 2: Building Precedent (Requests 11-20)**

These requests start creating situations where past decisions should inform current ones.

11. **PR-011**: Customer Success requests FreshStack additional licenses, $2,800, routine. *Expected: Agent flags (not approved vendor). Reviewer approves - references PR-005 precedent, FreshStack is proving useful.*
12. **PR-012**: Marketing requests CreativeHub premium tier upgrade, $28,000, urgent. *Expected: Agent flags (>$25K). Reviewer questions urgency - Marketing pattern of panic-buying. Requests justification of why premium tier is needed vs. current plan.*
13. **PR-013**: Engineering requests DataStream Analytics enterprise license, $18,500, routine. *Expected: Agent approves. Reviewer flags for cost overrun check (references PR-004 pattern) and asks for TechFlow comparison (vendor consolidation).*
14. **PR-014**: Security requests emergency firewall hardware, $8,000, emergency. *Expected: Agent approves (emergency policy). Reviewer fast-tracks - security emergencies get immediate approval.*
15. **PR-015**: Sales requests new vendor "LeadGenPro" outbound tool, $9,500, routine. *Expected: Agent flags (not approved). Reviewer rejects - vendor consolidation directive, TechFlow has outbound module.*
16. **PR-016**: Customer Success requests Vertex Solutions integration support, $12,000, urgent. *Expected: Agent approves. Reviewer approves quickly - Vertex is preferred, CS gets benefit of doubt on urgency.*
17. **PR-017**: Marketing requests OmniConsult social media audit, $15,000, routine. *Expected: Agent approves. Reviewer skeptical - references PR-006 (Marketing consulting that went unused). Conditionally approves with defined deliverables and milestone payments only.*
18. **PR-018**: Engineering requests Vertex Solutions additional compute capacity, $32,000, urgent. *Expected: Agent flags (>$25K). Reviewer approves - Vertex goodwill from March outage, Engineering's urgency claims are legitimate here given production scaling needs.*
19. **PR-019**: Sales requests DataStream Analytics reporting module, $7,200, routine. *Expected: Agent approves. Reviewer adds cost overrun warning (references Engineering's DataStream experiences from PR-004, PR-013).*
20. **PR-020**: Security requests OmniConsult penetration testing, $55,000, routine. *Expected: Agent flags (>$50K consulting, needs VP). Reviewer recommends approval - security consulting gets different treatment than marketing consulting.*

**Batch 3: Testing the Compounding Loop (Requests 21-30)**

By now enough precedent exists that patterns should be visible. These requests test whether the system has accumulated enough traces to start making better initial assessments.

21. **PR-021**: Customer Success requests FreshStack enterprise plan, $11,000, routine. *Expected: By now there's a pattern - FreshStack has been approved twice for CS. Agent should note the precedent.*
22. **PR-022**: Engineering requests CloudBase Inc additional services, $14,000, routine. *Expected: Pattern established - CloudBase requests get pushed back. Agent should flag this proactively.*
23. **PR-023**: Marketing requests another consulting engagement (new vendor "BrandForce"), $20,000, urgent. *Expected: Multiple patterns converge - Marketing urgency skepticism + vendor consolidation + Marketing consulting track record.*
24. **PR-024**: Engineering requests DataStream Analytics training package, $4,500, routine. *Expected: Even though under auto-approve threshold, DataStream cost overrun pattern should trigger a flag.*
25. **PR-025**: Sales requests Vertex Solutions premium support, $16,000, routine. *Expected: Straightforward approve - Vertex is preferred, good relationship, within budget.*
26. **PR-026**: Customer Success requests emergency Vertex Solutions incident response, $25,000, emergency. *Expected: Fast-track approve - emergency + preferred vendor + CS benefit of doubt.*
27. **PR-027**: Marketing requests CreativeHub seat reduction and plan change, -$3,000 (credit), routine. *Expected: Approve - references PR-002 where reviewer questioned seat utilization. This is a positive outcome from that earlier decision.*
28. **PR-028**: Engineering requests FreshStack engineering tools, $8,000, routine. *Expected: Interesting test - FreshStack approved for CS but vendor consolidation says prefer existing vendors. Different department, different context.*
29. **PR-029**: Security requests Vertex Solutions security monitoring, $45,000, urgent. *Expected: Approve - security leeway + Vertex preferred status + legitimate urgency.*
30. **PR-030**: Sales requests Insight Partners sales training, $28,000, routine. *Expected: Reject - Insight Partners suspension should be well-established precedent by now.*

### Outcome Data

Each request should also have a predefined outcome that gets recorded after a simulated delay, closing the feedback loop:

- PR-004 (DataStream add-on): Implementation cost was 35% over quote, confirming Vera's pattern
- PR-005 (FreshStack for CS): Tool adopted successfully, used daily by team
- PR-006 (OmniConsult brand strategy): N/A - rejected
- PR-007 (SecureNet upgrade): Caught 3 critical vulnerabilities in first month
- PR-012 (CreativeHub premium): After providing justification, downgraded ask to standard tier - saved $16,000
- PR-013 (DataStream enterprise): Final cost $24,200 vs. $18,500 quote - 31% overrun
- PR-017 (OmniConsult social audit): Milestone structure worked - first deliverable was strong, engagement completed on budget
- PR-027 (CreativeHub reduction): Confirmed 8 of 20 seats were unused

---

---

# SYSTEM B: Context Graph Mining System

This is a **completely separate application** from System A. It has its own codebase, its own web UI, and its own agent. It connects to the context graph store as a read-only consumer and knows nothing about procurement, support, hiring, or any specific domain. It discovers domain semantics by inspecting the traces themselves.

An organization would deploy one mining system and point it at decision traces from all of their agent systems.

---

## Mining Agent

### Role

A domain-agnostic analyst that connects to a context graph store and helps users understand how their organization actually makes decisions. It reasons over trace *structure* - proposals, overrides, reasoning, entities, rules, outcomes - without knowing what domain those traces come from.

When the user asks "which vendors have the highest override rate?", the mining agent doesn't know what a "vendor" is from its own prompt. It discovers that `vendor` is an entity type present in traces from the `procurement-agent` source, sees that entities of this type appear in the `subject` role, and analyzes override patterns against them.

### System Prompt

The mining agent's system prompt describes its role in generic terms:

> You are an organizational decision analyst. You have access to a context graph store containing decision traces from one or more agent systems. Each trace records: what triggered a decision, what context was gathered, what the automated system proposed, what a human actually decided (and why), and what the outcome was.
>
> Your job is to find patterns in how the organization actually makes decisions, identify where automated proposals are consistently overridden (and whether those overrides produce better outcomes), surface rules that don't match practice, and recommend which decisions could be safely automated.
>
> You do not know what domain the traces come from. You discover this by inspecting sources, entity types, and trace attributes. Always ground your analysis in specific traces and evidence.

### Tools

**list_sources**
- Input: none
- Behavior: Returns all source systems that have written traces to the store, with descriptions, trace counts, date ranges, and entity types present.
- Output: List of sources with metadata. Allows the mining agent to understand what data is available before querying.
- Example output:
  ```
  [
    {
      "system": "procurement-agent",
      "description": "Procurement approval pipeline",
      "trace_count": 30,
      "date_range": ["2026-01-15", "2026-04-16"],
      "entity_types": ["vendor", "department", "person", "rule"],
      "trigger_types": ["purchase_request"],
      "override_rate": 0.47
    }
  ]
  ```

**get_schema**
- Input: source (optional - if omitted, returns schema across all sources)
- Behavior: Returns the distinct entity types, trigger types, attribute keys, rule names, and outcome statuses found in traces. This is how the mining agent learns the vocabulary of a domain it has never seen before.
- Output: Schema discovery result

**query_traces**
- Input: filters object with optional fields:
  - `source`: filter by source system
  - `entity_id` or `entity_type`: filter by involved entity
  - `override`: boolean - only overridden or non-overridden traces
  - `decision`: filter by proposal or resolution decision value
  - `rule`: filter by rules applied or cited
  - `date_range`: time window
  - `has_outcome`: boolean - only traces with recorded outcomes
  - `text_search`: full-text search across reasoning fields
- Behavior: Returns matching traces from the context graph store
- Output: List of matching traces with full detail

**find_patterns**
- Input:
  - `dimension`: what to group by (entity_type, entity_id, rule, source, trigger attribute)
  - `metric`: what to measure (override_rate, outcome_success_rate, proposal_accuracy, frequency)
  - `min_occurrences`: minimum traces to consider a pattern significant
- Behavior: Groups traces along the specified dimension, computes the metric, and ranks results. Identifies statistically notable clusters.
- Output: Ranked patterns with supporting trace IDs and counts

**compare_rules_to_practice**
- Input:
  - `rule_id` (optional - specific rule) or `source` (all rules in a source)
- Behavior: For each rule, computes: how often it was applied, how often the proposal that applied it was overridden, the most common override reasons, and whether overrides produced better or worse outcomes than compliance.
- Output: Per-rule analysis with compliance rate, override rate, override reasons, and outcome comparison

**get_outcomes**
- Input: filters (same structure as query_traces)
- Behavior: Returns outcome data for matching traces. Computes aggregate metrics: outcome success rate, attribute deltas (e.g., amount quoted vs. actual), and whether the override (or compliance) correlated with better outcomes.
- Output: Outcome metrics with per-trace detail

**get_entity_profile**
- Input: entity_id
- Behavior: Assembles a complete profile of an entity from all traces it appears in, across all sources. Returns: trace count, roles played, associated entities, override patterns when this entity is involved, outcome history, and reasoning excerpts where this entity is mentioned.
- Output: Entity profile

**suggest_automation**
- Input:
  - `confidence_threshold`: minimum confidence to suggest (e.g., 0.9)
  - `min_traces`: minimum supporting traces
  - `source` (optional)
- Behavior: Identifies decision patterns where: (a) the human consistently agrees with the agent (high agreement rate above threshold), or (b) the human consistently makes the same override for a recognizable pattern (the override itself is automatable). For each, returns the pattern description, confidence score, supporting trace IDs, and any edge cases where the pattern broke.
- Output: List of automation candidates with evidence

---

## Mining Console UI

### Separate Web Application

The mining console is its own web application, independent from the procurement UI. It connects to the context graph store via the same read API the mining agent uses.

### Layout

**Left panel: Source Explorer**
- Lists all source systems writing to the context graph store
- For each source: trace count, date range, override rate, entity types
- Clicking a source filters the chat context to that source (or "All Sources" for cross-system analysis)
- In the demo, only "procurement-agent" will appear. The UI should make it clear that other sources would appear here as more agent systems are connected.

**Center panel: Chat Interface**
- Natural language query input
- Mining agent responses with analysis, formatted as structured reports
- Responses cite specific trace IDs which are clickable

**Right panel: Evidence & Visualizations**

Three tabs:

1. **Evidence**: When the mining agent cites traces, they appear here as expandable cards showing the full trace. Clicking a trace ID in the chat scrolls to / highlights it here.

2. **Patterns**: When the mining agent identifies patterns, this tab shows visualizations:
   - Override rate by entity (bar chart)
   - Rule compliance vs. override over time (line chart)
   - Entity relationship map (nodes and edges from traces)
   - Outcome comparison: overridden vs. non-overridden decisions

3. **Recommendations**: Running list of actionable recommendations the mining agent has surfaced during the session:
   - Rules to update (with evidence)
   - Decisions to automate (with confidence and supporting traces)
   - Entities to flag (with pattern description)

### Sample Queries

These are written in domain-agnostic language as a user would ask them. The mining agent figures out the domain from the traces.

**Orientation (first-time user exploring the graph):**

1. "What data do you have access to? What kinds of decisions are being tracked?"
   - *Expected: The agent calls list_sources and get_schema. Reports that it has 30 traces from a procurement approval pipeline, with entity types vendor/department/person/rule, and a 47% override rate. Describes the decision flow it observes: triggers come in, an agent evaluates against rules, a human reviewer approves or overrides.*

2. "Give me a high-level summary of how this organization makes procurement decisions. Where does the human disagree with the automation?"
   - *Expected: Calls find_patterns across multiple dimensions. Reports the overall override rate, identifies the top entities and rules associated with overrides, and characterizes the types of disagreements (cost skepticism, relationship-based exceptions, consolidation enforcement).*

**Pattern Discovery:**

3. "Which entities are most associated with overrides? What's driving the disagreements?"
   - *Expected: Identifies DataStream (cost overrun pattern), CloudBase (SLA concerns), FreshStack (approved despite rule non-compliance). Each with specific traces cited. Also identifies Marketing department as facing higher scrutiny and Customer Success as receiving more leniency.*

4. "Are there patterns in how urgency claims are treated? Does the urgency attribute correlate with different decisions?"
   - *Expected: Groups traces by urgency attribute. Finds that "emergency" from Security is always fast-tracked, "urgent" from Marketing is questioned, "urgent" from Customer Success is accepted. Reports that urgency is not treated uniformly - it's modulated by which department is claiming it.*

5. "Show me all cases where the human cited a previous decision as precedent. How is precedent being used?"
   - *Expected: Queries traces where precedent_cited is non-empty. Maps the precedent chains (DT-004 → DT-013, DT-005 → DT-011 → DT-021, DT-006 → DT-017). Shows that precedent is used both positively (approving because a similar case was approved) and negatively (adding conditions because a similar case had poor outcomes).*

**Rule-Reality Gap Analysis:**

6. "Which rules are most frequently overridden? Are the overrides producing better outcomes?"
   - *Expected: Calls compare_rules_to_practice. Identifies vendor-approved-list (overridden for FreshStack, outcomes positive), vendor-consolidation-q2 (selectively enforced), consulting thresholds (overridden differently for security vs. marketing). Compares outcomes for overridden vs. compliant decisions.*

7. "Is there a rule that should be updated based on actual practice?"
   - *Expected: Synthesizes from rule analysis. The approved vendor list should add FreshStack (3 approvals for Customer Success, all positive outcomes). The consulting approval rule should distinguish between security consulting (always approved) and other consulting (mixed). CloudBase vendor status should carry a warning.*

8. "Are there decisions where the human consistently disagrees with the agent but the outcomes suggest the agent was right?"
   - *Expected: Looks for overrides where outcome_validates_override is false. May find cases where the reviewer's caution was unwarranted, or where conditions added unnecessary friction. This is the inverse of the usual analysis - checking whether the human's institutional knowledge actually helps.*

**Automation Candidates:**

9. "What decisions could be safely automated? Show me the evidence."
   - *Expected: Calls suggest_automation. Identifies: TechFlow purchases under $15K (100% agreement, zero overrides, 6+ traces). Vertex Solutions for Security and Customer Success (always approved). SecureNet Pro renewals (always approved). For each, cites the specific traces and flags any edge cases.*

10. "If a new decision came in matching [specific attributes], what would likely happen based on the history?"
    - *Expected: Given a hypothetical trigger (e.g., "Engineering, DataStream Analytics, $10K, routine"), the agent finds matching patterns and predicts: agent will recommend approval, reviewer will likely add cost overrun warning and request total cost estimate, final cost will be 30-40% higher. Recommends pre-emptively requesting the cost comparison to skip one round of review.*

**Cross-System (future-proofing the demo narrative):**

11. "If you had access to traces from other systems - say, support escalation or hiring - what kinds of cross-system patterns could you look for?"
    - *Expected: The agent describes hypothetically: it could find whether departments that overspend on tools also have higher support escalation rates (suggesting the tools aren't working), whether vendor choice correlates with downstream incidents, or whether hiring patterns in a department predict its procurement behavior. This demonstrates the mining agent's domain-agnostic design and the value of connecting multiple trace sources.*

---

---

# Demo Flow

The demo runs across both systems. The presenter starts in System A (procurement), builds up the context graph, then switches to System B (mining) to show what the graph reveals. The two systems are visibly separate applications.

## Act 1: Building the Graph (System A)

**Open the Procurement UI.** The context graph is empty.

Process requests 1-10 one at a time. For each request, the audience sees:
- The purchase request details
- The procurement agent gathering context and making its policy-based recommendation
- The human reviewer simulator (Vera) making the actual decision - sometimes agreeing, sometimes overriding with reasoning
- The decision trace being written to the store

At the end of Act 1, the audience has watched 10 decisions flow through and can see in the procurement UI:
- 10 decision traces logged
- The first override patterns emerging (DataStream cost skepticism, CloudBase pushback, CS leniency, FreshStack approved despite vendor list)
- The procurement agent is purely policy-based - it doesn't learn from Vera's overrides

Key moments to highlight:
- PR-004: Vera adds a cost overrun warning for DataStream that policy doesn't require
- PR-005: Vera approves FreshStack despite it failing the vendor check - institutional knowledge overrides policy
- PR-008: Vera rejects Insight Partners that the agent might have approved - suspension from a billing dispute the agent doesn't know about

## Act 2: Precedent Accumulates (System A)

Process requests 11-20. The audience now sees:
- PR-011: Vera references PR-005 when approving FreshStack again - precedent in action
- PR-013: Vera references PR-004 when flagging DataStream again - pattern is explicit
- PR-017: Vera conditionally approves consulting with milestones - learning from PR-006 rejection

Process requests 21-30 to complete the dataset. By now the audience can see the graph is dense with traces, but the procurement agent itself hasn't gotten smarter - it's still purely policy-based. All the institutional knowledge is locked in the traces.

## Act 3: Mining the Graph (System B)

**Switch to the Mining Console** - a completely separate application.

The presenter opens System B for the first time. The mining agent has never seen procurement data before. Walk through the queries in order:

**Step 1: Orientation** (queries 1-2)
The mining agent discovers what's in the store. It reports: "I have 30 decision traces from a procurement approval pipeline with a 47% override rate. Here's what I see..." This demonstrates the domain-agnostic discovery.

**Step 2: Pattern Discovery** (queries 3-5)
The mining agent identifies the key patterns: DataStream cost overruns, department-specific treatment, urgency reliability by department. The evidence panel fills with supporting traces.

**Step 3: Rule-Reality Gap** (queries 6-8)
The mining agent produces the "rules vs. reality" analysis. The audience sees concrete policy recommendations grounded in trace evidence. This is the core demonstration: knowledge that was locked in Vera's head is now structured, queryable, and actionable.

**Step 4: Automation** (queries 9-10)
The mining agent identifies which decisions could be safely automated, with evidence. It predicts what would happen for a hypothetical new request. This shows the compounding loop: accumulated traces enable future decisions to be better and faster.

**Step 5: The Bigger Picture** (query 11)
The presenter asks what the mining agent could do with traces from other systems. The agent describes cross-system patterns it would look for. The source explorer panel (currently showing only "procurement-agent") makes clear this is one of many possible sources.

## The Punchline

The demo's climax is the contrast between two moments:

1. **PR-005 in Act 1**: Vera approves FreshStack for Customer Success, overriding the agent's flag. Her reasoning is free text in a decision trace. No system learns from it.

2. **Query 9 in Act 3**: The mining agent, which has never been told about procurement, independently discovers that FreshStack has been approved 3 times for Customer Success with positive outcomes, and recommends formally adding it to the approved vendor list and auto-approving future FreshStack requests from CS under $12K.

That's the context graph: institutional knowledge that was locked in one person's head, captured as decision traces, and transformed into organizational intelligence by a system that doesn't even know what domain it's analyzing.

---

## Success Criteria

The demo successfully illustrates context graphs if:

1. **Two systems, one graph**: The audience clearly sees that System A and System B are independent applications connected only by the shared trace store. The mining agent has no procurement-specific knowledge.
2. **The gap is visible**: Viewers can see cases where policy says one thing but the reviewer does another, and *why* - the decision traces make implicit reasoning explicit.
3. **Precedent compounds**: Later decisions in System A visibly reference earlier ones - the graph is a living system where past decisions inform future ones.
4. **Domain-agnostic discovery works**: The mining agent successfully identifies patterns, entities, and rules it was never told about - it discovers the domain from the traces themselves.
5. **Automation is earned**: The mining agent's recommendations are grounded in specific, traceable evidence - not "you approve TechFlow a lot" but "100% approval rate, zero overrides, across 6 traces: DT-001, DT-009, DT-025..."
6. **The multi-source narrative is clear**: Even though only one source exists in the demo, the UI and the mining agent's behavior make it obvious that connecting additional agent systems would multiply the value.
