"use client";

import { useState } from "react";
import type { Session } from "../lib/types";

const DEPT_LABELS: Record<string, string> = {
  Kayachikitsa: "Kayachikitsa OPD",
  Panchakarma: "Panchakarma OPD",
};

function label(department: string | null): string {
  return (department && DEPT_LABELS[department]) || department || "Department not assigned yet";
}

function deptDescription(department: string | null): string {
  if (department === "Kayachikitsa") return "General Ayurvedic Medicine";
  if (department === "Panchakarma") return "Therapeutic Detoxification & Rejuvenation";
  return "";
}

export function PatientToken({
  session,
  onBackToRecords,
  onDone,
}: {
  session: Session;
  onBackToRecords: () => void;
  onDone: () => void;
}) {
  return (
    <div className="mk-p08">
      <header className="mk-p08-header">
        <div className="mk-p08-header__inner">
          <div className="mk-p08-brand">
            <div className="mk-p08-brand__logo" aria-hidden="true">
              <svg fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" viewBox="0 0 24 24">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </div>
            <div className="mk-p08-brand__name">
              <span>MediKiosk</span>
              <span className="mk-p08-brand__tag">OPD</span>
            </div>
          </div>
          <nav className="mk-p08-nav" aria-label="Progress">
            {[
              { label: "Language", state: "done" as const },
              { label: "Consent", state: "done" as const },
              { label: "Patient", state: "done" as const },
              { label: "Interview", state: "done" as const },
              { label: "Records", state: "done" as const },
              { label: "Summary", state: "done" as const },
              { label: "Token", state: "active" as const },
            ].map((s) => (
              <span
                key={s.label}
                className={`mk-p08-nav__pill ${s.state === "active" ? "mk-p08-nav__pill--active" : ""} ${s.state === "done" ? "mk-p08-nav__pill--done" : ""}`}
              >
                {s.label}
              </span>
            ))}
          </nav>
          <div className="mk-p08-header__spacer" aria-hidden="true" />
        </div>
      </header>

      <main className="mk-p08-main">
        <div className="mk-p08-title">
          <span className="mk-p08-eyebrow">CONFIRMATION & QUEUE TOKEN</span>
          <h1 className="mk-p08-h1">Your information is confirmed</h1>
          <p className="mk-p08-sub">
            Your intake details have been recorded for your consultation. Please take note of your token number below.
          </p>
        </div>

        <div className="mk-p08-card">
          {/* Verified Success State Pill */}
          <div className="mk-p08-success-pill">
            <span className="mk-p08-success-pill__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p08-success-pill__icon" aria-hidden="true">
                <path d="M9 11l3 3L22 4" />
              </svg>
            </span>
            <span className="mk-p08-success-pill__text">Intake Complete</span>
          </div>

          {/* Department Assigned */}
          <div className="mk-p08-department">
            <span className="mk-p08-department__label">Assigned OPD Department</span>
            <div className="mk-p08-department__value">{label(session.department)}</div>
            {session.department && (
              <p className="mk-p08-department__description">{deptDescription(session.department)}</p>
            )}
          </div>

          {/* Large Queue Token Callout Box */}
          <div className="mk-p08-token-box">
            <span className="mk-p08-token-box__label">DEPARTMENT QUEUE TOKEN</span>
            <div className="mk-p08-token-box__value">{session.queue_token || "—"}</div>
            <span className="mk-p08-token-box__subtext">Position in department queue</span>
          </div>

          {/* Differentiated Patient Code Strip */}
          <div className="mk-p08-patient-code-strip">
            <div className="mk-p08-patient-code-strip__left">
              <span className="mk-p08-patient-code-strip__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p08-patient-code-strip__icon" aria-hidden="true">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2 2z" />
                </svg>
              </span>
              <div>
                <div className="mk-p08-patient-code-strip__label">Patient Code:</div>
                <span className="mk-p08-patient-code-strip__value">{session.patient_code || "—"}</span>
              </div>
            </div>
            <p className="mk-p08-patient-code-strip__note">
              Identifies your MediKiosk record throughout your visit
            </p>
          </div>
        </div>

        {/* Clear Patient Guidance Note */}
        <div className="mk-p08-guidance">
          <p className="mk-p08-guidance__title">Please wait for your token to be called.</p>
          <p className="mk-p08-guidance__body">
            Your token number will be announced and displayed on the department screen. Keep your patient code and token handy for your consultation.
          </p>
        </div>

        <div className="mk-p08-actions">
          <button
            type="button"
            className="mk-p08-btn mk-p08-btn--secondary"
            onClick={onBackToRecords}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
            </svg>
            Back to Records
          </button>
          <button
            type="button"
            className="mk-p08-btn mk-p08-btn--primary"
            onClick={onDone}
          >
            Done / View Waiting Screen
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p08-btn__icon" aria-hidden="true">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        <div className="mk-p08-footer">
          MediKiosk OPD Assistant • MediKiosk Patient Intake
        </div>
      </main>
    </div>
  );
}