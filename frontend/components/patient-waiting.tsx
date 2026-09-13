"use client";

import { useEffect, useState } from "react";
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

export function PatientWaiting({
  session,
  onBackToRecords,
}: {
  session: Session;
  onBackToRecords: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="mk-p09">
      <header className="mk-p09-header">
        <div className="mk-p09-header__inner">
          <div className="mk-p09-brand">
            <div className="mk-p09-brand__logo" aria-hidden="true">
              <svg fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" viewBox="0 0 24 24">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </div>
            <div className="mk-p09-brand__name">
              <span>MediKiosk</span>
              <span className="mk-p09-brand__tag">OPD</span>
            </div>
          </div>
          <nav className="mk-p09-nav" aria-label="Progress">
            {[
              { label: "Language", state: "done" as const },
              { label: "Consent", state: "done" as const },
              { label: "Patient", state: "done" as const },
              { label: "Interview", state: "done" as const },
              { label: "Records", state: "done" as const },
              { label: "Summary", state: "done" as const },
              { label: "Token", state: "done" as const },
              { label: "Waiting", state: "active" as const },
            ].map((s) => (
              <span
                key={s.label}
                className={`mk-p09-nav__pill ${s.state === "active" ? "mk-p09-nav__pill--active" : ""} ${s.state === "done" ? "mk-p09-nav__pill--done" : ""}`}
              >
                {s.label}
              </span>
            ))}
          </nav>
          <div className="mk-p09-header__spacer" aria-hidden="true" />
        </div>
      </header>

      <main className="mk-p09-main">
        <div className="mk-p09-title">
          <span className="mk-p09-eyebrow">WAITING FOR CONSULTATION</span>
          <h1 className="mk-p09-h1">Your intake is complete</h1>
          <p className="mk-p09-sub">
            Please wait for your token to be called. You are now in the queue for your selected department.
          </p>
        </div>

        <div className="mk-p09-card">
          {/* Token Information */}
          <div className="mk-p09-token-info">
            <div className="mk-p09-token-info__label">Your Token</div>
            <div className="mk-p09-token-info__value">{session.queue_token || "—"}</div>
          </div>

          {/* Department Information */}
          <div className="mk-p09-department-info">
            <div className="mk-p09-department-info__label">Assigned Department</div>
            <div className="mk-p09-department-info__value">{label(session.department)}</div>
            {session.department && (
              <p className="mk-p09-department-info__description">{deptDescription(session.department)}</p>
            )}
          </div>

          {/* Patient Code */}
          <div className="mk-p09-patient-code">
            <div className="mk-p09-patient-code__label">Patient Code</div>
            <div className="mk-p09-patient-code__value">{session.patient_code || "—"}</div>
          </div>

          {/* Instructions */}
          <div className="mk-p09-instructions">
            <p className="mk-p09-instructions__title">What happens next?</p>
            <p className="mk-p09-instructions__body">
              When it is your turn, your token number will be displayed on the department screen and announced.
              Please keep your patient code and token handy for your consultation.
            </p>
          </div>
        </div>

        {/* Assistance Area */}
        <div className="mk-p09-assistance">
          <div className="mk-p09-assistance__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="8" />
            </svg>
          </div>
          <div>
            <p className="mk-p09-assistance__title">Need Help?</p>
            <p className="mk-p09-assistance__body">
              If you require assistance, please press the help button or approach the reception desk.
            </p>
          </div>
        </div>

        {/* Action Area */}
        <div className="mk-p09-actions">
          <button
            type="button"
            className="mk-p09-btn mk-p09-btn--secondary"
            onClick={onBackToRecords}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
            </svg>
            Back to Records
          </button>
        </div>

        {/* Footer */}
        <div className="mk-p09-footer">
          MediKiosk OPD Assistant • MediKiosk Patient Intake
        </div>
      </main>
    </div>
  );
}