export interface AnswerRecord {
  question: string;
  answer: string;
  timestamp: string;
  provider: string | null;
  confidence: number | null;
  needs_review: boolean;
}

export interface DocumentField {
  type: "prescription" | "lab_report" | "other";
  extracted_value: string | null;
  strength: string | null;
  dose: string | null;
  frequency: string | null;
  confidence: number;
  source: "ocr" | "voice" | "manual";
  provider: "gemini" | "groq" | "sarvam" | "unknown";
  needs_review: boolean;
  manually_corrected: boolean;
  original_extraction: { medicine: string | null; strength: string | null; dose: string | null; frequency: string | null } | null;
  raw_result: Record<string, unknown> | null;
}

export interface Patient {
  name: string;
  age: number;
  gender: string;
}

export interface HistoryOfPresentIllness {
  onset: string | null;
  duration: string | null;
  character: string | null;
  severity: string | null;
  associated_symptoms: string[];
}

export interface DoctorReview {
  edited: boolean;
  confirmed: boolean;
}

export interface Session {
  session_id: string;
  patient: Patient;
  language: string;
  visit_type: string;
  consent_given: boolean;
  patient_code: string | null;
  interview_step: string;
  interview_complete: boolean;
  document_intake_done: boolean;
  chief_complaint: string | null;
  history_of_present_illness: HistoryOfPresentIllness;
  documents: DocumentField[];
  doctor_review: DoctorReview;
  answer_records: AnswerRecord[];
  raw_answers: Array<{ field: string; answer: string; timestamp: string; red_flag: boolean }>;
  next_question: string | null;
  safety_flagged: boolean;
  safety_flag_time: string | null;
  safety_detail: string[];
  department: string | null;
  queue_token: string | null;
}

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  retryable?: boolean;
}

export interface StartSessionRequest {
  patient: Patient;
  language: string;
  visit_type: string;
}

export interface StartSessionResponse {
  session_id: string;
}

export interface ConsentRequest {
  consent_given: boolean;
}

export interface ConsentResponse {
  status: string;
  detail: string;
}

export interface PatientCodeResponse {
  patient_code: string;
}

export interface AnswerRequest {
  answer: string;
}

export interface AnswerResponse {
  next_question: string | null;
  session_complete: boolean;
  red_flag: boolean;
  needs_review: boolean;
  completion_message?: string | null;
}

export interface UploadResponse {
  extracted_value: string | null;
  confidence: number;
  needs_review: boolean;
  medicine: string | null;
  strength: string | null;
  dose: string | null;
  frequency: string | null;
  message: string | null;
}

export interface DocumentCorrectionRequest {
  corrected_value?: string;
  strength?: string;
  dose?: string;
  frequency?: string;
}

export interface SessionResponse extends Session {}

export interface EmergencyItem {
  session_id: string;
  patient_code: string;
  patient_name: string;
  symptom: string;
  reported_at: string;
  status: string;
}

export interface TokenResponse {
  token: string;
  department: string;
}

export interface QueueItem {
  session_id: string;
  patient_code: string;
  patient_name: string;
  chief_complaint: string;
  department: string | null;
  queue_token: string | null;
  confirmed: boolean;
  ready_for_review: boolean;
  check_in_time: string;
}

export interface DoctorSessionPatch {
  chief_complaint?: string;
  onset?: string;
  duration?: string;
  severity?: string;
  character?: string;
  associated_symptoms?: string[];
  doctor_confirmed?: boolean;
}
