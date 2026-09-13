// P07 SUMMARY REVIEW browser test.
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

// --- Setup: create session through full flow to summary ---
const ANSWERS = [
  ["chief_complaint", "persistent cough"],
  ["onset", "1 week ago"],
  ["duration", "1 week"],
  ["severity", "moderate"],
  ["character", "dry"],
  ["associated_symptoms", "sore throat"],
];

const { session_id: sid } = await api("/session/start", "POST", {
  patient: { name: "Summary Test", age: 50, gender: "female" },
  language: "en",
  visit_type: "new",
});
await api(`/session/${sid}/consent`, "POST", { consent_given: true });
await api(`/session/${sid}/patient-code`, "POST");
for (const [, ans] of ANSWERS) await api(`/session/${sid}/answer`, "POST", { answer: ans });
await api(`/session/${sid}/documents-complete`, "POST");

// Navigate to summary screen
await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
await page.evaluate((sessionId) => {
  window.sessionStorage.setItem("medikiosk_session_id", sessionId);
}, sid);
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector(".mk-p07", { timeout: 15000 });

// --- 1. Structure: header, nav, content ---
record("p07_reaches_summary", true);
record("p07_has_header", (await page.locator(".mk-p07-header").count()) === 1);
record("p07_has_brand", (await page.locator(".mk-p07-brand").count()) === 1);
record("p07_has_7_nav_pills", (await page.locator(".mk-p07-nav__pill").count()) === 7);
const summaryActive = await page.locator(".mk-p07-nav__pill--active").textContent();
record("p07_summary_is_active_step", (summaryActive || "").trim() === "Summary");
record("p07_has_eyebrow", ((await page.locator(".mk-p07-eyebrow").textContent()) || "").includes("CASE REVIEW"));
record("p07_has_h1", ((await page.locator(".mk-p07-h1").textContent()) || "").includes("Review your information"));
record("p07_has_subtitle", (await page.locator(".mk-p07-sub").count()) === 1);
record("p07_has_card", (await page.locator(".mk-p07-card").count()) === 1);
record("p07_has_footer", (await page.locator(".mk-p07-footer").count()) === 1);

// --- 2. Four sections with correct titles ---
const sections = page.locator(".mk-p07-section");
const sectionCount = await sections.count();
record("p07_has_4_sections", sectionCount === 4, `got ${sectionCount}`);
const titles = await page.locator(".mk-p07-section__title").allTextContents();
record("p07_section1_chief_complaint", titles.some((t) => t.includes("Chief Complaint")));
record("p07_section2_medical_history", titles.some((t) => t.includes("Medical")));
record("p07_section3_ayurvedic", titles.some((t) => t.includes("Ayurvedic")));
record("p07_section4_documents", titles.some((t) => t.includes("Document")));

// --- 3. Edit buttons per section ---
const editButtons = page.locator(".mk-p07-btn--pill");
record("p07_has_4_edit_buttons", (await editButtons.count()) >= 4);

// --- 4. Dividers present ---
record("p07_has_3_dividers", (await page.locator(".mk-p07-divider").count()) === 3);

// --- 5. Disclaimer notice ---
const notice = page.locator(".mk-p07-notice");
record("p07_has_notice", (await notice.count()) === 1);
const noticeText = (await notice.textContent()) || "";
record("p07_notice_mentions_no_diagnosis", noticeText.includes("does not diagnose") || noticeText.includes("does not provide diagnoses"));

// --- 6. Action buttons ---
const confirmBtn = page.locator(".mk-p07-btn--primary");
record("p07_has_confirm_button", (await confirmBtn.count()) === 1);
record("p07_confirm_text", (await confirmBtn.textContent() || "").includes("Confirm"));
const backBtn = page.locator(".mk-p07-btn--secondary");
record("p07_has_back_button", (await backBtn.count()) >= 1);
const backTexts = await backBtn.allTextContents();
record("p07_back_text_mentions_records", backTexts.some((t) => t.includes("Back to Records")));

// --- 7. Provenance chips ---
const provenance = page.locator(".mk-p07-provenance");
const provenanceCount = await provenance.count();
record("p07_has_provenance_chips", provenanceCount >= 2, `got ${provenanceCount}`);

// --- 8. Click confirm -> token (now renders P08 screen) ---
await confirmBtn.click();
await page.waitForTimeout(2000);
const tokenNumber = page.locator(".mk-p08-token-box__number");
const tokenVisible = (await tokenNumber.count()) === 1;
record("p07_token_generated", tokenVisible);
if (tokenVisible) {
  const tokenText = (await tokenNumber.textContent()) || "";
  record("p07_token_is_nonempty", tokenText.trim().length > 0, tokenText.trim());
}
record("p07_has_return_button", (await page.locator(".mk-p08-btn").count()) >= 1);

// --- 9. Return to welcome ---
const returnBtn = page.locator(".mk-p08-btn");
await returnBtn.first().click();
await page.waitForTimeout(1500);
const isBackOnWelcome = (await page.locator(".mk-p08").count()) === 0 || (await page.locator("[class*='mk-welcome']").count()) > 0 || (await page.locator("text=Select your preferred language").count()) > 0;
record("p07_return_to_welcome", isBackOnWelcome);

// --- 10. No JS errors ---
record("p07_no_js_errors", errors.length === 0, errors.length > 0 ? errors.join("; ") : "");

await browser.close();

console.log(`\n--- P07 Summary: ${results.filter((r) => r.ok).length}/${results.length} passed ---`);
if (results.some((r) => !r.ok)) process.exit(1);
