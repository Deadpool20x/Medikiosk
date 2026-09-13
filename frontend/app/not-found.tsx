import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="max-w-md w-full bg-white rounded-2xl border border-slate-200 shadow-sm p-8 text-center">
        <div className="w-14 h-14 mx-auto rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600 mb-5">
          <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>

        <span className="text-xs font-semibold tracking-wider text-slate-500 uppercase">
          404 — Page Not Found
        </span>

        <h1 className="text-xl font-bold text-slate-900 mt-2">
          Requested Screen Unavailable
        </h1>

        <p className="text-sm text-slate-600 mt-3 leading-relaxed">
          The requested path does not exist on this MediKiosk reception terminal. Please return to the kiosk main screen.
        </p>

        <div className="mt-6">
          <Link
            href="/"
            className="inline-flex items-center justify-center w-full px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded-xl transition shadow-sm"
          >
            Return to Welcome Screen
          </Link>
        </div>

        <p className="text-xs text-slate-400 mt-6">
          MediKiosk Clinical OS • Reception Terminal
        </p>
      </div>
    </div>
  );
}
