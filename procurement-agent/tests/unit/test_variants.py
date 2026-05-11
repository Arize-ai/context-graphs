"""Tests for src/variants.load_variant.

Variant loading is the gate for runtime parameterization. With no
EXPERIMENT_VARIANT set, the agent must behave exactly as it did pre-
variant — these tests anchor that contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.variants import VARIANT_ENV, Variant, load_variant


def test_no_env_returns_empty_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIANT_ENV, raising=False)
    v = load_variant()
    assert isinstance(v, Variant)
    assert v.is_active is False
    assert v.id == ""
    assert v.extra_context == ""
    assert v.vendor_overlay == {}
    assert v.department_overlay == {}


def test_explicit_empty_string_is_inactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIANT_ENV, "")
    v = load_variant()
    assert v.is_active is False


def test_missing_variant_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="does not exist"):
        load_variant(variant_id="never-created", variants_dir=tmp_path)


def test_loads_all_files(tmp_path: Path) -> None:
    variant_dir = tmp_path / "cycle-1-B"
    variant_dir.mkdir(parents=True)
    (variant_dir / "system_prompt.txt").write_text(
        "Reviewers cite institutional knowledge — read it.", encoding="utf-8"
    )
    (variant_dir / "vendors.json").write_text(
        json.dumps(
            {
                "DataStream Analytics": {"cost_overrun_factor": 1.4},
                "CloudBase Inc": {"deprecating_in_favor_of": "Vertex Solutions"},
            }
        ),
        encoding="utf-8",
    )
    (variant_dir / "departments.json").write_text(
        json.dumps({"Marketing": {"behavior_notes": ["Panic-buy single-campaign tools"]}}),
        encoding="utf-8",
    )

    v = load_variant(variant_id="cycle-1-B", variants_dir=tmp_path)
    assert v.is_active is True
    assert v.id == "cycle-1-B"
    assert "institutional knowledge" in v.extra_context
    assert v.vendor_overlay["DataStream Analytics"]["cost_overrun_factor"] == 1.4
    assert (
        v.vendor_overlay["CloudBase Inc"]["deprecating_in_favor_of"]
        == "Vertex Solutions"
    )
    assert v.department_overlay["Marketing"]["behavior_notes"] == [
        "Panic-buy single-campaign tools"
    ]


def test_partial_files_use_safe_defaults(tmp_path: Path) -> None:
    """A variant directory with only one file is valid — others fall back to empty."""
    variant_dir = tmp_path / "cycle-1-A"
    variant_dir.mkdir(parents=True)
    (variant_dir / "system_prompt.txt").write_text("Read context graph.", encoding="utf-8")

    v = load_variant(variant_id="cycle-1-A", variants_dir=tmp_path)
    assert v.is_active is True
    assert v.extra_context == "Read context graph."
    assert v.vendor_overlay == {}
    assert v.department_overlay == {}


def test_invalid_json_raises_with_path(tmp_path: Path) -> None:
    variant_dir = tmp_path / "broken"
    variant_dir.mkdir(parents=True)
    (variant_dir / "vendors.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Invalid JSON"):
        load_variant(variant_id="broken", variants_dir=tmp_path)


def test_non_object_json_raises(tmp_path: Path) -> None:
    variant_dir = tmp_path / "wrong-shape"
    variant_dir.mkdir(parents=True)
    (variant_dir / "vendors.json").write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(RuntimeError, match="JSON object"):
        load_variant(variant_id="wrong-shape", variants_dir=tmp_path)
