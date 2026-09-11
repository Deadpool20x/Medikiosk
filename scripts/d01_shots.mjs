// D01 DOCTOR DEPARTMENT QUEUE screenshots — 1440 / 1024 / 768 / 390.
// Usage: node scripts/d01_shots.mjs <outDir>  (default: D:\tmp\d01_shots)
// Expected running: p0_server.py on 127.0.0.1:8001, `npm run dev` on :3000.
import { createRequire } from "module";
const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");
import { join } from "path";

const API = "http://127.0.0.1:8001";
const WEB = "http://localhost:3000";
const OUT = process.argv[2] || "D:\\tmp\\d01_shots";

const fs = await import("fs");
fs.mkdirSync(OUT, { recursive: true });

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
  return api(`/session/${session_id}/token`, "POST");
}

await seedPatient("Ravi Kumar", 42, "male", ["back pain", "2w", "2w", "mild", "dull", "stiffness"]);
await seedPatient("Meena Devi", 38, "female", ["neck pain", "1w", "1w", "moderate", "aching", "headache"]);
await seedPatient("Arjun Nair", 45, "male", ["knee pain", "3w", "3w", "mild", "dull", "stiffness"]);
await seedPatient("Lakshmi Rao", 50, "female", ["Sthaulya", "1 week ago", "1 week", "moderate", "dull", "bloating"]);
console.log("seeded 3 Kayachikitsa + 1 Panchakarma queue patients");

const browser = await chromium.launch({ channel: "msedge", headless: true });
const results = [];

async function shot(page, name, width, dir) {
  await page.waitForTimeout(450);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  const p = join(OUT, dir, `${name}.png`);
  fs.mkdirSync(join(OUT, dir), { recursive: true });
  await page.screenshot({ path: p, fullPage: true });
  results.push({ name, width, overflow });
  console.log(`shot ${name} overflow=${overflow}`);
}

for (const width of [1440, 1024, 768, 390]) {
  const page = await browser.newPage({ viewport: { width, height: width === 390 ? 844 : 900 } });
  page.on("pageerror", (e) => console.log(`pageerror ${width}: ${e}`));
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });
  await page.click("button:has-text('Kayachikitsa Queue')");
  await page.waitForSelector(".mk-d01-table", { timeout: 15000 });
  await shot(page, "d01_kayachikitsa", width, String(width));
  await page.close();
}

// Panchakarma + Emergency at 1440 (same component, different config)
{
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-sidebar__nav", { timeout: 20000 });
  await page.click("button:has-text('Panchakarma Queue')");
  await page.waitForSelector(".mk-d01-table", { timeout: 15000 });
  await shot(page, "d01_panchakarma", 1440, "1440");
  await page.click("button:has-text('Emergency Escalations')");
  await page.waitForSelector(".mk-escalation-list", { timeout: 15000 });
  await shot(page, "d01_emergency", 1440, "1440");
  await page.close();
}

await browser.close();
console.log(JSON.stringify(results, null, 2));