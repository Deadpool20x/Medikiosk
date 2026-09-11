#!/usr/bin/env python3
"""
MediKiosk — Demo Database Reset (F-07)

Creates a fresh, deterministic demo database for SIH presentation.

Dataset (4 sessions, no random clutter):
  demo-ky-001  Kayachikitsa completed case  — doctor-confirmed, queued
  demo-pk-001  Panchakarma completed case   — awaiting doctor review, queued
  demo-safe-01 Safety-flagged case          — D04 emergency dashboard
  demo-wip-001 In-progress interview        — mid-way through P04

Usage (from project root):
    python scripts/make_demo.py
"""
import sys
import os
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

DB_PATH = os.getenv("DATABASE_PATH") or os.path.join(PROJECT_ROOT, "backend", "data", "medikiosk.db")

from backend.db import init_db, save_session
from backend.models.schema import (
    Session, Patient, HistoryOfPresentIllness,
    DoctorReview, AnswerRecord, DocumentField,
)


def _now(delta_minutes: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=delta_minutes)


def _ar(field: str, answer: str, provider: str = "groq") -> AnswerRecord:
    return AnswerRecord(
        question=field,
        answer=answer,
        provider=provider,
        confidence=0.92,
        needs_review=False,
    )


def _build_kayachikitsa() -> Session:
    """demo-ky-001: Completed Kayachikitsa case, awaiting doctor review, token KY-001."""
    return Session(
        session_id="demo-ky-001",
        patient=Patient(name="Arjun Sharma", age=34, gender="Male"),
        language="en",
        visit_type="new",
        consent_given=True,
        patient_code="MK-KY0042",
        interview_step="complete",
        interview_complete=True,
        chief_complaint="Persistent stomach pain and digestive issues for the past week",
        history_of_present_illness=HistoryOfPresentIllness(
            onset="One week ago after a heavy meal",
            duration="Constant, worsening after meals",
            severity="Moderate — 5 out of 10",
            character="Dull, cramping pain in the lower abdomen",
            associated_symptoms=["nausea", "bloating", "mild fatigue"],
        ),
        doctor_review=DoctorReview(edited=False, confirmed=False),
        documents=[
            DocumentField(
                type="prescription",
                extracted_value="Metformin",
                strength="500 mg",
                dose="One tablet",
                frequency="Twice daily",
                confidence=0.95,
                source="ocr",
                provider="groq",
                needs_review=False,
                manually_corrected=False,
                original_extraction={
                    "medicine": "Metformin",
                    "strength": "500 mg",
                    "dose": "One tablet",
                    "frequency": "Twice daily",
                    "confidence": 0.95,
                    "provider": "groq",
                },
                raw_result={
                    "medicine": "Metformin",
                    "strength": "500 mg",
                    "dose": "One tablet",
                    "frequency": "Twice daily",
                    "confidence": 0.95,
                },
            )
        ],

        answer_records=[
            _ar("chief_complaint", "I have been having stomach pain for the past week"),
            _ar("onset", "Started about a week ago after a heavy meal"),
            _ar("duration", "Constant, worse after eating"),
            _ar("severity", "Around 5 out of 10"),
            _ar("character", "Dull cramping pain in my lower belly"),
            _ar("associated_symptoms", "Also nausea, bloating, and tired"),
        ],
        safety_flagged=False,
        document_intake_done=True,
        department="Kayachikitsa",
        queue_token="KY-001",
    )


def _build_panchakarma() -> Session:
    """demo-pk-001: Completed Panchakarma case, queued, awaiting doctor review."""
    return Session(
        session_id="demo-pk-001",
        patient=Patient(name="Priya Nair", age=52, gender="Female"),
        language="en",
        visit_type="new",
        consent_given=True,
        patient_code="MK-PK0015",
        interview_step="complete",
        interview_complete=True,
        chief_complaint="Chronic joint pain and stiffness in the knees and lower back",
        history_of_present_illness=HistoryOfPresentIllness(
            onset="About three months ago",
            duration="Persistent, worse in the morning",
            severity="Severe in the morning — 7 out of 10",
            character="Stiffness and aching, occasionally sharp when moving",
            associated_symptoms=["morning stiffness", "reduced mobility", "mild swelling"],
        ),
        doctor_review=DoctorReview(edited=False, confirmed=False),
        answer_records=[
            _ar("chief_complaint", "Chronic knee and lower back pain for about 3 months"),
            _ar("onset", "About 3 months ago, gradually worsened"),
            _ar("duration", "Persistent, worse in the morning"),
            _ar("severity", "7 in morning, 4 in the afternoon"),
            _ar("character", "Stiffness and aching, sometimes sharp when moving"),
            _ar("associated_symptoms", "Morning stiffness, hard to move, some swelling"),
        ],
        safety_flagged=False,
        document_intake_done=True,
        department="Panchakarma",
        queue_token="PK-001",
    )


def _build_safety_case() -> Session:
    """demo-safe-01: Safety-flagged — chest pain. Appears in D04 only."""
    return Session(
        session_id="demo-safe-01",
        patient=Patient(name="Ramesh Kumar", age=61, gender="Male"),
        language="en",
        visit_type="new",
        consent_given=True,
        patient_code="MK-SF0007",
        interview_step="onset",
        interview_complete=False,
        chief_complaint=None,
        history_of_present_illness=HistoryOfPresentIllness(),
        doctor_review=DoctorReview(),
        answer_records=[
            AnswerRecord(
                question="chief_complaint",
                answer="I have chest pain and difficulty breathing since this morning",
                provider=None,
                confidence=None,
                needs_review=True,
            ),
        ],
        raw_answers=[
            {
                "field": "chief_complaint",
                "answer": "I have chest pain and difficulty breathing since this morning",
                "timestamp": _now(5).isoformat(),
                "red_flag": True,
            }
        ],
        safety_flagged=True,
        safety_flag_time=_now(5),
        safety_detail=["chest pain", "difficulty breathing"],
        document_intake_done=False,
        department=None,
        queue_token=None,
    )


def _build_in_progress() -> Session:
    """demo-wip-001: Patient mid-interview at severity step."""
    return Session(
        session_id="demo-wip-001",
        patient=Patient(name="Sunita Patel", age=28, gender="Female"),
        language="en",
        visit_type="new",
        consent_given=True,
        patient_code="MK-WI0099",
        interview_step="severity",
        interview_complete=False,
        chief_complaint="Recurring headaches and fatigue",
        history_of_present_illness=HistoryOfPresentIllness(
            onset="About two weeks ago",
            duration="On and off throughout the day",
        ),
        doctor_review=DoctorReview(),
        answer_records=[
            _ar("chief_complaint", "I get recurring headaches and feel very tired"),
            _ar("onset", "Started about 2 weeks ago"),
            _ar("duration", "Come and go throughout the day, worse in the afternoon"),
        ],
        safety_flagged=False,
        document_intake_done=False,
        department=None,
        queue_token=None,
    )


def reset_demo_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing DB: {DB_PATH}")
    init_db(DB_PATH)
    print("Schema initialised")
    os.environ["DATABASE_PATH"] = DB_PATH
    sessions = [
        _build_kayachikitsa(),
        _build_panchakarma(),
        _build_safety_case(),
        _build_in_progress(),
    ]
    for s in sessions:
        save_session(s, db_path=DB_PATH)
        print(f"  Seeded: {s.session_id} ({s.patient.name})")
    print("\nDemo database ready.")
    print("  KY queue: demo-ky-001  (Arjun Sharma, confirmed)")
    print("  PK queue: demo-pk-001  (Priya Nair, awaiting review)")
    print("  D04 flag: demo-safe-01 (Ramesh Kumar, chest pain)")
    print("  P04 WIP:  demo-wip-001 (Sunita Patel, mid-interview)")


if __name__ == "__main__":
    reset_demo_db()
