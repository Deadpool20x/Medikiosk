# MediKiosk Live Demonstration & SIH 2026 Storyline

This guide describes how to run an interactive, end-to-end clinical demonstration of MediKiosk for evaluators and clinicians.

---

## 1. Demo Roles & Surfaces

| Persona | Surface | URL | Key Features Demonstrated |
| :--- | :--- | :--- | :--- |
| **Patient** | Kiosk Touchscreen | [http://localhost:3000](http://localhost:3000) | Multilingual welcome (EN, HI, MR, GU), consent, clinical interview, prescription upload, token generation |
| **Doctor** | Clinic Desktop | [http://localhost:3000/doctor](http://localhost:3000/doctor) | Real-time department queue, patient case inspection, OCR verification, clinical notes edit, confirmation |
| **Emergency Staff** | Triage Monitor | [http://localhost:3000/doctor/emergency](http://localhost:3000/doctor/emergency) | Priority-0 red-flag alerts, immediate diversion instructions, emergency tracking |

---

## 2. Controlled Demo Seed Data

To demonstrate the doctor workspace immediately without running manual intake first:

```bash
# Seeds pre-configured synthetic patients across Kayachikitsa and Panchakarma
python scripts/seed_demo.py
```

This seeds:
- Valid completed cases ready in the Kayachikitsa OPD queue (`KY-014`).
- Valid completed cases ready in the Panchakarma OPD queue (`PK-008`).
- Controlled emergency cases in the Emergency Dashboard (`D04`).

---

## 3. Recommended Live Demonstration Scenarios

### Scenario A: Normal Patient Intake & Prescription Upload
1. **P01 Welcome**: Select **Hindi (हिन्दी)** or **English**.
2. **P02 Consent**: Read and accept the patient intake consent.
3. **P03 Code**: Receive and note the 6-character session code.
4. **P04 Interview**:
   - Chief complaint: "Severe joint pain and knee swelling for 3 days."
   - Answer follow-up questions about onset, duration, and severity.
5. **P06 Records Upload**:
   - Upload sample prescription image (e.g. `tests/fixtures/sample_prescription.jpg`) or proceed.
   - Observe Vision LLM extracting medications (`Ashwagandha Churna 3g BD`).
6. **P07 Summary**: Verify the synthesized clinical summary.
7. **P08 Token**: Receive official queue token (e.g., `KY-014`).
8. **P09 Waiting Room**: View real-time estimated waiting time and queue status.

### Scenario B: Emergency Red-Flag Escalation
1. Start intake as a new patient.
2. In **P04 Clinical Interview**, enter:
   - *"I have severe chest pain radiating to my left arm and difficulty breathing."*
3. **P05 Emergency Alert**:
   - The kiosk immediately locks down the normal intake path.
   - Screen turns high-contrast emergency red with flashing medical instructions.
   - Directs patient to Emergency Room Bay 1 immediately.
   - No queue token is issued.
4. **D04 Verification**:
   - Open [http://localhost:3000/doctor/emergency](http://localhost:3000/doctor/emergency).
   - Verify the patient appears instantly with the red-flag symptom highlighted.

### Scenario C: Physician Consultation Review
1. Open [http://localhost:3000/doctor](http://localhost:3000/doctor).
2. Switch between **Kayachikitsa** and **Panchakarma** queues to observe deterministic departmental routing.
3. Click on the patient case to enter **D02 (Case Overview)**.
4. Click **Review & Edit (D03)**:
   - Verify AI-extracted symptoms and OCR medications.
   - Make a clinical correction to the dosage.
   - Click **Confirm Consultation**.
   - Observe the session state update atomically in the database.
