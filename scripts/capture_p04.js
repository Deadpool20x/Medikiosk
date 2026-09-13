// Drive P01 -> P02 -> P03 -> P04 and capture screenshots at 4 breakpoints.
// Also runs functional checks.
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
  // P01
  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.mk-p01-lang-card');
  await page.locator('.mk-p01-lang-card', { hasText: 'English' }).click();
  await page.locator('.mk-p01-status-card', { hasText: 'New Patient' }).click();
  await page.click('text=Continue to Consent');
  // Patient welcome form
  await page.waitForSelector('input[placeholder="Enter your name"]');
  await page.fill('input[placeholder="Enter your name"]', 'Verify Patient');
  await page.fill('input[placeholder="Enter your age"]', '38');
  await page.locator('.mk-chip', { hasText: /^Male$/ }).click();
  await page.click('text=Start Now');
  // P02
  await page.waitForSelector('#consent-agreement');
  await page.check('#consent-agreement');
  await page.click('text=Agree & Continue');
  // P03
  await page.waitForSelector('.mk-p03-code');
  await page.waitForFunction(() => {
    const el = document.querySelector('.mk-p03-code');
    return el && el.textContent && el.textContent.trim() !== 'Generating…';
  });
  await page.click('.mk-p03-btn--primary');
  // P04
  await page.waitForSelector('.mk-p04-h1');
}

async function verifyP04Structure(page) {
  // Wait until the question is filled in (not the fallback text).
  await page.waitForFunction(() => {
    const el = document.querySelector('.mk-p04-h1');
    if (!el) return false;
    const t = (el.textContent || '').trim();
    return t && t !== 'Please answer the question below.';
  }, { timeout: 15000 });

  const eyebrow = await page.locator('.mk-p04-eyebrow').textContent();
  const stepChip = await page.locator('.mk-p04-step-chip').textContent();
  const question = await page.locator('.mk-p04-h1').textContent();
  const sub = await page.locator('.mk-p04-sub').textContent();
  const assistantLabel = await page.locator('.mk-p04-assistant__label').textContent();
  const assistantBody = await page.locator('.mk-p04-assistant__body').textContent();
  const fieldLabel = await page.locator('.mk-p04-field__label').textContent();
  const voiceDisabled = await page.locator('.mk-p04-voice').isDisabled();
  const activeNav = await page.locator('.mk-p04-nav__pill--active').textContent();
  const doneCount = await page.locator('.mk-p04-nav__pill--done').count();
  const dotCount = await page.locator('.mk-p04-progress__dot').count();
  const activeDot = await page.locator('.mk-p04-progress__dot--active').count();
  const doneDot = await page.locator('.mk-p04-progress__dot--done').count();

  console.log('eyebrow            =', JSON.stringify(eyebrow.trim()));
  console.log('step chip          =', JSON.stringify(stepChip.trim()));
  console.log('question           =', JSON.stringify(question.trim()));
  console.log('sub text           =', JSON.stringify(sub.trim()));
  console.log('assistant label    =', JSON.stringify(assistantLabel.trim()));
  console.log('assistant body     =', JSON.stringify(assistantBody.trim().slice(0, 80)));
  console.log('field label        =', JSON.stringify(fieldLabel.trim()));
  console.log('voice disabled     =', voiceDisabled);
  console.log('active nav pill    =', JSON.stringify(activeNav.trim()));
  console.log('done nav count     =', doneCount);
  console.log('progress dots      =', dotCount, '(active:', activeDot, 'done:', doneDot, ')');

  // Test: empty answer cannot advance (button disabled).
  const btn = page.locator('.mk-p04-btn--primary');
  await page.locator('.mk-p04-textarea').fill('');
  const disabledEmpty = await btn.isDisabled();
  console.log('empty submit disabled =', disabledEmpty);

  // Test: type an answer and submit.
  await page.locator('.mk-p04-textarea').fill('Sharp abdominal pain for three days');
  const enabled = await btn.isEnabled();
  console.log('with-text submit enabled =', enabled);

  // Test: previous step button.
  const backDisabled = await page.locator('.mk-p04-btn--back').isDisabled();
  console.log('back button not disabled =', !backDisabled);

  // Submit and verify next question appears.
  await btn.click();
  // Loading state should appear briefly; then next question comes in.
  await page.waitForFunction(() => {
    const el = document.querySelector('.mk-p04-h1');
    if (!el) return false;
    const t = (el.textContent || '').trim();
    return t && t !== 'Sharp abdominal pain for three days';
  }, { timeout: 15000 });
  const q2 = await page.locator('.mk-p04-h1').textContent();
  console.log('next question      =', JSON.stringify(q2.trim()));
  // First answer should now be cleared.
  const ta = await page.locator('.mk-p04-textarea').inputValue();
  console.log('textarea cleared after submit =', ta === '');

  // Verify progress: one done, one active.
  const ddone = await page.locator('.mk-p04-progress__dot--done').count();
  const dactive = await page.locator('.mk-p04-progress__dot--active').count();
  console.log('progress after submit: done=', ddone, 'active=', dactive);
}

(async () => {
  const browser = await chromium.launch({ executablePath: findBrowser(), headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message));
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push('console.error: ' + msg.text());
  });

  try {
    await goThroughP04(page);
    console.log('--- P04 functional checks ---');
    await verifyP04Structure(page);
  } catch (e) {
    console.error('FLOW ERROR:', e.message);
  }

  // Capture screenshots at the four breakpoints.
  for (const w of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 1300 } });
    const p = await ctx.newPage();
    try {
      await goThroughP04(p);
    } catch (e) {
      console.error(`[${w}] flow error:`, e.message);
    }
    await p.waitForTimeout(400);
    const file = path.join(OUT, `p04-${w}.png`);
    await p.screenshot({ path: file, fullPage: true });
    console.log(`[${w}] saved`, file);
    await ctx.close();
  }

  if (consoleErrors.length) {
    console.log('--- console errors ---');
    consoleErrors.forEach((e) => console.log(e));
  } else {
    console.log('--- no console errors ---');
  }

  await browser.close();
})();
