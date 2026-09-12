import { chromium } from "playwright-core";

const WEB = "http://localhost:3000";

async function runTests() {
  console.log("=== STARTING P04 REAL BROWSER SUITE ===");
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const results = [];

  function record(name, pass, details = "") {
    results.push({ name, pass, details });
    console.log(`${pass ? "[PASS]" : "[FAIL]"} ${name} ${details ? "- " + details : ""}`);
  }

  try {
    // -------------------------------------------------------------
    // TEST 1: P04 Real Multi-Turn Interview & Anti-Stall Verification
    // -------------------------------------------------------------
    console.log("\n--- TEST 1: P04 Real Multi-Turn Flow & Anti-Stall ---");
    const context1 = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page1 = await context1.newPage();

    // 1. Visit landing page (P01)
    await page1.goto(WEB, { waitUntil: "networkidle" });
    await page1.click(".mk-p01-cta"); // "Continue to Consent ->"

    // 2. Patient registration form on /patient
    await page1.waitForSelector("input[placeholder='Enter your name']");
    await page1.fill("input[placeholder='Enter your name']", "Ramesh Patel");
    await page1.fill("input[placeholder='Enter your age']", "58");
    await page1.click(".mk-chip:has-text('Male')");
    await page1.click("button:has-text('Start Now')");

    // 3. Consent screen (P02)
    await page1.waitForSelector("#consent-agreement");
    await page1.check("#consent-agreement");
    await page1.click("button:has-text('Agree & Continue')");

    // 4. Code screen (P03)
    await page1.waitForSelector("button:has-text('Continue to Interview')");
    await page1.click("button:has-text('Continue to Interview')");

    // 5. P04 Interview Screen
    await page1.waitForSelector(".mk-p04-h1");
    const q1Text = await page1.locator(".mk-p04-h1").innerText();
    record("p04_q1_displayed", q1Text.length > 10, `Q1: "${q1Text}"`);

    // Turn 1 Answer
    const answer1 = "My left knee has been hurting for about six months and it gets worse when I climb stairs.";
    await page1.fill("#mk-p04-input", answer1);
    
    // Click submit and verify state transitions
    const submitBtn = page1.locator(".mk-p04-btn--primary");
    await submitBtn.click();

    // Wait for Next Question to appear
    await page1.waitForFunction(
      (oldQ) => {
        const h1 = document.querySelector(".mk-p04-h1");
        return h1 && h1.innerText !== oldQ;
      },
      q1Text,
      { timeout: 20000 }
    );

    const q2Text = await page1.locator(".mk-p04-h1").innerText();
    const textareaVal1 = await page1.locator("#mk-p04-input").inputValue();

    record("p04_question_advanced_turn1", q2Text !== q1Text && q2Text.length > 5, `Q2: "${q2Text}"`);
    record("p04_textarea_cleared_turn1", textareaVal1 === "", `Textarea value empty: ${textareaVal1 === ""}`);

    // Turn 2 Answer
    const answer2 = "It is an aching pain, around 6 out of 10 in severity.";
    await page1.fill("#mk-p04-input", answer2);
    await submitBtn.click();

    await page1.waitForFunction(
      (oldQ) => {
        const h1 = document.querySelector(".mk-p04-h1");
        return h1 && h1.innerText !== oldQ;
      },
      q2Text,
      { timeout: 20000 }
    );

    const q3Text = await page1.locator(".mk-p04-h1").innerText();
    const textareaVal2 = await page1.locator("#mk-p04-input").inputValue();

    record("p04_question_advanced_turn2", q3Text !== q2Text && q3Text.length > 5, `Q3: "${q3Text}"`);
    record("p04_textarea_cleared_turn2", textareaVal2 === "", `Textarea value empty: ${textareaVal2 === ""}`);

    // -------------------------------------------------------------
    // TEST 2: Mid-Interview Refresh Persistence on P04
    // -------------------------------------------------------------
    console.log("\n--- TEST 2: Mid-Interview Refresh Persistence on P04 ---");
    await page1.reload({ waitUntil: "networkidle" });
    await page1.waitForSelector(".mk-p04-h1");
    const qAfterRefresh = await page1.locator(".mk-p04-h1").innerText();
    record("refresh_preserves_interview_question", qAfterRefresh === q3Text, `Preserved Q: "${qAfterRefresh}"`);

    await context1.close();

    // -------------------------------------------------------------
    // TEST 3: Multilingual UI Flows (Hindi and Gujarati)
    // -------------------------------------------------------------
    console.log("\n--- TEST 3: Multilingual Flow (Hindi) ---");
    const contextHi = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const pageHi = await contextHi.newPage();

    await pageHi.goto(WEB, { waitUntil: "networkidle" });
    // Click Hindi
    await pageHi.click(".mk-p01-lang-card:has-text('हिन्दी')");
    await pageHi.click(".mk-p01-cta");

    await pageHi.waitForSelector("input[placeholder='Enter your name']");
    await pageHi.fill("input[placeholder='Enter your name']", "सुरेश कुमार");
    await pageHi.fill("input[placeholder='Enter your age']", "45");
    await pageHi.click(".mk-chip:has-text('Male')");
    await pageHi.click("button:has-text('Start Now')");

    await pageHi.waitForSelector("#consent-agreement");
    await pageHi.check("#consent-agreement");
    await pageHi.click("button:has-text('Agree & Continue')");

    await pageHi.waitForSelector("button:has-text('Continue to Interview')");
    await pageHi.click("button:has-text('Continue to Interview')");

    await pageHi.waitForSelector(".mk-p04-h1");
    const qHi1 = await pageHi.locator(".mk-p04-h1").innerText();
    record("hindi_initial_question_rendered", qHi1.length > 5, `Hindi Q1: "${qHi1}"`);

    // Submit Hindi response
    await pageHi.fill("#mk-p04-input", "मुझे पिछले तीन दिन से खांसी और बुखार है।");
    await pageHi.locator(".mk-p04-btn--primary").click();

    await pageHi.waitForFunction(
      (oldQ) => {
        const h1 = document.querySelector(".mk-p04-h1");
        return h1 && h1.innerText !== oldQ;
      },
      qHi1,
      { timeout: 20000 }
    );
    const qHi2 = await pageHi.locator(".mk-p04-h1").innerText();
    record("hindi_turn2_advanced", qHi2 !== qHi1 && qHi2.length > 5, `Hindi Q2: "${qHi2}"`);

    await contextHi.close();

    console.log("\n--- TEST 4: Multilingual Flow (Gujarati) ---");
    const contextGu = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const pageGu = await contextGu.newPage();

    await pageGu.goto(WEB, { waitUntil: "networkidle" });
    // Click Gujarati
    await pageGu.click(".mk-p01-lang-card:has-text('ગુજરાતી')");
    await pageGu.click(".mk-p01-cta");

    await pageGu.waitForSelector("input[placeholder='Enter your name']");
    await pageGu.fill("input[placeholder='Enter your name']", "દિનેશ પટેલ");
    await pageGu.fill("input[placeholder='Enter your age']", "50");
    await pageGu.click(".mk-chip:has-text('Male')");
    await pageGu.click("button:has-text('Start Now')");

    await pageGu.waitForSelector("#consent-agreement");
    await pageGu.check("#consent-agreement");
    await pageGu.click("button:has-text('Agree & Continue')");

    await pageGu.waitForSelector("button:has-text('Continue to Interview')");
    await pageGu.click("button:has-text('Continue to Interview')");

    await pageGu.waitForSelector(".mk-p04-h1");
    const qGu1 = await pageGu.locator(".mk-p04-h1").innerText();
    record("gujarati_initial_question_rendered", qGu1.length > 5, `Gujarati Q1: "${qGu1}"`);

    // Submit Gujarati response
    await pageGu.fill("#mk-p04-input", "મને બે દિવસથી પેટમાં બળતરા થાય છે.");
    await pageGu.locator(".mk-p04-btn--primary").click();

    await pageGu.waitForFunction(
      (oldQ) => {
        const h1 = document.querySelector(".mk-p04-h1");
        return h1 && h1.innerText !== oldQ;
      },
      qGu1,
      { timeout: 20000 }
    );
    const qGu2 = await pageGu.locator(".mk-p04-h1").innerText();
    record("gujarati_turn2_advanced", qGu2 !== qGu1 && qGu2.length > 5, `Gujarati Q2: "${qGu2}"`);

    await contextGu.close();

  } catch (err) {
    console.error("Browser test encountered error:", err);
    record("suite_execution", false, String(err));
  } finally {
    await browser.close();
  }

  console.log("\n==================================================");
  console.log("BROWSER TEST SUMMARY:");
  const passCount = results.filter(r => r.pass).length;
  const failCount = results.filter(r => !r.pass).length;
  console.log(`Total: ${results.length} | Passed: ${passCount} | Failed: ${failCount}`);
  console.log("==================================================");
  if (failCount > 0) process.exit(1);
}

runTests();
