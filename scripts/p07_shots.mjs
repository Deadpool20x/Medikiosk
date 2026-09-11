// P07 SUMMARY REVIEW screenshots — drives the real Next.js app + mock backend.
// Expected running: p0_server.py on 127.0.0.1:8001, `npm run dev` on :3000.
// Run from the frontend directory:  node ..\scripts\p07_shots.mjs <outDir>
import { createRequire } from "module";
import { mkdirSync } from "fs";
import { join } from "path";

const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");

const OUT = process.argv[2];
const API = "http://127.0.0.1:8001";
const WEB = "http://localhost:3000";

if (!OUT) {
  console.error("usage: node p07_shots.mjs <outDir>");
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

const ANSWERS = [
  ["chief_complaint", "mild back pain"],
  ["onset", "2 weeks ago"],
  ["duration", "2 weeks"],
  ["severity", "mild"],
  ["character", "dull"],
  ["associated_symptoms", "stiffness"],
];

// Create session and navigate through full flow to summary
console.log("creating session for P07…");
const { session_id: sid } = await api("/session/start", "POST", {
  patient: { name: "Summary Patient", age: 45, gender: "male" },
  language: "en",
  visit_type: "new",
});
await api(`/session/${sid}/consent`, "POST", { consent_given: true });
await api(`/session/${sid}/patient-code`, "POST");
for (const [, ans] of ANSWERS) await api(`/session/${sid}/answer`, "POST", { answer: ans });
await api(`/session/${sid}/documents-complete`, "POST");
console.log(`  session ${sid} ready for summary`);

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

  await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
  await page.evaluate((sessionId) => {
    window.sessionStorage.setItem("medikiosk_session_id", sessionId);
  }, sid);
  await page.reload({ waitUntil: "networkidle" });

  await page.waitForSelector(".mk-p07", { timeout: 15000 });
  await page.waitForTimeout(400);

  await page.screenshot({ path: join(OUT, String(width), "p07_review.png"), fullPage: true });
  const hasOverflow = await overflow(page);
  const headerPresent = (await page.locator(".mk-p07-header").count()) > 0;
  const navPillCount = await page.locator(".mk-p07-nav__pill").count();
  const sectionCount = await page.locator(".mk-p07-section").count();
  const cardPresent = (await page.locator(".mk-p07-card").count()) > 0;

  results.push({
    width,
    file: "p07_review.png",
    hasOverflow,
    headerPresent,
    navPillCount,
    sectionCount,
    cardPresent,
    jsErrors: errors.length > 0 ? errors : undefined,
  });
  console.log(`  ${width}px  overflow=${hasOverflow}  header=${headerPresent}  navPills=${navPillCount}  sections=${sectionCount}  card=${cardPresent}  errors=${errors.length}`);
  await page.close();
}

await browser.close();
console.log("\nresults:");
for (const r of results) console.log(JSON.stringify(r));
console.log(`\nscreenshots saved to ${OUT}`);
