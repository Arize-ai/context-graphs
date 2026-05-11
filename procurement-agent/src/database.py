"""SQLite persistence layer.

Tables: departments, vendors, policies (reference data); purchase_requests
(request lifecycle); assessments (one row per agent run, keyed by
`session_id`); reviews (zero-or-one row per assessment, joined back via
`session_id`). Connections are opened with WAL journaling and foreign-key
enforcement enabled.

The DB path is derived from `EXPERIMENT_VARIANT`:

  - unset                → `data/procurement.db` (frozen cycle-0 baseline)
  - `cycle-1-A`          → `data/procurement-cycle-1-A.db`
  - `cycle-N-X`          → `data/procurement-cycle-N-X.db`

This pairs with the per-variant Arize project name in `instrumentation.py` —
one env var flips both DB and project together so a variant agent never
writes into the canonical baseline DB.
"""

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from src.models import (
    AssessmentRecord,
    Department,
    EvaluatorAssessment,
    Policy,
    PurchaseRequest,
    RequestStatus,
    ReviewDecision,
    Urgency,
    Vendor,
    VendorStatus,
)

_ISO_FMT = "%Y-%m-%dT%H:%M:%S"


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime(_ISO_FMT)

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "procurement.db"


def resolve_db_path() -> Path:
    """Return the DB path for the current EXPERIMENT_VARIANT (baseline if unset)."""
    variant = os.environ.get("EXPERIMENT_VARIANT", "").strip()
    if not variant:
        return DEFAULT_DB_PATH
    return DEFAULT_DB_PATH.parent / f"procurement-{variant}.db"


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path if db_path is not None else resolve_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS departments (
            name TEXT PRIMARY KEY,
            headcount INTEGER NOT NULL,
            quarterly_budget REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vendors (
            name TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            categories TEXT NOT NULL,  -- JSON array
            notes TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS policies (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            rules TEXT NOT NULL  -- JSON array
        );

        CREATE TABLE IF NOT EXISTS purchase_requests (
            id TEXT PRIMARY KEY,
            requester TEXT NOT NULL,
            department TEXT NOT NULL REFERENCES departments(name),
            item TEXT NOT NULL,
            vendor TEXT NOT NULL,
            amount REAL NOT NULL,
            justification TEXT NOT NULL,
            urgency TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL REFERENCES purchase_requests(id),
            session_id TEXT NOT NULL UNIQUE,
            assessment_json TEXT NOT NULL,
            span_id TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE REFERENCES assessments(session_id),
            review_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    # Migration: add span_id column if missing (existing DBs from before this
    # field existed). Idempotent — `ALTER TABLE ADD COLUMN` raises if column
    # already exists, so we check first.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(assessments)").fetchall()}
    if "span_id" not in cols:
        conn.execute("ALTER TABLE assessments ADD COLUMN span_id TEXT")


def insert_department(conn: sqlite3.Connection, dept: Department) -> None:
    conn.execute(
        "INSERT INTO departments (name, headcount, quarterly_budget) VALUES (?, ?, ?)",
        (dept.name, dept.headcount, dept.quarterly_budget),
    )


def insert_vendor(conn: sqlite3.Connection, vendor: Vendor) -> None:
    conn.execute(
        "INSERT INTO vendors (name, status, categories, notes) VALUES (?, ?, ?, ?)",
        (vendor.name, vendor.status.value, json.dumps(vendor.categories), vendor.notes),
    )


def insert_policy(conn: sqlite3.Connection, policy: Policy) -> None:
    conn.execute(
        "INSERT INTO policies (name, description, rules) VALUES (?, ?, ?)",
        (policy.name, policy.description, json.dumps(policy.rules)),
    )


def insert_purchase_request(conn: sqlite3.Connection, req: PurchaseRequest) -> None:
    conn.execute(
        """INSERT INTO purchase_requests
           (id, requester, department, item, vendor, amount, justification, urgency, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            req.id,
            req.requester,
            req.department,
            req.item,
            req.vendor,
            req.amount,
            req.justification,
            req.urgency.value,
            req.status.value,
            _fmt_dt(req.created_at),
            _fmt_dt(req.updated_at),
        ),
    )


def get_all_departments(conn: sqlite3.Connection) -> list[Department]:
    rows = conn.execute("SELECT * FROM departments").fetchall()
    return [Department(name=r["name"], headcount=r["headcount"], quarterly_budget=r["quarterly_budget"]) for r in rows]


def get_all_vendors(conn: sqlite3.Connection) -> list[Vendor]:
    rows = conn.execute("SELECT * FROM vendors").fetchall()
    return [
        Vendor(
            name=r["name"],
            status=VendorStatus(r["status"]),
            categories=json.loads(r["categories"]),
            notes=r["notes"],
        )
        for r in rows
    ]


def get_all_policies(conn: sqlite3.Connection) -> list[Policy]:
    rows = conn.execute("SELECT * FROM policies").fetchall()
    return [Policy(name=r["name"], description=r["description"], rules=json.loads(r["rules"])) for r in rows]


def _row_to_request(r: sqlite3.Row) -> PurchaseRequest:
    return PurchaseRequest(
        id=r["id"],
        requester=r["requester"],
        department=r["department"],
        item=r["item"],
        vendor=r["vendor"],
        amount=r["amount"],
        justification=r["justification"],
        urgency=Urgency(r["urgency"]),
        status=RequestStatus(r["status"]),
        created_at=_parse_dt(r["created_at"]),
        updated_at=_parse_dt(r["updated_at"]),
    )


def get_all_purchase_requests(conn: sqlite3.Connection) -> list[PurchaseRequest]:
    rows = conn.execute("SELECT * FROM purchase_requests ORDER BY id").fetchall()
    return [_row_to_request(r) for r in rows]


def get_purchase_request(conn: sqlite3.Connection, request_id: str) -> PurchaseRequest | None:
    row = conn.execute("SELECT * FROM purchase_requests WHERE id = ?", (request_id,)).fetchone()
    if row is None:
        return None
    return _row_to_request(row)


def next_request_id(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT id FROM purchase_requests ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return "PR-001"
    num = int(row["id"].split("-")[1]) + 1
    return f"PR-{num:03d}"


def update_request_status(conn: sqlite3.Connection, request_id: str, status: RequestStatus) -> bool:
    cursor = conn.execute(
        "UPDATE purchase_requests SET status = ?, updated_at = ? WHERE id = ?",
        (status.value, _fmt_dt(datetime.now(UTC).replace(tzinfo=None)), request_id),
    )
    return cursor.rowcount > 0


def insert_assessment(conn: sqlite3.Connection, record: AssessmentRecord) -> None:
    """Store an evaluator assessment. The review field on `record` is ignored —
    reviews are added separately via `insert_review`."""
    conn.execute(
        """INSERT INTO assessments (request_id, session_id, assessment_json, span_id, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (
            record.request_id,
            record.session_id,
            record.assessment.model_dump_json(),
            record.span_id,
            _fmt_dt(record.created_at),
        ),
    )


def insert_review(
    conn: sqlite3.Connection,
    session_id: str,
    review: ReviewDecision,
    reviewed_at: datetime | None = None,
) -> None:
    """Attach a human review to an existing assessment session."""
    ts = reviewed_at or datetime.now(UTC).replace(tzinfo=None)
    conn.execute(
        """INSERT INTO reviews (session_id, review_json, created_at)
           VALUES (?, ?, ?)""",
        (session_id, review.model_dump_json(), _fmt_dt(ts)),
    )


def _row_to_assessment_record(row: sqlite3.Row) -> AssessmentRecord:
    review = ReviewDecision.model_validate_json(row["review_json"]) if row["review_json"] else None
    reviewed_at = _parse_dt(row["reviewed_at"]) if row["reviewed_at"] else None
    span_id = row["span_id"] if "span_id" in row.keys() else None
    return AssessmentRecord(
        request_id=row["request_id"],
        session_id=row["session_id"],
        assessment=EvaluatorAssessment.model_validate_json(row["assessment_json"]),
        review=review,
        span_id=span_id,
        created_at=_parse_dt(row["created_at"]),
        reviewed_at=reviewed_at,
    )


_SELECT_ASSESSMENTS_WITH_REVIEWS = """
    SELECT
        a.request_id,
        a.session_id,
        a.assessment_json,
        a.span_id,
        a.created_at,
        r.review_json AS review_json,
        r.created_at AS reviewed_at
    FROM assessments a
    LEFT JOIN reviews r ON r.session_id = a.session_id
"""


def get_assessments_for_request(
    conn: sqlite3.Connection, request_id: str
) -> list[AssessmentRecord]:
    """Return all assessments for a request, newest first, with reviews joined when present."""
    rows = conn.execute(
        _SELECT_ASSESSMENTS_WITH_REVIEWS + " WHERE a.request_id = ? ORDER BY a.created_at DESC",
        (request_id,),
    ).fetchall()
    return [_row_to_assessment_record(r) for r in rows]


def get_latest_assessment(
    conn: sqlite3.Connection, request_id: str
) -> AssessmentRecord | None:
    row = conn.execute(
        _SELECT_ASSESSMENTS_WITH_REVIEWS
        + " WHERE a.request_id = ? ORDER BY a.created_at DESC LIMIT 1",
        (request_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_assessment_record(row)


def get_unreviewed_assessments(conn: sqlite3.Connection) -> list[AssessmentRecord]:
    """Return all assessments that don't yet have a review attached, oldest first."""
    rows = conn.execute(
        _SELECT_ASSESSMENTS_WITH_REVIEWS
        + " WHERE r.session_id IS NULL ORDER BY a.created_at ASC"
    ).fetchall()
    return [_row_to_assessment_record(r) for r in rows]


def get_all_assessments(conn: sqlite3.Connection) -> list[AssessmentRecord]:
    """Return every assessment in the store, newest first."""
    rows = conn.execute(
        _SELECT_ASSESSMENTS_WITH_REVIEWS + " ORDER BY a.created_at DESC"
    ).fetchall()
    return [_row_to_assessment_record(r) for r in rows]


def get_assessment_by_session(
    conn: sqlite3.Connection, session_id: str
) -> AssessmentRecord | None:
    row = conn.execute(
        _SELECT_ASSESSMENTS_WITH_REVIEWS + " WHERE a.session_id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_assessment_record(row)
