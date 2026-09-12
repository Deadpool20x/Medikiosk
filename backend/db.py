import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from backend.models.schema import Session, Patient, HistoryOfPresentIllness, DoctorReview, DocumentField, AnswerRecord

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "medikiosk.db")

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
    except Exception:
        pass
    try:
        _migrate_sessions_table(conn)
    except Exception:
        pass
    return conn

def init_db(db_path: Optional[str] = None) -> None:
    """Idempotently initialize SQLite database tables and performance indexes."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    patient_json TEXT NOT NULL,
                    language TEXT NOT NULL DEFAULT 'en',
                    visit_type TEXT NOT NULL DEFAULT 'new',
                    consent_given INTEGER NOT NULL DEFAULT 0,
                    patient_code TEXT,
                    interview_step TEXT NOT NULL DEFAULT 'chief_complaint',
                    interview_complete INTEGER NOT NULL DEFAULT 0,
                    chief_complaint TEXT,
                    hpi_json TEXT NOT NULL,
                    documents_json TEXT NOT NULL,
                    doctor_review_json TEXT NOT NULL,
                    answer_records_json TEXT NOT NULL DEFAULT '[]',
                    raw_answers_json TEXT NOT NULL DEFAULT '[]',
                    safety_flagged INTEGER NOT NULL DEFAULT 0,
                    safety_flag_time TEXT,
                    safety_detail_json TEXT NOT NULL DEFAULT '[]',
                    department TEXT,
                    queue_token TEXT,
                    presentation_domain TEXT,
                    collected_concepts_json TEXT NOT NULL DEFAULT '{}',
                    asked_questions_json TEXT NOT NULL DEFAULT '[]',
                    asked_concepts_json TEXT NOT NULL DEFAULT '[]',
                    current_pending_question TEXT,
                    adaptive_question_count INTEGER NOT NULL DEFAULT 0,
                    mentioned_documents_json TEXT NOT NULL DEFAULT '[]',
                    adaptive INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            _migrate_sessions_table(conn)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_queue ON sessions(queue_token, safety_flagged);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_safety ON sessions(safety_flagged);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_dept ON sessions(department);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_code ON sessions(patient_code);")
    finally:
        conn.close()

def _migrate_sessions_table(conn: sqlite3.Connection) -> None:
    """Idempotently add new columns to pre-existing sessions tables."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "sessions" not in tables:
        return
    columns = {
        "language": "TEXT NOT NULL DEFAULT 'en'",
        "visit_type": "TEXT NOT NULL DEFAULT 'new'",
        "consent_given": "INTEGER NOT NULL DEFAULT 0",
        "patient_code": "TEXT",
        "interview_step": "TEXT NOT NULL DEFAULT 'chief_complaint'",
        "interview_complete": "INTEGER NOT NULL DEFAULT 0",
        "document_intake_done": "INTEGER NOT NULL DEFAULT 0",
        "chief_complaint": "TEXT",
        "answer_records_json": "TEXT NOT NULL DEFAULT '[]'",
        "raw_answers_json": "TEXT NOT NULL DEFAULT '[]'",
        "safety_flagged": "INTEGER NOT NULL DEFAULT 0",
        "safety_flag_time": "TEXT",
        "safety_detail_json": "TEXT NOT NULL DEFAULT '[]'",
        "department": "TEXT",
        "queue_token": "TEXT",
        "presentation_domain": "TEXT",
        "collected_concepts_json": "TEXT NOT NULL DEFAULT '{}'",
        "asked_questions_json": "TEXT NOT NULL DEFAULT '[]'",
        "asked_concepts_json": "TEXT NOT NULL DEFAULT '[]'",
        "current_pending_question": "TEXT",
        "adaptive_question_count": "INTEGER NOT NULL DEFAULT 0",
        "mentioned_documents_json": "TEXT NOT NULL DEFAULT '[]'",
        "adaptive": "INTEGER NOT NULL DEFAULT 1",
    }
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}
    for col, ddl in columns.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {ddl}")

def save_session(session: Session, db_path: Optional[str] = None) -> None:
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT INTO sessions (
                    session_id, patient_json, language, visit_type, consent_given, patient_code,
                    interview_step, interview_complete, document_intake_done, chief_complaint, hpi_json, documents_json,
                    doctor_review_json, answer_records_json, raw_answers_json, safety_flagged,
                    safety_flag_time, safety_detail_json, department, queue_token,
                    presentation_domain, collected_concepts_json, asked_questions_json, asked_concepts_json, current_pending_question, adaptive_question_count, mentioned_documents_json, adaptive, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    patient_json = excluded.patient_json,
                    language = excluded.language,
                    visit_type = excluded.visit_type,
                    consent_given = excluded.consent_given,
                    patient_code = excluded.patient_code,
                    interview_step = excluded.interview_step,
                    interview_complete = excluded.interview_complete,
                    document_intake_done = excluded.document_intake_done,
                    chief_complaint = excluded.chief_complaint,
                    hpi_json = excluded.hpi_json,
                    documents_json = excluded.documents_json,
                    doctor_review_json = excluded.doctor_review_json,
                    answer_records_json = excluded.answer_records_json,
                    raw_answers_json = excluded.raw_answers_json,
                    safety_flagged = excluded.safety_flagged,
                    safety_flag_time = excluded.safety_flag_time,
                    safety_detail_json = excluded.safety_detail_json,
                    department = excluded.department,
                    queue_token = excluded.queue_token,
                    presentation_domain = excluded.presentation_domain,
                    collected_concepts_json = excluded.collected_concepts_json,
                    asked_questions_json = excluded.asked_questions_json,
                    asked_concepts_json = excluded.asked_concepts_json,
                    current_pending_question = excluded.current_pending_question,
                    adaptive_question_count = excluded.adaptive_question_count,
                    mentioned_documents_json = excluded.mentioned_documents_json,
                    adaptive = excluded.adaptive,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                session.session_id,
                session.patient.model_dump_json(),
                session.language,
                session.visit_type,
                int(session.consent_given),
                session.patient_code,
                session.interview_step,
                int(session.interview_complete),
                int(session.document_intake_done),
                session.chief_complaint,
                session.history_of_present_illness.model_dump_json(),
                json.dumps([doc.model_dump(mode="json") for doc in session.documents]),
                session.doctor_review.model_dump_json(),
                json.dumps([ar.model_dump(mode="json") for ar in session.answer_records]),
                json.dumps(session.raw_answers),
                int(session.safety_flagged),
                session.safety_flag_time.isoformat() if session.safety_flag_time else None,
                json.dumps(session.safety_detail),
                session.department,
                session.queue_token,
                session.presentation_domain,
                json.dumps(session.collected_concepts),
                json.dumps(session.asked_questions),
                json.dumps(session.asked_concepts),
                session.current_pending_question,
                int(session.adaptive_question_count),
                json.dumps(session.mentioned_documents),
                int(session.adaptive),
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
        answer_records_data = json.loads(row["answer_records_json"])
        raw_answers_data = json.loads(row["raw_answers_json"])
        safety_flag_time_str = row["safety_flag_time"]
        safety_detail_data = json.loads(row["safety_detail_json"])

        row_keys = row.keys()
        presentation_domain = row["presentation_domain"] if "presentation_domain" in row_keys else None
        collected_concepts = json.loads(row["collected_concepts_json"]) if "collected_concepts_json" in row_keys and row["collected_concepts_json"] else {}
        asked_questions = json.loads(row["asked_questions_json"]) if "asked_questions_json" in row_keys and row["asked_questions_json"] else []
        asked_concepts = json.loads(row["asked_concepts_json"]) if "asked_concepts_json" in row_keys and row["asked_concepts_json"] else []
        current_pending_question = row["current_pending_question"] if "current_pending_question" in row_keys else None
        adaptive_question_count = int(row["adaptive_question_count"]) if "adaptive_question_count" in row_keys and row["adaptive_question_count"] is not None else 0
        mentioned_documents = json.loads(row["mentioned_documents_json"]) if "mentioned_documents_json" in row_keys and row["mentioned_documents_json"] else []
        adaptive = bool(row["adaptive"]) if "adaptive" in row_keys and row["adaptive"] is not None else False
        
        return Session(
            session_id=row["session_id"],
            patient=Patient(**patient_data),
            language=row["language"],
            visit_type=row["visit_type"],
            consent_given=bool(row["consent_given"]),
            patient_code=row["patient_code"],
            interview_step=row["interview_step"],
            interview_complete=bool(row["interview_complete"]),
            document_intake_done=bool(row["document_intake_done"]),
            chief_complaint=row["chief_complaint"],
            history_of_present_illness=HistoryOfPresentIllness(**hpi_data),
            documents=[DocumentField(**d) for d in docs_data],
            doctor_review=DoctorReview(**review_data),
            answer_records=[AnswerRecord(**ar) for ar in answer_records_data],
            raw_answers=raw_answers_data,
            safety_flagged=bool(row["safety_flagged"]),
            safety_flag_time=datetime.fromisoformat(safety_flag_time_str) if safety_flag_time_str else None,
            safety_detail=safety_detail_data,
            department=row["department"],
            queue_token=row["queue_token"],
            presentation_domain=presentation_domain,
            collected_concepts=collected_concepts,
            asked_questions=asked_questions,
            asked_concepts=asked_concepts,
            current_pending_question=current_pending_question,
            adaptive_question_count=adaptive_question_count,
            mentioned_documents=mentioned_documents,
            adaptive=adaptive,
        )

    finally:
        conn.close()

def list_sessions(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id, patient_json, doctor_review_json FROM sessions "
            "WHERE safety_flagged = 0 ORDER BY created_at DESC"
        )
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

def next_queue_token(prefix: str, db_path: Optional[str] = None) -> str:
    """Return the next sequential queue token for a department prefix.

    Tokens look like ``KY-014`` / ``PK-008``. Sequence is derived from the
    highest existing number for the prefix + 1, so it is stable across
    restarts and idempotent per session.
    """
    conn = get_db_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT queue_token FROM sessions WHERE queue_token LIKE ?",
            (f"{prefix}-%",),
        ).fetchall()
    finally:
        conn.close()
    max_num = 0
    for r in rows:
        try:
            num = int(r["queue_token"].split("-", 1)[1])
            max_num = max(max_num, num)
        except (ValueError, IndexError):
            continue
    return f"{prefix}-{max_num + 1:03d}"

def list_queued_sessions(department: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return sessions that hold a department queue token for the D01 view.

    Only completed, non-flagged, token-issued sessions. Optionally filtered by
    department. Ordered oldest first (arrival at the department queue).
    """
    conn = get_db_connection(db_path)
    try:
        sql = (
            "SELECT session_id, patient_json, patient_code, chief_complaint, "
            "department, queue_token, doctor_review_json, created_at FROM sessions "
            "WHERE safety_flagged = 0 AND queue_token IS NOT NULL"
        )
        params: List[Any] = []
        if department:
            sql += " AND department = ?"
            params.append(department)
        sql += " ORDER BY created_at ASC"
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        result: List[Dict[str, Any]] = []
        for r in rows:
            patient = json.loads(r["patient_json"])
            review = json.loads(r["doctor_review_json"])
            result.append({
                "session_id": r["session_id"],
                "patient_code": r["patient_code"] or "",
                "patient_name": patient.get("name", "Unknown"),
                "chief_complaint": r["chief_complaint"] or "",
                "department": r["department"],
                "queue_token": r["queue_token"],
                "confirmed": bool(review.get("confirmed", False)),
                "ready_for_review": not review.get("confirmed", False),
                "check_in_time": r["created_at"] or "",
            })
        return result
    finally:
        conn.close()

def list_flagged_sessions(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return sessions whose safety_flagged=1 for the emergency dashboard."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id, patient_code, patient_json, chief_complaint, "
            "safety_flag_time, raw_answers_json FROM sessions "
            "WHERE safety_flagged = 1 ORDER BY safety_flag_time DESC"
        )
        rows = cursor.fetchall()
        result: List[Dict[str, Any]] = []
        for r in rows:
            patient = json.loads(r["patient_json"])
            raw_answers = json.loads(r["raw_answers_json"])
            flagged_raw = next(
                (a["answer"] for a in raw_answers if a.get("red_flag")), None
            )
            symptom = flagged_raw or r["chief_complaint"] or "Symptom not specified"
            result.append({
                "session_id": r["session_id"],
                "patient_code": r["patient_code"] or "",
                "patient_name": patient.get("name", "Unknown"),
                "symptom": symptom,
                "reported_at": r["safety_flag_time"] or "",
            })
        return result
    finally:
        conn.close()