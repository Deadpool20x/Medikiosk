from pydantic import BaseModel, Field
from typing import Optional, Literal, List

class MedicineExtraction(BaseModel):
    medicine: Optional[str] = None
    strength: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")

class DocumentField(BaseModel):
    type: Literal["prescription", "lab_report", "other"]
    extracted_value: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0, description="Field confidence score between 0.0 and 1.0")
    source: Literal["ocr", "voice", "manual"]
    provider: Literal["gemini", "groq", "sarvam"]
    needs_review: bool
    manually_corrected: bool = False

class HistoryOfPresentIllness(BaseModel):
    onset: Optional[str] = None
    duration: Optional[str] = None
    character: Optional[str] = None
    severity: Optional[str] = None
    associated_symptoms: List[str] = Field(default_factory=list)

class Patient(BaseModel):
    name: str = Field(..., min_length=1)
    age: int = Field(..., ge=0, le=130)
    gender: str = Field(..., min_length=1)

class DoctorReview(BaseModel):
    edited: bool = False
    confirmed: bool = False

class Session(BaseModel):
    session_id: str
    patient: Patient
    chief_complaint: Optional[str] = None
    history_of_present_illness: HistoryOfPresentIllness = Field(default_factory=HistoryOfPresentIllness)
    documents: List[DocumentField] = Field(default_factory=list)
    doctor_review: DoctorReview = Field(default_factory=DoctorReview)

class HealthResponse(BaseModel):
    status: str = "ok"

class ErrorResponse(BaseModel):
    error: str
    retryable: bool = False
