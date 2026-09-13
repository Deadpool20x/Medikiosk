# MediKiosk Phase 1: Adaptive Case-Taking Engine Foundation - Summary

## Objective
Replace the current static six-question interview architecture with a reusable adaptive case-taking engine foundation.

## Files Changed

### New Files
1. `backend/rules/adaptive_interview.py` - Contains the adaptive interview engine, presentation domains, question policies, and helper functions.
2. `backend/tests/test_adaptive_interview.py` - Comprehensive tests for the adaptive engine.

### Modified Files
1. `backend/routers/session.py` - Updated to conditionally use the adaptive engine based on session parameters and to expose adaptive-specific fields in the session response.
2. `backend/db.py` - The `init_db` function already included the new columns (presentation_domain, collected_concepts_json, etc.) so no change was needed, but we verified the schema is up-to-date.

## Architecture Implemented

### Core Components
- **PresentationProfile**: Defines a clinical domain (e.g., musculoskeletal, respiratory) with:
  - `domain_id`: Unique identifier
  - `display_name`: Human-readable name
  - `triggers`: Keywords that suggest this domain
  - `required_concepts`: Concepts that must be collected for the interview to be considered sufficient
  - `question_sequence`: Ordered list of `QuestionPolicy` objects
  - `max_questions`: Maximum number of questions to ask in this domain (default 5)
  - `min_concepts`: Minimum number of distinct concepts to collect before considering the interview complete

- **QuestionPolicy**: Represents a single question in the interview flow:
  - `concept_key`: The concept this question aims to elicit
  - `question_text`: The actual question to ask the patient
  - `priority`: Lower numbers are asked first
  - `required`: Whether the concept is required for sufficiency
  - `legacy_field`: Maps the concept to the existing session schema (e.g., `primary_symptom` -> `chief_complaint`)

### Engine Logic
1. **Safety First**: Before any adaptive processing, the existing safety rules are executed. If a safety flag is triggered, the interview halts and the session is marked as safety_flagged.
2. **Domain Classification**: On the first turn, the engine classifies the patient's presentation into one of the predefined domains (or general/unclear) using keyword matching on the patient's answer and chief complaint.
3. **Concept Extraction**: 
   - The LLM is used to extract structured concepts from the patient's answer (with fallback to rule-based extraction).
   - The engine normalizes concept names (e.g., "complaint" -> "primary_symptom").
   - The engine ensures that the concept corresponding to the current question is marked as collected (using the raw answer as a fallback if the LLM extraction fails).
4. **Question Selection**: 
   - The deterministic engine selects the next question based on:
     - The current domain's question sequence (sorted by priority)
     - Concepts already collected (from LLM extraction or rule-based fallback)
     - Questions already asked
     - The engine skips questions for which a usable value already exists.
5. **Sufficiency and Stop Conditions**:
   - The interview stops when:
     - All required concepts for the domain are collected.
     - The number of questions asked reaches `max_questions` for the domain.
     - The engine determines there are no more relevant questions to ask (i.e., `select_next_question` returns None).
   - The LLM is never allowed to decide sufficiency or completion; this is strictly deterministic.
6. **Backward Compatibility**: 
   - Adaptive concepts are mirrored into the legacy session fields (chief_complaint, history_of_present_illness) so that existing components (D02/D03, department routing, summary screen) continue to work unchanged.
   - The session model includes new fields for adaptive data but retains all existing fields.

### Key Features Implemented from Requirements
- **First-Turn Multi-Concept Extraction**: The first patient answer can contain multiple pieces of information (e.g., "Severe lower back pain for three days, worse when I bend.") and the engine will extract and mark all relevant concepts as collected.
- **Deterministic Engine Authority**: The engine, not the LLM, controls workflow progression, question selection, and sufficiency.
- **Safety Authority**: Safety checks run before adaptive processing and are independent of the LLM.
- **Question Policy Structure**: Questions are represented as structured policy objects, not a global flat list.
- **Multi-Disease Behavior**: Pilot pathways for musculoskeletal, respiratory, digestive, dermatological, metabolic, and general domains.
- **Document Mentions**: Added support for detecting simple document mentions (e.g., "I have an old blood report.") and storing them in `mentioned_documents`.
- **LLM Contract**: The LLM returns a structured extraction with domain, concepts, confidence, and provider. On failure, the engine falls back to rule-based extraction and continues.
- **Ayurveda Boundary**: The engine is strictly an intake and structured history-gathering tool; it does not attempt autonomous Ayurvedic diagnosis or treatment recommendations.
- **Test Coverage**: Added tests for:
  - Domain-specific flows (musculoskeletal, respiratory, digestive)
  - General domain fallback
  - Question limit enforcement
  - Multi-concept extraction and skipping already collected concepts
  - Safety blocking adaptive progression
  - Preservation of existing session data (backward compatibility)

## Example Patient Flows (Before vs After)

### Before (Static Engine)
Regardless of the patient's answer, the interview always followed the same six questions in order:
1. Chief Complaint
2. Onset
3. Duration
4. Severity
5. Character
6. Associated Symptoms

### After (Adaptive Engine)
The question sequence adapts to the patient's presentation:

**Example 1: Musculoskeletal**
Patient: "I have severe lower back pain for 2 days."
- Extracts: primary_symptom="lower back pain", site="lower back", duration="2 days"
- Skips questions for primary_symptom, site, and duration (already collected)
- Next question: onset (if not extracted) or aggravating_factors (based on priority)
- Interview may complete after 3-4 questions if sufficient concepts are collected.

**Example 2: Respiratory**
Patient: "I have been having a dry cough for 3 days."
- Extracts: primary_symptom="cough", cough_character="dry", duration="3 days"
- Skips questions for primary_symptom, cough_character, duration
- Next question: onset or associated_symptoms
- Interview completes after collecting required concepts (primary_symptom, duration, cough_character).

**Example 3: Unclear Symptoms**
Patient: "I just feel weird and tired."
- No clear domain detected -> falls back to general domain
- Asks: primary_symptom, onset, duration, severity, character, associated_symptoms (in order)
- Interview completes after collecting all six required concepts (or hitting max_questions).

## Test Results
- All existing audit tests pass (9/9) - confirming no regression in normal patient flow, safety, OCR, token generation, doctor workflow, etc.
- All new adaptive interview tests pass (5/5) - verifying the adaptive engine works as intended for various domains and edge cases.

## Next Steps for Phase 2
1. **Frontend Integration**: Create or modify frontend components (likely a new P09 or enhanced P04) to consume the adaptive engine's API response (which includes current question, presentation domain, progress, etc.).
2. **Clinical Refinement**: Work with Ayurvedic practitioners to validate and refine the clinical concepts, question policies, and domain definitions.
3. **Safety Integration**: Ensure that the adaptive engine's sufficiency and stop conditions are clinically appropriate.
4. **Performance Optimization**: Consider caching or optimizing the rule-based extraction for better performance.
5. **Documentation Update**: Expand `docs/ARCHITECTURE.md` and `docs/TESTING.md` with details of the adaptive engine.

## Verification of Regression Requirements
- [x] Existing doctor workflow still works (verified by audit)
- [x] OCR still works (verified by audit)
- [x] Safety still works (verified by audit)
- [x] Token/queue still works (verified by audit)
- [x] Normal patient flow still works (verified by audit)
- [x] No data is lost (backward compatibility maintained)
- [x] Existing tests do not regress unexpectedly (audit passes)

## Proof of Success
The proof of success is not merely that the API returns 200, but that:
- DIFFERENT PATIENT PRESENTATIONS
        ↓
- DIFFERENT EXTRACTED CONCEPTS
        ↓
- DIFFERENT QUESTION PATHS
        ↓
- DIFFERENT STRUCTURED CASES
while the deterministic safety/workflow boundaries remain intact.

We have demonstrated this with the three synthetic patient journeys (musculoskeletal, respiratory, digestive) in our tests, each producing different question sequences and different structured concepts collected.