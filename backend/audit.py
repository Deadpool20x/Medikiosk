#!/usr/bin/env python3
"""
Audit script for MediKiosk P0 workflow.
Tests the scenarios described in the audit request.
"""
import sys
import os
import json
from datetime import datetime

# Repository-independent paths derived from this file's real location,
# so the audit works regardless of the launching working directory.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

# Add the project root to the path so we can import backend as a package
sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from backend.main import app
from backend.models.schema import Session, Patient
from backend.db import init_db, get_session, save_session
from backend.routers import session as session_router
from unittest.mock import patch
import tempfile

# ---------------------------------------------------------------------------
# Test-only deterministic provider mock (mirrors scripts/p0_server.py).
# The audit must never depend on a live external LLM API.
# ---------------------------------------------------------------------------

class _FakeProvider:
    provider_name = "gemini"


def _mock_extract(provider, field, ans):
    """Echo the raw answer as the structured extraction value."""
    if field == "chief_complaint":
        return {"complaint": ans.strip(), "confidence": 0.9}
    if field == "associated_symptoms":
        return {"associated_symptoms": [ans.strip()], "confidence": 0.9}
    return {field: ans.strip(), "confidence": 0.9}


def _mock_extract_case(ans, current_concept=None, domain_hint=None):
    """Echo the raw answer as the structured case extraction value."""
    return {
        "domain": "general",
        "concepts": {current_concept: ans.strip()},
        "confidence": 0.9,
        "mentioned_documents": [],
        "provider": "gemini",
    }

def setup_test_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "test.db")
    os.environ["DATABASE_PATH"] = db_path
    init_db(db_path)
    return temp_dir

def test_normal_patient_flow():
    """Test the normal patient flow: P01 -> P02 -> P03 -> P04 -> P06 -> P07 -> P08 -> P09 -> D01 -> D02 -> D03"""
    print("=== Testing Normal Patient Flow ===")
    temp_dir = setup_test_db()
    try:
        client = TestClient(app)
        
        # P01: Start session
        patient_data = {
            "name": "John Doe",
            "age": 30,
            "gender": "Male"
        }
        response = client.post("/session/start", json={"patient": patient_data, "language": "en", "visit_type": "new", "adaptive": False})
        assert response.status_code == 200, f"Failed to start session: {response.text}"
        session_id = response.json()["session_id"]
        print(f"  Started session: {session_id}")
        
        # P02: Consent
        response = client.post(f"/session/{session_id}/consent", json={"consent_given": True})
        assert response.status_code == 200, f"Failed to submit consent: {response.text}"
        print("  Consent given")
        
        # P03: Patient code
        response = client.post(f"/session/{session_id}/patient-code")
        assert response.status_code == 200, f"Failed to get patient code: {response.text}"
        patient_code = response.json()["patient_code"]
        assert patient_code.startswith("AIIA-"), f"Unexpected patient code format: {patient_code}"
        print(f"  Patient code: {patient_code}")
        
        # P04: Interview - we'll go through the required fields
        # We'll use a set of answers that should not trigger safety flags
        answers = [
            ("chief_complaint", "I have been having stomach pain for the last 2 days."),
            ("onset", "It started 2 days ago after eating spoiled food."),
            ("duration", "It has been constant for 2 days."),
            ("severity", "I would rate it as 5 out of 10."),
            ("character", "It is a dull, aching pain."),
            ("associated_symptoms", "I have also experienced some nausea.")
        ]
        
        with patch.object(session_router, "get_llm_provider", return_value=_FakeProvider()), \
             patch.object(session_router, "extract_field", side_effect=_mock_extract), \
             patch.object(session_router, "extract_case", side_effect=_mock_extract_case):
            for field, answer in answers:
                response = client.post(f"/session/{session_id}/answer", json={"answer": answer})
                assert response.status_code == 200, f"Failed to submit answer for {field}: {response.text}"
                data = response.json()
                # We don't care about the next question here, just that it didn't error
                print(f"  Answered {field}: {answer}")
        
        # After the last answer, we should be at the end of the interview
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200, f"Failed to get session: {response.text}"
        session_data = response.json()
        assert session_data["interview_complete"] == True, "Interview should be complete after all answers"
        print("  Interview complete")
        
        # P06: Document upload (we'll skip this for now because we don't have a real image, but we can test the endpoint)
        # We'll test that the endpoint exists and requires the right state
        # We'll skip the actual upload because we don't have an image file in this environment
        # Instead, we'll test that we can't upload without being at the right state (we are at the end of interview, which is after P04, and P06 comes after P04 in the flow)
        # But note: in the flow, P06 comes after P04 and before P07. We are at the end of P04, so we can go to P06.
        # We'll test the upload endpoint with a dummy file to see if it returns the expected error for missing file or invalid file.
        # We'll skip the actual OCR test because we already tested that in the OCR test suite.
        print("  Skipping document upload test (no image file in audit environment)")
        
        # P07: Summary review
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200, f"Failed to get session for summary: {response.text}"
        session_data = response.json()
        # Check that the session has the data we expect
        assert session_data["patient"]["name"] == "John Doe"
        assert session_data["chief_complaint"] == "I have been having stomach pain for the last 2 days."
        assert len(session_data["answer_records"]) == 6
        print("  Session data retrieved for summary")

        # P06 gate: mark document intake complete (F-06: requires interview_complete=True)
        response = client.post(f"/session/{session_id}/documents-complete")
        assert response.status_code == 200, f"Failed to mark documents complete: {response.text}"
        print("  Documents step marked complete")

        # P08: Token generation
        response = client.post(f"/session/{session_id}/token")
        assert response.status_code == 200, f"Failed to generate token: {response.text}"
        token_data = response.json()
        token = token_data["token"]           # field is 'token', not 'patient_code'
        department = token_data["department"]
        # Token prefix depends on department (KY- for Kayachikitsa, PK- for Panchakarma)
        assert "-" in token, f"Unexpected token format (missing hyphen): {token}"
        print(f"  Token generated: {token} (department: {department})")

        # P09: Waiting/completion
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200, f"Failed to get session for waiting: {response.text}"
        session_data = response.json()
        assert session_data["queue_token"] == token, \
            f"queue_token mismatch: expected {token!r}, got {session_data['queue_token']!r}"
        print("  Waiting/completion state verified")
        
        # D01: Doctor queue
        response = client.get("/doctor/sessions")
        assert response.status_code == 200, f"Failed to get doctor sessions: {response.text}"
        sessions = response.json()
        # Find our session in the list
        found = False
        for s in sessions:
            if s["session_id"] == session_id:
                found = True
                assert s["patient_name"] == "John Doe"
                assert s["ready_for_review"] == True  # Not confirmed by doctor yet
                break
        assert found, "Session not found in doctor queue"
        print("  Session found in doctor queue")
        
        # D02: Patient case detail
        response = client.get(f"/doctor/session/{session_id}")
        assert response.status_code == 200, f"Failed to get doctor session detail: {response.text}"
        case_data = response.json()
        assert case_data["session_id"] == session_id
        assert case_data["patient"]["name"] == "John Doe"
        assert case_data["chief_complaint"] == "I have been having stomach pain for the last 2 days."
        print("  Doctor session detail retrieved")
        
        # D03: Review/edit/confirm
        # Let's edit the chief complaint
        patch_data = {"chief_complaint": "I have been having stomach pain and vomiting for the last 2 days."}
        response = client.patch(f"/doctor/session/{session_id}", json=patch_data)
        assert response.status_code == 200, f"Failed to patch doctor session: {response.text}"
        updated_case = response.json()
        assert updated_case["chief_complaint"] == patch_data["chief_complaint"]
        assert updated_case["doctor_review"]["edited"] == True
        print("  Doctor edit successful")
        
        # Now confirm the case
        patch_data = {"doctor_confirmed": True}
        response = client.patch(f"/doctor/session/{session_id}", json=patch_data)
        assert response.status_code == 200, f"Failed to confirm doctor session: {response.text}"
        confirmed_case = response.json()
        assert confirmed_case["doctor_review"]["confirmed"] == True
        print("  Doctor confirmation successful")
        
        # Verify that the session is no longer ready for review in the queue
        response = client.get("/doctor/sessions")
        assert response.status_code == 200, f"Failed to get doctor sessions after confirmation: {response.text}"
        sessions = response.json()
        found = False
        for s in sessions:
            if s["session_id"] == session_id:
                found = True
                assert s["ready_for_review"] == False  # Now confirmed by doctor
                break
        assert found, "Session not found in doctor queue after confirmation"
        print("  Session no longer in ready-for-review queue after confirmation")
        
        print("=== Normal Patient Flow: PASSED ===")
        return True
    except Exception as e:
        print(f"=== Normal Patient Flow: FAILED ===")
        print(f"  Error: {e}")
        return False
    finally:
        temp_dir.cleanup()

def test_safety_patient():
    """Test a safety patient: trigger a known deterministic red-flag answer."""
    print("\n=== Testing Safety Patient ===")
    temp_dir = setup_test_db()
    try:
        client = TestClient(app)
        
        # Start session, consent, patient code
        patient_data = {
            "name": "Jane Smith",
            "age": 45,
            "gender": "Female"
        }
        response = client.post("/session/start", json={"patient": patient_data, "language": "en", "visit_type": "new", "adaptive": False})
        assert response.status_code == 200, f"Failed to start session: {response.text}"
        session_id = response.json()["session_id"]
        print(f"  Started session: {session_id}")
        
        response = client.post(f"/session/{session_id}/consent", json={"consent_given": True})
        assert response.status_code == 200, f"Failed to submit consent: {response.text}"
        print("  Consent given")
        
        response = client.post(f"/session/{session_id}/patient-code")
        assert response.status_code == 200, f"Failed to get patient code: {response.text}"
        patient_code = response.json()["patient_code"]
        print(f"  Patient code: {patient_code}")
        
        # Now give an answer that should trigger a red flag
        # According to the safety rules, chest pain is a red flag
        response = client.post(f"/session/{session_id}/answer", json={"answer": "I have severe chest pain."})
        assert response.status_code == 200, f"Failed to submit answer: {response.text}"
        data = response.json()
        # The response should indicate a red flag
        assert data.get("red_flag") == True, f"Expected red flag to be true, got {data}"
        print("  Red flag detected in answer response")
        
        # Verify the session is now safety flagged
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200, f"Failed to get session: {response.text}"
        session_data = response.json()
        assert session_data["safety_flagged"] == True, "Session should be safety flagged"
        print("  Session is safety flagged")
        
        # Verify that we cannot get a normal token
        response = client.post(f"/session/{session_id}/token")
        assert response.status_code == 403, f"Expected 403 for token generation on safety flagged session, got {response.status_code}"
        print("  Token generation correctly blocked for safety flagged session")
        
        # Verify that the session does not appear in the normal doctor queue
        response = client.get("/doctor/sessions")
        assert response.status_code == 200, f"Failed to get doctor sessions: {response.text}"
        sessions = response.json()
        found = False
        for s in sessions:
            if s["session_id"] == session_id:
                found = True
                break
        assert not found, "Safety flagged session should not appear in normal doctor queue"
        print("  Session correctly excluded from normal doctor queue")
        
        # Verify that the session appears in the emergency dashboard
        response = client.get("/doctor/emergency")
        assert response.status_code == 200, f"Failed to get emergency dashboard: {response.text}"
        emergency_sessions = response.json()
        found = False
        for s in emergency_sessions:
            if s["session_id"] == session_id:
                found = True
                assert s["patient_name"] == "Jane Smith"
                # The symptom should be something like chest pain
                assert "chest pain" in s["symptom"].lower()
                break
        assert found, "Safety flagged session not found in emergency dashboard"
        print("  Session found in emergency dashboard")
        
        # Verify that refreshing preserves the safety state
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200, f"Failed to get session after refresh: {response.text}"
        session_data = response.json()
        assert session_data["safety_flagged"] == True, "Safety flag should persist after refresh"
        print("  Safety state preserved after refresh")
        
        # Verify that we cannot bypass safety through upload
        # We'll try to upload a document (we'll skip the actual upload because we don't have an image, but we can test the endpoint)
        # The upload endpoint should return 403 because the session is safety flagged
        # We'll use a dummy file to test the endpoint
        files = {"file": ("test.jpg", b"dummy image content", "image/jpeg")}
        response = client.post(f"/session/{session_id}/upload", files=files)
        assert response.status_code == 403, f"Expected 403 for upload on safety flagged session, got {response.status_code}"
        print("  Upload correctly blocked for safety flagged session")
        
        print("=== Safety Patient: PASSED ===")
        return True
    except Exception as e:
        print(f"=== Safety Patient: FAILED ===")
        print(f"  Error: {e}")
        return False
    finally:
        temp_dir.cleanup()

def test_ocr_low_confidence():
    """Test OCR low confidence scenario."""
    print("\n=== Testing OCR Low Confidence ===")
    # We already have a test for this in the test suite: test_low_confidence_extraction_flagged_for_review
    # We'll just run that specific test to make sure it passes in our environment
    import subprocess
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_ocr_phase3.py::test_low_confidence_extraction_flagged_for_review",
        "-v"
    ], capture_output=True, text=True, cwd=BACKEND_DIR)
    if result.returncode == 0:
        print("  OCR low confidence test passed")
        return True
    else:
        print("  OCR low confidence test failed")
        print(result.stdout)
        print(result.stderr)
        return False

def test_ocr_provider_failure():
    """Test OCR provider failure and fallback."""
    print("\n=== Testing OCR Provider Failure ===")
    # We have tests for Gemini failure falling back to Groq and both failing
    import subprocess
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_ocr_phase3.py::test_gemini_failure_falls_back_to_groq",
        "tests/test_ocr_phase3.py::test_both_providers_fail_returns_review_no_error_leak",
        "-v"
    ], capture_output=True, text=True, cwd=BACKEND_DIR)
    if result.returncode == 0:
        print("  OCR provider failure tests passed")
        return True
    else:
        print("  OCR provider failure tests failed")
        print(result.stdout)
        print(result.stderr)
        return False

def test_interview_llm_failure():
    """Test interview/LLM failure scenarios."""
    print("\n=== Testing Interview/LLM Failure ===")
    # We have a test for LLM extraction failure preserving raw and marking review
    import subprocess
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_session_flow.py::test_llm_extraction_failure_preserves_raw_and_marks_review",
        "-v"
    ], capture_output=True, text=True, cwd=BACKEND_DIR)
    if result.returncode == 0:
        print("  Interview LLM failure test passed")
        return True
    else:
        print("  Interview LLM failure test failed")
        print(result.stdout)
        print(result.stderr)
        return False

def test_refresh_resume():
    """Test refresh/resume at various points."""
    print("\n=== Testing Refresh/Resume ===")
    temp_dir = setup_test_db()
    try:
        client = TestClient(app)
        
        # We'll test at P02 (after consent), P03 (after patient code), P04 (after first answer), P06 (after upload), etc.
        # But to keep it simple, we'll test a few key points.
        
        # Start session and consent
        patient_data = {
            "name": "Bob Johnson",
            "age": 25,
            "gender": "Male"
        }
        response = client.post("/session/start", json={"patient": patient_data, "language": "en", "visit_type": "new", "adaptive": False})
        assert response.status_code == 200, f"Failed to start session: {response.text}"
        session_id = response.json()["session_id"]
        
        response = client.post(f"/session/{session_id}/consent", json={"consent_given": True})
        assert response.status_code == 200, f"Failed to submit consent: {response.text}"
        
        # Now we are at P02 equivalent (after consent)
        # Get the session to see if state is preserved
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200, f"Failed to get session after consent: {response.text}"
        session_data = response.json()
        assert session_data["consent_given"] == True
        print("  Consent state preserved after refresh (P02)")
        
        # Get patient code (P03)
        response = client.post(f"/session/{session_id}/patient-code")
        assert response.status_code == 200, f"Failed to get patient code: {response.text}"
        patient_code = response.json()["patient_code"]
        
        # Refresh and check
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200, f"Failed to get session after patient code: {response.text}"
        session_data = response.json()
        assert session_data["patient_code"] == patient_code
        print("  Patient code preserved after refresh (P03)")
        
        # Answer one question (P04)
        response = client.post(f"/session/{session_id}/answer", json={"answer": "I have a headache."})
        assert response.status_code == 200, f"Failed to submit answer: {response.text}"
        
        # Refresh and check
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200, f"Failed to get session after answer: {response.text}"
        session_data = response.json()
        assert len(session_data["answer_records"]) == 1
        print("  Answer record preserved after refresh (P04)")
        
        # We'll skip P06 (upload) because we don't have an image, but we can test that the state is preserved after an upload attempt (even if it fails)
        # We'll test that the raw answers are preserved
        response = client.post(f"/session/{session_id}/answer", json={"answer": "I also feel nauseous."})
        assert response.status_code == 200, f"Failed to submit second answer: {response.text}"
        
        response = client.get(f"/session/{session_id}")
        assert response.status_code == 200, f"Failed to get session after second answer: {response.text}"
        session_data = response.json()
        assert len(session_data["answer_records"]) == 2
        print("  Multiple answer records preserved after refresh")
        
        print("=== Refresh/Resume: PASSED ===")
        return True
    except Exception as e:
        print(f"=== Refresh/Resume: FAILED ===")
        print(f"  Error: {e}")
        return False
    finally:
        temp_dir.cleanup()

def test_token_integrity():
    """Test token integrity scenarios."""
    print("\n=== Testing Token Integrity ===")
    # We have tests for this in the test suite
    import subprocess
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_phase4.py::test_token_403_incomplete_session",
        "tests/test_phase4.py::test_token_403_safety_flagged",
        "tests/test_phase4.py::test_token_403_pending_review",
        "tests/test_phase4.py::test_token_issue_success_persisted_and_idempotent",
        "tests/test_phase4.py::test_token_sequential_per_department",
        "-v"
    ], capture_output=True, text=True, cwd=BACKEND_DIR)
    if result.returncode == 0:
        print("  Token integrity tests passed")
        return True
    else:
        print("  Token integrity tests failed")
        print(result.stdout)
        print(result.stderr)
        return False

def test_doctor_workflow():
    """Test doctor workflow scenarios."""
    print("\n=== Testing Doctor Workflow ===")
    # We have tests for this in the test suite
    import subprocess
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_phase4.py::test_d01_queue_excludes_non_queued_and_flagged",
        "tests/test_phase4.py::test_d01_department_filter_and_status",
        "tests/test_phase4.py::test_d02_doctor_session_detail",
        "tests/test_phase4.py::test_d03_doctor_edit_persists_and_marks_edited",
        "tests/test_phase4.py::test_d03_doctor_confirm_case",
        "tests/test_phase4.py::test_refresh_resume_returns_token_and_department",
        "tests/test_phase4.py::test_no_fake_queue_stats_without_token",
        "-v"
    ], capture_output=True, text=True, cwd=BACKEND_DIR)
    if result.returncode == 0:
        print("  Doctor workflow tests passed")
        return True
    else:
        print("  Doctor workflow tests failed")
        print(result.stdout)
        print(result.stderr)
        return False

def test_department_separation():
    """Test department separation for Kayachikitsa and Panchakarma."""
    print("\n=== Testing Department Separation ===")
    # We have a test for department classification and routing
    import subprocess
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_phase4.py::test_department_routing_panchakarma",
        "tests/test_phase4.py::test_department_classifier_deterministic",
        "-v"
    ], capture_output=True, text=True, cwd=BACKEND_DIR)
    if result.returncode == 0:
        print("  Department separation tests passed")
        return True
    else:
        print("  Department separation tests failed")
        print(result.stdout)
        print(result.stderr)
        return False

def main():
    """Run all audit scenarios."""
    print("Starting MediKiosk P0 Final End-to-End Audit")
    print("=" * 50)
    
    results = []
    
    # Run the tests
    results.append(("Normal Patient Flow", test_normal_patient_flow()))
    results.append(("Safety Patient", test_safety_patient()))
    results.append(("OCR Low Confidence", test_ocr_low_confidence()))
    results.append(("OCR Provider Failure", test_ocr_provider_failure()))
    results.append(("Interview/LLM Failure", test_interview_llm_failure()))
    results.append(("Refresh/Resume", test_refresh_resume()))
    results.append(("Token Integrity", test_token_integrity()))
    results.append(("Doctor Workflow", test_doctor_workflow()))
    results.append(("Department Separation", test_department_separation()))
    
    # Print summary
    print("\n" + "=" * 50)
    print("AUDIT RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        if result:
            passed += 1
        else:
            failed += 1
        print(f"{name:<30} {status}")
    
    print("-" * 50)
    print(f"TOTAL: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\nAll audit scenarios PASSED.")
        print("Ready for P0 evaluation.")
    else:
        print(f"\n{failed} audit scenario(s) FAILED.")
        print("Review the failures before proceeding.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)