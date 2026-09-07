import os
import json
import pytest
from backend.models.schema import Patient, HistoryOfPresentIllness

def test_synthetic_patient_data_validates():
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "synthetic_patients.json")
    assert os.path.exists(data_path), f"Synthetic patient file not found at {data_path}"
    
    with open(data_path, "r", encoding="utf-8") as f:
        patients = json.load(f)
    
    assert isinstance(patients, list)
    assert len(patients) >= 3
    
    for item in patients:
        # Validate Patient submodel
        patient = Patient(name=item["name"], age=item["age"], gender=item["gender"])
        assert patient.age > 0
        assert len(patient.name) > 0
        
        # Validate HPI submodel
        hpi = HistoryOfPresentIllness(
            onset=item.get("onset"),
            duration=item.get("duration"),
            character=item.get("character"),
            severity=item.get("severity"),
            associated_symptoms=item.get("associated_symptoms", [])
        )
        assert isinstance(hpi.associated_symptoms, list)
