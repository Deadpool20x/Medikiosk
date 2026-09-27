from fastapi import APIRouter, HTTPException, Request, Depends
from typing import List, Optional
from pydantic import BaseModel
from backend.models.schema import Session
from backend.db import get_session, save_session, list_sessions, list_flagged_sessions, list_queued_sessions
from backend.rules.adaptive_interview import completeness_gaps
from backend.rules.clinical_review import clinical_mentions
from backend.services.documents import correct_document

import os

# ----- Access guard (Production Token + Local Demo Loopback Fallback) -----
# In production, DOCTOR_SECRET_TOKEN can be set to require 'X-Doctor-Token'.
# In demo mode, loopback clients (the kiosk host itself) are allowed.
_LOOPBACK_CLIENTS = {"127.0.0.1", "::1", "localhost", "testclient"}  # testclient = ASGI TestClient

def require_doctor_access(request: Request) -> None:
    secret_token = os.getenv("DOCTOR_SECRET_TOKEN", "").strip()
    if secret_token:
        provided = request.headers.get("X-Doctor-Token", "")
        if provided != secret_token:
            raise HTTPException(status_code=401, detail="Unauthorized doctor access token.")
        return

    host = request.client.host if request.client else ""
    if host not in _LOOPBACK_CLIENTS:
        raise HTTPException(status_code=403, detail="Doctor workspace is local-only in this demo build.")

require_loopback = require_doctor_access

router = APIRouter(prefix="/doctor", tags=["doctor"], dependencies=[Depends(require_doctor_access)])

class SessionSummary(BaseModel):
    session_id: str
    patient_name: str
    ready_for_review: bool

class QueueItem(BaseModel):
    session_id: str
    patient_code: str
    patient_name: str
    chief_complaint: str
    department: Optional[str] = None
    queue_token: Optional[str] = None
    confirmed: bool
    ready_for_review: bool
    check_in_time: str

class EmergencyItem(BaseModel):
    session_id: str
    patient_code: str
    patient_name: str
    symptom: str
    reported_at: str
    status: str = "Safety Alert — Review Required"

class SessionPatchRequest(BaseModel):
    chief_complaint: Optional[str] = None
    onset: Optional[str] = None
    duration: Optional[str] = None
    severity: Optional[str] = None
    character: Optional[str] = None
    associated_symptoms: Optional[List[str]] = None
    doctor_confirmed: Optional[bool] = None

class DocumentCorrectionRequest(BaseModel):
    corrected_value: Optional[str] = None
    strength: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None


class CaseSummaryResponse(BaseModel):
    summary: str
    provider: str
    generated_at: str

@router.get("/sessions", response_model=List[SessionSummary])
async def get_doctor_sessions():
    sessions = list_sessions()
    return [SessionSummary(**s) for s in sessions]

@router.get("/emergency", response_model=List[EmergencyItem])
async def get_doctor_emergency():
    flagged = list_flagged_sessions()
    return [EmergencyItem(**s) for s in flagged]

@router.get("/queue", response_model=List[QueueItem])
async def get_doctor_queue(department: Optional[str] = None):
    """D01: department queue of completed, token-issued sessions."""
    return [QueueItem(**s) for s in list_queued_sessions(department=department)]

@router.get("/session/{session_id}", response_model=Session)
async def get_doctor_session(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Doctor-facing completeness gaps + term standings, computed on read.
    session.completeness_gaps = completeness_gaps(session)
    session.clinical_mentions = clinical_mentions(session)
    return session


@router.patch("/session/{session_id}", response_model=Session)
async def patch_doctor_session(session_id: str, patch_data: SessionPatchRequest):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    hpi = session.history_of_present_illness
    changed = False

    def _mark_clinician(*keys: str) -> None:
        for k in keys:
            session.concept_provenance[k] = {"source": "clinician-entered", "provider": None}

    if patch_data.chief_complaint is not None and patch_data.chief_complaint != session.chief_complaint:
        session.chief_complaint = patch_data.chief_complaint
        _mark_clinician("chief_complaint", "primary_symptom")
        changed = True
    if patch_data.onset is not None and patch_data.onset != hpi.onset:
        hpi.onset = patch_data.onset
        _mark_clinician("onset")
        changed = True
    if patch_data.duration is not None and patch_data.duration != hpi.duration:
        hpi.duration = patch_data.duration
        _mark_clinician("duration")
        changed = True
    if patch_data.severity is not None and patch_data.severity != hpi.severity:
        hpi.severity = patch_data.severity
        _mark_clinician("severity")
        changed = True
    if patch_data.character is not None and patch_data.character != hpi.character:
        hpi.character = patch_data.character
        _mark_clinician("character")
        changed = True
    if patch_data.associated_symptoms is not None and patch_data.associated_symptoms != hpi.associated_symptoms:
        hpi.associated_symptoms = patch_data.associated_symptoms
        _mark_clinician("associated_symptoms")
        changed = True

    if changed:
        session.doctor_review.edited = True
    if patch_data.doctor_confirmed is not None:
        if patch_data.doctor_confirmed and session.safety_flagged:
            raise HTTPException(
                status_code=409,
                detail="Cannot confirm a safety-flagged session. Resolve the safety flag first.",
            )
        session.doctor_review.confirmed = patch_data.doctor_confirmed

    save_session(session)
    session.completeness_gaps = completeness_gaps(session)
    session.clinical_mentions = clinical_mentions(session)
    return session

@router.patch("/session/{session_id}/document/{index}", response_model=Session)
async def correct_doctor_document(session_id: str, index: int, payload: DocumentCorrectionRequest):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        correct_document(
            session, index,
            corrected_value=payload.corrected_value,
            strength=payload.strength,
            dose=payload.dose,
            frequency=payload.frequency,
        )
    except IndexError:
        raise HTTPException(status_code=404, detail="Document not found")
    save_session(session)
    return session


# Spec §7.3: physician-readable prose generated ONLY from already-structured
# data (never raw text, never new facts). Transient: nothing is persisted,
# nothing is diagnosed. 502 + retryable when no provider or output invalid.
@router.post("/session/{session_id}/summary", response_model=CaseSummaryResponse)
async def generate_case_summary(session_id: str):
    from datetime import datetime, timezone
    from backend.services.llm_provider import iter_llm_providers
    from backend.rules.adaptive_interview import PROHIBITED_QUESTION_PATTERNS
    import re

    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    structured = {
        "chief_complaint": session.chief_complaint,
        "history_of_present_illness": session.history_of_present_illness.model_dump(),
        "collected_concepts": session.collected_concepts,
        "concept_provenance": session.concept_provenance,
        "completeness_gaps": completeness_gaps(session),
        "documents": [
            {"type": d.type, "extracted_value": d.extracted_value,
             "needs_review": d.needs_review,
             "manually_corrected": d.manually_corrected} for d in session.documents
        ],
        "safety_flagged": session.safety_flagged,
        "doctor_edited": session.doctor_review.edited,
        "doctor_confirmed": session.doctor_review.confirmed,
    }
    system_prompt = (
        "Convert this structured clinical data into a short, factual summary for a "
        "physician. Do not add any information not present in the input data. Do not "
        "suggest a diagnosis or treatment. If a field is missing or null, state that it is "
        "not available rather than omitting it silently."
    )
    import json as _json
    user_prompt = f"Input: {_json.dumps(structured, ensure_ascii=False)}"

    try:
        providers = iter_llm_providers()
    except RuntimeError:
        raise HTTPException(status_code=502, detail={"error": "summary_unavailable",
                                                     "reason": "No LLM provider configured",
                                                     "retryable": True})
    last_error = "unknown"
    for provider in providers:
        try:
            text = await provider.generate(user_prompt, system_prompt=system_prompt)
            if not text or not text.strip():
                last_error = f"{provider.provider_name} returned empty output"
                continue
            lowered = text.lower()
            if "{" in text or "}" in text or "```" in text:
                last_error = f"{provider.provider_name} returned non-prose output"
                continue
            if any(re.search(p, lowered) for p in PROHIBITED_QUESTION_PATTERNS):
                last_error = f"{provider.provider_name} output violated scope ban"
                continue
            return CaseSummaryResponse(
                summary=text.strip()[:2000],
                provider=provider.provider_name,
                generated_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:  # noqa: BLE001 - try next provider in chain
            last_error = str(e)[:200]
            continue
    raise HTTPException(status_code=502, detail={"error": "summary_unavailable",
                                                 "reason": f"All providers failed: {last_error}",
                                                 "retryable": True})
