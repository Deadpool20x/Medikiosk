// P08 TOKEN ISSUED browser tests — drives the real Next.js app + mock backend.
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

// Create session → navigate to summary → generate token
console.log("creating session…");
const { session_id: sid } = await api("/session/start", "POST", {
  patient: { name: "Token Test Patient", age: 50, gender: "female" },
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

// Click Confirm & Generate Token
const confirmBtn = page.locator("button", { hasText: /confirm.*token|generate.*token/i });
if ((await confirmBtn.count()) === 0) {
  await page.locator(".mk-p07-btn", { hasText: /confirm/i }).first().click();
} else {
  await confirmBtn.first().click();
}

// Wait for P08 token screen
await page.waitForSelector(".mk-p08", { timeout: 15000 });
await page.waitForTimeout(500);

const results = [];
function record(name, ok, detail) {
  results.push({ name, ok, detail: detail || "" });
  console.log(ok ? `PASS ${name}` : `FAIL ${name}${detail ? " — " + detail : ""}`);
}

// --- Tests ---

// 1. Token screen renders
record("p08_reaches_token_screen", (await page.locator(".mk-p08").count()) === 1);

// 2. Header present
record("p08_has_header", (await page.locator(".mk-p08-header").count()) === 1);

// 3. Brand present
record("p08_has_brand", (await page.locator(".mk-p08-brand__name").count()) === 1);
const brandText = await page.locator(".mk-p08-brand__name").textContent() || "";
record("p08_brand_says_medikiosk", brandText.includes("MediKiosk"), brandText);

// 4. 7 nav pills
const navPillCount = await page.locator(".mk-p08-nav__pill").count();
record("p08_has_7_nav_pills", navPillCount === 7, `got ${navPillCount}`);

// 5. Token pill is active
const activePill = page.locator(".mk-p08-nav__pill--active");
const activePillText = (await activePill.textContent()) || "";
record("p08_token_is_active_step", activePillText.includes("Token"), activePillText);

// 6. All previous steps done (6 done pills)
const donePills = await page.locator(".mk-p08-nav__pill--done").count();
record("p08_has_6_done_pills", donePills === 6, `got ${donePills}`);

// 7. Eyebrow
const eyebrow = page.locator(".mk-p08-eyebrow");
record("p08_has_eyebrow", (await eyebrow.count()) === 1);
const eyebrowText = (await eyebrow.textContent()) || "";
record("p08_eyebrow_says_confirmation", eyebrowText.includes("CONFIRMATION"), eyebrowText);

// 8. H1
const h1 = page.locator(".mk-p08-h1");
record("p08_has_h1", (await h1.count()) === 1);
const h1Text = (await h1.textContent()) || "";
record("p08_h1_says_confirmed", h1Text.includes("confirmed"), h1Text);

// 9. Subtitle
const sub = page.locator(".mk-p08-sub");
record("p08_has_subtitle", (await sub.count()) === 1);

// 10. Card
record("p08_has_card", (await page.locator(".mk-p08-card").count()) === 1);

// 11. Status badge
const statusBadge = page.locator(".mk-p08-status__badge");
record("p08_has_status_badge", (await statusBadge.count()) === 1);
const statusText = (await statusBadge.textContent()) || "";
record("p08_status_says_intake_complete", statusText.includes("Intake Complete"), statusText);

// 12. Department section
const deptName = page.locator(".mk-p08-dept__name");
record("p08_has_department", (await deptName.count()) === 1);
const deptText = (await deptName.textContent()) || "";
record("p08_department_is_nonempty", deptText.trim().length > 0, deptText);

// 13. Token box
const tokenNumber = page.locator(".mk-p08-token-box__number");
record("p08_has_token_number", (await tokenNumber.count()) === 1);
const tokenText = (await tokenNumber.textContent()) || "";
record("p08_token_is_nonempty", tokenText.trim().length > 0, tokenText);

// 14. Patient code
const patientCode = page.locator(".mk-p08-patient-code__badge");
record("p08_has_patient_code", (await patientCode.count()) === 1);
const pcText = (await patientCode.textContent()) || "";
record("p08_patient_code_has_prefix", pcText.includes("Patient Code:"), pcText);

// 15. Guidance
const guidance = page.locator(".mk-p08-guidance");
record("p08_has_guidance", (await guidance.count()) === 1);
const guidanceText = (await guidance.textContent()) || "";
record("p08_guidance_mentions_wait", guidanceText.includes("wait"), guidanceText);

// 16. Done button
const doneBtn = page.locator(".mk-p08-btn");
record("p08_has_done_button", (await doneBtn.count()) === 1);
const doneBtnText = (await doneBtn.textContent()) || "";
record("p08_done_button_says_done", doneBtnText.includes("Done"), doneBtnText);

// 17. Footer
const footer = page.locator(".mk-p08-footer__protocol");
record("p08_has_footer", (await footer.count()) === 1);
const footerText = (await footer.textContent()) || "";
record("p08_footer_mentions_medikiosk", footerText.includes("MediKiosk"), footerText);

// 18. Token pill has checkmark (SVG)
const tokenPill = page.locator(".mk-p08-nav__pill--active");
const tokenPillSvg = await tokenPill.locator("svg").count();
record("p08_token_pill_has_no_check", tokenPillSvg === 0, `svg count: ${tokenPillSvg}`);

// 19. Done pills have checkmarks
const donePillWithCheck = page.locator(".mk-p08-nav__pill--done");
let doneWithCheck = 0;
for (let i = 0; i < (await donePillWithCheck.count()); i++) {
  const svgCount = await donePillWithCheck.nth(i).locator("svg").count();
  if (svgCount > 0) doneWithCheck++;
}
record("p08_done_pills_have_checks", doneWithCheck === 6, `got ${doneWithCheck}`);

// 20. Click Done -> goes to P09 waiting screen
await doneBtn.first().click();
await page.waitForSelector(".mk-p09", { timeout: 10000 });
record("p08_done_goes_to_waiting", (await page.locator(".mk-p09").count()) === 1);

// 21. No JS errors
record("p08_no_js_errors", errors.length === 0, errors.length > 0 ? errors.join("; ") : "");

await browser.close();

console.log(`\n--- P08 Token: ${results.filter((r) => r.ok).length}/${results.length} passed ---`);
if (results.some((r) => !r.ok)) process.exit(1);
