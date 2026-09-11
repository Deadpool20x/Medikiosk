// P02 PATIENT CONSENT browser test.
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

const consentPayloads = [];
page.on("request", (req) => {
  if (req.url().includes("/consent") && req.method() === "POST") {
    consentPayloads.push({ url: req.url(), postData: req.postData() });
  }
});

// 1. Reach the consent screen (P01 -> continue -> welcome form -> start)
await page.goto(WEB, { waitUntil: "networkidle" });
await page.waitForSelector(".mk-p01-lang-card");
await page.click(".mk-p01-cta");
await page.waitForURL("**/patient", { timeout: 15000 });
await page.waitForSelector("input[placeholder='Enter your name']", { timeout: 15000 });
await page.fill("input[placeholder='Enter your name']", "Ravi Kumar");
await page.fill("input[placeholder='Enter your age']", "41");
await page.click("button:has-text('Start Now')");
await page.waitForSelector(".mk-p02", { timeout: 15000 });

// 2. Layout render: eyebrow, title, sub, 3 info points, checkbox, actions, footer
record("p02_title", (await page.locator(".mk-p02-h1").textContent()) === "Patient Consent");
record("p02_eyebrow", ((await page.locator(".mk-p02-eyebrow").textContent()) || "").toLowerCase().includes("consent"));
record("p02_three_info_points", (await page.locator(".mk-p02-point").count()) === 3, `count=${await page.locator(".mk-p02-point").count()}`);
record("p02_has_subtitle", (await page.locator(".mk-p02-sub").textContent()).length > 20);
record("p02_has_checkbox", (await page.locator(".mk-p02-agree__check").count()) === 1);
record("p02_has_footer", ((await page.locator(".mk-p02-footer").textContent()) || "").includes("MediKiosk"));
record("p02_has_back_and_primary", (await page.locator(".mk-p02-btn--back").count()) === 1 && (await page.locator(".mk-p02-btn--primary").count()) === 1);

// 3. Stepper shows Consent active, Language done
const navClasses = await page.locator(".mk-p02-nav__pill").evaluateAll((els) => els.map((el) => el.className));
const activePillIdx = navClasses.findIndex((c) => c.includes("mk-p02-nav__pill--active"));
record("p02_stepper_order", navClasses.length === 7, `count=${navClasses.length}`);
record("p02_consent_is_active_step", activePillIdx === 1, `activeIdx=${activePillIdx}`);

// 4. Unchecked consent -> primary disabled (cannot continue)
const disabledUnchecked = await page.locator(".mk-p02-btn--primary").isDisabled();
record("p02_cannot_continue_unchecked", disabledUnchecked);

// 5. No patient code visible before consent
const pageTextBefore = await page.locator("body").textContent();
record("p02_no_patient_code_before_consent", !(pageTextBefore || "").includes("patient code"));

// 6. Check agreement -> primary enabled
await page.check(".mk-p02-agree__check");
const enabledChecked = await page.locator(".mk-p02-btn--primary").isEnabled();
record("p02_can_continue_after_check", enabledChecked);

// 7. Agree & Continue -> POST /session/{id}/consent {"consent_given":true}, moves to code screen
await page.click(".mk-p02-btn--primary");
await page.waitForURL("**/patient", { timeout: 15000 });
await page.waitForSelector("text=Patient Code", { timeout: 15000 });
record("p02_consent_post_sent", consentPayloads.length === 1 && JSON.parse(consentPayloads[0].postData).consent_given === true, consentPayloads.length ? consentPayloads[0].postData : "no payload");
record("p02_reached_code_screen_after_consent", true);

// 8. Refresh -> consent not lost (session restored, still on code screen, no re-prompt)
await page.reload({ waitUntil: "networkidle" });
await page.waitForSelector("text=Patient Code", { timeout: 15000 });
const textAfterRefresh = await page.locator("body").textContent();
record("p02_refresh_keeps_consent", !(textAfterRefresh || "").includes("Patient Consent"));

record("no_page_errors", errors.length === 0, errors.join("; "));

await browser.close();
const bad = results.filter((r) => !r.ok);
console.log(bad.length === 0 ? "ALL P02 CONSENT CHECKS GREEN" : `FAILURES: ${JSON.stringify(bad, null, 2)}`);
process.exit(bad.length === 0 ? 0 : 1);