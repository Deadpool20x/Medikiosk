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
  lookupPatient,
} from "../lib/api";
import type { Patient, Session as SessionType } from "../lib/types";
import { DocumentUpload } from "./document-upload";
import PatientConfirm from "./patient-confirm";
import { pt } from "../lib/i18n";

const SESSION_KEY = "medikiosk_session_id";

function MediKioskLogo() {
  return (
    <svg viewBox="0 0 40 40" fill="none" className="w-8 h-8" aria-hidden="true">
      <rect width="40" height="40" rx="10" fill="#2563EB" />
      <path d="M20 10v20M10 20h20" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" />
    </svg>
  );
}

export function EmergencyHelpButton({ onHelp, language = "en" }: { onHelp: () => void; language?: string }) {
  return (
    <button
      type="button"
      onClick={onHelp}
      className="mk-emergency-btn"
      id="mk-always-visible-emergency-btn"
      aria-label={pt(language, "emerg_aria")}
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
        zIndex: 50,
      }}
    >
      <span style={{ fontSize: "15px" }} aria-hidden="true">🚨</span> {pt(language, "emerg_btn")}
    </button>
  );
}

type Screen = "welcome" | "lookup" | "consent" | "code" | "interview" | "documents" | "summary" | "safety" | "waiting";

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
  // P01 preferred language & visit_type handoff from sessionStorage
  const [language, setLanguage] = useState(() =>
    typeof window !== "undefined" ? window.sessionStorage.getItem("medikiosk_preferred_language") || "en" : "en"
  );
  const [visitType] = useState<"new" | "returning">(() =>
    typeof window !== "undefined" ? (window.sessionStorage.getItem("medikiosk_visit_type") as "new" | "returning") || "new" : "new"
  );
  const [consentChecked, setConsentChecked] = useState(false);
  const router = useRouter();

  // Returning patient lookup state
  const [priorPatientCode, setPriorPatientCode] = useState("");
  const [lookupResult, setLookupResult] = useState<{ found: boolean; chief_complaint: string; visit_date: string } | null>(null);

  // P04 interview state
  const [answerInput, setAnswerInput] = useState("");
  const [chat, setChat] = useState<Array<{ q: string; a: string }>>([]);
  const [redFlag, setRedFlag] = useState(false);

  // P08 token state
  const [tokenData, setTokenData] = useState<{ token: string; department: string } | null>(null);

  // Adaptive-aware progress: use backend authoritative counts for adaptive sessions,
  // fall back to legacy field-count for non-adaptive sessions.
  const isAdaptive = session?.adaptive_question_limit != null && session.adaptive_question_limit > 0;
  const ANSWERED_COUNT = isAdaptive
    ? (session?.adaptive_question_count ?? session?.questions_asked ?? 0)
    : (() => {
        const LEGACY_FIELDS = ["chief_complaint", "onset", "duration", "severity", "character", "associated_symptoms"];
        return session
          ? LEGACY_FIELDS.filter((f) => {
              if (f === "chief_complaint") return !!session.chief_complaint;
              if (f === "associated_symptoms")
                return (session.history_of_present_illness.associated_symptoms?.length ?? 0) > 0;
              const v = (session.history_of_present_illness as unknown as Record<string, unknown>)[f];
              return typeof v === "string" && v.trim().length > 0;
            }).length
          : 0;
      })();
  const TOTAL_STEPS = isAdaptive
    ? (session?.adaptive_question_limit ?? 5)
    : 6;
  // Step chip label: adaptive sessions show "Interview in progress" with honest count,
  // legacy sessions show the current field name.
  const CURRENT_STEP_LABEL = isAdaptive
    ? (ANSWERED_COUNT > 0
        ? (ANSWERED_COUNT === 1
            ? pt(language, "iv_asked_one")
            : pt(language, "iv_asked_many", { n: ANSWERED_COUNT }))
        : pt(language, "iv_in_progress"))
    : (() => {
        const FIELD_LABELS = [
          { id: "chief_complaint", key: "step_chief_complaint" },
          { id: "onset", key: "step_onset" },
          { id: "duration", key: "step_duration" },
          { id: "severity", key: "step_severity" },
          { id: "character", key: "step_character" },
          { id: "associated_symptoms", key: "step_assoc" },
        ] as const;
        const found = FIELD_LABELS.find((f) => f.id === (session?.interview_step ?? ""));
        return found ? pt(language, found.key) : pt(language, "nav_interview");
      })();
  // Dot count for progress bar: adaptive shows asked dots (max 5 slots), not a fixed total
  const PROGRESS_DOT_COUNT = isAdaptive ? Math.min(TOTAL_STEPS, 5) : TOTAL_STEPS;

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

  async function handleLookup() {
    const code = priorPatientCode.trim();
    if (!code) return;
    setError(null);
    setLoading(true);
    try {
      const result = await lookupPatient(code);
      setLookupResult(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleStart() {
    setError(null);
    setLoading(true);
    try {
      const patient: Patient = { name: name.trim(), age: Number(age), gender };
      const resolvedPriorCode = visitType === "returning" && lookupResult?.found ? priorPatientCode.trim() : undefined;
      const res = await startPatientSession(patient, language, visitType, true, resolvedPriorCode);
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
      const qText = reactQuestion || pt(language, "iv_q_fallback");
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
    setLoading(true);
    try {
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const patient: Patient = {
          name: name.trim() || "Emergency Walk-In",
          age: Number(age) || 0,
          gender: gender || "other",
        };
        const res = await startPatientSession(patient, language, visitType);
        currentSessionId = res.session_id;
        setSessionId(res.session_id);
        window.sessionStorage.setItem(SESSION_KEY, res.session_id);
      }
      const res = await triggerEmergency(currentSessionId);
      if (res.patient_code) {
        setPatientCode(res.patient_code);
      }
      try {
        const s = await getSession(currentSessionId);
        setSession(s);
        if (s.patient_code) {
          setPatientCode(s.patient_code);
        }
      } catch {
        // best effort
      }
    } catch (e) {
      console.error("Emergency trigger error:", e);
    } finally {
      setLoading(false);
      setRedFlag(true);
      setScreen("safety");
    }
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
        setError(pt(language, "d_no_record"));
        return;
      }
      setScreen("summary");
    } catch (e) {
      setError((e as Error).message || pt(language, "d_failed"));
    }
  }

  if (screen === "consent" && sessionId) {
    const steps: { label: string; state: "done" | "active" | "upcoming" }[] = [
      { label: pt(language, "nav_language"), state: "done" },
      { label: pt(language, "nav_consent"), state: "active" },
      { label: pt(language, "nav_code"), state: "upcoming" },
      { label: pt(language, "nav_interview"), state: "upcoming" },
      { label: pt(language, "nav_records"), state: "upcoming" },
      { label: pt(language, "nav_summary"), state: "upcoming" },
      { label: pt(language, "nav_token"), state: "upcoming" },
    ];
    const points: { title: string; body: string; icon: ReactElement }[] = [
      {
        title: pt(language, "c_p1t"),
        body: pt(language, "c_p1b"),
        icon: (
          <svg className="mk-p02-point__icon" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.5L18 8.5V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ),
      },
      {
        title: pt(language, "c_p2t"),
        body: pt(language, "c_p2b"),
        icon: (
          <svg className="mk-p02-point__icon" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 002 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ),
      },
      {
        title: pt(language, "c_p3t"),
        body: pt(language, "c_p3b"),
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
            <nav className="mk-p02-nav" aria-label={pt(language, "a11y_progress")}>
              {steps.map((s) => (
                <span
                  key={s.label}
                  className={`mk-p02-nav__pill${s.state === "active" ? " mk-p02-nav__pill--active" : s.state === "done" ? " mk-p02-nav__pill--done" : ""}`}
                >
                  {s.label}
                </span>
              ))}
            </nav>
            <EmergencyHelpButton onHelp={handleEmergencyAlert} language={language} />
          </div>
        </header>
        <main className="mk-p02-main">
          <div className="mk-p02-title">
            <span className="mk-p02-eyebrow">{pt(language, "c_eyebrow")}</span>
            <h1 className="mk-p02-h1">{pt(language, "c_title")}</h1>
            <p className="mk-p02-sub">
              {pt(language, "c_sub")}
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
                    {pt(language, "c_agree")}
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
                {pt(language, "back")}
              </button>
              <button className="mk-p02-btn mk-p02-btn--primary" type="button" onClick={handleConsent} disabled={loading || !consentChecked}>
                {loading ? pt(language, "c_saving") : pt(language, "c_btn")}
                <svg className="mk-p02-btn__arrow" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M14 5l7 7m0 0l-7 7m7-7H3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        </main>
        <footer className="mk-p02-footer">
          {pt(language, "footer")}
        </footer>
      </div>
    );
  }

  if (screen === "code" && sessionId) {
    const steps: { label: string; state: "done" | "active" | "upcoming" }[] = [
      { label: pt(language, "nav_language"), state: "done" },
      { label: pt(language, "nav_consent"), state: "done" },
      { label: pt(language, "nav_patient"), state: "active" },
      { label: pt(language, "nav_interview"), state: "upcoming" },
      { label: pt(language, "nav_records"), state: "upcoming" },
      { label: pt(language, "nav_summary"), state: "upcoming" },
      { label: pt(language, "nav_token"), state: "upcoming" },
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
            <nav className="mk-p03-nav" aria-label={pt(language, "a11y_progress")}>
              {steps.map((s) => (
                <span key={s.label} className={`mk-p03-nav__pill ${s.state === "active" ? "mk-p03-nav__pill--active" : ""} ${s.state === "done" ? "mk-p03-nav__pill--done" : ""}`}>
                  {s.label}
                </span>
              ))}
            </nav>
            <EmergencyHelpButton onHelp={handleEmergencyAlert} language={language} />
          </div>
        </header>

        <main className="mk-p03-main">
          <div className="mk-p03-title">
            <span className="mk-p03-capsule">
              <span className="mk-p03-capsule__dot" />
              {pt(language, "code_eyebrow")}
            </span>
            <h1 className="mk-p03-h1">{pt(language, "code_title")}</h1>
            <p className="mk-p03-sub">
              {pt(language, "code_sub")}
            </p>
          </div>

          {error && (
            <div className="mk-error-banner" role="alert">{error}</div>
          )}

          <div className="mk-p03-case">
            <div className="mk-p03-code-panel">
              <span className="mk-p03-code-panel__hash" aria-hidden="true">#</span>
              <span className="mk-p03-code-label">{pt(language, "code_generated")}</span>
              <div className="mk-p03-code-row">
                <span className="mk-p03-code mk-token-number" aria-live="polite">
                  {patientCode ?? pt(language, "code_generating")}
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
                  title={pt(language, "code_copy")}
                  aria-label={pt(language, "code_copy")}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="mk-p03-copy__icon">
                    <rect x="9" y="9" width="11" height="11" rx="2" />
                    <path d="M5 15V5a2 2 0 0 1 2-2h10" />
                  </svg>
                </button>
              </div>
              <span className="mk-p03-toast" aria-live="polite">
                {pt(language, "code_copied")}
              </span>
            </div>

            <div className="mk-p03-save">
              <div className="mk-p03-save__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <h2 className="mk-p03-save__title">{pt(language, "code_save_t")}</h2>
              <p className="mk-p03-save__body">
                {pt(language, "code_save_b")}
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
                {pt(language, "back")}
              </button>
              <button
                type="button"
                className="mk-p03-btn mk-p03-btn--primary"
                onClick={handleEnterInterview}
                disabled={loading || !patientCode}
              >
                {loading ? pt(language, "code_continuing") : pt(language, "code_continue")}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p03-btn__icon">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        </main>

        <footer className="mk-p03-footer">{pt(language, "footer")}</footer>
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
            <nav className="mk-p04-nav" aria-label={pt(language, "a11y_progress")}>
              {[
                { label: pt(language, "nav_language"), state: "done" as const },
                { label: pt(language, "nav_consent"), state: "done" as const },
                { label: pt(language, "nav_patient"), state: "done" as const },
                { label: pt(language, "nav_interview"), state: "active" as const },
                { label: pt(language, "nav_records"), state: "upcoming" as const },
                { label: pt(language, "nav_summary"), state: "upcoming" as const },
                { label: pt(language, "nav_token"), state: "upcoming" as const },
              ].map((s) => (
                <span
                  key={s.label}
                  className={`mk-p04-nav__pill ${s.state === "active" ? "mk-p04-nav__pill--active" : ""} ${s.state === "done" ? "mk-p04-nav__pill--done" : ""}`}
                >
                  {s.label}
                </span>
              ))}
            </nav>
            <EmergencyHelpButton onHelp={handleEmergencyAlert} language={language} />
          </div>
        </header>

        <main className="mk-p04-main">
          <div className="mk-p04-title">
            <div className="mk-p04-title__row">
              <span className="mk-p04-eyebrow">{pt(language, "iv_eyebrow")}</span>
              <span className="mk-p04-step-chip">
                <span>{CURRENT_STEP_LABEL}</span>
              </span>
            </div>
            <h1 className="mk-p04-h1">
              {reactQuestion || pt(language, "iv_q_fallback")}
            </h1>
            <p className="mk-p04-sub">
              {pt(language, "iv_sub")}
            </p>
            <div className="mk-p04-progress" aria-label={isAdaptive ? pt(language, "iv_asked_aria", { n: ANSWERED_COUNT }) : pt(language, "iv_progress_aria", { n: Math.min(ANSWERED_COUNT + 1, TOTAL_STEPS), total: TOTAL_STEPS })}>
              {Array.from({ length: PROGRESS_DOT_COUNT }).map((_, i) => (
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
                <span className="mk-p04-assistant__label">{pt(language, "iv_assist")}</span>
                <p className="mk-p04-assistant__body">
                  {pt(language, "iv_assist_b")}
                </p>
              </div>
            </div>

            <div className="mk-p04-field">
              <label className="mk-p04-field__label" htmlFor="mk-p04-input">
                <span>{pt(language, "iv_field")}</span>
                <span className="mk-p04-field__count">{pt(language, "iv_chars", { n: answerInput.length })}</span>
              </label>
              <textarea
                id="mk-p04-input"
                className="mk-p04-textarea"
                placeholder={pt(language, "iv_ph")}
                value={answerInput}
                onChange={(e) => setAnswerInput(e.target.value)}
                disabled={loading}
                aria-label={pt(language, "iv_answer_aria")}
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
                  title={pt(language, "iv_voice_title")}
                  aria-label={pt(language, "iv_voice_na")}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="mk-p04-voice__icon" aria-hidden="true">
                    <rect x="9" y="3" width="6" height="11" rx="3" />
                    <path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8" />
                  </svg>
                  <span>{pt(language, "iv_voice_na")}</span>
                </button>
                <button
                  type="button"
                  className="mk-p04-clear"
                  onClick={() => setAnswerInput("")}
                  disabled={loading || answerInput.length === 0}
                  aria-label={pt(language, "iv_clear_aria")}
                >
                  {pt(language, "iv_clear")}
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
                {pt(language, "iv_prev")}
              </button>
              <button
                type="button"
                className="mk-p04-btn mk-p04-btn--primary"
                onClick={handleAnswer}
                disabled={loading || !answerInput.trim()}
              >
                {loading ? pt(language, "iv_submitting") : pt(language, "iv_next")}
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
              {pt(language, "iv_disclaimer")}
            </p>
          </div>
        </main>

        <footer className="mk-p04-footer">{pt(language, "footer")}</footer>
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
            <nav className="mk-p06-nav" aria-label={pt(language, "a11y_progress")}>
              {[
                { label: pt(language, "nav_language"), state: "done" as const },
                { label: pt(language, "nav_consent"), state: "done" as const },
                { label: pt(language, "nav_code"), state: "done" as const },
                { label: pt(language, "nav_interview"), state: "done" as const },
                { label: pt(language, "nav_records"), state: "active" as const },
                { label: pt(language, "nav_summary"), state: "upcoming" as const },
                { label: pt(language, "nav_token"), state: "upcoming" as const },
              ].map((s) => (
                <span
                  key={s.label}
                  className={`mk-p06-nav__pill ${s.state === "active" ? "mk-p06-nav__pill--active" : ""} ${s.state === "done" ? "mk-p06-nav__pill--done" : ""}`}
                >
                  {s.label}
                </span>
              ))}
            </nav>
            <EmergencyHelpButton onHelp={handleEmergencyAlert} language={language} />
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
            language={language}
            onContinue={handleDocumentsDone}
            onSkip={handleDocumentsDone}
          />
        </main>

        <footer className="mk-p06-footer">
          <p className="mk-p06-footer__notice">
            {pt(language, "d_footer_note")}
          </p>
          <div className="mk-p06-footer__protocol">
            {pt(language, "footer")}
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
            <nav className="mk-p08-nav" aria-label={pt(language, "a11y_progress")}>
              {[
                { label: pt(language, "nav_language"), state: "done" as const },
                { label: pt(language, "nav_consent"), state: "done" as const },
                { label: pt(language, "nav_code"), state: "done" as const },
                { label: pt(language, "nav_interview"), state: "done" as const },
                { label: pt(language, "nav_records"), state: "done" as const },
                { label: pt(language, "nav_summary"), state: "done" as const },
                { label: pt(language, "nav_token"), state: "active" as const },
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
            <EmergencyHelpButton onHelp={handleEmergencyAlert} language={language} />
          </div>
        </header>

        <main className="mk-p08-main">
          <div className="mk-p08-content">
            <span className="mk-p08-eyebrow">{pt(language, "t_eyebrow")}</span>
            <h1 className="mk-p08-h1">{pt(language, "t_title")}</h1>
            <p className="mk-p08-sub">{pt(language, "t_sub")}</p>

            <div className="mk-p08-card">
              <div className="mk-p08-status">
                <div className="mk-p08-status__badge">
                  <svg className="mk-p08-status__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                  {pt(language, "t_done")}
                </div>
              </div>

              <div className="mk-p08-dept">
                <span className="mk-p08-dept__label">{pt(language, "t_dept")}</span>
                <span className="mk-p08-dept__name">{tokenData.department}</span>
                <span className="mk-p08-dept__sub">{pt(language, "t_dept_sub")}</span>
              </div>

              <div className="mk-p08-token-box">
                <div className="mk-p08-token-box__label">{pt(language, "t_token_label")}</div>
                <div className="mk-p08-token-box__number">{tokenData.token}</div>
                <div className="mk-p08-token-box__sub">{pt(language, "t_token_sub")}</div>
              </div>

              <div className="mk-p08-patient-code">
                <div className="mk-p08-patient-code__badge">
                  <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="8.5" cy="7" r="4" />
                    <path d="M20 8v6M23 11h-6" />
                  </svg>
                  {pt(language, "t_code_label")} {patientCode || session.patient_code || "—"}
                </div>
                <p className="mk-p08-patient-code__desc">{pt(language, "t_code_desc")}</p>
              </div>

              <div className="mk-p08-guidance">
                <p className="mk-p08-guidance__title">{pt(language, "t_wait_t")}</p>
                <p className="mk-p08-guidance__desc">{pt(language, "t_wait_d")}</p>
              </div>

              <button type="button" className="mk-p08-btn" onClick={handleGotoWaiting}>
                {pt(language, "t_goto")}
                <svg className="mk-p08-btn__arrow" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        </main>

        <footer className="mk-p08-footer">
          <p className="mk-p08-footer__protocol">{pt(language, "footer")}</p>
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
            <nav className="mk-p09-nav" aria-label={pt(language, "a11y_progress")}>
              {[
                { label: pt(language, "nav_language"), state: "done" as const },
                { label: pt(language, "nav_consent"), state: "done" as const },
                { label: pt(language, "nav_code"), state: "done" as const },
                { label: pt(language, "nav_interview"), state: "done" as const },
                { label: pt(language, "nav_records"), state: "done" as const },
                { label: pt(language, "nav_summary"), state: "done" as const },
                { label: pt(language, "nav_token_done"), state: "active" as const },
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
            <EmergencyHelpButton onHelp={handleEmergencyAlert} language={language} />
          </div>
        </header>

        <main className="mk-p09-main">
          <div className="mk-p09-content">
            <span className="mk-p09-eyebrow">{pt(language, "w9_eyebrow")}</span>
            <h1 className="mk-p09-h1">{pt(language, "w9_title")}</h1>
            <p className="mk-p09-sub">{pt(language, "w9_sub")}</p>

            <div className="mk-p09-card">
              <div className="mk-p09-status">
                <div className="mk-p09-status__badge">
                  <svg className="mk-p09-status__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                  {pt(language, "t_done")}
                </div>
              </div>

              <div className="mk-p09-dept">
                <span className="mk-p09-dept__label">{pt(language, "w9_dept")}</span>
                <span className="mk-p09-dept__name">{tokenData.department}</span>
                <span className="mk-p09-dept__sub">{pt(language, "t_dept_sub")}</span>
              </div>

              <div className="mk-p09-token-box">
                <div className="mk-p09-token-box__label">{pt(language, "w9_token_label")}</div>
                <div className="mk-p09-token-box__number">{tokenData.token}</div>
                <div className="mk-p09-token-box__sub">{pt(language, "t_token_sub")}</div>
              </div>

              <div className="mk-p09-patient-code">
                <div className="mk-p09-patient-code__badge">
                  <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                  {pt(language, "t_code_label")} <strong>{patientCode || session.patient_code || "-"}</strong>
                </div>
                <p className="mk-p09-patient-code__desc">{pt(language, "w9_code_desc")}</p>
              </div>

              <div className="mk-p09-guidance">
                <p className="mk-p09-guidance__title">{pt(language, "w9_keep_t")}</p>
                <p className="mk-p09-guidance__desc">{pt(language, "w9_keep_d")}</p>
              </div>

              <button type="button" className="mk-p09-btn" onClick={handleSafetyReset}>
                <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                {pt(language, "w9_done")}
              </button>
            </div>
          </div>
        </main>

        <footer className="mk-p09-footer">
          <p className="mk-p09-footer__protocol">{pt(language, "footer")}</p>
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
            <nav className="mk-p07-nav" aria-label={pt(language, "a11y_progress")}>
              {[
                { label: pt(language, "nav_language"), state: "done" as const },
                { label: pt(language, "nav_consent"), state: "done" as const },
                { label: pt(language, "nav_code"), state: "done" as const },
                { label: pt(language, "nav_interview"), state: "done" as const },
                { label: pt(language, "nav_records"), state: "done" as const },
                { label: pt(language, "nav_summary"), state: "active" as const },
                { label: pt(language, "nav_token"), state: "upcoming" as const },
              ].map((s) => (
                <span
                  key={s.label}
                  className={`mk-p07-nav__pill ${s.state === "active" ? "mk-p07-nav__pill--active" : ""} ${s.state === "done" ? "mk-p07-nav__pill--done" : ""}`}
                >
                  {s.label}
                </span>
              ))}
            </nav>
            <EmergencyHelpButton onHelp={handleEmergencyAlert} language={language} />
          </div>
        </header>

        <main className="mk-p07-main">
          <PatientConfirm
            session={session}
            sessionId={sessionId ?? ""}
            patientCode={patientCode || session.patient_code || undefined}
            language={language}
            onReset={handleSafetyReset}
            onBackToRecords={() => setScreen("documents")}
            onTokenGenerated={(token, dept) => setTokenData({ token, department: dept })}
          />
        </main>

        <footer className="mk-p07-footer">
          <p className="mk-p07-footer__protocol">
            {pt(language, "footer")}
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
        <EmergencyHelpButton onHelp={handleEmergencyAlert} language={language} />
      </div>
      <div className="mk-patient-card">
        {error && (
          <div className="mk-error-banner" role="alert">{error}</div>
        )}

        {screen === "welcome" && (
          <div>
            <h1 className="mk-question">
              {pt(language, "w_title_a")} <span style={{ color: "var(--mk-primary)" }}>MediKiosk</span>
            </h1>
            <p className="mk-helper">{pt(language, "w_sub")}</p>

            <div className="mk-form-group">
              <label className="mk-field-label">{pt(language, "w_language")}</label>
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
              <label className="mk-field-label">{pt(language, "w_visit")}</label>
              <div className="mk-chip-group">
                <div className="mk-chip selected">
                  {visitType === "returning" ? pt(language, "w_ret") : pt(language, "w_new")}
                </div>
              </div>
            </div>

            <div className="mk-form-group">
              <label className="mk-field-label">{pt(language, "w_name")}</label>
              <input
                className="mk-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={pt(language, "w_name_ph")}
              />
            </div>

            <div className="mk-form-group">
              <label className="mk-field-label">{pt(language, "w_age")}</label>
              <input
                className="mk-input"
                value={age}
                onChange={(e) => setAge(e.target.value.replace(/\D/g, ""))}
                placeholder={pt(language, "w_age_ph")}
                inputMode="numeric"
              />
            </div>

            <div className="mk-form-group">
              <label className="mk-field-label">{pt(language, "w_gender")}</label>
              <div className="mk-chip-group">
                {(["male", "female", "other"] as const).map((g) => (
                  <button
                    key={g}
                    type="button"
                    className={`mk-chip ${gender === g ? "selected" : ""}`}
                    onClick={() => setGender(g)}
                  >
                    {g === "male" ? pt(language, "w_male") : g === "female" ? pt(language, "w_female") : pt(language, "w_other")}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={visitType === "returning" ? () => setScreen("lookup") : handleStart}
              disabled={!canStart || loading}
              className="mk-button mk-button--primary"
              style={{ width: "100%" }}
            >
              {loading ? pt(language, "w_starting") : visitType === "returning" ? pt(language, "w_continue") : pt(language, "w_start")}
            </button>
          </div>
        )}

        {screen === "lookup" && (
          <div>
            <h1 className="mk-question">{pt(language, "lk_title")}</h1>
            <p className="mk-helper">{pt(language, "lk_sub")}</p>

            <div className="mk-form-group">
              <label className="mk-field-label">{pt(language, "lk_label")}</label>
              <input
                className="mk-input"
                value={priorPatientCode}
                onChange={(e) => { setPriorPatientCode(e.target.value.toUpperCase()); setLookupResult(null); }}
                placeholder={pt(language, "lk_ph")}
                autoComplete="off"
                onKeyDown={(e) => e.key === "Enter" && handleLookup()}
              />
            </div>

            {lookupResult !== null && (
              <div className={`mk-info-banner ${lookupResult.found ? "mk-info-banner--success" : "mk-info-banner--warn"}`} role="status">
                {lookupResult.found ? (
                  <>
                    <strong>{pt(language, "lk_found")}</strong>
                    {lookupResult.chief_complaint && (
                      <p style={{ margin: "4px 0 0" }}>{pt(language, "lk_last", { complaint: lookupResult.chief_complaint })}</p>
                    )}
                    {lookupResult.visit_date && (
                      <p style={{ margin: "2px 0 0", fontSize: "0.85em", opacity: 0.75 }}>{lookupResult.visit_date.slice(0, 10)}</p>
                    )}
                  </>
                ) : (
                  <span>{pt(language, "lk_notfound")}</span>
                )}
              </div>
            )}

            <div style={{ display: "flex", gap: "8px", marginTop: "16px" }}>
              <button
                onClick={() => setScreen("welcome")}
                className="mk-button"
                style={{ flex: "0 0 auto" }}
              >
                {pt(language, "back")}
              </button>
              {lookupResult === null ? (
                <button
                  onClick={handleLookup}
                  disabled={!priorPatientCode.trim() || loading}
                  className="mk-button mk-button--primary"
                  style={{ flex: 1 }}
                >
                  {loading ? pt(language, "lk_looking") : pt(language, "lk_lookup")}
                </button>
              ) : (
                <button
                  onClick={handleStart}
                  disabled={loading}
                  className="mk-button mk-button--primary"
                  style={{ flex: 1 }}
                >
                  {loading ? pt(language, "w_starting") : pt(language, "lk_start")}
                </button>
              )}
            </div>
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
                    <span>{pt(language, "s_eyebrow")}</span>
                  </div>
                  <span className="mk-p05-status">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p05-status__icon" aria-hidden="true">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="10" y1="9" x2="10" y2="13" />
                      <line x1="10" y1="17" x2="14" y2="17" />
                      <line x1="10" y1="15" x2="14" y2="15" />
                    </svg>
                    <span>{pt(language, "s_paused")}</span>
                  </span>
                </div>
                <h1 className="mk-p05-h1">{pt(language, "s_title")}</h1>
                <p className="mk-p05-sub">
                  {pt(language, "s_sub")}
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
                    <h2 className="mk-p05-info__title">{pt(language, "s_info1t")}</h2>
                    <p className="mk-p05-info__body">
                      {pt(language, "s_info1b")}
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
                    <h2 className="mk-p05-info__title">{pt(language, "s_info2t")}</h2>
                    <p className="mk-p05-info__body">
                      {pt(language, "s_info2b")}
                    </p>
                  </div>
                </div>

                <div className="mk-p05-ref">
                  <span className="mk-p05-ref__label">{pt(language, "s_ref")}</span>
                  <span className="mk-p05-ref__value">
                    {pt(language, "s_patient_code")}&nbsp;
                    <strong>{patientCode || session?.patient_code || pt(language, "s_assigned")}</strong>
                  </span>
                  <span className="mk-p05-ref__hint">
                    {pt(language, "s_keep")}
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
                  {pt(language, "s_back")}
                </button>
              </div>

              <div className="mk-p05-protocol">
                <span>MediKiosk OPD Assistant</span>
                <span className="mk-p05-protocol__sep">•</span>
                <span>{pt(language, "s_protocol")}</span>
              </div>
            </main>

            <footer className="mk-p05-footer">{pt(language, "footer")}</footer>
          </div>
        )}
      </div>
    </div>
  );
}
