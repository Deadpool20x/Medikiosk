"use client";

import { useEffect } from "react";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log unexpected client runtime errors for observability
    console.error("MediKiosk Client Error Boundary Caught:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 shadow-sm p-8 text-center">
        <div className="w-14 h-14 mx-auto rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600 mb-5">
          <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>

        <span className="text-xs font-semibold tracking-wider text-slate-500 uppercase">
          Kiosk Recovery System
        </span>

        <h1 className="text-xl font-bold text-slate-900 mt-2">
          Temporary System Notice
        </h1>

        <p className="text-sm text-slate-600 mt-3 leading-relaxed">
          An unexpected application issue occurred. Your clinical data and session progress remain securely preserved on the server.
        </p>

        <div className="mt-6 flex flex-col sm:flex-row gap-3">
          <button
            type="button"
            onClick={() => reset()}
            className="flex-1 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-xl transition shadow-sm"
          >
            Try Again
          </button>
          <button
            type="button"
            onClick={() => {
              window.location.href = "/";
            }}
            className="flex-1 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-xl transition"
          >
            Return to Start
          </button>
        </div>

        <p className="text-xs text-slate-400 mt-6">
          MediKiosk Clinical OS • Department Reception Kiosk
        </p>
      </div>
    </div>
  );
}
