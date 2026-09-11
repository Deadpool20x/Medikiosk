// P05 PATIENT SAFETY ESCALATION browser test.
// Drives the real Next.js dev app on :3000 (mock backend on :8001).
import { createRequire } from "module";
const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");

const WEB = "http://localhost:3000";
const API = "http://127.0.0.1:8001";

const results = [];
function record(name, ok, note = "") {
  results.push({ name, ok, note });
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${note ? " — " + note : ""}`);
}

async function api(path, method = "GET", body) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}: ${text.slice(0, 200)}`);
  return text ? JSON.parse(text) : {};
}

const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

// --- Setup: create a safety-flagged session via API ---
const { session_id: sid } = await api("/session/start", "POST", {
  patient: { name: "Safety Test", age: 60, gender: "female" },
  language: "en",
  visit_type: "new",
});
await api(`/session/${sid}/consent`, "POST", { consent_given: true });
const codeRes = await api(`/session/${sid}/patient-code`, "POST");
const patientCode = codeRes.patient_code;
await api(`/session/${sid}/answer`, "POST", { answer: "chest pain" });

// --- 1. Safety-flagged session reaches P05 ---
await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
await page.evaluate((sessionId) => {
  window.sessionStorage.setItem("medikiosk_session_id", sessionId);
}, sid);
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".mk-p05", { timeout: 15000 });

record("p05_flagged_reaches_safety_screen", true);
record("p05_has_header", (await page.locator(".mk-p05-header").count()) === 1);
record("p05_has_brand", (await page.locator(".mk-p05-brand").count()) === 1);
record("p05_has_eyebrow", ((await page.locator(".mk-p05-eyebrow").textContent()) || "").includes("CLINICAL SAFETY NOTICE"));
record("p05_has_status_badge", ((await page.locator(".mk-p05-status").textContent()) || "").includes("Intake Paused"));
record("p05_has_h1", ((await page.locator(".mk-p05-h1").textContent()) || "").includes("speak with a staff member"));
record("p05_has_subtitle", (await page.locator(".mk-p05-sub").count()) === 1);
record("p05_has_two_info_panels", (await page.locator(".mk-p05-info").count()) === 2);
record("p05_has_ref_code", ((await page.locator(".mk-p05-ref__value").textContent()) || "").includes(patientCode));
record("p05_has_return_button", (await page.locator(".mk-p05-btn").count()) === 1);
record("p05_has_footer", ((await page.locator(".mk-p05-footer").textContent()) || "").includes("MediKiosk"));

// --- 2. Safe session does NOT reach P05 ---
const { session_id: safeSid } = await api("/session/start", "POST", {
  patient: { name: "Safe Patient", age: 30, gender: "male" },
  language: "en",
  visit_type: "new",
});
await api(`/session/${safeSid}/consent`, "POST", { consent_given: true });
await api(`/session/${safeSid}/patient-code`, "POST");
await api(`/session/${safeSid}/answer`, "POST", { answer: "headache" });

const safePage = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
await safePage.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
await safePage.evaluate((sessionId) => {
  window.sessionStorage.setItem("medikiosk_session_id", sessionId);
}, safeSid);
await safePage.reload({ waitUntil: "networkidle" });
// Should NOT show P05 — should be on interview or next screen
await safePage.waitForTimeout(2000);
const safeP05Count = await safePage.locator(".mk-p05").count();
record("p05_safe_session_no_safety_screen", safeP05Count === 0, `mk-p05 count=${safeP05Count}`);
await safePage.close();

// --- 3. Refresh preserves P05 state ---
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".mk-p05", { timeout: 15000 });
const h1AfterRefresh = (await page.locator(".mk-p05-h1").textContent() || "").trim();
record("p05_refresh_preserves_state", h1AfterRefresh.includes("speak with a staff member"));

// --- 4. Return to Welcome resets session ---
await page.click(".mk-p05-btn");
await page.waitForSelector(".mk-patient-shell", { timeout: 15000 });
record("p05_return_to_welcome_works", true);
// Session should be cleared — no P05 on reload with cleared storage
const clearedStorage = await page.evaluate(() => window.sessionStorage.getItem("medikiosk_session_id"));
record("p05_session_cleared_after_return", clearedStorage === null, `storage=${clearedStorage}`);

record("no_page_errors", errors.length === 0, errors.join("; "));

await browser.close();
const bad = results.filter((r) => !r.ok);
console.log(bad.length === 0 ? "ALL P05 SAFETY CHECKS GREEN" : `FAILURES: ${JSON.stringify(bad, null, 2)}`);
process.exit(bad.length === 0 ? 0 : 1);
