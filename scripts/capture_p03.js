// Drive P01 -> P03 and capture screenshots at 4 breakpoints.
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');

const BASE = 'http://localhost:3000';
const OUT = path.resolve(__dirname, '..', 'frontend', '.next', 'p03-screens');
const WIDTHS = [1440, 1024, 768, 390];

fs.mkdirSync(OUT, { recursive: true });

async function goThroughP03(page) {
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: /^English$/ }).click();
  await page.getByRole('button', { name: /^New Patient$/ }).click();
  await page.getByRole('button', { name: /^Continue to Consent$/ }).click();
  await page.waitForSelector('input[placeholder="Enter your name"]');
  await page.fill('input[placeholder="Enter your name"]', 'Screenshot User');
  await page.fill('input[placeholder="Enter your age"]', '42');
  await page.getByRole('button', { name: /^Male$/ }).click();
  await page.getByRole('button', { name: /^Start Now$/ }).click();
  await page.waitForSelector('#consent-agreement');
  await page.check('#consent-agreement');
  await page.getByRole('button', { name: /Agree & Continue/ }).click();
  await page.waitForSelector('.mk-p03-code');
  await page.waitForFunction(() => {
    const el = document.querySelector('.mk-p03-code');
    return el && el.textContent && el.textContent.trim() !== 'Generating…';
  });
}

(async () => {
  // Try to use the bundled Chromium that may already be on disk.
  const candidates = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Users/yashp/AppData/Local/ms-playwright/chromium-1193/chrome-win/chrome.exe',
    'C:/Users/yashp/AppData/Local/ms-playwright/chromium-1148/chrome-win/chrome.exe',
  ];
  let executablePath;
  for (const c of candidates) {
    if (fs.existsSync(c)) { executablePath = c; break; }
  }
  if (!executablePath) {
    // Look for any chrome.exe under the user's playwright cache
    const root = 'C:/Users/yashp/AppData/Local/ms-playwright';
    if (fs.existsSync(root)) {
      for (const d of fs.readdirSync(root)) {
        const sub = path.join(root, d, 'chrome-win', 'chrome.exe');
        if (fs.existsSync(sub)) { executablePath = sub; break; }
      }
    }
  }
  if (!executablePath) {
    console.error('No Chrome/Chromium found. Install via npx playwright install.');
    process.exit(1);
  }
  const browser = await chromium.launch({ executablePath, headless: true });
  for (const w of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 1200 } });
    const page = await ctx.newPage();
    try {
      await goThroughP03(page);
    } catch (e) {
      console.error(`[${w}] flow error:`, e.message);
    }
    await page.waitForTimeout(400);
    const file = path.join(OUT, `p03-${w}.png`);
    await page.screenshot({ path: file, fullPage: true });
    console.log(`[${w}] saved`, file);
    await ctx.close();
  }
  await browser.close();
})();
