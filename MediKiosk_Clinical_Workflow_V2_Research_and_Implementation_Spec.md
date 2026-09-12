# MediKiosk — Clinical Workflow V2 & Adaptive Ayurvedic Case-Taking Specification

Status: Working specification after judge feedback, hands-on testing, repository audit, and external research
Date: 12 September 2026

## 1. Why this document exists

MediKiosk is technically functional, but the current patient journey behaves too much like a fixed questionnaire. The key defects are:

- the backend currently defines six fixed questions in a fixed order;
- the LLM extracts the current field but does not meaningfully determine adaptive follow-up questions;
- language is stored but not propagated through question/UI behavior;
- returning-patient behavior is currently a dead UI concept;
- emergency handling is mixed into the self-service kiosk journey;
- the Ayurvedic case-taking layer is not yet clinician-validated.

This specification changes the product goal from “AI questionnaire” to “AI-assisted, multilingual, adaptive pre-consultation for an Ayurveda OPD.”

This is an implementation specification, not a claim that any clinical protocol is already validated. Ayurvedic question sets must be reviewed with an Ayurvedic clinician before being presented as clinically validated.

## 2. External grounding

AIIA's published hospital material shows a real multi-specialty OPD environment rather than a single generic clinic. AIIA describes multiple specialty/care units including gastrointestinal and liver disorders, rheumatology/musculoskeletal/neurological care, diabetes/metabolic disorders, skin/cancer care and general OPD. AIIA also has a dedicated Panchakarma department and publishes its own registration/appointment information.

Official AYUSH/CCRAS material states that CCRAS developed a Standardized Ayurvedic Case Taking Protocol (SACTP), with first-phase validation/reliability work for Kasa, Swasa and Jwara. CCRAS also publishes disease-specific Ayurveda clinical-method series, including respiratory and skin assessment methods.

Peer-reviewed literature similarly indicates that Ayurvedic diagnostic approaches are person-centred and require structured assessment, but the literature also highlights variability and the need to validate diagnostic tools rather than assuming an AI model is clinically authoritative.

Sources:
- https://www.aiia.gov.in/
- https://aiia.gov.in/news/patient-registration/
- https://aiia.gov.in/hospital/out-patient-department-opd/kayachikitsa-internal-medicine/
- https://aiia.gov.in/hospital/out-patient-department-opd/panchkarma/
- https://ayush.gov.in/resources/annualReport/Annual-report-2019-20_English.pdf
- https://ccras.nic.in/services/fundamental-research/

## 3. Product definition

### Product statement

MediKiosk is a patient-facing pre-consultation layer that:

1. registers or identifies the patient;
2. captures consent and preferred language;
3. performs immediate escalation for a patient who requests urgent help;
4. understands the patient's complaint in natural language;
5. selects an appropriate, clinician-defined case-taking pathway;
6. asks only the information-relevant follow-ups needed for doctor preparation;
7. captures documents when the patient has them;
8. produces a structured, provenance-preserving case summary;
9. routes the patient to the correct OPD/queue;
10. lets the doctor review, correct and confirm the intake.

The system does not autonomously diagnose disease, prescribe treatment, or determine emergency care.

## 4. Target architecture

Patient input
    -> language/voice/text normalization
    -> safety gate
    -> clinical concept extraction
    -> presentation/domain classification
    -> clinician-defined question policy
    -> adaptive follow-up loop
    -> sufficiency / stop rule
    -> document capture when relevant
    -> structured summary
    -> patient confirmation
    -> department/queue routing
    -> doctor review

LLM responsibilities:
- understand natural language;
- extract structured concepts;
- recognize synonyms and multilingual wording;
- classify presentation/domain with confidence;
- detect information already supplied in a patient answer;
- generate patient-friendly wording only within an approved question policy;
- summarize captured information.

Deterministic responsibilities:
- consent and patient identity state;
- emergency/urgent escalation state;
- allowed question domains;
- required minimum information;
- stop conditions;
- session transitions;
- department routing policy;
- data validation;
- audit trail.

## 5. Clinical safety model

Emergency should be a separate operational path, not a normal multi-turn interview.

Patient-facing behavior:

- Always-visible “I need help now” control.
- Immediate staff notification when activated.
- Stop normal intake.
- Display clear instruction to seek staff assistance.

Background safety net:
- Continue conservative safety screening of free-text answers.
- If a potential emergency is detected, stop the interview and escalate.
- Do not continue asking routine questions after escalation.

Staff-facing behavior:
- Emergency/urgent cases appear in a staff dashboard.
- No patient should wait in the ordinary OPD queue after an emergency escalation.

## 6. New-patient workflow

P01 Welcome
  -> preferred language
  -> New Patient

P02 Consent
  -> consent record

P03 Patient code/identity
  -> internal patient identifier

P04 Adaptive case-taking
  -> common intake
  -> presentation classification
  -> domain-specific follow-up
  -> sufficiency check

P06 Documents
  -> upload only if relevant/available
  -> OCR + confidence + correction

P07 Summary review
  -> patient checks high-level captured facts

P08 Confirmation/token
  -> department assignment
  -> queue token

P09 Waiting
  -> queue status

D01-D03
  -> doctor queue
  -> patient case
  -> doctor edit/confirmation

## 7. Returning-patient workflow

The current dead “Returning Patient” option must not remain decorative.

When implemented:

P01 Welcome
  -> Returning Patient

Identity retrieval
  -> patient code / hospital identifier / supported scan

Identity verification
  -> minimal verification before showing prior data

Previous visit snapshot
  -> last relevant OPD/visit
  -> prior complaint summary
  -> previous documents available
  -> doctor-reviewed information

Change-focused intake
  -> “What has changed since your last visit?”
  -> compare new complaint to prior case
  -> ask only missing/new information

Avoid re-asking stable information unless required for safety or the current clinical pathway.

Until the complete retrieval + verification + update pathway exists, hide the returning-patient entry point rather than shipping a dead screen.

## 8. Adaptive interview engine

### 8.1 Replace the fixed six-question concept

Current conceptual model:

REQUIRED_FIELDS_ORDER = [chief_complaint, onset, duration, severity, character, associated_symptoms]

Target model:

COMMON_INTAKE
  -> PRESENTATION_PROFILE
  -> QUESTION_POLICY
  -> ADAPTIVE_LOOP
  -> SUFFICIENCY_CHECK

The exact number of questions is not fixed.

### 8.2 Common intake

Minimum information should be limited to information needed for patient identification, safety, complaint framing and immediate routing.

Potential common concepts:
- chief concern / reason for visit;
- onset/course;
- severity or functional impact when relevant;
- immediately relevant associated symptoms;
- current medications/history when clinically relevant;
- documents/reports mentioned by patient.

Do not ask the patient the same concept twice when the first response already contains it.

### 8.3 Presentation profile

The system should classify the patient's presentation into a small number of operational domains, not pretend to classify every disease perfectly.

Initial domains for the pilot:
- musculoskeletal / pain;
- respiratory;
- digestive / gastrointestinal;
- dermatological;
- neurological;
- metabolic / endocrine;
- women's health;
- general/systemic;
- other / uncertain.

The domain classifier should return:
- domain;
- confidence;
- supporting concepts;
- unresolved concepts;
- safe next-question policy identifier.

When confidence is low, ask a clarifying question instead of inventing specificity.

### 8.4 Question policy

Each domain gets a clinician-defined question policy.

A policy contains:
- purpose;
- required concepts;
- optional concepts;
- triggers;
- follow-up dependencies;
- stop criteria;
- safety exceptions;
- language variants;
- provenance/version.

The LLM may choose phrasing within the policy, but it must not invent a new clinical branch outside the policy.

### 8.5 Stop condition

The interviewer stops when:
- minimum clinically useful information for the selected pathway is present;
- no high-priority unresolved branch is active;
- the patient has not introduced a new concern requiring further clarification;
- safety status is clear enough for this stage.

This means one case may need four questions and another may need eight or more. The system should be information-driven, not question-count-driven.

## 9. Ayurvedic layer

The judge's feedback specifically requests understanding of Ayurvedic terminology and the history required by Ayurvedic doctors.

This must be handled as a clinician-informed knowledge acquisition task.

### 9.1 First step: clinician interview

Get 30–60 minutes with at least one practicing BAMS/Ayurvedic doctor, ideally more than one if possible.

Ask:
- What do you ask in the first five minutes?
- What differs by OPD/specialty?
- Which history items are frequently missed by patients?
- Which terms should a digital intake recognize?
- Which findings belong to patient-reported history versus physical examination?
- Which Ayurvedic concepts are appropriate for patient questioning?
- Which concepts should only be assessed by the clinician?
- When does Prakriti matter in your intake?
- When do Agni, Koshta, Nidra, Ahara-Vihara, etc. become relevant?
- What would make an intake summary genuinely useful before consultation?
- Which questions are redundant or burdensome?

Capture the doctor's wording and examples before turning them into software rules.

### 9.2 Do not invent “validated” Ayurvedic questions

Use published CCRAS/AYUSH disease-specific methods as references, but label any unreviewed adaptation as provisional.

Do not claim that a generated AI question set is validated merely because it sounds Ayurvedic.

### 9.3 Patient-report vs clinician-exam boundary

Patient-facing kiosk can collect reported history and simple observable information.

Clinician-only assessments may include examination methods that require a practitioner, such as palpation/tactile findings or specialist examination. Do not simulate those as patient-reported certainty.

## 10. Language implementation

Do not ship a language selector that only changes visual selection.

Minimum real implementation:
- English + Hindi + Gujarati for the pilot;
- translated UI strings;
- translated question policy strings;
- language stored in session;
- prompt locale passed to the LLM;
- multilingual answer accepted;
- structured concepts normalized independent of display language;
- doctor-facing summary available in the hospital's preferred clinical language/format;
- original patient wording retained when useful.

Locale architecture:

session.language
  -> UI locale
  -> question template locale
  -> speech locale
  -> LLM prompt locale
  -> confirmation locale

Use stable translation keys, not scattered string literals.

Example:
patient_locale = gu
question_key = case_taking.musculoskeletal.onset
rendered_question = Gujarati translation

The question policy remains language-neutral; only its patient-facing representation changes.

## 11. Document capture

Keep OCR because medical document digitization is a core problem requirement.

Add a low-cost text concept:
mentioned_documents = [“blood test”, “previous prescription”]

This is supplemental, not a replacement for OCR.

Flow:
- patient mentions document;
- kiosk records the mention;
- optional prompt to upload if available;
- OCR extracts structured data;
- confidence gate;
- manual correction;
- preserve original extraction snapshot;
- closing reminder to show physical documents to doctor.

## 12. Patient identifier

Do not confuse privacy-sensitive global identifiers with a local hospital operational code.

Preferred local format from the current research plan:
AIIA-YYYYMM-NNNNN

Example:
AIIA-202609-00047

This requires concurrency-safe sequence generation and must never be used as the only authorization factor for accessing health records.

Before implementation verify the existing next_queue_token logic because the prefix contains multiple hyphens.

## 13. Department routing

AIIA publishes multiple specialty/care units. MediKiosk should route to a small, honest pilot set rather than pretend to implement every AIIA clinic.

Pilot routing examples:
- Kayachikitsa / General Medicine
- Musculoskeletal / Neurology
- Gastrointestinal / Liver
- Diabetes / Metabolic
- Skin
- Panchakarma
- General / unclear

Routing confidence should be explicit.

High confidence -> automatic operational routing within approved rules.
Low confidence -> General/Screening or staff selection.

Do not claim the current simple Sthaulya-vs-everything classifier is a full hospital routing system.

## 14. Doctor experience

Doctor should see:
- patient identity and visit type;
- patient language;
- current complaint;
- structured history;
- relevant Ayurvedic intake fields where available;
- unresolved/low-confidence items;
- documents and OCR provenance;
- original patient wording when needed;
- reason for routing;
- safety status;
- audit trail of edits.

The doctor can correct any AI-extracted value and confirm the intake.

AI-generated values must remain distinguishable from doctor-confirmed values.

## 15. Data model changes

Add concepts such as:
- presentation_domain;
- domain_confidence;
- active_question_policy;
- question_policy_version;
- collected_concepts;
- unresolved_concepts;
- mentioned_documents;
- visit_type with an actual implemented branch only when returning flow exists;
- provenance for structured values.

Each concept should carry provenance when feasible:
- patient_reported;
- llm_extracted;
- clinician_confirmed;
- document_ocr;
- manually_corrected.

## 16. Testing strategy

Do not only test whether the happy path reaches P07.

### Adaptive cases
Create deterministic synthetic scenarios for:
- headache presentation;
- knee/back pain;
- cough/breathlessness;
- abdominal/digestive complaint;
- skin complaint;
- diabetes/metabolic complaint;
- ambiguous complaint;
- multiple complaints.

For each scenario assert:
- domain selection;
- relevant questions are asked;
- irrelevant questions are avoided;
- a concept mentioned in the first answer is not asked again unnecessarily;
- stop condition works;
- doctor summary contains expected concepts.

### LLM resilience
Test:
- valid structured output;
- null field;
- empty field;
- malformed JSON;
- provider timeout;
- provider failure + fallback;
- low-confidence classification;
- conflicting information.

### Language
For English/Hindi/Gujarati:
- language changes UI;
- language changes questions;
- answer can be entered in selected language;
- normalized concepts remain stable;
- doctor summary is correct.

### Returning patient
Once built:
- patient lookup;
- identity verification;
- prior history retrieval;
- changed complaint branch;
- no accidental exposure of another patient's data.

### Emergency
Test:
- manual “I need help now” control;
- conversational safety backstop;
- immediate state interruption;
- no routine queue token after escalation;
- staff alert visibility.

## 17. Implementation sequence

### Phase 0 — Clinical discovery
BLOCKER for claiming Ayurvedic clinical validation.

1. Interview clinician(s).
2. Capture actual first-five-minute history.
3. Select pilot domains.
4. Convert clinician notes into versioned question policies.
5. Review policies with clinician again.

### Phase 1 — Adaptive engine

1. Replace fixed QUESTION_BANK progression with policy-driven state.
2. Add presentation profile.
3. Add concept memory so already-supplied information is reused.
4. Add adaptive follow-up selection.
5. Add stop condition.
6. Preserve deterministic safety and workflow controls.
7. Add synthetic-domain regression suite.

### Phase 2 — Real multilingual support

1. Introduce translation keys.
2. Implement en/hi/gu UI translations.
3. Translate pilot question policies.
4. Pass locale to LLM prompt.
5. Add multilingual E2E tests.

### Phase 3 — Emergency separation

1. Add always-visible urgent-help control.
2. Create staff escalation state.
3. Stop normal kiosk workflow after escalation.
4. Keep background safety screening as backstop.
5. Rework demo flow so emergency is shown as a separate operational path.

### Phase 4 — Returning patient

Only start after patient lookup and security design is clear.

1. Lookup by local patient identifier.
2. Verify identity.
3. Retrieve prior visit snapshot.
4. Ask what changed.
5. Run targeted follow-up.
6. Generate delta summary for doctor.

### Phase 5 — Clinical/document/queue integration

1. mentioned_documents.
2. document upload prompting.
3. OCR provenance.
4. department routing confidence.
5. patient confirmation.
6. doctor review.

### Phase 6 — Final product polish

Only after behavior is real:
- visual refinements;
- animations;
- demo script;
- README updates;
- final screenshots/recording.

## 18. Current repository reality check

The repository branch `release/sih-2026-demo` is currently at commit `ba4fcdecb1abe91d0967891d19ecc95468e2ad2c`.

The current GitHub copy still contains the original static six-question `QUESTION_BANK` and the old fallback behavior in `backend/routers/session.py`. Therefore, the post-judge local changes described in the leader's report have not yet been demonstrated as present in the GitHub branch inspected during this research pass.

That discrepancy must be resolved before assuming the repository is synchronized with local validation results.

## 19. Definition of “real” for this project

MediKiosk should not be considered complete merely because:
- an API returns 200;
- Gemini/Groq was called;
- six questions were answered;
- a summary appeared;
- the dashboard looks polished.

For this phase, “real” means:
- different presentations produce meaningfully different information requests;
- patient language changes actual interaction behavior;
- returning-patient behavior is either truly implemented or honestly hidden;
- emergency is a separate operational path;
- Ayurvedic terminology and history are informed by clinicians and grounded in published material;
- the doctor sees a useful, traceable pre-consultation record;
- the system fails safely when AI fails.

## 20. Judge-demo success criteria

A judge should be able to test three patients:

Patient A:
“Severe knee pain when climbing stairs for six months.”

Patient B:
“Cough with breathlessness and wheezing for three days.”

Patient C:
“Itchy red patches on both arms after starting a new cosmetic.”

The system should not ask the same follow-up sequence for all three.

The judge should also be able to change the language and immediately observe real language behavior, not only a selection highlight.

A returning-patient demo should either work end-to-end or not be shown as an available option.

An emergency demonstration should show immediate staff escalation rather than a patient completing a routine questionnaire.

## 21. Non-goals

Do not build:
- autonomous Ayurvedic diagnosis;
- autonomous treatment selection;
- prescription generation for patients;
- fake validation claims;
- dozens of disease-specific hardcoded branches without clinical governance;
- a generic chatbot that bypasses the deterministic workflow;
- a visually complete but behaviorally empty returning-patient journey.

## 22. Immediate next action

The first coding task is NOT to rewrite P04.

The first real development task is to implement the data and engine foundations required for adaptive case-taking while keeping the current UI stable:

1. clinician-policy schema;
2. presentation profile schema;
3. concept memory;
4. question-policy engine;
5. adaptive state transition API;
6. synthetic multi-domain test fixtures;
7. English pilot implementation only until multilingual behavior is ready;
8. explicit feature flags for unfinished returning-patient functionality.

After that foundation passes tests, connect the existing P04 visual UI to the new adaptive engine.

