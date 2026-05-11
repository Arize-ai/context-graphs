"""Tests for the LangChain tool helpers in src/agent/tools.py.

The public `@tool`-decorated entry points open their own DB connections via
`get_connection`, so unit tests target the underscore-prefixed helpers and
pass in a seeded test connection. The `@tool` wrappers are thin and are
exercised end-to-end by `test_process_endpoint`.
"""

import sqlite3
from pathlib import Path

import pytest

from src.agent.tools import (
    _check_budget,
    _check_policy,
    _lookup_department,
    _lookup_vendor,
)
from src.database import get_connection
from src.seed_data import seed
from src.variants import Variant


@pytest.fixture()
def seeded_db(tmp_path: Path) -> sqlite3.Connection:
    conn = get_connection(tmp_path / "test.db")
    seed(conn)
    yield conn
    conn.close()


class TestCheckPolicy:
    def test_under_5k_auto_approved(self, seeded_db: sqlite3.Connection):
        out = _check_policy(seeded_db, 4000, "TechFlow")
        assert "auto-approved" in out
        assert "$5,000" in out

    def test_5k_to_25k_manager(self, seeded_db: sqlite3.Connection):
        out = _check_policy(seeded_db, 12000, "TechFlow")
        assert "manager approval" in out
        assert "$5K-$25K" in out

    def test_25k_to_50k_vp(self, seeded_db: sqlite3.Connection):
        out = _check_policy(seeded_db, 35000, "TechFlow")
        assert "VP approval" in out

    def test_over_50k_vp(self, seeded_db: sqlite3.Connection):
        out = _check_policy(seeded_db, 75000, "TechFlow")
        assert "VP approval" in out

    def test_returns_full_policy_catalog(self, seeded_db: sqlite3.Connection):
        out = _check_policy(seeded_db, 1000, "TechFlow")
        assert "Software Procurement" in out
        assert "Hardware Procurement" in out
        assert "Consulting Engagements" in out


class TestLookupVendor:
    def test_preferred(self, seeded_db: sqlite3.Connection):
        out = _lookup_vendor(seeded_db, "TechFlow")
        assert "Status: preferred" in out

    def test_suspended_includes_notes(self, seeded_db: sqlite3.Connection):
        out = _lookup_vendor(seeded_db, "Insight Partners")
        assert "Status: suspended" in out
        assert "billing dispute" in out.lower()

    def test_case_insensitive(self, seeded_db: sqlite3.Connection):
        upper = _lookup_vendor(seeded_db, "TECHFLOW")
        lower = _lookup_vendor(seeded_db, "techflow")
        assert "TechFlow" in upper and "TechFlow" in lower

    def test_unknown_vendor_returns_not_listed(self, seeded_db: sqlite3.Connection):
        out = _lookup_vendor(seeded_db, "UnknownCo")
        assert "not_listed" in out
        assert "not found" in out.lower()


class TestCheckBudget:
    def test_known_department(self, seeded_db: sqlite3.Connection):
        out = _check_budget(seeded_db, "Engineering", 10000)
        assert "Engineering" in out
        assert "Quarterly budget" in out
        assert "$10,000" in out

    def test_unknown_department(self, seeded_db: sqlite3.Connection):
        out = _check_budget(seeded_db, "NoSuchDept", 1000)
        assert "not found" in out.lower()


class TestLookupVendorWithVariant:
    """Variant overlay surfaces extra metadata; baseline output unchanged when no overlay."""

    def test_baseline_output_unchanged(self, seeded_db: sqlite3.Connection):
        out = _lookup_vendor(seeded_db, "DataStream Analytics", variant=Variant())
        # Pre-variant fields still present
        assert "Status: approved" in out
        assert "Cost overrun history" in out
        # Variant-only fields absent
        assert "Cost-overrun factor" not in out
        assert "Relationship credit" not in out
        assert "Deprecation notice" not in out

    def test_overlay_surfaces_cost_overrun_factor(
        self, seeded_db: sqlite3.Connection
    ):
        variant = Variant(
            id="cycle-1-B",
            vendor_overlay={"DataStream Analytics": {"cost_overrun_factor": 1.4}},
        )
        out = _lookup_vendor(
            seeded_db, "DataStream Analytics", variant=variant, amount=10000
        )
        assert "Cost-overrun factor: 1.40" in out
        # Effective amount is reported when amount is provided
        assert "$14,000" in out

    def test_overlay_surfaces_relationship_credit(
        self, seeded_db: sqlite3.Connection
    ):
        variant = Variant(
            id="cycle-1-B",
            vendor_overlay={
                "Vertex Solutions": {"relationship_credit": "March outage emergency pricing"}
            },
        )
        out = _lookup_vendor(seeded_db, "Vertex Solutions", variant=variant)
        assert "Relationship credit: March outage emergency pricing" in out

    def test_overlay_surfaces_deprecation(self, seeded_db: sqlite3.Connection):
        variant = Variant(
            id="cycle-1-B",
            vendor_overlay={"CloudBase Inc": {"deprecating_in_favor_of": "Vertex Solutions"}},
        )
        out = _lookup_vendor(seeded_db, "CloudBase Inc", variant=variant)
        assert "Deprecation notice" in out
        assert "Vertex Solutions" in out


class TestLookupDepartment:
    """The new lookup_department tool returns 'no data' baseline; overlay supplies notes."""

    def test_baseline_returns_no_data(self, seeded_db: sqlite3.Connection):
        out = _lookup_department(seeded_db, "Marketing", variant=Variant())
        assert "No behavior data available" in out

    def test_baseline_with_no_overlay_says_decide_alone(
        self, seeded_db: sqlite3.Connection
    ):
        out = _lookup_department(seeded_db, "Engineering", variant=Variant())
        assert "policy and budget" in out

    def test_overlay_supplies_behavior_notes(self, seeded_db: sqlite3.Connection):
        variant = Variant(
            id="cycle-1-B",
            department_overlay={
                "Marketing": {
                    "behavior_notes": [
                        "Tends to panic-buy single-campaign tools",
                        "Prefer sustained-use justifications",
                    ]
                }
            },
        )
        out = _lookup_department(seeded_db, "Marketing", variant=variant)
        assert "Behavioral context" in out
        assert "panic-buy single-campaign tools" in out
        assert "sustained-use justifications" in out

    def test_unknown_department_with_no_overlay(self, seeded_db: sqlite3.Connection):
        out = _lookup_department(seeded_db, "NoSuchDept", variant=Variant())
        assert "not found" in out.lower()
