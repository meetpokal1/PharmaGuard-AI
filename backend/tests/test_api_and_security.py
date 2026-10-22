import io
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from main import app, UPLOAD_DIR  # noqa: E402
from utils.case_store import init_case_store, list_complaints  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Test client with isolated uploads directory and database."""
    test_upload_dir = tmp_path / "uploads"
    test_upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("main.UPLOAD_DIR", str(test_upload_dir))

    # Initialize in-memory/temp database for case store
    test_db = tmp_path / "test_cases.sqlite3"
    monkeypatch.setattr("utils.case_store.DEFAULT_DB_PATH", str(test_db))
    monkeypatch.setattr("agent.tools.save_complaint.__defaults__", (str(test_db),))
    init_case_store(str(test_db))

    with TestClient(app) as test_client:
        yield test_client


def test_home_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "PharmaGuard AI"
    assert data["status"] == "online"


def test_upload_rejects_non_pdf_extension(client):
    file_bytes = b"Hello world text file"
    response = client.post(
        "/upload",
        files={"file": ("notes.txt", file_bytes, "text/plain")}
    )
    assert response.status_code == 400
    assert "Only PDF files are supported" in response.json()["error"]


def test_upload_rejects_fake_pdf_magic_bytes(client):
    file_bytes = b"NOT_A_REAL_PDF_HEADER_DATA"
    response = client.post(
        "/upload",
        files={"file": ("malicious.pdf", file_bytes, "application/pdf")}
    )
    assert response.status_code == 400
    assert "not a valid PDF document" in response.json()["error"]


def test_upload_rejects_oversized_file(client):
    # Create content larger than 10MB
    oversized_content = b"%PDF-1.4 " + (b"A" * (10 * 1024 * 1024 + 10))
    response = client.post(
        "/upload",
        files={"file": ("huge.pdf", oversized_content, "application/pdf")}
    )
    assert response.status_code == 413
    assert "exceeds maximum limit" in response.json()["error"]


def test_upload_valid_pdf_and_list_files(client):
    valid_pdf = b"%PDF-1.4 Minimal test PDF body"
    response = client.post(
        "/upload",
        files={"file": ("sample_report.pdf", valid_pdf, "application/pdf")}
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "sample_report.pdf"

    files_response = client.get("/files")
    assert files_response.status_code == 200
    assert "sample_report.pdf" in files_response.json()["files"]


def test_path_traversal_prevention(client):
    # Attempting to access files outside upload dir with path traversal
    response = client.get("/files/../../etc/passwd")
    assert response.status_code == 404

    response2 = client.get("/extract/../../secret.txt")
    assert response2.status_code == 404


def test_chat_conversational_greeting_without_groq(client):
    response = client.post(
        "/chat",
        json={"message": "Hello, how does PharmaGuard AI work?", "session_id": "test-session-1"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["reply"]) > 10


def test_chat_complaint_intake_creates_persisted_record(client):
    complaint_prompt = (
        "Batch BATCH-88: Amoxicillin 500 mg capsules reported broken packaging and contaminated blister foil at City Care Pharmacy."
    )
    response = client.post(
        "/chat",
        json={"message": complaint_prompt, "session_id": "test-session-2"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "complaint" in data

    # Verify severity classification and complaint registration
    assert data["complaint"]["severity"] in ["Critical", "Major", "Minor"]
    assert data["complaint"]["complaint_id"].startswith("CMP-")

    # Verify complaints list returns the newly registered complaint
    register_response = client.get("/complaints")
    assert register_response.status_code == 200
    cases = register_response.json()["cases"]
    assert any(c["complaint_id"] == data["complaint"]["complaint_id"] for c in cases)


def test_chat_reset_endpoint(client):
    reset_response = client.post(
        "/chat/reset",
        json={"session_id": "test-session-reset"}
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["session_id"] == "test-session-reset"
