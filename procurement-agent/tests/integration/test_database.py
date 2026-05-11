import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from src.database import (
    get_all_departments,
    get_all_policies,
    get_all_purchase_requests,
    get_all_vendors,
    get_assessments_for_request,
    get_connection,
    get_latest_assessment,
    get_purchase_request,
    get_unreviewed_assessments,
    init_schema,
    insert_assessment,
    insert_department,
    insert_purchase_request,
    insert_review,
    insert_vendor,
    next_request_id,
    update_request_status,
)
from src.models import (
    AssessmentRecord,
    Confidence,
    Department,
    EvaluatorAssessment,
    PolicyCompliance,
    PurchaseRequest,
    Recommendation,
    RequestStatus,
    ReviewDecision,
    ReviewerDecision,
    Vendor,
    VendorStatus,
)
from src.seed_data import seed
from tests.fixtures import CURATED_TEST_REQUESTS


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = get_connection(tmp_path / "test.db")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture()
def seeded_db(tmp_path: Path) -> sqlite3.Connection:
    """DB with reference data plus a small inline curated test set.

    `seed()` writes only reference data in production. The assessment /
    review tests below assume PR-001..PR-NN exist (foreign-key
    constraints), so we insert the test fixture set directly.
    """
    conn = get_connection(tmp_path / "test.db")
    seed(conn)
    for req in CURATED_TEST_REQUESTS:
        insert_purchase_request(conn, req)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def reference_only_db(tmp_path: Path) -> sqlite3.Connection:
    """DB after `seed()` exactly — reference data, no requests."""
    conn = get_connection(tmp_path / "test.db")
    seed(conn)
    yield conn
    conn.close()


class TestSchema:
    def test_tables_created(self, db: sqlite3.Connection):
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        assert tables == {
            "departments",
            "vendors",
            "policies",
            "purchase_requests",
            "assessments",
            "reviews",
        }

    def test_foreign_key_enforcement(self, db: sqlite3.Connection):
        """purchase_requests.department references departments.name."""
        req = PurchaseRequest(
            id="PR-001",
            requester="X",
            department="NonExistent",
            item="I",
            vendor="V",
            amount=1,
            justification="J",
            urgency="routine",
        )
        with pytest.raises(sqlite3.IntegrityError):
            insert_purchase_request(db, req)
            db.commit()


class TestInsertAndRetrieve:
    def test_insert_and_get_departments(self, db: sqlite3.Connection):
        dept = Department(name="Engineering", headcount=50, quarterly_budget=200_000)
        insert_department(db, dept)
        db.commit()

        result = get_all_departments(db)
        assert len(result) == 1
        assert result[0] == dept

    def test_insert_and_get_vendors(self, db: sqlite3.Connection):
        vendor = Vendor(name="TechFlow", status=VendorStatus.PREFERRED, categories=["software"], notes="Good")
        insert_vendor(db, vendor)
        db.commit()

        result = get_all_vendors(db)
        assert len(result) == 1
        assert result[0] == vendor

    def test_insert_and_get_purchase_request(self, db: sqlite3.Connection):
        insert_department(db, Department(name="Engineering", headcount=50, quarterly_budget=200_000))
        ts = datetime(2026, 4, 15, 10, 30, 0)
        req = PurchaseRequest(
            id="PR-001",
            requester="Alex",
            department="Engineering",
            item="Licenses",
            vendor="TechFlow",
            amount=3200,
            justification="Need them",
            urgency="routine",
            created_at=ts,
            updated_at=ts,
        )
        insert_purchase_request(db, req)
        db.commit()

        result = get_purchase_request(db, "PR-001")
        assert result == req
        assert result.created_at == ts
        assert result.updated_at == ts

    def test_get_nonexistent_request_returns_none(self, db: sqlite3.Connection):
        assert get_purchase_request(db, "PR-999") is None

    def test_duplicate_id_raises(self, db: sqlite3.Connection):
        insert_department(db, Department(name="Engineering", headcount=50, quarterly_budget=200_000))
        req = PurchaseRequest(
            id="PR-001", requester="X", department="Engineering",
            item="I", vendor="V", amount=1, justification="J", urgency="routine",
        )
        insert_purchase_request(db, req)
        db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            insert_purchase_request(db, req)


class TestUpdateStatus:
    def test_update_status(self, db: sqlite3.Connection):
        insert_department(db, Department(name="Eng", headcount=1, quarterly_budget=1000))
        req = PurchaseRequest(
            id="PR-001", requester="X", department="Eng",
            item="I", vendor="V", amount=1, justification="J", urgency="routine",
        )
        insert_purchase_request(db, req)
        db.commit()

        assert update_request_status(db, "PR-001", RequestStatus.PROCESSING)
        db.commit()

        updated = get_purchase_request(db, "PR-001")
        assert updated.status == RequestStatus.PROCESSING

    def test_update_nonexistent_returns_false(self, db: sqlite3.Connection):
        assert not update_request_status(db, "PR-999", RequestStatus.COMPLETED)


class TestNextRequestId:
    def test_empty_table_returns_001(self, db: sqlite3.Connection):
        assert next_request_id(db) == "PR-001"

    def test_after_seed_returns_next_id(self, reference_only_db: sqlite3.Connection):
        # `seed()` populates only reference data — no purchase requests —
        # so the next id off an empty requests table is PR-001.
        assert next_request_id(reference_only_db) == "PR-001"

    def test_increments_correctly(self, db: sqlite3.Connection):
        insert_department(db, Department(name="Eng", headcount=1, quarterly_budget=1000))
        for i in range(1, 4):
            req = PurchaseRequest(
                id=f"PR-{i:03d}", requester="X", department="Eng",
                item="I", vendor="V", amount=1, justification="J", urgency="routine",
            )
            insert_purchase_request(db, req)
        db.commit()
        assert next_request_id(db) == "PR-004"


class TestSeedData:
    def test_seed_populates_reference_data_only(self, reference_only_db: sqlite3.Connection):
        assert len(get_all_departments(reference_only_db)) == 5
        assert len(get_all_vendors(reference_only_db)) == 9
        assert len(get_all_policies(reference_only_db)) == 5
        # Purchase requests are NOT inserted by seed() — they go through
        # the API now (see src/seed_requests.py for the bulk helper).
        assert len(get_all_purchase_requests(reference_only_db)) == 0

    def test_seed_departments_match_spec(self, seeded_db: sqlite3.Connection):
        depts = {d.name: d for d in get_all_departments(seeded_db)}
        assert depts["Engineering"].headcount == 50
        assert depts["Engineering"].quarterly_budget == 200_000
        assert depts["Customer Success"].headcount == 15
        assert depts["Security"].quarterly_budget == 100_000

    def test_seed_vendors_match_spec(self, seeded_db: sqlite3.Connection):
        vendors = {v.name: v for v in get_all_vendors(seeded_db)}
        assert vendors["TechFlow"].status == VendorStatus.PREFERRED
        assert vendors["Insight Partners"].status == VendorStatus.SUSPENDED
        assert vendors["FreshStack"].status == VendorStatus.NOT_LISTED


def _make_assessment(request_id: str, session_id: str, ts: datetime | None = None) -> AssessmentRecord:
    assessment = EvaluatorAssessment(
        request_id=request_id,
        policy_compliance=PolicyCompliance.COMPLIANT,
        policy_details="OK",
        budget_status="OK",
        vendor_status="OK",
        duplicate_check="OK",
        history_notes="OK",
        recommendation=Recommendation.APPROVE,
        recommendation_reasoning="All clear",
        confidence=Confidence.HIGH,
    )
    kwargs = {"request_id": request_id, "session_id": session_id, "assessment": assessment}
    if ts:
        kwargs["created_at"] = ts
    return AssessmentRecord(**kwargs)


def _make_review_decision(request_id: str, override: bool = False) -> ReviewDecision:
    return ReviewDecision(
        request_id=request_id,
        agent_recommendation=Recommendation.APPROVE,
        reviewer_decision=ReviewerDecision.REJECT if override else ReviewerDecision.APPROVE,
        override=override,
        reasoning="Test review",
        confidence=Confidence.HIGH,
    )


class TestAssessments:
    def test_insert_and_get_without_review(self, seeded_db: sqlite3.Connection):
        ts = datetime(2026, 4, 18, 10, 0, 0)
        record = _make_assessment("PR-001", "sess-1", ts)
        insert_assessment(seeded_db, record)
        seeded_db.commit()

        records = get_assessments_for_request(seeded_db, "PR-001")
        assert len(records) == 1
        assert records[0].session_id == "sess-1"
        assert records[0].assessment.recommendation == Recommendation.APPROVE
        assert records[0].review is None
        assert records[0].reviewed_at is None

    def test_multiple_assessments_ordered_newest_first(self, seeded_db: sqlite3.Connection):
        insert_assessment(seeded_db, _make_assessment("PR-001", "sess-old", datetime(2026, 4, 17, 10, 0, 0)))
        insert_assessment(seeded_db, _make_assessment("PR-001", "sess-new", datetime(2026, 4, 18, 10, 0, 0)))
        seeded_db.commit()

        records = get_assessments_for_request(seeded_db, "PR-001")
        assert len(records) == 2
        assert records[0].session_id == "sess-new"
        assert records[1].session_id == "sess-old"

    def test_get_latest_assessment(self, seeded_db: sqlite3.Connection):
        insert_assessment(seeded_db, _make_assessment("PR-002", "sess-1", datetime(2026, 4, 17, 10, 0, 0)))
        insert_assessment(seeded_db, _make_assessment("PR-002", "sess-2", datetime(2026, 4, 18, 10, 0, 0)))
        seeded_db.commit()

        latest = get_latest_assessment(seeded_db, "PR-002")
        assert latest.session_id == "sess-2"

    def test_get_latest_assessment_none(self, seeded_db: sqlite3.Connection):
        assert get_latest_assessment(seeded_db, "PR-001") is None

    def test_assessments_scoped_to_request(self, seeded_db: sqlite3.Connection):
        insert_assessment(seeded_db, _make_assessment("PR-001", "sess-a", datetime(2026, 4, 18, 10, 0, 0)))
        insert_assessment(seeded_db, _make_assessment("PR-002", "sess-b", datetime(2026, 4, 18, 11, 0, 0)))
        seeded_db.commit()

        assert len(get_assessments_for_request(seeded_db, "PR-001")) == 1
        assert len(get_assessments_for_request(seeded_db, "PR-002")) == 1


class TestReviews:
    def test_insert_review_attaches_to_assessment(self, seeded_db: sqlite3.Connection):
        insert_assessment(seeded_db, _make_assessment("PR-001", "sess-1", datetime(2026, 4, 18, 10, 0, 0)))
        seeded_db.commit()

        review = _make_review_decision("PR-001", override=True)
        insert_review(seeded_db, "sess-1", review, datetime(2026, 4, 19, 9, 0, 0))
        seeded_db.commit()

        records = get_assessments_for_request(seeded_db, "PR-001")
        assert len(records) == 1
        assert records[0].review is not None
        assert records[0].review.override is True
        assert records[0].reviewed_at == datetime(2026, 4, 19, 9, 0, 0)

    def test_review_requires_existing_session(self, seeded_db: sqlite3.Connection):
        with pytest.raises(sqlite3.IntegrityError):
            insert_review(seeded_db, "no-such-session", _make_review_decision("PR-001"))
            seeded_db.commit()

    def test_one_review_per_session(self, seeded_db: sqlite3.Connection):
        insert_assessment(seeded_db, _make_assessment("PR-001", "sess-1", datetime(2026, 4, 18, 10, 0, 0)))
        seeded_db.commit()
        insert_review(seeded_db, "sess-1", _make_review_decision("PR-001"))
        seeded_db.commit()

        with pytest.raises(sqlite3.IntegrityError):
            insert_review(seeded_db, "sess-1", _make_review_decision("PR-001"))
            seeded_db.commit()

    def test_get_unreviewed_assessments(self, seeded_db: sqlite3.Connection):
        insert_assessment(seeded_db, _make_assessment("PR-001", "sess-a", datetime(2026, 4, 18, 10, 0, 0)))
        insert_assessment(seeded_db, _make_assessment("PR-002", "sess-b", datetime(2026, 4, 18, 11, 0, 0)))
        seeded_db.commit()
        insert_review(seeded_db, "sess-a", _make_review_decision("PR-001"))
        seeded_db.commit()

        unreviewed = get_unreviewed_assessments(seeded_db)
        assert len(unreviewed) == 1
        assert unreviewed[0].session_id == "sess-b"
