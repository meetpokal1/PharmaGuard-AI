import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from utils.case_store import (  # noqa: E402
    get_batch_signals,
    get_case_events,
    get_case_summary,
    list_complaints,
    save_complaint,
)


def case(case_id, product="PainRelief", batch="BATCH-7", severity="Major", text="Bottle seal was broken and tablets were scattered."):
    return {
        "complaint_id": case_id,
        "customer_name": "Demo Pharmacy",
        "product_name": product,
        "product_strength": "500 mg",
        "batch_number": batch,
        "manufacturing_date": "2026-01-01",
        "expiry_date": "2027-01-01",
        "affected_quantity": "3",
        "complaint": text,
        "severity": severity,
        "severity_reason": "Potential product quality impact.",
        "risk_level": "Medium",
        "recommended_action": "Route to QA for review.",
        "department": "QA Investigation",
        "status": "Under Investigation",
    }


def test_case_survives_read_and_update_keeps_same_id(tmp_path):
    database = tmp_path / "cases.sqlite3"
    saved = save_complaint(case("PG-001"), database)
    assert saved["complaint_id"] == "PG-001"

    updated = case("PG-001", text="Bottle seal was broken and tablets were scattered; photo attached.")
    updated["severity"] = "Critical"
    save_complaint(updated, database)

    rows = list_complaints(db_path=database)
    assert len(rows) == 1
    assert rows[0]["severity"] == "Critical"
    assert rows[0]["complaint_id"] == "PG-001"
    events = get_case_events("PG-001", database)
    assert [event["event_type"] for event in events] == ["created", "updated"]
    assert "severity" in events[1]["changed_fields"]


def test_repeat_batch_signal_groups_case_insensitively_and_excludes_blank_batches(tmp_path):
    database = tmp_path / "signals.sqlite3"
    save_complaint(case("PG-001", product="PainRelief", batch="BATCH-7"), database)
    save_complaint(case("PG-002", product=" painrelief ", batch="batch-7", severity="Critical"), database)
    save_complaint(case("PG-003", product="PainRelief", batch=""), database)

    signals = get_batch_signals(days=30, min_reports=2, db_path=database)
    assert len(signals) == 1
    assert signals[0]["report_count"] == 2
    assert signals[0]["critical_count"] == 1
    assert signals[0]["review_required"] is True
    assert "does not establish causality" in signals[0]["review_note"]


def test_dashboard_summary_uses_real_database_counts(tmp_path):
    database = tmp_path / "summary.sqlite3"
    save_complaint(case("PG-001", severity="Critical", text="Patient hospitalization reported after suspected contamination event."), database)
    resolved = case("PG-002")
    resolved["status"] = "Resolved"
    save_complaint(resolved, database)

    assert get_case_summary(database) == {
        "total": 2,
        "critical": 1,
        "pending": 1,
        "resolved": 1,
    }


def test_invalid_case_without_required_description_is_not_saved(tmp_path):
    database = tmp_path / "bad.sqlite3"
    invalid = case("PG-001", text="bad")
    with pytest.raises(ValueError, match="meaningful complaint"):
        save_complaint(invalid, database)
    assert list_complaints(db_path=database) == []
