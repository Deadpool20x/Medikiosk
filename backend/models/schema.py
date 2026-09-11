from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime, timezone

class AnswerRecord(BaseModel):
    question: str
    answer: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider: Optional[str] = Field(default=None)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    needs_review: bool = Field(default=False)

class MedicineExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medicine: Optional[str] = None
    strength: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")

class DocumentField(BaseModel):
    type: Literal["prescription", "lab_report", "other"]
    extracted_value: Optional[str] = None
    strength: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0, description="Field confidence score between 0.0 and 1.0")
    source: Literal["ocr", "voice", "manual"]
    provider: Literal["gemini", "groq", "sarvam", "unknown"]
    needs_review: bool
    manually_corrected: bool = Field(default=False)
    original_extraction: Optional[Dict[str, Any]] = Field(default=None)
    raw_result: Optional[Dict[str, Any]] = Field(default=None)

class HistoryOfPresentIllness(BaseModel):
    onset: Optional[str] = Field(default=None)
    duration: Optional[str] = Field(default=None)
    character: Optional[str] = Field(default=None)
    severity: Optional[str] = Field(default=None)
    associated_symptoms: List[str] = Field(default_factory=list)

class Patient(BaseModel):
    name: str = Field(..., min_length=1)
    age: int = Field(..., ge=0, le=130)
    gender: str = Field(..., min_length=1)

class DoctorReview(BaseModel):
    edited: bool = Field(default=False)
    confirmed: bool = Field(default=False)

class Session(BaseModel):
    session_id: str
    patient: Patient
    language: str = Field(default="en")
    visit_type: str = Field(default="new")
    consent_given: bool = Field(default=False)
    patient_code: Optional[str] = Field(default=None)
    interview_step: str = Field(default="chief_complaint")
    interview_complete: bool = Field(default=False)
    document_intake_done: bool = Field(default=False)
    chief_complaint: Optional[str] = Field(default=None)
    history_of_present_illness: HistoryOfPresentIllness = Field(default_factory=HistoryOfPresentIllness)
    documents: List[DocumentField] = Field(default_factory=list)
    doctor_review: DoctorReview = Field(default_factory=DoctorReview)
    answer_records: List[AnswerRecord] = Field(default_factory=list)
    raw_answers: List[Dict[str, Any]] = Field(default_factory=list)
    safety_flagged: bool = Field(default=False)
    safety_flag_time: Optional[datetime] = Field(default=None)
    safety_detail: List[str] = Field(default_factory=list)
    department: Optional[str] = Field(default=None)
    queue_token: Optional[str] = Field(default=None)

class HealthResponse(BaseModel):
    status: str = "ok"

class ErrorResponse(BaseModel):
    error: str
    retryable: bool = False
