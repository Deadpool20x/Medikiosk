from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from backend.models.schema import Session
from backend.db import get_session, save_session, list_sessions

router = APIRouter(prefix="/doctor", tags=["doctor"])

class SessionSummary(BaseModel):
    session_id: str
    patient_name: str
    ready_for_review: bool

class SessionPatchRequest(BaseModel):
    chief_complaint: Optional[str] = None
    doctor_confirmed: Optional[bool] = None

@router.get("/sessions", response_model=List[SessionSummary])
async def get_doctor_sessions():
    sessions = list_sessions()
    return [SessionSummary(**s) for s in sessions]

@router.get("/session/{session_id}", response_model=Session)
async def get_doctor_session(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.patch("/session/{session_id}", response_model=Session)
async def patch_doctor_session(session_id: str, patch_data: SessionPatchRequest):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if patch_data.chief_complaint is not None:
        session.chief_complaint = patch_data.chief_complaint
        session.doctor_review.edited = True
    if patch_data.doctor_confirmed is not None:
        session.doctor_review.confirmed = patch_data.doctor_confirmed
    
    save_session(session)
    return session
