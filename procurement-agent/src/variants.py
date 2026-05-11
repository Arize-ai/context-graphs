"""Experiment-variant loading.

When `EXPERIMENT_VARIANT` is set, the procurement-agent loads a config
bundle from `experiments/variants/<id>/` and overlays it at *read time*
on top of the canonical reference data — no DB rewrite, no behavior
change with the variable unset.

Variant directory layout (all files optional):

    experiments/variants/<id>/
    ├── manifest.yaml          # human-facing record of what was applied
    ├── system_prompt.txt      # text appended to evaluator system prompt
    ├── vendors.json           # {"VendorName": {"cost_overrun_factor": 1.4, ...}}
    └── departments.json       # {"DeptName": {"behavior_notes": ["panic-buy"]}}

The vendor / department overlays are partial — only the fields you specify
get applied. Fields you omit fall back to the DB's baseline values.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VARIANTS_DIR = REPO_ROOT / "experiments" / "variants"

VARIANT_ENV = "EXPERIMENT_VARIANT"


@dataclass(frozen=True)
class Variant:
    """The loaded variant — empty fields when no variant is active."""

    id: str = ""
    extra_context: str = ""
    vendor_overlay: dict[str, dict] = field(default_factory=dict)
    department_overlay: dict[str, dict] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return bool(self.id)


def _read_optional_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in variant file {path}: {e}") from e
    if not isinstance(data, dict):
        raise RuntimeError(f"Variant file {path} must contain a JSON object")
    return data


def _read_optional_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_variant(
    variant_id: str | None = None,
    variants_dir: Path = DEFAULT_VARIANTS_DIR,
) -> Variant:
    """Load the active variant, or an empty Variant when none is set.

    Resolution order:
      1. Explicit `variant_id` argument (used by tests).
      2. `EXPERIMENT_VARIANT` env var.
      3. None → empty Variant (baseline behavior).
    """
    resolved = variant_id if variant_id is not None else os.environ.get(VARIANT_ENV, "")
    if not resolved:
        return Variant()

    base = variants_dir / resolved
    if not base.is_dir():
        raise RuntimeError(
            f"EXPERIMENT_VARIANT={resolved!r} but {base} does not exist."
        )

    return Variant(
        id=resolved,
        extra_context=_read_optional_text(base / "system_prompt.txt"),
        vendor_overlay=_read_optional_json(base / "vendors.json"),
        department_overlay=_read_optional_json(base / "departments.json"),
    )
