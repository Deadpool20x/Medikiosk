---
version: "alpha"
revision: "1.0"
name: "MediKiosk Stitch Design Brief"
description: "Source-constrained design context for Google Stitch. Patient: Cal.com + Intercom + limited Notion. Doctor: Linear navigation/density + Airtable data structure + limited Notion grouping."

colors:
  patient-canvas: "#FFFFFF"
  patient-surface-soft: "#F8F9FA"
  patient-ink: "#111111"
  patient-body: "#374151"
  patient-muted: "#6B7280"
  patient-hairline: "#E5E7EB"
  patient-primary: "#111111"
  patient-focus: "#3B82F6"
  doctor-canvas: "#F8FAFC"
  doctor-surface: "#FFFFFF"
  doctor-ink: "#181D26"
  doctor-body: "#333840"
  doctor-hairline: "#DDDDDD"
  doctor-sidebar: "#181D26"
  doctor-sidebar-text: "#F7F8F8"
  doctor-accent: "#5E6AD2"
  link: "#1B61C9"
  success: "#10B981"
  success-soft: "#ECFDF5"
  warning: "#F59E0B"
  warning-soft: "#FFFBEB"
  danger: "#EF4444"
  danger-soft: "#FEF2F2"

typography:
  display:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "40px"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-1px"
  patient-question:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.5px"
  doctor-title:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.35
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  compact-body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.4

rounded:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  pill: "9999px"

spacing:
  1: "4px"
  2: "8px"
  3: "12px"
  4: "16px"
  6: "24px"
  8: "32px"
  12: "48px"
  16: "64px"
  24: "96px"

components:
  patient-primary-button:
    backgroundColor: "{colors.patient-primary}"
    textColor: "{colors.patient-canvas}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    height: "48px"
    padding: "0 20px"
  patient-secondary-button:
    backgroundColor: "{colors.patient-canvas}"
    textColor: "{colors.patient-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    height: "48px"
    padding: "0 20px"
  doctor-primary-button:
    backgroundColor: "{colors.doctor-ink}"
    textColor: "{colors.patient-canvas}"
    typography: "{typography.compact-body}"
    rounded: "{rounded.lg}"
    height: "40px"
    padding: "0 16px"
  patient-input:
    backgroundColor: "{colors.patient-canvas}"
    textColor: "{colors.patient-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    height: "48px"
    padding: "0 16px"
  doctor-table-row:
    backgroundColor: "{colors.doctor-surface}"
    textColor: "{colors.doctor-body}"
    typography: "{typography.compact-body}"
    padding: "12px 16px"
  status-success:
    backgroundColor: "{colors.success-soft}"
    textColor: "{colors.success}"
    rounded: "{rounded.pill}"
    padding: "4px 8px"
  status-warning:
    backgroundColor: "{colors.warning-soft}"
    textColor: "{colors.warning}"
    rounded: "{rounded.pill}"
    padding: "4px 8px"
  status-danger:
    backgroundColor: "{colors.danger-soft}"
    textColor: "{colors.danger}"
    rounded: "{rounded.pill}"
    padding: "4px 8px"
---

# MediKiosk — Stitch Visual Design Contract

## 1. Purpose and authority

This document is the visual and product-context source for **Google Stitch**.

It is a **Stitch generation brief and implementation reference**, not a claim that every described workflow is already live in the application.

Precedence:

1. `MediKiosk-Implementation-Spec-v4.md` — product scope, sequencing, technical truth.
2. This file — visual direction, screen scope, design constraints.
3. The root `DESIGN.md` — production implementation token contract after a Stitch screen is approved.
4. Generated Stitch screens — visual references, never automatic production code.

Before generating any screen, read this entire file.

## 2. Product context

MediKiosk is an AI-assisted pre-consultation clinical case-taking platform for an Ayurvedic OPD.

It helps patients record history before consultation and gives doctors an editable, structured case view. It is **not** an autonomous doctor, diagnosis engine, treatment system, or production ABDM integration.

MediKiosk may eventually:

- collect patient history;
- guide patients through deterministic questions;
- support voice and touch interaction;
- run red-flag checking;
- process uploaded prescriptions or reports;
- create a structured case summary;
- route an eligible patient to a department;
- generate a queue token; and
- give a doctor a reviewable, editable case.

The doctor makes every final clinical decision.

### Implementation truth rule

This brief is allowed to design future workflow states. A rendered screen must **not** imply that its backend feature is live until it is implemented and verified.

For early prototype screens:

- label patient/case examples as **Synthetic demo**;
- label AI output as **extracted information** or **draft for doctor review**;
- say **extraction confidence**, never diagnosis confidence or medical certainty;
- do not present voice controls as active recording unless speech support is connected;
- do not claim automated routing, red-flag detection, OCR, or queue issuance is active before it is verified.

## 3. Core flow

```text
PATIENT
  ↓
Language
  ↓
New / Returning
  ↓
Consent
  ↓
Patient Code
  ↓
Guided interview
  ├── Chief Complaint
  ├── Symptom / HPI
  ├── Medical History
  ├── Drug / Allergy
  ├── Family / Personal History
  └── Ayurvedic Assessment
  ↓
Red-flag check
  ├── Red flag → Emergency operational queue
  │              → no normal token
  │              → no normal department queue
  └── Safe → department classification
             ↓
       Kayachikitsa / Panchakarma
             ↓
       Document Upload → Extraction → Review
             ↓
       Structured Summary → Patient Confirmation
             ↓
       Token → Department Queue → Doctor Review → Consultation
```

The patient experience must feel like **one natural guided conversation**, even though the application maintains deterministic internal stages.

## 4. Source systems and the non-collage rule

This design is derived from public `getdesign.md` analyses of **Cal.com, Intercom, Airtable, Linear, and Notion**.

They are references for documented patterns, hierarchy, density, and interaction behavior—not brand assets to copy.

Never use a source company’s:

- logo;
- wordmark;
- illustration;
- proprietary font;
- exact page composition; or
- whole branded palette.

### Font rule

Use **Inter** throughout MediKiosk. Do not attempt to ship Cal Sans, Saans, Haas Grotesk, Linear fonts, or Notion Sans without explicit licensing and availability confirmation.

### Palette rule

Use the named MediKiosk role tokens in YAML. These values are selected from compatible source roles, but they form an original role-based product system.

Do not mix raw source palettes inside a single surface.

### Surface recipes

| Surface | Primary source | Secondary source | Limited support source | What to take |
|---|---|---|---|---|
| Patient kiosk | Cal.com | Intercom | Notion | Neutral canvas, black primary action, generous whitespace, deliberate progression; conversational message/input hierarchy; calm summary grouping. |
| Doctor workspace | Linear | Airtable | Notion | Dark navigation and precise scanning; light structured table/queue; readable grouped case sections. |
| Emergency workspace | Linear | Airtable | — | Dense operational layout; clear alert rows; restrained semantic warning/danger states. |

## 5. Adopted visual recipes

### 5.1 Patient kiosk — Cal.com first, Intercom only for conversation

Use:

- white or near-white canvas;
- near-black primary actions;
- 8px control radius and 12px content-card radius;
- clear step progression;
- generous whitespace;
- thin neutral hairlines;
- one dominant action per screen;
- short human prompts and a limited conversation history.

Do not use:

- Cal.com logos or visual copies;
- Intercom cream/orange as the brand palette;
- Notion purple as patient primary;
- Linear’s dark canvas;
- generic ChatGPT message-column UI;
- decorative medical stock images or giant illustrations.

### 5.2 Doctor workspace — Linear navigation, Airtable data area

Use:

- dark doctor navigation/sidebar only (`doctor-sidebar`);
- white/light workspace canvas and table surfaces;
- compact 14px table data, clear metadata, hairline dividers;
- one quiet accent for selected state/focus;
- Airtable-like structured rows and queue organization;
- Notion-like grouped case sections for readable review;
- no chart-first analytics dashboard.

Do not use:

- a full dark Linear interface with white Airtable cards scattered inside it;
- a rainbow category system;
- a large card for every single clinical field;
- Linear or Airtable logos/brand marks.

### 5.3 Emergency workspace — calm urgency

Use the doctor shell with a dedicated emergency list.

Priority order:

```text
Alert state → Patient code → Complaint fragment → Timestamp → Staff action
```

Use a semantic danger or warning label plus text. The alert must never rely on color alone.

Do not use glowing red effects, flashing states, siren graphics, dramatic illustrations, or continuous animation.

## 6. Product content

### Patient communication

Use direct plain language:

- “What is the main problem you are experiencing?”
- “How long have you had this problem?”
- “Please review the information before continuing.”

Avoid:

- “Enter chief complaint.”
- “Specify symptom duration.”
- “The AI has diagnosed…”
- “Your diagnosis confidence is…”

### Doctor communication

The doctor experience may use structured clinical terms and Ayurvedic assessment labels. Every AI-derived/extracted field must show source and extraction confidence and remain editable.

### Ayurvedic content inventory

Support the following structured categories:

- Prakriti
- Agni
- Koshtha
- Nidana
- Ahara-Vihara

Defined issue examples:

- Sandhivata
- Agnimandya
- Kushtha
- Pratishyaya
- Jwara
- Katishoola
- Shirahshoola
- Arsha
- Prameha
- Sthaulya

Routing visual rule:

```text
All listed issues except Sthaulya → Kayachikitsa
Sthaulya → Panchakarma
Any red flag → Emergency operational dashboard
```

This rule does not permit a patient-facing screen to claim autonomous clinical diagnosis.

## 7. Required screens

### Patient

| ID | Screen | Required design content |
|---|---|---|
| P01 | Welcome / Language | MediKiosk identity; visible language selector; New Patient primary action; Returning Patient secondary action; help and privacy reassurance. |
| P02 | Consent | concise explanation; clear consent choice; continue; plain-language data use statement. |
| P03 | Patient Code | generated/retrieved patient code; clear explanation; continue. |
| P04 | Guided Interview | step progress; one current question; short conversation context; text input; optional voice affordance; one primary action. |
| P05 | Red-Flag / Emergency Redirect | restrained urgent instruction; clear staff action; explicit no-token/no-normal-queue state. |
| P06 | Document Upload | upload/skip; supported types/size; preview; processing; extraction state; recovery. |
| P07 | Summary Review | chief complaint; history; Ayurvedic section; document extraction; source; extraction confidence; editable correction. |
| P08 | Confirmation / Token | confirmation; department; token; explicit clinician-review reassurance. |
| P09 | Waiting / Completion | token; department; sparse waiting message; new-patient/reset action where appropriate. |

### Doctor

| ID | Screen | Required design content |
|---|---|---|
| D01 | Kayachikitsa Queue | department; token; patient code; complaint; status; time; queue action. |
| D02 | Kayachikitsa Patient Case | code; complaint; history; Ayurvedic assessment; documents; extracted values; source; extraction confidence. |
| D03 | Kayachikitsa Review / Edit | inline or panel editing; original extracted value; corrected value; source; extraction confidence; save/confirm. |
| D04 | Emergency Dashboard | active alerts; patient code; complaint fragment; timestamp; alert state; staff action. |

Panchakarma reuses D01/D02/D03 exactly. Only department configuration/data differs.

## 8. Component system

Create reusable variants for:

- kiosk header/language control;
- patient and doctor primary/secondary buttons;
- icon buttons;
- progress indicator;
- textarea/text input;
- optional voice control and unavailable state;
- conversational message and question block;
- choice/segmented control;
- upload area and upload recovery state;
- document preview;
- extraction row;
- confidence badge;
- status badge;
- queue row;
- grouped case section;
- editable field;
- summary card;
- emergency alert row;
- empty, loading, error, and success states;
- token display.

### Required component states

Every interactive component must define default, hover, focus-visible, disabled, loading, error, and success/selected states where relevant.

- Patient controls: minimum 48×48px touch targets.
- A visual state must have text, icon, or pattern support—not color alone.
- Long patient names, complaint text, and filenames must wrap or use deliberate truncation without layout overflow.

## 9. Information hierarchy

### Patient

```text
Question
  ↓
Supporting explanation
  ↓
Patient input
  ↓
Single primary action
```

The patient must never face doctor-dashboard density or multiple competing primary CTAs.

### Doctor

```text
Patient / Token
  ↓
Chief Complaint
  ↓
Important History
  ↓
Ayurvedic Assessment
  ↓
Documents and extracted information
  ↓
Source / extraction confidence
  ↓
Edit / confirm
```

Doctor detail should support fast scanning; it must not lead with one large AI-generated paragraph.

## 10. Accessibility and responsive requirements

### Accessibility

- Normal text targets 4.5:1 contrast.
- Important state is never color-only.
- All keyboard controls show visible focus.
- Patient controls are at least 48×48px.
- Patient body text never falls below 16px.
- Respect `prefers-reduced-motion`.
- Voice must never be the only input/recovery path.

### Responsive behavior

Patient: kiosk/desktop, tablet, and narrow mobile.

Doctor: desktop and tablet first.

At narrower widths:

- patient actions stack safely;
- patient content stays in one readable column;
- doctor sidebar becomes a navigation drawer or collapses;
- tables turn into structured case rows/cards when their columns cannot fit;
- document split views stack with original document before extracted fields;
- no horizontal page scrolling from text, chips, names, or filenames.

## 11. Anti-patterns

Do not generate:

- a generic centered AI chatbot landing page;
- a template-like hospital dashboard;
- glassmorphism;
- neon gradients;
- purple AI glow;
- random medical stock imagery;
- decorative 3D objects;
- excessive shadows;
- excessive rounded cards;
- a floating card per tiny field;
- chart-heavy analytics where a queue/table is needed;
- copied logos, illustrations, or brand layouts;
- raw provider/server errors;
- fake diagnosis/treatment certainty;
- fake live feature claims.

The result must look like an original MediKiosk product grounded in proven interface patterns—not a collage of the reference products.

## 12. Stitch generation method

Do not generate the entire interface in one request.

Use this sequence:

1. Create the MediKiosk Stitch project.
2. Attach/read this full file as project context.
3. Generate **P01 Welcome / Language** only.
4. Check it against Sections 4, 5.1, 7, 9, 10, and 11.
5. Correct it until it passes.
6. Generate P02–P09 one screen at a time, carrying forward the approved patient system.
7. Generate D01 next, establish the doctor shell and queue system.
8. Generate D02 and D03 using D01’s approved shell/components.
9. Generate D04 using the same doctor shell and restrained emergency treatment.
10. Only then export/implement approved screens.

### Screen acceptance gate

For each generated screen verify:

- source mapping is visible in behavior, not copied identity;
- hierarchy is clear;
- no generic AI-healthcare pattern has appeared;
- patient/doctor/emergency context is unmistakable;
- no unavailable backend feature is presented as live;
- text can be read fully at its target viewport;
- responsive behavior is specified;
- components reuse the established surface recipe.

## 13. Source provenance

Visual references:

- Cal.com — clean controls, progression, whitespace.
- Intercom — conversational hierarchy, friendly input/message relationship.
- Airtable — structured data, queues, status information.
- Linear — professional scanning density, restrained workspace navigation.
- Notion — calm information grouping and summary organization.

These are public-pattern analyses from getdesign.md, not official brand guidelines.

## 14. Approved Stitch generation prompt

Use the following prompt after attaching this file as context:

```text
You are designing the complete UI/UX for MediKiosk.

IMPORTANT:
I have provided a file named:

MediKiosk-STITCH-DESIGN.md

READ THE ENTIRE FILE FIRST.

That file is the visual and product design contract for this project.

Do not invent a separate design system.
Do not create a generic AI healthcare UI.
Do not redesign the visual direction yourself.

Use the source-specific design mappings and MediKiosk role tokens in the file.
Treat Cal.com, Intercom, Airtable, Linear, and Notion as behavioral and compositional references only. Do not copy a company logo, proprietary font, illustration, exact page layout, or whole brand palette.

PRODUCT

MediKiosk is an AI-assisted pre-consultation clinical case-taking platform for an Ayurvedic OPD.

It helps patients complete history before consultation, supports deterministic guided questions, can eventually support voice/touch, records documents for extraction and doctor review, routes eligible cases, and provides a doctor with an editable structured case.

MediKiosk does NOT diagnose, prescribe treatment, or replace the doctor. The doctor makes the final clinical decision.

IMPLEMENTATION TRUTH

This is a design brief. Do not make unimplemented functionality appear live. Label prototype values as Synthetic demo. Call AI outputs extracted information or draft for doctor review. Use extraction confidence only, never medical certainty. Do not show live recording, live OCR, automatic routing, or active red-flag decisions unless those capabilities are connected and verified.

DESIGN SOURCE MAPPING

PATIENT EXPERIENCE
→ Cal.com for whitespace, progression, neutral controls, and restrained actions
→ Intercom for conversational hierarchy and friendly message/input behavior
→ Notion only for calm summary grouping

DOCTOR EXPERIENCE
→ Linear for dark navigation and precise scanning density
→ Airtable for light structured tables, queues, rows, and status organization
→ Notion only for readable grouped case sections

EMERGENCY EXPERIENCE
→ Linear operational density
→ Airtable information rows
→ restrained semantic warning/danger treatment

Do not mix all five systems randomly. The complete mappings and role tokens are in the provided file.

MAIN FLOW

Patient → Language → New/Returning → Consent → Patient Code → Guided Interview → Red-Flag Check → Safe Department Classification → Document Upload → Extraction Review → Structured Summary → Patient Confirmation → Token → Department Queue → Doctor Review → Consultation.

A red-flagged patient receives no normal token and enters no normal queue. Emergency is a separate doctor operational view.

SCREENS TO DESIGN

Patient: P01 Welcome/Language, P02 Consent, P03 Patient Code, P04 Guided Interview, P05 Red-Flag Redirect, P06 Document Upload, P07 Summary Review, P08 Confirmation/Token, P09 Waiting/Completion.

Doctor: D01 Kayachikitsa Queue, D02 Kayachikitsa Patient Case, D03 Kayachikitsa Review/Edit. Reuse this system for Panchakarma. Also create D04 Emergency Dashboard.

PATIENT RULES

The patient interface is calm, simple, trustworthy, human, touch-friendly, and non-technical.

Hierarchy: Question → Supporting explanation → Input → One primary action.

Do not make generic ChatGPT chat, giant AI branding, unnecessary menus, excessive cards, or decorative AI graphics.

DOCTOR RULES

The doctor interface is professional, precise, fast to scan, structured, and information-dense without clutter.

Hierarchy: Patient/Token → Chief Complaint → History → Ayurvedic Assessment → Documents/Extracted Information → Source/Extraction Confidence → Edit/Confirm.

Do not turn it into an analytics dashboard full of charts.

EMERGENCY RULES

Show active alert, patient code, complaint fragment, timestamp, alert state, and staff action. Make urgency noticeable but restrained. Do not use flashing, glowing red effects, dramatic illustrations, or excessive animation.

AYURVEDIC CONTENT

Support Prakriti, Agni, Koshtha, Nidana, and Ahara-Vihara. Support the defined issue examples in the context file. The interface must not claim diagnostic certainty.

DOCUMENT EXPERIENCE

Design: Upload → Preview → Processing → Extracted information → Extraction confidence → Review/correction → Merge into case summary.

COMPONENT SYSTEM

Use reusable buttons, inputs, voice controls including unavailable state, conversational messages, progress, upload, document preview, extraction rows, confidence/status badges, queue rows, grouped case sections, editable fields, summary cards, alert rows, loading/error/success states, and token display.

VISUAL QUALITY

Use strong whitespace, typography, alignment, and information architecture. Do not produce generic AI dashboards, template hospital software, glassmorphism, neon gradients, purple AI glow, random stock imagery, decorative 3D objects, excessive charts, or inconsistent styles.

RESPONSIVE

Patient screens must work on kiosk/desktop, tablet, and narrow mobile. Doctor screens prioritize desktop/tablet. Preserve readable text, 48px patient touch targets, grouping, and no horizontal text overflow.

WORKING METHOD

Do not create all screens in one generation. Generate one screen at a time, starting with P01. Preserve the approved patient system for P02–P09, establish the doctor system with D01, then reuse it for D02–D04. Before finalizing each screen, check it against MediKiosk-STITCH-DESIGN.md.

Generate the highest-fidelity version possible, grounded in the approved source mappings and MediKiosk’s original product identity.
```

## 15. Change control

When a Stitch screen is approved:

1. record the accepted visual decisions in root `DESIGN.md`;
2. export or retrieve the screen code/image;
3. implement the screen in Next.js without blindly copying generated code;
4. test responsive layout, text overflow, keyboard focus, and state behavior;
5. label unresolved visual/feature gaps honestly.
