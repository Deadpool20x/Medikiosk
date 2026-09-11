const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function runDoctorE2E() {
  const screenshotsDir = path.resolve(__dirname, '..', 'test-artifacts', 'screenshots');
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
  }

  const results = {
    test1_d01_queue: {},
    test2_d02_case_detail: {},
    test3_d03_review_edit: {},
    test4_safety_protection: {},
    test5_browser_health: {},
    test6_refresh: {},
    screenshots: {},
    overallPass: false
  };

  const browserErrors = [];
  const unexpectedNetworkErrors = [];

  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true
  });

  const context = await browser.newContext({
    viewport: { width: 1400, height: 950 }
  });

  const page = await context.newPage();

  // Monitor console errors (ignore known favicon 404 per prompt requirement)
  page.on('console', msg => {
    const text = msg.text();
    const loc = (msg.location() && msg.location().url) || '';
    const isFavicon = text.includes('favicon.ico') || loc.includes('favicon.ico') || (text.includes('404') && text.includes('Failed to load resource'));
    if (msg.type() === 'error' && !isFavicon) {
      browserErrors.push(text);
      console.error('[BROWSER ERROR]', text);
    }
  });

  page.on('pageerror', err => {
    browserErrors.push(err.message);
    console.error('[PAGE UNCAUGHT ERROR]', err.message);
  });

  // Track unexpected 4xx/5xx responses
  page.on('response', res => {
    const url = res.url();
    const status = res.status();
    // Exclude favicon and intentional 409 probe in Test 4
    if (status >= 400 && !url.includes('favicon.ico') && !(url.includes('/doctor/session/demo-safe-01') && status === 409)) {
      unexpectedNetworkErrors.push({ url, status, method: res.request().method() });
      console.warn('[UNEXPECTED HTTP ERROR]', res.request().method(), url, status);
    }
  });

  console.log('\n======================================================');
  console.log('TEST 1 — D01 QUEUE & DEPARTMENT SEPARATION');
  console.log('======================================================');

  await page.goto('http://localhost:3000/doctor', { waitUntil: 'networkidle' });

  // 1. Open Kayachikitsa Queue
  const kayaBtn = page.locator('.mk-sidebar__item').filter({ hasText: 'Kayachikitsa Queue' });
  await kayaBtn.click();
  await page.waitForSelector('.mk-d01-row', { timeout: 15000 });

  const kayaText = await page.locator('.mk-main-content').innerText();
  const kyCasePresent = kayaText.includes('KY-001') && kayaText.includes('MK-KY0042');
  const pkCaseAbsentFromKy = !kayaText.includes('PK-001') && !kayaText.includes('MK-PK0015');
  const safeCaseAbsentFromKy = !kayaText.includes('MK-SF0007') && !kayaText.includes('Ramesh Kumar');

  console.log('Kayachikitsa Queue checks:', {
    kyCasePresent,
    pkCaseAbsentFromKy,
    safeCaseAbsentFromKy
  });

  // 2. Open Panchakarma Queue
  const panchaBtn = page.locator('.mk-sidebar__item').filter({ hasText: 'Panchakarma Queue' });
  await panchaBtn.click();
  await page.waitForSelector('.mk-d01-row', { timeout: 15000 });

  const panchaText = await page.locator('.mk-main-content').innerText();
  const pkCasePresent = panchaText.includes('PK-001') && panchaText.includes('MK-PK0015');
  const kyCaseAbsentFromPk = !panchaText.includes('KY-001') && !panchaText.includes('MK-KY0042');
  const safeCaseAbsentFromPk = !panchaText.includes('MK-SF0007') && !panchaText.includes('Ramesh Kumar');

  console.log('Panchakarma Queue checks:', {
    pkCasePresent,
    kyCaseAbsentFromPk,
    safeCaseAbsentFromPk
  });

  // Switch back to Kayachikitsa for D01 screenshot
  await kayaBtn.click();
  await page.waitForSelector('.mk-d01-row', { timeout: 15000 });
  const d01Screenshot = path.join(screenshotsDir, 'D01_queue.png');
  await page.screenshot({ path: d01Screenshot, fullPage: true });
  results.screenshots['D01_queue'] = d01Screenshot;

  results.test1_d01_queue = {
    pass: kyCasePresent && pkCaseAbsentFromKy && safeCaseAbsentFromKy && pkCasePresent && kyCaseAbsentFromPk && safeCaseAbsentFromPk,
    kyCasePresent,
    pkCaseAbsentFromKy,
    safeCaseAbsentFromKy,
    pkCasePresent,
    kyCaseAbsentFromPk,
    safeCaseAbsentFromPk
  };
  console.log('TEST 1 Result:', results.test1_d01_queue.pass ? 'PASS ✅' : 'FAIL ❌');

  console.log('\n======================================================');
  console.log('TEST 2 — D02 CASE DETAIL');
  console.log('======================================================');

  // Open the completed patient from D01 (KY-001 / MK-KY0042)
  const openCaseBtn = page.locator('.mk-d01-row').filter({ hasText: 'KY-001' }).locator('button.mk-d01-open');
  await openCaseBtn.click();

  await page.waitForSelector('.mk-d02-head', { timeout: 15000 });
  console.log('D02 Case Detail view loaded.');

  const d02Screenshot = path.join(screenshotsDir, 'D02_case.png');
  await page.screenshot({ path: d02Screenshot, fullPage: true });
  results.screenshots['D02_case'] = d02Screenshot;

  const d02Text = await page.locator('.mk-doctor-shell').innerText();

  const hasPatientIdentity = d02Text.includes('MK-KY0042') && d02Text.includes('KY-001');
  const hasChiefComplaint = d02Text.includes('Persistent stomach pain and digestive issues');
  const hasHpiFields = d02Text.includes('One week ago after a heavy meal') && d02Text.includes('Constant, worsening after meals');
  const hasSymptoms = d02Text.includes('nausea') && d02Text.includes('bloating');
  const hasOcrInfo = d02Text.includes('Metformin') && d02Text.includes('500 mg') && d02Text.includes('Twice daily');
  const hasProvenance = d02Text.includes('AI extraction (groq)') || d02Text.includes('OCR extraction') || d02Text.includes('High confidence');
  const hasNoFabricatedAyurveda = !d02Text.includes('Pitta Dosha Imbalance') && !d02Text.includes('Vata Aggravation');
  const hasSafetyIndicator = !d02Text.includes('CLINICAL SAFETY NOTICE');

  results.test2_d02_case_detail = {
    pass: hasPatientIdentity && hasChiefComplaint && hasHpiFields && hasSymptoms && hasOcrInfo && hasNoFabricatedAyurveda && hasSafetyIndicator,
    hasPatientIdentity,
    hasChiefComplaint,
    hasHpiFields,
    hasSymptoms,
    hasOcrInfo,
    hasProvenance,
    hasNoFabricatedAyurveda,
    hasSafetyIndicator
  };
  console.log('TEST 2 Result:', results.test2_d02_case_detail.pass ? 'PASS ✅' : 'FAIL ❌', results.test2_d02_case_detail);

  console.log('\n======================================================');
  console.log('TEST 3 — D03 REVIEW / EDIT & CONFIRMATION');
  console.log('======================================================');

  // Open D03 by clicking "Review & Edit Case Details →"
  const editBtn = page.locator('button:has-text("Review & Edit Case Details →")');
  await editBtn.click();

  await page.waitForSelector('.mk-d03-os', { timeout: 15000 });
  console.log('D03 Review / Edit view loaded.');

  const d03BeforeScreenshot = path.join(screenshotsDir, 'D03_review_edit_before_save.png');
  await page.screenshot({ path: d03BeforeScreenshot, fullPage: true });
  results.screenshots['D03_review_edit_before_save'] = d03BeforeScreenshot;

  // Test discard/cancel behavior:
  const onsetInput = page.locator('[data-purpose="onset-input"]');
  const originalOnset = await onsetInput.inputValue();
  await onsetInput.fill('Temporary uncommitted text to test discard');
  const discardBtn = page.locator('.mk-d03-footer button:has-text("Discard Changes")');
  await discardBtn.click();
  const onsetAfterDiscard = await onsetInput.inputValue();
  const discardReverted = onsetAfterDiscard === originalOnset;
  console.log('Discard reverted input:', discardReverted);

  // Edit fields
  const newChief = 'Persistent severe epigastric cramping and indigestion after meals';
  const newSeverity = 'Severe — 7 out of 10';
  const chiefTextarea = page.locator('[data-purpose="chief-complaint-input"]');
  await chiefTextarea.fill(newChief);
  const severityInput = page.locator('[data-purpose="severity-input"]');
  await severityInput.fill(newSeverity);

  // Save changes
  const saveBtn = page.locator('.mk-d03-footer button:has-text("Save Changes")');
  await saveBtn.click();
  await page.waitForTimeout(1500);

  const d03AfterSaveScreenshot = path.join(screenshotsDir, 'D03_after_save.png');
  await page.screenshot({ path: d03AfterSaveScreenshot, fullPage: true });
  results.screenshots['D03_after_save'] = d03AfterSaveScreenshot;

  // Verify persistence via reload on D03
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('.mk-d03-os', { timeout: 10000 });

  const reloadedChief = await page.locator('[data-purpose="chief-complaint-input"]').inputValue();
  const reloadedSeverity = await page.locator('[data-purpose="severity-input"]').inputValue();
  const editPersisted = (reloadedChief === newChief) && (reloadedSeverity === newSeverity);

  // Check backend session state
  const sResp = await page.request.get('http://127.0.0.1:8000/doctor/session/demo-ky-001');
  const sJson = await sResp.json();
  const doctorReviewEdited = sJson.doctor_review.edited === true;
  const ocrPreserved = sJson.documents.length > 0 && sJson.documents[0].extracted_value === 'Metformin' && !!sJson.documents[0].original_extraction;

  console.log('D03 Edit checks:', {
    editPersisted,
    doctorReviewEdited,
    ocrPreserved
  });

  // Confirm case
  const confirmBtn = page.locator('.mk-d03-footer button:has-text("Confirm Case")');
  await confirmBtn.click();
  await page.waitForTimeout(1500);

  const sConfirmedResp = await page.request.get('http://127.0.0.1:8000/doctor/session/demo-ky-001');
  const sConfirmedJson = await sConfirmedResp.json();
  const doctorConfirmed = sConfirmedJson.doctor_review.confirmed === true;
  console.log('Doctor Confirmed in backend:', doctorConfirmed);

  results.test3_d03_review_edit = {
    pass: discardReverted && editPersisted && doctorReviewEdited && ocrPreserved && doctorConfirmed,
    discardReverted,
    editPersisted,
    doctorReviewEdited,
    ocrPreserved,
    doctorConfirmed
  };
  console.log('TEST 3 Result:', results.test3_d03_review_edit.pass ? 'PASS ✅' : 'FAIL ❌');

  console.log('\n======================================================');
  console.log('TEST 4 — SAFETY PROTECTION');
  console.log('======================================================');

  // Navigate back to workspace queue via ClinicalOSBar Queue button or evaluate clearing sessionStorage
  const queueNavBtn = page.locator('header.mk-d03-os button:has-text("Queue")');
  if (await queueNavBtn.isVisible()) {
    await queueNavBtn.click();
  } else {
    await page.evaluate(() => window.sessionStorage.removeItem('mk_doctor_view'));
    await page.goto('http://localhost:3000/doctor', { waitUntil: 'networkidle' });
  }

  // 1. Open Emergency Escalations (D04)
  const emergBtn = page.locator('.mk-sidebar__item').filter({ hasText: 'Emergency Escalations' });
  await emergBtn.click();
  await page.waitForSelector('.mk-d04-header-card', { timeout: 10000 });
  await page.waitForTimeout(1000);

  const d04Text = await page.locator('.mk-d04-queue-section').innerText();
  const caseFoundInD04 = d04Text.includes('Ramesh Kumar') && d04Text.includes('MK-SF0007') && d04Text.includes('chest pain');

  const d04Screenshot = path.join(screenshotsDir, 'D04_emergency.png');
  await page.screenshot({ path: d04Screenshot, fullPage: true });
  results.screenshots['D04_emergency'] = d04Screenshot;

  // 2. Prohibited confirmation: doctor PATCH on safety-flagged session with doctor_confirmed=true returns 409
  const patchSafetyResp = await page.request.patch('http://127.0.0.1:8000/doctor/session/demo-safe-01', {
    data: { doctor_confirmed: true }
  });
  const patchSafetyStatus = patchSafetyResp.status();
  const patchSafetyRejected = patchSafetyStatus === 409;
  console.log('Doctor PATCH on flagged session status:', patchSafetyStatus, '(Expected: 409)');

  // 3. Verify safety state remains true
  const safeSessionResp = await page.request.get('http://127.0.0.1:8000/doctor/session/demo-safe-01');
  const safeSessionJson = await safeSessionResp.json();
  const safetyStateRemains = safeSessionJson.safety_flagged === true && safeSessionJson.doctor_review.confirmed === false;
  console.log('Safety flagged remains true, confirmed remains false:', safetyStateRemains);

  results.test4_safety_protection = {
    pass: caseFoundInD04 && patchSafetyRejected && safetyStateRemains,
    caseFoundInD04,
    patchSafetyRejected,
    patchSafetyStatus,
    safetyStateRemains
  };
  console.log('TEST 4 Result:', results.test4_safety_protection.pass ? 'PASS ✅' : 'FAIL ❌');

  console.log('\n======================================================');
  console.log('TEST 6 — REFRESH PERSISTENCE (D01, D02, D03)');
  console.log('======================================================');

  // Refresh at D01
  const kayaNav = page.locator('.mk-sidebar__item').filter({ hasText: 'Kayachikitsa Queue' });
  await kayaNav.click();
  await page.waitForSelector('.mk-d01-row', { timeout: 10000 });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('.mk-d01-ribbon', { timeout: 10000 });
  const d01AfterReload = await page.locator('.mk-d01-ribbon__title').innerText();
  const d01Restored = d01AfterReload.includes('Kayachikitsa');
  console.log('D01 Refresh restored Kayachikitsa Queue:', d01Restored);

  // Open D02 and refresh
  const caseRowBtn = page.locator('.mk-d01-row').first().locator('button.mk-d01-open');
  await caseRowBtn.click();
  await page.waitForSelector('.mk-d02-head', { timeout: 10000 });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('.mk-d02-head', { timeout: 10000 });
  const d02AfterReload = await page.locator('.mk-d02-footer__token').innerText();
  const d02Restored = d02AfterReload.includes('KY-001');
  console.log('D02 Refresh restored case detail:', d02Restored);

  // Open D03 and refresh
  await page.locator('button:has-text("Review & Edit Case Details →")').click();
  await page.waitForSelector('.mk-d03-os', { timeout: 10000 });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('.mk-d03-os', { timeout: 10000 });
  const d03AfterReload = await page.locator('.mk-d03-banner__token').innerText();
  const d03Restored = d03AfterReload.includes('KY-001');
  console.log('D03 Refresh restored review/edit view:', d03Restored);

  results.test6_refresh = {
    pass: d01Restored && d02Restored && d03Restored,
    d01Restored,
    d02Restored,
    d03Restored
  };
  console.log('TEST 6 Result:', results.test6_refresh.pass ? 'PASS ✅' : 'FAIL ❌');

  console.log('\n======================================================');
  console.log('TEST 5 — BROWSER HEALTH & NETWORK INTEGRITY');
  console.log('======================================================');

  results.test5_browser_health = {
    pass: browserErrors.length === 0 && unexpectedNetworkErrors.length === 0,
    browserErrorsCount: browserErrors.length,
    browserErrors,
    unexpectedNetworkErrorsCount: unexpectedNetworkErrors.length,
    unexpectedNetworkErrors
  };
  console.log('TEST 5 Result:', results.test5_browser_health.pass ? 'PASS ✅' : 'FAIL ❌', results.test5_browser_health);

  await browser.close();

  results.overallPass = results.test1_d01_queue.pass &&
    results.test2_d02_case_detail.pass &&
    results.test3_d03_review_edit.pass &&
    results.test4_safety_protection.pass &&
    results.test5_browser_health.pass &&
    results.test6_refresh.pass;

  const reportPath = path.resolve(__dirname, '..', 'test-artifacts', 'doctor_e2e_report.json');
  fs.writeFileSync(reportPath, JSON.stringify(results, null, 2), 'utf8');
  console.log('\nDoctor E2E Report saved to:', reportPath);
  console.log(`\nOVERALL DOCTOR E2E RESULT: ${results.overallPass ? 'ALL TESTS PASSED ✅' : 'SOME TESTS FAILED ❌'}`);

  return results;
}

runDoctorE2E().then(r => {
  if (!r.overallPass) process.exit(1);
  process.exit(0);
}).catch(err => {
  console.error('FATAL DOCTOR E2E FAILURE:', err);
  process.exit(1);
});
