// D01 DOCTOR DEPARTMENT QUEUE browser tests — real Next.js app + real backend (mocked LLM/OCR).
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

const RESULTS = [];
function record(name, ok, detail) {
  RESULTS.push({ name, ok });
  console.log(ok ? `PASS ${name}` : `FAIL ${name}${detail ? " — " + detail : ""}`);
}

async function seedPatient(name, age, gender, answers) {
  const { session_id } = await api("/session/start", "POST", {
    patient: { name, age, gender },
    language: "en",
    visit_type: "new",
  });
  await api(`/session/${session_id}/consent`, "POST", { consent_given: true });
  await api(`/session/${session_id}/patient-code`, "POST");
  for (const a of answers) await api(`/session/${session_id}/answer`, "POST", { answer: a });
  await api(`/session/${session_id}/documents-complete`, "POST");
  const tok = await api(`/session/${session_id}/token`, "POST");
  return { session_id, token: tok.token, department: tok.department };
}

// --- Seed real backend data (baseline-aware so reruns stay deterministic) ---
const baseKY = await api("/doctor/queue?department=Kayachikitsa").then((d) => d.length);
const basePK = await api("/doctor/queue?department=Panchakarma").then((d) => d.length);

const ky1 = await seedPatient("Ravi Kumar", 42, "male", ["back pain", "2w", "2w", "mild", "dull", "stiffness"]);
const ky2 = await seedPatient("Meena Devi", 38, "female", ["neck pain", "1w", "1w", "moderate", "aching", "headache"]);
const ky3 = await seedPatient("Arjun Nair", 45, "male", ["knee pain", "3w", "3w", "mild", "dull", "stiffness"]);
const pk1 = await seedPatient("Lakshmi Rao", 50, "female", ["Sthaulya", "1 week ago", "1 week", "moderate", "dull", "bloating"]);
const { session_id: flaggedSid } = await api("/session/start", "POST", {
  patient: { name: "Dinesh Kumar", age: 60, gender: "male" },
  language: "en",
  visit_type: "new",
});
await api(`/session/${flaggedSid}/consent`, "POST", { consent_given: true });
await api(`/session/${flaggedSid}/patient-code`, "POST");
await api(`/session/${flaggedSid}/answer`, "POST", { answer: "chest pain" });

record("d01_kaya_seeded", ky1.department === "Kayachikitsa" && ky1.token.startsWith("KY-"), JSON.stringify(ky1));
record("d01_pk_seeded", pk1.department === "Panchakarma" && pk1.token.startsWith("PK-"), JSON.stringify(pk1));
const flaggedTokenResp = await fetch(`${API}/session/${flaggedSid}/token`, { method: "POST" });
record("d01_flagged_cannot_issue_token", flaggedTokenResp.status === 403, `status=${flaggedTokenResp.status}`);

const browser = await chromium.launch({ channel: "msedge", headless: true });

async function freshPage(width, height) {
  const page = await browser.newPage({ viewport: { width, height } });
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("Failed to load resource")) errs.push(m.text()); });
  page._errs = errs;
  return page;
}

// 1. Desktop Kayachikitsa queue — real data, faithful structure
{
  const page = await freshPage(1440, 900);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });

  const navLabels = await page.locator(".mk-sidebar__item").allTextContents();
  record("d01_nav_only_approved_destinations",
    navLabels.length === 3 &&
    navLabels.some((l) => /Emergency Escalations/.test(l)) &&
    navLabels.some((l) => /Kayachikitsa Queue/.test(l)) &&
    navLabels.some((l) => /Panchakarma Queue/.test(l)),
    navLabels.join(" | "));
  record("d01_nav_no_forbidden_destinations",
    !navLabels.some((l) => /Dashboard|Analytics|Patient Sessions|Settings/i.test(l)), navLabels.join(" | "));

  await page.click("button:has-text('Kayachikitsa Queue')");
  await page.waitForSelector(".mk-d01-table", { timeout: 15000 });
  await page.waitForTimeout(400);

  const title = (await page.locator(".mk-d01-ribbon__title").textContent()) || "";
  record("d01_title_is_department", title.trim() === "Kayachikitsa", title);

  const countText = (await page.locator(".mk-d01-ribbon__count").textContent()) || "";
  record("d01_count_matches_real_data", countText.trim() === `${baseKY + 3} patients waiting`, countText);

  const headers = (await page.locator(".mk-d01-table thead th").allTextContents()).map((h) => h.trim());
  record("d01_columns_match_master",
    headers.join("|") === "Queue Token|Patient Code|Status|Check-in Time|Action", headers.join("|"));

  const rows = page.locator(".mk-d01-table tbody tr");
  const rowCount = await rows.count();
  record("d01_row_count_matches_real_data", rowCount === baseKY + 3, `rows=${rowCount} base=${baseKY}`);

  const tokens = await page.locator(".mk-d01-token").allTextContents();
  record("d01_tokens_are_real_kya", tokens.length === rowCount && tokens.every((t) => /^KY-\d+$/.test(t.trim())), tokens.join(","));

  const codes = await page.locator(".mk-d01-code").allTextContents();
  record("d01_patient_codes_real", codes.length === rowCount && codes.every((c) => /^MK-[A-F0-9]+$/i.test(c.trim())), codes.join(","));

  const times = await page.locator(".mk-d01-time").allTextContents();
  record("d01_checkin_12h_format", times.length === rowCount && times.every((t) => /^\d{1,2}:\d{2}\s[APap][Mm]$/.test(t.trim())), times.join(","));

  const statuses = await page.locator(".mk-d01-status").allTextContents();
  record("d01_status_pills_waiting_ready", statuses.length === rowCount && statuses.every((s) => /Waiting|Ready/.test(s.trim())), statuses.join(","));

  record("d01_first_row_is_next", (await page.locator(".mk-d01-bar--next").count()) === 1);
  record("d01_first_row_primary_action", (await page.locator(".mk-d01-open--next").count()) === 1);
  record("d01_open_case_buttons", (await page.locator(".mk-d01-open", { hasText: "Open Case" }).count()) === rowCount);

  const bodyText = (await page.locator(".mk-main-content").textContent()) || "";
  record("d01_flagged_patient_not_in_queue", !bodyText.includes("Dinesh Kumar") && !bodyText.includes("chest pain"));
  record("d01_no_fake_wait_times", !bodyText.includes("minute") && !bodyText.includes("min wait"));
  record("d01_no_js_errors", page._errs.length === 0, page._errs.join(";"));

  // Open Case → D02 (existing DoctorCase), then back
  await page.locator(".mk-d01-open").first().click();
  await page.waitForSelector(".mk-d02-header", { timeout: 15000 });
  record("d01_open_case_reaches_d02", true);

  // refresh preserves department queue
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d01-table", { timeout: 15000 });
  const afterTitle = (await page.locator(".mk-d01-ribbon__title").textContent()) || "";
  record("d01_refresh_preserves_department", afterTitle.trim() === "Kayachikitsa", afterTitle);
  record("d01_refresh_preserves_no_js_errors", page._errs.length === 0, page._errs.join(";"));

  await page.close();
}

// 2. Panchakarma queue — same component, different config, no mixing
{
  const page = await freshPage(1440, 900);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });
  await page.click("button:has-text('Panchakarma Queue')");
  await page.waitForSelector(".mk-d01-table", { timeout: 15000 });
  await page.waitForTimeout(400);

  const pkTitle = (await page.locator(".mk-d01-ribbon__title").textContent()) || "";
  record("d01_pk_title", pkTitle.trim() === "Panchakarma", pkTitle);

  const rows = page.locator(".mk-d01-table tbody tr");
  const rowCount = await rows.count();
  record("d01_pk_row_count", rowCount === basePK + 1, `rows=${rowCount}`);

  const pkTokens = await page.locator(".mk-d01-token").allTextContents();
  record("d01_pk_tokens_only_pk", pkTokens.length === rowCount && pkTokens.every((t) => /^PK-\d+$/.test(t.trim())), pkTokens.join(","));

  const pkBody = (await page.locator(".mk-main-content").textContent()) || "";
  record("d01_pk_no_kya_leak", !/KY-\d/.test(pkBody));

  await page.close();
}

// 3. Kayachikitsa filter does not show Panchakarma tokens
{
  const page = await freshPage(1440, 900);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });
  await page.click("button:has-text('Kayachikitsa Queue')");
  await page.waitForSelector(".mk-d01-table", { timeout: 15000 });
  await page.waitForTimeout(400);
  const kayaTokens = await page.locator(".mk-d01-token").allTextContents();
  record("d01_kaya_no_pk_leak", kayaTokens.every((t) => !/PK-\d/.test(t)), kayaTokens.join(","));
  await page.close();
}

// 4. Emergency still reachable and shows the flagged session
{
  const page = await freshPage(1440, 900);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });
  await page.click("button:has-text('Emergency Escalations')");
  await page.waitForFunction(() => document.body.innerText.includes("Active Escalation Queue"), { timeout: 15000 });
  const emgBody = (await page.locator(".mk-main-content").textContent()) || "";
  record("d01_emergency_reachable", emgBody.includes("Dinesh Kumar"), emgBody.slice(0, 200));
  await page.close();
}

// 5. Empty queue state (intercepted empty response)
{
  const page = await freshPage(1440, 900);
  await page.route("**/doctor/queue**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" })
  );
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });
  await page.click("button:has-text('Kayachikitsa Queue')");
  await page.waitForSelector(".mk-d01-state", { timeout: 15000 });
  const emptyText = (await page.locator(".mk-d01-state").textContent()) || "";
  record("d01_empty_state_renders", emptyText.includes("No patients waiting"), emptyText);
  await page.close();
}

// 6. Backend error → safe retryable state
{
  const page = await freshPage(1440, 900);
  let intercepted = true;
  await page.route("**/doctor/queue**", (route) => {
    if (intercepted) route.abort();
    else route.continue();
  });
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });
  await page.click("button:has-text('Kayachikitsa Queue')");
  await page.waitForSelector(".mk-d01-error", { timeout: 15000 });
  record("d01_error_state_renders", (await page.locator(".mk-d01-error__retry").count()) === 1);
  intercepted = false;
  await page.click(".mk-d01-error__retry");
  await page.waitForSelector(".mk-d01-table", { timeout: 15000 });
  record("d01_error_retry_recovers", (await page.locator(".mk-d01-table tbody tr").count()) >= 1);
  await page.close();
}

// 7. Mobile 390px — nav reachable, stacked readable rows, touch targets, no overflow
{
  const page = await freshPage(390, 844);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });
  await page.click("button:has-text('Kayachikitsa Queue')");
  await page.waitForSelector(".mk-d01-table", { timeout: 15000 });
  await page.waitForTimeout(400);

  record("d01_mobile_nav_reachable", (await page.locator(".mk-sidebar__item").count()) === 3);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  record("d01_mobile_no_horizontal_overflow", overflow <= 0, `overflow=${overflow}`);

  const rowCount = await page.locator(".mk-d01-table tbody tr").count();
  record("d01_mobile_rows_stack", rowCount >= 1);

  const labels = await page.locator(".mk-d01-table tbody td[data-label]").evaluateAll((tds) => tds.map((td) => td.getAttribute("data-label")));
  record("d01_mobile_labels_shown", labels.length >= 3 && labels.includes("Status"), labels.join(","));

  const btn = page.locator(".mk-d01-open").first();
  const box = await btn.boundingBox();
  record("d01_mobile_touch_target_48px", !!box && box.height >= 48 && box.width >= 48, box ? `h=${box.height} w=${box.width}` : "no box");
  record("d01_mobile_open_case_full_width", !!box && box.width > 260, box ? `w=${box.width}` : "no box");

  record("d01_mobile_pk_reachable", true);
  await page.click("button:has-text('Panchakarma Queue')");
  await page.waitForSelector(".mk-d01-table", { timeout: 15000 });
  const mpk = (await page.locator(".mk-d01-ribbon__title").textContent()) || "";
  record("d01_mobile_pk_nav_works", mpk.trim() === "Panchakarma", mpk);

  record("d01_mobile_no_js_errors", page._errs.length === 0, page._errs.join(";"));
  await page.close();
}

await browser.close();

const failed = RESULTS.filter((r) => !r.ok);
console.log(`\n--- D01 Queue: ${RESULTS.length - failed.length}/${RESULTS.length} passed ---`);
if (failed.length) process.exit(1);