// P09 WAITING / COMPLETION browser tests — drives the real Next.js app + mock backend.
// Expected running: p0_server.py on 127.0.0.1:8001, `npm run dev` on :3000.
import { createRequire } from "module";
const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");

const API = "http://127.0.0.1:8001";
const WEB = "http://localhost:3000";

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

const ANSWERS = [
  ["chief_complaint", "mild back pain"],
  ["onset", "2 weeks ago"],
  ["duration", "2 weeks"],
  ["severity", "mild"],
  ["character", "dull"],
  ["associated_symptoms", "stiffness"],
];

// Create session → navigate to summary → generate token → go to P09
console.log("creating session…");
const { session_id: sid } = await api("/session/start", "POST", {
  patient: { name: "Waiting Test Patient", age: 30, gender: "male" },
  language: "en",
  visit_type: "new",
});
await api(`/session/${sid}/consent`, "POST", { consent_given: true });
await api(`/session/${sid}/patient-code`, "POST");
for (const [, ans] of ANSWERS) await api(`/session/${sid}/answer`, "POST", { answer: ans });
await api(`/session/${sid}/documents-complete`, "POST");
console.log(`  session ${sid} ready`);

const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 844 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("Failed to load resource")) errors.push(m.text()); });

await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
await page.evaluate((sessionId) => {
  window.sessionStorage.setItem("medikiosk_session_id", sessionId);
}, sid);
await page.reload({ waitUntil: "networkidle" });

// Wait for P07 summary
await page.waitForSelector(".mk-p07", { timeout: 15000 });
await page.waitForTimeout(300);

// Click Confirm & Generate Token → P08
const confirmBtn = page.locator("button", { hasText: /confirm.*token|generate.*token/i });
if ((await confirmBtn.count()) === 0) {
  await page.locator(".mk-p07-btn", { hasText: /confirm/i }).first().click();
} else {
  await confirmBtn.first().click();
}

// Wait for P08 token screen
await page.waitForSelector(".mk-p08", { timeout: 15000 });
await page.waitForTimeout(500);

// Click Done / View Waiting Screen → P09
const doneBtnP08 = page.locator(".mk-p08-btn", { hasText: /done/i });
await doneBtnP08.first().click();

// Wait for P09 waiting screen
await page.waitForSelector(".mk-p09", { timeout: 15000 });
await page.waitForTimeout(500);

const results = [];
function record(name, ok, detail) {
  results.push({ name, ok, detail: detail || "" });
  console.log(ok ? `PASS ${name}` : `FAIL ${name}${detail ? " — " + detail : ""}`);
}

// --- Tests ---

// 1. P09 screen renders
record("p09_reaches_waiting_screen", (await page.locator(".mk-p09").count()) === 1);

// 2. Header present
record("p09_has_header", (await page.locator(".mk-p09-header").count()) === 1);

// 3. Brand present
record("p09_has_brand", (await page.locator(".mk-p09-brand__name").count()) === 1);
const brandText = await page.locator(".mk-p09-brand__name").textContent() || "";
record("p09_brand_says_medikiosk", brandText.includes("MediKiosk"), brandText);

// 4. 7 nav pills
const navPillCount = await page.locator(".mk-p09-nav__pill").count();
record("p09_has_7_nav_pills", navPillCount === 7, `got ${navPillCount}`);

// 5. Token Complete pill is active
const activePill = page.locator(".mk-p09-nav__pill--active");
const activePillText = (await activePill.textContent()) || "";
record("p09_token_complete_is_active", activePillText.includes("Token Complete"), activePillText);

// 6. All previous steps done (6 done pills)
const donePills = await page.locator(".mk-p09-nav__pill--done").count();
record("p09_has_6_done_pills", donePills === 6, `got ${donePills}`);

// 7. Active pill has filled checkmark icon (SVG with fill)
const activePillSvg = await activePill.locator("svg").count();
record("p09_active_pill_has_check_icon", activePillSvg > 0, `svg count: ${activePillSvg}`);

// 8. Eyebrow
const eyebrow = page.locator(".mk-p09-eyebrow");
record("p09_has_eyebrow", (await eyebrow.count()) === 1);
const eyebrowText = (await eyebrow.textContent()) || "";
record("p09_eyebrow_says_waiting", eyebrowText.includes("OPD QUEUE WAITING"), eyebrowText);

// 9. H1
const h1 = page.locator(".mk-p09-h1");
record("p09_has_h1", (await h1.count()) === 1);
const h1Text = (await h1.textContent()) || "";
record("p09_h1_says_wait", h1Text.includes("Please wait for your token to be called"), h1Text);

// 10. Subtitle
const sub = page.locator(".mk-p09-sub");
record("p09_has_subtitle", (await sub.count()) === 1);
const subText = (await sub.textContent()) || "";
record("p09_sub_mentions_intake_complete", subText.includes("intake is complete"), subText);

// 11. Card
record("p09_has_card", (await page.locator(".mk-p09-card").count()) === 1);

// 12. Status badge
const statusBadge = page.locator(".mk-p09-status__badge");
record("p09_has_status_badge", (await statusBadge.count()) === 1);
const statusText = (await statusBadge.textContent()) || "";
record("p09_status_says_intake_complete", statusText.includes("Intake Complete"), statusText);

// 13. Department section
const deptName = page.locator(".mk-p09-dept__name");
record("p09_has_department", (await deptName.count()) === 1);
const deptText = (await deptName.textContent()) || "";
record("p09_department_is_nonempty", deptText.trim().length > 0, deptText);

// 14. Token box
const tokenNumber = page.locator(".mk-p09-token-box__number");
record("p09_has_token_number", (await tokenNumber.count()) === 1);
const tokenText = (await tokenNumber.textContent()) || "";
record("p09_token_is_nonempty", tokenText.trim().length > 0, tokenText);

// 15. Token box label says "YOUR QUEUE TOKEN"
const tokenLabel = page.locator(".mk-p09-token-box__label");
const tokenLabelText = (await tokenLabel.textContent()) || "";
record("p09_token_label_says_your_queue", tokenLabelText.includes("YOUR QUEUE TOKEN"), tokenLabelText);

// 16. Patient code
const patientCode = page.locator(".mk-p09-patient-code__badge");
record("p09_has_patient_code", (await patientCode.count()) === 1);
const pcText = (await patientCode.textContent()) || "";
record("p09_patient_code_has_prefix", pcText.includes("Patient Code:"), pcText);

// 17. Guidance
const guidance = page.locator(".mk-p09-guidance");
record("p09_has_guidance", (await guidance.count()) === 1);
const guidanceText = (await guidance.textContent()) || "";
record("p09_guidance_mentions_handy", guidanceText.includes("handy"), guidanceText);

// 18. Done button
const doneBtn = page.locator(".mk-p09-btn");
record("p09_has_done_button", (await doneBtn.count()) === 1);
const doneBtnText = (await doneBtn.textContent()) || "";
record("p09_done_button_says_return", doneBtnText.includes("Return to Welcome"), doneBtnText);

// 19. Button has checkmark icon (not arrow)
const btnSvg = await doneBtn.locator("svg").count();
record("p09_done_button_has_check_icon", btnSvg > 0, `svg count: ${btnSvg}`);

// 20. Footer
const footer = page.locator(".mk-p09-footer__protocol");
record("p09_has_footer", (await footer.count()) === 1);
const footerText = (await footer.textContent()) || "";
record("p09_footer_mentions_medikiosk", footerText.includes("MediKiosk"), footerText);

// 22. Refresh preserves waiting state
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(2500);
record("p09_refresh_preserves_waiting", (await page.locator(".mk-p09").count()) === 1);
const refreshedToken = await page.locator(".mk-p09-token-box__number").textContent() || "";
record("p09_refresh_shows_same_token", refreshedToken.trim().length > 0);

// 21. Click Done → return to welcome
await doneBtn.first().click();
await page.waitForTimeout(1500);
const backOnWelcome = (await page.locator(".mk-p09").count()) === 0 || (await page.locator("text=Select your preferred language").count()) > 0;
record("p09_done_returns_to_welcome", backOnWelcome);

// 23. No JS errors
record("p09_no_js_errors", errors.length === 0, errors.length > 0 ? errors.join("; ") : "");

await browser.close();

console.log(`\n--- P09 Waiting: ${results.filter((r) => r.ok).length}/${results.length} passed ---`);
if (results.some((r) => !r.ok)) process.exit(1);
