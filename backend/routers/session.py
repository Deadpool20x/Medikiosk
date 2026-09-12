from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import io
import uuid
import secrets
from datetime import datetime, timezone
from backend.models.schema import Session, Patient, DoctorReview, DocumentField, HistoryOfPresentIllness, AnswerRecord
from backend.db import get_session as db_get_session, save_session as db_save_session, init_db, next_queue_token
import os
from backend.rules.adaptive_interview import (
    ALL_DOMAINS,
    MAX_ADAPTIVE_QUESTIONS,
    classify_presentation_domain,
    extract_mentioned_documents,
    extract_concepts_from_payload,
    extract_concepts_from_text,
    extract_denied_concepts,
    find_concept_conflicts,
    select_next_question,
    evaluate_conversational_sufficiency,
    evaluate_sufficiency,
    bridge_concepts_to_legacy,
    get_presentation_profile,
    get_domain_knowledge,
    get_fallback_question,
    validate_llm_proposal,
    build_conversation_context,
    DOMAIN_GENERAL,
)
from backend.rules.interview_rules import get_next_question, get_field_value, REQUIRED_FIELDS_ORDER
from backend.rules.safety_rules import evaluate_safety
from backend.rules.department_rules import classify_department, DEPARTMENT_TOKEN_PREFIX
from backend.services.llm_provider import (
    extract_case,
    extract_field,
    get_llm_provider,
    iter_llm_providers,
    generate_adaptive_turn,
    correct_adaptive_turn,
    AdaptiveTurnProposal,
)
from backend.services.ocr_provider import run_document_ocr, OCRUnavailableError, OCR_CONFIDENCE_THRESHOLD
from backend.services.documents import correct_document
from PIL import Image

router = APIRouter(prefix="/session", tags=["session"])

ALLOWED_DOC_MIME = {
    "image/jpeg", "image/png", "image/webp", "image/gif", "image/tiff",
}
MAX_DOC_BYTES = 8 * 1024 * 1024  # 8 MB

_MIME_TO_FORMAT = {
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/tiff": "tiff",
}


def _detect_image_format(data: bytes) -> Optional[str]:
    """Magic-byte detection so content-type claims are not trusted blindly."""
    if data[:3] == b"\xff\xd8\xff":  # JPEG
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":  # PNG
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):  # GIF
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":  # WebP
        return "webp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):  # TIFF
        return "tiff"
    return None


def _looks_like_image(data: bytes) -> bool:
    return _detect_image_format(data) is not None


def _is_valid_image(data: bytes, mime: str) -> bool:
    """Full integrity check: declared MIME matches magic bytes AND Pillow can
    decode the whole payload. Magic bytes alone accept corrupt/truncated files,
    so Pillow is the authority here."""
    if _detect_image_format(data) != _MIME_TO_FORMAT.get(mime):
        return False
    try:
        img = Image.open(io.BytesIO(data))
        try:
            img.verify()  # structural check
        finally:
            img.close()
        with Image.open(io.BytesIO(data)) as img2:
            img2.load()  # full decode: rejects truncated/corrupt bodies
        return True
    except Exception:  # noqa: BLE001 - any decode failure is an invalid upload
        return False

def _concept_from_step(step: str) -> str:
    """Map the legacy interview_step name to the adaptive concept key.
    All profiles ask primary_symptom as their first question, which is
    presented to the legacy fields as chief_complaint."""
    if step == "chief_complaint":
        return "primary_symptom"
    return step


def _usable_concept_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return any(_usable_concept_value(v) for v in value)
    if isinstance(value, dict):
        return any(_usable_concept_value(v) for v in value.values())
    return True


def _select_pending(session: Session) -> Optional[Dict[str, Any]]:
    """Deterministic next-question selection (engine authority)."""
    if session.interview_complete or session.safety_flagged:
        return None
    return select_next_question(session)


def _next_question_text(session: Session) -> Optional[str]:
    if session.interview_complete or session.safety_flagged:
        return None
    if getattr(session, "adaptive", False):
        if getattr(session, "current_pending_question", None):
            return session.current_pending_question
        fallback = get_fallback_question(session)
        return fallback["text"]
    pending = _select_pending(session)
    return pending["question_text"] if pending else None


def _interview_status(session: Session) -> str:
    if session.safety_flagged:
        return "safety_flagged"
    if session.interview_complete:
        return "complete"
    return "in_progress"


class StartSessionRequest(BaseModel):
    patient: Patient
    language: str = Field(default="en")
    visit_type: str = Field(default="new")
    adaptive: Optional[bool] = Field(default=None)

class StartSessionResponse(BaseModel):
    session_id: str

class ConsentRequest(BaseModel):
    consent_given: bool = True

class ConsentResponse(BaseModel):
    status: str
    detail: str

class PatientCodeResponse(BaseModel):
    patient_code: str

class AnswerRequest(BaseModel):
    answer: str = Field(..., max_length=5000)

class AnswerResponse(BaseModel):
    next_question: Optional[str]
    session_complete: bool
    red_flag: bool = False
    needs_review: bool = False
    presentation_domain: Optional[str] = None
    interview_status: str = "in_progress"
    questions_asked: int = 0
    adaptive_question_limit: int = MAX_ADAPTIVE_QUESTIONS
    mentioned_documents: List[str] = Field(default_factory=list)
    denied_concepts: List[str] = Field(default_factory=list)

class UploadResponse(BaseModel):
    extracted_value: Optional[str] = None
    confidence: float
    needs_review: bool
    medicine: Optional[str] = None
    strength: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None
    message: Optional[str] = None

class DocumentCorrectionRequest(BaseModel):
    corrected_value: Optional[str] = None
    strength: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None

class StatusResponse(BaseModel):
    ready_for_review: bool

class TokenResponse(BaseModel):
    token: str
    department: str

class SessionResponse(BaseModel):
    session_id: str
    patient: Patient
    language: str
    visit_type: str
    consent_given: bool
    patient_code: Optional[str]
    interview_step: str
    interview_complete: bool
    document_intake_done: bool = False
    chief_complaint: Optional[str]
    history_of_present_illness: Dict[str, Any]
    documents: list
    doctor_review: Dict[str, Any]
    answer_records: list
    raw_answers: list
    next_question: Optional[str] = None
    safety_flagged: bool = False
    safety_flag_time: Optional[str] = None
    safety_detail: List[str] = Field(default_factory=list)
    department: Optional[str] = None
    queue_token: Optional[str] = None
    presentation_domain: Optional[str] = None
    collected_concepts: Dict[str, Any] = Field(default_factory=dict)
    asked_questions: List[str] = Field(default_factory=list)
    adaptive_question_count: int = 0
    mentioned_documents: List[str] = Field(default_factory=list)
    denied_concepts: List[str] = Field(default_factory=list)
    interview_status: str = "in_progress"
    adaptive_question_limit: int = MAX_ADAPTIVE_QUESTIONS

@router.post("/start", response_model=StartSessionResponse)
async def start_session(payload: StartSessionRequest):
    session_id = str(uuid.uuid4())
    use_adaptive = True
    if payload.adaptive is False:
        use_adaptive = False

    session = Session(
        session_id=session_id,
        patient=payload.patient,
        language=payload.language,
        visit_type=payload.visit_type,
        consent_given=False,
        patient_code=None,
        interview_step="chief_complaint",
        interview_complete=False,
        chief_complaint=None,
        history_of_present_illness=HistoryOfPresentIllness(),
        documents=[],
        doctor_review=DoctorReview(),
        answer_records=[],
        raw_answers=[],
        presentation_domain=None,
        collected_concepts={},
        asked_questions=[],
        asked_concepts=[],
        current_pending_question=None,
        adaptive_question_count=0,
        mentioned_documents=[],
        adaptive=use_adaptive,
    )
    if use_adaptive:
        initial_q = get_fallback_question(session, "primary_symptom")
        session.current_pending_question = initial_q["text"]
        session.asked_questions = [initial_q["text"]]
        session.asked_concepts = ["primary_symptom"]
    db_save_session(session)
    return StartSessionResponse(session_id=session_id)

@router.post("/{session_id}/consent", response_model=ConsentResponse)
async def submit_consent(session_id: str, payload: ConsentRequest):
    session = db_get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.consent_given and payload.consent_given:
        # Idempotent: repeated valid call returns success
        return ConsentResponse(status="success", detail="Consent already recorded")

    if not payload.consent_given:
        return ConsentResponse(status="error", detail="Consent must be given")

    session.consent_given = True
    db_save_session(session)
    return ConsentResponse(status="success", detail="Consent recorded")

@router.post("/{session_id}/patient-code", response_model=PatientCodeResponse)
async def get_patient_code(session_id: str):
    session = db_get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.consent_given:
        raise HTTPException(status_code=403, detail="Consent required before patient code")

    if session.safety_flagged:
        raise HTTPException(status_code=403, detail="Safety review required; no code is issued")

    if session.patient_code:
        # Return existing code (generated once, persisted)
        return PatientCodeResponse(patient_code=session.patient_code)

    # Generate patient code: format MK-{8 chars}
    code = f"MK-{secrets.token_hex(4).upper()}"
    session.patient_code = code
    db_save_session(session)
    return PatientCodeResponse(patient_code=code)

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    session = db_get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if getattr(session, "adaptive", False):
        next_question = _next_question_text(session)
    else:
        next_question = get_next_question(session) if not session.interview_complete else None

    return SessionResponse(
        session_id=session.session_id,
        patient=session.patient,
        language=session.language,
        visit_type=session.visit_type,
        consent_given=session.consent_given,
        patient_code=session.patient_code,
        interview_step=session.interview_step,
        interview_complete=session.interview_complete,
        document_intake_done=session.document_intake_done,
        chief_complaint=session.chief_complaint,
        history_of_present_illness=session.history_of_present_illness.model_dump(),
        documents=[doc.model_dump() for doc in session.documents],
        doctor_review=session.doctor_review.model_dump(),
        answer_records=[ar.model_dump(mode="json") for ar in session.answer_records],
        raw_answers=session.raw_answers,
        next_question=next_question,
        safety_flagged=session.safety_flagged,
        safety_flag_time=session.safety_flag_time.isoformat() if session.safety_flag_time else None,
        safety_detail=session.safety_detail,
        department=session.department,
        queue_token=session.queue_token,
        presentation_domain=session.presentation_domain,
        collected_concepts=session.collected_concepts,
        asked_questions=session.asked_questions,
        adaptive_question_count=session.adaptive_question_count,
        mentioned_documents=session.mentioned_documents,
        denied_concepts=session.denied_concepts,
        interview_status=_interview_status(session),
        adaptive_question_limit=get_presentation_profile(session.presentation_domain).max_questions,
    )

@router.post("/{session_id}/answer", response_model=AnswerResponse)
async def submit_answer(session_id: str, payload: AnswerRequest):
    session = db_get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.consent_given:
        raise HTTPException(status_code=403, detail="Consent required before answering")

    if not session.patient_code:
        raise HTTPException(status_code=403, detail="Patient code required before answering")

    if session.safety_flagged:
        return AnswerResponse(next_question=None, session_complete=session.interview_complete, red_flag=True, interview_status="safety_flagged")

    safety = evaluate_safety(payload.answer, session)
    if safety.flagged:
        session.safety_flagged = True
        session.safety_flag_time = datetime.now(timezone.utc)
        session.safety_detail = safety.matched_terms

        raw_answer_record = {
            "field": session.interview_step,
            "answer": payload.answer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "red_flag": True,
        }
        session.raw_answers.append(raw_answer_record)
        db_save_session(session)
        return AnswerResponse(next_question=None, session_complete=session.interview_complete, red_flag=True, interview_status="safety_flagged")

    if session.interview_complete:
        return AnswerResponse(next_question=None, session_complete=True, interview_status="complete")

    current_field = session.interview_step

    raw_answer_record = {
        "field": current_field,
        "answer": payload.answer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "red_flag": False,
    }
    session.raw_answers.append(raw_answer_record)

    if not getattr(session, "adaptive", True):
        # Legacy sequential progression
        extracted_data = None
        provider_used = None
        confidence = None
        needs_review = False

        try:
            primary = get_llm_provider()
            try:
                extracted_data = await extract_field(primary, current_field, payload.answer)
                provider_used = primary.provider_name
                confidence = extracted_data.get("confidence", 0.8) if isinstance(extracted_data, dict) else 0.8
            except Exception:
                chain = [p for p in iter_llm_providers() if p is not primary]
                for fallback in chain:
                    try:
                        extracted_data = await extract_field(fallback, current_field, payload.answer)
                        provider_used = fallback.provider_name
                        if isinstance(extracted_data, dict) and "confidence" in extracted_data:
                            confidence = min(extracted_data["confidence"], 0.7)
                        else:
                            confidence = 0.7
                        break
                    except Exception:
                        continue
                if extracted_data is None:
                    needs_review = True
        except Exception:
            needs_review = True

        if extracted_data and isinstance(extracted_data, dict):
            if current_field == "chief_complaint":
                field_value = extracted_data.get("complaint")
                if field_value and str(field_value).strip():
                    session.chief_complaint = str(field_value).strip()
                else:
                    session.chief_complaint = payload.answer
                    needs_review = True
            elif current_field == "onset":
                field_value = extracted_data.get("onset")
                if field_value and str(field_value).strip():
                    session.history_of_present_illness.onset = str(field_value).strip()
                else:
                    session.history_of_present_illness.onset = payload.answer
                    needs_review = True
            elif current_field == "duration":
                field_value = extracted_data.get("duration")
                if field_value and str(field_value).strip():
                    session.history_of_present_illness.duration = str(field_value).strip()
                else:
                    session.history_of_present_illness.duration = payload.answer
                    needs_review = True
            elif current_field == "severity":
                field_value = extracted_data.get("severity")
                if field_value and str(field_value).strip():
                    session.history_of_present_illness.severity = str(field_value).strip()
                else:
                    session.history_of_present_illness.severity = payload.answer
                    needs_review = True
            elif current_field == "character":
                field_value = extracted_data.get("character")
                if field_value and str(field_value).strip():
                    session.history_of_present_illness.character = str(field_value).strip()
                else:
                    session.history_of_present_illness.character = payload.answer
                    needs_review = True
            elif current_field == "associated_symptoms":
                field_value = extracted_data.get("associated_symptoms")
                if field_value and isinstance(field_value, list) and len(field_value) > 0 and any(s for s in field_value if s and str(s).strip()):
                    session.history_of_present_illness.associated_symptoms = [str(s).strip() for s in field_value if s and str(s).strip()]
                elif field_value and isinstance(field_value, str) and field_value.strip():
                    symptoms = [s.strip() for s in field_value.split(",") if s.strip()]
                    session.history_of_present_illness.associated_symptoms = symptoms if symptoms else [field_value.strip()]
                else:
                    session.history_of_present_illness.associated_symptoms = [payload.answer]
                    needs_review = True
        else:
            needs_review = True
            if current_field == "chief_complaint":
                session.chief_complaint = payload.answer
            elif current_field == "onset":
                session.history_of_present_illness.onset = payload.answer
            elif current_field == "duration":
                session.history_of_present_illness.duration = payload.answer
            elif current_field == "severity":
                session.history_of_present_illness.severity = payload.answer
            elif current_field == "character":
                session.history_of_present_illness.character = payload.answer
            elif current_field == "associated_symptoms":
                session.history_of_present_illness.associated_symptoms = [payload.answer]

        answer_record = AnswerRecord(
            question=current_field,
            answer=payload.answer,
            provider=provider_used,
            confidence=confidence,
            needs_review=needs_review,
        )
        session.answer_records.append(answer_record)

        next_field = None
        for field in REQUIRED_FIELDS_ORDER:
            if get_field_value(session, field) is None:
                next_field = field
                break

        if next_field:
            session.interview_step = next_field
            session.interview_complete = False
        else:
            session.interview_complete = True
            session.interview_step = "complete"

        db_save_session(session)
        next_question = get_next_question(session) if not session.interview_complete else None
        return AnswerResponse(
            next_question=next_question,
            session_complete=session.interview_complete,
            red_flag=False,
            needs_review=needs_review,
            interview_status="complete" if session.interview_complete else "in_progress",
        )

    # ── Adaptive Conversational Interviewer Execution Path ─────────────────
    if session.asked_concepts:
        current_concept = session.asked_concepts[-1]
    else:
        current_concept = "primary_symptom"

    provider_used = None
    confidence = 0.85
    needs_review = False
    new_question_text = None
    new_target_concept = None

    # ── 10-Stage Turn Pipeline (Phase 1.7 Conversational Reliability) ──
    # Stage 1: Safety precheck already passed above

    # Stage 2: Language-aware normalization, denied concepts & extraction
    denied_this_turn = extract_denied_concepts(payload.answer)
    for d in denied_this_turn:
        if d not in session.denied_concepts:
            session.denied_concepts.append(d)

    # Heuristic free-text extraction for resilience
    text_concepts = extract_concepts_from_text(payload.answer, domain=session.presentation_domain)

    # Stage 3: Formulate bounded context (including denied concepts)
    context = build_conversation_context(session, payload.answer)

    # Stage 4: LLM next-question generation
    llm_result = None
    try:
        llm_result = await generate_adaptive_turn(context)
        provider_used = llm_result.get("provider")
        confidence = llm_result.get("confidence", 0.85)
    except Exception:
        # Fallback to extract_case if mocked in legacy tests
        try:
            legacy_case = await extract_case(payload.answer, current_concept, session.presentation_domain)
            llm_result = {
                "case_update": {
                    "presentation": legacy_case.get("domain"),
                    "concepts": legacy_case.get("concepts", {}),
                    "denied_concepts": [],
                    "mentioned_documents": legacy_case.get("mentioned_documents", []),
                },
                "next_question": None,
                "status": "continue",
                "confidence": legacy_case.get("confidence", 0.8),
                "provider": legacy_case.get("provider"),
            }
            provider_used = legacy_case.get("provider")
            confidence = legacy_case.get("confidence", 0.8)
        except Exception:
            needs_review = True

    # Structured case-state concepts & domain update
    concepts: Dict[str, Any] = {}
    extracted_domain = None
    mentioned: List[str] = []

    if llm_result and isinstance(llm_result, dict):
        case_up = llm_result.get("case_update") or {}
        extracted_concepts = case_up.get("concepts") or {}
        concepts = {k: v for k, v in extracted_concepts.items() if _usable_concept_value(v)}
        extracted_domain = case_up.get("presentation")
        mentioned = [str(d) for d in (case_up.get("mentioned_documents") or []) if d and str(d).strip()]
        for d in case_up.get("denied_concepts") or []:
            if d and d not in session.denied_concepts:
                session.denied_concepts.append(d)

    # Blend heuristic extraction where LLM missed
    for hk, hv in text_concepts.items():
        if _usable_concept_value(hv) and not _usable_concept_value(concepts.get(hk)):
            concepts[hk] = hv

    # Clinical Meaning Conflict Check
    conflicts = find_concept_conflicts(concepts, payload.answer, session.collected_concepts, session.denied_concepts)
    if conflicts:
        needs_review = True
        # Purge conflicting concepts so invalid extractions (e.g. jaw pain from stomach burning) are not persisted
        sanitized_concepts = {}
        for ck, cv in concepts.items():
            if not any(f"'{ck}'" in conf for conf in conflicts):
                sanitized_concepts[ck] = cv
        concepts = sanitized_concepts

    # Normalization
    if "complaint" in concepts and "primary_symptom" not in concepts:
        concepts["primary_symptom"] = concepts["complaint"]
    if "primary_symptom" in concepts and "chief_complaint" not in concepts:
        concepts["chief_complaint"] = concepts["primary_symptom"]

    # Ensure current concept is captured if answered
    if _usable_concept_value(payload.answer) and not _usable_concept_value(concepts.get(current_concept)):
        concepts[current_concept] = payload.answer.strip()
        if not llm_result:
            needs_review = True

    # Presentation domain update
    if extracted_domain in ALL_DOMAINS and (not session.presentation_domain or session.presentation_domain == DOMAIN_GENERAL):
        session.presentation_domain = extracted_domain
    elif not session.presentation_domain or session.presentation_domain == DOMAIN_GENERAL:
        detected = classify_presentation_domain(f"{payload.answer} {session.chief_complaint or ''}")
        if detected != DOMAIN_GENERAL:
            session.presentation_domain = detected

    # Update collected concepts in session
    for c_k, c_v in concepts.items():
        if _usable_concept_value(c_v):
            session.collected_concepts[c_k] = c_v

    # Documents
    doc_matches = extract_mentioned_documents(payload.answer)
    session.mentioned_documents = list(dict.fromkeys([*(session.mentioned_documents or []), *mentioned, *doc_matches]))

    # Stage 5: Deterministic Validator
    validation = None
    is_valid = False
    llm_status = llm_result.get("status", "continue") if llm_result else None

    if llm_result and isinstance(llm_result, dict):
        from types import SimpleNamespace
        next_q_data = llm_result.get("next_question")
        dummy_prop = SimpleNamespace(
            case_update=SimpleNamespace(concepts=concepts),
            next_question=SimpleNamespace(**next_q_data) if next_q_data else None,
            status=llm_status,
        )
        validation = validate_llm_proposal(dummy_prop, session, session.presentation_domain)
        if validation.valid and dummy_prop.next_question:
            is_valid = True
            new_question_text = dummy_prop.next_question.text
            new_target_concept = dummy_prop.next_question.target_concept
        elif validation.valid and dummy_prop.status == "sufficient":
            is_valid = True
        elif not validation.valid:
            # Stage 6: One Bounded LLM Self-Correction
            try:
                corrected_result = await correct_adaptive_turn(
                    session_context=context,
                    validation_reasons=validation.reasons,
                    recovery_hint=validation.recovery_hint,
                )
                if corrected_result and isinstance(corrected_result, dict):
                    corr_next_q = corrected_result.get("next_question")
                    corr_status = corrected_result.get("status", "continue")
                    corr_prop = SimpleNamespace(
                        case_update=SimpleNamespace(concepts=concepts),
                        next_question=SimpleNamespace(**corr_next_q) if corr_next_q else None,
                        status=corr_status,
                    )
                    # Stage 7: Validate corrected proposal
                    corr_val = validate_llm_proposal(corr_prop, session, session.presentation_domain)
                    if corr_val.valid and corr_prop.next_question:
                        is_valid = True
                        new_question_text = corr_prop.next_question.text
                        new_target_concept = corr_prop.next_question.target_concept
                        llm_status = corr_status
                        provider_used = corrected_result.get("provider", provider_used)
                    elif corr_val.valid and corr_prop.status == "sufficient":
                        is_valid = True
                        llm_status = "sufficient"
                    else:
                        needs_review = True
                else:
                    needs_review = True
            except Exception:
                needs_review = True

    # Stage 8: Sufficiency evaluation or human fallback
    session.adaptive_question_count += 1
    is_sufficient = evaluate_conversational_sufficiency(session, llm_status)

    if is_sufficient or session.adaptive_question_count >= MAX_ADAPTIVE_QUESTIONS:
        session.interview_complete = True
        session.interview_step = "complete"
        session.current_pending_question = None
        new_question_text = None
    else:
        if not is_valid or not new_question_text:
            # Stage 8: Human-written deterministic fallback
            fallback = get_fallback_question(session)
            new_question_text = fallback["text"]
            new_target_concept = fallback["target_concept"]
            needs_review = True

        session.interview_complete = False
        session.interview_step = new_target_concept
        session.current_pending_question = new_question_text
        session.asked_questions.append(new_question_text)
        session.asked_concepts.append(new_target_concept)

    # Stage 9: Persist state & bridge to legacy schema
    bridge_concepts_to_legacy(session)

    answer_record = AnswerRecord(
        question=current_concept,
        answer=payload.answer,
        provider=provider_used,
        confidence=confidence,
        needs_review=needs_review,
    )
    session.answer_records.append(answer_record)

    db_save_session(session)

    # Stage 10: Return question response
    return AnswerResponse(
        next_question=new_question_text,
        session_complete=session.interview_complete,
        red_flag=False,
        needs_review=needs_review,
        presentation_domain=session.presentation_domain,
        interview_status=_interview_status(session),
        questions_asked=session.adaptive_question_count,
        adaptive_question_limit=MAX_ADAPTIVE_QUESTIONS,
        mentioned_documents=session.mentioned_documents,
    )

@router.post("/{session_id}/upload", response_model=UploadResponse)
async def upload_document(session_id: str, file: UploadFile = File(...)):
    session = db_get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.safety_flagged:
        raise HTTPException(status_code=403, detail="Safety review required before document upload")

    if not session.consent_given:
        raise HTTPException(status_code=403, detail="Consent required before upload")

    if not session.patient_code:
        raise HTTPException(status_code=403, detail="Patient code required before upload")

    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_DOC_MIME:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload an image (JPEG, PNG, WEBP, GIF, or TIFF).")

    content = await file.read(MAX_DOC_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > MAX_DOC_BYTES:
        raise HTTPException(status_code=413, detail="The uploaded file is too large (maximum 8 MB).")
    if not _is_valid_image(content, mime):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid image.")

    try:
        extraction, provider_name, raw_json = await run_document_ocr(content, mime)
    except OCRUnavailableError:
        doc = DocumentField(
            type="prescription",
            extracted_value=None,
            confidence=0.0,
            source="ocr",
            provider="unknown",
            needs_review=True,
        )
        session.documents.append(doc)
        db_save_session(session)
        return UploadResponse(
            extracted_value=None,
            confidence=0.0,
            needs_review=True,
            message="We could not analyze this document right now. Please try again with a clearer photo.",
        )

    medicine = (extraction.medicine or "").strip() or None
    needs_review = (medicine is None) or (extraction.confidence < OCR_CONFIDENCE_THRESHOLD)

    doc = DocumentField(
        type="prescription",
        extracted_value=medicine,
        strength=extraction.strength,
        dose=extraction.dose,
        frequency=extraction.frequency,
        confidence=extraction.confidence,
        source="ocr",
        provider=provider_name,
        needs_review=needs_review,
        raw_result=raw_json,
    )
    session.documents.append(doc)
    db_save_session(session)

    return UploadResponse(
        extracted_value=medicine,
        confidence=extraction.confidence,
        needs_review=needs_review,
        medicine=medicine,
        strength=extraction.strength,
        dose=extraction.dose,
        frequency=extraction.frequency,
    )

@router.patch("/{session_id}/document/{index}", response_model=DocumentField)
async def correct_patient_document(session_id: str, index: int, payload: DocumentCorrectionRequest):
    session = db_get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        doc = correct_document(
            session, index,
            corrected_value=payload.corrected_value,
            strength=payload.strength,
            dose=payload.dose,
            frequency=payload.frequency,
        )
    except IndexError:
        raise HTTPException(status_code=404, detail="Document not found")
    db_save_session(session)
    return doc

@router.get("/{session_id}/status", response_model=StatusResponse)
async def get_session_status(session_id: str):
    session = db_get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return StatusResponse(ready_for_review=not session.doctor_review.confirmed)

@router.post("/{session_id}/documents-complete", response_model=ConsentResponse)
async def complete_documents_step(session_id: str):
    """Record that the patient has explicitly passed through the P06 document
    intake (uploaded and continued, or skipped). Persisted so a refresh can
    never silently skip P06: tokens are withheld until this step is recorded.
    """
    session = db_get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.interview_complete:
        raise HTTPException(
            status_code=403,
            detail={"error": "incomplete_interview",
                    "reason": "Interview not complete; please finish the questions first."}
        )
    if session.document_intake_done:
        return ConsentResponse(status="success", detail="Document step already complete")
    session.document_intake_done = True
    try:
        db_save_session(session)
    except Exception:
        # If persisting fails, we must NOT advance the patient; revert the flag
        session.document_intake_done = False
        raise HTTPException(status_code=500, detail="Failed to persist document step")
    return ConsentResponse(status="success", detail="Document step complete")

@router.post("/{session_id}/token", response_model=TokenResponse)
async def generate_queue_token(session_id: str):
    """Issue the department queue token exactly once, idempotently.

    Eligibility: completed interview, not safety-flagged, no document waiting
    on review. Returns the persisted token + department on success. 403 with a
    machine-readable ``reason`` (incomplete_session / safety_flagged /
    pending_review) when the session is not yet eligible.
    """
    session = db_get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.safety_flagged:
        raise HTTPException(
            status_code=403,
            detail={"error": "safety_flagged",
                    "reason": "Safety review required; call +91 00000 00000."}
        )
    if not session.interview_complete:
        raise HTTPException(
            status_code=403,
            detail={"error": "incomplete_session",
                    "reason": "Interview not complete; please finish the questions first."}
        )
    if not session.document_intake_done:
        raise HTTPException(
            status_code=403,
            detail={"error": "incomplete_document_step",
                    "reason": "Please finish the document step before continuing."}
        )
    if any(doc.needs_review for doc in session.documents):
        raise HTTPException(
            status_code=403,
            detail={"error": "pending_review",
                    "reason": "One or more documents need review before a token can be issued."}
        )

    if session.queue_token:
        return TokenResponse(token=session.queue_token, department=session.department or "")

    department = classify_department(session)
    prefix = DEPARTMENT_TOKEN_PREFIX.get(department, "KY")
    token = next_queue_token(prefix)
    session.department = department
    session.queue_token = token
    db_save_session(session)
    return TokenResponse(token=token, department=department)