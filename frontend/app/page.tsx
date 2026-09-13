"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const LANGUAGE_KEY = "medikiosk_preferred_language";

export default function HomePage() {
  const router = useRouter();
  const [selectedLanguage, setSelectedLanguage] = useState("en");

  const languages = [
    { code: "en", label: "English" },
    { code: "hi", label: "हिन्दी" },
    { code: "mr", label: "मराठी" },
    { code: "gu", label: "ગુજરાતી" },
  ];

  function handleLanguageClick(code: string) {
    setSelectedLanguage(code);
  }



  function handleContinue() {
    // P01 -> P02 handoff: persist the chosen language so the session created on
    // /patient (POST /session/start) carries it. New Patient is the P0 default.
    window.sessionStorage.setItem(LANGUAGE_KEY, selectedLanguage);
    router.push("/patient");
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
        <nav className="mk-p01-header__nav" aria-label="Workflow">
          {["Language", "Consent", "Code", "Interview", "Records", "Summary", "Token"].map((item, i) => (
            <button
              key={item}
              className={`mk-p01-nav__item ${i === 0 ? "mk-p01-nav__item--active" : ""}`}
              type="button"
            >
              {item}
            </button>
          ))}
        </nav>
        <div className="mk-p01-header__right">
          <button
            type="button"
            onClick={() => router.push("/patient")}
            className="mk-p01-header__action"
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
            aria-label="Request immediate emergency medical assistance"
          >
            <span aria-hidden="true">🚨</span> Need Help Now
          </button>
          <button className="mk-p01-header__action" aria-label="Reset" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /></svg>
            Reset
          </button>
          <button className="mk-p01-header__action" aria-label="Help" type="button">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4"><circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>
            Help
          </button>
          <div className="mk-p01-header__avatar" aria-label="User menu">
            <div className="mk-p01-header__avatar-ring">
              <div className="mk-p01-header__avatar-dot" />
            </div>
          </div>
        </div>
      </header>

      <main className="mk-p01-main">
        <div className="mk-p01-main__left">
          <div className="mk-p01-step">
            <span className="mk-p01-step__label">STEP 01 / 06 Initialization</span>
            <div className="mk-p01-step__dots">
              {[1, 2, 3, 4, 5, 6].map((n) => (
                <span key={n} className={`mk-p01-step__dot ${n <= 1 ? "mk-p01-step__dot--active" : ""} ${n < 1 ? "mk-p01-step__dot--done" : ""}`} />
              ))}
            </div>
          </div>

          <p className="mk-p01-eyebrow">GOVT. AYURVEDIC HOSPITAL CLINICAL TRIAGE</p>
          <h1 className="mk-p01-title">Welcome to MediKiosk</h1>
          <p className="mk-p01-desc">
            Your secure pre-consultation pathway. Answer questions, select your language,
            and prepare for your Ayurvedic OPD visit in Hall A.
          </p>

          <div className="mk-p01-section">
            <div className="mk-p01-section__header">
              <h2 className="mk-p01-section__title">1. SELECT PREFERRED LANGUAGE</h2>
              <span className="mk-p01-section__hint">Audio prompts available</span>
            </div>
            <div className="mk-p01-lang-grid">
              {languages.map((lang) => (
                <button
                  key={lang.code}
                  type="button"
                  className={`mk-p01-lang-card ${selectedLanguage === lang.code ? "mk-p01-lang-card--active" : ""}`}
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
              <h2 className="mk-p01-section__title">2. PATIENT STATUS</h2>
              <span className="mk-p01-section__hint">First time OPD visit</span>
            </div>
            <div className="mk-p01-status-grid">
              <div className="mk-p01-status-card mk-p01-status-card--active">
                <span className="mk-p01-status-card__dot" />
                <div>
                  <span className="mk-p01-status-card__label">New Patient</span>
                  <span className="mk-p01-status-card__sub">First visit</span>
                </div>
              </div>
            </div>
          </div>

          <button
            type="button"
            className="mk-p01-cta"
            onClick={handleContinue}
          >
            Continue to Consent →
            <span className="mk-p01-cta__status" />
            <span className="mk-p01-cta__sid">S-1047</span>
          </button>
        </div>

        <div className="mk-p01-main__right">
          <div className="mk-p01-howitworks">
            <h2 className="mk-p01-howitworks__title">How MediKiosk Works</h2>
            <div className="mk-p01-howitworks__list">
              <div className="mk-p01-howitworks__row">
                <div className="mk-p01-howitworks__icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>
                </div>
                <div>
                  <p className="mk-p01-howitworks__row-title">Voice & Touch</p>
                  <p className="mk-p01-howitworks__row-desc">Answer naturally or tap to select</p>
                </div>
              </div>
              <div className="mk-p01-howitworks__row">
                <div className="mk-p01-howitworks__icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
                </div>
                <div>
                  <p className="mk-p01-howitworks__row-title">Records Digitization</p>
                  <p className="mk-p01-howitworks__row-desc">Upload optional documents</p>
                </div>
              </div>
              <div className="mk-p01-howitworks__row">
                <div className="mk-p01-howitworks__icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5"><path d="M22 12h-4l-3 9L9 3l-3 9H2" /></svg>
                </div>
                <div>
                  <p className="mk-p01-howitworks__row-title">Doctor Review</p>
                  <p className="mk-p01-howitworks__row-desc">Clinician sees structured summary</p>
                </div>
              </div>
            </div>
          </div>

          <div className="mk-p01-queue">
            <h3 className="mk-p01-queue__title">OPD Queue Status</h3>
            <div className="mk-p01-queue__body">
              <span className="mk-p01-queue__count">12</span>
              <span className="mk-p01-queue__label">patients waiting</span>
              <div className="mk-p01-queue__bar">
                <div className="mk-p01-queue__fill" style={{ width: "65%" }} />
              </div>
            </div>
          </div>

          <div className="mk-p01-assistance">
            <div className="mk-p01-assistance__icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
            </div>
            <div>
              <p className="mk-p01-assistance__title">Assistance</p>
              <p className="mk-p01-assistance__desc">Need help? Connect with a nurse</p>
            </div>
            <button className="mk-p01-assistance__btn" type="button">Call Nurse</button>
          </div>
        </div>
      </main>

      <footer className="mk-p01-footer">
        <div className="mk-p01-footer__left">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 mk-p01-footer__lock"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
          <span>Secure & Encrypted</span>
        </div>
        <button className="mk-p01-footer__btn" type="button">Assistance / Call Nurse</button>
      </footer>
    </div>
  );
}