import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediKiosk",
  description: "AI-assisted pre-consultation case-taking and clinician review",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
