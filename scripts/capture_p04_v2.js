// Capture P04 at 4 breakpoints, plus functional checks.
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');

const BASE = 'http://localhost:3000';
const OUT = path.resolve(__dirname, '..', 'frontend', '.next', 'p04-screens');
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

async function goThroughP04(page) {
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.mk-p01-lang-card');
  await page.locator('.mk-p01-lang-card', { hasText: 'English' }).click();
  await page.locator('.mk-p01-status-card', { hasText: 'New Patient' }).click();
  await page.click('text=Continue to Consent');
  await page.waitForSelector('input[placeholder="Enter your name"]');
  await page.fill('input[placeholder="Enter your name"]', 'Verify Patient');
  await page.fill('input[placeholder="Enter your age"]', '38');
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
}

(async () => {
  const browser = await chromium.launch({ executablePath: findBrowser(), headless: true });
  // Functional check
  const ctx0 = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const p0 = await ctx0.newPage();
  try {
    await goThroughP04(p0);
    const headerH = await p0.locator('.mk-p04-header').evaluate(el => el.getBoundingClientRect().height);
    const mainW = await p0.locator('.mk-p04-main').evaluate(el => el.getBoundingClientRect().width);
    const cardW = await p0.locator('.mk-p04-card').evaluate(el => el.getBoundingClientRect().width);
    const brandCount = await p0.locator('.mk-p04-brand').count();
    const navPills = await p0.locator('.mk-p04-nav__pill').count();
    const fieldLabel = await p0.locator('.mk-p04-field__label > span').first().textContent();
    const emptyDisabled = await p0.locator('.mk-p04-textarea').inputValue().then(v => v === '');
    const voiceDisabled = await p0.locator('.mk-p04-voice').isDisabled();
    const voiceText = await p0.locator('.mk-p04-voice').textContent();
    console.log('header height        =', headerH);
    console.log('main width @1440     =', mainW, '(target ~672)');
    console.log('card width @1440     =', cardW);
    console.log('brand blocks count   =', brandCount);
    console.log('nav pills count      =', navPills);
    console.log('field label          =', JSON.stringify(fieldLabel.trim()));
    console.log('textarea empty at first =', emptyDisabled);
    console.log('voice button text    =', JSON.stringify(voiceText.trim()));
    console.log('voice disabled       =', voiceDisabled);
    const bb = await p0.evaluate(() => {
      const headerEl = document.querySelector('.mk-p04-header');
      const mainEl = document.querySelector('.mk-p04-main');
      const cardEl = document.querySelector('.mk-p04-card');
      const discEl = document.querySelector('.mk-p04-disclaimer');
      const footerEl = document.querySelector('.mk-p04-footer');
      const insideHeader = !!headerEl;
      const insideCard = !!mainEl && mainEl.contains(cardEl);
      const outsideMain = mainEl && discEl && !mainEl.contains(discEl);
      const footerOutside = footerEl && mainEl && !mainEl.contains(footerEl);
      return { insideHeader, insideCard, outsideMain, footerOutside };
    });
    console.log('structure check      =', JSON.stringify(bb));
  } catch (e) {
    console.error('FUNCTIONAL ERR:', e.message);
  }
  await ctx0.close();

  // Screenshots
  for (const w of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 1100 } });
    const p = await ctx.newPage();
    try {
      await goThroughP04(p);
    } catch (e) {
      console.error(`[${w}] flow error:`, e.message);
    }
    await p.waitForTimeout(400);
    const file = path.join(OUT, `p04-${w}.png`);
    await p.screenshot({ path: file, fullPage: true });
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    console.log(`[${w}] saved ${file}  (horizontal overflow = ${overflow}px)`);
    await ctx.close();
  }
  await browser.close();
})();
