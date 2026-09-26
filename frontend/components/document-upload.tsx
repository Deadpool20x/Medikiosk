"use client";

import { useRef, useState, useCallback } from "react";
import { uploadDocument, correctDocument } from "../lib/api";
import { pt } from "../lib/i18n";

type Stage = "idle" | "selected" | "processing" | "extracted" | "review" | "error";

const ACCEPTED = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/tiff"];
const MAX_BYTES = 8 * 1024 * 1024;

interface DocResult {
  medicine: string;
  strength: string;
  dose: string;
  frequency: string;
  confidence: number;
  needs_review: boolean;
  file: File;
}

const FIELD_META: Array<{ key: keyof Omit<DocResult, "file" | "confidence" | "needs_review">; langKey: "d_med" | "d_strength" | "d_dose" | "d_freq" }> = [
  { key: "medicine", langKey: "d_med" },
  { key: "strength", langKey: "d_strength" },
  { key: "dose", langKey: "d_dose" },
  { key: "frequency", langKey: "d_freq" },
];

function confidenceLabel(lang: string, c: number) {
  return pt(lang, c >= 0.5 ? "d_high" : "d_low");
}

export function DocumentUpload({
  sessionId,
  onContinue,
  onSkip,
  language = "en",
}: {
  sessionId: string;
  onContinue: () => void;
  onSkip: () => void;
  language?: string;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [docs, setDocs] = useState<DocResult[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const resetUpload = useCallback(() => {
    setFile(null);
    setStage("idle");
    setError(null);
  }, []);

  function pickFile(f: File | null) {
    setError(null);
    if (!f) return;
    if (!ACCEPTED.includes(f.type)) {
      setError(pt(language, "d_badtype"));
      return;
    }
    if (f.size > MAX_BYTES) {
      setError(pt(language, "d_toolarge"));
      return;
    }
    setFile(f);
    setStage("selected");
  }

  async function analyze(f: File) {
    setStage("processing");
    setError(null);
    try {
      const res = await uploadDocument(sessionId, f);
      const doc: DocResult = {
        medicine: res.medicine ?? "",
        strength: res.strength ?? "",
        dose: res.dose ?? "",
        frequency: res.frequency ?? "",
        confidence: res.confidence,
        needs_review: res.needs_review,
        file: f,
      };
      const nextDocs = [...docs, doc];
      setDocs(nextDocs);
      setSelectedIndex(nextDocs.length - 1);
      setStage(doc.needs_review ? "review" : "extracted");
    } catch (e) {
      setError((e as Error).message);
      setStage("error");
    }
  }

  async function handleSaveCorrection() {
    if (selectedIndex === null) return;
    const doc = docs[selectedIndex];
    try {
      await correctDocument(sessionId, selectedIndex, {
        corrected_value: doc.medicine || undefined,
        strength: doc.strength || undefined,
        dose: doc.dose || undefined,
        frequency: doc.frequency || undefined,
      });
    } catch {
      // best-effort; do not block intake
    }
    setDocs((prev) => {
      const next = [...prev];
      if (selectedIndex !== null && next[selectedIndex]) {
        next[selectedIndex] = { ...next[selectedIndex], needs_review: false };
      }
      return next;
    });
    setStage("extracted");
  }

  async function handleContinueWithSave() {
    if (activeDoc && selectedIndex !== null) {
      try {
        await correctDocument(sessionId, selectedIndex, {
          corrected_value: activeDoc.medicine || undefined,
          strength: activeDoc.strength || undefined,
          dose: activeDoc.dose || undefined,
          frequency: activeDoc.frequency || undefined,
        });
      } catch {
        // best-effort; do not block intake
      }
    }
    onContinue();
  }

  function handleRetry() {
    if (file) {
      analyze(file);
    } else {
      setStage("idle");
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.[0]) {
      pickFile(e.dataTransfer.files[0]);
    }
  }

  const activeDoc = selectedIndex !== null && selectedIndex < docs.length ? docs[selectedIndex] : null;
  const isResult = stage === "extracted" || stage === "review";

  return (
    <>
      <div className="mk-p06-title">
        <div className="mk-p06-title__row">
          <span className="mk-p06-eyebrow">{pt(language, "d_eyebrow")}</span>
        </div>
        <h1 className="mk-p06-h1">{pt(language, "d_title")}</h1>
        <p className="mk-p06-sub">
          {pt(language, "d_sub")}
        </p>
      </div>

      <div className="mk-p06-card">
        {/* Upload zone — idle / error */}
        {(stage === "idle" || stage === "error") && (
          <>
            <div className="mk-p06-doc-header">
              <span className="mk-p06-doc-header__label">{pt(language, "d_uploaded")}</span>
              <span className="mk-p06-doc-header__types">{pt(language, "d_types")}</span>
            </div>
            <button
              type="button"
              className={`mk-p06-dropzone ${dragOver ? "mk-p06-dropzone--over" : ""}`}
              onClick={() => fileInput.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              <span className="mk-p06-dropzone__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 16V4m0 0l-4 4m4-4l4 4" />
                  <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
                </svg>
              </span>
              <span className="mk-p06-dropzone__title">{pt(language, "d_choose")}</span>
              <span className="mk-p06-dropzone__sub">{pt(language, "d_formats")}</span>
            </button>
            {error && <div className="mk-p06-error" role="alert">{error}</div>}
            {stage === "error" && (
              <button type="button" className="mk-p06-retry-btn" onClick={handleRetry}>
                {pt(language, "d_retry")}
              </button>
            )}
          </>
        )}

        {/* Selected — file preview before upload */}
        {stage === "selected" && file && (
          <>
            <div className="mk-p06-doc-header">
              <span className="mk-p06-doc-header__label">{pt(language, "d_uploaded")}</span>
              <span className="mk-p06-doc-header__types">{pt(language, "d_types")}</span>
            </div>
            <div className="mk-p06-file-box">
              <div className="mk-p06-file-box__left">
                <div className="mk-p06-file-box__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6" />
                  </svg>
                </div>
                <div className="mk-p06-file-box__meta">
                  <span className="mk-p06-file-box__name">{file.name}</span>
                  <span className="mk-p06-file-box__detail">{file.type} • {(file.size / (1024 * 1024)).toFixed(1)} MB</span>
                </div>
              </div>
              <div className="mk-p06-file-box__actions">
                <button type="button" className="mk-p06-file-box__cancel" onClick={resetUpload}>{pt(language, "d_cancel")}</button>
                <button type="button" className="mk-p06-file-box__upload" onClick={() => analyze(file)}>{pt(language, "d_upload")}</button>
              </div>
            </div>
          </>
        )}

        {/* Processing */}
        {stage === "processing" && (
          <div className="mk-p06-processing">
            <span className="mk-p06-spinner" aria-hidden="true" />
            <p className="mk-p06-processing__title">{pt(language, "d_reading_t")}</p>
            <p className="mk-p06-processing__sub">{pt(language, "d_reading_s")}</p>
          </div>
        )}

        {/* Extracted / Review */}
        {isResult && activeDoc && (
          <>
            {/* File presentation box */}
            <div className="mk-p06-doc-header">
              <span className="mk-p06-doc-header__label">{pt(language, "d_uploaded")}</span>
              <span className="mk-p06-doc-header__types">{pt(language, "d_types")}</span>
            </div>
            <div className="mk-p06-file-box">
              <div className="mk-p06-file-box__left">
                <div className="mk-p06-file-box__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <path d="M14 2v6h6" />
                  </svg>
                </div>
                <div className="mk-p06-file-box__meta">
                  <div className="mk-p06-file-box__name-row">
                    <span className="mk-p06-file-box__name">{activeDoc.file.name}</span>
                    {activeDoc.needs_review && (
                      <span className="mk-p06-badge mk-p06-badge--review">{pt(language, "d_needs_review")}</span>
                    )}
                    <span className="mk-p06-badge mk-p06-badge--uploaded">{pt(language, "d_uploaded_badge")}</span>
                  </div>
                  <span className="mk-p06-file-box__detail">
                    {activeDoc.file.type} • {(activeDoc.file.size / (1024 * 1024)).toFixed(1)} MB • {pt(language, "d_analyzed")}
                  </span>
                </div>
              </div>
              <div className="mk-p06-file-box__actions">
                <button type="button" className="mk-p06-file-box__replace" onClick={resetUpload}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p06-file-box__replace-icon">
                    <path d="M21 2v6h-6" /><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M3 22v-6h6" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
                  </svg>
                  {pt(language, "d_replace")}
                </button>
                <button type="button" className="mk-p06-file-box__delete" onClick={resetUpload} aria-label={pt(language, "d_remove")}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 6h18" /><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" /><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Extracted Information Preview */}
            <div className="mk-p06-extracted">
              <div className="mk-p06-extracted__header">
                <div className="mk-p06-extracted__title-row">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p06-extracted__icon">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M8 13h3" /><path d="M16 13h-2" /><path d="M8 17h8" />
                  </svg>
                  <h2 className="mk-p06-extracted__heading">{pt(language, "d_preview")}</h2>
                </div>
                <div className="mk-p06-extracted__meta">
                  <span className="mk-p06-badge mk-p06-badge--source">{pt(language, "d_from_doc")}</span>
                  <span className="mk-p06-extracted__meta-sep">•</span>
                  <span className="mk-p06-extracted__meta-hint">{pt(language, "d_review_hint")}</span>
                </div>
              </div>

              {stage === "review" && (
                <div className="mk-p06-review-alert" role="alert">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p06-review-alert__icon">
                    <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <span>{pt(language, "d_unread")}</span>
                </div>
              )}

              <div className="mk-p06-fields">
                {FIELD_META.map(({ key, langKey }) => (
                  <div key={key} className="mk-p06-field">
                    <div className="mk-p06-field__left">
                      <span className="mk-p06-field__label">{pt(language, langKey)} {pt(language, "d_field_suffix")}</span>
                      {stage === "review" ? (
                        <input
                          className="mk-p06-field__input"
                          value={activeDoc[key] ?? ""}
                          onChange={(e) => setDocs((prev) => {
                            const next = [...prev];
                            if (selectedIndex !== null && next[selectedIndex]) {
                              next[selectedIndex] = { ...next[selectedIndex], [key]: e.target.value };
                            }
                            return next;
                          })}
                        />
                      ) : (
                        <span className="mk-p06-field__value">{activeDoc[key] || "—"}</span>
                      )}
                    </div>
                    <div className="mk-p06-field__right">
                      <span className={`mk-p06-badge mk-p06-badge--confidence ${activeDoc.confidence >= 0.5 ? "" : "mk-p06-badge--confidence--low"}`}>
                        {confidenceLabel(language, activeDoc.confidence)} {pt(language, "d_conf")}
                      </span>
                      {stage === "review" ? (
                        <button type="button" className="mk-p06-field__edit" onClick={handleSaveCorrection}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p06-field__edit-icon">
                            <path d="M20 6L9 17l-5-5" />
                          </svg>
                          {pt(language, "d_save")}
                        </button>
                      ) : (
                        <button type="button" className="mk-p06-field__edit" onClick={() => setStage("review")}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p06-field__edit-icon">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                          </svg>
                          {pt(language, "d_edit")}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mk-p06-disclaimer">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p06-disclaimer__icon">
                  <circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
                <p>
                  {pt(language, "d_disclaimer")}
                </p>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Actions */}
      <div className="mk-p06-actions">
        <button
          type="button"
          className="mk-p06-btn mk-p06-btn--skip"
          onClick={onSkip}
          disabled={stage === "processing"}
        >
          {pt(language, "d_skip")}
        </button>
        {stage === "review" ? (
          <button
            type="button"
            className="mk-p06-btn mk-p06-btn--continue"
            onClick={handleSaveCorrection}
          >
            {pt(language, "d_save_corr")}
          </button>
        ) : (
          <button
            type="button"
            className="mk-p06-btn mk-p06-btn--continue"
            onClick={handleContinueWithSave}
            disabled={stage === "processing" || stage === "idle" || stage === "selected" || stage === "error"}
          >
            {pt(language, "d_continue")}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mk-p06-btn__icon">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        )}
      </div>

      <input
        ref={fileInput}
        type="file"
        accept={ACCEPTED.join(",")}
        className="mk-visually-hidden"
        onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
      />
    </>
  );
}
