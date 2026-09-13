"use client";

import { useEffect, useRef, useState } from "react";
import { getDoctorSession, patchDoctorSession, correctDoctorDocument } from "../lib/api";
import type { Session } from "../lib/types";

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

function currentMeds(s: Session): Array<{ name: string; detail: string }> {
  const out: Array<{ name: string; detail: string }> = [];
  for (const doc of s.documents) {
    const name = (doc.extracted_value || "").trim();
    if (!name) continue;
    const detail = [doc.strength, doc.dose, doc.frequency].filter(Boolean).join(" · ");
    out.push({ name, detail });
  }
  return out;
}

function hpiPill(s: Session, field: string): ConfState {
  const rec = s.answer_records.find((r) => r.question === field);
  if (rec) return confidenceState(rec.needs_review, false);
  return "high";
}

function hpiTooltipValue(s: Session, field: string): string {
  const rec = s.answer_records.find((r) => r.question === field);
  if (!rec) return "Patient-entered value";
  const prov = rec.provider ? `AI extraction (${rec.provider})` : "AI extraction";
  return `${prov} · ${CONF_LABEL[confidenceState(rec.needs_review, false)]}`;
}

function ConfPill({ state, title }: { state: ConfState; title?: string }) {
  return <span className={`mk-d02-pill mk-d02-pill--${state}`} title={title}>{CONF_LABEL[state]}</span>;
}

function SectionHead({ number, title, badge }: { number: string; title: string; badge: string }) {
  return (
    <div className="mk-d02-head">
      <div className="mk-d02-head__title">
        <span className="mk-d02-head__bar" aria-hidden="true" />
        <h2>{number}. {title}</h2>
      </div>
      <span className="mk-d02-badge">{badge}</span>
    </div>
  );
}

function HpiCell({ label, value, detail, state, note }: {
  label: string; value: string; detail?: string; state?: ConfState; note?: string;
}) {
  return (
    <div className="mk-d02-cell">
      <span className="mk-d02-cell__label">{label}</span>
      <span className="mk-d02-cell__value">{value || "—"}</span>
      {detail && <span className="mk-d02-cell__value">{detail}</span>}
      {state && <span className="mk-d02-cell__meta"><ConfPill state={state} title={note} /></span>}
    </div>
  );
}

export function DoctorCase({
  sessionId,
  onBack,
  onEdit,
}: {
  sessionId: string;
  onBack: () => void;
  onEdit?: () => void;
}) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const rootRef = useRef<HTMLDivElement | null>(null);
  const footerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const root = rootRef.current;
    const footer = footerRef.current;
    if (!root || !footer) return;
    const MIN = 104;
    const update = () => {
      root.style.setProperty("--d02-bottom-space", `${Math.max(MIN, footer.offsetHeight + 16)}px`);
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

  async function handleConfirm() {
    if (!session) return;
    setSaving(true);
    setError(null);
    try {
      const next = await patchDoctorSession(sessionId, { doctor_confirmed: !session.doctor_review.confirmed });
      setSession(next);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDocCorrection(index: number, corrected_value: string) {
    setError(null);
    try {
      const next = await correctDoctorDocument(sessionId, index, { corrected_value });
      setSession(next);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (loading) return <p className="mk-page-desc">Loading case…</p>;

  if (!session) {
    return (
      <div>
        {error && <div className="mk-error-banner" role="alert">{error}</div>}
        <button className="mk-button mk-button--secondary" onClick={onBack}>← Back to Queue</button>
      </div>
    );
  }

  if (session.safety_flagged) {
    return (
      <div className="mk-d02">
        <button className="mk-d02-back" onClick={onBack}>← Back to Queue</button>
        <div className="mk-d02-safety" role="alert" data-purpose="safety-flagged-case">
          <div className="mk-d02-safety__icon">!</div>
          <div>
            <h2>Safety Flagged — Not a standard queue case</h2>
            <p>This session was paused for safety review and did not receive a normal department queue token.</p>
            {session.safety_detail.length > 0 && (
              <ul>
                {session.safety_detail.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            )}
          </div>
        </div>
      </div>
    );
  }

  const hpi = session.history_of_present_illness;
  const meds = currentMeds(session);
  const checkIn = firstAnswerTime(session);
  const confirmed = session.doctor_review.confirmed;

  return (
    <div className="mk-d02" ref={rootRef}>
      <button className="mk-d02-back" onClick={onBack}>← Back to Queue</button>

      <section className="mk-d02-header" data-purpose="patient-header">
        <div className="mk-d02-idents">
          <div className="mk-d02-ident mk-d02-ident--token">
            <span className="mk-d02-ident__label">Queue Token</span>
            <span className="mk-d02-ident__value">{session.queue_token || "—"}</span>
          </div>
          <div className="mk-d02-divider" aria-hidden="true" />
          <div className="mk-d02-ident">
            <span className="mk-d02-ident__label">Patient Code</span>
            <span className="mk-d02-ident__value">{session.patient_code || "—"}</span>
          </div>
          <div className="mk-d02-divider" aria-hidden="true" />
          <div className="mk-d02-ident">
            <span className="mk-d02-ident__label">Department</span>
            <span className="mk-d02-ident__value">{depLabel(session.department)}</span>
          </div>
          {checkIn && (
            <>
              <div className="mk-d02-divider" aria-hidden="true" />
              <div className="mk-d02-ident">
                <span className="mk-d02-ident__label">Check-in Time</span>
                <span className="mk-d02-ident__value">{formatClock(checkIn)}</span>
              </div>
            </>
          )}
        </div>
        <div className="mk-d02-header__actions">
          <span className={`mk-d02-status mk-d02-status--${confirmed ? "confirmed" : "review"}`}>
            <span className="mk-d02-status__dot" aria-hidden="true" />
            {confirmed ? "Case Confirmed" : "Awaiting Doctor Review"}
          </span>
          <button className="mk-button mk-button--primary" onClick={onEdit}>
            Review / Edit Case
          </button>
        </div>
      </section>

      {error && <div className="mk-error-banner" role="alert" style={{ margin: "16px 0" }}>{error}</div>}

      <div className="mk-d02-grid">
        <div className="mk-d02-left">
          <section className="mk-d02-card" data-purpose="chief-complaint-section">
            <SectionHead number="1" title="Chief Complaint & History of Present Illness (HPI)" badge="Source: Patient Interview" />
            <div className="mk-d02-report">
              <span className="mk-d02-report__label">Reported Complaint</span>
              <p className="mk-d02-report__text">{session.chief_complaint || "—"}</p>
            </div>
            <div className="mk-d02-cells">
              <HpiCell
                label="Onset & Duration"
                value={hpi.onset || "—"}
                detail={hpi.duration || "—"}
                state={hpiPill(session, "onset")}
                note={hpiTooltipValue(session, "onset")}
              />
              <HpiCell
                label="Character & Severity"
                value={hpi.character || "—"}
                detail={hpi.severity || "—"}
                state={hpiPill(session, "character")}
                note={hpiTooltipValue(session, "character")}
              />
              <HpiCell
                label="Associated Symptoms"
                value={hpi.associated_symptoms.length > 0 ? hpi.associated_symptoms.join(", ") : "—"}
                state={hpiPill(session, "associated_symptoms")}
                note={hpiTooltipValue(session, "associated_symptoms")}
              />
            </div>
          </section>

          <section className="mk-d02-card" data-purpose="medical-history-section">
            <SectionHead number="2" title="Medical & Health History" badge="Source: Patient Interview" />
            {meds.length > 0 ? (
              <div className="mk-d02-cells">
                {meds.map((m, i) => (
                  <div key={i} className="mk-d02-cell">
                    <span className="mk-d02-cell__label">
                      Current Medications
                      <span className="mk-d02-badge mk-d02-badge--mini">From uploaded document</span>
                    </span>
                    <span className="mk-d02-cell__value">{m.name}</span>
                    {m.detail && <span className="mk-d02-cell__value">{m.detail}</span>}
                  </div>
                ))}
                <div className="mk-d02-empty">
                  No other medical history (past history, allergies, family history) was recorded during this visit.
                </div>
              </div>
            ) : (
              <div className="mk-d02-empty">
                No medical / health history beyond the chief complaint and HPI was recorded in this visit.
              </div>
            )}
          </section>

          <section className="mk-d02-card" data-purpose="ayurvedic-assessment-section">
            <SectionHead number="3" title="Ayurvedic Baseline Assessment" badge="Recorded Baseline • Uninterpreted" />
            <p className="mk-d02-none">Patient-reported characteristics only; no clinical diagnosis or dosha classification inferred.</p>
            <div className="mk-d02-empty">
              No Ayurvedic baseline was recorded for this visit. The current intake captures only the chief complaint and HPI.
            </div>
          </section>
        </div>

        <aside className="mk-d02-right">
          <section className="mk-d02-card" data-purpose="document-extraction-section">
            <div className="mk-d02-head">
              <div className="mk-d02-head__title">
                <span className="mk-d02-head__bar" aria-hidden="true" />
                <h2>4. Uploaded Documents</h2>
              </div>
              <span className="mk-d02-count">{session.documents.length} {session.documents.length === 1 ? "Document" : "Documents"}</span>
            </div>
            {session.documents.length === 0 ? (
              <div className="mk-d02-empty">No documents were uploaded for this visit.</div>
            ) : (
              session.documents.map((doc, i) => {
                const extra = [doc.strength, doc.dose, doc.frequency].filter(Boolean).join(" · ");
                const state = confidenceState(doc.needs_review, doc.manually_corrected);
                return (
                  <div key={i} className="mk-d02-doc">
                    <div className="mk-d02-doc__head">
                      <div className="mk-d02-doc__file">
                        <span className="mk-d02-doc__icon">▤</span>
                        <div>
                          <div className="mk-d02-doc__name">{doc.type === "prescription" ? "Uploaded prescription" : doc.type === "lab_report" ? "Uploaded lab report" : "Uploaded document"}</div>
                          <div className="mk-d02-doc__meta">{doc.source === "ocr" ? "OCR extraction" : doc.source === "voice" ? "Voice note" : "Manual entry"}</div>
                        </div>
                      </div>
                      <ConfPill state={state} />
                    </div>
                    <div className="mk-d02-doc__body">
                      <span className="mk-d02-doc__extract-label">Extracted Content:</span>
                      <p className="mk-d02-doc__extract">
                        <span>{doc.extracted_value || "No medicine could be read from this document."}</span>
                        {extra && <span className="mk-d02-doc__extra">{extra}</span>}
                      </p>
                      <div className="mk-d02-doc__foot">
                        <span>Status: {doc.manually_corrected ? "Manually corrected" : doc.needs_review ? "Reviewable by doctor" : "Reviewed"}</span>
                      </div>
                      {!doc.manually_corrected && (
                        <div className="mk-d02-fix">
                          <input
                            className="mk-input"
                            defaultValue={doc.extracted_value ?? ""}
                            placeholder="Correct extracted medicine"
                            aria-label="Corrected medicine value"
                            onKeyDown={(e) => {
                              if (e.key === "Enter" && (e.target as HTMLInputElement).value.trim()) {
                                handleDocCorrection(i, (e.target as HTMLInputElement).value.trim());
                              }
                            }}
                          />
                          <button
                            className="mk-button mk-button--secondary"
                            onClick={(e) => {
                              const inp = e.currentTarget.previousElementSibling as HTMLInputElement;
                              if (inp.value.trim()) handleDocCorrection(i, inp.value.trim());
                            }}
                            disabled={saving}
                          >
                            Save correction
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </section>
        </aside>
      </div>

      <footer className="mk-d02-footer" data-purpose="case-action-bar" ref={footerRef}>
        <div className="mk-d02-footer__meta">
          <span className="mk-d02-footer__token">{session.queue_token || "—"}</span>
          <span className="mk-d02-footer__sep">|</span>
          <span>Patient Code: {session.patient_code || "—"}</span>
          <span className="mk-d02-footer__sep mk-d02-footer__sep--hide" aria-hidden="true">|</span>
          <span className="mk-d02-footer__status mk-d02-footer__status--hide">
            Status: {confirmed ? "Confirmed" : "Awaiting Doctor Review"}
          </span>
        </div>
        <div className="mk-d02-footer__actions">
          <button className="mk-button mk-button--secondary" onClick={handleConfirm} disabled={saving}>
            {confirmed ? "Confirmed" : "Confirm Case"}
          </button>
          <button className="mk-button mk-button--primary" onClick={onEdit}>
            Review & Edit Case Details →
          </button>
        </div>
      </footer>
    </div>
  );
}
