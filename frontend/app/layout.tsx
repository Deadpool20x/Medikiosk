import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediKiosk",
  description: "AI-assisted pre-consultation case-taking and clinician review",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="mk-app-header">
          <div className="mk-app-header__inner">
            <Link className="mk-wordmark" href="/">MediKiosk</Link>
            <span className="mk-demo-label">Synthetic demo</span>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
