// P06 state walkthrough + screenshots.
const { chromium } = require('playwright-core');
const path = require('path');
const fs = require('fs');

const BASE = 'http://localhost:3000';
const OUT = path.resolve(__dirname, '..', 'frontend', '.next', 'p06-screens');
const WIDTHS = [1440, 1024, 768, 390];
const SAMPLE_PNG = path.resolve(__dirname, '..', 'frontend', 'sample-prescription.png');

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

async function goThroughP06(page) {
  // P01 -> P04
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.mk-p01-lang-card');
  await page.locator('.mk-p01-lang-card', { hasText: 'English' }).click();
  await page.locator('.mk-p01-status-card', { hasText: 'New Patient' }).click();
  await page.click('text=Continue to Consent');
  await page.waitForSelector('input[placeholder="Enter your name"]');
  await page.fill('input[placeholder="Enter your name"]', 'P06 Test');
  await page.fill('input[placeholder="Enter your age"]', '32');
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
  // Submit one safe answer to advance from chief_complaint so P06 entry isn't blocked.
  await page.locator('.mk-p04-textarea').fill('mild seasonal cough');
  await page.click('.mk-p04-btn--primary');
  await page.waitForTimeout(800);
  // P06 (early-return page).
  await page.waitForSelector('.mk-p06-h1', { timeout: 15000 });
}

async function verifyP06Structure(page) {
  const eyebrow = await page.locator('.mk-p06-eyebrow').textContent();
  const h1 = await page.locator('.mk-p06-h1').textContent();
  const sub = await page.locator('.mk-p06-sub').textContent();
  const activeNav = await page.locator('.mk-p06-nav__pill--active').textContent();
  const doneNavCount = await page.locator('.mk-p06-nav__pill--done').count();
  const totalNav = await page.locator('.mk-p06-nav__pill').count();
  const dropzoneShown = await page.locator('.mk-p06-dropzone').count();
  const skipBtn = await page.locator('.mk-p06-btn--skip').count();
  const continueBtn = await page.locator('.mk-p06-btn--continue').count();
  const mainW = await page.locator('.mk-p06-main').evaluate(el => el.getBoundingClientRect().width);
  const cardW = await page.locator('.mk-p06-card').evaluate(el => el.getBoundingClientRect().width);
  const footerShown = await page.locator('.mk-p06-footer').count();
  const notice = await page.locator('.mk-p06-footer__notice').textContent();
  const protocol = await page.locator('.mk-p06-footer__protocol').textContent();

  console.log('eyebrow           =', JSON.stringify(eyebrow.trim()));
  console.log('h1                =', JSON.stringify(h1.trim()));
  console.log('sub               =', JSON.stringify(sub.trim()));
  console.log('active nav        =', JSON.stringify(activeNav.trim()));
  console.log('done nav count    =', doneNavCount);
  console.log('total nav pills   =', totalNav);
  console.log('dropzone (idle)   =', dropzoneShown > 0);
  console.log('skip + continue   =', skipBtn, '/', continueBtn);
  console.log('main width @1440  =', mainW);
  console.log('card width @1440  =', cardW);
  console.log('footer            =', footerShown > 0);
  console.log('footer notice     =', JSON.stringify(notice.trim()));
  console.log('footer protocol   =', JSON.stringify(protocol.replace(/\s+/g, ' ').trim()));
}

async function uploadSample(page) {
  // Trigger file picker via setInputFiles.
  const input = await page.locator('input[type="file"]');
  await input.setInputFiles(SAMPLE_PNG);
  // Stage should be "selected"
  await page.waitForSelector('.mk-p06-file-box__name', { timeout: 5000 });
  const sel = await page.locator('.mk-p06-file-box__name').textContent();
  console.log('file selected     =', JSON.stringify(sel.trim()));
  // Click upload button
  await page.locator('.mk-p06-file-box__upload').click();
  // Wait for either extracted/review or error
  await Promise.race([
    page.waitForSelector('.mk-p06-extracted__heading', { timeout: 15000 }),
    page.waitForSelector('.mk-p06-error', { timeout: 15000 }),
  ]);
  const extracted = await page.locator('.mk-p06-extracted__heading').count();
  const error = await page.locator('.mk-p06-error').count();
  if (extracted > 0) {
    const fields = await page.locator('.mk-p06-field').count();
    console.log('extracted state   = OK, fields =', fields);
    const confBadge = await page.locator('.mk-p06-badge--confidence').count();
    console.log('confidence badges =', confBadge);
    const replace = await page.locator('.mk-p06-file-box__replace').count();
    console.log('replace button    =', replace > 0);
  } else if (error > 0) {
    const msg = await page.locator('.mk-p06-error').textContent();
    console.log('OCR error         =', JSON.stringify(msg.trim()));
  }
  return extracted > 0;
}

(async () => {
  const browser = await chromium.launch({ executablePath: findBrowser(), headless: true });
  const errs = [];

  // Functional walk
  const ctx0 = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const p0 = await ctx0.newPage();
  p0.on('pageerror', e => errs.push('pageerror: ' + e.message));
  p0.on('console', m => { if (m.type() === 'error') errs.push('console.error: ' + m.text()); });
  try {
    await goThroughP06(p0);
    console.log('--- P06 structural checks (idle) ---');
    await verifyP06Structure(p0);
    console.log('--- P06 upload walk ---');
    await uploadSample(p0);
  } catch (e) {
    console.error('FUNCTIONAL ERR:', e.message);
  }
  await ctx0.close();

  // Screenshots: idle at each breakpoint
  for (const w of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 1100 } });
    const p = await ctx.newPage();
    try {
      await goThroughP06(p);
    } catch (e) {
      console.error(`[${w}] flow error:`, e.message);
    }
    await p.waitForTimeout(400);
    const file = path.join(OUT, `p06-idle-${w}.png`);
    await p.screenshot({ path: file, fullPage: true });
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    console.log(`[idle ${w}] saved ${file}  (overflow = ${overflow}px)`);
    await ctx.close();
  }

  // Screenshots: extracted
  for (const w of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 1100 } });
    const p = await ctx.newPage();
    try {
      await goThroughP06(p);
      const ok = await uploadSample(p);
      if (ok) {
        await p.waitForTimeout(400);
        const file = path.join(OUT, `p06-extracted-${w}.png`);
        await p.screenshot({ path: file, fullPage: true });
        const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        console.log(`[extracted ${w}] saved ${file}  (overflow = ${overflow}px)`);
      }
    } catch (e) {
      console.error(`[extracted ${w}] flow error:`, e.message);
    }
    await ctx.close();
  }

  // Screenshots: selected (file preview before processing)
  for (const w of [1440, 768]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 1100 } });
    const p = await ctx.newPage();
    try {
      await goThroughP06(p);
      await p.locator('input[type="file"]').setInputFiles(SAMPLE_PNG);
      await p.waitForSelector('.mk-p06-file-box__name');
      await p.waitForTimeout(300);
      const file = path.join(OUT, `p06-selected-${w}.png`);
      await p.screenshot({ path: file, fullPage: true });
      console.log(`[selected ${w}] saved ${file}`);
    } catch (e) {
      console.error(`[selected ${w}] flow error:`, e.message);
    }
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
