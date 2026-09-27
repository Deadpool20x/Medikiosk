"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LifeBuoy } from "lucide-react";
import { startPatientSession, triggerEmergency } from "../lib/api";
import { pt } from "../lib/i18n";

const LANGUAGE_KEY = "medikiosk_preferred_language";

const VISIT_TYPE_KEY = "medikiosk_visit_type";

export default function HomePage() {
  const router = useRouter();
  const [selectedLanguage, setSelectedLanguage] = useState("en");
  const [visitType, setVisitType] = useState<"new" | "returning">("new");

  const languages = [
    { code: "en", label: "English" },
    { code: "hi", label: "हिन्दी" },
    { code: "gu", label: "ગુજરાતી" },
  ];

  const NAV_KEYS = [
    "nav_language",
    "nav_consent",
    "nav_code",
    "nav_interview",
    "nav_records",
    "nav_summary",
    "nav_token",
  ] as const;

  function handleLanguageClick(code: string) {
    setSelectedLanguage(code);
  }

  function handleContinue() {
    window.sessionStorage.setItem(LANGUAGE_KEY, selectedLanguage);
    window.sessionStorage.setItem(VISIT_TYPE_KEY, visitType);
    router.push("/patient");
  }

  async function handleEmergency() {
    try {
      const res = await startPatientSession(
        { name: "Emergency Walk-In", age: 0, gender: "other" },
        selectedLanguage,
        "new"
      );
      window.sessionStorage.setItem("medikiosk_session_id", res.session_id);
      await triggerEmergency(res.session_id);
    } catch (e) {
      console.error("Emergency trigger from landing page failed:", e);
    } finally {
      router.push("/patient");
    }
  }

  return (
    <div className="mk-p01">
      <header className="mk-p01-header">
        <div className="mk-p01-header__left">
          <svg viewBox="0 0 40 40" fill="none" width="28" height="28" aria-hidden="true">
            <rect width="40" height="40" rx="10" fill="#111111" />
            <path d="M20 10v20M10 20h20" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" />
          </svg>
          <span className="mk-p01-header__brand">MediKiosk</span>
          <span className="mk-p01-header__pill">AYURVEDIC OPD — HALL A</span>
        </div>
        <nav className="mk-p01-header__nav" aria-label={pt(selectedLanguage, "a11y_workflow")}>
          {NAV_KEYS.map((key, i) => (
            <span
              key={key}
              aria-current={i === 0 ? "step" : undefined}
              className={`mk-p01-nav__item ${i === 0 ? "mk-p01-nav__item--active" : ""}`}
            >
              {pt(selectedLanguage, key)}
            </span>
          ))}
        </nav>
        <div className="mk-p01-header__right">
          <button
            type="button"
            onClick={handleEmergency}
            className="mk-btn mk-btn--danger mk-p01-header__action mk-emergency-btn"
            id="mk-always-visible-emergency-btn"
            style={{
              backgroundColor: "#DC2626",
              color: "#FFFFFF",
              fontWeight: 700,
              padding: "6px 12px",
              borderRadius: "6px",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              border: "1px solid #B91C1C",
            }}
            aria-label={pt(selectedLanguage, "emerg_aria")}
          >
            <span aria-hidden="true">🚨</span> {pt(selectedLanguage, "emerg_btn")}
          </button>
          <button className="mk-p01-header__action" aria-label={pt(selectedLanguage, "p01_reset")} type="button"
            onClick={() => { setSelectedLanguage("en"); setVisitType("new"); }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /></svg>
            {pt(selectedLanguage, "p01_reset")}
          </button>
          <button className="mk-p01-header__action" aria-label={pt(selectedLanguage, "p01_help")} type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
            {pt(selectedLanguage, "p01_help")}
          </button>
          <div className="mk-p01-header__avatar" aria-label={pt(selectedLanguage, "a11y_user_menu")}>
            <div className="mk-p01-header__avatar-ring">
              <div className="mk-p01-header__avatar-dot" />
            </div>
          </div>
        </div>
      </header>

      <main className="mk-p01-main">
        <div className="mk-p01-main__left">
          <div className="mk-p01-step">
            <span className="mk-p01-step__label">{pt(selectedLanguage, "p01_step")}</span>
            <div className="mk-p01-step__dots">
              {NAV_KEYS.map((key, i) => (
                <span key={key} className={`mk-p01-step__dot ${i === 0 ? "mk-p01-step__dot--active" : ""}`} />
              ))}
            </div>
          </div>

          <p className="mk-p01-eyebrow">{pt(selectedLanguage, "p01_eyebrow")}</p>
          <h1 className="mk-p01-title">{pt(selectedLanguage, "p01_title")}</h1>
          <p className="mk-p01-desc">
            {pt(selectedLanguage, "p01_desc")}
          </p>

          <div className="mk-p01-section">
            <div className="mk-p01-section__header">
              <h2 className="mk-p01-section__title">{pt(selectedLanguage, "p01_sec1")}</h2>
              <span className="mk-p01-section__hint">{pt(selectedLanguage, "p01_sec1_hint")}</span>
            </div>
            <div className="mk-p01-lang-grid">
              {languages.map((lang) => (
                <button
                  key={lang.code}
                  type="button"
                  className={`mk-btn mk-btn--secondary mk-p01-lang-card ${selectedLanguage === lang.code ? "mk-p01-lang-card--active" : ""}`}
                  onClick={() => handleLanguageClick(lang.code)}
                >
                  <span className="mk-p01-lang-card__code">{lang.code.toUpperCase()}</span>
                  <span className="mk-p01-lang-card__label">{lang.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="mk-p01-section">
            <div className="mk-p01-section__header">
              <h2 className="mk-p01-section__title">{pt(selectedLanguage, "p01_sec2")}</h2>
              <span className="mk-p01-section__hint">{pt(selectedLanguage, "p01_sec2_hint")}</span>
            </div>
            <div className="mk-p01-status-grid">
              <button
                type="button"
                className={`mk-btn mk-btn--secondary mk-p01-status-card ${visitType === "new" ? "mk-p01-status-card--active" : ""}`}
                onClick={() => setVisitType("new")}
                aria-pressed={visitType === "new"}
              >
                <span className="mk-p01-status-card__dot" />
                <div>
                  <span className="mk-p01-status-card__label">{pt(selectedLanguage, "p01_new")}</span>
                  <span className="mk-p01-status-card__sub">{pt(selectedLanguage, "p01_new_sub")}</span>
                </div>
              </button>
              <button
                type="button"
                className={`mk-btn mk-btn--secondary mk-p01-status-card ${visitType === "returning" ? "mk-p01-status-card--active" : ""}`}
                onClick={() => setVisitType("returning")}
                aria-pressed={visitType === "returning"}
              >
                <span className="mk-p01-status-card__dot" />
                <div>
                  <span className="mk-p01-status-card__label">{pt(selectedLanguage, "p01_ret")}</span>
                  <span className="mk-p01-status-card__sub">{pt(selectedLanguage, "p01_ret_sub")}</span>
                </div>
              </button>
            </div>
          </div>

          <button
            type="button"
            className="mk-btn mk-btn--primary mk-p01-cta"
            onClick={handleContinue}
          >
            {pt(selectedLanguage, "p01_cta")}
          </button>
        </div>

        <div className="mk-p01-main__right">
          <div className="mk-p01-howitworks">
            <h2 className="mk-p01-howitworks__title">{pt(selectedLanguage, "p01_how")}</h2>
            <div className="mk-p01-howitworks__list">
              <div className="mk-p01-howitworks__row">
                <div className="mk-p01-howitworks__icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>
                </div>
                <div>
                  <p className="mk-p01-howitworks__row-title">{pt(selectedLanguage, "p01_voice_t")}</p>
                  <p className="mk-p01-howitworks__row-desc">{pt(selectedLanguage, "p01_voice_d")}</p>
                </div>
              </div>
              <div className="mk-p01-howitworks__row">
                <div className="mk-p01-howitworks__icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
                </div>
                <div>
                  <p className="mk-p01-howitworks__row-title">{pt(selectedLanguage, "p01_rec_t")}</p>
                  <p className="mk-p01-howitworks__row-desc">{pt(selectedLanguage, "p01_rec_d")}</p>
                </div>
              </div>
              <div className="mk-p01-howitworks__row">
                <div className="mk-p01-howitworks__icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5"><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg>
                </div>
                <div>
                  <p className="mk-p01-howitworks__row-title">{pt(selectedLanguage, "p01_doc_t")}</p>
                  <p className="mk-p01-howitworks__row-desc">{pt(selectedLanguage, "p01_doc_d")}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="mk-p01-queue">
            <h3 className="mk-p01-queue__title">{pt(selectedLanguage, "p01_queue_t")}</h3>
            <div className="mk-p01-queue__body">
              <span className="mk-p01-queue__label">{pt(selectedLanguage, "p01_queue_label")}</span>
            </div>
            <progress
              className="mk-p01-queue__bar"
              aria-label={pt(selectedLanguage, "p01_queue_aria")}
            />
          </div>

          <div className="mk-p01-assistance">
            <div className="mk-p01-assistance__icon">
              <LifeBuoy className="w-5 h-5" aria-hidden="true" />
            </div>
            <div>
              <p className="mk-p01-assistance__title">{pt(selectedLanguage, "p01_help_t")}</p>
              <p className="mk-p01-assistance__desc">{pt(selectedLanguage, "p01_help_d")}</p>
            </div>
            <button className="mk-btn mk-p01-assistance__btn" type="button">{pt(selectedLanguage, "p01_help_btn")}</button>
          </div>
        </div>
      </main>

      <footer className="mk-p01-footer">
        <div className="mk-p01-footer__left">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 mk-p01-footer__lock"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
          <span>{pt(selectedLanguage, "p01_secure")}</span>
        </div>
      </footer>
    </div>
  );
}