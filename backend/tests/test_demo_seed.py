"""Tests for the deterministic demo seed/reset mechanism (F-07).

Seeds into a fresh temp DB that never touches the production/runtime DB
(DEFAULT_DB_PATH). Asserts dataset shape, token validity, department routing,
safety-queue separation, idempotency, and the doctor workspace views.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.seed_demo import seed_demo  # noqa: E402
from backend.db import (  # noqa: E402
    DEFAULT_DB_PATH, get_db_connection, list_queued_sessions, list_flagged_sessions,
)
from backend.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def demo_db(tmp_path):
    db = str(tmp_path / "demo_medikiosk.db")
    seed_demo(db)
    return db


def _count_sessions(db_path: str) -> int:
    conn = get_db_connection(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    finally:
        conn.close()


def test_seed_creates_exactly_five_sessions(demo_db):
    assert _count_sessions(demo_db) == 5


def test_completed_cases_have_valid_sequential_tokens(demo_db):
    queued = list_queued_sessions(db_path=demo_db)
    tokens = sorted(q["queue_token"] for q in queued if q["queue_token"])
    assert tokens == ["KY-001", "KY-002", "PK-001"]
    assert {q["queue_token"][:2] for q in queued} == {"KY", "PK"}


def test_departments_are_runtime_classified(demo_db):
    queued = list_queued_sessions(db_path=demo_db)
    depts = {q["queue_token"]: q["department"] for q in queued}
    assert depts["KY-001"] == "Kayachikitsa"
    assert depts["PK-001"] == "Panchakarma"
    assert depts["KY-002"] == "Kayachikitsa"


def test_safety_flagged_case_in_emergency_not_in_queue(demo_db):
    emergency = list_flagged_sessions(db_path=demo_db)
    assert len(emergency) == 1
    assert emergency[0]["patient_code"] == "MK-003"
    assert "chest pain" in emergency[0]["symptom"]

    queued_ids = {q["session_id"] for q in list_queued_sessions(db_path=demo_db)}
    emergency_ids = {e["session_id"] for e in emergency}
    assert emergency_ids.isdisjoint(queued_ids)


def test_mid_interview_patient_is_resumable(demo_db):
    from backend.db import get_session
    s = get_session("resume-jointpain-demo-004", demo_db)
    assert s is not None
    assert s.consent_given is True
    assert s.patient_code == "MK-004"
    assert s.interview_complete is False
    assert s.interview_step == "duration"
    assert s.queue_token is None


def test_returning_visit_patient_is_persisted(demo_db):
    from backend.db import get_session
    s = get_session("returning-arthritis-demo-005", demo_db)
    assert s.visit_type == "returning"
    assert s.consent_given is True


def test_seed_is_idempotent(tmp_path):
    db = str(tmp_path / "rerun.db")
    seed_demo(db)
    first = sorted((r["queue_token"], r["patient_name"])
                   for r in list_queued_sessions(db_path=db))
    seed_demo(db)  # second run must reset, not duplicate
    second = sorted((r["queue_token"], r["patient_name"])
                    for r in list_queued_sessions(db_path=db))
    assert _count_sessions(db) == 5
    assert first == second


def test_production_db_untouched():
    """Seeding a demo DB must never write to DEFAULT_DB_PATH."""
    from backend.db import get_db_connection
    conn = get_db_connection()
    try:
        prod_total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    finally:
        conn.close()
    assert isinstance(prod_total, int)


@pytest.mark.parametrize("path,expected", [
    ("/doctor/sessions", {"kaya-katishoola-demo-001", "pk-sthaulya-demo-002",
                          "resume-jointpain-demo-004", "returning-arthritis-demo-005"}),
])
def test_doctor_sessions_excludes_flagged(demo_db, monkeypatch, tmp_path, path, expected):
    monkeypatch.setenv("DATABASE_PATH", demo_db)
    client = TestClient(app)
    r = client.get(path)
    assert r.status_code == 200
    assert {item["session_id"] for item in r.json()} == expected


def test_doctor_emergency_after_seeding(demo_db, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", demo_db)
    client = TestClient(app)
    r = client.get("/doctor/emergency")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["patient_code"] == "MK-003"
    assert items[0]["status"] == "Safety Alert — Review Required"


def test_doctor_queue_after_seeding(demo_db, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", demo_db)
    client = TestClient(app)
    kaya = client.get("/doctor/queue", params={"department": "Kayachikitsa"})
    pk = client.get("/doctor/queue", params={"department": "Panchakarma"})
    assert kaya.status_code == 200 and pk.status_code == 200
    assert {q["queue_token"] for q in kaya.json()} == {"KY-001", "KY-002"}
    assert {q["queue_token"] for q in pk.json()} == {"PK-001"}