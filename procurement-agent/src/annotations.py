"""Arize annotation management for human-review overrides.

The agent owns annotation lifecycle so every override that flows through
`/api/requests/{id}/override` — whether from the UI or the
reviewer-agent CLI — produces both a traced agent run AND the
matching human-review annotation in Arize, with no client-side work.

Two responsibilities:

1. **Configs (schema)** — `ensure_configs()` runs once at startup. We
   shell out to the `ax` CLI because the Arize Python SDK doesn't expose
   config CRUD; `ax` is idempotent (409 Conflict on re-create is treated
   as success).

2. **Per-override annotations** — `apply_override_annotation()` builds a
   one-row pandas DataFrame keyed on `context.span_id` and calls
   `Client.log_annotations`. Failures log a warning but don't raise: the
   override's persisted `ReviewDecision` is the durable record of human
   intent; the annotation is the secondary signal in Arize.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import HumanOverride

logger = logging.getLogger(__name__)

DEFAULT_PROJECT_NAME = "procurement-agent"

# The Arize SDK validates `annotation.<name>.label` values at 1–100 chars.
# Long human reasoning routinely exceeds that, so we model the structured
# fields as categorical / short freeform `.label`s and use the per-row
# `annotation.notes` sink for the long-form reviewer text.
_LABEL_MAX_LEN = 100

_CATEGORICAL_CONFIGS: list[tuple[str, list[str]]] = [
    ("Reviewer Decision", ["approve", "reject"]),
    ("Reviewer Confidence", ["high", "medium", "low"]),
]
# Reviewer Name is a freeform config but its values are short (a person's
# name), so it stays as a `.label`. Reasoning, precedent, and conditions
# go into `annotation.notes` because they routinely exceed the label cap.
_SHORT_FREEFORM_CONFIGS: list[str] = ["Reviewer Name"]

_configs_lock = threading.Lock()
_configs_ensured = False
_client: object | None = None  # arize.pandas.logger.Client when ready


def _arize_creds() -> tuple[str, str] | None:
    api_key = os.environ.get("ARIZE_API_KEY")
    space_id = os.environ.get("ARIZE_SPACE_ID")
    if not api_key or not space_id:
        return None
    return api_key, space_id


def ensure_configs(space_id: str | None = None) -> None:
    """Create the override annotation configs in the Arize space if missing.

    Idempotent: a 409 Conflict from a prior run is fine. Network/CLI
    failures are logged and swallowed so a flaky `ax` install doesn't
    block the agent from starting.
    """
    global _configs_ensured
    with _configs_lock:
        if _configs_ensured:
            return

        creds = _arize_creds() if space_id is None else (None, space_id)
        if creds is None:
            logger.info("annotations: skipping config setup — ARIZE creds not set")
            return
        space = creds[1]

        for name, values in _CATEGORICAL_CONFIGS:
            cmd = [
                "ax", "annotation-configs", "create",
                "--name", name,
                "--space", space,
                "--type", "categorical",
            ]
            for v in values:
                cmd += ["--value", v]
            _run_idempotent(cmd, name)

        for name in _SHORT_FREEFORM_CONFIGS:
            cmd = [
                "ax", "annotation-configs", "create",
                "--name", name,
                "--space", space,
                "--type", "freeform",
            ]
            _run_idempotent(cmd, name)

        _configs_ensured = True


def _run_idempotent(cmd: list[str], config_name: str) -> None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        logger.warning("annotations: failed to invoke ax for %s: %s", config_name, e)
        return

    if result.returncode == 0:
        logger.info("annotations: created config %r", config_name)
    else:
        # Most likely 409 — config already exists. Treat as success unless
        # the message clearly indicates something else.
        message = (result.stderr or result.stdout or "").lower()
        if "already exists" in message or "409" in message or "conflict" in message:
            logger.info("annotations: config %r already exists (ok)", config_name)
        else:
            logger.warning(
                "annotations: ax create failed for %r: %s",
                config_name,
                (result.stderr or result.stdout or "").strip()[:300],
            )


def _get_client():
    """Lazily build the Arize SDK client. Returns None when creds missing."""
    global _client
    if _client is not None:
        return _client
    creds = _arize_creds()
    if creds is None:
        return None
    api_key, space_id = creds
    from arize.pandas.logger import Client

    _client = Client(api_key=api_key, space_id=space_id)
    return _client


def apply_override_annotation(
    span_id: str,
    override: HumanOverride,
    project_name: str = DEFAULT_PROJECT_NAME,
) -> bool:
    """Push the reviewer's annotation onto the root span of the override run.

    Returns True if the annotation was sent; False on any failure
    (caller logs but should not surface this to the user — the
    persisted `ReviewDecision` is the durable record).
    """
    client = _get_client()
    if client is None:
        logger.info("annotations: no Arize creds, skipping annotation for span %s", span_id)
        return False

    import pandas as pd

    # Build the long-form notes block. Reasoning, precedent, and
    # conditions live here because they routinely exceed the SDK's
    # 100-char `.label` cap.
    notes_parts: list[str] = []
    if override.reasoning:
        notes_parts.append(f"Reasoning: {override.reasoning}")
    if override.precedent_applied:
        notes_parts.append(f"Precedent: {override.precedent_applied}")
    if override.conditions:
        notes_parts.append(f"Conditions: {override.conditions}")
    notes = "\n".join(notes_parts)

    reviewer_name = (override.reviewer_name or "").strip()[:_LABEL_MAX_LEN]

    row: dict[str, object] = {
        "context.span_id": span_id,
        "annotation.Reviewer Decision.label": override.decision.value,
        "annotation.Reviewer Confidence.label": override.confidence.value,
        "annotation.Reviewer Decision.updated_by": reviewer_name,
    }
    if reviewer_name:
        row["annotation.Reviewer Name.label"] = reviewer_name
    if notes:
        row["annotation.notes"] = notes

    df = pd.DataFrame([row])

    try:
        client.log_annotations(dataframe=df, project_name=project_name, validate=True)
    except Exception as e:  # noqa: BLE001 — best-effort; never fail the override
        logger.warning("annotations: log_annotations failed for span %s: %s", span_id, e)
        return False

    logger.warning(
        "annotations: pushed override annotation for span %s (decision=%s, by=%s)",
        span_id,
        override.decision.value,
        override.reviewer_name or "(anonymous)",
    )
    return True
