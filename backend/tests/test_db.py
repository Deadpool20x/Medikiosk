import os
import tempfile
import pytest
from backend.db import init_db, save_session, get_session, list_sessions
from backend.models.schema import Session, Patient, HistoryOfPresentIllness, DocumentField

def test_db_init_and_idempotency():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_medikiosk.db")
        # First initialization
        init_db(db_file)
        assert os.path.exists(db_file)
        # Second initialization (must not fail or error out)
        init_db(db_file)

def test_save_and_retrieve_session():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = os.path.join(tmpdir, "test_medikiosk.db")
        init_db(db_file)
        
        session = Session(
            session_id="test-uuid-123",
            patient=Patient(name="Test Patient", age=45, gender="Other"),
            chief_complaint="Chest discomfort",
            history_of_present_illness=HistoryOfPresentIllness(
                onset="2 days ago",
                associated_symptoms=["shortness of breath"]
            ),
            documents=[
                DocumentField(
                    type="prescription",
                    extracted_value="Aspirin 75mg",
                    confidence=0.92,
                    source="ocr",
                    provider="gemini",
                    needs_review=False
                )
            ]
        )
        save_session(session, db_file)
        
        retrieved = get_session("test-uuid-123", db_file)
        assert retrieved is not None
        assert retrieved.session_id == "test-uuid-123"
        assert retrieved.patient.name == "Test Patient"
        assert retrieved.chief_complaint == "Chest discomfort"
        assert retrieved.history_of_present_illness.onset == "2 days ago"
        assert len(retrieved.documents) == 1
        assert retrieved.documents[0].extracted_value == "Aspirin 75mg"

        # Check list sessions
        summaries = list_sessions(db_file)
        assert len(summaries) == 1
        assert summaries[0]["session_id"] == "test-uuid-123"
        assert summaries[0]["patient_name"] == "Test Patient"
        assert summaries[0]["ready_for_review"] is True
