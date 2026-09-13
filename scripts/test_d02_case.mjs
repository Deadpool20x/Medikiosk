// D02 DOCTOR PATIENT CASE browser tests — real Next.js app + real backend (mocked LLM/OCR).
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

async function openQueue(page) {
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });
  await page.click("button:has-text('Kayachikitsa Queue')");
  await page.waitForSelector(".mk-d01-table", { timeout: 20000 });
}

const patientName = `D02Case Pat${Date.now() % 100000}`;
const { session_id: caseSid, token: caseToken, department: caseDept } = await seedPatient(
  patientName,
  45,
  "female",
  ["back pain", "2 weeks ago", "2 weeks", "moderate", "dull", "stiffness in morning"]
);
record("d02_case_seeded_kaya", caseDept === "Kayachikitsa" && String(caseToken).startsWith("KY-"), JSON.stringify({ caseToken, caseDept }));

// Upload a real prescription image.
const buf = readFileSync("D:/project/Medikishok/frontend/sample-prescription.png");
const form = new FormData();
form.append("file", new Blob([buf], { type: "image/png" }), "sample-prescription.png");
const upRes = await fetch(`${API}/session/${caseSid}/upload`, { method: "POST", body: form });
const upText = await upRes.text();
record("d02_upload_accepted", upRes.ok && upRes.status < 300, `HTTP ${upRes.status}: ${upText.slice(0, 120)}`);
await api(`/session/${caseSid}/documents-complete`, "POST");

const savedSession = await api(`/session/${caseSid}`);
const docs0 = savedSession.documents || [];
record(
  "d02_upload_persisted_doc",
  docs0.length === 1 && docs0[0].source === "ocr" && !!docs0[0].extracted_value,
  (JSON.stringify(docs0[0]) || "").slice(0, 200)
);

// Flagged session (safety escalation) — not a queue case.
const { session_id: flaggedSid } = await api("/session/start", "POST", {
  patient: { name: "Dinesh Kumar", age: 60, gender: "male" },
  language: "en",
  visit_type: "new",
});
await api(`/session/${flaggedSid}/consent`, "POST", { consent_given: true });
await api(`/session/${flaggedSid}/patient-code`, "POST");
await api(`/session/${flaggedSid}/answer`, "POST", { answer: "chest pain" });

// 1a. Desktop — Open Case from the queue (first visible patient) renders the case view
{
  const page = await freshPage(1440, 900);
  await openQueue(page);
  const visibleRows = await page.locator(".mk-d01-table tbody tr").count();
  record("d02_queue_renders_next_patients", visibleRows >= 1, `rows=${visibleRows}`);
  await page.locator(".mk-d01-open").first().click();
  await page.waitForSelector(".mk-d02-header", { timeout: 15000 });
  record("d02_open_case_from_queue_renders", true);
  record("d02_open_case_status_pill", ((await page.locator(".mk-d02-status").textContent()) || "").includes("Awaiting Doctor Review"));
  record("d02_open_case_has_footer", (await page.locator("[data-purpose='case-action-bar']").count()) === 1);
  await page.locator(".mk-d02-back").click();
  await page.waitForSelector(".mk-d01-ribbon__title", { timeout: 15000 });
  record("d02_open_case_back_to_queue", ((await page.locator(".mk-d01-ribbon__title").textContent()) || "").trim() === "Kayachikitsa");
  record("d02_open_case_no_js_errors", page._errs.length === 0, page._errs.join(";"));
  await page.close();
}

// 1b. Desktop — targeted patient case view (direct Open via stored view, same component/data)
{
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript((view) => {
    window.sessionStorage.setItem("mk_doctor_view", JSON.stringify(view));
  }, { kind: "case", sessionId: caseSid, department: "Kayachikitsa" });
  const page = await context.newPage();
  page._errs = await pageErrors(page);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d02-header", { timeout: 20000 });

  const idents = await page.locator(".mk-d02-ident").evaluateAll((els) =>
    els.map((el) => `${el.querySelector(".mk-d02-ident__label")?.textContent}:${el.querySelector(".mk-d02-ident__value")?.textContent}`)
  );
  const idText = idents.join(" | ");
  record("d02_header_token", idents.some((i) => i.startsWith("Queue Token:")) && idText.includes(caseToken), idText);
  record("d02_header_patient_code", idents.some((i) => /^Patient Code:MK-[A-F0-9]+$/i.test(i)), idents.filter((i) => i.startsWith("Patient Code")).join(","));
  record("d02_header_department", idents.some((i) => i.startsWith("Department:") && /Kayachikitsa/i.test(i)), idText);
  record("d02_header_checkin_time", idents.some((i) => /^Check-in Time:\d{1,2}:\d{2}\s[APap][Mm]$/.test(i)), idText);
  record("d02_status_pill_awaiting", ((await page.locator(".mk-d02-status").textContent()) || "").includes("Awaiting Doctor Review"));

  const hpiLabels = await page.locator("[data-purpose='chief-complaint-section']").locator(".mk-d02-cell__label").allTextContents();
  const hpiValues = await page.locator("[data-purpose='chief-complaint-section']").locator(".mk-d02-cell__value").allTextContents();
  const have = ["Onset", "Duration", "Severity", "Character", "Associated Symptoms"].filter((l) => hpiLabels.some((h) => h.includes(l)));
  record("d02_hpi_5_cells_present", have.length === 5, hpiLabels.join(","));
  record("d02_hpi_values_real", hpiValues.every((v) => v && v !== "—"), hpiValues.join(","));
  const report = (await page.locator(".mk-d02-report__text").textContent()) || "";
  record("d02_reported_complaint", report.length > 0 && report !== "—", report.slice(0, 60));

  const caseText = (await page.locator(".mk-d02").textContent()) || "";
  record("d02_provenance_badges", caseText.split("Source: Patient Interview").length - 1 >= 2);
  record("d02_no_confident_pct", !/%\s*(confiden|high|right)/i.test(caseText) && !/\d+%/.test(caseText), caseText.match(/\d+%|%\s*\w+/g)?.join(","));
  record("d02_no_diagnosis_treatment", !/\b(treatment|recommendation|prescribed?)\b/i.test(caseText) && !/(has been|is being) (diagnosed|treated)/i.test(caseText), caseText.match(/\b(treatment|recommendation|prescribed?)\b/gi)?.join(","));
  const pills = await page.locator(".mk-d02-pill").allTextContents();
  record("d02_confidence_pills_in_set", pills.length >= 3 && pills.every((p) => ["High confidence", "Review", "Manually corrected"].includes(p.trim())), pills.join(","));

  const docText = (await page.locator("[data-purpose='document-extraction-section']").textContent()) || "";
  record("d02_doc_uploaded_name", /Uploaded (prescription|lab report|document)/.test(docText), docText.slice(0, 80));
  record("d02_doc_source_ocr", docText.includes("OCR extraction"));
  record("d02_doc_real_extract", docText.includes("Metformin"), docText.slice(0, 200));
  record("d02_doc_high_conf_pill", docText.includes("High confidence"));
  record("d02_doc_needs_correction_input", (await page.locator("[aria-label='Corrected medicine value']").count()) === 1);

  const fixInput = page.locator("[aria-label='Corrected medicine value']");
  await fixInput.fill("Ashwagandha 500 mg");
  await page.locator("button:has-text('Save correction')").click();
  await page.waitForFunction(() => document.body.innerText.includes("Manually corrected"), { timeout: 15000 });
  const afterDoc = await api(`/session/${caseSid}`);
  const fixed = afterDoc.documents[0];
  record("d02_doc_correction_persisted", fixed.manually_corrected === true && fixed.extracted_value === "Ashwagandha 500 mg", JSON.stringify(fixed).slice(0, 160));

  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d02-header", { timeout: 15000 });
  record("d02_refresh_preserves_case", (await page.locator(".mk-d02-header").count()) === 1);

  await page.locator("button:has-text('Confirm Case')").click();
  await page.waitForFunction(() => document.body.innerText.includes("Case Confirmed"), { timeout: 15000 });
  const afterConfirm = await api(`/session/${caseSid}`);
  record("d02_confirm_persisted", afterConfirm.doctor_review.confirmed === true, JSON.stringify(afterConfirm.doctor_review));
  record("d02_footer_confirmed", ((await page.locator("[data-purpose='case-action-bar']").textContent()) || "").includes("Confirmed"));

  await page.locator("button:has-text('Review & Edit Case Details')").click();
  await page.waitForSelector("[data-purpose='d03-review']", { timeout: 10000 });
  const sev = page.locator("[data-purpose='severity-input']");
  await sev.fill("severe");
  await page.locator("[data-purpose='d03-footer'] button:has-text('Save Changes')").click();
  let afterEdit = null;
  for (let i = 0; i < 40; i++) {
    const s = await api(`/session/${caseSid}`);
    if (s.history_of_present_illness.severity === "severe" && s.doctor_review.edited === true) { afterEdit = s; break; }
    await new Promise((r) => setTimeout(r, 250));
  }
  record("d02_edit_persisted", !!afterEdit && afterEdit.history_of_present_illness.severity === "severe" && afterEdit.doctor_review.edited === true, JSON.stringify(afterEdit ? afterEdit.history_of_present_illness : null).slice(0, 120));
  await page.locator(".mk-d03-back").click();
  await page.waitForSelector(".mk-d02-header", { timeout: 15000 });
  const afterEditBack = ((await page.locator("[data-purpose='chief-complaint-section']").textContent()) || "").includes("severe");
  record("d02_edited_value_rendered", afterEditBack);

  record("d02_no_js_errors", page._errs.length === 0, page._errs.join(";"));

  await page.locator(".mk-d02-back").click();
  await page.waitForSelector(".mk-d01-ribbon__title", { timeout: 15000 });
  record("d02_back_to_queue", ((await page.locator(".mk-d01-ribbon__title").textContent()) || "").trim() === "Kayachikitsa");

  await page.close();
}

// 2. Flagged session — safety banner, NOT a normal queue case
{
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript((view) => {
    window.sessionStorage.setItem("mk_doctor_view", JSON.stringify(view));
  }, { kind: "case", sessionId: flaggedSid, department: "Kayachikitsa" });
  const page = await context.newPage();
  page._errs = await pageErrors(page);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d02-safety", { timeout: 20000 });
  const safeText = (await page.locator(".mk-d02-safety").textContent()) || "";
  record("d02_flagged_safety_banner", safeText.includes("Safety Flagged") && safeText.includes("Not a standard queue case"), safeText.slice(0, 120));
  record("d02_flagged_no_case_header", (await page.locator(".mk-d02-header").count()) === 0);
  record("d02_flagged_no_docs_section", (await page.locator("[data-purpose='document-extraction-section']").count()) === 0);
  record("d02_flagged_no_js_errors", page._errs.length === 0, page._errs.join(";"));
  await page.close();
}

// 3. Mobile 390 — stacked layout, touch targets, no horizontal overflow
{
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await context.addInitScript((view) => {
    window.sessionStorage.setItem("mk_doctor_view", JSON.stringify(view));
  }, { kind: "case", sessionId: caseSid, department: "Kayachikitsa" });
  const page = await context.newPage();
  page._errs = await pageErrors(page);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d02-header", { timeout: 20000 });

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  record("d02_mobile_no_horizontal_overflow", overflow <= 1, `overflow=${overflow}`);
  const confirmBtn = page.locator("[data-purpose='case-action-bar'] button", { hasText: /Confirmed?/ });
  const box = await confirmBtn.boundingBox();
  record("d02_mobile_footer_touch_48px", !!box && box.height >= 48, box ? `h=${box.height}` : "no box");
  const cells = await page.locator(".mk-d02-cells").first().evaluate((el) => getComputedStyle(el).gridTemplateColumns);
  record("d02_mobile_cells_stack", !cells.includes(" ") && !cells.includes("fr"), cells);

  const footer = page.locator("[data-purpose='case-action-bar']");
  const footerBox = await footer.boundingBox();
  const padOk = await page.locator(".mk-d02").first().evaluate((el) => parseFloat(getComputedStyle(el).paddingBottom));
  record("d02_mobile_bottom_padding_clears_fixed_bar", footerBox !== null && padOk >= footerBox.height, `pad=${padOk} footerH=${footerBox?.height}`);

  let allClear = true;
  for (const purpose of ["chief-complaint-section", "medical-history-section", "ayurvedic-assessment-section", "document-extraction-section"]) {
    const sec = page.locator(`[data-purpose='${purpose}']`);
    if ((await sec.count()) === 0) continue;
    await sec.scrollIntoViewIfNeeded();
    await page.waitForTimeout(120);
    const secBox = await sec.boundingBox();
    const fBox = await footer.boundingBox();
    if (secBox && fBox && secBox.bottom > fBox.top) {
      allClear = false;
      console.log(`  obscured: ${purpose} bottom=${secBox.bottom} footerTop=${fBox.top}`);
    }
  }
  record("d02_mobile_no_content_obscured", allClear);
  record("d02_mobile_no_js_errors", page._errs.length === 0, page._errs.join(";"));
  await page.close();
}

const passed = RESULTS.filter((r) => r.ok).length;
const failed = RESULTS.filter((r) => !r.ok).length;
console.log(`--- D02 Case: ${passed}/${RESULTS.length} passed ---`);
process.exit(failed === 0 ? 0 : 1);