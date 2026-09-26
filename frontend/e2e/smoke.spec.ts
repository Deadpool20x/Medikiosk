import { test, expect, type Page, type APIRequestContext } from "@playwright/test";

const API = "http://127.0.0.1:8124";

// NOTE: this environment has no live LLM provider keys, so interviewer
// questions come from the deterministic fallback path (honestly labeled
// `fallback_generated` server-side). These specs prove observable patient-UX
// behavior: language chrome, routing, persistence, completion. Live-LLM
// question quality is covered by backend stub tests, not fabricated here.

async function chooseLanguage(page: Page, label: string) {
  await page.goto("/");
  await page.getByRole("button", { name: label }).click();
}

async function continueToPatient(page: Page, ctaName: string) {
  await page.getByRole("button", { name: ctaName }).click();
  await expect(page).toHaveURL(/\/patient/);
}

async function fillWelcome(page: Page, namePH: string, agePH: string, startName: string) {
  await page.getByPlaceholder(namePH).fill("Smoke Patient");
  await page.getByPlaceholder(agePH).fill("34");
  await page.getByRole("button", { name: startName }).click();
}

async function passConsent(page: Page, agreeName: string) {
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: agreeName }).click();
}

async function passCodeScreen(page: Page, continueName: string) {
  await expect(page.getByText(/AIIA-/).first()).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: continueName }).click();
}

async function answerInterview(page: Page, inputPH: string, nextName: string, text: string) {
  await page.getByPlaceholder(inputPH).fill(text);
  await page.getByRole("button", { name: nextName }).click();
}

function interviewQuestion(page: Page) {
  return page.locator(".mk-p04-h1");
}

async function completePriorVisit(request: APIRequestContext): Promise<string> {
  const start = await request.post(`${API}/session/start`, {
    data: { patient: { name: "Prior Pat", age: 50, gender: "male" }, language: "en", visit_type: "new" },
  });
  const sid = (await start.json()).session_id as string;
  await request.post(`${API}/session/${sid}/consent`, { data: { consent_given: true } });
  const codeRes = await request.post(`${API}/session/${sid}/patient-code`);
  const code = (await codeRes.json()).patient_code as string;
  for (const a of [
    "Lower back pain for two months.",
    "It is on the left side.",
    "Pain increases when climbing stairs.",
    "Mornings feel stiff.",
    "It disturbs my daily work.",
  ]) {
    await request.post(`${API}/session/${sid}/answer`, { data: { answer: a } });
  }
  await request.post(`${API}/session/${sid}/documents-complete`);
  return code;
}

test("1. new patient EN adaptive interview to token + waiting", async ({ page }) => {
  await chooseLanguage(page, "English");
  await continueToPatient(page, "Continue to Consent");
  await fillWelcome(page, "Enter your name", "Enter your age", "Start Now");
  await passConsent(page, "Agree & Continue");
  await passCodeScreen(page, "Continue to Interview");

  const q = interviewQuestion(page);
  await expect(q).toContainText(/./);
  const q1 = (await q.textContent()) ?? "";

  // multi-answer adaptive loop (5 max turns)
  for (const a of [
    "I have had stomach burning for two weeks.",
    "It gets worse after spicy food.",
    "No fever.",
    "It is mild.",
    "It disturbs my sleep.",
  ]) {
    await answerInterview(page, "Type your response here", "Next Question", a);
    if (await page.getByRole("button", { name: "Skip this step" }).count()) break;
  }
  // documents → skip → summary → token → waiting
  await page.getByRole("button", { name: "Skip this step" }).click();
  await expect(page.getByText("Review your information")).toBeVisible();
  await page.getByRole("button", { name: "Confirm & Generate Token" }).click();
  await expect(page.getByText("Your information is confirmed")).toBeVisible();
  await expect(page.locator(".mk-p08-token-box__number")).toContainText(/-/);
  await page.getByRole("button", { name: "Done / View Waiting Screen" }).click();
  await expect(page.getByText("Please wait for your token to be called")).toBeVisible();
  expect(q1.length).toBeGreaterThan(5);
});

test("2. new patient HI: chrome + interviewer question in Hindi", async ({ page }) => {
  await chooseLanguage(page, "हिन्दी");
  await continueToPatient(page, "सहमति के लिए आगे बढ़ें");
  await expect(page.getByText("पूरा नाम")).toBeVisible();
  await fillWelcome(page, "अपना नाम लिखें", "अपनी आयु लिखें", "अभी शुरू करें");
  await passConsent(page, "सहमत हूँ और आगे बढ़ें");
  await passCodeScreen(page, "साक्षात्कार के लिए आगे बढ़ें");
  const q = interviewQuestion(page);
  await expect(q).toContainText(/[\u0900-\u097F][\u0900-\u097F\s]{9,}/);
  await expect(q).not.toContainText(/What is the primary/i);
  await answerInterview(page, "अपना उत्तर यहाँ लिखें", "अगला प्रश्न", "मुझे दो हफ्तों से पेट में जलन है");
  await expect(interviewQuestion(page)).toContainText(/[\u0900-\u097F][\u0900-\u097F\s]{9,}/);
});

test("3. new patient GU: chrome + interviewer question in Gujarati script", async ({ page }) => {
  await chooseLanguage(page, "ગુજરાતી");
  await continueToPatient(page, "સંમતિ માટે આગળ વધો");
  await expect(page.getByText("પૂરું નામ")).toBeVisible();
  await fillWelcome(page, "આપનું નામ લખો", "આપની ઉંમર લખો", "હમણાં શરૂ કરો");
  await passConsent(page, "સંમત છું અને આગળ વધો");
  await passCodeScreen(page, "ઇન્ટરવ્યૂ માટે આગળ વધો");
  const q = interviewQuestion(page);
  await expect(q).toContainText(/[\u0A80-\u0AFF][\u0A80-\u0AFF\s]{9,}/);
  await expect(q).not.toContainText(/What is the primary/i);
  await answerInterview(page, "આપનો જવાબ અહીં લખો", "આગળનો પ્રશ્ન", "મને બે અઠવાડિયાથી પેટમાં બળતરા છે");
  const q2 = interviewQuestion(page);
  await expect(q2).toContainText(/[\u0A80-\u0AFF][\u0A80-\u0AFF\s]{9,}/);
  await expect(q2).not.toContainText(/How long have you been experiencing this issue\?/);
});

test("4. returning patient: prior code resolves + new interview starts", async ({ page, request }) => {
  const code = await completePriorVisit(request);
  await chooseLanguage(page, "English");
  await page.getByRole("button", { name: "Returning Patient" }).click();
  await continueToPatient(page, "Continue to Consent");
  await fillWelcome(page, "Enter your name", "Enter your age", "Continue");
  await page.getByPlaceholder("AIIA-YYYYMM-NNNNN").fill(code);
  await page.getByRole("button", { name: "Look Up" }).click();
  await expect(page.getByText("Previous visit found")).toBeVisible();
  await expect(page.getByText(/Last complaint:/)).toContainText(/Lower back pain/);
  await page.getByRole("button", { name: "Start Visit" }).click();
  await passConsent(page, "Agree & Continue");
  await passCodeScreen(page, "Continue to Interview");
  await expect(interviewQuestion(page)).toContainText(/./);
});

test("5. refresh during interview restores state", async ({ page }) => {
  await chooseLanguage(page, "English");
  await continueToPatient(page, "Continue to Consent");
  await fillWelcome(page, "Enter your name", "Enter your age", "Start Now");
  await passConsent(page, "Agree & Continue");
  await passCodeScreen(page, "Continue to Interview");
  const q1 = ((await interviewQuestion(page).textContent()) ?? "").trim();
  await answerInterview(page, "Type your response here", "Next Question", "Lower back pain for two months.");
  await expect(interviewQuestion(page)).not.toHaveText(q1, { timeout: 15_000 });
  const before = ((await interviewQuestion(page).textContent()) ?? "").trim();
  expect(before.length).toBeGreaterThan(5);
  await page.reload();
  await expect(interviewQuestion(page)).toHaveText(before, { timeout: 15_000 });
});

test("6. multi-fact answer does not re-ask known duration", async ({ page }) => {
  await chooseLanguage(page, "English");
  await continueToPatient(page, "Continue to Consent");
  await fillWelcome(page, "Enter your name", "Enter your age", "Start Now");
  await passConsent(page, "Agree & Continue");
  await passCodeScreen(page, "Continue to Interview");
  await answerInterview(
    page,
    "Type your response here",
    "Next Question",
    "I've had this for two weeks, it is mild, and spicy food makes it worse.",
  );
  await expect(interviewQuestion(page)).not.toContainText("How long have you been experiencing this issue?");
});
