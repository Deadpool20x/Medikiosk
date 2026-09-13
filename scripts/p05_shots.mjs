// P05 SAFETY ESCALATION screenshots — drives the real Next.js app + mock backend.
// Expected running: p0_server.py on 127.0.0.1:8001, `npm run dev` on :3000.
// Run from the frontend directory:  node ..\scripts\p05_shots.mjs <outDir>
import { createRequire } from "module";
import { mkdirSync, writeFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");

const OUT = process.argv[2];
const API = "http://127.0.0.1:8001";
const WEB = "http://localhost:3000";

if (!OUT) {
  console.error("usage: node p05_shots.mjs <outDir>");
  process.exit(2);
}
for (const w of ["1440", "1024", "768", "390"]) mkdirSync(join(OUT, w), { recursive: true });

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

// Create a safety-flagged session via API
console.log("creating safety-flagged session…");
const { session_id: sid } = await api("/session/start", "POST", {
  patient: { name: "Flagged Patient", age: 55, gender: "male" },
  language: "en",
  visit_type: "new",
});
await api(`/session/${sid}/consent`, "POST", { consent_given: true });
const codeRes = await api(`/session/${sid}/patient-code`, "POST");
const patientCode = codeRes.patient_code;
console.log(`  session ${sid}, code ${patientCode}`);

// Submit answer with red-flag keyword to trigger safety
const ansRes = await api(`/session/${sid}/answer`, "POST", { answer: "chest pain" });
console.log(`  red_flag=${ansRes.red_flag}`);

const browser = await chromium.launch({ channel: "msedge", headless: true });
const results = [];

async function overflow(page) {
  const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  return m.sw > m.cw;
}

for (const width of [1440, 1024, 768, 390]) {
  const page = await browser.newPage({ viewport: { width, height: 844 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("Failed to load resource")) errors.push(m.text()); });

  // Restore session in browser via sessionStorage
  await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
  await page.evaluate((sessionId) => {
    window.sessionStorage.setItem("medikiosk_session_id", sessionId);
  }, sid);
  await page.reload({ waitUntil: "networkidle" });

  // Wait for P05 screen to appear
  await page.waitForSelector(".mk-p05", { timeout: 15000 });
  await page.waitForTimeout(400);

  await page.screenshot({ path: join(OUT, String(width), "p05_safety.png"), fullPage: true });
  const hasOverflow = await overflow(page);
  const headerPresent = (await page.locator(".mk-p05-header").count()) > 0;
  const eyebrowText = (await page.locator(".mk-p05-eyebrow").textContent() || "").trim();
  const h1Text = (await page.locator(".mk-p05-h1").textContent() || "").trim();
  const infoPanelCount = await page.locator(".mk-p05-info").count();
  const refPresent = (await page.locator(".mk-p05-ref").count()) > 0;
  const btnPresent = (await page.locator(".mk-p05-btn").count()) > 0;
  const footerPresent = (await page.locator(".mk-p05-footer").count()) > 0;

  results.push({
    name: `p05_safety_${width}`,
    width,
    overflow: hasOverflow,
    headerPresent,
    eyebrowText,
    h1Text,
    infoPanelCount,
    refPresent,
    btnPresent,
    footerPresent,
    errors: errors.length,
  });
  console.log(`p05_${width}: overflow=${hasOverflow} header=${headerPresent} eyebrow="${eyebrowText}" h1="${h1Text}" panels=${infoPanelCount} ref=${refPresent} btn=${btnPresent} footer=${footerPresent} errors=${errors.length}`);
  await page.close();
}

await browser.close();
writeFileSync(join(OUT, "p05_metrics.json"), JSON.stringify(results, null, 2));
const bad = results.filter((r) => r.overflow || !r.headerPresent || !r.refPresent || !r.btnPresent || !r.footerPresent || r.infoPanelCount < 2);
console.log(bad.length === 0 ? "ALL P05 SHOT CHECKS GREEN" : `FAILURES: ${JSON.stringify(bad, null, 2)}`);
console.log("metrics:", join(OUT, "p05_metrics.json"));
