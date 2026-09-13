---
version: "alpha"
revision: "3.0"
name: "MediKiosk"
description: "Consumer-onboarding meets clinician-operations. Cal.com stepper + Intercom conversation + Airtable density."

colors:
  primary: "#2563EB"
  primary-hover: "#1D4ED8"
  primary-soft: "#EFF6FF"
  secondary: "#0F172A"
  background: "#F0F9FF"
  surface: "#FFFFFF"
  border: "#E2E8F0"
  text: "#0F172A"
  text-secondary: "#475569"
  success: "#10B981"
  success-soft: "#ECFDF5"
  warning: "#F59E0B"
  warning-soft: "#FFFBEB"
  danger: "#EF4444"
  danger-soft: "#FEF2F2"

typography:
  h1:
    fontFamily: "Inter, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Inter, sans-serif"
    fontSize: "1rem"
    lineHeight: 1.5

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    rounded: "12px"
    padding: "12px 24px"
    fontWeight: 600
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "12px"
    padding: "12px 24px"
    border: "1px solid {colors.border}"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "16px"
    shadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)"
    padding: "24px"
  input:
    backgroundColor: "{colors.surface}"
    border: "1px solid {colors.border}"
    rounded: "12px"
    padding: "12px"
  stepper:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary}"
    activeBackgroundColor: "{colors.primary}"
    activeTextColor: "#FFFFFF"
  status-pill:
    rounded: "9999px"
    padding: "4px 12px"
    fontSize: "0.875rem"
    fontWeight: 500
---

# MediKiosk — Agent-Grade Design Contract v3.0

## 1. Overview

MediKiosk is an AI-assisted pre-consultation patient case-taking interface.

This file is the **visual source of truth** for UI work.

The product has three surfaces:

1. Patient kiosk (Conversational, Cal.com-style stepper)
2. Doctor workspace (Airtable/Linear-style density)
3. Document/OCR review

The surfaces must look like one product.

### Normative priority

When instructions conflict, follow this order:

1. Exact YAML tokens and component tokens
2. Explicit MUST / MUST NOT rules
3. Component state matrix
4. Layout contracts
5. Screen contracts
6. Rationale and inspiration
7. Agent judgment

Do not invent a value when this file already defines one.

### Design intent

MediKiosk should feel:

- calm
- trustworthy
- clear
- restrained
- professional
- human
- efficient

It must **not** feel:

- flashy
- futuristic
- gaming-oriented
- generic SaaS
- AI-demo-like
- decorative
- clinically authoritative beyond the product's actual scope

---

## 2. Inspiration Evidence

The visual system is a synthesis, not a copy.

### Cal.com influence

Use for:

- restrained control hierarchy
- clear progression (stepper)
- whitespace
- simple action surfaces
- practical form layout

Do not copy Cal.com's brand colors or branding.

### Intercom influence

Use for:

- conversational interaction behavior
- message hierarchy
- short prompts
- clear response/action relationship
- friendly avatar/illustration usage

Do not turn MediKiosk into a customer-support chat clone.

### Airtable influence

Use for:

- structured information
- table scanning
- status presentation
- review-oriented data density

Do not copy Airtable's branding or color system.

### Linear influence

Use for:

- information density
- metadata hierarchy
- scanning discipline
- compact doctor-side controls

Do not require Linear's dark visual treatment.

### Evidence rule

Inspiration defines **behavior and principles**, not copied visual identity.

Never write code such as:

```text
"make it look like Linear"
```

Instead use the explicit MediKiosk tokens and component rules in this file.

---

## 3. Token Rules

### Mandatory

- Use only defined color tokens.
- Use only defined typography tokens.
- Use only defined spacing tokens.
- Use only defined radius tokens.
- Component values must reference tokens where a token exists.
- New values require a DESIGN.md change before implementation.
- Do not create one-off hex colors.
- Do not create arbitrary spacing such as 23px.
- Do not create arbitrary border radii.

### CSS variable mapping

Implementation should expose the design tokens as CSS custom properties:

```css
:root {
  --mk-primary: #2563EB;
  --mk-primary-hover: #1D4ED8;
  --mk-primary-soft: #EFF6FF;
  --mk-secondary: #0F172A;
  --mk-background: #F0F9FF;
  --mk-surface: #FFFFFF;
  --mk-border: #E2E8F0;
  --mk-text: #0F172A;
  --mk-text-secondary: #475569;
  --mk-success: #10B981;
  --mk-success-soft: #ECFDF5;
  --mk-warning: #F59E0B;
  --mk-warning-soft: #FFFBEB;
  --mk-danger: #EF4444;
  --mk-danger-soft: #FEF2F2;
}
```

Do not hard-code these values in component CSS when a token exists.

---

## 4. Layout Contract

### Patient kiosk

```text
content max width: 720px
preferred content width: 640–720px
desktop horizontal padding: 32–64px
narrow horizontal padding: 20px
primary control height: 56px preferred
minimum interactive target: 48×48px
```

### Doctor workspace

```text
desktop target width: 1280px+
maximum content width: 1440px
standard section gap: 24px
compact metadata gap: 8–12px
main two-column gap: 24px
```

### Density

Patient:

```text
spacious
one question
one primary action
minimal simultaneous decisions
```

Doctor:

```text
compact
structured
scannable
editable
metadata visible
```

Never apply doctor density to the patient experience.

---

## 5. Responsive Contract

### Patient

At narrow widths:

- content becomes one column
- horizontal padding becomes 20px
- actions stack when needed
- touch targets remain at least 48×48px
- question typography may reduce from 32px to 28px
- body typography must remain at least 16px
- no horizontal scrolling

### Doctor

At widths below desktop:

- two-column review becomes stacked
- document preview appears before extracted fields
- dense tables may become structured rows/cards
- primary actions remain visible
- metadata may wrap but must not disappear

Responsive changes must preserve hierarchy, not simply shrink everything.

---

## 6. Typography Contract

### Patient

Question:

```text
32px / 600 / 1.2
```

Section:

```text
24px / 600 / 1.25
```

Body:

```text
18px / 400 / 1.5
```

Button:

```text
18px / 600 / 1.2
```

Helper:

```text
15px / 400 / 1.45
```

### Doctor

Title:

```text
24px / 600 / 1.25
```

Section:

```text
16px / 600 / 1.35
```

Body:

```text
14px / 400 / 1.45
```

Label:

```text
12px / 600 / 1.3
```

Metadata:

```text
12px / 400 / 1.3
```

### Typography restrictions

- Maximum two font weights in a single view unless a defined component requires another.
- No decorative display fonts.
- No all-caps patient questions.
- Do not center long body paragraphs.
- Do not reduce patient body text below 16px.

---

## 7. Shape and Elevation

### Radius

```text
8px   small
12px  controls
16px  cards
999px status pills
```

### Elevation

Default:

```text
prefer border + surface contrast
```

Cards:

```text
border: 1px solid #E2E8F0
shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1)
```

Do not use floating-card stacks.

Do not use glassmorphism.

Do not use backdrop blur as decoration.

---

## 8. Component State Matrix

Every interactive component must support explicit states.

### Button

| State | Required behavior |
|---|---|
| Default | defined token treatment |
| Hover | primary becomes `primary-hover` |
| Focus | visible 2px focus indication |
| Pressed | visibly active without changing layout |
| Disabled | muted, non-interactive |
| Loading | preserve dimensions, show progress indicator |
| Error | use contextual error messaging, not red-only decoration |

Never put two primary buttons beside each other.

### Input

| State | Required behavior |
|---|---|
| Empty | label + usable control |
| Focus | visible focus ring |
| Filled | preserve label |
| Error | danger border + text explanation |
| Disabled | muted and non-editable |
| Read-only | distinguish from disabled |
| Loading | preserve dimensions |

Placeholder text is never the only label.

### Upload

| State | Required behavior |
|---|---|
| Empty | clear upload action |
| Dragging | visible drop target |
| Uploading | progress/loading |
| Success | filename + success state |
| Error | recovery message |
| Needs review | review status |
| Corrected | distinguish corrected value |

### Confidence

Use only:

```text
High confidence
Review
Manually corrected
```

These indicate **data extraction/provenance confidence**, not medical certainty.

Never display:

```text
92% medically correct
92% diagnosis confidence
92% patient health confidence
```

---

## 9. Patient Screen Contracts

### Screen P01 — Welcome

Required:

- MediKiosk identity
- short purpose statement
- primary Start action
- language
- help
- privacy reassurance

Do not:

- show a dashboard
- show medical statistics
- show unnecessary navigation

### Screen P02 — Language

Required:

- clearly readable language names
- selected state
- Continue action

Do not rely on flags alone.

### Screen P03 — Interview

Required hierarchy:

```text
progress
question
helper/example
answer control
primary action
```

### Screen P04 — Choice question

Use large selectable rows/cards.

Selected state must use:

- border/surface change
- label or icon
- not color alone

### Screen P05 — Voice

Required:

```text
Listening
visible recording state
Stop
recognized answer
Edit
Continue
```

Never make voice the only recovery path.

### Screen P06 — Error

Use:

```text
what happened
what to do
recovery action
```

Never show stack traces, HTTP errors, provider names, or raw JSON.

### Screen P07 — Upload

Required:

- supported file types
- size guidance
- selected files
- processing state
- retry/remove controls

### Screen P08 — OCR review

Show:

```text
original document
extracted value
confidence/provenance
edit action
corrected value
```

Do not silently overwrite the original AI extraction.

### Screen P09 — Completion

Show:

- successful submission
- patient/session token if implemented
- next action
- simple reassurance

Do not claim a clinical decision was made.

---

## 10. Doctor Screen Contracts

### Screen D01 — Case list

Required:

- search
- useful filters
- patient/session identifier
- case status
- submission time
- action

Status must be readable without color.

### Screen D02 — Case detail

Priority:

```text
patient context
case status
structured case data
source
confidence
edit
confirmation
```

Do not lead with a large AI paragraph.

### Screen D03 — Field editing

Every editable AI-derived field should show:

```text
value
source
confidence
edit control
```

When corrected:

```text
original AI value
corrected value
manually corrected
```

### Screen D04 — Document review

Use split view on desktop:

```text
original document | extracted information
```

Stack on narrow layouts.

---

## 11. Content Contract

### Patient language

Prefer:

> What is the main problem you are experiencing?

Avoid:

> Enter chief complaint.

Prefer:

> How long have you had this problem?

Avoid:

> Specify symptom duration.

### Doctor language

Structured clinical terminology is acceptable on the doctor side.

### Prohibited claims

The UI must not state or imply:

- diagnosis by the AI
- autonomous treatment
- clinical certainty from extraction confidence
- completed ABDM integration when it is not implemented
- completed FHIR interoperability when it is not implemented
- validated Prakriti scoring when it is not implemented

---

## 12. Icon Contract

Use one consistent outline icon system.

Preferred:

- 16px inline
- 20px default
- 24px emphasis
- consistent stroke
- inherited semantic color

Do not mix icon libraries in one view.

Do not use emoji as UI icons.

Do not use decorative robot/brain icons to represent Artificial Intelligence (AI).

---

## 13. Accessibility Contract

Required:

- WCAG AA-oriented contrast.
- Important state never conveyed by color alone.
- visible `:focus-visible`.
- keyboard-accessible controls.
- minimum 48×48px target.
- patient body text minimum 16px.
- no hover-only interaction.
- readable language labels.
- accessible names for controls.
- reduced-motion support.
- zoom without loss of core functionality.

### Contrast gate

Normal text must target at least:

```text
4.5:1
```

Large text may target:

```text
3:1
```

Contrast must be checked from the actual rendered foreground/background pair, not from token names.

---

## 14. Motion Contract

MediKiosk is not an entertainment interface.

Use motion only to explain:

- progress
- loading
- state changes
- confirmation
- focus

Preferred durations:

```text
fast: 120ms
normal: 180ms
slow: 240ms
```

Use a standard ease-out curve for entering UI.

Respect:

```css
@media (prefers-reduced-motion: reduce)
```

Reduced motion should remove decorative movement while preserving state changes.

Do not animate medical data continuously.

---

## 15. Anti-Pattern Contract

NEVER introduce:

- gradients
- glassmorphism
- excessive blur
- neon colors
- giant AI illustrations
- emoji UI icons
- generic three-column SaaS landing-page layouts
- excessive pill buttons
- excessive floating cards
- arbitrary spacing
- arbitrary colors
- arbitrary radii
- multiple competing primary CTAs
- color-only status
- raw server/provider errors
- fake clinical certainty
- fake ABDM/FHIR integration
- fake medical statistics
- invented patient data presented as real

---

## 16. Visual Reference Contract

The approved visual direction is the MediKiosk composite reference showing:

- patient welcome
- step-based interview
- conversational prompt behavior
- document upload
- completion/token state
- doctor case list
- doctor structured review
- confidence/status presentation
- inspiration notes

The reference is a **visual target**, not a literal pixel-copy instruction.

When implementation differs from the reference:

1. Prefer this DESIGN.md's exact tokens.
2. Preserve information hierarchy.
3. Preserve component behavior.
4. Preserve accessibility.
5. Record a DESIGN.md decision if the difference is intentional.

---

## 17. Known Gaps

The following are intentionally not visually specified as implemented product features:

- live ABDM integration
- FHIR export
- consent workflow
- audit logging runtime
- Hospital Information System (HIS) integration
- red-flag engine
- full Prakriti scoring
- autonomous diagnosis/treatment
- local model inference

Do not invent screens that make these features appear implemented.

---

## 18. Design Decisions

### v3.0

Decision:

Adopt a "Consumer-onboarding meets clinician-operations" aesthetic.

Reason:

The vision analysis confirmed the need for a Cal.com-style stepper for patients and an Airtable/Linear-style dashboard for doctors, unified by a soft healthcare-blue palette.

### v2.1

Decision:

Use `text-secondary` rather than `text-muted` for disabled button text on the `border` surface.

Reason:

The previous pair measured 3.15:1 and failed the required WCAG AA contrast gate. `text-secondary` on `border` measures 4.80:1 while preserving the disabled treatment.

### v2.0

Decision:

Use a single MediKiosk visual system synthesized from Cal.com, Intercom, Airtable, Linear, and limited Notion influence.

Reason:

The product needs patient calmness, conversational interaction, structured clinical review, and high information density without visually becoming a copy of any source product.

Decision:

Use exact tokens as normative values.

Reason:

Natural-language descriptions leave too much freedom to coding agents.

Decision:

Add explicit component states.

Reason:

Happy-path-only specifications cause agents to invent disabled, loading, error, and focus treatments.

Decision:

Add negative constraints.

Reason:

Agents otherwise tend to fall back to generic modern SaaS patterns.

Decision:

Add measurable QA gates.

Reason:

A design contract must be testable rather than purely subjective.

---

## 19. Agent Pre-Flight Checklist

Before changing UI, verify:

```text
[ ] Read DESIGN.md
[ ] Identify affected screen contract
[ ] Identify affected component tokens
[ ] Reuse existing tokens
[ ] Reuse existing components
[ ] No new arbitrary colors
[ ] No new arbitrary spacing
[ ] No new arbitrary radii
[ ] All required states considered
[ ] Patient/doctor density boundary preserved
[ ] Accessibility requirements preserved
[ ] Provenance/confidence preserved
[ ] No out-of-scope feature implied
[ ] Responsive behavior checked
[ ] Visual screenshot checked
[ ] DESIGN.md updated if a real design decision changed
```

A component is not complete until the checklist passes.

---

## 20. Visual QA Gate

The visual loop is mandatory:

```text
DESIGN.md
    ↓
Implement
    ↓
Render
    ↓
Screenshot
    ↓
Compare against approved reference
    ↓
Check tokens
    ↓
Check component states
    ↓
Check accessibility
    ↓
Check responsive behavior
    ↓
Record P0 / P1 / P2 gaps
    ↓
Repair DESIGN.md when the rule is missing/wrong
    ↓
Rebuild
    ↓
Re-test
```

### P0

Core workflow blocked or unusable.

Examples:

- primary action unclear
- unreadable text
- unusable touch target
- critical information hidden

### P1

Major design-system or usability deviation.

Examples:

- wrong hierarchy
- incorrect density
- inconsistent component behavior
- broken responsive layout
- provenance difficult to locate

### P2

Polish issue.

Examples:

- alignment
- minor spacing drift
- inconsistent icon sizing

### PASS

No unresolved P0/P1 findings.

P2 findings may remain only when they do not violate the design contract and are explicitly recorded.

---

## 21. Change Control

DESIGN.md is a living contract.

When a real design decision changes:

1. update DESIGN.md first
2. bump the version
3. state what changed
4. state why
5. rebuild affected screens
6. visually re-test
7. compare the design diff

Never silently modify the implementation while leaving DESIGN.md stale.
