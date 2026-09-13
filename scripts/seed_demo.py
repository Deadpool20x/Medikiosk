"""Deterministic, repeatable demo dataset for the MediKiosk SIH demo.

Creates a deliberately separate demo database (never the production/runtime DB)
containing exactly five realistic, de-identified sessions that hit every doctor
workspace state:

- one completed Kayachikitsa case with a valid queue token (KY-001)
- one completed Panchakarma case with a valid queue token  (PK-001)
- one safety-flagged case visible in D04 and excluded from D01 queues
- one mid-interview patient that can be resumed
- one returning-visit patient (visit_type="returning")

Rows are written through the app's own models + db.save_session, so the demo
data is byte-for-byte compatible with the runtime schema. No LLM, no network,
no provider keys. Running twice yields the same logical dataset.

Usage:
    python scripts/seed_demo.py [DB_PATH]
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import init_db, save_session, next_queue_token, DEFAULT_DB_PATH  # noqa: E402
from backend.models.schema import (  # noqa: E402
    Session, Patient, HistoryOfPresentIllness, DoctorReview, AnswerRecord,
)
from backend.rules.department_rules import classify_department  # noqa: E402

DEMO_DB_PATH = os.path.join(os.path.dirname(DEFAULT_DB_PATH), "demo_medikiosk.db")

_NOW = datetime.now(timezone.utc)


def _iso(days_ago: int) -> str:
    return (_NOW - timedelta(days=days_ago)).isoformat()


def _answers(session: Session) -> List[AnswerRecord]:
    """Real-shaped structured records for the six interview fields."""
    hpi = session.history_of_present_illness
    values: List[tuple] = [
        ("chief_complaint", session.chief_complaint or "", 0.92),
        ("onset", hpi.onset or "", 0.85),
        ("duration", hpi.duration or "", 0.84),
        ("severity", hpi.severity or "", 0.83),
        ("character", hpi.character or "", 0.82),
        ("associated_symptoms", ", ".join(hpi.associated_symptoms), 0.81),
    ]
    return [
        AnswerRecord(question=q, answer=a, provider="groq", confidence=c, needs_review=False)
        for q, a, c in values
    ]


def _raw_answers(session: Session) -> List[Dict[str, Any]]:
    hpi = session.history_of_present_illness
    return [
        {"field": "chief_complaint", "answer": session.chief_complaint or "", "timestamp": _iso(3), "red_flag": False},
        {"field": "onset", "answer": hpi.onset or "", "timestamp": _iso(2), "red_flag": False},
        {"field": "duration", "answer": hpi.duration or "", "timestamp": _iso(2), "red_flag": False},
        {"field": "severity", "answer": hpi.severity or "", "timestamp": _iso(2), "red_flag": False},
        {"field": "character", "answer": hpi.character or "", "timestamp": _iso(1), "red_flag": False},
        {"field": "associated_symptoms", "answer": "; ".join(hpi.associated_symptoms), "timestamp": _iso(1), "red_flag": False},
    ]


def _completed_department_case(session_id: str, name: str, age: int, gender: str,
                               complaint: str, hpi: Dict[str, Any],
                               physician_tasks: bool = False) -> Session:
    session = Session(
        session_id=session_id,
        patient=Patient(name=name, age=age, gender=gender),
        consent_given=True,
        patient_code=f"MK-{session_id.split('-')[-1].upper()}",
        interview_step="complete",
        interview_complete=True,
        document_intake_done=True,
        chief_complaint=complaint,
        history_of_present_illness=HistoryOfPresentIllness(**hpi),
        answer_records=[],
        raw_answers=[],
    )
    session.answer_records = _answers(session)
    session.raw_answers = _raw_answers(session)
    # Department assignment goes through the real classifier so the seeded row
    # is exactly what the runtime rules engine would produce.
    session.department = classify_department(session)
    return session


def seed_demo(db_path: str) -> List[Session]:
    """Reset sessions in ``db_path`` and insert the deterministic demo set.

    Returns the inserted Session objects (with queue tokens assigned).
    """
    init_db(db_path)

    from backend.db import get_db_connection
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM sessions")
    finally:
        conn.close()

    cases: List[Session] = []

    # 1. Completed Kayachikitsa case (Katishoola -> Kayachikitsa).
    kaya = _completed_department_case(
        "kaya-katishoola-demo-001",
        "Ramesh Nair", 54, "Male",
        "Katishoola, lower back pain for 3 months",
        {"onset": "3 months ago after lifting heavy weight",
         "duration": "3 months, constant dull ache",
         "severity": "5/10, worse in the morning",
         "character": "dull aching, radiating to right thigh",
         "associated_symptoms": ["stiffness in the morning", "mild hip pain"]},
    )
    kaya.queue_token = next_queue_token("KY", db_path)
    cases.append(kaya)
    save_session(kaya, db_path)

    # 2. Completed Panchakarma case (Sthaulya -> Panchakarma).
    pk = _completed_department_case(
        "pk-sthaulya-demo-002",
        "Sunita Iyer", 47, "Female",
        "Sthaulya, weight gain with fatigue",
        {"onset": "2 years ago", "duration": "2 years, gradual",
         "severity": "3/10", "character": "heavy feeling, lethargy",
         "associated_symptoms": ["increased appetite", "joint pain"]},
    )
    pk.queue_token = next_queue_token("PK", db_path)
    cases.append(pk)
    save_session(pk, db_path)

    # 3. Safety-flagged case: red-flagged raw answer, no token, D04-only.
    flagged_raw_answer = {
        "field": "chief_complaint",
        "answer": "severe chest pain and difficulty breathing",
        "timestamp": _iso(0),
        "red_flag": True,
    }
    flagged = Session(
        session_id="safety-chestpain-demo-003",
        patient=Patient(name="Akshay Patil", age=62, gender="Male"),
        consent_given=True,
        patient_code="MK-003",
        interview_step="chief_complaint",
        interview_complete=False,
        document_intake_done=False,
        chief_complaint=None,
        answer_records=[],
        raw_answers=[flagged_raw_answer],
        safety_flagged=True,
        safety_flag_time=datetime.fromisoformat(_iso(0)),
        safety_detail=["chest pain", "difficulty breathing"],
    )
    cases.append(flagged)

    # 4. Mid-interview, resumable patient (chief complaint + onset done).
    resume = Session(
        session_id="resume-jointpain-demo-004",
        patient=Patient(name="Meena Kulkarni", age=35, gender="Female"),
        consent_given=True,
        patient_code="MK-004",
        interview_step="duration",
        interview_complete=False,
        document_intake_done=False,
        chief_complaint="Joint pain in both knees",
        history_of_present_illness=HistoryOfPresentIllness(
            onset="after a long trek last month",
        ),
        answer_records=[
            AnswerRecord(question="chief_complaint", answer="Joint pain in both knees",
                         provider="groq", confidence=0.9, needs_review=False),
            AnswerRecord(question="onset", answer="after a long trek last month",
                         provider="groq", confidence=0.86, needs_review=False),
        ],
        raw_answers=[
            {"field": "chief_complaint", "answer": "Joint pain in both knees",
             "timestamp": _iso(1), "red_flag": False},
            {"field": "onset", "answer": "after a long trek last month",
             "timestamp": _iso(1), "red_flag": False},
        ],
    )
    cases.append(resume)

    # 5. Returning-visit patient (visit_type persisted by the workflow).
    returning = _completed_department_case(
        "returning-arthritis-demo-005",
        "Gopal Krishnan", 60, "Male",
        "Known knee arthritis, routine follow-up",
        {"onset": "1 year ago", "duration": "1 year, intermittent",
         "severity": "4/10", "character": "stiffness and swelling",
         "associated_symptoms": ["morning stiffness ~20 minutes"]},
    )
    returning.visit_type = "returning"
    returning.queue_token = next_queue_token("KY", db_path)
    cases.append(returning)
    save_session(returning, db_path)

    for session in cases:
        save_session(session, db_path)
    return cases


def _print_summary(cases: List[Session]) -> None:
    print("Demo dataset seeded:")
    for s in cases:
        state = [
            "FLAGGED" if s.safety_flagged else "",
            f"token={s.queue_token}" if s.queue_token else "",
            s.department or "",
            s.visit_type if s.visit_type != "new" else "",
        ]
        print(f"  {s.session_id:32s} {s.patient.name:20s} {' '.join(x for x in state if x)}")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else DEMO_DB_PATH
    cases = seed_demo(db_path)
    _print_summary(cases)
    print(f"\nDB: {os.path.abspath(db_path)}")
    print(f"Production DB ({DEFAULT_DB_PATH}) was NOT modified.")