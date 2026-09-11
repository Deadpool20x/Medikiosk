// P06 DOCUMENT UPLOAD browser test.
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

// --- Setup: create session through interview to documents step ---
const ANSWERS = [
  ["chief_complaint", "mild headache"],
  ["onset", "3 days ago"],
  ["duration", "3 days"],
  ["severity", "mild"],
  ["character", "throbbing"],
  ["associated_symptoms", "fatigue"],
];

const { session_id: sid } = await api("/session/start", "POST", {
  patient: { name: "Doc Test Patient", age: 35, gender: "female" },
  language: "en",
  visit_type: "new",
});
await api(`/session/${sid}/consent`, "POST", { consent_given: true });
const codeRes = await api(`/session/${sid}/patient-code`, "POST");
for (const [, ans] of ANSWERS) await api(`/session/${sid}/answer`, "POST", { answer: ans });

// Navigate to documents screen
await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
await page.evaluate((sessionId) => {
  window.sessionStorage.setItem("medikiosk_session_id", sessionId);
}, sid);
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".mk-p06", { timeout: 15000 });

// --- 1. Idle state structure ---
record("p06_idle_reaches_documents", true);
record("p06_has_header", (await page.locator(".mk-p06-header").count()) === 1);
record("p06_has_brand", (await page.locator(".mk-p06-brand").count()) === 1);
record("p06_has_7_nav_pills", (await page.locator(".mk-p06-nav__pill").count()) === 7);
const recordsActive = await page.locator(".mk-p06-nav__pill--active").textContent();
record("p06_records_is_active_step", (recordsActive || "").trim() === "Records");
record("p06_has_eyebrow", ((await page.locator(".mk-p06-eyebrow").textContent()) || "").includes("OPTIONAL MEDICAL RECORDS"));
record("p06_has_h1", ((await page.locator(".mk-p06-h1").textContent()) || "").includes("Upload an existing medical document"));
record("p06_has_subtitle", (await page.locator(".mk-p06-sub").count()) === 1);
record("p06_has_dropzone", (await page.locator(".mk-p06-dropzone").count()) === 1);
record("p06_has_footer", (await page.locator(".mk-p06-footer").count()) === 1);
record("p06_has_skip_button", (await page.locator(".mk-p06-btn--skip").count()) === 1);
record("p06_continue_disabled_when_idle", await page.locator(".mk-p06-btn--continue").isDisabled());

// --- 2. Invalid file type rejected ---
const invalidBuffer = Buffer.from("not an image");
const fs = await import("fs");
const invalidFile = "D:\\tmp\\test_invalid.txt";
fs.writeFileSync(invalidFile, invalidBuffer);
const fileInput = page.locator("input[type='file']");
await fileInput.setInputFiles(invalidFile);
await page.waitForTimeout(300);
const errorVisible = (await page.locator(".mk-p06-error").count()) > 0;
record("p06_invalid_file_rejected", errorVisible);
fs.unlinkSync(invalidFile);

// --- 3. Valid upload reaches extracted state ---
// Reset error state by navigating fresh
await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
await page.evaluate((sessionId) => {
  window.sessionStorage.setItem("medikiosk_session_id", sessionId);
}, sid);
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".mk-p06", { timeout: 15000 });

// Create valid PNG
const pngHeader = Buffer.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
  0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
  0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
  0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
  0xde, 0x00, 0x00, 0x00, 0x0c, 0x49, 0x44, 0x41,
  0x54, 0x08, 0xd7, 0x63, 0xf8, 0xcf, 0xc0, 0x00,
  0x00, 0x00, 0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc,
  0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e,
  0x44, 0xae, 0x42, 0x60, 0x82,
]);
const validFile = "D:\\tmp\\test_valid.png";
fs.writeFileSync(validFile, pngHeader);

await fileInput.setInputFiles(validFile);
await page.waitForSelector(".mk-p06-file-box__upload", { timeout: 10000 });
await page.click(".mk-p06-file-box__upload");
await page.waitForSelector(".mk-p06-extracted, .mk-p06-review-alert", { timeout: 20000 });
await page.waitForTimeout(500);

record("p06_upload_reaches_extracted", true);
record("p06_has_4_fields", (await page.locator(".mk-p06-field").count()) === 4);
record("p06_has_disclaimer", (await page.locator(".mk-p06-disclaimer").count()) === 1);
record("p06_has_file_box", (await page.locator(".mk-p06-file-box").count()) === 1);
record("p06_has_replace_button", (await page.locator(".mk-p06-file-box__replace").count()) === 1);
record("p06_has_delete_button", (await page.locator(".mk-p06-file-box__delete").count()) === 1);
record("p06_has_extracted_header", ((await page.locator(".mk-p06-extracted__heading").textContent()) || "").includes("Extracted Information Preview"));
record("p06_continue_enabled_after_upload", await page.locator(".mk-p06-btn--continue").isEnabled());

// --- 4. Continue to summary ---
await page.click(".mk-p06-btn--continue");
await page.waitForTimeout(1000);
const onSummary = (await page.locator(".mk-p06").count()) === 0;
record("p06_continue_advances_to_next", onSummary);

fs.unlinkSync(validFile);
record("no_page_errors", errors.length === 0, errors.join("; "));

await browser.close();
const bad = results.filter((r) => !r.ok);
console.log(bad.length === 0 ? "ALL P06 DOCUMENT CHECKS GREEN" : `FAILURES: ${JSON.stringify(bad, null, 2)}`);
process.exit(bad.length === 0 ? 0 : 1);
