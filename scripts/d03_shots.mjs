// D03 screenshots — review/edit screen at 1440/1024/768/390. Saves to D:\tmp\d03_shots\
// Expected running: p0_server.py on 127.0.0.1:8001, `npm run dev` on :3000.
import { createRequire } from "module";
const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("playwright-core");
import { mkdirSync } from "fs";
import { readFileSync } from "fs";

const API = "http://127.0.0.1:8001";
const WEB = "http://localhost:3000";
const OUT = "D:/tmp/d03_shots";
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

const stamp = Date.now() % 100000;
const { session_id, token } = await api("/session/start", "POST", {
  patient: { name: `Shot Review ${stamp}`, age: 46, gender: "female" },
  language: "en",
  visit_type: "new",
});
await api(`/session/${session_id}/consent`, "POST", { consent_given: true });
await api(`/session/${session_id}/patient-code`, "POST");
for (const a of ["lower back stiffness and knee pain", "6 months ago", "6 months", "moderate", "dull", "morning stiffness"]) {
  await api(`/session/${session_id}/answer`, "POST", { answer: a });
}
const buf = readFileSync("D:/project/Medikishok/frontend/sample-prescription.png");
const form = new FormData();
form.append("file", new Blob([buf], { type: "image/png" }), "sample-prescription.png");
await fetch(`${API}/session/${session_id}/upload`, { method: "POST", body: form });
await api(`/session/${session_id}/documents-complete`, "POST");
await api(`/session/${session_id}/token`, "POST");

const browser = await chromium.launch();
async function shot(w, h, name) {
  const context = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  await context.addInitScript((view) => {
    window.sessionStorage.setItem("mk_doctor_view", JSON.stringify(view));
  }, { kind: "review", sessionId: session_id, department: "Kayachikitsa" });
  const page = await context.newPage();
  await page.goto(`${WEB}/doctor`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-purpose='d03-review']", { timeout: 20000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  await page.close();
  await context.close();
  console.log(`saved ${name}.png (${w}x${h})`);
}

await shot(1440, 900, "d03_review_1440");
await shot(1024, 900, "d03_review_1024");
await shot(768, 900, "d03_review_768");
await shot(390, 844, "d03_review_390");
await browser.close();
console.log("D03 shots done");