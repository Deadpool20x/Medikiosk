// P0 audit — browser capture harness (scenario 10/11 evidence).
//
// Drives the REAL Next.js frontend against the mocked-provider backend
// (scripts/p0_server.py) and screenshots every patient + doctor screen at
// 1440px and 390px. Also records console/page errors and horizontal overflow
// per screenshot as scenario-11 (UX) evidence.
//
// Run from frontend/ directory:  node ..\scripts\p0_shots.mjs
import { createRequire } from "module";
import path from "path";
import fs from "fs";
import os from "os";

const require = createRequire(path.join(process.cwd(), "package.json"));
const { chromium } = require("playwright-core");

const ROOT = path.resolve("..");
const SHOTS = path.join(ROOT, "stitch_medikiosk_FINAL", "p0_shots");
const WEB = process.env.P0_WEB_URL || "http://localhost:3000";

const tiniestPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
  "base64"
);
const RX = path.join(os.tmpdir(), "p0_rx.png");
fs.writeFileSync(RX, tiniestPng);

const questions = [
  "What is the primary reason",
  "When did these symptoms",
  "How long have you been experiencing",
  "how severe is the pain",
  "what the symptom feels like",
  "any other symptoms",
];

async function waitText(page, text, timeout = 10000) {
  await page.getByText(text, { exact: false }).first().waitFor({ state: "visible", timeout });
}

async function clickBtn(page, text) {
  const b = page.locator("button", { hasText: text }).first();
  await b.waitFor({ state: "visible", timeout: 10000 });
  await b.click();
}

const metrics = [];
async function shot(page, dir, name) {
  const dims = await page.evaluate(() => ({
    w: document.documentElement.scrollWidth,
    iw: window.innerWidth,
    h: document.documentElement.scrollHeight,
    ih: window.innerHeight,
  }));
  metrics.push({ name, ...dims, overflow: dims.w > dims.iw + 1 });
  fs.mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage: true });
  console.log(`shot: ${name}  ${dims.w}x${dims.h} viewport=${dims.iw}x${dims.ih} overflow=${dims.w > dims.iw + 1}`);
}

async function runPatientFlow(page, dir, { name, age, complaint, safety = false, showP04mid = true }) {
  await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
  await page.evaluate(() => sessionStorage.clear());
  await page.reload({ waitUntil: "networkidle" });

  // P01 welcome
  await page.fill('input[placeholder="Enter your name"]', name);
  await page.fill('input[placeholder="Enter your age"]', age);
  await shot(page, dir, "p01_welcome");
  await clickBtn(page, "Start Now");

  // P02 consent
  await waitText(page, "Consent");
  await shot(page, dir, "p02_consent");
  await clickBtn(page, "I Agree");

  // P03 patient code
  await waitText(page, "Your Patient Code");
  await shot(page, dir, "p03_patient_code");
  await clickBtn(page, "Generate Code");

  // P04 interview
  await page.waitForSelector(".mk-ask", { timeout: 10000 });
  await shot(page, dir, "p04_interview_q1");

  const answers = safety
    ? [["severe chest pain", null]]
    : [
        [complaint, questions[1]],
        ["About 1 week ago", questions[2]],
        ["Constant for a week", questions[3]],
        ["Moderate, 5 out of 10", questions[4]],
        ["Dull aching", questions[5]],
        ["Stiffness in the morning", null],
      ];

  for (let i = 0; i < answers.length; i++) {
    const [ans, nextQ] = answers[i];
    await page.fill(".mk-input-area", ans);
    await clickBtn(page, "Continue");
    if (nextQ) await waitText(page, nextQ);
    if (i === 1 && showP04mid && !safety) await shot(page, dir, "p04_interview_mid");
    if (safety && i === 0) {
      await waitText(page, "Intake Paused");
      await shot(page, dir, "p05_safety");
      return;
    }
  }
  if (safety) return;

  // P06 documents
  await waitText(page, "Upload an existing medical document");
  await shot(page, dir, "p06_documents_empty");
  const [chooser] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.locator(".mk-doc-dropzone").click(),
  ]);
  await chooser.setFiles(RX);
  await waitText(page, "Upload");
  await clickBtn(page, "Upload");
  await waitText(page, "Analyzed via OCR");
  await page.waitForTimeout(250);
  await shot(page, dir, "p06_documents_uploaded");

  // P07 summary
  await clickBtn(page, "Continue to Summary");
  await waitText(page, "Review Your Summary");
  await shot(page, dir, "p07_summary");

  // P08 confirmation token
  await clickBtn(page, "Confirm & Get Token");
  await waitText(page, "Confirmed");
  await waitText(page, "Your queue token");
  await shot(page, dir, "p08_confirmation_token");

  // P09 waiting
  await clickBtn(page, "View Waiting Screen");
  await waitText(page, "all set");
  await shot(page, dir, "p09_waiting");
}

async function waitQueueRows(page) {
  await page
    .locator(".mk-queue-table tbody tr, .mk-empty-state")
    .first()
    .waitFor({ state: "visible", timeout: 10000 });
}

async function runDoctorFlow(page, dir, { navAccessible }) {
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });

  // D04 emergency dashboard
  await waitText(page, "Emergency Safety Escalations");
  await waitText(page, "Active Escalation Queue");
  await shot(page, dir, "d04_emergency");

  if (!navAccessible) return; // sidebar hidden <=768px; D01-D03 unreachable

  // D01 Kayachikitsa queue
  await clickBtn(page, "Kayachikitsa Queue");
  await waitText(page, "Kayachikitsa Department Queue");
  await waitQueueRows(page);
  await shot(page, dir, "d01_queue_kaya");

  // D02 patient case
  await clickBtn(page, "Open Case");
  await waitText(page, "Patient Case");
  await shot(page, dir, "d02_patient_case");

  // D03 doctor review/edit
  await clickBtn(page, "Review / Edit Case");
  await waitText(page, "Edit Clinical Data");
  await shot(page, dir, "d03_review_edit");

  // Panchakarma queue (bonus: department separation evidence)
  await clickBtn(page, "Panchakarma Queue");
  await waitText(page, "Panchakarma Department Queue");
  await waitQueueRows(page);
  await shot(page, dir, "d01_queue_pancha");
}

(async () => {
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const issues = [];

  for (const viewport of [
    { label: "1440", width: 1440, height: 950 },
    { label: "390", width: 390, height: 844 },
  ]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    page.on("pageerror", (e) => issues.push(`[${viewport.label}] pageerror: ${e.message}`));
    page.on("console", (m) => {
      if (m.type() === "error") issues.push(`[${viewport.label}] console.error: ${m.text()}`);
    });
    const dir = path.join(SHOTS, viewport.label);

    if (viewport.label === "1440") {
      await runPatientFlow(page, dir, { name: "Alok Verma", age: "42", complaint: "Lower back pain" });
      await runPatientFlow(page, dir, { name: "Aarti Sharma", age: "31", complaint: "", safety: true });
    } else {
      await runPatientFlow(page, dir, { name: "Meena Kumari", age: "38", complaint: "Sthaulya" });
    }
    await runDoctorFlow(page, dir, { navAccessible: viewport.label === "1440" });
    await context.close();
  }

  await browser.close();
  console.log("\n=== overflow evidence (scenario 11) ===");
  console.table(metrics.map((m) => ({ shot: m.name, overflow: m.overflow, w: m.w, iw: m.iw })));
  console.log("\n=== console/page errors ===");
  console.log(issues.length ? issues.join("\n") : "(none)");
})();