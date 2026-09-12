import {
  Patient,
  StartSessionResponse,
  ConsentResponse,
  PatientCodeResponse,
  AnswerResponse,
  SessionResponse,
  Session,
  EmergencyItem,
  UploadResponse,
  DocumentCorrectionRequest,
  TokenResponse,
  QueueItem,
  DoctorSessionPatch,
} from "./types";

// Base URL is read safely from public env var with fallback
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface HealthCheckResponse {
  status: string;
}

/**
 * Robust JSON response handler that extracts detailed clinical or validation error
 * messages from FastAPI response payloads (e.g. detail, reason, error) instead of
 * exposing raw opaque HTTP codes to the user.
 */
async function handleResponse<T>(response: Response, defaultMessage: string): Promise<T> {
  if (!response.ok) {
    let detail = `${defaultMessage}: HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) {
        detail = typeof body.detail === "string" ? body.detail : (body.detail.reason || JSON.stringify(body.detail));
      } else if (body?.error) {
        detail = String(body.error);
      }
    } catch {
      // keep fallback message
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function checkBackendHealth(): Promise<HealthCheckResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  return handleResponse<HealthCheckResponse>(response, "Health check failed");
}

export async function startPatientSession(
  patient: Patient,
  language: string = "en",
  visit_type: string = "new",
  adaptive: boolean = true
): Promise<StartSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/session/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ patient, language, visit_type, adaptive }),
  });

  return handleResponse<StartSessionResponse>(response, "Failed to start patient session");
}

export async function submitConsent(sessionId: string): Promise<ConsentResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/consent`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ consent_given: true }),
  });

  return handleResponse<ConsentResponse>(response, "Failed to record consent");
}

export async function getPatientCode(sessionId: string): Promise<PatientCodeResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/patient-code`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  return handleResponse<PatientCodeResponse>(response, "Failed to generate patient code");
}

export async function submitAnswer(sessionId: string, answer: string): Promise<AnswerResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/answer`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ answer }),
  });

  return handleResponse<AnswerResponse>(response, "Failed to submit interview answer");
}

export async function getEmergencySessions(): Promise<EmergencyItem[]> {
  const response = await fetch(`${API_BASE_URL}/doctor/emergency`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  return handleResponse<EmergencyItem[]>(response, "Failed to load emergency dashboard");
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  return handleResponse<SessionResponse>(response, "Failed to retrieve intake session");
}

export async function completeDocumentIntake(sessionId: string): Promise<ConsentResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/documents-complete`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  return handleResponse<ConsentResponse>(response, "Failed to finalize document step");
}

export async function uploadDocument(sessionId: string, file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/upload`, {
    method: "POST",
    body: form,
  });

  return handleResponse<UploadResponse>(response, "Document upload failed");
}

export async function correctDocument(
  sessionId: string,
  index: number,
  payload: DocumentCorrectionRequest
): Promise<SessionResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/document/${index}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return handleResponse<SessionResponse>(response, "Failed to save prescription correction");
}

export async function requestToken(sessionId: string): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  return handleResponse<TokenResponse>(response, "Failed to issue queue token");
}

export async function getDoctorQueue(department?: string): Promise<QueueItem[]> {
  const qs = department ? `?department=${encodeURIComponent(department)}` : "";
  const response = await fetch(`${API_BASE_URL}/doctor/queue${qs}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });

  return handleResponse<QueueItem[]>(response, "Failed to load department queue");
}

export async function getDoctorSession(sessionId: string): Promise<Session> {
  const response = await fetch(`${API_BASE_URL}/doctor/session/${sessionId}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });

  return handleResponse<Session>(response, "Failed to load clinical case detail");
}

export async function patchDoctorSession(sessionId: string, patch: DoctorSessionPatch): Promise<Session> {
  const response = await fetch(`${API_BASE_URL}/doctor/session/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });

  return handleResponse<Session>(response, "Failed to update clinical case");
}

export async function correctDoctorDocument(
  sessionId: string,
  index: number,
  payload: DocumentCorrectionRequest
): Promise<Session> {
  const response = await fetch(`${API_BASE_URL}/doctor/session/${sessionId}/document/${index}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  return handleResponse<Session>(response, "Failed to save document correction");
}
