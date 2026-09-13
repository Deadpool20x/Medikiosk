"use client";

import { useEffect, useRef, useState } from "react";
import { getDoctorSession, patchDoctorSession, correctDoctorDocument } from "../lib/api";
import type { Session, DocumentField } from "../lib/types";

const DEPT_LABELS: Record<string, string> = {
  Kayachikitsa: "Kayachikitsa OPD",
  Panchakarma: "Panchakarma OPD",
};

function depLabel(department: string | null): string {
  return (department && DEPT_LABELS[department]) || department || "—";
}

function formatClock(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

function firstAnswerTime(s: Session): string {
  const stamps = [...s.answer_records, ...s.raw_answers.map((r) => ({ timestamp: r.timestamp }))]
    .map((r) => r.timestamp)
    .filter(Boolean) as string[];
  if (stamps.length === 0) return "";
  stamps.sort();
  return stamps[0];
}

type ConfState = "high" | "review" | "corrected";

function confidenceState(needs_review: boolean, manually_corrected: boolean): ConfState {
  if (manually_corrected) return "corrected";
  if (needs_review) return "review";
  return "high";
}

const CONF_LABEL: Record<ConfState, string> = {
  high: "High confidence",
  review: "Review",
  corrected: "Manually corrected",
};

function ConfidenceChip({ state }: { state: ConfState }) {
  return <span className={`mk-d03-chip mk-d03-chip--${state}`}>{CONF_LABEL[state]}</span>;
}

function blockConfidence(docs: DocumentField[]): ConfState {
  const state: ConfState = "high";
  return docs.reduce<ConfState>((worst, d) => {
    const s = confidenceState(d.needs_review, d.manually_corrected);
    return s === "corrected" || worst === "corrected" ? "corrected" : s === "review" || worst === "review" ? "review" : "high";
  }, state);
}

function VerifiedChip() {
  return (
    <span className="mk-d03-chip mk-d03-chip--verified">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
      Doctor Verified
    </span>
  );
}

function ClinicalOSBar({ department, onNavQueue }: { department: string; onNavQueue?: () => void }) {
  const dept = depLabel(department || null).toUpperCase();
  return (
    <header className="mk-d03-os" data-purpose="d03-os">
      <div className="mk-d03-os__brand">
        <div className="mk-d03-os__title">
          <span className="mk-d03-os__wordmark">MEDIKIOSK</span>
          <span className="mk-d03-os__sub">OPD CLINICAL OS</span>
        </div>
        <span className="mk-d03-os__dept">DEPT: {dept}</span>
      </div>
      <nav className="mk-d03-os__nav" aria-label="Clinical OS">
        <button type="button" className="mk-d03-os__link" onClick={() => onNavQueue && onNavQueue()}>Queue</button>
        <a className="mk-d03-os__link" href="#" onClick={(e) => e.preventDefault()}>Cases</a>
        <a className="mk-d03-os__link" href="#" onClick={(e) => e.preventDefault()}>Archive</a>
      </nav>
      <div className="mk-d03-os__ctl">
        <span className="mk-d03-os__status">
          <span className="mk-d03-os__dot" aria-hidden="true" />
          ONLINE / QUEUE ACTIVE
        </span>
        <div className="mk-d03-os__account">
          <span className="mk-d03-os__avatar" aria-hidden="true">MK</span>
          <span className="mk-d03-os__acct">Demo Clinician</span>
        </div>
      </div>
    </header>
  );
}

export function DoctorReview({
  sessionId,
  department,
  onBack,
  onNavQueue,
}: {
  sessionId: string;
  department: string;
  onBack: () => void;
  onNavQueue?: () => void;
}) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [chief, setChief] = useState("");
  const [onset, setOnset] = useState("");
  const [duration, setDuration] = useState("");
  const [severity, setSeverity] = useState("");
  const [character, setCharacter] = useState("");
  const [symptoms, setSymptoms] = useState("");

  const [editingDocIdx, setEditingDocIdx] = useState<number | null>(null);
  const [correctionVal, setCorrectionVal] = useState("");

  const rootRef = useRef<HTMLDivElement | null>(null);
  const footerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const root = rootRef.current;
    const footer = footerRef.current;
    if (!root || !footer) return;
    const MIN = 104;
    const update = () => {
      root.style.setProperty("--d03-bottom-space", `${Math.max(MIN, footer.offsetHeight + 16)}px`);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(footer);
    return () => ro.disconnect();
  }, [session]);

  async function load() {
    try {
      const s = await getDoctorSession(sessionId);
      setSession(s);
      setChief(s.chief_complaint ?? "");
      setOnset(s.history_of_present_illness.onset ?? "");
      setDuration(s.history_of_present_illness.duration ?? "");
      setSeverity(s.history_of_present_illness.severity ?? "");
      setCharacter(s.history_of_present_illness.character ?? "");
      setSymptoms(s.history_of_present_illness.associated_symptoms.join(", "));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  async function handleSave() {
    if (!session) return;
    setSaving(true);
    setError(null);
    try {
      const next = await patchDoctorSession(sessionId, {
        chief_complaint: chief.trim() || undefined,
        onset: onset.trim() || undefined,
        duration: duration.trim() || undefined,
        severity: severity.trim() || undefined,
        character: character.trim() || undefined,
        associated_symptoms: symptoms.split(",").map((s) => s.trim()).filter(Boolean) || undefined,
      });
      setSession(next);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleConfirm() {
    if (!session) return;
    if (session.safety_flagged) return;
    setSaving(true);
    setError(null);
    try {
      const next = await patchDoctorSession(sessionId, { doctor_confirmed: true });
      setSession(next);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  function handleDiscard() {
    if (!session) return;
    setChief(session.chief_complaint ?? "");
    setOnset(session.history_of_present_illness.onset ?? "");
    setDuration(session.history_of_present_illness.duration ?? "");
    setSeverity(session.history_of_present_illness.severity ?? "");
    setCharacter(session.history_of_present_illness.character ?? "");
    setSymptoms(session.history_of_present_illness.associated_symptoms.join(", "));
    setEditingDocIdx(null);
    setCorrectionVal("");
  }

  async function handleDocCorrection(index: number) {
    if (!correctionVal.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const next = await correctDoctorDocument(sessionId, index, { corrected_value: correctionVal.trim() });
      setSession(next);
      setEditingDocIdx(null);
      setCorrectionVal("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  function startDocEdit(idx: number, currentVal: string) {
    setEditingDocIdx(idx);
    setCorrectionVal(currentVal);
  }

  if (loading) {
    return (
      <div className="mk-d03" data-purpose="d03-review">
        <ClinicalOSBar department={department} onNavQueue={onNavQueue} />
        <div className="mk-d03-body"><p className="mk-page-desc">Loading review…</p></div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="mk-d03" data-purpose="d03-review">
        <ClinicalOSBar department={department} onNavQueue={onNavQueue} />
        <div className="mk-d03-body">
          {error && <div className="mk-error-banner" role="alert">{error}</div>}
          <button className="mk-button mk-button--secondary" onClick={onBack}>← Back</button>
        </div>
      </div>
    );
  }

  if (session.safety_flagged) {
    return (
      <div className="mk-d03" ref={rootRef} data-purpose="d03-review">
        <ClinicalOSBar department={department} onNavQueue={onNavQueue} />
        <div className="mk-d03-body">
          <div className="mk-d03-topbar">
            <button className="mk-d03-back" onClick={onBack}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>
              Back to Case ({session.queue_token || "—"})
            </button>
          </div>
          <div className="mk-d03-safety" role="alert" data-purpose="safety-flagged-review">
            <div className="mk-d03-safety__icon">!</div>
            <div>
              <h2>Safety Flagged — Case cannot be reviewed or confirmed</h2>
              <p>This session was flagged for safety review. Editing and confirmation are disabled until the safety flag is resolved by an administrator.</p>
              {session.safety_detail.length > 0 && (
                <ul>{session.safety_detail.map((d, i) => <li key={i}>{d}</li>)}</ul>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  const checkIn = firstAnswerTime(session);
  const confirmed = session.doctor_review.confirmed;
  const edited = session.doctor_review.edited;

  return (
    <div className="mk-d03" ref={rootRef} data-purpose="d03-review">
      <ClinicalOSBar department={department} onNavQueue={onNavQueue} />
      <div className="mk-d03-body">
      {/* Sub-header: breadcrumb + action bar */}
      <div className="mk-d03-topbar">
        <div className="mk-d03-topbar__left">
          <button className="mk-d03-back" onClick={onBack}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>
            Back to Case ({session.queue_token || "—"})
          </button>
        </div>
        <div className="mk-d03-topbar__right">
          <button className="mk-d03-btn mk-d03-btn--ghost" onClick={handleDiscard} disabled={saving}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
            Discard Changes
          </button>
          <button className="mk-d03-btn mk-d03-btn--primary" onClick={handleConfirm} disabled={saving || confirmed}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>
            {confirmed ? "Confirmed" : "Confirm Case"}
          </button>
        </div>
      </div>

      {/* Patient ID banner */}
      <div className="mk-d03-banner" data-purpose="patient-banner">
        <div className="mk-d03-banner__idents">
          <div className="mk-d03-banner__group">
            <span className="mk-d03-banner__label">Queue Token</span>
            <div className="mk-d03-banner__token-row">
              <span className="mk-d03-banner__token">{session.queue_token || "—"}</span>
              <span className="mk-d03-chip mk-d03-chip--warning">Review &amp; Edit</span>
            </div>
          </div>
          <div className="mk-d03-banner__divider" />
          <div className="mk-d03-banner__group">
            <span className="mk-d03-banner__label">Patient Code</span>
            <span className="mk-d03-banner__value">{session.patient_code || "—"}</span>
          </div>
          <div className="mk-d03-banner__group">
            <span className="mk-d03-banner__label">Department</span>
            <span className="mk-d03-banner__value">{depLabel(session.department || department)}</span>
          </div>
          {checkIn && (
            <div className="mk-d03-banner__group">
              <span className="mk-d03-banner__label">Check-in Time</span>
              <span className="mk-d03-banner__value">{formatClock(checkIn)}</span>
            </div>
          )}
          <div className="mk-d03-banner__group">
            <span className="mk-d03-banner__label">Case Status</span>
            <div className="mk-d03-banner__status">
              <span className="mk-d03-banner__dot" />
              <span className="mk-d03-banner__status-label">{confirmed ? "Confirmed" : "Review & Edit"}</span>
            </div>
          </div>
        </div>
      </div>

      {error && <div className="mk-error-banner" role="alert" style={{ margin: "16px 0" }}>{error}</div>}

      {/* Clinical grid: 8/4 */}
      <div className="mk-d03-grid">
        <div className="mk-d03-main">
          {/* Section 01: Chief Complaint & HPI */}
          <section className="mk-d03-card" data-purpose="section-01-hpi">
            <div className="mk-d03-card__head">
              <div className="mk-d03-card__head-left">
                <span className="mk-d03-card__number">01</span>
                <h2 className="mk-d03-card__title">Chief Complaint &amp; History of Present Illness (HPI)</h2>
              </div>
              <div className="mk-d03-card__head-right">
                <span className="mk-d03-chip mk-d03-chip--muted">Source: Patient Interview</span>
                <span className="mk-d03-chip mk-d03-chip--editable">Editable</span>
              </div>
            </div>
            <div className="mk-d03-fields">
              <div className="mk-d03-field">
                <label className="mk-d03-label">Reported Complaint</label>
                <textarea
                  className="mk-d03-textarea"
                  value={chief}
                  onChange={(e) => setChief(e.target.value)}
                  rows={3}
                  data-purpose="chief-complaint-input"
                />
              </div>
              <div className="mk-d03-field-row">
                <div className="mk-d03-field">
                  <label className="mk-d03-label">Onset</label>
                  <input className="mk-d03-input" value={onset} onChange={(e) => setOnset(e.target.value)} data-purpose="onset-input" />
                </div>
                <div className="mk-d03-field">
                  <label className="mk-d03-label">Duration</label>
                  <input className="mk-d03-input" value={duration} onChange={(e) => setDuration(e.target.value)} data-purpose="duration-input" />
                </div>
              </div>
              <div className="mk-d03-field-row">
                <div className="mk-d03-field">
                  <label className="mk-d03-label">Severity</label>
                  <input className="mk-d03-input" value={severity} onChange={(e) => setSeverity(e.target.value)} data-purpose="severity-input" />
                </div>
                <div className="mk-d03-field">
                  <label className="mk-d03-label">Character</label>
                  <input className="mk-d03-input" value={character} onChange={(e) => setCharacter(e.target.value)} data-purpose="character-input" />
                </div>
              </div>
              <div className="mk-d03-field">
                <label className="mk-d03-label">Associated Symptoms</label>
                <input className="mk-d03-input" value={symptoms} onChange={(e) => setSymptoms(e.target.value)} data-purpose="symptoms-input" />
              </div>
            </div>
          </section>

          {/* Section 02: Medical & Health History */}
          <section className="mk-d03-card" data-purpose="section-02-medical">
            <div className="mk-d03-card__head">
              <div className="mk-d03-card__head-left">
                <span className="mk-d03-card__number">02</span>
                <h2 className="mk-d03-card__title">Medical &amp; Health History</h2>
              </div>
              <div className="mk-d03-card__head-right">
                <span className="mk-d03-chip mk-d03-chip--muted">Source: Patient Interview &amp; Uploaded Document</span>
              </div>
            </div>

{session.documents.length > 0 && (
                  <div className="mk-d03-meds-block">
                    <div className="mk-d03-meds-header">
                      <span className="mk-d03-label" style={{ fontWeight: 600 }}>Current Medications</span>
                      <div className="mk-d03-meds-badges">
                        <span className="mk-d03-chip mk-d03-chip--secondary">From uploaded document</span>
                        <ConfidenceChip state={blockConfidence(session.documents)} />
                      </div>
                    </div>
                {session.documents.map((doc, i) => {
                  const display = [doc.extracted_value || "", doc.strength, doc.dose, doc.frequency].filter(Boolean).join(" · ");
                  if (!doc.extracted_value) return null;
                  return (
                    <div key={i} className="mk-d03-meds-row" data-purpose={`doc-item-${i}`}>
                      <div className="mk-d03-meds-original">
                        <span className="mk-d03-meds-original__label">Original Extracted Item {String(i + 1).padStart(2, "0")}</span>
                        <span className="mk-d03-meds-original__value">{display}</span>
                        <span className="mk-d03-meds-original__source">
                          {doc.manually_corrected && doc.original_extraction
                            ? `Corrected from: ${[doc.original_extraction.medicine, doc.original_extraction.strength, doc.original_extraction.dose, doc.original_extraction.frequency].filter(Boolean).join(" ")}`
                            : `From uploaded document`}
                        </span>
                      </div>
                      <div className="mk-d03-meds-validated">
                        <div className="mk-d03-meds-validated__head">
                          <span className="mk-d03-meds-validated__label">Doctor Validated Entry</span>
                          {doc.manually_corrected && <VerifiedChip />}
                        </div>
                        <span className="mk-d03-meds-validated__value">{display}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="mk-d03-empty-note">
              No past medical history, allergies, or family history was recorded during this intake visit.
            </div>
          </section>

          {/* Section 03: Patient-Reported Ayurvedic Information */}
          <section className="mk-d03-card" data-purpose="section-03-ayurvedic">
            <div className="mk-d03-card__head">
              <div className="mk-d03-card__head-left">
                <span className="mk-d03-card__number">03</span>
                <h2 className="mk-d03-card__title">Patient-Reported Ayurvedic Information</h2>
              </div>
              <div className="mk-d03-card__head-right">
                <span className="mk-d03-chip mk-d03-chip--muted">Patient-Reported &bull; Uninterpreted</span>
              </div>
            </div>
            <p className="mk-d03-disclaimer">
              Patient-reported characteristics only; no clinical diagnosis or dosha classification inferred.
            </p>
            <div className="mk-d03-empty-note">
              No structured Ayurvedic baseline was recorded during this visit. The current intake captures only the chief complaint and HPI.
            </div>
          </section>
        </div>

        {/* Side panel: section 04 */}
        <div className="mk-d03-side">
          <section className="mk-d03-card" data-purpose="section-04-documents">
            <div className="mk-d03-card__head">
              <div className="mk-d03-card__head-left">
                <span className="mk-d03-card__number">04</span>
                <h2 className="mk-d03-card__title">Uploaded Documents</h2>
              </div>
              <span className="mk-d03-chip mk-d03-chip--count">
                {session.documents.length} {session.documents.length === 1 ? "Document" : "Documents"}
              </span>
            </div>
            <div className="mk-d03-extract-label">Extracted Items Verification</div>
            {session.documents.length === 0 ? (
              <div className="mk-d03-empty-note">No documents were uploaded for this visit.</div>
            ) : (
              session.documents.map((doc, i) => {
                const display = [doc.extracted_value || "", doc.strength, doc.dose, doc.frequency].filter(Boolean).join(" · ");
                const state = confidenceState(doc.needs_review, doc.manually_corrected);
                const isEditing = editingDocIdx === i;
                return (
                  <div key={i} className="mk-d03-doc" data-purpose={`doc-extract-${i}`}>
                    <div className="mk-d03-doc__main">
                      <div className="mk-d03-doc__info">
                        <span className="mk-d03-doc__value">{display || "No medicine could be read from this document."}</span>
                        <span className="mk-d03-doc__meta">
                          From uploaded document &bull; <ConfidenceChip state={state} />
                        </span>
                      </div>
                      {doc.manually_corrected && (
                        <div className="mk-d03-chip mk-d03-chip--verified">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
                          Doctor Verified
                        </div>
                      )}
                    </div>
                    {!isEditing ? (
                      <button className="mk-d03-doc__edit" onClick={() => startDocEdit(i, doc.extracted_value ?? "")}>
                        Edit
                      </button>
                    ) : (
                      <div className="mk-d03-doc__correct" data-purpose="doc-correction-form">
                        <input
                          className="mk-d03-input"
                          value={correctionVal}
                          onChange={(e) => setCorrectionVal(e.target.value)}
                          aria-label="Corrected medicine value"
                          onKeyDown={(e) => { if (e.key === "Enter") handleDocCorrection(i); }}
                          autoFocus
                        />
                        <div className="mk-d03-doc__correct-actions">
                          <button className="mk-d03-btn mk-d03-btn--ghost" onClick={() => { setEditingDocIdx(null); setCorrectionVal(""); }} disabled={saving}>
                            Cancel
                          </button>
                          <button className="mk-d03-btn mk-d03-btn--primary" onClick={() => handleDocCorrection(i)} disabled={saving || !correctionVal.trim()}>
                            {saving ? "Saving…" : "Save correction"}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </section>
        </div>
      </div>

      {/* Bottom sticky action bar */}
      <footer className="mk-d03-footer" data-purpose="d03-footer" ref={footerRef}>
        <div className="mk-d03-footer__meta">
          <span className="mk-d03-footer__token">{session.queue_token || "—"}</span>
          <span className="mk-d03-footer__sep">|</span>
          <span>Patient Code: <strong>{session.patient_code || "—"}</strong></span>
          <span className="mk-d03-footer__sep">|</span>
          <span className="mk-d03-footer__status">{confirmed ? "Confirmed" : "Review & Edit"}</span>
        </div>
        <div className="mk-d03-footer__actions">
          <button className="mk-d03-btn mk-d03-btn--ghost" onClick={handleDiscard} disabled={saving}>Discard Changes</button>
          <button className="mk-d03-btn mk-d03-btn--outline" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save Changes"}
          </button>
          <button className="mk-d03-btn mk-d03-btn--primary" onClick={handleConfirm} disabled={saving || confirmed}>
            <span>{confirmed ? "Confirmed" : "Confirm Case"}</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>
            <span className="mk-d03-footer__status-right">| {confirmed ? "Confirmed" : "Review & Edit"}</span>
          </button>
        </div>
      </footer>
      </div>
    </div>
  );
}
