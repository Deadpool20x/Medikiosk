const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function runSafetyE2E() {
  const screenshotsDir = path.resolve(__dirname, '..', 'test-artifacts', 'screenshots');
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
  }

  const results = {
    checkpoints: {},
    sessionId: null,
    patientCode: null,
    patientName: 'Kavita Verma',
    redFlagPhrase: 'I have severe chest pain and difficulty breathing since one hour ago',
    screenshots: {},
    browserErrors: [],
    unexpectedHttpErrors: [],
    prohibitedOperations: {},
    doctorPatch409Verified: false,
    overallPass: false
  };

  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 }
  });

  const page = await context.newPage();

  // Monitor console errors (ignore known favicon 404 behavior per prompt requirement 12)
  page.on('console', msg => {
    const text = msg.text();
    const loc = (msg.location() && msg.location().url) || '';
    const isFavicon404 = text.includes('favicon.ico') || loc.includes('favicon.ico') || (text.includes('404') && text.includes('Failed to load resource'));
    if (msg.type() === 'error' && !isFavicon404) {
      results.browserErrors.push(text);
      console.error('[BROWSER ERROR]', text);
    }
  });


  page.on('pageerror', err => {
    results.browserErrors.push(err.message);
    console.error('[PAGE UNCAUGHT ERROR]', err.message);
  });

  // Track network responses to catch unexpected 4xx/5xx (excluding intentional test probes)
  const intentionalProbeUrls = ['/token', '/upload', '/doctor/session/'];
  page.on('response', res => {
    const url = res.url();
    const status = res.status();
    if (status >= 400 && !url.includes('/favicon.ico')) {
      const isExpectedProbe = intentionalProbeUrls.some(p => url.includes(p));
      if (!isExpectedProbe) {
        results.unexpectedHttpErrors.push({ url, status, method: res.request().method() });
        console.warn('[UNEXPECTED HTTP ERROR]', res.request().method(), url, status);
      }
    }
  });

  console.log('\n======================================================');
  console.log('1. P01 -> P02 -> P03 -> P04 Normal Path');
  console.log('======================================================');

  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  
  // Select English, New Patient
  await page.locator('.mk-p01-lang-card').filter({ hasText: 'English' }).click();
  await page.locator('.mk-p01-status-card').filter({ hasText: 'New Patient' }).click();
  await page.locator('button.mk-p01-cta').click();

  await page.waitForURL('**/patient', { timeout: 10000 });

  // P01 Patient Welcome Form
  const nameInput = page.locator('input[placeholder="Enter your name"]');
  await nameInput.waitFor({ state: 'visible', timeout: 5000 });
  await nameInput.fill(results.patientName);
  await page.locator('input[placeholder="Enter your age"]').fill('45');
  await page.locator('.mk-chip').filter({ hasText: 'Female' }).click();

  // Start Session
  await page.locator('button:has-text("Start Now")').click();

  // P02 Consent
  await page.waitForSelector('.mk-p02', { timeout: 15000 });
  await page.locator('#consent-agreement').check();
  await page.locator('button:has-text("Agree & Continue")').click();

  // P03 Patient Code
  await page.waitForSelector('.mk-p03', { timeout: 15000 });
  await page.waitForFunction(() => {
    const el = document.querySelector('.mk-p03-code');
    return el && el.textContent && el.textContent.startsWith('MK-');
  }, { timeout: 10000 });

  results.patientCode = (await page.locator('.mk-p03-code').textContent()).trim();
  console.log('Patient Code generated:', results.patientCode);

  // Retrieve sessionId from sessionStorage
  results.sessionId = await page.evaluate(() => window.sessionStorage.getItem('medikiosk_session_id'));
  console.log('Session ID:', results.sessionId);

  results.checkpoints['1_normal_p01_to_p03'] = results.patientCode.startsWith('MK-') && !!results.sessionId;

  // Continue to Interview (P04)
  await page.locator('button:has-text("Continue to Interview")').click();
  await page.waitForSelector('.mk-p04', { timeout: 15000 });

  // Capture P04 before red flag
  const p04Screenshot = path.join(screenshotsDir, 'P04_before_red_flag.png');
  await page.screenshot({ path: p04Screenshot, fullPage: true });
  results.screenshots['P04_before_red_flag'] = p04Screenshot;
  console.log('P04 reached. Screenshot saved:', p04Screenshot);

  console.log('\n======================================================');
  console.log('2. Submit Red-Flag Response & Verify Transition to P05');
  console.log('======================================================');

  console.log(`Entering red-flag answer: "${results.redFlagPhrase}"`);
  const textarea = page.locator('#mk-p04-input');
  await textarea.fill(results.redFlagPhrase);

  const submitBtn = page.locator('button:has-text("Next Question")');
  await submitBtn.click();

  // Wait for P05 safety screen (.mk-p05)
  await page.waitForSelector('.mk-p05', { timeout: 15000 });
  console.log('P05 Safety screen rendered successfully.');

  const p05Screenshot = path.join(screenshotsDir, 'P05_safety_screen.png');
  await page.screenshot({ path: p05Screenshot, fullPage: true });
  results.screenshots['P05_safety_screen'] = p05Screenshot;

  results.checkpoints['2_red_flag_submitted'] = true;
  results.checkpoints['3_transition_to_p05'] = await page.locator('.mk-p05').isVisible();

  // 4. Verify session.safety_flagged == true in backend
  const backendCheck1 = await page.request.get(`http://127.0.0.1:8000/session/${results.sessionId}`);
  const sData1 = await backendCheck1.json();
  results.checkpoints['4_session_safety_flagged_true'] = sData1.safety_flagged === true;
  console.log('Backend safety_flagged:', sData1.safety_flagged, 'matched_terms:', sData1.safety_detail);

  // 5. Verify P05 shows intended safety escalation UI
  const p05Title = await page.locator('.mk-p05-h1').innerText();
  const p05Text = await page.locator('.mk-p05').innerText();
  const hasIntakePaused = p05Text.includes('Intake Process Paused') || p05Text.includes('Intake Paused');
  const hasStaffGuidance = p05Title.includes('Please speak with a staff member') || p05Text.includes('speak with a staff member');
  const hasNoTokenNotice = p05Text.includes('No department queue token has been generated');
  
  results.checkpoints['5_p05_escalation_ui'] = hasIntakePaused && hasStaffGuidance && hasNoTokenNotice;
  console.log('P05 UI Elements verified:', { hasIntakePaused, hasStaffGuidance, hasNoTokenNotice });

  // 6. Verify session does NOT receive a normal queue token
  results.checkpoints['6_no_normal_queue_token'] = sData1.queue_token === null;
  console.log('Queue token in backend:', sData1.queue_token);

  console.log('\n======================================================');
  console.log('7 & 8. Verify D01 Normal Queue Absence & D04 Presence');
  console.log('======================================================');

  // Open doctor page in new context/page
  const docPage = await context.newPage();
  await docPage.goto('http://localhost:3000/doctor', { waitUntil: 'networkidle' });

  // Check D04 Emergency Dashboard (default or click Emergency Escalations)
  await docPage.waitForSelector('.mk-d04-header-card', { timeout: 10000 });
  const d04Text = await docPage.locator('.mk-d04-queue-section').innerText();
  const caseFoundInD04 = d04Text.includes(results.patientCode) && d04Text.includes(results.patientName);

  const d04Screenshot = path.join(screenshotsDir, 'D04_emergency_dashboard.png');
  await docPage.screenshot({ path: d04Screenshot, fullPage: true });
  results.screenshots['D04_emergency_dashboard'] = d04Screenshot;

  results.checkpoints['8_appears_in_d04_emergency'] = caseFoundInD04;
  console.log('Case found in D04 Emergency Escalations:', caseFoundInD04);

  // Check D01 Normal Queues (Kayachikitsa and Panchakarma)
  const kayaBtn = docPage.locator('.mk-sidebar__item').filter({ hasText: 'Kayachikitsa Queue' });
  await kayaBtn.click();
  await docPage.waitForSelector('.mk-d01-ribbon', { timeout: 10000 });
  await docPage.waitForTimeout(1000);
  const kayaText = await docPage.locator('.mk-main-content').innerText();
  const caseAbsentInKaya = !kayaText.includes(results.patientCode);

  const panchaBtn = docPage.locator('.mk-sidebar__item').filter({ hasText: 'Panchakarma Queue' });
  await panchaBtn.click();
  await docPage.waitForSelector('.mk-d01-ribbon', { timeout: 10000 });
  await docPage.waitForTimeout(1000);
  const panchaText = await docPage.locator('.mk-main-content').innerText();
  const caseAbsentInPancha = !panchaText.includes(results.patientCode);

  const d01Screenshot = path.join(screenshotsDir, 'D01_normal_queue_case_absent.png');
  await docPage.screenshot({ path: d01Screenshot, fullPage: true });
  results.screenshots['D01_normal_queue_case_absent'] = d01Screenshot;

  results.checkpoints['7_absent_from_d01_normal_queue'] = caseAbsentInKaya && caseAbsentInPancha;
  console.log('Case absent from D01 queues:', { caseAbsentInKaya, caseAbsentInPancha });

  await docPage.close();

  console.log('\n======================================================');
  console.log('9. Refresh Patient Browser & Verify Safety State Persists');
  console.log('======================================================');

  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('.mk-p05', { timeout: 10000 });
  const p05PostRefreshText = await page.locator('.mk-p05').innerText();
  const postRefreshSafetyActive = p05PostRefreshText.includes('Intake Process Paused') || p05PostRefreshText.includes('Intake Paused');

  const postRefreshScreenshot = path.join(screenshotsDir, 'P05_post_refresh_safety.png');
  await page.screenshot({ path: postRefreshScreenshot, fullPage: true });
  results.screenshots['P05_post_refresh_safety'] = postRefreshScreenshot;

  results.checkpoints['9_refresh_safety_state_persists'] = postRefreshSafetyActive;
  console.log('Post-refresh safety screen persists:', postRefreshSafetyActive);

  console.log('\n======================================================');
  console.log('10 & 11. Attempt Prohibited Operations (API & Doctor)');
  console.log('======================================================');

  // Prohibited Op A: Token creation on safety-flagged session
  const tokenResp = await page.request.post(`http://127.0.0.1:8000/session/${results.sessionId}/token`);
  const tokenStatus = tokenResp.status();
  results.prohibitedOperations['token_creation'] = {
    status: tokenStatus,
    rejected: tokenStatus === 403
  };
  console.log('Prohibited token creation status:', tokenStatus, '(Expected: 403)');

  // Prohibited Op B: Document upload on safety-flagged session
  const prescriptionPath = path.resolve(__dirname, '..', 'sample-prescription.png');
  const fileBuffer = fs.readFileSync(prescriptionPath);
  const uploadResp = await page.request.post(`http://127.0.0.1:8000/session/${results.sessionId}/upload`, {
    multipart: {
      file: {
        name: 'sample-prescription.png',
        mimeType: 'image/png',
        buffer: fileBuffer
      }
    }
  });
  const uploadStatus = uploadResp.status();
  results.prohibitedOperations['document_upload'] = {
    status: uploadStatus,
    rejected: uploadStatus === 403
  };
  console.log('Prohibited document upload status:', uploadStatus, '(Expected: 403)');

  // Prohibited Op C / 11: Doctor confirmation on safety-flagged session (PATCH with doctor_confirmed=true)
  const doctorPatchResp = await page.request.patch(`http://127.0.0.1:8000/doctor/session/${results.sessionId}`, {
    data: { doctor_confirmed: true }
  });
  const doctorPatchStatus = doctorPatchResp.status();
  results.prohibitedOperations['doctor_confirmation'] = {
    status: doctorPatchStatus,
    rejectedWith409: doctorPatchStatus === 409
  };
  results.doctorPatch409Verified = (doctorPatchStatus === 409);
  console.log('Prohibited doctor confirmation status:', doctorPatchStatus, '(Expected: 409)');

  results.checkpoints['10_prohibited_operations_rejected'] = (tokenStatus === 403) && (uploadStatus === 403);
  results.checkpoints['11_doctor_confirmation_returns_409'] = (doctorPatchStatus === 409);

  // 12. Verify no browser console errors
  results.checkpoints['12_no_browser_console_errors'] = results.browserErrors.length === 0;

  // 13. Verify no unexpected HTTP 4xx/5xx
  results.checkpoints['13_no_unexpected_http_errors'] = results.unexpectedHttpErrors.length === 0;

  await browser.close();

  results.overallPass = Object.values(results.checkpoints).every(v => v === true);

  const reportPath = path.resolve(__dirname, '..', 'test-artifacts', 'safety_e2e_report.json');
  fs.writeFileSync(reportPath, JSON.stringify(results, null, 2), 'utf8');
  console.log('\nSafety E2E Report saved to:', reportPath);
  console.log(`OVERALL SAFETY E2E RESULT: ${results.overallPass ? 'ALL CHECKPOINTS PASSED ✅' : 'SOME CHECKPOINTS FAILED ❌'}`);

  return results;
}

runSafetyE2E().then(r => {
  if (!r.overallPass) process.exit(1);
  process.exit(0);
}).catch(err => {
  console.error('FATAL SAFETY E2E FAILURE:', err);
  process.exit(1);
});
