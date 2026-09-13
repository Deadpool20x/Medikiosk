"use client";

import { useEffect, useState } from "react";
import { getDoctorQueue } from "../lib/api";
import type { QueueItem } from "../lib/types";

export function DoctorQueue({
  department,
  onOpenCase,
}: {
  department: string;
  onOpenCase: (sessionId: string) => void;
}) {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    try {
      const data = await getDoctorQueue(department);
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
  }, [department]);

  return (
    <div>
      <div className="mk-d01-ribbon">
        <div>
          <h1 className="mk-d01-ribbon__title">{department}</h1>
          <p className="mk-d01-ribbon__count">
            {loading ? "Loading queue…" : `${items.length} patient${items.length === 1 ? "" : "s"} waiting`}
          </p>
        </div>
        <button
          className="mk-d01-refresh"
          onClick={() => {
            setRefreshing(true);
            load();
          }}
          disabled={refreshing}
        >
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error && (
        <div className="mk-d01-error" role="alert">
          <span className="mk-d01-error__msg">{error}</span>
          <button
            className="mk-d01-refresh mk-d01-error__retry"
            onClick={() => {
              setError(null);
              setLoading(true);
              load();
            }}
          >
            Retry
          </button>
        </div>
      )}

      {!error && loading ? (
        <div className="mk-d01-state">
          <p className="mk-d01-state__title">Loading request queue…</p>
        </div>
      ) : !error && items.length === 0 ? (
        <div className="mk-d01-state">
          <p className="mk-d01-state__title">No patients waiting</p>
          <p className="mk-d01-state__desc">
            Completed intake sessions for {department} will appear here once they receive a queue token.
          </p>
        </div>
      ) : !error ? (
        <div className="mk-d01-table-wrap">
          <table className="mk-d01-table">
            <thead>
              <tr>
                <th>Queue Token</th>
                <th>Patient Code</th>
                <th>Status</th>
                <th>Check-in Time</th>
                <th className="mk-d01-th--right">Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => {
                const isNext = i === 0;
                const ready = !!item.confirmed;
                return (
                  <tr key={item.session_id} className="mk-d01-row">
                    <td>
                      <span className="mk-d01-token-grp">
                        <span className={`mk-d01-bar ${isNext ? "mk-d01-bar--next" : ""}`} />
                        <span className="mk-d01-token">{item.queue_token || "—"}</span>
                      </span>
                    </td>
                    <td data-label="Patient Code">
                      <span className="mk-d01-code">{item.patient_code || "—"}</span>
                    </td>
                    <td data-label="Status">
                      <span className={`mk-d01-status ${ready ? "mk-d01-status--ready" : ""}`}>
                        <span className={`mk-d01-status__dot ${ready ? "mk-d01-status__dot--ready" : ""}`} />
                        {ready ? "Ready" : "Waiting"}
                      </span>
                    </td>
                    <td data-label="Check-in Time">
                      <span className="mk-d01-time">{formatClock(item.check_in_time)}</span>
                    </td>
                    <td className="mk-d01-cell--action">
                      <button
                        className={`mk-d01-open ${isNext ? "mk-d01-open--next" : ""}`}
                        onClick={() => onOpenCase(item.session_id)}
                      >
                        <span>Open Case</span>
                        {isNext ? (
                          <svg
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            className="mk-d01-open__arrow"
                            aria-hidden="true"
                          >
                            <path d="M5 12h14" />
                            <path d="m12 5 7 7-7 7" />
                          </svg>
                        ) : null}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function formatClock(iso: string): string {
  if (!iso) return "—";
  const d = new Date(String(iso).replace(" ", "T"));
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}