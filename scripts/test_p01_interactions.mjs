// P01 INTERACTION RESTORATION browser test.
// Drives the real Next.js dev app on :3000 (mock backend on :8001).
import { createRequire } from "module";
const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");

const WEB = "http://localhost:3000";

const results = [];
function record(name, ok, note = "") {
  results.push({ name, ok, note });
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${note ? " — " + note : ""}`);
}

const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

const startPayloads = [];
page.on("request", (req) => {
  if (req.url().includes("/session/start") && req.method() === "POST") {
    startPayloads.push({ url: req.url(), postData: req.postData() });
  }
});

const active = () => page.locator(".mk-p01-lang-card--active").evaluateAll((els) => els.map((el) => el.textContent));
const statusActive = () => page.locator(".mk-p01-status-card--active").evaluateAll((els) => els.map((el) => el.textContent));

// 1. Landing page renders all four languages
await page.goto(WEB, { waitUntil: "networkidle" });
await page.waitForSelector(".mk-p01-lang-card");
const langCount = await page.locator(".mk-p01-lang-card").count();
record("landing_shows_4_languages", langCount === 4, `count=${langCount}`);

// 2. Default: English active, New Patient active
const defaultLangs = await active();
record("default_language_english", defaultLangs.some((t) => t.includes("English")), JSON.stringify(defaultLangs));
const defaultStatus = await statusActive();
record("default_status_new_patient", defaultStatus.some((t) => t.includes("New Patient")), JSON.stringify(defaultStatus));

// 3. Click each language -> active state follows (incl. hindi/marathi/gujarati)
for (const [label, code] of [["हिन्दी", "HI"], ["मराठी", "MR"], ["ગુજરાતી", "GU"], ["English", "EN"]]) {
  await page.click(`.mk-p01-lang-card:has-text("${label}")`);
  const langs = await active();
  record(`select_language_${code}`, langs.some((t) => t.includes(code)), JSON.stringify(langs));
}

// 4. Returning Patient click must NOT activate nor navigate
const urlBefore = page.url();
await page.click(".mk-p01-status-card:has-text('Returning Patient')");
await page.waitForTimeout(300);
const rStatus = await statusActive();
record("returning_patient_stays_visual_only", rStatus.some((t) => t.includes("New Patient")) && !rStatus.some((t) => t.includes("Returning")), JSON.stringify(rStatus));
record("returning_patient_no_navigation", page.url() === urlBefore, `${urlBefore} -> ${page.url()}`);

// 5. New Patient click keeps it selected (default)
await page.click(".mk-p01-status-card:has-text('New Patient')");
const nStatus = await statusActive();
record("new_patient_selectable", nStatus.some((t) => t.includes("New Patient")), JSON.stringify(nStatus));

// 5b. Reset / Help are present on landing and visual-only (no navigation)
const url2 = page.url();
await page.click('.mk-p01-header__action[aria-label="Reset"]');
await page.click('.mk-p01-header__action[aria-label="Help"]');
await page.waitForTimeout(200);
record("reset_help_visual_only", page.url() === url2, `${url2} -> ${page.url()}`);

// 6. Select Marathi, click Continue -> language stored + sent to /session/start
await page.click('.mk-p01-lang-card:has-text("मराठी")');
await page.click(".mk-p01-cta");
await page.waitForURL("**/patient", { timeout: 15000 });
const storedLang = await page.evaluate(() => window.sessionStorage.getItem("medikiosk_preferred_language"));
record("continue_persists_selected_language", storedLang === "mr", `stored=${storedLang}`);

// 7. On P02, fill the welcome form and Start Now -> /session/start carries language mr
await page.waitForSelector("input[placeholder='Enter your name']", { timeout: 15000 });
await page.fill("input[placeholder='Enter your name']", "Ravi Kumar");
await page.fill("input[placeholder='Enter your age']", "41");
const startPayload = new Promise((resolve) => {
  page.on("request", (req) => {
    if (req.url().includes("/session/start") && req.method() === "POST") resolve(req.postData());
  });
});
await page.click("button:has-text('Start Now')");
const payload = await Promise.race([startPayload, new Promise((r) => setTimeout(() => r(null), 15000))]);
record("session_start_sent_with_language", !!payload && JSON.parse(payload).language === "mr", payload ?? "no payload");
record("session_start_visit_type_new", !!payload && JSON.parse(payload).visit_type === "new", payload ?? "no payload");

// 8. Session actually created -> consent screen
await page.waitForSelector("text=Agree & Continue", { timeout: 15000 });
record("reached_consent_screen", true);

record("no_page_errors", errors.length === 0, errors.join("; "));

await browser.close();
const bad = results.filter((r) => !r.ok);
console.log(bad.length === 0 ? "ALL P01 INTERACTION CHECKS GREEN" : `FAILURES: ${JSON.stringify(bad, null, 2)}`);
process.exit(bad.length === 0 ? 0 : 1);