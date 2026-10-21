"""SQLite persistence and repeat-batch signal detection for PharmaGuard AI.

Signals are review prompts only. They do not establish causality or product defect.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "complaints.sqlite3"

CASE_FIELDS = (
    "customer_name",
    "product_name",
    "product_strength",
    "batch_number",
    "manufacturing_date",
    "expiry_date",
    "affected_quantity",
    "complaint",
    "severity",
    "severity_reason",
    "risk_level",
    "recommended_action",
    "department",
    "status",
)


def _path(db_path: str | os.PathLike | None = None) -> Path:
    return Path(db_path or os.environ.get("PHARMAGUARD_DB_PATH", DEFAULT_DB_PATH)).expanduser()


def _connect(db_path: str | os.PathLike | None = None) -> sqlite3.Connection:
    path = _path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def init_case_store(db_path: str | os.PathLike | None = None) -> None:
    """Create the case register and append-only event log if they do not exist."""
    with _connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS complaint_cases (
                complaint_id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL DEFAULT '',
                product_name TEXT NOT NULL,
                product_strength TEXT NOT NULL DEFAULT '',
                batch_number TEXT NOT NULL DEFAULT '',
                manufacturing_date TEXT NOT NULL DEFAULT '',
                expiry_date TEXT NOT NULL DEFAULT '',
                affected_quantity TEXT NOT NULL DEFAULT '',
                complaint TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'Minor',
                severity_reason TEXT NOT NULL DEFAULT '',
                risk_level TEXT NOT NULL DEFAULT 'Low',
                recommended_action TEXT NOT NULL DEFAULT '',
                department TEXT NOT NULL DEFAULT 'QA Investigation',
                status TEXT NOT NULL DEFAULT 'Under Investigation',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cases_created
                ON complaint_cases(created_at);
            CREATE INDEX IF NOT EXISTS idx_cases_product_batch
                ON complaint_cases(product_name, batch_number);

            CREATE TABLE IF NOT EXISTS complaint_case_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                changed_fields TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (complaint_id) REFERENCES complaint_cases(complaint_id)
            );
            CREATE INDEX IF NOT EXISTS idx_case_events_case
                ON complaint_case_events(complaint_id, created_at);
            """
        )


def save_complaint(
    complaint_data: dict[str, Any],
    db_path: str | os.PathLike | None = None,
) -> dict[str, Any]:
    """Insert a new case or update an existing case without changing its ID.

    A new audit event is appended only when the case is created or fields change.
    """
    init_case_store(db_path)
    case_id = str(complaint_data.get("complaint_id") or "").strip()
    product = str(complaint_data.get("product_name") or "").strip()
    complaint = str(complaint_data.get("complaint") or "").strip()
    if not case_id:
        raise ValueError("A complaint ID is required before saving a case.")
    if not product:
        raise ValueError("A product name is required before saving a case.")
    if len(complaint) < 15:
        raise ValueError("A meaningful complaint description is required before saving a case.")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    values = {
        field: str(complaint_data.get(field) or "").strip()
        for field in CASE_FIELDS
    }
    values["product_name"] = product
    values["complaint"] = complaint

    with _connect(db_path) as connection:
        previous = connection.execute(
            "SELECT * FROM complaint_cases WHERE complaint_id = ?",
            (case_id,),
        ).fetchone()

        if previous is None:
            connection.execute(
                """
                INSERT INTO complaint_cases (
                    complaint_id, customer_name, product_name, product_strength,
                    batch_number, manufacturing_date, expiry_date, affected_quantity,
                    complaint, severity, severity_reason, risk_level, recommended_action,
                    department, status, created_at, updated_at
                ) VALUES (
                    :complaint_id, :customer_name, :product_name, :product_strength,
                    :batch_number, :manufacturing_date, :expiry_date, :affected_quantity,
                    :complaint, :severity, :severity_reason, :risk_level, :recommended_action,
                    :department, :status, :created_at, :updated_at
                )
                """,
                {
                    "complaint_id": case_id,
                    **values,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            event_type = "created"
            changed_fields = list(values.keys())
        else:
            changed_fields = [
                field for field in CASE_FIELDS
                if str(previous[field] or "") != values[field]
            ]
            if changed_fields:
                assignments = ", ".join(f"{field} = :{field}" for field in CASE_FIELDS)
                connection.execute(
                    f"""UPDATE complaint_cases
                        SET {assignments}, updated_at = :updated_at
                        WHERE complaint_id = :complaint_id""",
                    {**values, "updated_at": now, "complaint_id": case_id},
                )
                event_type = "updated"
            else:
                event_type = ""

        if event_type:
            connection.execute(
                """INSERT INTO complaint_case_events
                   (complaint_id, event_type, changed_fields, created_at)
                   VALUES (?, ?, ?, ?)""",
                (case_id, event_type, json.dumps(changed_fields), now),
            )

        saved = connection.execute(
            "SELECT * FROM complaint_cases WHERE complaint_id = ?",
            (case_id,),
        ).fetchone()
        return dict(saved)


def list_complaints(
    limit: int = 50,
    severity: str | None = None,
    status: str | None = None,
    batch_number: str | None = None,
    db_path: str | os.PathLike | None = None,
) -> list[dict[str, Any]]:
    """Return recent persisted cases with optional exact filters."""
    init_case_store(db_path)
    limit = max(1, min(int(limit), 200))
    clauses = []
    params: list[Any] = []
    if severity and severity.strip():
        clauses.append("LOWER(severity) = LOWER(?)")
        params.append(severity.strip())
    if status and status.strip():
        clauses.append("LOWER(status) = LOWER(?)")
        params.append(status.strip())
    if batch_number and batch_number.strip():
        clauses.append("LOWER(batch_number) = LOWER(?)")
        params.append(batch_number.strip())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    with _connect(db_path) as connection:
        rows = connection.execute(
            f"""SELECT * FROM complaint_cases {where}
                ORDER BY updated_at DESC, created_at DESC LIMIT ?""",
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def get_complaint(
    complaint_id: str,
    db_path: str | os.PathLike | None = None,
) -> dict[str, Any] | None:
    init_case_store(db_path)
    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM complaint_cases WHERE complaint_id = ?",
            (complaint_id.strip(),),
        ).fetchone()
        return dict(row) if row else None


def get_case_events(
    complaint_id: str,
    db_path: str | os.PathLike | None = None,
) -> list[dict[str, Any]]:
    """Return the append-only create/update history for one case."""
    init_case_store(db_path)
    with _connect(db_path) as connection:
        rows = connection.execute(
            """SELECT event_id, complaint_id, event_type, changed_fields, created_at
               FROM complaint_case_events
               WHERE complaint_id = ?
               ORDER BY event_id ASC""",
            (complaint_id.strip(),),
        ).fetchall()
        events = [dict(row) for row in rows]
        for event in events:
            event["changed_fields"] = json.loads(event["changed_fields"])
        return events


def get_batch_signals(
    days: int = 30,
    min_reports: int = 2,
    db_path: str | os.PathLike | None = None,
) -> list[dict[str, Any]]:
    """Find product/batch pairs with repeated reports in a recent time window.

    Only records with a non-empty batch number qualify. The result is a triage
    signal for a human reviewer, never an assertion of a confirmed defect.
    """
    init_case_store(db_path)
    days = max(1, min(int(days), 365))
    min_reports = max(2, min(int(min_reports), 100))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")

    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                LOWER(TRIM(product_name)) AS product_key,
                LOWER(TRIM(batch_number)) AS batch_key,
                MIN(product_name) AS product_name,
                MIN(batch_number) AS batch_number,
                COUNT(*) AS report_count,
                SUM(CASE WHEN LOWER(severity) = 'critical' THEN 1 ELSE 0 END) AS critical_count,
                MIN(created_at) AS first_report_at,
                MAX(updated_at) AS latest_update_at
            FROM complaint_cases
            WHERE TRIM(batch_number) <> ''
              AND created_at >= ?
            GROUP BY LOWER(TRIM(product_name)), LOWER(TRIM(batch_number))
            HAVING COUNT(*) >= ?
            ORDER BY critical_count DESC, report_count DESC, latest_update_at DESC
            """,
            (cutoff, min_reports),
        ).fetchall()

    return [
        {
            **dict(row),
            "signal_type": "Repeated product/batch reports",
            "review_required": True,
            "review_note": (
                "Potential related reports only. Verify source complaints, batch identity, "
                "and clinical/quality facts; this signal does not establish causality."
            ),
        }
        for row in rows
    ]
