// D04 screenshots — emergency safety dashboard at 1440/1024/768/390. Saves to D:\tmp\d04_shots\
// Expected running: p0_server.py on 127.0.0.1:8001, `npm run dev` on :3000.
import { createRequire } from "module";
const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");
import { mkdirSync } from "fs";

const API = "http://127.0.0.1:8001";
const WEB = "http://localhost:3000";
const OUT = "D:/tmp/d04_shots";
mkdirSync(OUT, { recursive: true });

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

async function startFlagged(name) {
  const stamp = Date.now() % 1000000;
  const { session_id } = await api("/session/start", "POST", {
    patient: { name, age: 55, gender: "female" },
    language: "en",
    visit_type: "new",
  });
  await api(`/session/${session_id}/consent`, "POST", { consent_given: true });
  await api(`/session/${session_id}/patient-code`, "POST");
  // "chest tightness" / "difficulty breathing" are deterministic safety flags.
  await api(`/session/${session_id}/answer`, "POST", { answer: `chest tightness radiating to the arm ${stamp}` });
  return session_id;
}

const [sid1, sid2] = [await startFlagged("Asha Reddy"), await startFlagged("Meena Iyer")];

const browser = await chromium.launch();
async function shot(w, h, name, { ack = false } = {}) {
  const context = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  await context.addInitScript((view) => {
    window.sessionStorage.setItem("mk_doctor_view", JSON.stringify(view));
  }, { kind: "emergency" });
  const page = await context.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.type() === "error") errs.push("console.error: " + m.text()); });
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector(".mk-d04-header-card", { timeout: 20000 });
  await page.waitForSelector(".mk-d04-alert-card", { timeout: 20000 });
  await page.waitForTimeout(500);
  if (ack) {
    await page.locator(".mk-d04-ack-btn").first().click();
    await page.waitForSelector(".mk-d04-ack-btn--done", { timeout: 5000 });
    await page.waitForTimeout(300);
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  const cards = await page.locator(".mk-d04-alert-card").count();
  console.log(`saved ${name}.png (${w}x${h}) cards=${cards} overflow=${overflow}px errs=${errs.length}`);
  await page.close();
  await context.close();
}

await shot(1440, 900, "d04_1440");
await shot(1024, 900, "d04_1024");
await shot(768, 900, "d04_768");
await shot(390, 844, "d04_390");
await shot(390, 844, "d04_390_ack", { ack: true });
await browser.close();
console.log("D04 shots done (seeds:", sid1, sid2 + ")");