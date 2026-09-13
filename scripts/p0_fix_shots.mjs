// P0 FIX PASS screenshots (F3, F1, F5, P01) — drives the real Next.js app + mock backend.
// Expected running: p0_server.py on 127.0.0.1:8001, `npm run dev` on :3000.
// Run from the frontend directory:  node ..\scripts\p0_fix_shots.mjs <dbPath> <outDir>
import { createRequire } from "module";
import { execFileSync } from "child_process";
import { mkdirSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");

const here = dirname(fileURLToPath(import.meta.url));
const VENV_PY = join(process.cwd(), "..", "backend", ".venv", "Scripts", "python.exe");
const DB = process.argv[2];
const OUT = process.argv[3];
const API = "http://127.0.0.1:8001";
const WEB = "http://localhost:3000";

if (!DB || !OUT) {
  console.error("usage: node p0_fix_shots.mjs <dbPath> <outDir>");
  process.exit(2);
}
mkdirSync(join(OUT, "1440"), { recursive: true });
mkdirSync(join(OUT, "1024"), { recursive: true });
mkdirSync(join(OUT, "768"), { recursive: true });
mkdirSync(join(OUT, "390"), { recursive: true });

async function api(path, method = "GET", body) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}: ${text.slice(0, 160)}`);
  return text ? JSON.parse(text) : {};
}

const ANSWERS = [
  ["chief_complaint", "katishoola"],
  ["onset", "1 week ago"],
  ["duration", "1 week"],
  ["severity", "moderate"],
  ["character", "dull"],
  ["associated_symptoms", "stiffness"],
];

console.log("seeding doctor-queue patient…");
const { session_id: queueSid } = await api("/session/start", "POST", {
  patient: { name: "Sara Verma", age: 41, gender: "female" }, language: "en", visit_type: "new",
});
await api(`/session/${queueSid}/consent`, "POST", { consent_given: true });
await api(`/session/${queueSid}/patient-code`, "POST");
for (const [, ans] of ANSWERS) await api(`/session/${queueSid}/answer`, "POST", { answer: ans });
await api(`/session/${queueSid}/documents-complete`, "POST");
await api(`/session/${queueSid}/token`, "POST");
console.log("flagging an interview answer…");
execFileSync(VENV_PY, [join(here, "p0_flag_answers.py"), DB, queueSid]);

const browser = await chromium.launch({ channel: "msedge", headless: true });
const results = [];

async function newPage(width, height, mobile = false) {
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("Failed to load resource")) errors.push(m.text()); });
  page.agentErrors = errors;
  await page.goto(WEB, { waitUntil: "load" });
  if (mobile) {
    await page.context().clearCookies();
    await page.goto(WEB, { waitUntil: "load" });
  }
  return page;
}

async function overflow(page) {
  const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  return m.sw > m.cw;
}

// ---- P02 patient-consent screen (checked state, as in the master) ----
for (const width of [1440, 1024, 768, 390]) {
  const page = await newPage(width, 844);
  await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=Start Now", { timeout: 20000 });
  await page.fill("input[placeholder='Enter your name']", "Ravi Kumar");
  await page.fill("input[placeholder='Enter your age']", "41");
  await page.click("button.mk-chip:has-text('Male')");
  await page.click("button:has-text('Start Now')");
  await page.waitForSelector(".mk-p02", { timeout: 15000 });
  await page.check(".mk-p02-agree__check");
  await page.waitForTimeout(200);
  await page.screenshot({ path: join(OUT, String(width), "p02_consent.png"), fullPage: true });
  results.push({ name: `p02_consent_${width}`, width, overflow: await overflow(page) });
  console.log(`p02_${width} ok`);
  await page.close();
}

// ---- P03 patient-code screen via the real UI flow (F3) ----
for (const width of [1440, 390]) {
  const page = await newPage(width, 844);
  await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=Start Now", { timeout: 20000 });
  await page.fill("input[placeholder='Enter your name']", "Ravi Kumar");
  await page.fill("input[placeholder='Enter your age']", "41");
  await page.click("button.mk-chip:has-text('Male')");
  await page.click("button:has-text('Start Now')");
  await page.waitForSelector(".mk-p02", { timeout: 15000 });
  await page.check(".mk-p02-agree__check");
  await page.click("button:has-text('Agree & Continue')");
  await page.waitForSelector("text=Your Patient Code", { timeout: 20000 });
  await page.waitForSelector(".mk-token-number", { timeout: 10000 });
  const codeBefore = (await page.locator(".mk-token-number").innerText()).trim();
  await page.screenshot({ path: join(OUT, String(width), "p03_code.png"), fullPage: true });
  results.push({ name: `p03_code_${width}`, width, overflow: await overflow(page) });

  // refresh must show the SAME code (F3: never regenerate)
  await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=Your Patient Code", { timeout: 20000 });
  await page.waitForFunction(() => {
    const el = document.querySelector('.mk-token-number');
    return el && el.textContent && !el.textContent.includes('Generating');
  }, { timeout: 10000 });
  const codeAfter = (await page.locator(".mk-token-number").innerText()).trim();
  results.push({ name: `p03_refresh_same_code_${width}`, width, sameCode: codeBefore === codeAfter });
  console.log(`p03_${width}: code '${codeBefore}' same after refresh=${codeBefore === codeAfter}`);

  // screenshot again post-refresh to show P03 persists on reload
  await page.screenshot({ path: join(OUT, String(width), "p03_code_refresh.png"), fullPage: true });
  results.push({ name: `p03_code_refresh_${width}`, width, overflow: await overflow(page) });

  if (width === 390) {
    await page.click("button:has-text('Continue to Interview')");
    await page.waitForSelector(".mk-p04", { timeout: 15000 });
    await page.waitForTimeout(700);
    await page.screenshot({ path: join(OUT, "390", "p04_interview.png"), fullPage: true });
    results.push({ name: "p04_interview_390", width, overflow: await overflow(page) });
    console.log("p04_390 ok");
  }
  await page.close();
}

// ---- P04 patient-interview screen at all breakpoints ----
for (const width of [1440, 1024, 768]) {
  const page = await newPage(width, 844);
  await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
  await page.waitForSelector("text=Start Now", { timeout: 20000 });
  await page.fill("input[placeholder='Enter your name']", "Ravi Kumar");
  await page.fill("input[placeholder='Enter your age']", "41");
  await page.click("button.mk-chip:has-text('Male')");
  await page.click("button:has-text('Start Now')");
  await page.waitForSelector(".mk-p02", { timeout: 15000 });
  await page.check(".mk-p02-agree__check");
  await page.click("button:has-text('Agree & Continue')");
  await page.waitForSelector(".mk-token-number", { timeout: 15000 });
  await page.waitForFunction(() => {
    const el = document.querySelector('.mk-token-number');
    return el && el.textContent && !el.textContent.includes('Generating');
  }, { timeout: 10000 });
  await page.click("button:has-text('Continue to Interview')");
  await page.waitForSelector(".mk-p04", { timeout: 15000 });
  await page.waitForTimeout(700);
  await page.screenshot({ path: join(OUT, String(width), "p04_interview.png"), fullPage: true });
  results.push({ name: `p04_interview_${width}`, width, overflow: await overflow(page) });
  console.log(`p04_${width} ok`);
  await page.close();
}

// ---- Doctor workspace at 390px: compact nav reaches every department (F1) ----
{
  const page = await newPage(390, 844);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(OUT, "390", "d01_workspace_mobile.png"), fullPage: true });
  results.push({ name: "d01_workspace_mobile", width: 390, overflow: await overflow(page) });

  await page.click("button:has-text('Kayachikitsa Queue')");
  await page.waitForSelector("text=Kayachikitsa Department Queue", { timeout: 15000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: join(OUT, "390", "d01_queue_mobile.png"), fullPage: true });
  results.push({ name: "d01_queue_mobile", width: 390, overflow: await overflow(page) });

  await page.click("button:has-text('Open Case')");
  await page.waitForSelector("text=Patient Case", { timeout: 15000 });
  await page.waitForTimeout(600);
  await page.screenshot({ path: join(OUT, "390", "d02_case_mobile.png"), fullPage: true });
  results.push({ name: "d02_case_mobile", width: 390, overflow: await overflow(page) });
  const flagged = (await page.locator("text=Answers Flagged for Review").count()) > 0;
  results.push({ name: "d02_flagged_card_mobile", width: 390, present: flagged });
  console.log(`d02 mobile ok flaggedCard=${flagged} errors=${page.agentErrors.length}`);
  await page.close();
}

// ---- Doctor case at 1440px (F5 desktop parity, wheelchair nav unchanged) ----
{
  const page = await newPage(1440, 950);
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector("button:has-text('Kayachikitsa Queue')", { timeout: 20000 });
  await page.click("button:has-text('Kayachikitsa Queue')");
  await page.waitForSelector("button:has-text('Open Case')", { timeout: 15000 });
  await page.click("button:has-text('Open Case')");
  await page.waitForSelector("text=Patient Case", { timeout: 15000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: join(OUT, "1440", "d02_case_desktop.png"), fullPage: true });
  results.push({ name: "d02_case_desktop", width: 1440, overflow: await overflow(page) });
  const flagged = (await page.locator("text=Answers Flagged for Review").count()) > 0;
  results.push({ name: "d02_flagged_card_desktop", width: 1440, present: flagged });
  console.log(`d02 desktop ok flaggedCard=${flagged} errors=${page.agentErrors.length}`);
  await page.close();
}

// ---- P01 welcome/language screen at multiple breakpoints ----
for (const width of [1440, 1024, 768, 390]) {
  const page = await newPage(width, 900);
  await page.goto(WEB, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  const p01Name = width === 1440 ? "p01_welcome_1440" : width === 1024 ? "p01_welcome_1024" : width === 768 ? "p01_welcome_768" : "p01_welcome_390";
  await page.screenshot({ path: join(OUT, String(width), `${p01Name}.png`), fullPage: true });
  results.push({ name: p01Name, width, overflow: await overflow(page) });
  console.log(`${p01Name} ok`);
  await page.close();
}

await browser.close();
writeFileSync(join(OUT, "fix_metrics.json"), JSON.stringify(results, null, 2));
const bad = results.filter((r) => (r.overflow === true) || (r.sameCode === false) || (r.present === false));
console.log(bad.length === 0 ? "ALL SHOT CHECKS GREEN" : `FAILURES: ${JSON.stringify(bad, null, 2)}`);
console.log("metrics:", join(OUT, "fix_metrics.json"));