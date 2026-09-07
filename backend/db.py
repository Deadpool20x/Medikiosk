import sqlite3
import os
import json
from typing import Optional, List, Dict, Any
from backend.models.schema import Session, Patient, HistoryOfPresentIllness, DoctorReview, DocumentField

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "medikiosk.db")

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Optional[str] = None) -> None:
    """Idempotently initialize SQLite database tables."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    patient_json TEXT NOT NULL,
                    chief_complaint TEXT,
                    hpi_json TEXT NOT NULL,
                    documents_json TEXT NOT NULL,
                    doctor_review_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
    finally:
        conn.close()

def save_session(session: Session, db_path: Optional[str] = None) -> None:
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT INTO sessions (
                    session_id, patient_json, chief_complaint, hpi_json, documents_json, doctor_review_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    patient_json = excluded.patient_json,
                    chief_complaint = excluded.chief_complaint,
                    hpi_json = excluded.hpi_json,
                    documents_json = excluded.documents_json,
                    doctor_review_json = excluded.doctor_review_json,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                session.session_id,
                session.patient.model_dump_json(),
                session.chief_complaint,
                session.history_of_present_illness.model_dump_json(),
                json.dumps([doc.model_dump() for doc in session.documents]),
                session.doctor_review.model_dump_json()
            ))
    finally:
        conn.close()

def get_session(session_id: str, db_path: Optional[str] = None) -> Optional[Session]:
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        patient_data = json.loads(row["patient_json"])
        hpi_data = json.loads(row["hpi_json"])
        docs_data = json.loads(row["documents_json"])
        review_data = json.loads(row["doctor_review_json"])
        
        return Session(
            session_id=row["session_id"],
            patient=Patient(**patient_data),
            chief_complaint=row["chief_complaint"],
            history_of_present_illness=HistoryOfPresentIllness(**hpi_data),
            documents=[DocumentField(**d) for d in docs_data],
            doctor_review=DoctorReview(**review_data)
        )
    finally:
        conn.close()

def list_sessions(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT session_id, patient_json, doctor_review_json FROM sessions ORDER BY created_at DESC")
        rows = cursor.fetchall()
        result = []
        for r in rows:
            patient = json.loads(r["patient_json"])
            review = json.loads(r["doctor_review_json"])
            result.append({
                "session_id": r["session_id"],
                "patient_name": patient.get("name", "Unknown"),
                "ready_for_review": not review.get("confirmed", False)
            })
        return result
    finally:
        conn.close()
