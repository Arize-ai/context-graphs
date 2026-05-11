"""Async helper that seeds purchase requests through the procurement-agent API.

Run this against a running procurement-agent (the API auto-processes each
request, so the agent must be up and reachable). POSTs every curated +
generated request from `synthetic_data.py`, 10 at a time via an asyncio
semaphore, and reports per-request progress.

Usage:
    cd scripts/
    uv run python seed_requests.py

Environment:
    PROCUREMENT_AGENT_URL — base URL of the API (default http://localhost:8000)
    SEED_PARALLELISM      — max concurrent in-flight requests (default 10)
    SEED_TIMEOUT_SECONDS  — per-request HTTP timeout (default 180)
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any

import httpx

from synthetic_data import all_requests, to_create_body

DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_PARALLELISM = 10
DEFAULT_TIMEOUT_SECONDS = 180


async def _post_one(
    client: httpx.AsyncClient,
    body: dict[str, Any],
    sem: asyncio.Semaphore,
) -> tuple[bool, str]:
    async with sem:
        try:
            resp = await client.post("/api/requests", json=body)
            resp.raise_for_status()
            data = resp.json()
            return True, f"{data['id']} → {data['status']}"
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:200]
            return False, f"HTTP {e.response.status_code}: {detail}"
        except httpx.HTTPError as e:
            return False, f"{type(e).__name__}: {e}"


async def _seed(
    api_url: str,
    parallelism: int,
    timeout_seconds: float,
    bodies: list[dict[str, Any]],
) -> int:
    sem = asyncio.Semaphore(parallelism)
    timeout = httpx.Timeout(timeout_seconds)

    async with httpx.AsyncClient(base_url=api_url, timeout=timeout) as client:
        # Probe the API early so we fail fast on a misconfigured URL.
        try:
            probe = await client.get("/api/requests", timeout=5)
            probe.raise_for_status()
        except Exception as e:  # noqa: BLE001 — probe surfaces any failure
            print(f"API not reachable at {api_url}: {e}", file=sys.stderr)
            return 1

        total = len(bodies)
        succeeded = 0
        failed = 0
        start = time.monotonic()

        tasks = [
            asyncio.create_task(_post_one(client, body, sem)) for body in bodies
        ]
        for i, completed in enumerate(asyncio.as_completed(tasks), start=1):
            ok, info = await completed
            if ok:
                succeeded += 1
                print(f"[{i:>3}/{total}] ✓  {info}")
            else:
                failed += 1
                print(f"[{i:>3}/{total}] ✗  {info}", file=sys.stderr)

        elapsed = time.monotonic() - start
        print(
            f"\nDone in {elapsed:.1f}s. "
            f"Succeeded: {succeeded}, Failed: {failed}, Total: {total}"
        )
        return 0 if failed == 0 else 1


def main() -> int:
    api_url = os.environ.get("PROCUREMENT_AGENT_URL", DEFAULT_API_URL).rstrip("/")
    parallelism = int(os.environ.get("SEED_PARALLELISM", DEFAULT_PARALLELISM))
    timeout_seconds = float(
        os.environ.get("SEED_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    )

    bodies = [to_create_body(req) for req in all_requests()]
    print(
        f"Seeding {len(bodies)} requests against {api_url} "
        f"(parallelism={parallelism}, timeout={timeout_seconds:.0f}s)..."
    )
    return asyncio.run(_seed(api_url, parallelism, timeout_seconds, bodies))


if __name__ == "__main__":
    sys.exit(main())
