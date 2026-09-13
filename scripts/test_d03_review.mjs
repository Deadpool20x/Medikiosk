// D03 DOCTOR REVIEW / EDIT / CONFIRM browser tests — real Next.js app + real backend (mocked LLM/OCR).
// Expected running: p0_server.py on 127.0.0.1:8001, `npm run dev` on :3000.
import { createRequire } from "module";
import { readFileSync } from "fs";
const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");

const API = "http://127.0.0.1:8001";
const WEB = "http://localhost:3000";

async function pageErrors(page) {
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e.message || e)));
  page.on("console", (m) => {
    if (m.type() === "error") errs.push(m.text());
  });
  return errs;
}

async function freshPage(w, h) {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page._errs = await pageErrors(page);
  return page;
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

const ALLOWED_CONF = ["High confidence", "Review", "Manually corrected"];

// 1. Seeded Kayachikitsa case with a real uploaded prescription.
const patientName = `D03Rev Pat${Date.now() % 100000}`;
const { session_id: caseSid, token: caseToken, department: caseDept } = await seedPatient(
  patientName,
  41,
  "male",
  ["knee joint pain and stiffness", "3 months ago", "3 months", "moderate", "aching", "worse in the morning"]
);
record("d03_case_seeded_kaya", caseDept === "Kayachikitsa" && String(caseToken).startsWith("KY-"), JSON.stringify({ caseToken, caseDept }));

const buf = readFileSync("D:/project/Medikishok/frontend/sample-prescription.png");
const form = new FormData();
form.append("file", new Blob([buf], { type: "image/png" }), "sample-prescription.png");
const upRes = await fetch(`${API}/session/${caseSid}/upload`, { method: "POST", body: form });
record("d03_upload_accepted", upRes.ok && upRes.status < 300, `HTTP ${upRes.status}`);
await api(`/session/${caseSid}/documents-complete`, "POST");

// 2. Main flow: D01 -> D02 -> D03 via buttons; edit; save; confirm; provenance; docs correction; discard.
{
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript((view) => {
    window.sessionStorage.setItem("mk_doctor_view", JSON.stringify(view));
  }, { kind: "queue", department: "Kayachikitsa" });
  const page = await context.newPage();
  page._errs = await pageErrors(page);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d01-table", { timeout: 20000 });

  // D01 -> D02.
  await page.locator("tr", { hasText: String(caseToken) }).locator(".mk-d01-open").first().click();
  await page.waitForSelector(".mk-d02-header", { timeout: 15000 });
  record("d03_from_queue_to_case", (await page.locator(".mk-d02-header").count()) === 1);

  // D02 -> D03 via Review & Edit.
  await page.locator("button:has-text('Review & Edit Case Details')").click();
  await page.waitForSelector("[data-purpose='d03-review']", { timeout: 15000 });
  record("d03_review_screen_reached", true);

  // Correct patient case: queue token from this seeded case is on the banner.
  const d03Text = (await page.locator("[data-purpose='d03-review']").innerText()) || "";
  record("d03_matches_patient_case", d03Text.includes(String(caseToken)), caseToken);

  // Visual structure: standalone light clinical-OS header, no dark D01/D02 sidebar shell.
  record("d03_no_dark_sidebar", (await page.locator(".mk-sidebar").count()) === 0, "dark sidebar must not be present on D03");
  const os = await page.locator("[data-purpose='d03-os']");
  record("d03_light_os_header", (await os.count()) === 1);
  const osText = (await os.innerText()) || "";
  record("d03_os_brand_identifiers", ["MEDIKIOSK", "OPD CLINICAL OS", "ONLINE", "QUEUE ACTIVE", "Demo Clinician"].every((s) => osText.includes(s)), "header must show brand, online/queue-active status, and account control");
  record("d03_os_nav_links", ["Queue", "Cases", "Archive"].every((s) => osText.includes(s)), "header must show Queue | Cases | Archive");

  // Composition: topbar breadcrumb + banner + 4 numbered sections + footer.
  const banner = await page.locator("[data-purpose='patient-banner']");
  record("d03_patient_banner", (await banner.count()) === 1 && ((await banner.innerText()) || "").includes("Review & Edit"));
  record("d03_back_breadcrumb", (((await page.locator("[data-purpose='d03-review']").locator(".mk-d03-back").first().innerText()) || "").includes("Back to Case")));
  const sections = [
    "[data-purpose='section-01-hpi']",
    "[data-purpose='section-02-medical']",
    "[data-purpose='section-03-ayurvedic']",
    "[data-purpose='section-04-documents']",
  ];
  for (const sel of sections) {
    if ((await page.locator(sel).count()) !== 1) { record(`d03_section_${sel.replace(/[^0-9]/g, "")}_present`, false, sel); }
  }
  record("d03_sections_present", (await Promise.all(sections.map((s) => page.locator(s).count()))).every((c) => c === 1));

  // Numbered chips 01-04.
  const nums = await page.locator(".mk-d03-card__number").allInnerTexts();
  record("d03_numbered_sections", JSON.stringify(nums) === JSON.stringify(["01", "02", "03", "04"]), nums.join(","));

  // Editing is a dedicated D03 screen, NOT the legacy D02 inline panel.
  record("d03_no_legacy_inline_panel", (await page.locator("[data-purpose='review-edit-panel']").count()) === 0);

  // Edit fields, Save, verify persistence via backend.
  await page.locator("[data-purpose='chief-complaint-input']").fill("Chronic knee pain, stiffness every morning");
  await page.locator("[data-purpose='onset-input']").fill("Three months ago");
  await page.locator("[data-purpose='duration-input']").fill("3 months");
  await page.locator("[data-purpose='severity-input']").fill("moderate-severe");
  await page.locator("[data-purpose='character-input']").fill("aching and dull");
  await page.locator("[data-purpose='symptoms-input']").fill("morning stiffness, swelling, difficulty climbing stairs");
  await page.locator("[data-purpose='d03-footer'] button:has-text('Save Changes')").click();

  let afterEdit = null;
  for (let i = 0; i < 40; i++) {
    const s = await api(`/session/${caseSid}`);
    if (s.chief_complaint === "Chronic knee pain, stiffness every morning" && s.doctor_review.edited) { afterEdit = s; break; }
    await new Promise((r) => setTimeout(r, 250));
  }
  record("d03_edit_persisted", !!afterEdit && afterEdit.chief_complaint === "Chronic knee pain, stiffness every morning" && afterEdit.history_of_present_illness.severity === "moderate-severe" && afterEdit.history_of_present_illness.associated_symptoms.length === 3 && afterEdit.doctor_review.edited === true, JSON.stringify(afterEdit ? { cc: afterEdit.chief_complaint, hpi: afterEdit.history_of_present_illness, edited: afterEdit.doctor_review.edited } : null).slice(0, 200));

  // Confidence labels restricted to the allowed set.
  const chips = await page.locator(".mk-d03-chip").allInnerTexts();
  const confChips = chips.map((c) => c.trim()).filter((c) => c && !["Review & Edit", "Source: Patient Interview", "Editable", "Source: Patient Interview & Uploaded Document", "Patient-Reported • Uninterpreted", "From uploaded document", "Doctor Verified", "High confidence"].includes(c) && !/document/i.test(c));
  record("d03_confidence_labels_only_allowed", confChips.length === 0 || confChips.every((c) => ALLOWED_CONF.includes(c)), confChips.join(","));

  // Discard returns fields to last-saved values.
  await page.locator("[data-purpose='severity-input']").fill("changed locally");
  await page.locator("[data-purpose='d03-footer'] button:has-text('Discard Changes')").click();
  const sevAfterDiscard = await page.locator("[data-purpose='severity-input']").inputValue();
  record("d03_discard_resets_to_saved", sevAfterDiscard === "moderate-severe", sevAfterDiscard);

  // Confirm persists.
  await page.locator("[data-purpose='d03-footer'] button:has-text('Confirm Case')").click();
  let afterConfirm = null;
  for (let i = 0; i < 40; i++) {
    const s = await api(`/session/${caseSid}`);
    if (s.doctor_review.confirmed === true) { afterConfirm = s; break; }
    await new Promise((r) => setTimeout(r, 250));
  }
  record("d03_confirm_persisted", !!afterConfirm && afterConfirm.doctor_review.confirmed === true, JSON.stringify(afterConfirm ? afterConfirm.doctor_review : null));
  await page.waitForFunction(() => document.body.innerText.includes("Confirmed"), { timeout: 15000 });
  const footerText = ((await page.locator("[data-purpose='d03-footer']").innerText()) || "");
  record("d03_footer_confirmed_state", footerText.includes("Confirmed"), footerText.includes("Confirmed") ? footerText.slice(-120) : "");
  record("d03_confirm_btn_disabled_after", await page.locator("[data-purpose='d03-footer'] button:has-text('Confirmed')").isDisabled(), "");
  record("d03_no_js_errors", page._errs.length === 0, page._errs.join(";"));

  await page.close();
  await browser.close();
}

// 3. Document correction with original-extraction preservation + Doctor Verified provenance.
{
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript((view) => {
    window.sessionStorage.setItem("mk_doctor_view", JSON.stringify(view));
  }, { kind: "review", sessionId: caseSid, department: "Kayachikitsa" });
  const page = await context.newPage();
  page._errs = await pageErrors(page);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-purpose='d03-review']", { timeout: 20000 });

  const docCards = await page.locator("[data-purpose^='doc-extract-']").count();
  if (docCards > 0) {
    const firstIdx = 0;
    const originalBefore = await api(`/session/${caseSid}`);
    const docBefore = originalBefore.documents[firstIdx];
    await page.locator(`[data-purpose='doc-extract-${firstIdx}'] button:has-text('Edit')`).click();
    await page.waitForSelector("[data-purpose='doc-correction-form']", { timeout: 10000 });
    await page.locator("[aria-label='Corrected medicine value']").fill("Ashwagandha 500 mg corrected");
    await page.locator("[data-purpose='doc-correction-form'] button:has-text('Save correction')").click();
    let fixed = null;
    for (let i = 0; i < 40; i++) {
      const s = await api(`/session/${caseSid}`);
      if (s.documents[firstIdx].manually_corrected === true) { fixed = s.documents[firstIdx]; break; }
      await new Promise((r) => setTimeout(r, 250));
    }
    record("d03_doc_corrected", !!fixed && fixed.extracted_value === "Ashwagandha 500 mg corrected", JSON.stringify(fixed && { v: fixed.extracted_value, mc: fixed.manually_corrected }));
    record("d03_doc_original_preserved", !!fixed && !!fixed.original_extraction && fixed.original_extraction.medicine === docBefore.extracted_value, JSON.stringify(fixed && fixed.original_extraction).slice(0, 140));
    await page.waitForFunction(() => document.body.innerText.includes("Doctor Verified"), { timeout: 10000 }).catch(() => {});
    record("d03_doc_verified_provenance", ((await page.locator("[data-purpose='doc-extract-0']").innerText()) || "").includes("Doctor Verified"));
  } else {
    record("d03_doc_corrected", false, "no documents present on case");
    record("d03_doc_original_preserved", false, "no documents present on case");
    record("d03_doc_verified_provenance", false, "no documents present on case");
  }
  record("d03_doc_step_no_js_errors", page._errs.length === 0, page._errs.join(";"));
  await page.close();
  await browser.close();
}

// 4. Refresh preserves the D03 review view via sessionStorage.
{
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page._errs = await pageErrors(page);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });
  await page.click("button:has-text('Kayachikitsa Queue')");
  await page.waitForSelector(".mk-d01-table", { timeout: 20000 });
  await page.locator("tr", { hasText: String(caseToken) }).locator(".mk-d01-open").first().click();
  await page.waitForSelector(".mk-d02-header", { timeout: 15000 });
  await page.locator("button:has-text('Review / Edit Case')").click();
  await page.waitForSelector("[data-purpose='d03-review']", { timeout: 15000 });
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector("[data-purpose='d03-review']", { timeout: 20000 });
  const afterReload = ((await page.locator("[data-purpose='d03-review']").innerText()) || "").includes(String(caseToken));
  record("d03_refresh_preserves_review", afterReload);
  await page.close();
  await browser.close();
}

// 5. Safety-flagged session: banner, no editable form, confirm disabled.
{
  const { session_id: flagSid, token: flagToken } = await api("/session/start", "POST", {
    patient: { name: `Flag Pat${Date.now() % 100000}`, age: 48, gender: "female" },
    language: "en",
    visit_type: "new",
  });
  await api(`/session/${flagSid}/consent`, "POST", { consent_given: true });
  await api(`/session/${flagSid}/patient-code`, "POST");
  await api(`/session/${flagSid}/answer`, "POST", { answer: "chest pain" });
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript((view) => {
    window.sessionStorage.setItem("mk_doctor_view", JSON.stringify(view));
  }, { kind: "review", sessionId: flagSid, department: "Kayachikitsa" });
  const page = await context.newPage();
  page._errs = await pageErrors(page);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-purpose='safety-flagged-review']", { timeout: 20000 });
  const st = ((await page.locator("[data-purpose='safety-flagged-review']").innerText()) || "");
  record("d03_flagged_safety_banner", st.includes("Safety Flagged") && st.includes("cannot be reviewed"), st.slice(0, 120));
  record("d03_flagged_no_editable_fields", (await page.locator("[data-purpose='severity-input']").count()) === 0);
  record("d03_flagged_no_confirm", (await page.locator("[data-purpose='d03-footer']").count()) === 0);
  record("d03_flagged_no_js_errors", page._errs.length === 0, page._errs.join(";"));
  await page.close();
  await browser.close();
}

// 6. Mobile 390 — stacked layout, footer visible, no horizontal overflow, no obscured content.
{
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await context.addInitScript((view) => {
    window.sessionStorage.setItem("mk_doctor_view", JSON.stringify(view));
  }, { kind: "review", sessionId: caseSid, department: "Kayachikitsa" });
  const page = await context.newPage();
  page._errs = await pageErrors(page);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-purpose='d03-review']", { timeout: 20000 });
  const w = await page.evaluate(() => document.documentElement.scrollWidth);
  record("d03_mobile_no_h_overflow", w <= 390, `scrollWidth=${w}`);
  const footer = page.locator("[data-purpose='d03-footer']");
  record("d03_mobile_footer_visible", (await footer.count()) === 1);
  const fBox = await footer.boundingBox();
  record("d03_mobile_footer_bottom_visible", !!fBox && fBox.y + fBox.height <= 844, JSON.stringify(fBox));
  const needs = ["[data-purpose='section-01-hpi']", "[data-purpose='section-02-medical']", "[data-purpose='section-03-ayurvedic']", "[data-purpose='section-04-documents']"];
  let allClear = true;
  for (const sel of needs) {
    if ((await page.locator(sel).count()) === 0) continue;
    const secBox = await page.locator(sel).scrollIntoViewIfNeeded().then(() => page.locator(sel).boundingBox());
    if (secBox && fBox && secBox.bottom > fBox.top) { allClear = false; console.log(`  obscured: ${sel}`); }
  }
  record("d03_mobile_content_clears_footer", allClear);
  record("d03_mobile_field_row_stacked", (await page.evaluate(() => {
    const a = document.querySelector("[data-purpose='severity-input']");
    const b = document.querySelector("[data-purpose='character-input']");
    if (!a || !b) return false;
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    return rb.top >= ra.bottom;
  })));
  record("d03_mobile_touch_targets_48px", (await page.evaluate(() => {
    const f = document.querySelector("[data-purpose='d03-footer']");
    if (!f) return false;
    const btns = [...f.querySelectorAll(".mk-d03-btn")];
    return btns.length > 0 && btns.every((b) => { const r = b.getBoundingClientRect(); return r.height >= 48 && r.width >= 48; });
  })));
  record("d03_mobile_no_js_errors", page._errs.length === 0, page._errs.join(";"));
  await page.close();
  await browser.close();
}

const passed = RESULTS.filter((r) => r.ok).length;
const failed = RESULTS.filter((r) => !r.ok).length;
console.log(`--- D03 Review: ${passed}/${RESULTS.length} passed ---`);
process.exit(failed === 0 ? 0 : 1);