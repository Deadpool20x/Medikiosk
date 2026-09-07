from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional
import uuid
from backend.models.schema import Session, Patient, DoctorReview, DocumentField
from backend.db import get_session, save_session
from backend.rules.interview_rules import get_next_question

router = APIRouter(prefix="/session", tags=["session"])

class StartSessionRequest(BaseModel):
    patient: Patient

class StartSessionResponse(BaseModel):
    session_id: str
    next_question: str

class AnswerRequest(BaseModel):
    answer: str

class AnswerResponse(BaseModel):
    next_question: Optional[str]
    session_complete: bool

class UploadResponse(BaseModel):
    extracted_value: Optional[str] = None
    confidence: float
    needs_review: bool

class StatusResponse(BaseModel):
    ready_for_review: bool

@router.post("/start", response_model=StartSessionResponse)
async def start_session(payload: StartSessionRequest):
    session_id = str(uuid.uuid4())
    session = Session(session_id=session_id, patient=payload.patient)
    save_session(session)
    next_q = get_next_question(session) or ""
    return StartSessionResponse(session_id=session_id, next_question=next_q)

@router.post("/{session_id}/answer", response_model=AnswerResponse)
async def submit_answer(session_id: str, payload: AnswerRequest):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Placeholder for extraction in Day 2
    next_q = get_next_question(session)
    return AnswerResponse(next_question=next_q, session_complete=(next_q is None))

@router.post("/{session_id}/upload", response_model=UploadResponse)
async def upload_document(session_id: str, file: UploadFile = File(...)):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Placeholder for OCR in Day 4
    return UploadResponse(extracted_value=None, confidence=0.0, needs_review=True)

@router.get("/{session_id}/status", response_model=StatusResponse)
async def get_session_status(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return StatusResponse(ready_for_review=not session.doctor_review.confirmed)
