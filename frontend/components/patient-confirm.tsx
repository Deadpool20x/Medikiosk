"use client";

import { useState } from "react";
import type { Session, DocumentField } from "@/lib/types";
import { requestToken } from "@/lib/api";

interface PatientConfirmProps {
  session: Session;
  sessionId: string;
  patientCode?: string;
  onReset: () => void;
  onBackToRecords?: () => void;
  onTokenGenerated?: (token: string, department: string) => void;
}

export default function PatientConfirm({ session, sessionId, patientCode, onReset, onBackToRecords, onTokenGenerated }: PatientConfirmProps) {
  const [tokenLoading, setTokenLoading] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);

  async function handleConfirm() {
    if (!sessionId) return;
    setTokenLoading(true);
    setTokenError(null);
    try {
      const resp = await requestToken(sessionId);
      onTokenGenerated?.(resp.token, resp.department || "General Medicine");
    } catch (e) {
      setTokenError((e as Error).message || "Failed to generate token.");
    } finally {
      setTokenLoading(false);
    }
  }

  const hpi = session.history_of_present_illness;
  const docs = session.documents ?? [];

  return (
    <div className="mk-p07">
      <div className="mk-p07-content">
        <span className="mk-p07-eyebrow">CASE REVIEW</span>
        <h1 className="mk-p07-h1">Review your information before meeting the doctor</h1>
        <p className="mk-p07-sub">
          Please check that your symptoms, health history, and uploaded records are recorded accurately. You can edit any section before finalizing.
        </p>

        <div className="mk-p07-card">
          {/* Section 1: Chief Complaint & Symptoms */}
          <section className="mk-p07-section">
            <div className="mk-p07-section__head">
              <div className="mk-p07-section__title-row">
                <svg className="mk-p07-section__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3" /><path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4" /><circle cx="20" cy="10" r="2" /></svg>
                <h2 className="mk-p07-section__title">Chief Complaint &amp; Symptoms</h2>
              </div>
              <button type="button" className="mk-p07-btn mk-p07-btn--pill" onClick={() => onReset?.()}>
                <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                Edit
              </button>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Primary Concern</span>
              <div className="mk-p07-grid__value mk-p07-grid__value--bold">
                {session.chief_complaint || "Not provided"}
              </div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Duration &amp; Progression</span>
              <div className="mk-p07-grid__value">
                {hpi?.onset || "Not specified"}
                {hpi?.duration ? ` for ${hpi.duration}` : ""}
                {hpi?.severity ? ` — Severity: ${hpi.severity}` : ""}
                {hpi?.character ? `, ${hpi.character}` : ""}
              </div>
            </div>
            <div className="mk-p07-provenance">
              <span className="mk-p07-provenance__dot" />
              Patient Interview • Recorded by MediKiosk Assistant
            </div>
          </section>

          <div className="mk-p07-divider" />

          {/* Section 2: Medical & Health History */}
          <section className="mk-p07-section">
            <div className="mk-p07-section__head">
              <div className="mk-p07-section__title-row">
                <svg className="mk-p07-section__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 6v14" /><path d="M8 10h8" /><rect x="3" y="3" width="18" height="18" rx="3" /></svg>
                <h2 className="mk-p07-section__title">Medical &amp; Health History</h2>
              </div>
              <button type="button" className="mk-p07-btn mk-p07-btn--pill" onClick={() => onReset?.()}>
                <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                Edit
              </button>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Past Conditions</span>
              <div className="mk-p07-grid__value">
                {hpi?.associated_symptoms && hpi.associated_symptoms.length > 0
                  ? hpi.associated_symptoms.join(", ")
                  : "None reported"}
              </div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Historical Medication</span>
              <div className="mk-p07-grid__value-row">
                {docs.length > 0 ? (
                  <>
                    <span className="mk-p07-grid__value">
                      {docs.map((f: DocumentField) => f.extracted_value || `${f.strength || ""} ${f.dose || ""}`.trim()).filter(Boolean).join(", ") || "None"}
                    </span>
                    <span className="mk-p07-provenance-chip">From uploaded document</span>
                  </>
                ) : (
                  <span className="mk-p07-grid__value">None</span>
                )}
              </div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Known Allergies</span>
              <div className="mk-p07-grid__value">No known drug or food allergies reported</div>
            </div>
            <div className="mk-p07-provenance">
              <span className="mk-p07-provenance__dot" />
              Patient Interview (Conditions &amp; Allergies)
            </div>
          </section>

          <div className="mk-p07-divider" />

          {/* Section 3: Ayurvedic Assessment */}
          <section className="mk-p07-section">
            <div className="mk-p07-section__head mk-p07-section__head--tight">
              <div className="mk-p07-section__title-row">
                <svg className="mk-p07-section__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
                <h2 className="mk-p07-section__title">Ayurvedic Assessment</h2>
              </div>
              <button type="button" className="mk-p07-btn mk-p07-btn--pill" onClick={() => onReset?.()}>
                <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                Edit
              </button>
            </div>
            <p className="mk-p07-section__desc">
              Patient-reported intake responses recorded for the doctor&apos;s review. This is not an interpretation or assessment made by MediKiosk.
            </p>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Prakriti</span>
              <div className="mk-p07-grid__value">Not collected</div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Agni</span>
              <div className="mk-p07-grid__value">Not collected</div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Koshtha</span>
              <div className="mk-p07-grid__value">Not collected</div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Nidana</span>
              <div className="mk-p07-grid__value">Not collected</div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Ahara / Vihara</span>
              <div className="mk-p07-grid__value">Not collected</div>
            </div>
          </section>

          <div className="mk-p07-divider" />

          {/* Section 4: Uploaded Document & Extracted Records */}
          <section className="mk-p07-section">
            <div className="mk-p07-section__head">
              <div className="mk-p07-section__title-row">
                <svg className="mk-p07-section__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
                <h2 className="mk-p07-section__title">Uploaded Document &amp; Extracted Records</h2>
              </div>
              <button type="button" className="mk-p07-btn mk-p07-btn--pill" onClick={onBackToRecords}>
                <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                Edit
              </button>
            </div>
            {docs.length > 0 ? (
              <>
                <div className="mk-p07-doc-badge">
                  <div className="mk-p07-doc-badge__icon">
                    <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
                  </div>
                  <div className="mk-p07-doc-badge__meta">
                    <p className="mk-p07-doc-badge__name">
                      {docs[0].type === "prescription" ? "Prescription" : docs[0].type === "lab_report" ? "Lab Report" : "Uploaded Document"}
                    </p>
                    <p className="mk-p07-doc-badge__detail">Attached document</p>
                  </div>
                  <div className="mk-p07-doc-badge__status">
                    <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
                    Attached
                  </div>
                </div>
                <div className="mk-p07-doc-fields">
                  {docs.map((f: DocumentField, i: number) => (
                    <div key={i} className="mk-p07-grid">
                      <span className="mk-p07-grid__label">
                        {f.type === "prescription" ? "Medication" : f.type === "lab_report" ? "Lab Result" : "Field"}
                      </span>
                      <div className="mk-p07-grid__value">
                        {f.extracted_value || `${f.strength || ""} ${f.dose || ""} ${f.frequency || ""}`.trim() || "No value"}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mk-p07-provenance-row">
                  <span className="mk-p07-provenance-chip">
                    <span className="mk-p07-provenance-chip__dot" />
                    From uploaded document
                  </span>
                  {docs.some((f) => f.confidence > 0.8) && (
                    <span className="mk-p07-confidence-chip">High confidence</span>
                  )}
                </div>
              </>
            ) : (
              <div className="mk-p07-empty-state">
                <p>No documents uploaded yet</p>
              </div>
            )}
          </section>
        </div>

        <div className="mk-p07-notice">
          <svg className="mk-p07-notice__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></svg>
          <p>MediKiosk organizes your medical history for your doctor. It does not diagnose conditions, interpret clinical significance, or prescribe treatments. Your doctor will review and confirm all details with you during consultation.</p>
        </div>

        <div className="mk-p07-actions">
          <button type="button" className="mk-p07-btn mk-p07-btn--secondary" onClick={onBackToRecords}>
            <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
            Back to Records
          </button>
          <button
            type="button"
            className="mk-p07-btn mk-p07-btn--primary"
            onClick={handleConfirm}
            disabled={tokenLoading}
          >
            {tokenLoading ? "Generating..." : "Confirm & Generate Token"}
            {!tokenLoading && <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>}
          </button>
        </div>

        {tokenError && (
          <p className="mk-p07-error" role="alert">{tokenError}</p>
        )}

        <div className="mk-p07-footer-stamp">
          <p>MediKiosk OPD Assistant • MediKiosk Patient Intake</p>
        </div>
      </div>
    </div>
  );
}
