# scripts

Synthetic data and helper scripts for the procurement demo. Self-contained
— depends only on `httpx`, no coupling to `procurement-agent` source code.

## Files

- `synthetic_data.py` — `curated_requests()` (30 hand-written) +
  `generated_requests()` (100 procedurally generated, fixed RNG seed).
  Returns plain dicts ready to JSON-serialize. Also exports
  `to_create_body()` (strips server-assigned fields) and
  `assign_curated_timestamps` / `assign_generated_timestamps` for tests
  that bypass the API and write to the database directly.
- `seed_requests.py` — async script that POSTs every `all_requests()`
  entry to `/api/requests`, 10 at a time. Each POST triggers the agent's
  auto-process flow.

## Running

The procurement-agent must be running first (it auto-processes each
incoming request, so the script needs the API live).

```bash
cd scripts/
uv sync
uv run python seed_requests.py
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `PROCUREMENT_AGENT_URL` | `http://localhost:8000` | Base URL of the agent's HTTP API. |
| `SEED_PARALLELISM` | `10` | Max concurrent in-flight requests. |
| `SEED_TIMEOUT_SECONDS` | `180` | Per-request HTTP timeout. |

## Output

Per-request progress on stdout, summary at the end:

```
Seeding 130 requests against http://localhost:8000 (parallelism=10, timeout=180s)...
[  1/130] ✓  PR-001 → completed
[  2/130] ✓  PR-002 → completed
...

Done in 103.4s. Succeeded: 130, Failed: 0, Total: 130
```

A typical full run is ~100 seconds. Each request triggers an LLM call
inside the agent, so this consumes real OpenAI tokens.
