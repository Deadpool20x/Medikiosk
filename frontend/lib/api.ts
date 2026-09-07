import { Patient } from "./types";

// Base URL is read safely from public env var with fallback
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface HealthCheckResponse {
  status: string;
}

export interface StartSessionResponse {
  session_id: string;
  next_question: string;
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

export async function startPatientSession(patient: Patient): Promise<StartSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/session/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ patient }),
  });

  if (!response.ok) {
    throw new Error(`Failed to start session: HTTP ${response.status}`);
  }

  return response.json();
}
