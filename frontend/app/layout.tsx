import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediKiosk - AI-Assisted Clinical Case-Taking",
  description: "Smart India Hackathon 2026 pre-consultation case-taking kiosk",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-slate-50 text-slate-900">
        <header className="border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <h1 className="text-xl font-bold tracking-tight text-blue-600">MediKiosk</h1>
            <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
              Foundation Ready (Day 1)
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-7xl p-6">
          {children}
        </main>
      </body>
    </html>
  );
}
