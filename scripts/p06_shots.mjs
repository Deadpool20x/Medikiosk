// P06 DOCUMENT UPLOAD screenshots — drives the real Next.js app + mock backend.
// Expected running: p0_server.py on 127.0.0.1:8001, `npm run dev` on :3000.
// Run from the frontend directory:  node ..\scripts\p06_shots.mjs <outDir>
import { createRequire } from "module";
import { mkdirSync, writeFileSync } from "fs";
import { join } from "path";
import { fileURLToPath } from "url";

const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");

const OUT = process.argv[2];
const API = "http://127.0.0.1:8001";
const WEB = "http://localhost:3000";

if (!OUT) {
  console.error("usage: node p06_shots.mjs <outDir>");
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

// Create session and navigate through flow to documents step
console.log("creating session for P06…");
const { session_id: sid } = await api("/session/start", "POST", {
  patient: { name: "Doc Patient", age: 45, gender: "male" },
  language: "en",
  visit_type: "new",
});
await api(`/session/${sid}/consent`, "POST", { consent_given: true });
await api(`/session/${sid}/patient-code`, "POST");
for (const [, ans] of ANSWERS) await api(`/session/${sid}/answer`, "POST", { answer: ans });
console.log(`  session ${sid} ready for documents`);

const browser = await chromium.launch({ channel: "msedge", headless: true });
const results = [];

async function overflow(page) {
  const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  return m.sw > m.cw;
}

// --- P06 IDLE state at all breakpoints ---
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

  await page.waitForSelector(".mk-p06", { timeout: 15000 });
  await page.waitForTimeout(400);

  await page.screenshot({ path: join(OUT, String(width), "p06_idle.png"), fullPage: true });
  const hasOverflow = await overflow(page);
  const headerPresent = (await page.locator(".mk-p06-header").count()) > 0;
  const navPillCount = await page.locator(".mk-p06-nav__pill").count();
  const eyebrowText = (await page.locator(".mk-p06-eyebrow").textContent() || "").trim();
  const h1Text = (await page.locator(".mk-p06-h1").textContent() || "").trim();
  const dropzonePresent = (await page.locator(".mk-p06-dropzone").count()) > 0;
  const footerPresent = (await page.locator(".mk-p06-footer").count()) > 0;

  results.push({
    name: `p06_idle_${width}`,
    width,
    overflow: hasOverflow,
    headerPresent,
    navPillCount,
    eyebrowText,
    h1Text,
    dropzonePresent,
    footerPresent,
    errors: errors.length,
  });
  console.log(`p06_idle_${width}: overflow=${hasOverflow} header=${headerPresent} navPills=${navPillCount} eyebrow="${eyebrowText}" dropzone=${dropzonePresent} footer=${footerPresent} errors=${errors.length}`);
  await page.close();
}

// --- P06 EXTRACTED state (upload a file) ---
{
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

  await page.goto(`${WEB}/patient`, { waitUntil: "networkidle" });
  await page.evaluate((sessionId) => {
    window.sessionStorage.setItem("medikiosk_session_id", sessionId);
  }, sid);
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForSelector(".mk-p06", { timeout: 15000 });

  // Create a minimal valid PNG file (1x1 pixel)
  const pngHeader = Buffer.from([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, // PNG signature
    0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52, // IHDR chunk
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
    0xde, 0x00, 0x00, 0x00, 0x0c, 0x49, 0x44, 0x41, // IDAT chunk
    0x54, 0x08, 0xd7, 0x63, 0xf8, 0xcf, 0xc0, 0x00,
    0x00, 0x00, 0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc,
    0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, // IEND chunk
    0x44, 0xae, 0x42, 0x60, 0x82,
  ]);
  const fs = await import("fs");
  const tmpFile = join(OUT, "test_upload.png");
  fs.writeFileSync(tmpFile, pngHeader);

  // Upload via file input
  const fileInput = page.locator("input[type='file']");
  await fileInput.setInputFiles(tmpFile);
  console.log("  file set on input");

  // Wait for the selected state (file preview) then click Upload
  await page.waitForSelector(".mk-p06-file-box__upload", { timeout: 10000 });
  await page.click(".mk-p06-file-box__upload");
  console.log("  upload button clicked");

  // Wait for processing then extracted or review
  try {
    await page.waitForSelector(".mk-p06-extracted, .mk-p06-review-alert", { timeout: 20000 });
    await page.waitForTimeout(500);
    console.log("  extracted state reached");
  } catch (e) {
    // Check what state we're in
    const stage = await page.evaluate(() => {
      const el = document.querySelector(".mk-p06-card");
      return el ? el.innerHTML.slice(0, 300) : "no card";
    });
    console.log("  state after upload:", stage.slice(0, 200));
  }

  await page.screenshot({ path: join(OUT, "1440", "p06_extracted.png"), fullPage: true });
  const hasOverflow = await overflow(page);
  const fieldCount = await page.locator(".mk-p06-field").count();
  const disclaimerPresent = (await page.locator(".mk-p06-disclaimer").count()) > 0;

  results.push({
    name: "p06_extracted_1440",
    width: 1440,
    overflow: hasOverflow,
    fieldCount,
    disclaimerPresent,
    errors: errors.length,
  });
  console.log(`p06_extracted_1440: overflow=${hasOverflow} fields=${fieldCount} disclaimer=${disclaimerPresent} errors=${errors.length}`);

  fs.unlinkSync(tmpFile);
  await page.close();
}

await browser.close();
writeFileSync(join(OUT, "p06_metrics.json"), JSON.stringify(results, null, 2));
const bad = results.filter((r) => r.overflow || (r.headerPresent === false) || (r.footerPresent === false));
console.log(bad.length === 0 ? "ALL P06 SHOT CHECKS GREEN" : `FAILURES: ${JSON.stringify(bad, null, 2)}`);
console.log("metrics:", join(OUT, "p06_metrics.json"));
