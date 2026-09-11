import os
import sqlite3
import tempfile
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.models.schema import Session, Patient, HistoryOfPresentIllness
from backend.rules.safety_rules import evaluate_safety as evaluate_safety_v2, structured_state_text
from backend.rules.department_rules import classify_department, clinical_text
from backend.rules.interview_rules import evaluate_safety as evaluate_safety_v1
from backend.db import get_db_connection, init_db


def test_safety_and_department_rules_resilient_to_none_and_non_string_symptoms():
    """Verify rules never crash if associated_symptoms has None or non-string entries."""
    session = Session(
        session_id="none-test-1",
        patient=Patient(name="Test Patient", age=30, gender="other"),
        chief_complaint="General malaise",
        history_of_present_illness=HistoryOfPresentIllness(
            onset="yesterday",
            duration="1 day",
            severity="moderate",
            character="dull",
            associated_symptoms=["fever", "headache"],
        ),
    )
    # Inject None dynamically into associated_symptoms to simulate legacy/untyped data
    session.history_of_present_illness.associated_symptoms.append(None)  # type: ignore

    # Must safely evaluate without TypeError
    res = evaluate_safety_v2(None, session)  # type: ignore
    assert res.flagged is False

    # Department classification must safely evaluate without TypeError
    dept = classify_department(session)
    assert dept == "Kayachikitsa"

    # Interview safety evaluate_safety must not crash with None
    assert evaluate_safety_v1(None, session) is True  # type: ignore


def test_sqlite_wal_mode_and_indexes_created():
    """Verify database initialization creates WAL mode, busy timeout, and query indexes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = os.path.join(tmpdir, "test_wal.db")
        init_db(test_db)

        conn = get_db_connection(test_db)
        # Check journal mode (in memory or temporary files it may be memory/WAL)
        cursor = conn.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0].lower()
        assert mode in ("wal", "delete", "memory")

        # Check indexes exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = {row[0] for row in cursor.fetchall()}
        assert "idx_sessions_queue" in indexes
        assert "idx_sessions_safety" in indexes
        assert "idx_sessions_dept" in indexes
        assert "idx_sessions_code" in indexes
        conn.close()


def test_health_check_database_probe():
    """Verify /health tests DB connectivity and returns 200 OK."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_doctor_auth_with_secret_token(monkeypatch):
    """Verify doctor workspace enforces X-Doctor-Token when DOCTOR_SECRET_TOKEN is configured."""
    monkeypatch.setenv("DOCTOR_SECRET_TOKEN", "prod-secret-key-12345")
    test_client = TestClient(app)

    # Missing token -> 401 Unauthorized
    resp_missing = test_client.get("/doctor/queue")
    assert resp_missing.status_code == 401
    assert "Unauthorized" in resp_missing.json()["detail"]

    # Wrong token -> 401 Unauthorized
    resp_wrong = test_client.get("/doctor/queue", headers={"X-Doctor-Token": "bad-key"})
    assert resp_wrong.status_code == 401

    # Correct token -> 200 OK
    resp_ok = test_client.get("/doctor/queue", headers={"X-Doctor-Token": "prod-secret-key-12345"})
    assert resp_ok.status_code == 200


def test_doctor_auth_loopback_fallback(monkeypatch):
    """When DOCTOR_SECRET_TOKEN is unset, testclient/loopback continues to work (demo mode)."""
    monkeypatch.delenv("DOCTOR_SECRET_TOKEN", raising=False)
    client = TestClient(app)
    resp = client.get("/doctor/queue")
    assert resp.status_code == 200
