"use client";

import { useEffect, useState } from "react";
import { getSession } from "../lib/api";

export function SummaryReview({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSession() {
      try {
        setLoading(true);
        setError(null);
        const data = await getSession(sessionId);
        setSession(data);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load session summary"
        );
      } finally {
        setLoading(false);
      }
    }

    loadSession();
  }, [sessionId]);

  if (loading) {
    return (
      <div className="mk-summary-loading">
        <div className="mk-doc-spinner" aria-hidden="true" />
        <p className="mk-summary-loading__title">Preparing your summary…</p>
        <p className="mk-summary-loading__sub">
          Organizing your information for review
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mk-error-banner" role="alert">
        <p>{error}</p>
        <button
          type="button"
          className="mk-button mk-button--secondary"
          onClick={() => window.location.reload()}
        >
          Try again
        </button>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="mk-summary-empty">
        <p className="mk-summary-empty__title">No session data found</p>
        <p className="mk-summary-empty__sub">
          Please start a new session to begin your consultation
        </p>
      </div>
    );
  }

  return (
    <div className="mk-summary-card">
      <div className="mk-summary-header">
        <h1 className="mk-summary-title">Your Consultation Summary</h1>
        <p className="mk-summary-subtitle">
          Please review the information below before submitting
        </p>
      </div>

      <div className="mk-summary-section">
        <h2 className="mk-section-title">Patient Information</h2>
        <div className="mk-info-grid">
          <div className="mk-info-row">
            <span className="mk-info-label">Name</span>
            <span className="mk-info-value">
              {session.patient.name}
            </span>
          </div>
          <div className="mk-info-row">
            <span className="mk-info-label">Age</span>
            <span className="mk-info-value">
              {session.patient.age}
            </span>
          </div>
          <div className="mk-info-row">
            <span className="mk-info-label">Gender</span>
            <span className="mk-info-value">
              {session.patient.gender}
            </span>
          </div>
          <div className="mk-info-row">
            <span className="mk-info-label">Language</span>
            <span className="mk-info-value">
              {session.language}
            </span>
          </div>
          <div className="mk-info-row">
            <span className="mk-info-label">Visit Type</span>
            <span className="mk-info-value">
              {session.visit_type}
            </span>
          </div>
        </div>
      </div>

      <div className="mk-summary-section">
        <h2 className="mk-section-title">Consultation Details</h2>
        <div className="mk-info-grid">
          <div className="mk-info-row">
            <span className="mk-info-label">Chief Complaint</span>
            <span className="mk-info-value">
              {session.chief_complaint || "Not provided"}
            </span>
          </div>
          <div className="mk-info-row">
            <span className="mk-info-label">Onset</span>
            <span className="mk-info-value">
              {session.history_of_present_illness.onset || "Not specified"}
            </span>
          </div>
          <div className="mk-info-row">
            <span className="mk-info-label">Duration</span>
            <span className="mk-info-value">
              {session.history_of_present_illness.duration || "Not specified"}
            </span>
          </div>
          <div className="mk-info-row">
            <span className="mk-info-label">Severity</span>
            <span className="mk-info-value">
              {session.history_of_present_illness.severity || "Not specified"}
            </span>
          </div>
          <div className="mk-info-row">
            <span className="mk-info-label">Character</span>
            <span className="mk-info-value">
              {session.history_of_present_illness.character || "Not specified"}
            </span>
          </div>
          <div className="mk-info-row">
            <span className="mk-info-label">Associated Symptoms</span>
            <span className="mk-info-value">
              {session.history_of_present_illness.associated_symptoms.length > 0
                ? session.history_of_present_illness.associated_symptoms.join(
                    ", "
                  )
                : "None reported"}
            </span>
          </div>
        </div>
      </div>

      {session.documents.length > 0 && (
        <div className="mk-summary-section">
          <h2 className="mk-section-title">Documents Uploaded</h2>
          <div className="mk-documents-list">
            {session.documents.map((doc: any, index: number) => (
              <div key={index} className="mk-doc-item">
                <div className="mk-doc-item__header">
                  <span className="mk-doc-item__type">
                    {doc.type === "prescription"
                      ? "Prescription"
                      : doc.type === "lab_report"
                      ? "Lab Report"
                      : "Other Document"}
                  </span>
                  {doc.needs_review && (
                    <span className="mk-doc-badge mk-doc-badge--low">
                      Review needed
                    </span>
                  )}
                </div>
                <div className="mk-doc-item__details">
                  <div className="mk-doc-item__field">
                    <span className="mk-doc-item__label">Medicine</span>
                    <span className="mk-doc-item__value">
                      {doc.extracted_value || "Not detected"}
                    </span>
                  </div>
                  <div className="mk-doc-item__field">
                    <span className="mk-doc-item__label">Strength</span>
                    <span className="mk-doc-item__value">
                      {doc.strength || "Not specified"}
                    </span>
                  </div>
                  <div className="mk-doc-item__field">
                    <span className="mk-doc-item__label">Dose</span>
                    <span className="mk-doc-item__value">
                      {doc.dose || "Not specified"}
                    </span>
                  </div>
                  <div className="mk-doc-item__field">
                    <span className="mk-doc-item__label">Frequency</span>
                    <span className="mk-doc-item__value">
                      {doc.frequency || "Not specified"}
                    </span>
                  </div>
                  <div className="mk-doc-item__field">
                    <span className="mk-doc-item__label">Confidence</span>
                    <span className={`mk-doc-confidence ${
                      doc.confidence >= 0.5
                        ? "mk-doc-confidence--high"
                        : "mk-doc-confidence--low"
                    }`}>
                      {Math.round(doc.confidence * 100)}%
                    </span>
                  </div>
                  <div className="mk-doc-item__field">
                    <span className="mk-doc-item__label">Source</span>
                    <span className="mk-doc-item__value">
                      {doc.source === "ocr"
                        ? "AI Extraction"
                        : doc.source === "manual"
                        ? "Manual Correction"
                        : doc.source}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mk-summary-section">
        <h2 className="mk-section-title">Answers Provided</h2>
        {session.answer_records.length > 0 ? (
          <div className="mk-answers-list">
            {session.answer_records.map((answer: any, index: number) => (
              <div key={index} className="mk-answer-item">
                <div className="mk-answer-item__question">
                  <strong>{answer.question}</strong>
                </div>
                <div className="mk-answer-item__answer">
                  {answer.answer}
                </div>
                {answer.provider && answer.confidence !== null && (
                  <div className="mk-answer-item__meta">
                    <span className="mk-answer-item__provider">
                      {answer.provider.toUpperCase()}
                    </span>
                    <span className="mk-answer-item__confidence">
                      {Math.round(answer.confidence * 100)}% confidence
                    </span>
                    {answer.needs_review && (
                      <span className="mk-answer-item__needs-review">
                        Review suggested
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="mk-summary-empty">
            No detailed answers recorded
          </p>
        )}
      </div>

      <div className="mk-summary-actions">
        <button
          type="button"
          className="mk-button mk-button--secondary"
          onClick={() => {
            // In a real app, this would navigate back to interview for edits
            window.history.back();
          }}
        >
          ← Back to Interview
        </button>
        <button
          type="button"
          className="mk-button mk-button--primary"
          onClick={() => {
            // Navigate to confirmation/token step
            window.location.href = `/patient/confirmation?sessionId=${sessionId}`;
          }}
        >
          Submit for Review →
        </button>
      </div>
    </div>
  );
}