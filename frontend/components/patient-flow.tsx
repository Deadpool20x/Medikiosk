"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactElement } from "react";
import { useRouter } from "next/navigation";
import {
  startPatientSession,
  submitConsent,
  getPatientCode,
  submitAnswer,
  getSession,
  completeDocumentIntake,
  triggerEmergency,
} from "../lib/api";
import type { Patient, Session as SessionType } from "../lib/types";
import { DocumentUpload } from "./document-upload";
import PatientConfirm from "./patient-confirm";

const SESSION_KEY = "medikiosk_session_id";

function MediKioskLogo() {
  return (
    <svg viewBox="0 0 40 40" fill="none" className="w-8 h-8" aria-hidden="true">
      <rect width="40" height="40" rx="10" fill="#2563EB" />
      <path d="M20 10v20M10 20h20" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" />
    </svg>
  );
}

function EmergencyHelpButton({ onHelp }: { onHelp: () => void }) {
  return (
    <button
      type="button"
      onClick={onHelp}
      className="mk-emergency-btn"
      aria-label="Request immediate emergency medical assistance"
      style={{
        backgroundColor: "#DC2626",
        color: "#FFFFFF",
        fontWeight: 700,
        padding: "8px 14px",
        borderRadius: "8px",
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        fontSize: "13px",
        cursor: "pointer",
        border: "1px solid #B91C1C",
        boxShadow: "0 2px 4px rgba(220, 38, 38, 0.25)",
      }}
    >
      <span style={{ fontSize: "15px" }} aria-hidden="true">🚨</span> Need Help Now
    </button>
  );
}

type Screen = "welcome" | "consent" | "code" | "interview" | "documents" | "summary" | "safety" | "waiting";

export function PatientFlow() {
  const [screen, setScreen] = useState<Screen>("welcome");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<SessionType | null>(null);
  const [reactQuestion, setReactQuestion] = useState<string | null>(null);
  const [completionMessage, setCompletionMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [patientCode, setPatientCode] = useState<string | null>(null);

  // P01 form state
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("male");
  // P01 preferred language handoff: seed from sessionStorage so the sessions
  // created by POST /session/start carry the language chosen on the landing page.
  const [language, setLanguage] = useState(() =>
    typeof window !== "undefined" ? window.sessionStorage.getItem("medikiosk_preferred_language") || "en" : "en"
  );
  const [visitType, setVisitType] = useState("new");
  const [consentChecked, setConsentChecked] = useState(false);
  const router = useRouter();

  // P04 interview state
  const [answerInput, setAnswerInput] = useState("");
  const [chat, setChat] = useState<Array<{ q: string; a: string }>>([]);
  const [redFlag, setRedFlag] = useState(false);

  // P08 token state
  const [tokenData, setTokenData] = useState<{ token: string; department: string } | null>(null);

  // Frontend mirrors of backend field ids/labels (matches backend rules/interview_rules.py).
  // Backend is authoritative for the actual question string (`session.next_question`).
  const FIELD_LABELS: Array<{ id: string; label: string }> = [
    { id: "chief_complaint", label: "Chief Complaint" },
    { id: "onset", label: "Onset" },
    { id: "duration", label: "Duration" },
    { id: "severity", label: "Severity" },
    { id: "character", label: "Character" },
    { id: "associated_symptoms", label: "Associated Symptoms" },
  ];
  const CURRENT_FIELD_ID = session?.interview_step ?? "";
  const CURRENT_STEP_LABEL =
    FIELD_LABELS.find((f) => f.id === CURRENT_FIELD_ID)?.label ?? "Interview";
  const ANSWERED_COUNT = session
    ? FIELD_LABELS.filter((f) => {
        if (f.id === "chief_complaint") return !!session.chief_complaint;
        if (f.id === "associated_symptoms")
          return (session.history_of_present_illness.associated_symptoms?.length ?? 0) > 0;
        const v = (session.history_of_present_illness as unknown as Record<string, unknown>)[f.id];
        return typeof v === "string" && v.trim().length > 0;
      }).length
    : 0;
  const TOTAL_STEPS = FIELD_LABELS.length;

  // Restore session on refresh from sessionStorage
  useEffect(() => {
    const sid = window.sessionStorage.getItem(SESSION_KEY);
    if (!sid) return;
    (async () => {
      try {
        const s = await getSession(sid);
        setSessionId(sid);
        setSession(s);
        if (s.safety_flagged) {
          setScreen("safety");
          setRedFlag(true);
          return;
        }
        if (window.sessionStorage.getItem("medikiosk_waiting") === "1" && s.queue_token) {
          setTokenData({ token: s.queue_token as string, department: s.department ?? "" });
          setScreen("waiting");
          return;
        }
        // Backend is authoritative: only show the P07 summary once the P06
        // document step has actually been completed. Otherwise resume at P06.
        setScreen(s.interview_complete ? (s.document_intake_done ? "summary" : "documents") : screenForSession(s));
        if (s.consent_given && s.patient_code) {
          setPatientCode(s.patient_code);
        }
        if (s.answer_records.length > 0) {
          const qs = interviewHistory(s);
          setChat(qs);
          setReactQuestion(s.next_question);
        } else {
          setReactQuestion(s.next_question);
        }
      } catch {
        // session no longer valid; start fresh
        window.sessionStorage.removeItem(SESSION_KEY);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function screenForSession(s: SessionType): Screen {
    if (!s.consent_given) return "consent";
    // P03: the persisted code is shown again before the interview starts. Once
    // any answer exists the interview can resume directly at P04.
    if (s.answer_records.length === 0) return "code";
    return "interview";
  }

  function interviewHistory(s: SessionType) {
    return s.answer_records.map((r) => ({ q: r.question, a: r.answer }));
  }

  const canStart = useMemo(
    () => name.trim().length > 0 && age !== "" && Number(age) >= 0 && Number(age) <= 130,
    [name, age]
  );

  async function handleStart() {
    setError(null);
    setLoading(true);
    try {
      const patient: Patient = { name: name.trim(), age: Number(age), gender };
      const res = await startPatientSession(patient, language, visitType);
      setSessionId(res.session_id);
      window.sessionStorage.setItem(SESSION_KEY, res.session_id);
      setScreen("consent");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleConsent() {
    if (!sessionId) return;
    setError(null);
    setLoading(true);
    try {
      await submitConsent(sessionId);
      setScreen("code");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerateCode() {
    if (!sessionId) return;
    setError(null);
    setLoading(true);
    try {
      const res = await getPatientCode(sessionId);
      setPatientCode(res.patient_code);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleEnterInterview() {
    if (!sessionId) return;
    setError(null);
    setLoading(true);
    try {
      const s = await getSession(sessionId);
      setSession(s);
      setReactQuestion(s.next_question);
      setScreen("interview");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  // P03: fetch/share the persisted code as soon as the screen opens so the code
  // is actually displayed (it is never regenerated — the backend returns the
  // existing persisted code idempotently).
  useEffect(() => {
    if (screen !== "code" || !sessionId || patientCode) return;
    let cancelled = false;
    setLoading(true);
    getPatientCode(sessionId)
      .then((res) => {
        if (!cancelled) setPatientCode(res.patient_code);
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [screen, sessionId, patientCode]);

  async function handleAnswer() {
    if (!sessionId || !answerInput.trim()) return;
    setError(null);
    setLoading(true);
    try {
      const qText = reactQuestion || "Answer";
      const res = await submitAnswer(sessionId, answerInput.trim());
      setChat((prev) => [...prev, { q: qText, a: answerInput.trim() }]);
      setAnswerInput("");
      // Update session immediately so progress indicator and step chip advance without refresh
      try {
        const s = await getSession(sessionId);
        setSession(s);
      } catch {
        // best effort
      }
      if (res.red_flag) {
        setRedFlag(true);
        setScreen("safety");
        return;
      }
      if (res.session_complete) {
        if (res.completion_message) {
          setCompletionMessage(res.completion_message);
        }
        setScreen("documents");
        return;
      }
      if (res.next_question) {
        setReactQuestion(res.next_question);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleEmergencyAlert() {
    try {
      if (sessionId) {
        await triggerEmergency(sessionId);
      }
    } catch {
      // Prioritize client safety view transition
    }
    setRedFlag(true);
    setScreen("safety");
  }




  function handleSafetyReset() {
    window.sessionStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    setSession(null);
    setPatientCode(null);
    setRedFlag(false);
    setChat([]);
    setAnswerInput("");
    setTokenData(null);
    window.sessionStorage.removeItem("medikiosk_waiting");
    setScreen("welcome");
  }

  function handleGotoWaiting() {
    setScreen("waiting");
    window.sessionStorage.setItem("medikiosk_waiting", "1");
  }

  async function handleDocumentsDone() {
    if (!sessionId) return;
    try {
      await completeDocumentIntake(sessionId);
      const s = await getSession(sessionId);
      setSession(s);
      if (!s.document_intake_done) {
        setError("Document step was not recorded. Please try again.");
        return;
      }
      setScreen("summary");
    } catch (e) {
      setError((e as Error).message || "Something went wrong. Please try again.");
    }
  }

  if (screen === "consent" && sessionId) {
    const steps: { label: string; state: "done" | "active" | "upcoming" }[] = [
      { label: "Language", state: "done" },
      { label: "Consent", state: "active" },
      { label: "Patient Code", state: "upcoming" },
      { label: "Interview", state: "upcoming" },
      { label: "Records", state: "upcoming" },
      { label: "Summary", state: "upcoming" },
      { label: "Token", state: "upcoming" },
    ];
    const points: { title: string; body: string; icon: ReactElement }[] = [
      {
        title: "Assisting Your Consultation",
        body: "MediKiosk records your health symptoms and Ayurvedic lifestyle history so your Vaidya (doctor) has a clear summary ready before your consultation.",
        icon: (
          <svg className="mk-p02-point__icon" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.5L18 8.5V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ),
      },
      {
        title: "Your information",
        body: "Your responses and health records will be available to your treating doctor as part of your consultation.",
        icon: (
          <svg className="mk-p02-point__icon" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 002 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ),
      },
      {
        title: "Doctor Makes All Decisions",
        body: "MediKiosk helps organize your medical history. It does not diagnose, prescribe medication, or replace doctor advice.",
        icon: (
          <svg className="mk-p02-point__icon" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ),
      },
    ];
    return (
      <div className="mk-p02">
        <header className="mk-p02-header">
          <div className="mk-p02-header__inner">
            <div className="mk-p02-brand">
              <div className="mk-p02-brand__logo">
                <svg fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" viewBox="0 0 24 24">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </div>
              <div className="mk-p02-brand__name">
                <span>MediKiosk</span>
                <span className="mk-p02-brand__tag">OPD</span>
              </div>
            </div>
            <nav className="mk-p02-nav" aria-label="Progress">
              {steps.map((s) => (
                <span
                  key={s.label}
                  className={`mk-p02-nav__pill${s.state === "active" ? " mk-p02-nav__pill--active" : s.state === "done" ? " mk-p02-nav__pill--done" : ""}`}
                >
                  {s.label}
                </span>
              ))}
            </nav>
            <EmergencyHelpButton onHelp={handleEmergencyAlert} />
          </div>
        </header>
        <main className="mk-p02-main">
          <div className="mk-p02-title">
            <span className="mk-p02-eyebrow">CONSENT & PRIVACY</span>
            <h1 className="mk-p02-h1">Patient Consent</h1>
            <p className="mk-p02-sub">
              Please review and agree to the consent details below before proceeding with your intake session.
            </p>
          </div>
          <div className="mk-p02-card">
            <div className="mk-p02-points">
              {points.map((pt) => (
                <div key={pt.title} className="mk-p02-point">
                  <div className="mk-p02-point__box">{pt.icon}</div>
                  <div className="mk-p02-point__text">
                    <h2 className="mk-p02-point__title">{pt.title}</h2>
                    <p className="mk-p02-point__body">{pt.body}</p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mk-p02-agree">
              <label className="mk-p02-agree__label">
                <div className="mk-p02-agree__lead">
                  <input className="mk-p02-agree__check" id="consent-agreement" type="checkbox" checked={consentChecked} onChange={(e) => setConsentChecked(e.target.checked)} />
                  <span className="mk-p02-agree__text">
                    I understand and agree to share my symptom and health history for this pre-consultation intake.
                  </span>
                </div>
                <div className="mk-p02-agree__badge">
                  <svg fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                    <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
              </label>
            </div>
            <div className="mk-p02-actions">
              <button className="mk-p02-btn mk-p02-btn--back" type="button" onClick={() => router.push("/")}>
                ← Back
              </button>
              <button className="mk-p02-btn mk-p02-btn--primary" type="button" onClick={handleConsent} disabled={loading || !consentChecked}>
                {loading ? "Saving…" : "Agree & Continue"}
                <svg className="mk-p02-btn__arrow" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M14 5l7 7m0 0l-7 7m7-7H3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        </main>
        <footer className="mk-p02-footer">
          MediKiosk OPD Assistant • MediKiosk Patient Intake
        </footer>
      </div>
    );
  }

  if (screen === "code" && sessionId) {
    const steps: { label: string; state: "done" | "active" | "upcoming" }[] = [
      { label: "Language", state: "done" },
      { label: "Consent", state: "done" },
      { label: "Patient", state: "active" },
      { label: "Interview", state: "upcoming" },
      { label: "Records", state: "upcoming" },
      { label: "Summary", state: "upcoming" },
      { label: "Token", state: "upcoming" },
    ];
    return (
      <div className="mk-p03">
        <header className="mk-p03-header">
          <div className="mk-p03-header__inner">
            <div className="mk-p03-brand">
              <div className="mk-p03-brand__logo">
                <svg fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" viewBox="0 0 24 24">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </div>
              <div className="mk-p03-brand__name">
                <span>MediKiosk</span>
                <span className="mk-p03-brand__tag">OPD</span>
              </div>
            </div>
            <nav className="mk-p03-nav" aria-label="Progress">
              {steps.map((s) => (
                <span key={s.label} className={`mk-p03-nav__pill ${s.state === "active" ? "mk-p03-nav__pill--active" : ""} ${s.state === "done" ? "mk-p03-nav__pill--done" : ""}`}>
                  {s.label}
                </span>
              ))}
            </nav>
            <EmergencyHelpButton onHelp={handleEmergencyAlert} />
          </div>
        </header>

        <main className="mk-p03-main">
          <div className="mk-p03-title">
            <span className="mk-p03-capsule">
              <span className="mk-p03-capsule__dot" />
              PATIENT IDENTIFICATION
            </span>
            <h1 className="mk-p03-h1">Your Patient Code</h1>
            <p className="mk-p03-sub">
              Your unique intake code has been generated. Please keep this code for your records and future visits.
            </p>
          </div>

          {error && (
            <div className="mk-error-banner" role="alert">{error}</div>
          )}

          <div className="mk-p03-case">
            <div className="mk-p03-code-panel">
              <span className="mk-p03-code-panel__hash" aria-hidden="true">#</span>
              <span className="mk-p03-code-label">Generated Patient Code</span>
              <div className="mk-p03-code-row">
                <span className="mk-p03-code mk-token-number" aria-live="polite">
                  {patientCode ?? "Generating…"}
                </span>
                <button
                  type="button"
                  className="mk-p03-copy"
                  onClick={async () => {
                    if (!patientCode) return;
                    try {
                      await navigator.clipboard.writeText(patientCode);
                      setError(null);
                    } catch {
                      // Clipboard may be unavailable; fall back silently.
                    }
                  }}
                  disabled={!patientCode}
                  title="Copy code"
                  aria-label="Copy patient code"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="mk-p03-copy__icon">
                    <rect x="9" y="9" width="11" height="11" rx="2" />
                    <path d="M5 15V5a2 2 0 0 1 2-2h10" />
                  </svg>
                </button>
              </div>
              <span className="mk-p03-toast" aria-live="polite">
                Code copied to clipboard
              </span>
            </div>

            <div className="mk-p03-save">
              <div className="mk-p03-save__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <h2 className="mk-p03-save__title">Save for Future Visits</h2>
              <p className="mk-p03-save__body">
                Please note or save this code. You will need it to retrieve your MediKiosk intake record and for future visits.
              </p>
            </div>

            <div className="mk-p03-actions">
              <button
                type="button"
                className="mk-p03-btn mk-p03-btn--back"
                onClick={() => setScreen("consent")}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p03-btn__icon">
                  <path d="M19 12H5M12 19l-7-7 7-7" />
                </svg>
                Back
              </button>
              <button
                type="button"
                className="mk-p03-btn mk-p03-btn--primary"
                onClick={handleEnterInterview}
                disabled={loading || !patientCode}
              >
                {loading ? "Continuing…" : "Continue to Interview"}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p03-btn__icon">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        </main>

        <footer className="mk-p03-footer">MediKiosk OPD Assistant • MediKiosk Patient Intake</footer>
      </div>
    );
  }

  if (screen === "interview" && sessionId) {
    return (
      <div className="mk-p04">
        <header className="mk-p04-header">
          <div className="mk-p04-header__inner">
            <div className="mk-p04-brand">
              <div className="mk-p04-brand__logo">
                <svg fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" viewBox="0 0 24 24">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </div>
              <div className="mk-p04-brand__name">
                <span>MediKiosk</span>
                <span className="mk-p04-brand__tag">OPD</span>
              </div>
            </div>
            <nav className="mk-p04-nav" aria-label="Progress">
              {[
                { label: "Language", state: "done" as const },
                { label: "Consent", state: "done" as const },
                { label: "Patient", state: "done" as const },
                { label: "Interview", state: "active" as const },
                { label: "Records", state: "upcoming" as const },
                { label: "Summary", state: "upcoming" as const },
                { label: "Token", state: "upcoming" as const },
              ].map((s) => (
                <span
                  key={s.label}
                  className={`mk-p04-nav__pill ${s.state === "active" ? "mk-p04-nav__pill--active" : ""} ${s.state === "done" ? "mk-p04-nav__pill--done" : ""}`}
                >
                  {s.label}
                </span>
              ))}
            </nav>
            <EmergencyHelpButton onHelp={handleEmergencyAlert} />
          </div>
        </header>

        <main className="mk-p04-main">
          <div className="mk-p04-title">
            <div className="mk-p04-title__row">
              <span className="mk-p04-eyebrow">CLINICAL INTAKE INTERVIEW</span>
              <span className="mk-p04-step-chip">
                <span>{CURRENT_STEP_LABEL}</span>
              </span>
            </div>
            <h1 className="mk-p04-h1">
              {reactQuestion || "Please answer the question below."}
            </h1>
            <p className="mk-p04-sub">
              Please describe what you are experiencing in your own words. We will take this one step at a time.
            </p>
            <div className="mk-p04-progress" aria-label={`Question ${Math.min(ANSWERED_COUNT + 1, TOTAL_STEPS)} of ${TOTAL_STEPS}`}>
              {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
                <span
                  key={i}
                  className={`mk-p04-progress__dot ${i < ANSWERED_COUNT ? "mk-p04-progress__dot--done" : ""} ${i === ANSWERED_COUNT ? "mk-p04-progress__dot--active" : ""}`}
                />
              ))}
            </div>
          </div>

          {error && (
            <div className="mk-error-banner" role="alert">{error}</div>
          )}

          <div className="mk-p04-card">
            <div className="mk-p04-assistant">
              <div className="mk-p04-assistant__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                </svg>
              </div>
              <div className="mk-p04-assistant__text">
                <span className="mk-p04-assistant__label">MediKiosk Assistant</span>
                <p className="mk-p04-assistant__body">
                  Welcome! I&rsquo;ll ask a few guided questions to record your symptoms and health history before your consultation.
                </p>
              </div>
            </div>

            <div className="mk-p04-field">
              <label className="mk-p04-field__label" htmlFor="mk-p04-input">
                <span>Primary symptom or concern</span>
                <span className="mk-p04-field__count">{answerInput.length} characters</span>
              </label>
              <textarea
                id="mk-p04-input"
                className="mk-p04-textarea"
                placeholder="Type your response here, or tap the microphone to speak..."
                value={answerInput}
                onChange={(e) => setAnswerInput(e.target.value)}
                disabled={loading}
                aria-label="Interview answer"
                maxLength={2000}
                rows={4}
              />
            </div>

            <div className="mk-p04-aux">
              <div className="mk-p04-aux__left">
                <button
                  type="button"
                  className="mk-p04-voice"
                  disabled
                  title="Voice input coming soon"
                  aria-label="Voice input (currently unavailable)"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="mk-p04-voice__icon" aria-hidden="true">
                    <rect x="9" y="3" width="6" height="11" rx="3" />
                    <path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8" />
                  </svg>
                  <span>Voice unavailable</span>
                </button>
                <button
                  type="button"
                  className="mk-p04-clear"
                  onClick={() => setAnswerInput("")}
                  disabled={loading || answerInput.length === 0}
                  aria-label="Clear response"
                >
                  Clear
                </button>
              </div>
            </div>

            <div className="mk-p04-actions">
              <button
                type="button"
                className="mk-p04-btn mk-p04-btn--back"
                onClick={() => setScreen("code")}
                disabled={loading}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p04-btn__icon" aria-hidden="true">
                  <path d="M19 12H5M12 19l-7-7 7-7" />
                </svg>
                Previous Step
              </button>
              <button
                type="button"
                className="mk-p04-btn mk-p04-btn--primary"
                onClick={handleAnswer}
                disabled={loading || !answerInput.trim()}
              >
                {loading ? "Submitting…" : "Next Question"}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p04-btn__icon" aria-hidden="true">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>

          <div className="mk-p04-disclaimer">
            <span className="mk-p04-disclaimer__icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
            </span>
            <p>
              MediKiosk organizes your medical history for your doctor. It does not provide diagnoses or prescribe treatments.
            </p>
          </div>
        </main>

        <footer className="mk-p04-footer">MediKiosk OPD Assistant • MediKiosk Patient Intake</footer>
      </div>
    );
  }

  if (screen === "documents" && sessionId) {
    return (
      <div className="mk-p06">
        <header className="mk-p06-header">
          <div className="mk-p06-header__inner">
            <div className="mk-p06-brand">
              <div className="mk-p06-brand__logo" aria-hidden="true">
                <svg fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" viewBox="0 0 24 24">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </div>
              <div className="mk-p06-brand__name">
                <span>MediKiosk</span>
                <span className="mk-p06-brand__tag">OPD</span>
              </div>
            </div>
            <nav className="mk-p06-nav" aria-label="Progress">
              {[
                { label: "Language", state: "done" as const },
                { label: "Consent", state: "done" as const },
                { label: "Code", state: "done" as const },
                { label: "Interview", state: "done" as const },
                { label: "Records", state: "active" as const },
                { label: "Summary", state: "upcoming" as const },
                { label: "Token", state: "upcoming" as const },
              ].map((s) => (
                <span
                  key={s.label}
                  className={`mk-p06-nav__pill ${s.state === "active" ? "mk-p06-nav__pill--active" : ""} ${s.state === "done" ? "mk-p06-nav__pill--done" : ""}`}
                >
                  {s.label}
                </span>
              ))}
            </nav>
            <EmergencyHelpButton onHelp={handleEmergencyAlert} />
          </div>
        </header>

        <main className="mk-p06-main">
          {completionMessage && (
            <div
              className="mk-completion-banner"
              style={{
                background: "var(--mk-surface, #F8FAFC)",
                border: "1px solid var(--mk-border, #E2E8F0)",
                borderLeft: "4px solid var(--mk-primary, #0D9488)",
                borderRadius: "8px",
                padding: "12px 16px",
                marginBottom: "20px",
                fontSize: "14px",
                lineHeight: "1.5",
                color: "var(--mk-text, #1E293B)",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <span style={{ fontSize: "18px" }} aria-hidden="true">📋</span>
              <span>{completionMessage}</span>
            </div>
          )}
          <DocumentUpload
            sessionId={sessionId}
            onContinue={handleDocumentsDone}
            onSkip={handleDocumentsDone}
          />
        </main>

        <footer className="mk-p06-footer">
          <p className="mk-p06-footer__notice">
            MediKiosk organizes your medical records for your doctor. It does not provide diagnoses or prescribe treatments.
          </p>
          <div className="mk-p06-footer__protocol">
            <span>MediKiosk OPD Assistant</span>
            <span className="mk-p06-footer__sep">•</span>
            <span>MediKiosk Patient Intake</span>
          </div>
        </footer>
      </div>
    );
  }

  // P08 — Token Issued screen (shown when tokenData exists but not on waiting screen)
  if (tokenData && session && (screen as string) !== "waiting") {
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
                { label: "Code", state: "done" as const },
                { label: "Interview", state: "done" as const },
                { label: "Records", state: "done" as const },
                { label: "Summary", state: "done" as const },
                { label: "Token", state: "active" as const },
              ].map((s) => (
                <span
                  key={s.label}
                  className={`mk-p08-nav__pill ${s.state === "active" ? "mk-p08-nav__pill--active" : ""} ${s.state === "done" ? "mk-p08-nav__pill--done" : ""}`}
                >
                  {s.state === "done" && (
                    <svg className="mk-p08-nav__check" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path d="M20 6L9 17l-5-5" />
                    </svg>
                  )}
                  {s.label}
                </span>
              ))}
            </nav>
            <div className="mk-p08-header__spacer" aria-hidden="true" />
          </div>
        </header>

        <main className="mk-p08-main">
          <div className="mk-p08-content">
            <span className="mk-p08-eyebrow">CONFIRMATION &amp; QUEUE TOKEN</span>
            <h1 className="mk-p08-h1">Your information is confirmed</h1>
            <p className="mk-p08-sub">Your intake details have been recorded for your consultation. Please take note of your token number below.</p>

            <div className="mk-p08-card">
              <div className="mk-p08-status">
                <div className="mk-p08-status__badge">
                  <svg className="mk-p08-status__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                  Intake Complete
                </div>
              </div>

              <div className="mk-p08-dept">
                <span className="mk-p08-dept__label">ASSIGNED OPD DEPARTMENT</span>
                <span className="mk-p08-dept__name">{tokenData.department}</span>
                <span className="mk-p08-dept__sub">General Ayurvedic Medicine</span>
              </div>

              <div className="mk-p08-token-box">
                <div className="mk-p08-token-box__label">DEPARTMENT QUEUE TOKEN</div>
                <div className="mk-p08-token-box__number">{tokenData.token}</div>
                <div className="mk-p08-token-box__sub">Position in department queue</div>
              </div>

              <div className="mk-p08-patient-code">
                <div className="mk-p08-patient-code__badge">
                  <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="8.5" cy="7" r="4" />
                    <path d="M20 8v6M23 11h-6" />
                  </svg>
                  Patient Code: {patientCode || session.patient_code || "—"}
                </div>
                <p className="mk-p08-patient-code__desc">Share this code with clinic staff when called. It links your intake data to your consultation record.</p>
              </div>

              <div className="mk-p08-guidance">
                <p className="mk-p08-guidance__title">Please wait for your token to be called.</p>
                <p className="mk-p08-guidance__desc">Stay in the waiting area near the OPD reception. Your token will appear on the waiting screen and be called aloud by the receptionist.</p>
              </div>

              <button type="button" className="mk-p08-btn" onClick={handleGotoWaiting}>
                Done / View Waiting Screen
                <svg className="mk-p08-btn__arrow" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        </main>

        <footer className="mk-p08-footer">
          <p className="mk-p08-footer__protocol">MediKiosk OPD Assistant &bull; MediKiosk Patient Intake</p>
        </footer>
      </div>
    );
  }

  // P09 - Waiting / Completion screen
  if (screen === "waiting" && tokenData && session) {
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
                { label: "Code", state: "done" as const },
                { label: "Interview", state: "done" as const },
                { label: "Records", state: "done" as const },
                { label: "Summary", state: "done" as const },
                { label: "Token Complete", state: "active" as const },
              ].map((s) => (
                <span
                  key={s.label}
                  className={`mk-p09-nav__pill ${s.state === "active" ? "mk-p09-nav__pill--active" : ""} ${s.state === "done" ? "mk-p09-nav__pill--done" : ""}`}
                >
                  {s.state === "done" && (
                    <svg className="mk-p09-nav__check" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path d="M20 6L9 17l-5-5" />
                    </svg>
                  )}
                  {s.state === "active" && (
                    <svg className="mk-p09-nav__check" width="14" height="14" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                    </svg>
                  )}
                  {s.label}
                </span>
              ))}
            </nav>
            <div className="mk-p09-header__spacer" aria-hidden="true" />
          </div>
        </header>

        <main className="mk-p09-main">
          <div className="mk-p09-content">
            <span className="mk-p09-eyebrow">OPD QUEUE WAITING</span>
            <h1 className="mk-p09-h1">Please wait for your token to be called</h1>
            <p className="mk-p09-sub">Your intake is complete. Please remain in the waiting area until your department queue token is announced or displayed.</p>

            <div className="mk-p09-card">
              <div className="mk-p09-status">
                <div className="mk-p09-status__badge">
                  <svg className="mk-p09-status__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                  Intake Complete
                </div>
              </div>

              <div className="mk-p09-dept">
                <span className="mk-p09-dept__label">DEPARTMENT</span>
                <span className="mk-p09-dept__name">{tokenData.department}</span>
                <span className="mk-p09-dept__sub">General Ayurvedic Medicine</span>
              </div>

              <div className="mk-p09-token-box">
                <div className="mk-p09-token-box__label">YOUR QUEUE TOKEN</div>
                <div className="mk-p09-token-box__number">{tokenData.token}</div>
                <div className="mk-p09-token-box__sub">Position in department queue</div>
              </div>

              <div className="mk-p09-patient-code">
                <div className="mk-p09-patient-code__badge">
                  <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                  Patient Code: <strong>{patientCode || session.patient_code || "-"}</strong>
                </div>
                <p className="mk-p09-patient-code__desc">Identifies your MediKiosk record throughout your visit</p>
              </div>

              <div className="mk-p09-guidance">
                <p className="mk-p09-guidance__title">Keep your patient code and queue token handy.</p>
                <p className="mk-p09-guidance__desc">When your token number is called, follow the instructions provided by the department.</p>
              </div>

              <button type="button" className="mk-p09-btn" onClick={handleSafetyReset}>
                <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                Done / Return to Welcome
              </button>
            </div>
          </div>
        </main>

        <footer className="mk-p09-footer">
          <p className="mk-p09-footer__protocol">MediKiosk OPD Assistant &bull; MediKiosk Patient Intake</p>
        </footer>
      </div>
    );
  }

  if (screen === "summary" && session) {
    return (
      <div className="mk-p07">
        <header className="mk-p07-header">
          <div className="mk-p07-header__inner">
            <div className="mk-p07-brand">
              <div className="mk-p07-brand__logo" aria-hidden="true">
                <svg fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" viewBox="0 0 24 24">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </div>
              <div className="mk-p07-brand__name">
                <span>MediKiosk</span>
                <span className="mk-p07-brand__tag">OPD</span>
              </div>
            </div>
            <nav className="mk-p07-nav" aria-label="Progress">
              {[
                { label: "Language", state: "done" as const },
                { label: "Consent", state: "done" as const },
                { label: "Code", state: "done" as const },
                { label: "Interview", state: "done" as const },
                { label: "Records", state: "done" as const },
                { label: "Summary", state: "active" as const },
                { label: "Token", state: "upcoming" as const },
              ].map((s) => (
                <span
                  key={s.label}
                  className={`mk-p07-nav__pill ${s.state === "active" ? "mk-p07-nav__pill--active" : ""} ${s.state === "done" ? "mk-p07-nav__pill--done" : ""}`}
                >
                  {s.label}
                </span>
              ))}
            </nav>
            <EmergencyHelpButton onHelp={handleEmergencyAlert} />
          </div>
        </header>

        <main className="mk-p07-main">
          <PatientConfirm
            session={session}
            sessionId={sessionId ?? ""}
            patientCode={patientCode || session.patient_code || undefined}
            onReset={handleSafetyReset}
            onBackToRecords={() => setScreen("documents")}
            onTokenGenerated={(token, dept) => setTokenData({ token, department: dept })}
          />
        </main>

        <footer className="mk-p07-footer">
          <p className="mk-p07-footer__protocol">
            MediKiosk OPD Assistant • MediKiosk Patient Intake
          </p>
        </footer>
      </div>
    );
  }

  return (
    <div className="mk-patient-shell">
      <div className="mk-patient-header" style={{ width: "100%", maxWidth: "680px", display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <MediKioskLogo />
          <span className="mk-patient-header__wordmark">MediKiosk</span>
        </div>
        <EmergencyHelpButton onHelp={handleEmergencyAlert} />
      </div>
      <div className="mk-patient-card">
        {error && (
          <div className="mk-error-banner" role="alert">{error}</div>
        )}

        {screen === "welcome" && (
          <div>
            <h1 className="mk-question">
              Welcome to <span style={{ color: "var(--mk-primary)" }}>MediKiosk</span>
            </h1>
            <p className="mk-helper">Quick. Simple. Secure.</p>

            <div className="mk-form-group">
              <label className="mk-field-label">Language</label>
              <div className="mk-chip-group">
                {[
                  { code: "en", label: "English" },
                  { code: "hi", label: "हिन्दी" },
                  { code: "gu", label: "ગુજરાતી" },
                ].map((l) => (
                  <button
                    key={l.code}
                    type="button"
                    className={`mk-chip ${language === l.code ? "selected" : ""}`}
                    onClick={() => setLanguage(l.code)}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mk-form-group">
              <label className="mk-field-label">Visit status</label>
              <div className="mk-chip-group">
                <button
                  type="button"
                  className="mk-chip selected"
                  onClick={() => setVisitType("new")}
                >
                  New Patient
                </button>
              </div>
            </div>

            <div className="mk-form-group">
              <label className="mk-field-label">Full name</label>
              <input
                className="mk-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your name"
              />
            </div>

            <div className="mk-form-group">
              <label className="mk-field-label">Age</label>
              <input
                className="mk-input"
                value={age}
                onChange={(e) => setAge(e.target.value.replace(/\D/g, ""))}
                placeholder="Enter your age"
                inputMode="numeric"
              />
            </div>

            <div className="mk-form-group">
              <label className="mk-field-label">Gender</label>
              <div className="mk-chip-group">
                {["male", "female", "other"].map((g) => (
                  <button
                    key={g}
                    type="button"
                    className={`mk-chip ${gender === g ? "selected" : ""}`}
                    onClick={() => setGender(g)}
                  >
                    {g.charAt(0).toUpperCase() + g.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={handleStart}
              disabled={!canStart || loading}
              className="mk-button mk-button--primary"
              style={{ width: "100%" }}
            >
              {loading ? "Starting…" : "Start Now →"}
            </button>
          </div>
        )}

        {screen === "safety" && (
          <div className="mk-p05">
            <header className="mk-p05-header">
              <div className="mk-p05-header__inner">
                <div className="mk-p05-brand">
                  <div className="mk-p05-brand__logo" aria-hidden="true">
                    <svg fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" viewBox="0 0 24 24">
                      <line x1="12" y1="5" x2="12" y2="19" />
                      <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                  </div>
                  <div className="mk-p05-brand__name">
                    <span>MediKiosk</span>
                    <span className="mk-p05-brand__tag">OPD</span>
                  </div>
                </div>
                <div className="mk-p05-header__spacer" aria-hidden="true" />
              </div>
            </header>

            <main className="mk-p05-main" role="alert" aria-live="polite">
              <div className="mk-p05-title">
                <div className="mk-p05-title__row">
                  <div className="mk-p05-eyebrow">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p05-eyebrow__icon" aria-hidden="true">
                      <path d="M9 12l2 2 4-4" />
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                    </svg>
                    <span>CLINICAL SAFETY NOTICE</span>
                  </div>
                  <span className="mk-p05-status">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p05-status__icon" aria-hidden="true">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="10" y1="9" x2="10" y2="13" />
                      <line x1="10" y1="17" x2="14" y2="17" />
                      <line x1="10" y1="15" x2="14" y2="15" />
                    </svg>
                    <span>Intake Paused</span>
                  </span>
                </div>
                <h1 className="mk-p05-h1">Please speak with a staff member before continuing.</h1>
                <p className="mk-p05-sub">
                  We need to pause this intake session. Please speak with a staff member for further assistance.
                </p>
              </div>

              <div className="mk-p05-card">
                <div className="mk-p05-info">
                  <div className="mk-p05-info__icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" />
                      <path d="M10 8l-3 4 3 4" />
                      <path d="M14 8l3 4-3 4" />
                    </svg>
                  </div>
                  <div className="mk-p05-info__text">
                    <h2 className="mk-p05-info__title">Intake Process Paused</h2>
                    <p className="mk-p05-info__body">
                      Based on the responses entered during your MediKiosk intake, the session has been paused. No department queue token has been generated from this kiosk.
                    </p>
                  </div>
                </div>

                <div className="mk-p05-info">
                  <div className="mk-p05-info__icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
                    </svg>
                  </div>
                  <div className="mk-p05-info__text">
                    <h2 className="mk-p05-info__title">Next Steps for Assistance</h2>
                    <p className="mk-p05-info__body">
                      Please speak directly with a clinic staff member in the area. Let them know that your intake requires staff review.
                    </p>
                  </div>
                </div>

                <div className="mk-p05-ref">
                  <span className="mk-p05-ref__label">Reference Identifier</span>
                  <span className="mk-p05-ref__value">
                    Patient Code:&nbsp;
                    <strong>{patientCode || session?.patient_code || "Assigned at check-in"}</strong>
                  </span>
                  <span className="mk-p05-ref__hint">
                    Keep this reference code handy when speaking with clinic staff.
                  </span>
                </div>
              </div>

              <div className="mk-p05-actions">
                <button
                  type="button"
                  className="mk-p05-btn"
                  onClick={handleSafetyReset}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p05-btn__icon" aria-hidden="true">
                    <path d="M19 12H5M12 19l-7-7 7-7" />
                  </svg>
                  Return to Welcome Screen
                </button>
              </div>

              <div className="mk-p05-protocol">
                <span>MediKiosk OPD Assistant</span>
                <span className="mk-p05-protocol__sep">•</span>
                <span>Patient Intake Protocol P05</span>
              </div>
            </main>

            <footer className="mk-p05-footer">MediKiosk OPD Assistant • MediKiosk Patient Intake</footer>
          </div>
        )}
      </div>
    </div>
  );
}
