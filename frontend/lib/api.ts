import { Patient, StartSessionResponse, ConsentResponse, PatientCodeResponse, AnswerResponse, SessionResponse, Session, EmergencyItem, UploadResponse, DocumentCorrectionRequest, TokenResponse, QueueItem, DoctorSessionPatch } from "./types";

// Base URL is read safely from public env var with fallback
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface HealthCheckResponse {
  status: string;
}

export async function checkBackendHealth(): Promise<HealthCheckResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Health check failed with HTTP status ${response.status}`);
  }

  return response.json();
}

export async function startPatientSession(patient: Patient, language: string = "en", visit_type: string = "new"): Promise<StartSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/session/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ patient, language, visit_type }),
  });

  if (!response.ok) {
    throw new Error(`Failed to start session: HTTP ${response.status}`);
  }

  return response.json();
}

export async function submitConsent(sessionId: string): Promise<ConsentResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/consent`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ consent_given: true }),
  });

  if (!response.ok) {
    throw new Error(`Failed to submit consent: HTTP ${response.status}`);
  }

  return response.json();
}

export async function getPatientCode(sessionId: string): Promise<PatientCodeResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/patient-code`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get patient code: HTTP ${response.status}`);
  }

  return response.json();
}

export async function submitAnswer(sessionId: string, answer: string): Promise<AnswerResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/answer`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ answer }),
  });

  if (!response.ok) {
    throw new Error(`Failed to submit answer: HTTP ${response.status}`);
  }

  return response.json();
}

export async function getEmergencySessions(): Promise<EmergencyItem[]> {
  const response = await fetch(`${API_BASE_URL}/doctor/emergency`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to get emergency sessions: HTTP ${response.status}`);
  }

  return response.json();
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to get session: HTTP ${response.status}`);
  }

  return response.json();
}

export async function completeDocumentIntake(sessionId: string): Promise<ConsentResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/documents-complete`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to record document step: HTTP ${response.status}`);
  }

  return response.json();
}

export async function uploadDocument(sessionId: string, file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/upload`, {
    method: "POST",
    body: form,
  });

  if (!response.ok) {
    let detail = `Upload failed: HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      // keep default message
    }
    throw new Error(detail);
  }

  return response.json();
}

export async function correctDocument(sessionId: string, index: number, payload: DocumentCorrectionRequest): Promise<SessionResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/document/${index}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Failed to save correction: HTTP ${response.status}`);
  }

  return response.json();
}

export async function requestToken(sessionId: string): Promise<TokenResponse> {
  const response = await fetch(`${API_BASE_URL}/session/${sessionId}/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (response.status === 403) {
    const body = await response.json();
    throw new Error(body?.detail?.reason || `Token not available: HTTP ${response.status}`);
  }
  if (!response.ok) {
    throw new Error(`Failed to issue token: HTTP ${response.status}`);
  }

  return response.json();
}

export async function getDoctorQueue(department?: string): Promise<QueueItem[]> {
  const qs = department ? `?department=${encodeURIComponent(department)}` : "";
  const response = await fetch(`${API_BASE_URL}/doctor/queue${qs}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to load department queue: HTTP ${response.status}`);
  }

  return response.json();
}

export async function getDoctorSession(sessionId: string): Promise<Session> {
  const response = await fetch(`${API_BASE_URL}/doctor/session/${sessionId}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to load case: HTTP ${response.status}`);
  }

  return response.json();
}

export async function patchDoctorSession(sessionId: string, patch: DoctorSessionPatch): Promise<Session> {
  const response = await fetch(`${API_BASE_URL}/doctor/session/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });

  if (!response.ok) {
    throw new Error(`Failed to save case: HTTP ${response.status}`);
  }

  return response.json();
}

export async function correctDoctorDocument(sessionId: string, index: number, payload: DocumentCorrectionRequest): Promise<Session> {
  const response = await fetch(`${API_BASE_URL}/doctor/session/${sessionId}/document/${index}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Failed to save document correction: HTTP ${response.status}`);
  }

  return response.json();
}
