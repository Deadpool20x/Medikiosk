import Link from "next/link";

export default function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl text-slate-900">
        MediKiosk Case-Taking System
      </h2>
      <p className="mt-4 max-w-2xl text-base text-slate-600">
        AI-assisted pre-consultation intake portal. Choose your interface below:
      </p>
      <div className="mt-8 flex gap-4">
        <Link
          href="/patient"
          className="rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white shadow hover:bg-blue-700 transition"
        >
          Patient Kiosk
        </Link>
        <Link
          href="/doctor"
          className="rounded-lg border border-slate-300 bg-white px-6 py-3 font-semibold text-slate-700 shadow-sm hover:bg-slate-50 transition"
        >
          Doctor Dashboard
        </Link>
      </div>
    </div>
  );
}
