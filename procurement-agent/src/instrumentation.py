"""Arize AX tracing setup for the procurement agent.

This module is imported by `src.main` *before* any LangChain / OpenAI imports
so the OpenInference instrumentors can monkey-patch those libraries on load.

Reads `ARIZE_API_KEY` and `ARIZE_SPACE_ID` from the environment; if either is
missing, instrumentation is skipped (no-op) so unit tests and unconfigured
local runs still work.

The Arize project name is derived from `EXPERIMENT_VARIANT`:

  - unset                → `procurement-agent` (frozen cycle-0 baseline)
  - `cycle-1-A`          → `procurement-agent-cycle-1-A`
  - `cycle-N-X`          → `procurement-agent-cycle-N-X`

This keeps each variant's traces in its own Arize project so cycle-N+1 mining
can target a specific project directly, and the project list visualizes the
agent's evolution over the loop.

`LangChainInstrumentor` covers LangGraph too — `langchain.agents.create_agent`
returns a `CompiledStateGraph` and its callbacks flow through LangChain.
"""

import os
import sys

_INSTRUMENTED = False
BASELINE_PROJECT = "procurement-agent"


def resolve_project_name() -> str:
    """Compute the Arize project name from `EXPERIMENT_VARIANT`."""
    variant = os.environ.get("EXPERIMENT_VARIANT", "").strip()
    if not variant:
        return BASELINE_PROJECT
    return f"{BASELINE_PROJECT}-{variant}"


def setup_tracing(project_name: str | None = None) -> None:
    global _INSTRUMENTED
    if _INSTRUMENTED:
        return

    api_key = os.environ.get("ARIZE_API_KEY")
    space_id = os.environ.get("ARIZE_SPACE_ID")
    if not api_key or not space_id:
        print(
            "[instrumentation] ARIZE_API_KEY or ARIZE_SPACE_ID not set — skipping Arize tracing.",
            file=sys.stderr,
        )
        return

    resolved_project = project_name if project_name is not None else resolve_project_name()

    from arize.otel import register
    from openinference.instrumentation.langchain import LangChainInstrumentor
    # from openinference.instrumentation.openai import OpenAIInstrumentor

    tracer_provider = register(
        space_id=space_id,
        api_key=api_key,
        project_name=resolved_project,
        batch=False,
        log_to_console=True,
    )

    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
    # OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

    _INSTRUMENTED = True
    print(
        f"[instrumentation] Arize tracing enabled for project '{resolved_project}'.",
        file=sys.stderr,
    )

    # Ensure annotation configs exist for human-review overrides. Idempotent
    # (no-op on re-create), best-effort — failures don't block startup.
    try:
        from src.annotations import ensure_configs
        ensure_configs(space_id=space_id)
    except Exception as e:  # noqa: BLE001
        print(
            f"[instrumentation] annotation config setup failed: {e}",
            file=sys.stderr,
        )


setup_tracing()
