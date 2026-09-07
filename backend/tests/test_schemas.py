import pytest
from pydantic import ValidationError
from backend.models.schema import (
    MedicineExtraction, DocumentField, Patient,
    HistoryOfPresentIllness, DoctorReview, Session
)

def test_valid_patient_schema():
    patient = Patient(name="Amit Kumar", age=40, gender="Male")
    assert patient.name == "Amit Kumar"
    assert patient.age == 40
    assert patient.gender == "Male"

def test_invalid_patient_age_rejected():
    with pytest.raises(ValidationError):
        Patient(name="Amit Kumar", age=-5, gender="Male")

def test_invalid_patient_empty_name_rejected():
    with pytest.raises(ValidationError):
        Patient(name="", age=25, gender="Female")

def test_valid_medicine_extraction():
    med = MedicineExtraction(
        medicine="Paracetamol",
        strength="500mg",
        dose="1 tablet",
        frequency="TDS",
        confidence=0.95
    )
    assert med.confidence == 0.95
    assert med.medicine == "Paracetamol"

def test_confidence_range_validation():
    # Confidence > 1.0 must fail
    with pytest.raises(ValidationError):
        MedicineExtraction(confidence=1.5)
    
    # Confidence < 0.0 must fail
    with pytest.raises(ValidationError):
        MedicineExtraction(confidence=-0.1)

    # DocumentField confidence > 1.0 must fail
    with pytest.raises(ValidationError):
        DocumentField(
            type="prescription",
            confidence=1.2,
            source="ocr",
            provider="gemini",
            needs_review=False
        )

    # DocumentField confidence < 0.0 must fail
    with pytest.raises(ValidationError):
        DocumentField(
            type="prescription",
            confidence=-0.5,
            source="ocr",
            provider="gemini",
            needs_review=False
        )

def test_session_mutable_defaults():
    session1 = Session(
        session_id="s-1",
        patient=Patient(name="Patient 1", age=25, gender="Female")
    )
    session2 = Session(
        session_id="s-2",
        patient=Patient(name="Patient 2", age=30, gender="Male")
    )
    
    session1.documents.append(DocumentField(
        type="prescription",
        confidence=0.8,
        source="ocr",
        provider="gemini",
        needs_review=False
    ))
    
    # Verify session2 documents list is independent and empty
    assert len(session1.documents) == 1
    assert len(session2.documents) == 0

def test_optional_fields_behavior():
    hpi = HistoryOfPresentIllness()
    assert hpi.onset is None
    assert hpi.duration is None
    assert hpi.character is None
    assert hpi.severity is None
    assert hpi.associated_symptoms == []
