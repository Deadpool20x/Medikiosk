"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { getEmergencySessions } from "../lib/api";
import type { EmergencyItem } from "../lib/types";
import { DoctorQueue } from "./doctor-queue";
import { DoctorCase } from "./doctor-case";
import { DoctorReview } from "./doctor-review";

function MediKioskLogo() {
  return (
    <svg viewBox="0 0 40 40" fill="none" className="w-8 h-8" aria-hidden="true">
      <rect width="40" height="40" rx="10" fill="#111111" />
      <path d="M20 10v20M10 20h20" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" />
    </svg>
  );
}

type View =
  | { kind: "emergency" }
  | { kind: "queue"; department: string }
  | { kind: "case"; sessionId: string; department: string }
  | { kind: "review"; sessionId: string; department: string };

const SIDEBAR_ITEMS: Array<{ key: string; label: string; kind: View }> = [
  { key: "emergency", label: "Emergency Escalations", kind: { kind: "emergency" } },
  { key: "kaya", label: "Kayachikitsa Queue", kind: { kind: "queue", department: "Kayachikitsa" } },
  { key: "pancha", label: "Panchakarma Queue", kind: { kind: "queue", department: "Panchakarma" } },
];

export function DoctorWorkspace() {
  const [view, setView] = useState<View>({ kind: "emergency" });

  function selectView(v: View) {
    window.sessionStorage.setItem("mk_doctor_view", JSON.stringify(v));
    setView(v);
  }

  const [items, setItems] = useState<EmergencyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    try {
      const data = await getEmergencySessions();
      setItems(data);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.sessionStorage.getItem("mk_doctor_view");
    if (saved) {
      try {
        const p = JSON.parse(saved);
        if (p && (p.kind === "emergency" || p.kind === "queue")) setView(p);
        else if (p && (p.kind === "case" || p.kind === "review") && typeof p.sessionId === "string") setView(p);
      } catch { /* ignore malformed */ }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function ack(id: string) {
    setAcknowledged((prev) => new Set(prev).add(id));
  }

  if (view.kind === "review") {
    return (
      <DoctorReview
        sessionId={view.sessionId}
        department={view.department}
        onBack={() => selectView({ kind: "case", sessionId: view.sessionId, department: view.department })}
        onNavQueue={() => selectView({ kind: "queue", department: view.department })}
      />
    );
  }

  return (
    <div className="mk-doctor-shell">
      <aside className="mk-sidebar">
        <div className="mk-sidebar__brand">
          <MediKioskLogo />
          <span className="mk-sidebar__wordmark">MediKiosk</span>
        </div>
        <nav className="mk-sidebar__nav">
          {SIDEBAR_ITEMS.map((item) => (
            <button
              key={item.key}
              className="mk-sidebar__item"
              data-active={JSON.stringify(view) === JSON.stringify(item.kind)}
              onClick={() => selectView(item.kind)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="mk-sidebar__user">
          <div className="mk-sidebar__avatar">MK</div>
          <div>
            <div className="mk-sidebar__name">Demo Clinician</div>
            <div className="mk-sidebar__role">On-Site Workstation</div>
          </div>
        </div>
      </aside>

      <main className="mk-main-content">
        {error && view.kind !== "emergency" && <div className="mk-error-banner" role="alert" style={{ marginBottom: "16px" }}>{error}</div>}

        {view.kind === "emergency" && (
          <>
            <div className="mk-d04-header-card">
              <div className="mk-d04-header-card__text">
                <h1 className="mk-d04-page-title">Emergency Safety Escalations</h1>
                <p className="mk-d04-page-desc">
                  Patients whose intake was paused for safety review appear here. They do not receive a normal department queue token.
                </p>
              </div>
              <button
                className="mk-d04-refresh"
                onClick={() => { setRefreshing(true); load(); }}
                disabled={refreshing}
              >
                <RefreshIcon />
                {refreshing ? "Refreshing…" : "Refresh"}
              </button>
            </div>

            <div className="mk-d04-queue-section">
              <div className="mk-d04-queue-heading">
                <span className="mk-d04-queue-heading__text">Active Escalation Queue</span>
              </div>

              {error ? (
                <div className="mk-d04-error" role="alert">
                  <p className="mk-d04-error__text">Could not load safety escalations.</p>
                  <button
                    className="mk-d04-refresh"
                    onClick={() => { setError(null); setLoading(true); load(); }}
                  >
                    Retry
                  </button>
                </div>
              ) : loading ? (
                <div className="mk-d04-loading">
                  <span className="mk-d04-loading__spinner" />
                  <span>Loading escalations…</span>
                </div>
              ) : items.length === 0 ? (
                <div className="mk-d04-empty">
                  <p className="mk-d04-empty__text">No active safety escalations.</p>
                </div>
              ) : (
                <div className="mk-d04-alert-list">
                  {items.map((item) => {
                    const done = acknowledged.has(item.session_id);
                    return (
                      <div key={item.session_id} className="mk-d04-alert-card">
                        <div className="mk-d04-alert-card__main">
                          <div className="mk-d04-alert-icon">
                            <WarningIcon />
                          </div>
                          <div className="mk-d04-alert-card__body">
                            <div className="mk-d04-alert-card__head">
                              <span className="mk-d04-alert-code">{item.patient_code}</span>
                              <span className="mk-d04-alert-badge">{item.status}</span>
                            </div>
                            <p className="mk-d04-alert-symptom">
                              {item.patient_name} — {item.symptom}
                            </p>
                            <div className="mk-d04-alert-meta">
                              <span>Reported at: <strong className="mk-d04-alert-meta__time">{formatTime(item.reported_at)}</strong></span>
                            </div>
                          </div>
                        </div>
                        <div className="mk-d04-alert-card__action">
                          <button
                            className={`mk-d04-ack-btn ${done ? "mk-d04-ack-btn--done" : ""}`}
                            onClick={() => ack(item.session_id)}
                            disabled={done}
                          >
                            {done ? (
                              <>
                                <CheckIcon />
                                <span>Acknowledged</span>
                              </>
                            ) : (
                              <>
                                <span>Acknowledge Alert</span>
                                <ArrowForwardIcon />
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        )}

        {view.kind === "queue" && (
          <DoctorQueue
            department={view.department}
            onOpenCase={(sessionId) => selectView({ kind: "case", sessionId, department: view.department })}
          />
        )}


        {view.kind === "case" && (
          <DoctorCase
            sessionId={view.sessionId}
            onBack={() => selectView({ kind: "queue", department: view.department })}
            onEdit={() => selectView({ kind: "review", sessionId: view.sessionId, department: view.department })}
          />
        )}
      </main>
    </div>
  );
}

function formatTime(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

function AlertIconBase({ children, className }: { children: ReactNode; className: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      {children}
    </svg>
  );
}

function WarningIcon() {
  return (
    <AlertIconBase className="mk-d04-warning-icon">
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </AlertIconBase>
  );
}

function RefreshIcon() {
  return (
    <AlertIconBase className="mk-d04-refresh-icon">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M8 16H3v5" />
    </AlertIconBase>
  );
}

function CheckIcon() {
  return (
    <AlertIconBase className="mk-d04-ack-icon">
      <path d="M20 6 9 17l-5-5" />
    </AlertIconBase>
  );
}

function ArrowForwardIcon() {
  return (
    <AlertIconBase className="mk-d04-ack-icon">
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </AlertIconBase>
  );
}
