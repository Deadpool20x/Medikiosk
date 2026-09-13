// Drive a safety-flag flow and capture P05 at 4 breakpoints.
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');

const BASE = 'http://localhost:3000';
const OUT = path.resolve(__dirname, '..', 'frontend', '.next', 'p05-screens');
const WIDTHS = [1440, 1024, 768, 390];

fs.mkdirSync(OUT, { recursive: true });

function findBrowser() {
  const candidates = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  ];
  for (const c of candidates) if (fs.existsSync(c)) return c;
  const root = 'C:/Users/yashp/AppData/Local/ms-playwright';
  if (fs.existsSync(root)) {
    for (const d of fs.readdirSync(root)) {
      const sub = path.join(root, d, 'chrome-win', 'chrome.exe');
      if (fs.existsSync(sub)) return sub;
    }
  }
  return null;
}

async function goThroughP05(page) {
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.mk-p01-lang-card');
  await page.locator('.mk-p01-lang-card', { hasText: 'English' }).click();
  await page.locator('.mk-p01-status-card', { hasText: 'New Patient' }).click();
  await page.click('text=Continue to Consent');
  await page.waitForSelector('input[placeholder="Enter your name"]');
  await page.fill('input[placeholder="Enter your name"]', 'Safety Test');
  await page.fill('input[placeholder="Enter your age"]', '45');
  await page.locator('.mk-chip', { hasText: /^Male$/ }).click();
  await page.click('text=Start Now');
  await page.waitForSelector('#consent-agreement');
  await page.check('#consent-agreement');
  await page.click('text=Agree & Continue');
  await page.waitForSelector('.mk-p03-code');
  await page.waitForFunction(() => {
    const el = document.querySelector('.mk-p03-code');
    return el && el.textContent && el.textContent.trim() !== 'Generating…';
  });
  await page.click('.mk-p03-btn--primary');
  await page.waitForSelector('.mk-p04-h1');
  await page.waitForFunction(() => {
    const el = document.querySelector('.mk-p04-h1');
    if (!el) return false;
    const t = (el.textContent || '').trim();
    return t && t !== 'Please answer the question below.';
  }, { timeout: 15000 });
  // Submit a red-flag answer.
  await page.locator('.mk-p04-textarea').fill('chest pain');
  await page.click('.mk-p04-btn--primary');
  // Wait for either safety screen or error.
  await page.waitForSelector('.mk-p05-h1', { timeout: 15000 });
}

async function verifyP05Structure(page) {
  const eyebrow = await page.locator('.mk-p05-eyebrow').textContent();
  const status = await page.locator('.mk-p05-status').textContent();
  const h1 = await page.locator('.mk-p05-h1').textContent();
  const sub = await page.locator('.mk-p05-sub').textContent();
  const infoCount = await page.locator('.mk-p05-info').count();
  const infoTitles = await page.locator('.mk-p05-info__title').allTextContents();
  const refLabel = await page.locator('.mk-p05-ref__label').textContent();
  const refValue = await page.locator('.mk-p05-ref__value').textContent();
  const refHint = await page.locator('.mk-p05-ref__hint').textContent();
  const btnText = await page.locator('.mk-p05-btn').textContent();
  const btnH = await page.locator('.mk-p05-btn').evaluate(el => el.getBoundingClientRect().height);
  const protocol = await page.locator('.mk-p05-protocol').textContent();
  const role = await page.locator('main[role="alert"]').count();
  const mainW = await page.locator('.mk-p05-main').evaluate(el => el.getBoundingClientRect().width);
  const cardW = await page.locator('.mk-p05-card').evaluate(el => el.getBoundingClientRect().width);

  console.log('eyebrow           =', JSON.stringify(eyebrow.trim()));
  console.log('status            =', JSON.stringify(status.trim()));
  console.log('h1                =', JSON.stringify(h1.trim()));
  console.log('sub               =', JSON.stringify(sub.trim()));
  console.log('info panels       =', infoCount, '| titles:', JSON.stringify(infoTitles.map(t => t.trim())));
  console.log('ref label         =', JSON.stringify(refLabel.trim()));
  console.log('ref value         =', JSON.stringify(refValue.replace(/\s+/g, ' ').trim()));
  console.log('ref hint          =', JSON.stringify(refHint.trim()));
  console.log('button            =', JSON.stringify(btnText.trim()));
  console.log('button height     =', btnH, '(>=48 required)');
  console.log('protocol footer   =', JSON.stringify(protocol.replace(/\s+/g, ' ').trim()));
  console.log('role=alert present=', role === 1);
  console.log('main width @1440  =', mainW, '(target 672)');
  console.log('card width @1440  =', cardW);

  // Try the Return to Welcome button.
  await page.click('.mk-p05-btn');
  await page.waitForSelector('input[placeholder="Enter your name"]', { timeout: 5000 });
  console.log('reset -> welcome  = OK');
}

(async () => {
  const browser = await chromium.launch({ executablePath: findBrowser(), headless: true });
  const ctx0 = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const p0 = await ctx0.newPage();
  const errs = [];
  p0.on('pageerror', e => errs.push('pageerror: ' + e.message));
  p0.on('console', m => { if (m.type() === 'error') errs.push('console.error: ' + m.text()); });

  try {
    await goThroughP05(p0);
    console.log('--- P05 structural checks ---');
    await verifyP05Structure(p0);
  } catch (e) {
    console.error('FUNCTIONAL ERR:', e.message);
  }
  await ctx0.close();

  for (const w of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 1100 } });
    const p = await ctx.newPage();
    try {
      await goThroughP05(p);
    } catch (e) {
      console.error(`[${w}] flow error:`, e.message);
    }
    await p.waitForTimeout(400);
    const file = path.join(OUT, `p05-${w}.png`);
    await p.screenshot({ path: file, fullPage: true });
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    console.log(`[${w}] saved ${file}  (overflow = ${overflow}px)`);
    await ctx.close();
  }

  if (errs.length) {
    console.log('--- console errors ---');
    errs.forEach(e => console.log(e));
  } else {
    console.log('--- no console errors ---');
  }

  await browser.close();
})();
