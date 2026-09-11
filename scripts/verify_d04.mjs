// D04 PROGRAMMATIC VERIFICATION — structural/layout assertions + state tests at 1440/1024/768/390.
// Expected running: p0_server.py (or dev backend) on 127.0.0.1:8001, `npm run dev` on :3000.
// Usage: node scripts/verify_d04.mjs
import { createRequire } from "module";
const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");

const API = "http://127.0.0.1:8001";
const WEB = "http://localhost:3000";
const VIEWPORTS = [
  { w: 1440, h: 900 },
  { w: 1024, h: 900 },
  { w: 768, h: 900 },
  { w: 390, h: 844 },
];
const MOCK = { // UI chrome only — never a fabricated clinical claim.
  blocklist: [
    /\brisk\b/i,
    /\b\d+(\.\d+)?\s*%\b/i,
    /\bdiagnos/i,
    /\btreat/i,
    /\bprescri/i,
    /\bdischarg/i,
    /\bseverity score\b/i,
    /\bresponse time\b/i,
    /\btriage tier\b/i,
    /\bwellness plan\b/i,
  ],
};

const RESULTS = [];
function record(ok, name, detail = "") {
  RESULTS.push({ ok, name });
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
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

const browser = await chromium.launch({ headless: true });

async function newEmergencyPage(w, h) {
  const context = await browser.newContext({ viewport: { width: w, height: h } });
  await context.addInitScript(() => {
    window.sessionStorage.setItem("mk_doctor_view", JSON.stringify({ kind: "emergency" }));
  });
  const page = await context.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
  page._errs = errs;
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d04-alert-card", { timeout: 20000 });
  return { page, context };
}

// ---- 13. API-level separation: safety sessions must never appear in D01 queues ----
{
  const [emergency, kaya, pk] = await Promise.all([
    api("/doctor/emergency"),
    api("/doctor/queue?department=Kayachikitsa"),
    api("/doctor/queue?department=Panchakarma"),
  ]);
  const emIds = new Set(emergency.map((e) => e.session_id));
  const qIds = new Set([...kaya, ...pk].map((q) => q.session_id));
  const overlap = [...emIds].filter((id) => qIds.has(id));
  record(overlap.length === 0, "d04_api_safety_disjoint_from_d01_queue", `overlap=${overlap.length} em=${emIds.size} q=${qIds.size}`);
}

// ---- Per-breakpoint structural/layout checks ----
for (const { w, h } of VIEWPORTS) {
  const tag = `[${w}px]`;
  const { page } = await newEmergencyPage(w, h);
  await page.waitForTimeout(400);

  // 3. emergency navigation active
  const activeItems = await page.locator('.mk-sidebar__item[data-active="true"]').allTextContents();
  record(activeItems.length === 1 && /Emergency Escalations/.test(activeItems[0] || ""),
    `${tag} emergency_nav_active`, activeItems.join(" | "));
  const navLabels = await page.locator(".mk-sidebar__item").allTextContents();
  record(navLabels.length === 3 && navLabels.every((l) => /Emergency Escalations|Kayachikitsa Queue|Panchakarma Queue/.test(l)),
    `${tag} nav_only_approved_destinations`, navLabels.join(" | "));

  // 1. expected D04 elements exist
  const selectors = [
    ".mk-d04-header-card", ".mk-d04-page-title", ".mk-d04-page-desc",
    ".mk-d04-refresh", ".mk-d04-queue-section", ".mk-d04-queue-heading__text",
    ".mk-d04-alert-list", ".mk-d04-alert-card", ".mk-d04-alert-icon",
    ".mk-d04-alert-code", ".mk-d04-alert-badge", ".mk-d04-alert-symptom",
    ".mk-d04-alert-meta", ".mk-d04-alert-meta__time", ".mk-d04-ack-btn",
    ".mk-d04-warning-icon",
  ];
  const missing = [];
  for (const s of selectors) {
    if ((await page.locator(s).count()) === 0) missing.push(s);
  }
  record(missing.length === 0, `${tag} elements_exist`, missing.join(","));

  // 4. heading and supporting text present
  const title = (await page.locator(".mk-d04-page-title").textContent())?.trim() || "";
  const desc = (await page.locator(".mk-d04-page-desc").textContent())?.trim() || "";
  const heading = (await page.locator(".mk-d04-queue-heading__text").textContent())?.trim() || "";
  record(title === "Emergency Safety Escalations", `${tag} page_title`, title);
  record(desc.length >= 20 && /queue token/i.test(desc), `${tag} page_desc_present`, desc.slice(0, 60));
  record(heading === "Active Escalation Queue", `${tag} queue_heading`, heading);

  // 2. correct DOM ordering: header-card before queue-section; card children in order
  const orderOk = await page.evaluate(() => {
    const a = document.querySelector(".mk-d04-header-card");
    const b = document.querySelector(".mk-d04-queue-section");
    if (!a || !b) return false;
    const before = a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING;
    const card = document.querySelector(".mk-d04-alert-card");
    if (!card) return false;
    const icon = card.querySelector(".mk-d04-alert-icon");
    const body = card.querySelector(".mk-d04-alert-card__body");
    const action = card.querySelector(".mk-d04-alert-card__action");
    if (!icon || !body || !action) return false;
    const iconFirst = icon.compareDocumentPosition(body) & Node.DOCUMENT_POSITION_FOLLOWING;
    const bodyFirst = body.compareDocumentPosition(action) & Node.DOCUMENT_POSITION_FOLLOWING;
    const head = card.querySelector(".mk-d04-alert-card__head .mk-d04-alert-code");
    const badge = card.querySelector(".mk-d04-alert-card__head .mk-d04-alert-badge");
    const symptom = card.querySelector(".mk-d04-alert-symptom");
    const meta = card.querySelector(".mk-d04-alert-meta");
    let seq = true;
    const els = [head, badge, symptom, meta].filter(Boolean);
    for (let i = 1; i < els.length; i++) {
      const prev = els[i - 1].compareDocumentPosition(els[i]);
      if (!(prev & Node.DOCUMENT_POSITION_FOLLOWING) && !(prev & Node.DOCUMENT_POSITION_CONTAINS)) seq = false;
    }
    return before && iconFirst && bodyFirst && seq;
  });
  record(orderOk, `${tag} dom_ordering`);

  // 5. alert queue/card structure correct
  const cardCount = await page.locator(".mk-d04-alert-card").count();
  const cardStructureValid = await page.evaluate(() => {
    const cards = [...document.querySelectorAll(".mk-d04-alert-card")];
    return cards.every((c) =>
      c.querySelector(".mk-d04-alert-icon") &&
      c.querySelector(".mk-d04-alert-code")?.textContent?.trim() &&
      c.querySelector(".mk-d04-alert-badge")?.textContent?.trim() &&
      c.querySelector(".mk-d04-alert-symptom")?.textContent?.trim() &&
      c.querySelector(".mk-d04-alert-meta__time")?.textContent?.trim() &&
      c.querySelector(".mk-d04-ack-btn")
    );
  });
  record(cardCount >= 1 && cardStructureValid, `${tag} alert_card_structure`, `cards=${cardCount}`);
  const listInsideSection = await page.evaluate(() => {
    const section = document.querySelector(".mk-d04-queue-section");
    return !!section && section.contains(document.querySelector(".mk-d04-alert-list"));
  });
  record(listInsideSection, `${tag} alert_list_in_queue_section`);

  // 6. status explicit and not color-only (text present on every badge + icon)
  const statusOk = await page.evaluate(() => {
    const badges = [...document.querySelectorAll(".mk-d04-alert-badge")];
    return badges.length >= 1 && badges.every((b) => b.textContent.trim().length >= 3);
  });
  record(statusOk, `${tag} status_explicit_text`);
  const iconPresent = (await page.locator(".mk-d04-alert-card .mk-d04-alert-icon svg").count()) >= 1;
  record(iconPresent, `${tag} status_has_warning_icon`);

  // 7. touch targets >= 48px at mobile (390)
  if (w === 390) {
    const boxes = await page.locator(".mk-d04-ack-btn, .mk-d04-refresh").evaluateAll((els) =>
      els.map((el) => { const r = el.getBoundingClientRect(); return { h: r.height, w: r.width }; })
    );
    const minOk = boxes.every((b) => b.h >= 48 && b.w >= 48);
    record(minOk, `${tag} touch_targets_48px`, boxes.length ? `n=${boxes.length} ` + boxes.map((b) => `${Math.round(b.h)}x${Math.round(b.w)}`).join(" ") : "none");
  }

  // 8. no horizontal overflow
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  record(overflow <= 0, `${tag} no_horizontal_overflow`, `overflow=${overflow}px`);

  // 9. no element clipped (key D04 elements within viewport horizontally)
  const clipped = await page.evaluate((vw) => {
    const els = [...document.querySelectorAll(
      ".mk-d04-header-card, .mk-d04-page-title, .mk-d04-page-desc, .mk-d04-refresh, " +
      ".mk-d04-queue-section, .mk-d04-queue-heading, .mk-d04-alert-card, .mk-d04-ack-btn"
    )];
    const bad = [];
    for (const el of els) {
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 || r.left < -1) bad.push(el.className);
    }
    return bad;
  }, w);
  record(clipped.length === 0, `${tag} no_clipped_elements`, clipped.slice(0, 5).join(","));

  // 10. no card/action covered by another element (hit-test on elements visible in viewport)
  const covered = await page.evaluate(() => {
    const targets = [];
    const ivw = window.innerWidth;
    const ivh = window.innerHeight;
    for (const sel of [".mk-d04-ack-btn", ".mk-d04-refresh", ".mk-d04-alert-card"]) {
      for (const el of document.querySelectorAll(sel)) {
        const r = el.getBoundingClientRect();
        if (r.bottom < 0 || r.top > ivh || r.right < 0 || r.left > ivw) continue; // off-screen
        const cx = r.left + Math.min(r.width / 2, 200); // avoid far-right edge rounding
        const cy = Math.min(r.top + r.height / 2, ivh - 1);
        const top = document.elementFromPoint(cx, cy);
        if (!top) { targets.push(sel + ":no-element"); continue; }
        if (sel === ".mk-d04-ack-btn" && !top.closest(".mk-d04-ack-btn")) targets.push(sel);
        if (sel === ".mk-d04-refresh" && !top.closest(".mk-d04-refresh")) targets.push(sel);
        if (sel === ".mk-d04-alert-card" && !top.closest(".mk-d04-alert-card")) targets.push(sel);
      }
    }
    return targets;
  });
  record(covered.length === 0, `${tag} no_overlap`, covered.slice(0, 5).join(","));

  // 12. real emergency API data used (DOM codes == API codes, DOM names in API)
  const emergencyApi = await api("/doctor/emergency");
  const apiCodes = new Set(emergencyApi.map((e) => e.patient_code));
  const apiNames = new Set(emergencyApi.map((e) => e.patient_name));
  const domCodes = (await page.locator(".mk-d04-alert-code").allTextContents()).map((t) => t.trim());
  const domText = (await page.locator(".mk-main-content").textContent()) || "";
  record(domCodes.length === emergencyApi.length && domCodes.every((c) => apiCodes.has(c)),
    `${tag} real_api_data_codes`, `dom=${domCodes.length} api=${emergencyApi.length}`);
  const namesShown = [...apiNames].filter((n) => domText.includes(n));
  record(namesShown.length >= 1, `${tag} real_api_data_names`, namesShown.slice(0, 3).join(","));

  // 14. no fake statistics/diagnosis/treatment content in D04 chrome
  const chromeText = await page.evaluate(() => {
    const parts = [
      document.querySelector(".mk-d04-header-card"),
      document.querySelector(".mk-d04-queue-heading"),
    ].filter(Boolean).map((el) => el.textContent || "");
    return parts.join(" ");
  });
  const hits = MOCK.blocklist.filter((re) => re.test(chromeText));
  record(hits.length === 0, `${tag} no_fake_clinical_claim`, hits.join(","));

  await page.close();
  await page.context().close();
}

// ---- 11. empty / loading / error / ack states (1440) ----
// 11a. loading state renders while request is in flight
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => window.sessionStorage.setItem("mk_doctor_view", JSON.stringify({ kind: "emergency" })));
  const page = await ctx.newPage();
  await page.route("**/doctor/emergency", async (route) => {
    await new Promise((r) => setTimeout(r, 2500));
    await route.continue();
  });
  await page.goto(`${WEB}/doctor`, { waitUntil: "domcontentloaded" });
  const loadingSeen = await (async () => {
    try { await page.waitForSelector(".mk-d04-loading", { timeout: 2000 }); return true; } catch { return false; }
  })();
  record(loadingSeen, "loading_state_renders");
  await page.waitForSelector(".mk-d04-alert-card", { timeout: 20000 });
  await page.close(); await ctx.close();
}

// 11b. empty state renders (intercepted [])
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => window.sessionStorage.setItem("mk_doctor_view", JSON.stringify({ kind: "emergency" })));
  const page = await ctx.newPage();
  await page.route("**/doctor/emergency", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d04-empty", { timeout: 15000 });
  const emptyText = (await page.locator(".mk-d04-empty__text").textContent())?.trim() || "";
  const noCards = (await page.locator(".mk-d04-alert-card").count()) === 0;
  record(noCards && /No active safety escalations/.test(emptyText), "empty_state_renders", emptyText);
  await page.close(); await ctx.close();
}

// 11c. error state renders + retry recovers (abort then continue)
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => window.sessionStorage.setItem("mk_doctor_view", JSON.stringify({ kind: "emergency" })));
  const page = await ctx.newPage();
  let intercept = true;
  await page.route("**/doctor/emergency", (route) => (intercept ? route.abort() : route.continue()));
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d04-error", { timeout: 15000 });
  const errText = (await page.locator(".mk-d04-error__text").textContent())?.trim() || "";
  record(/Could not load safety escalations/.test(errText), "error_state_renders", errText);
  intercept = false;
  await page.click(".mk-d04-error .mk-d04-refresh");
  await page.waitForSelector(".mk-d04-alert-card", { timeout: 15000 });
  record(true, "error_retry_recovers");
  await page.close(); await ctx.close();
}

// 11d. ack is explicit text + local-only (server list unchanged, state persists across bg nav)
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => window.sessionStorage.setItem("mk_doctor_view", JSON.stringify({ kind: "emergency" })));
  const page = await ctx.newPage();
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d04-alert-card", { timeout: 20000 });
  const before = (await api("/doctor/emergency")).length;
  await page.locator(".mk-d04-ack-btn").first().click();
  await page.waitForSelector(".mk-d04-ack-btn--done", { timeout: 5000 });
  const ackText = (await page.locator(".mk-d04-ack-btn--done").textContent())?.trim() || "";
  const disabled = await page.locator(".mk-d04-ack-btn--done").isDisabled();
  const after = (await api("/doctor/emergency")).length;
  record(/Acknowledged/.test(ackText) && disabled, "ack_toggles_text_and_disables", ackText);
  record(after === before, "ack_is_local_only_server_unchanged", `${before} -> ${after}`);
  await page.close(); await ctx.close();
}

// ---- 15. D01 still loads correctly after shared CSS/workspace changes ----
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript(() => window.sessionStorage.setItem("mk_doctor_view", JSON.stringify({ kind: "queue", department: "Kayachikitsa" })));
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d01-table", { timeout: 20000 });
  const title = (await page.locator(".mk-d01-ribbon__title").textContent())?.trim() || "";
  const rows = await page.locator(".mk-d01-table tbody tr").count();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  record(title === "Kayachikitsa" && rows >= 1, "d01_loads_after_d04_changes", `title=${title} rows=${rows}`);
  record(overflow <= 0, "d01_no_overflow_after_d04_changes", `overflow=${overflow}`);
  record(errs.length === 0, "d01_no_js_errors_after_d04_changes", errs.join(";"));
  await page.close(); await ctx.close();
}

await browser.close();

const failed = RESULTS.filter((r) => !r.ok);
console.log(`\n--- D04 verify: ${RESULTS.length - failed.length}/${RESULTS.length} passed ---`);
if (failed.length) {
  console.log("FAILED:", failed.map((f) => f.name).join(" | "));
  process.exit(1);
}