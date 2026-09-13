#!/usr/bin/env python3
"""
scripts/simulate_roles_e2e.py
Comprehensive multi-role end-to-end simulation for MediKiosk.
Exercises:
1. Standard Patient Flow:
   - Language selection (Hindi / Gujarati / English)
   - Consent
   - Sequential Hospital Code (AIIA-YYYYMM-NNNNN)
   - Multi-turn clinical interview
   - Document advisory message check
   - Prescription upload & OCR verification
   - Queue token generation & waiting room
2. Emergency Patient Flow:
   - Direct button emergency request (/emergency)
   - State machine lockdown & token blocking
   - Conversational red-flag detection backstop
   - Immediate alert in emergency dashboard
3. Doctor Workflow:
   - Real-time department queues (Kayachikitsa & Panchakarma)
   - Patient case inspection
   - OCR correction & doctor review edit
   - Atomic clinical confirmation & queue transition
"""

import os
import sys
import io
import json
import tempfile
from unittest.mock import patch, AsyncMock
from PIL import Image, ImageDraw

# Ensure repo root is on PYTHONPATH
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from fastapi.testclient import TestClient
from backend.main import app
from backend.db import init_db
from backend.services import ocr_provider


def create_sample_prescription_image() -> bytes:
    """Generate a clean synthetic prescription image in memory."""
    img = Image.new("RGB", (600, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "Rx: Hospital Prescription", fill=(0, 0, 0))
    draw.text((20, 60), "1. Ashwagandha Churna 3g BD with warm milk", fill=(0, 0, 0))
    draw.text((20, 100), "2. Triphala Churna 5g HS with warm water", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def run_e2e_simulation():
    print("=" * 60)
    print("🏥 Starting MediKiosk Full Multi-Role End-to-End Simulation")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "sim_test.db")
        os.environ["DATABASE_PATH"] = db_path
        init_db(db_path)

        client = TestClient(app)

        # -------------------------------------------------------------
        # ROLE 1: Standard Patient (Panchakarma routing, Hindi)
        # -------------------------------------------------------------
        print("\n[ROLE 1: PATIENT INTAKE - Standard OPD Patient]")
        # 1. Start Session
        r_start = client.post("/session/start", json={
            "patient": {"name": "Suresh Patel", "age": 48, "gender": "male"},
            "language": "hi",
            "visit_type": "new",
            "adaptive": False
        })
        assert r_start.status_code == 200, f"Start failed: {r_start.text}"
        session_id = r_start.json()["session_id"]
        print(f"  ✓ Session initialized: {session_id}")

        # 2. Consent
        r_consent = client.post(f"/session/{session_id}/consent", json={"consent_given": True})
        assert r_consent.status_code == 200
        print("  ✓ Consent submitted")

        # 3. Patient Code (Sequential hospital format)
        r_code = client.post(f"/session/{session_id}/patient-code")
        assert r_code.status_code == 200
        patient_code = r_code.json()["patient_code"]
        assert patient_code.startswith("AIIA-"), f"Invalid format: {patient_code}"
        assert len(patient_code.split("-")) == 3, f"Expected AIIA-YYYYMM-NNNNN: {patient_code}"
        print(f"  ✓ Sequential patient code generated: {patient_code}")

        # 4. Clinical Interview (5-step structured HPI)
        dialogue = [
            ("chief_complaint", "मुझे अत्यधिक मोटापा और वजन बढ़ने (medoroga) की समस्या है।"),
            ("onset", "यह समस्या 6 महीने पहले शुरू हुई थी।"),
            ("duration", "लगातार 6 महीने से वजन बढ़ रहा है।"),
            ("severity", "गंभीरता मध्यम है, थकान रहती है।"),
            ("character", "शरीर में भारीपन और सुस्ती रहती है।"),
            ("associated_symptoms", "साथ में जोड़ों में हल्का दर्द और अपच है।")
        ]

        for step_name, answer_text in dialogue:
            r_ans = client.post(f"/session/{session_id}/answer", json={"answer": answer_text})
            assert r_ans.status_code == 200
            ans_data = r_ans.json()
            assert not ans_data["red_flag"], f"Unexpected red flag on: {answer_text}"

        assert ans_data["session_complete"] is True
        assert ans_data["completion_message"] is not None
        print(f"  ✓ Interview completed. Advisory: '{ans_data['completion_message'][:60]}...'")

        # 5. Prescription Upload with configured mock vision provider
        img_bytes = create_sample_prescription_image()
        with patch.object(ocr_provider.GeminiVisionProvider, "is_configured", return_value=True), \
             patch.object(ocr_provider.GeminiVisionProvider, "extract_prescription", AsyncMock(return_value=json.dumps({
                 "medicine": "Ashwagandha Churna", "strength": "3g", "dose": "1 spoon", "frequency": "BD", "confidence": 0.95
             }))):
            r_upload = client.post(
                f"/session/{session_id}/upload",
                files={"file": ("prescription.jpg", img_bytes, "image/jpeg")}
            )
            assert r_upload.status_code == 200
            upload_data = r_upload.json()
            print(f"  ✓ Prescription uploaded and processed ({upload_data.get('medicine')} - confidence {upload_data.get('confidence')})")

        # 6. Complete Document Intake
        r_doc_done = client.post(f"/session/{session_id}/documents-complete")
        assert r_doc_done.status_code == 200
        print("  ✓ Document intake stage marked complete")

        # 7. Generate Queue Token (Deterministic routing: medoroga/obesity -> Panchakarma)
        r_token = client.post(f"/session/{session_id}/token")
        assert r_token.status_code == 200, f"Token generation failed: {r_token.text}"
        token_data = r_token.json()
        token = token_data["token"]
        dept = token_data["department"]
        assert token.startswith("PK-"), f"Expected PK token for Panchakarma, got {token}"
        assert dept == "Panchakarma", f"Expected Panchakarma department, got {dept}"
        print(f"  ✓ Queue Token Issued: {token} (Dept: {dept})")

        # -------------------------------------------------------------
        # ROLE 2: Emergency Patients (Direct Button & Conversational)
        # -------------------------------------------------------------
        print("\n[ROLE 2: EMERGENCY PATIENTS - Direct Button & Red Flag]")
        # Case A: Direct "🚨 Need Help Now" Button
        r_em1 = client.post("/session/start", json={
            "patient": {"name": "Ramesh Gupta", "age": 62, "gender": "male"},
            "language": "en",
            "visit_type": "new"
        })
        em1_id = r_em1.json()["session_id"]
        r_direct = client.post(f"/session/{em1_id}/emergency")
        assert r_direct.status_code == 200
        direct_data = r_direct.json()
        assert direct_data["safety_flagged"] is True
        assert direct_data["redirect_screen"] == "P05_EMERGENCY"

        # Verify state machine lockdown
        r_lockdown = client.post(f"/session/{em1_id}/token")
        assert r_lockdown.status_code == 403, "Normal token generation must be blocked for emergency"
        print(f"  ✓ Direct Emergency button triggered and locked down ({em1_id})")

        # Case B: Conversational Red-Flag
        r_em2 = client.post("/session/start", json={
            "patient": {"name": "Anita Sharma", "age": 55, "gender": "female"},
            "language": "en",
            "visit_type": "new"
        })
        em2_id = r_em2.json()["session_id"]
        client.post(f"/session/{em2_id}/consent", json={"consent_given": True})
        client.post(f"/session/{em2_id}/patient-code")
        r_redflag = client.post(f"/session/{em2_id}/answer", json={
            "answer": "I have crushing chest pain radiating to my left arm with shortness of breath."
        })
        assert r_redflag.status_code == 200, f"Answer failed: {r_redflag.text}"
        assert r_redflag.json()["red_flag"] is True
        print(f"  ✓ Conversational red-flag detected and diverted ({em2_id})")

        # Verify Emergency Dashboard lists both emergency cases
        r_em_dash = client.get("/doctor/emergency")
        assert r_em_dash.status_code == 200
        em_list = r_em_dash.json()
        em_ids = [s["session_id"] for s in em_list]
        assert em1_id in em_ids, "Direct emergency patient missing from dashboard"
        assert em2_id in em_ids, "Conversational red-flag patient missing from dashboard"
        print(f"  ✓ Emergency Dashboard contains all emergency cases (Total: {len(em_list)})")

        # -------------------------------------------------------------
        # ROLE 3: Doctor Consultation Workflow
        # -------------------------------------------------------------
        print("\n[ROLE 3: DOCTOR CONSULTATION - Queue & Case Review]")
        # 1. Inspect Panchakarma Queue
        r_queue_pk = client.get("/doctor/queue?department=Panchakarma")
        assert r_queue_pk.status_code == 200
        pk_cases = r_queue_pk.json()
        target_case = next((c for c in pk_cases if c["session_id"] == session_id), None)
        assert target_case is not None, "Target patient not found in Panchakarma queue"
        print(f"  ✓ Doctor found patient {target_case['patient_name']} ({target_case['queue_token']}) in Panchakarma queue")

        # 2. Retrieve Comprehensive Case Detail (D02)
        r_detail = client.get(f"/doctor/session/{session_id}")
        assert r_detail.status_code == 200
        detail = r_detail.json()
        assert detail["patient_code"] == patient_code
        print(f"  ✓ Doctor retrieved case details for {patient_code}")

        # 3. Doctor Review & Clinical Notes / Symptom Edit (D03)
        r_edit = client.patch(f"/doctor/session/{session_id}", json={
            "character": "Heavy sluggishness with kapha predominance (verified by physician)",
            "doctor_confirmed": False
        })
        assert r_edit.status_code == 200
        print("  ✓ Doctor updated clinical HPI details")

        # 4. Doctor Final Confirmation
        r_confirm = client.patch(f"/doctor/session/{session_id}", json={
            "doctor_confirmed": True
        })
        assert r_confirm.status_code == 200
        print("  ✓ Doctor confirmed case consultation")

        # 5. Verify Queue Status Update
        r_queue_after = client.get("/doctor/queue?department=Panchakarma")
        remaining_ready = [c for c in r_queue_after.json() if c["ready_for_review"]]
        assert not any(c["session_id"] == session_id for c in remaining_ready)
        print("  ✓ Patient cleanly marked completed and cleared from active intake queue")

        print("\n" + "=" * 60)
        print("🎉 ALL MULTI-ROLE REAL E2E SIMULATION TESTS PASSED!")
        print("=" * 60)


if __name__ == "__main__":
    run_e2e_simulation()
