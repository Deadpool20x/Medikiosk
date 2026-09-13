# MediKiosk Adaptive Conversational Interview Engine

## Architectural Specification & Clinical Governance Guide

> **Clinical Status Notice**: This engine represents a **Provisional Pilot Intake Framework pending Ayurvedic Clinician Review**. It is designed strictly for pre-consultation intake structuring and does NOT diagnose, treat, or make autonomous medical decisions.

---

## 1. Executive Summary & Design Rationale

Traditional clinical intake kiosks suffer from two polar failure modes:
1. **Rigid Static Questionnaires**: Asking fixed sequences of generic questions (e.g. onset, duration, severity) regardless of organ system or patient context, frustrating patients and generating sparse clinical summaries.
2. **Unconstrained Autonomous LLMs**: Allowing conversational AI models to freely interrogate patients, which introduces hallucinations, clinical scope creep, premature diagnostic proclamations, unsafe advice, repetitive loops, and unbound session lengths.

MediKiosk solves this tension through a **Dual-Architecture Conversational Model**:
- **The LLM acts as the conversational interviewer**: It receives bounded historical context, comprehends patient natural language answers across multiple Indian languages, extracts clinical concepts, identifies missing information against structured clinical guidelines, and generates natural follow-up questions.
- **The deterministic local engine acts as the authoritative policy validator, clinical gatekeeper, and fallback**: Every single output proposed by the LLM must pass 9 rigorous deterministic safety and policy checks before reaching the patient's screen. If any check fails or if the LLM provider fails, the system automatically falls back to curated deterministic questions without stalling.

---

## 2. Target Behavioral Loop

```
                     +---------------------------------------------------+
                     |           Patient Submits Natural Answer          |
                     +---------------------------------------------------+
                                               |
                                               v
                     +---------------------------------------------------+
                     |       1. Synchronous Red-Flag Safety Screen       |
                     +---------------------------------------------------+
                                    |                      |
                            [Red Flag Detected]    [No Red Flag]
                                    |                      |
                                    v                      v
                     +-------------------------+ +-----------------------------------+
                     | P0 Freeze & Escalation  | | 2. Assemble Bounded Context:      |
                     | Emergency Token (EM-xxx)| |    - Patient Profile (age, sex)   |
                     | Red-Flag Alert Screen   | |    - Chosen Language (en, hi, gu) |
                     +-------------------------+ |    - Prior Conversation Turns     |
                                                 |    - Collected Concepts & Domain  |
                                                 |    - Missing Concepts Guidance    |
                                                 +-----------------------------------+
                                                                   |
                                                                   v
                                                 +-----------------------------------+
                                                 | 3. LLM Natural Interpretation &   |
                                                 |    Follow-Up Proposal:            |
                                                 |    - CaseUpdate (concepts, domain)|
                                                 |    - NextQuestion (text, target)  |
                                                 |    - Status (continue/sufficient) |
                                                 +-----------------------------------+
                                                                   |
                                                                   v
                                                 +-----------------------------------+
                                                 | 4. Deterministic Policy Validator |
                                                 |    (9 Authoritative Checks)       |
                                                 +-----------------------------------+
                                                      |                       |
                                                 [PASSED]                  [FAILED]
                                                      |                       |
                                                      v                       v
                     +-----------------------------------+  +-----------------------------------+
                     | Accept LLM Question               |  | Reject LLM Question               |
                     | Format in patient's language      |  | Substitute Curated Local Fallback |
                     +-----------------------------------+  | Set needs_review = True           |
                                      \                     +-----------------------------------+
                                       \                                     /
                                        v                                   v
                                    +-------------------------------------------+
                                    | 5. Independent Sufficiency Check          |
                                    |    - Verify all mandatory concepts exist  |
                                    |    - Check Hard Cap (MAX_TURNS = 5)       |
                                    +-------------------------------------------+
                                          |                               |
                                  [Not Sufficient]                   [Sufficient]
                                          |                               |
                                          v                               v
                     +-----------------------------------+  +-----------------------------------+
                     | Display Next Question in P04      |  | Transition Interview to Complete  |
                     | Increment question counter        |  | Bridge concepts to Legacy HPI     |
                     | Persist state to SQLite (WAL)     |  | Proceed to Document Upload / P05  |
                     +-----------------------------------+  +-----------------------------------+
```

---

## 3. The 9 Deterministic Policy Checks

Before any LLM proposal is shown to a patient, `validate_llm_proposal()` evaluates the following criteria:

| Check | Rule | Rationale | Failure Action |
| :--- | :--- | :--- | :--- |
| **A. Emergency Safety** | Answer screened by `evaluate_safety` before LLM invocation | Immediate patient safety takes precedence over questioning | Immediate P0 session freeze, alert display |
| **B. Clinical Scope Ban** | Prohibits diagnostic claims (`"you have osteoarthritis"`, `"it appears you have GERD"`, `"nidan"`) and treatment recommendations (`"you should take"`, `"prescribing"`, `"undergo panchakarma"`) | Intake kiosks must NEVER practice medicine or dispense prescriptions | Question rejected, logged to audit |
| **C. Concept Relevance** | Target concept must belong to `CORE_CLINICAL_CONCEPTS` or domain's `relevant_concepts` | Prevents the LLM from asking medically irrelevant or bizarre questions | Question rejected |
| **D. No Concept Re-Asking** | Target concept must not already exist with non-empty value in `collected_concepts` | Prevents patient frustration from answering redundant questions | Question rejected |
| **E. Turn Limit Enforcement** | Total adaptive turns must not exceed `MAX_ADAPTIVE_QUESTIONS = 5` | Strict kiosk throughput guarantee; prevents interview fatigue | Interview marked complete |
| **F. Text Length & Artifacts** | Length must be 5–350 characters; must not contain JSON, code blocks, or braces | Prevents corrupted model outputs from appearing in UI | Question rejected |
| **G. No Semantic Repetition** | Proposal text must not be substantially identical (>85% token overlap) to any prior asked question | Protects against LLM loops | Question rejected |
| **H. Concept Frequency Cap** | Target concept must not have been previously asked in `asked_concepts` | Prevents model from repeatedly querying the same missing concept | Question rejected |
| **I. Independent Sufficiency** | LLM `status="sufficient"` is ignored unless local engine verifies all domain mandatory concepts are non-empty | Model cannot truncate intake before essential clinical baseline is gathered | Intake forced to continue |

---

## 4. Pilot Domain Pathways

The system defines 6 clinical knowledge domains grounded in classical intake frameworks:

### 4.1 Musculoskeletal & Joint Presentation (`musculoskeletal`)
- **Triggers**: Back pain, lower back, knee, joint, shoulder, neck pain, stiffness, sprain, swelling, arthritis, sciatica, sandhigata, amavata, kati, janu, greeva.
- **Mandatory Concepts**: `primary_symptom`, `site`, `duration`.
- **Relevant Concepts**: `laterality`, `severity`, `character`, `aggravating_factors`, `relieving_factors`, `stiffness_or_swelling`, `functional_limitation`.
- **Clinical Evidence Source**: *Charaka Samhita Chikitsa Sthana Vatavyadhi Adhyaya* (Pilot intake framework, non-diagnostic).

### 4.2 Respiratory & Pranavaha Presentation (`respiratory`)
- **Triggers**: Cough, cold, congestion, runny nose, sore throat, sneezing, phlegm, mucus, blocked nose, sinus, kasa, shwasa, pratishyaya.
- **Mandatory Concepts**: `primary_symptom`, `duration`, `cough_character`.
- **Relevant Concepts**: `onset`, `severity`, `associated_symptoms`, `triggers`, `relieving_factors`.
- **Clinical Evidence Source**: *Charaka Samhita Chikitsa Sthana Kasa/Shwasa Adhyaya* (Pilot intake framework, non-diagnostic).

### 4.3 Digestive & Annavaha Presentation (`digestive`)
- **Triggers**: Stomach pain, acidity, gas, bloating, constipation, diarrhea, loose motion, heartburn, indigestion, nausea, vomiting, belching, ajirna, agnimandya, amlapitta, chardi.
- **Mandatory Concepts**: `primary_symptom`, `duration`, `food_relationship`.
- **Relevant Concepts**: `bowel_habits`, `severity`, `associated_symptoms`, `relieving_factors`.
- **Clinical Evidence Source**: *Charaka Samhita Grahani/Amlapitta Nidana* (Pilot intake framework, non-diagnostic).

### 4.4 Dermatological Presentation (`dermatological`)
- **Triggers**: Skin rash, itching, boil, eczema, red patch, psoriasis, dry skin, blister, pimples, acne, ringworm, kushta, kandu, twak.
- **Mandatory Concepts**: `primary_symptom`, `site`, `duration`.
- **Relevant Concepts**: `itching_severity`, `triggers`, `associated_symptoms`, `relieving_factors`.
- **Clinical Evidence Source**: *Charaka Samhita Kushta Nidana* (Pilot intake framework, non-diagnostic).

### 4.5 Metabolic & General Wellness (`metabolic`)
- **Triggers**: Diabetes, sugar, high BP, thyroid, fatigue, weight gain, weight loss, excessive thirst, weakness, prameha, sthaulya, karshya, medoroga.
- **Mandatory Concepts**: `primary_symptom`, `duration`, `energy_and_thirst`.
- **Relevant Concepts**: `weight_changes`, `associated_symptoms`, `severity`, `previous_treatment`, `relevant_history`.
- **Clinical Evidence Source**: *Charaka Samhita Prameha/Sthaulya Adhyaya* (Pilot intake framework, non-diagnostic).

### 4.6 General Presentation (`general`)
- **Triggers**: Catch-all for non-specific, constitutional, or multi-system complaints.
- **Mandatory Concepts**: `primary_symptom`, `duration`.
- **Relevant Concepts**: `site`, `onset`, `severity`, `associated_symptoms`, `triggers`, `relieving_factors`.
- **Clinical Evidence Source**: *Ayurvedic Clinical Intake Methodology Standard* (Pilot intake framework, non-diagnostic).

---

## 5. Multilingual Question Generation

MediKiosk generates conversational questions directly in the patient's selected language (`en`, `hi`, `gu`):
- **Prompt Directive**: When language is `hi` (Hindi) or `gu` (Gujarati), the LLM is instructed:
  `"Generate the next_question text in clean, conversational Hindi (using Devanagari script) / Gujarati (using Gujarati script). The question must sound natural, compassionate, and culturally appropriate, not robotic or machine-translated."`
- **Fallback Guarantee**: Every domain maintains pre-translated, verified fallback question tables in all three languages. If the LLM generates English when Hindi was requested, or if generation fails, the deterministic fallback immediately provides the correct vernacular string.

---

## 6. Resilience & Graceful Fallback Chain

To maintain 100% kiosk uptime, the engine implements a tiered failover topology:

1. **Primary LLM Provider**: High-performance primary model (e.g. Groq `llama-3.3-70b-versatile`).
2. **Secondary Fallback Provider**: High-throughput fallback model (e.g. Cerebras `llama-3.3-70b`).
3. **Local Deterministic Fallback**: If all network or provider calls fail, or if proposed questions fail validator checks, `get_fallback_question()` queries the local knowledge table for the next highest-priority missing concept.
4. **No Stall Invariant**: When an LLM returns malformed JSON or empty dictionaries, the patient's raw response is captured, `needs_review` is flagged, and the deterministic fallback advances the interview to the next logical concept. The kiosk never stalls on an empty textarea.

---

## 7. Zero UI Redesign & Legacy Bridging

The conversational engine preserves the frozen Stitch UI layout without alterations:
- **Single Question Display**: P04 continues displaying a single active question string (`session.current_pending_question`) and a standard textarea.
- **Bridge Function**: `bridge_concepts_to_legacy()` continuously maps collected concepts (`primary_symptom`, `site`, `duration`, `severity`, `character`, `associated_symptoms`) into standard HPI schema fields.
- **Doctor Workspace Unaffected**: Doctors in D01-D04 see cleanly categorized clinical entities, audit indicators (`needs_review`), and complete answer histories.
