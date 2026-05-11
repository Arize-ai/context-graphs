"""Smoke tests for the synthetic-data shape.

These don't run the seed script (no live API in CI). They verify the
contract that `seed_requests.py` and any downstream consumer relies on.
"""

from synthetic_data import (
    all_requests,
    assign_curated_timestamps,
    assign_generated_timestamps,
    curated_requests,
    generated_requests,
    to_create_body,
)

CREATE_BODY_FIELDS = {
    "requester",
    "department",
    "item",
    "vendor",
    "amount",
    "justification",
    "urgency",
}


class TestCounts:
    def test_curated_count(self):
        assert len(curated_requests()) == 30

    def test_generated_count(self):
        assert len(generated_requests()) == 100

    def test_all_is_curated_plus_generated(self):
        assert len(all_requests()) == 130


class TestCuratedShape:
    def test_ids_are_contiguous(self):
        ids = [r["id"] for r in curated_requests()]
        assert ids == [f"PR-{i:03d}" for i in range(1, 31)]

    def test_pr027_negative_amount(self):
        pr027 = next(r for r in curated_requests() if r["id"] == "PR-027")
        assert pr027["amount"] == -3000

    def test_each_record_has_create_body_fields(self):
        for r in curated_requests():
            for f in CREATE_BODY_FIELDS:
                assert f in r, f"{r['id']} missing {f}"


class TestGeneratedShape:
    def test_ids_continue_from_31(self):
        ids = [r["id"] for r in generated_requests()]
        assert ids == [f"PR-{i:03d}" for i in range(31, 131)]

    def test_deterministic_seed(self):
        # Two calls produce identical output — fixed RNG seed.
        assert generated_requests() == generated_requests()


class TestToCreateBody:
    def test_strips_server_assigned_fields(self):
        record = curated_requests()[0]
        body = to_create_body(record)
        assert set(body.keys()) == CREATE_BODY_FIELDS
        # Specifically: id and timestamps are not sent.
        assert "id" not in body
        assert "created_at" not in body
        assert "updated_at" not in body

    def test_preserves_payload_values(self):
        record = curated_requests()[0]
        body = to_create_body(record)
        for f in CREATE_BODY_FIELDS:
            assert body[f] == record[f]


class TestTimestampHelpers:
    def test_curated_timestamps_attached(self):
        stamped = assign_curated_timestamps(curated_requests())
        assert len(stamped) == 30
        for r in stamped:
            assert "created_at" in r
            assert "updated_at" in r

    def test_generated_timestamps_attached(self):
        stamped = assign_generated_timestamps(generated_requests())
        assert len(stamped) == 100
        for r in stamped:
            assert "created_at" in r
            assert "updated_at" in r
