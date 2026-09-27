"use client";

import { useState } from "react";
import type { Session, DocumentField } from "@/lib/types";
import { requestToken } from "@/lib/api";
import { pt } from "@/lib/i18n";

interface PatientConfirmProps {
  session: Session;
  sessionId: string;
  patientCode?: string;
  language?: string;
  onReset: () => void;
  onBackToRecords?: () => void;
  onTokenGenerated?: (token: string, department: string) => void;
}

export default function PatientConfirm({ session, sessionId, patientCode, language: languageProp, onReset, onBackToRecords, onTokenGenerated }: PatientConfirmProps) {
  const language = languageProp ?? session.language ?? "en";
  const [tokenLoading, setTokenLoading] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);

  async function handleConfirm() {
    if (!sessionId) return;
    setTokenLoading(true);
    setTokenError(null);
    try {
      const resp = await requestToken(sessionId);
      onTokenGenerated?.(resp.token, resp.department || pt(language, "dept_general"));
    } catch (e) {
      setTokenError((e as Error).message || pt(language, "r_failed"));
    } finally {
      setTokenLoading(false);
    }
  }

  const hpi = session.history_of_present_illness;
  const docs = session.documents ?? [];

  return (
    <div className="mk-p07">
      <div className="mk-p07-content">
        <span className="mk-p07-eyebrow">{pt(language, "r_eyebrow")}</span>
        <h1 className="mk-p07-h1">{pt(language, "r_title")}</h1>
        <p className="mk-p07-sub">
          {pt(language, "r_sub")}
        </p>

        <div className="mk-p07-card">
          {/* Section 1: Chief Complaint & Symptoms */}
          <section className="mk-p07-section">
            <div className="mk-p07-section__head">
              <div className="mk-p07-section__title-row">
                <svg className="mk-p07-section__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3" /><path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4" /><circle cx="20" cy="10" r="2" /></svg>
                <h2 className="mk-p07-section__title">{pt(language, "r_sec1")}</h2>
              </div>
              <button type="button" className="mk-p07-btn mk-p07-btn--pill" onClick={() => onReset?.()}>
                <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                {pt(language, "d_edit")}
              </button>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">{pt(language, "r_primary")}</span>
              <div className="mk-p07-grid__value mk-p07-grid__value--bold">
                {session.chief_complaint || pt(language, "r_not_provided")}
              </div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">{pt(language, "r_duration")}</span>
              <div className="mk-p07-grid__value">
                {[hpi?.onset || pt(language, "r_not_specified"),
                  hpi?.duration ? pt(language, "r_for", { v: hpi.duration }) : "",
                  hpi?.severity ? pt(language, "r_severity", { v: hpi.severity }) : "",
                  hpi?.character ? `, ${hpi.character}` : ""]
                  .filter(Boolean).join(" ").replace(" ,", ",")}
              </div>
            </div>
            <div className="mk-p07-provenance">
              <span className="mk-p07-provenance__dot" />
              {pt(language, "r_provenance")}
            </div>
          </section>

          <div className="mk-p07-divider" />

          {/* Section 2: Medical & Health History */}
          <section className="mk-p07-section">
            <div className="mk-p07-section__head">
              <div className="mk-p07-section__title-row">
                <svg className="mk-p07-section__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 6v14" /><path d="M8 10h8" /><rect x="3" y="3" width="18" height="18" rx="3" /></svg>
                <h2 className="mk-p07-section__title">{pt(language, "r_sec2")}</h2>
              </div>
              <button type="button" className="mk-p07-btn mk-p07-btn--pill" onClick={() => onReset?.()}>
                <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                {pt(language, "d_edit")}
              </button>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">{pt(language, "r_past")}</span>
              <div className="mk-p07-grid__value">
                {hpi?.associated_symptoms && hpi.associated_symptoms.length > 0
                  ? hpi.associated_symptoms.join(", ")
                  : pt(language, "r_none_reported")}
              </div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">{pt(language, "r_hist_med")}</span>
              <div className="mk-p07-grid__value-row">
                {docs.length > 0 ? (
                  <>
                    <span className="mk-p07-grid__value">
                      {docs.map((f: DocumentField) => f.extracted_value || `${f.strength || ""} ${f.dose || ""}`.trim()).filter(Boolean).join(", ") || pt(language, "r_none")}
                    </span>
                    <span className="mk-p07-provenance-chip">{pt(language, "d_from_doc")}</span>
                  </>
                ) : (
                  <span className="mk-p07-grid__value">{pt(language, "r_none")}</span>
                )}
              </div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">{pt(language, "r_allergies")}</span>
              <div className="mk-p07-grid__value">{pt(language, "r_no_allergies")}</div>
            </div>
            <div className="mk-p07-provenance">
              <span className="mk-p07-provenance__dot" />
              {pt(language, "r_provenance2")}
            </div>
          </section>

          <div className="mk-p07-divider" />

          {/* Section 3: Ayurvedic Assessment */}
          <section className="mk-p07-section">
            <div className="mk-p07-section__head mk-p07-section__head--tight">
              <div className="mk-p07-section__title-row">
                <svg className="mk-p07-section__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
                <h2 className="mk-p07-section__title">{pt(language, "r_sec3")}</h2>
              </div>
              <button type="button" className="mk-p07-btn mk-p07-btn--pill" onClick={() => onReset?.()}>
                <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                {pt(language, "d_edit")}
              </button>
            </div>
            <p className="mk-p07-section__desc">
              {pt(language, "r_sec3_desc")}
            </p>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Prakriti</span>
              <div className="mk-p07-grid__value">{pt(language, "r_not_collected")}</div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Agni</span>
              <div className="mk-p07-grid__value">{pt(language, "r_not_collected")}</div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Koshtha</span>
              <div className="mk-p07-grid__value">{pt(language, "r_not_collected")}</div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Nidana</span>
              <div className="mk-p07-grid__value">{pt(language, "r_not_collected")}</div>
            </div>
            <div className="mk-p07-grid">
              <span className="mk-p07-grid__label">Ahara / Vihara</span>
              <div className="mk-p07-grid__value">{pt(language, "r_not_collected")}</div>
            </div>
          </section>

          <div className="mk-p07-divider" />

          {/* Section 4: Uploaded Document & Extracted Records */}
          <section className="mk-p07-section">
            <div className="mk-p07-section__head">
              <div className="mk-p07-section__title-row">
                <svg className="mk-p07-section__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
                <h2 className="mk-p07-section__title">{pt(language, "r_sec4")}</h2>
              </div>
              <button type="button" className="mk-p07-btn mk-p07-btn--pill" onClick={onBackToRecords}>
                <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                {pt(language, "d_edit")}
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
                      {docs[0].type === "prescription" ? pt(language, "r_prescription") : docs[0].type === "lab_report" ? pt(language, "r_lab") : pt(language, "r_uploaded_doc")}
                    </p>
                    <p className="mk-p07-doc-badge__detail">{pt(language, "r_attached_doc")}</p>
                  </div>
                  <div className="mk-p07-doc-badge__status">
                    <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
                    {pt(language, "r_attached")}
                  </div>
                </div>
                <div className="mk-p07-doc-fields">
                  {docs.map((f: DocumentField, i: number) => (
                    <div key={i} className="mk-p07-grid">
                      <span className="mk-p07-grid__label">
                        {f.type === "prescription" ? pt(language, "r_medication") : f.type === "lab_report" ? pt(language, "r_lab_result") : pt(language, "r_field")}
                      </span>
                      <div className="mk-p07-grid__value">
                        {f.extracted_value || `${f.strength || ""} ${f.dose || ""} ${f.frequency || ""}`.trim() || pt(language, "r_no_value")}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mk-p07-provenance-row">
                  <span className="mk-p07-provenance-chip">
                    <span className="mk-p07-provenance-chip__dot" />
                    {pt(language, "d_from_doc")}
                  </span>
                  {docs.some((f) => f.confidence > 0.8) && (
                    <span className="mk-p07-confidence-chip">{pt(language, "d_high")} {pt(language, "d_conf")}</span>
                  )}
                </div>
              </>
            ) : (
              <div className="mk-p07-empty-state">
                <p>{pt(language, "r_no_docs")}</p>
              </div>
            )}
          </section>
        </div>

        <div className="mk-p07-notice">
          <svg className="mk-p07-notice__icon" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></svg>
          <p>{pt(language, "r_notice")}</p>
        </div>

        <div className="mk-p07-actions">
          <button type="button" className="mk-p07-btn mk-p07-btn--secondary" onClick={onBackToRecords}>
            <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></svg>
            {pt(language, "r_back")}
          </button>
          <button
            type="button"
            className="mk-p07-btn mk-p07-btn--primary"
            onClick={handleConfirm}
            disabled={tokenLoading}
          >
            {tokenLoading ? pt(language, "r_generating") : pt(language, "r_confirm")}
            {!tokenLoading && <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>}
          </button>
        </div>

        {tokenError && (
          <p className="mk-p07-error" role="alert">{tokenError}</p>
        )}

        <div className="mk-p07-footer-stamp">
          <p>{pt(language, "footer")}</p>
        </div>
      </div>
    </div>
  );
}
