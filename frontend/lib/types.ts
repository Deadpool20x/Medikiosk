export interface DocumentField {
  type: "prescription" | "lab_report" | "other";
  extracted_value: string | null;
  confidence: number;
  source: "ocr" | "voice" | "manual";
  provider: "gemini" | "groq" | "sarvam";
  needs_review: boolean;
  manually_corrected: boolean;
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
  chief_complaint: string | null;
  history_of_present_illness: HistoryOfPresentIllness;
  documents: DocumentField[];
  doctor_review: DoctorReview;
}

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  retryable?: boolean;
}
