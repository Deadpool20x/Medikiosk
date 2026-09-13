/**
 * MediKiosk — Visual QA Screenshot Capture Script
 * Captures all 13 screens (P01..P09, D01..D04) in Desktop (1280x800) and Mobile (375x812) viewports.
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const OUT_DIR = path.resolve(__dirname, '..', 'test-artifacts', 'visual_qa');
fs.mkdirSync(OUT_DIR, { recursive: true });

async function captureScreen(page, screenId, filename) {
  const filePath = path.join(OUT_DIR, filename);
  await page.screenshot({ path: filePath, fullPage: true });
  console.log(`Captured ${screenId}: ${filename}`);
}

async function runCapture() {
  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true
  });

  console.log('Starting Visual QA Capture across Desktop and Mobile...');

  // =========================================================================
  // 1. DESKTOP CAPTURE (1280x800)
  // =========================================================================
  const desktopContext = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  });
  const page = await desktopContext.newPage();

  // P01: Welcome
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);
  await captureScreen(page, 'P01', 'P01_desktop.png');

  // Move to /patient
  await page.locator('button.mk-p01-cta').click();
  await page.waitForURL('**/patient', { timeout: 10000 });

  // Fill initial patient form
  await page.locator('input[placeholder="Enter your name"]').fill('Rajesh Sharma');
  await page.locator('input[placeholder="Enter your age"]').fill('38');
  await page.locator('button:has-text("Start Now")').click();

  // P02: Consent
  await page.waitForSelector('.mk-p02', { timeout: 15000 });
  await captureScreen(page, 'P02', 'P02_desktop.png');

  // Consent Agree -> P03
  await page.locator('#consent-agreement').check();
  await page.locator('button:has-text("Agree & Continue")').click();

  // P03: Patient Code
  await page.waitForSelector('.mk-p03-main', { timeout: 15000 });
  await captureScreen(page, 'P03', 'P03_desktop.png');

  // Move to P04 (Interview)
  const enterInterviewBtn = page.locator('button.mk-p03-btn--primary');
  await enterInterviewBtn.click();
  await page.waitForSelector('.mk-p04-main', { timeout: 15000 });
  await captureScreen(page, 'P04', 'P04_desktop.png');

  // P05 (Safety Escalation): submit a red-flag answer
  const answerInput = page.locator('#mk-p04-input');
  await answerInput.fill('Severe chest pain and difficulty breathing');
  await page.locator('button:has-text("Next Question")').click();
  await page.waitForSelector('.mk-p05-main', { timeout: 15000 });
  await captureScreen(page, 'P05', 'P05_desktop.png');

  // Now setup a fresh normal session for P06, P07, P08, P09
  await page.evaluate(() => window.sessionStorage.clear());
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await page.locator('button.mk-p01-cta').click();
  await page.waitForURL('**/patient', { timeout: 10000 });
  await page.locator('input[placeholder="Enter your name"]').fill('Arjun Sharma');
  await page.locator('input[placeholder="Enter your age"]').fill('34');
  await page.locator('button:has-text("Start Now")').click();

  await page.waitForSelector('.mk-p02', { timeout: 15000 });
  await page.locator('#consent-agreement').check();
  await page.locator('button:has-text("Agree & Continue")').click();
  await page.waitForSelector('.mk-p03-main', { timeout: 15000 });
  await page.locator('button.mk-p03-btn--primary').click();
  await page.waitForSelector('.mk-p04-main', { timeout: 15000 });

  // Complete interview safely
  const answers = [
    'I have persistent mild stomach ache for two days',
    'Two days ago after lunch',
    'Constant for two days',
    'Moderate 4 out of 10',
    'Dull aching sensation',
    'Occasional mild bloating'
  ];
  for (let i = 0; i < answers.length; i++) {
    await page.waitForSelector('#mk-p04-input', { timeout: 15000 });
    await page.locator('#mk-p04-input').fill(answers[i]);
    await page.locator('button:has-text("Next Question")').click();
    if (i < answers.length - 1) {
      await page.waitForFunction(() => {
        const inp = document.querySelector('#mk-p04-input');
        return inp && inp.value === '';
      }, { timeout: 20000 });
    }
  }

  // P06: Document Upload / OCR
  await page.waitForSelector('.mk-p06', { timeout: 15000 });
  await captureScreen(page, 'P06', 'P06_desktop.png');

  // Skip / complete document step -> P07
  await page.locator('button.mk-p06-btn--skip').click();
  await page.waitForSelector('.mk-p07', { timeout: 15000 });
  await captureScreen(page, 'P07', 'P07_desktop.png');

  // Confirm & Generate Token -> P08
  await page.locator('button:has-text("Confirm & Generate Token")').click();
  await page.waitForSelector('.mk-p08-main', { timeout: 15000 });
  await captureScreen(page, 'P08', 'P08_desktop.png');

  // Done / View Waiting Screen -> P09
  await page.locator('button:has-text("Done / View Waiting Screen")').click();
  await page.waitForSelector('.mk-p09-main', { timeout: 15000 });
  await captureScreen(page, 'P09', 'P09_desktop.png');

  // =========================================================================
  // DOCTOR WORKSPACE (DESKTOP)
  // =========================================================================
  // D01: Department Queue
  await page.goto('http://localhost:3000/doctor', { waitUntil: 'networkidle' });
  await page.locator('.mk-sidebar__item').filter({ hasText: 'Kayachikitsa Queue' }).click();
  await page.waitForSelector('.mk-d01-row', { timeout: 10000 });
  await captureScreen(page, 'D01', 'D01_desktop.png');

  // D02: Patient Case Detail
  await page.locator('.mk-d01-row').first().locator('button.mk-d01-open').click();
  await page.waitForSelector('.mk-d02-head', { timeout: 10000 });
  await captureScreen(page, 'D02', 'D02_desktop.png');

  // D03: Doctor Review & Edit
  await page.locator('button:has-text("Review & Edit Case Details →")').click();
  await page.waitForSelector('.mk-d03-os', { timeout: 10000 });
  await captureScreen(page, 'D03', 'D03_desktop.png');

  // D04: Emergency Dashboard
  await page.locator('header.mk-d03-os button:has-text("Queue")').click();
  await page.locator('.mk-sidebar__item').filter({ hasText: 'Emergency Escalations' }).click();
  await page.waitForSelector('.mk-d04-header-card', { timeout: 10000 });
  await captureScreen(page, 'D04', 'D04_desktop.png');

  await desktopContext.close();

  // =========================================================================
  // 2. MOBILE CAPTURE (375x812 - iPhone 12/13/14 scale)
  // =========================================================================
  const mobileContext = await browser.newContext({
    viewport: { width: 375, height: 812 },
    isMobile: true
  });
  const mPage = await mobileContext.newPage();

  // P01 Mobile
  await mPage.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await captureScreen(mPage, 'P01_mobile', 'P01_mobile.png');

  // P02 Mobile
  await mPage.locator('button.mk-p01-cta').click();
  await mPage.waitForURL('**/patient', { timeout: 10000 });
  await mPage.locator('input[placeholder="Enter your name"]').fill('Rajesh Sharma');
  await mPage.locator('input[placeholder="Enter your age"]').fill('38');
  await mPage.locator('button:has-text("Start Now")').click();

  await mPage.waitForSelector('.mk-p02', { timeout: 15000 });
  await captureScreen(mPage, 'P02_mobile', 'P02_mobile.png');

  // P03 Mobile
  await mPage.locator('#consent-agreement').check();
  await mPage.locator('button:has-text("Agree & Continue")').click();
  await mPage.waitForSelector('.mk-p03-main', { timeout: 15000 });
  await captureScreen(mPage, 'P03_mobile', 'P03_mobile.png');

  // P04 Mobile
  await mPage.locator('button.mk-p03-btn--primary').click();
  await mPage.waitForSelector('.mk-p04-main', { timeout: 15000 });
  await captureScreen(mPage, 'P04_mobile', 'P04_mobile.png');

  // P05 Mobile
  await mPage.locator('#mk-p04-input').fill('Severe chest pain and difficulty breathing');
  await mPage.locator('button:has-text("Next Question")').click();
  await mPage.waitForSelector('.mk-p05-main', { timeout: 15000 });
  await captureScreen(mPage, 'P05_mobile', 'P05_mobile.png');

  // P06, P07, P08, P09 Mobile
  await mPage.evaluate(() => window.sessionStorage.clear());
  await mPage.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await mPage.locator('button.mk-p01-cta').click();
  await mPage.waitForURL('**/patient', { timeout: 10000 });
  await mPage.locator('input[placeholder="Enter your name"]').fill('Arjun Sharma');
  await mPage.locator('input[placeholder="Enter your age"]').fill('34');
  await mPage.locator('button:has-text("Start Now")').click();

  await mPage.waitForSelector('.mk-p02', { timeout: 15000 });
  await mPage.locator('#consent-agreement').check();
  await mPage.locator('button:has-text("Agree & Continue")').click();
  await mPage.waitForSelector('.mk-p03-main', { timeout: 15000 });
  await mPage.locator('button.mk-p03-btn--primary').click();
  await mPage.waitForSelector('.mk-p04-main', { timeout: 15000 });

  for (let i = 0; i < answers.length; i++) {
    await mPage.waitForSelector('#mk-p04-input', { timeout: 15000 });
    await mPage.locator('#mk-p04-input').fill(answers[i]);
    await mPage.locator('button:has-text("Next Question")').click();
    if (i < answers.length - 1) {
      await mPage.waitForFunction(() => {
        const inp = document.querySelector('#mk-p04-input');
        return inp && inp.value === '';
      }, { timeout: 20000 });
    }
  }

  // P06 Mobile
  await mPage.waitForSelector('.mk-p06', { timeout: 15000 });
  await captureScreen(mPage, 'P06_mobile', 'P06_mobile.png');

  // P07 Mobile
  await mPage.locator('button.mk-p06-btn--skip').click();
  await mPage.waitForSelector('.mk-p07', { timeout: 15000 });
  await captureScreen(mPage, 'P07_mobile', 'P07_mobile.png');

  // P08 Mobile
  await mPage.locator('button:has-text("Confirm & Generate Token")').click();
  await mPage.waitForSelector('.mk-p08-main', { timeout: 15000 });
  await captureScreen(mPage, 'P08_mobile', 'P08_mobile.png');

  // P09 Mobile
  await mPage.locator('button:has-text("Done / View Waiting Screen")').click();
  await mPage.waitForSelector('.mk-p09-main', { timeout: 15000 });
  await captureScreen(mPage, 'P09_mobile', 'P09_mobile.png');

  // Doctor Workspace Mobile
  await mPage.goto('http://localhost:3000/doctor', { waitUntil: 'networkidle' });
  await mPage.locator('.mk-sidebar__item').filter({ hasText: 'Kayachikitsa Queue' }).click();
  await mPage.waitForSelector('.mk-d01-row', { timeout: 10000 });
  await captureScreen(mPage, 'D01_mobile', 'D01_mobile.png');

  await mPage.locator('.mk-d01-row').first().locator('button.mk-d01-open').click();
  await mPage.waitForSelector('.mk-d02-head', { timeout: 10000 });
  await captureScreen(mPage, 'D02_mobile', 'D02_mobile.png');

  await mPage.locator('button:has-text("Review & Edit Case Details →")').click();
  await mPage.waitForSelector('.mk-d03-os', { timeout: 10000 });
  await captureScreen(mPage, 'D03_mobile', 'D03_mobile.png');

  await mPage.locator('header.mk-d03-os button:has-text("Queue")').click();
  await mPage.locator('.mk-sidebar__item').filter({ hasText: 'Emergency Escalations' }).click();
  await mPage.waitForSelector('.mk-d04-header-card', { timeout: 10000 });
  await captureScreen(mPage, 'D04_mobile', 'D04_mobile.png');

  await mobileContext.close();
  await browser.close();

  console.log('\nAll Visual QA Screenshots captured successfully in:', OUT_DIR);
}

runCapture().catch((err) => {
  console.error('Visual QA capture failed:', err);
  process.exit(1);
});
