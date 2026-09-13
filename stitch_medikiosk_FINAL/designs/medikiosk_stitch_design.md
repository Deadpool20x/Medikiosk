# MediKiosk — Stitch Visual Design Contract

> **Purpose:** This file is the visual + product-context source for generating the MediKiosk user interface in Google Stitch.
>
> **Important:** The visual system below is derived from the published getdesign.md DESIGN.md analyses for **Cal.com, Intercom, Airtable, Linear, and Notion**. Product requirements come from the MediKiosk Final Project Plan. Do not invent a new visual system.

---

# 1. PROJECT CONTEXT

## Product

**MediKiosk** is an AI-assisted pre-consultation clinical case-taking tool for an Ayurvedic OPD.

It is **not** an autonomous doctor, diagnosis engine, or production ABDM integration.

## Primary objective

A patient completes medical and Ayurvedic history before consultation. MediKiosk structures the information, digitizes uploaded records, performs safety checking, routes the case to a defined department, and presents the doctor with an editable structured case.

## Product sides

### Patient experience

Patient-facing kiosk:

- Language selection
- New patient / returning patient
- Consent
- Patient code
- Guided AI interview
- Voice + touch interaction
- Chief complaint
- Symptom/history questions
- Standard medical history
- Ayurvedic assessment
- Red-flag handling
- Document upload
- Structured summary review
- Confirmation
- Department token

### Doctor experience

Three operational dashboards:

1. Kayachikitsa
2. Panchakarma
3. Emergency

Doctor dashboards show:

- Queue
- Patient code
- Chief complaint
- Structured history
- Ayurvedic assessment
- Uploaded documents
- Extracted information
- Confidence/source indicators
- Editable information
- Confirm/save

### Emergency experience

A red-flagged patient:

- stops the interview
- receives no token
- enters no normal queue
- creates an emergency alert
- appears in the Emergency dashboard

---

# 2. PRODUCT FLOW

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
AI Interview
  ├── Chief Complaint
  ├── Symptom / HPI
  ├── Medical History
  ├── Drug / Allergy
  ├── Family / Personal History
  └── Ayurvedic Assessment
  ↓
Red-Flag Check
  ├── YES → Emergency Dashboard
  │          → NO TOKEN
  │          → NO QUEUE
  │
  └── NO
       ↓
Department Classification
       ↓
Kayachikitsa / Panchakarma
       ↓
Document Upload
       ↓
Document Extraction
       ↓
Structured Summary
       ↓
Patient Confirmation
       ↓
Token
       ↓
Department Queue
       ↓
Doctor Dashboard
       ↓
Doctor Review / Edit / Confirm
       ↓
Consultation
```

The patient experience should feel like **one coherent guided conversation**, while the application may internally maintain deterministic interview stages.

---

# 3. INTERVIEW CONTENT

The interview gathers:

1. Chief complaint
2. History of present illness
3. Past medical / surgical history
4. Drug / allergy history
5. Family history
6. Personal history
7. Ayurvedic assessment:
   - Prakriti
   - Agni
   - Koshtha
   - Nidana
   - Ahara-Vihara

The AI asks one clear question at a time.

The AI does not diagnose or prescribe.

---

# 4. DEPARTMENT ROUTING

| Issue | Department |
|---|---|
| Sandhivata | Kayachikitsa |
| Agnimandya | Kayachikitsa |
| Kushtha | Kayachikitsa |
| Pratishyaya | Kayachikitsa |
| Jwara | Kayachikitsa |
| Katishoola | Kayachikitsa |
| Shirahshoola | Kayachikitsa |
| Arsha | Kayachikitsa |
| Prameha | Kayachikitsa |
| Sthaulya | Panchakarma |

Any red flag routes to Emergency instead.

---

# 5. STITCH GENERATION RULE

## Read this file first

Before generating any screen:

1. Read this entire file.
2. Treat the source-specific visual systems below as the design reference.
3. Treat the MediKiosk product requirements as the content/interaction reference.
4. Do not create a generic AI SaaS visual style.
5. Do not invent a new palette, typography system, spacing scale, radius scale, or component language.
6. Do not mix source systems randomly inside one screen.
7. Use the source mapping defined in Section 10.

The goal is not to copy a brand.

The goal is to use the **documented visual characteristics and component patterns** of the selected getdesign.md systems for the appropriate MediKiosk surface.

---

# 6. SOURCE DESIGN SYSTEMS

## 6.1 CAL.COM SOURCE

**Use for:** calm patient flow, progression, controls, whitespace, simple actions.

### Visual direction

- Clean neutral UI
- White canvas
- Black primary action
- Generous whitespace
- Soft-rounded cards
- Clear hierarchy
- Product UI fragments inside cards
- Minimal decorative treatment

### Colors

```text
primary              #111111
primary-active       #242424
primary-disabled     #e5e7eb
ink                  #111111
body                 #374151
muted                #6b7280
muted-soft           #898989
hairline             #e5e7eb
hairline-soft        #f3f4f6
canvas               #ffffff
surface-soft         #f8f9fa
surface-card         #f5f5f5
surface-strong       #e5e7eb
surface-dark         #101010
surface-dark-elevated #1a1a1a
on-primary           #ffffff
on-dark              #ffffff
on-dark-soft         #a1a1aa
brand-accent         #3b82f6
success              #10b981
warning              #f59e0b
error                #ef4444
badge-orange         #fb923c
badge-pink           #ec4899
badge-violet         #8b5cf6
badge-emerald        #34d399
```

### Typography

```text
display-xl  64px / 600 / 1.05 / -2px
display-lg  48px / 600 / 1.10 / -1.5px
display-md  36px / 600 / 1.15 / -1px
display-sm  28px / 600 / 1.20 / -0.5px
title-lg    22px / 600 / 1.30 / -0.3px
title-md    18px / 600 / 1.40 / 0
title-sm    16px / 600 / 1.40 / 0
body-md     16px / 400 / 1.50 / 0
body-sm     14px / 400 / 1.50 / 0
caption     13px / 500 / 1.40 / 0
button      14px / 600 / 1.00 / 0
nav-link    14px / 500 / 1.40 / 0
```

Font families:

- Display: Cal Sans, Inter, sans-serif
- UI/body: Inter, sans-serif
- Code: JetBrains Mono

### Radius

```text
xs    4px
sm    6px
md    8px
lg    12px
xl    16px
pill  9999px
full  9999px
```

### Spacing

```text
4, 8, 12, 16, 24, 32, 48, 96px
```

### Component patterns

- Primary button: black, white text, 8px radius, 12px × 20px padding, 40px height
- Secondary button: white canvas, ink text, hairline border
- Circular icon button: 36px
- Input: white canvas, 1px hairline, 8px radius
- Cards: light-gray card surface, 12px radius
- Pills: reserved for grouped navigation / badges
- No heavy shadows
- No glassmorphism
- Major sections use generous whitespace

---

# 6.2 INTERCOM SOURCE

**Use for:** patient conversational interaction and friendly communication hierarchy.

### Visual direction

- Friendly conversational UI
- Soft cream-white canvas
- Charcoal type
- Floating white tiles
- Thin hairline borders
- Modest 8–16px radii
- Product-led presentation
- Ornament kept rare

### Colors

```text
primary         #111111
on-primary      #ffffff
ink             #111111
ink-muted       #626260
ink-subtle      #7b7b78
ink-tertiary    #9c9fa5
canvas          #f5f1ec
surface-1       #ffffff
surface-2       #ebe7e1
inverse-canvas  #000000
inverse-surface #313130
inverse-ink     #ffffff
hairline        #d3cec6
hairline-soft   #ebe7e1
fin-orange      #ff5600
report-orange   #fe4c02
report-blue     #65b5ff
report-green    #0bdf50
report-pink     #ff2067
report-lime     #b3e01c
report-cyan     #03b2cb
brand-blue      #0007cb
semantic-error  #c41c1c
semantic-success #0bdf50
```

### Typography

```text
display-xl  72px / 500 / 1.05 / -2px
display-lg  56px / 500 / 1.10 / -1.4px
display-md  40px / 500 / 1.15 / -0.8px
headline    28px / 500 / 1.20 / -0.5px
card-title  22px / 500 / 1.25 / -0.3px
subhead     20px / 400 / 1.40 / -0.2px
body-lg     18px / 400 / 1.50 / -0.1px
body        16px / 400 / 1.50 / 0
body-sm     14px / 400 / 1.50 / 0
caption     12px / 400 / 1.40 / 0
button      15px / 500 / 1.20 / 0
eyebrow     14px / 500 / 1.30 / 0
mono        13px / 400 / 1.50 / 0
```

Font families:

- Saans, sans-serif
- SaansMono for mono

### Radius

```text
xs    4px
sm    6px
md    8px
lg    12px
xl    16px
xxl   24px
pill  9999px
full  9999px
```

### Spacing

```text
4, 8, 12, 16, 24, 32, 48, 96px
```

### Component patterns

- Primary button: charcoal with white text
- Secondary button: white surface
- Conversational input: white surface, 8px radius
- Conversational cards: white floating surfaces, 12–16px radius
- Pricing/tab patterns: pill treatments where appropriate
- Keep decorative color restrained
- Do not use Fin Orange as a MediKiosk brand color; it belongs to the source system only

---

# 6.3 AIRTABLE SOURCE

**Use for:** doctor structured data, queues, extracted documents, tables, status information.

### Visual direction

- Sober editorial workflow UI
- White canvas
- Dark ink
- Structured data aesthetic
- Signature surface cards
- Clear primary/secondary button pair
- Product UI fragments
- Strong information organization

### Colors

```text
primary             #181d26
primary-active      #0d1218
ink                 #181d26
body                #333840
muted               #41454d
hairline            #dddddd
border-strong       #9297a0
canvas               #ffffff
surface-soft         #f8fafc
surface-strong      #e0e2e6
surface-dark        #181d26
surface-dark-elevated #1d1f25
signature-coral     #aa2d00
signature-forest    #0a2e0e
signature-cream     #f5e9d4
signature-peach     #fcab79
signature-mint      #a8d8c4
signature-yellow    #f4d35e
signature-mustard   #d9a441
on-primary          #ffffff
on-dark             #ffffff
link                #1b61c9
link-active         #1a3866
info                #254fad
info-border         #458fff
success             #006400
success-border      #39bf45
pricing-ink         #1d1f25
```

### Typography

```text
display-xl      48px / 500 / 1.10 / 0
display-lg      40px / 400 / 1.20 / 0
display-md      32px / 400 / 1.20 / 0
title-lg        24px / 400 / 1.35 / 0.12px
title-md        20px / 400 / 1.50 / 0
title-sm        18px / 500 / 1.40 / 0
label-md        16px / 500 / 1.40 / 0
button          16px / 500 / 1.40 / 0
body-md         14px / 400 / 1.25 / 0
caption         14px / 500 / 1.35 / 0.16px
```

Font families:

- Haas Grotesk / Haas
- Inter Display for the pricing sub-system

### Radius

```text
xs    2px
sm    6px
md    10px
lg    12px
pill  9999px
full  9999px
```

### Spacing

```text
4, 8, 12, 16, 24, 32, 48, 96px
```

### Component patterns

- Primary CTA: near-black, white text, 12px radius
- Secondary CTA: white, ink text, hairline outline
- Circular icon: 40px
- Large structured cards: 10–12px radius
- Inputs: 6px radius
- Data layouts should feel organized rather than decorative
- Use signature colors only for meaningful category/status surfaces

---

# 6.4 LINEAR SOURCE

**Use for:** high-density professional doctor workspace and fast scanning.

### Visual direction

- Ultra-minimal
- Precise
- Product-focused
- Dense but controlled
- Strong surface hierarchy
- Hairline borders
- Product screenshots / product UI as the visual focus
- Accent used sparingly

### Colors

```text
primary             #5e6ad2
primary-hover       #828fff
primary-focus       #5e69d1
on-primary          #ffffff
ink                 #f7f8f8
ink-muted           #d0d6e0
ink-subtle          #8a8f98
ink-tertiary        #62666d
canvas              #010102
surface-1           #0f1011
surface-2           #141516
surface-3           #18191a
surface-4           #191a1b
hairline            #23252a
hairline-strong     #34343a
hairline-tertiary   #3e3e44
inverse-canvas      #ffffff
inverse-surface-1   #f5f6f6
inverse-surface-2   #f6f7f7
inverse-ink         #000000
brand-secure        #7a7fad
semantic-success    #27a644
```

### Typography

```text
display-xl  80px / 600 / 1.05 / -3px
display-lg  56px / 600 / 1.10 / -1.8px
display-md  40px / 600 / 1.15 / -1px
headline    28px / 600 / 1.20 / -0.6px
card-title  22px / 500 / 1.25 / -0.4px
subhead     20px / 400 / 1.40 / -0.2px
body-lg     18px / 400 / 1.50 / -0.1px
body        16px / 400 / 1.50 / -0.05px
body-sm     14px / 400 / 1.50 / 0
caption     12px / 400 / 1.40 / 0
button      14px / 500 / 1.20 / 0
eyebrow     13px / 500 / 1.30 / 0.4px
mono        13px / 400 / 1.50 / 0
```

Font families:

- Linear Display
- Linear Text
- Linear Mono

### Radius

```text
xs    4px
sm    6px
md    8px
lg    12px
xl    16px
xxl   24px
pill  9999px
full  9999px
```

### Spacing

```text
4, 8, 12, 16, 24, 32, 48, 96px
```

### Component patterns

- Primary button: accent lavender
- Secondary button: elevated dark surface
- Cards: dark charcoal surface + hairline
- Product data panels: compact and precise
- Status badges: restrained
- Accent is not decorative
- No atmospheric gradients
- No glassmorphism

---

# 6.5 NOTION SOURCE

**Use for:** calm workspace/document review surfaces and structured case information.

### Visual direction

- Warm minimalism
- Soft surfaces
- Workspace-like organization
- Rich but controlled pastel category surfaces
- Live workspace UI as the product content
- Clear typography hierarchy

### Colors

```text
primary             #5645d4
primary-pressed     #4534b3
primary-deep        #3a2a99
on-primary          #ffffff
brand-navy          #0a1530
brand-navy-deep     #070f24
brand-navy-mid      #1a2a52
link-blue           #0075de
link-blue-pressed   #005bab
brand-orange        #dd5b00
brand-orange-deep   #793400
brand-pink          #ff64c8
brand-pink-deep     #a02e6d
brand-purple       #7b3ff2
brand-purple-300   #d6b6f6
brand-purple-800   #391c57
brand-teal          #2a9d99
brand-green         #1aae39
brand-yellow        #f5d75e
brand-brown         #523410
card-tint-peach     #ffe8d4
card-tint-rose      #fde0ec
card-tint-mint      #d9f3e1
card-tint-lavender  #e6e0f5
card-tint-sky       #dcecfa
card-tint-yellow    #fef7d6
card-tint-yellow-bold #f9e79f
card-tint-cream     #f8f5e8
card-tint-gray      #f0eeec
canvas              #ffffff
surface             #f6f5f4
surface-soft        #fafaf9
hairline            #e5e3df
hairline-soft       #ede9e4
hairline-strong     #c8c4be
ink-deep            #000000
ink                 #1a1a1a
charcoal            #37352f
slate               #5d5b54
steel               #787671
stone               #a4a097
muted               #bbb8b1
on-dark             #ffffff
on-dark-muted       #a4a097
semantic-success    #1aae39
semantic-warning    #dd5b00
semantic-error      #e03131
```

### Typography

```text
hero-display  80px / 600 / 1.05 / -2px
display-lg    56px / 600 / 1.10 / -1px
heading-1     48px / 600 / 1.15 / -0.5px
heading-2     36px / 600 / 1.20 / -0.5px
heading-3     28px / 600 / 1.25
heading-4     22px / 600 / 1.30
heading-5     18px / 600 / 1.40
body-md       16px / 400 / 1.55
body-md-medium 16px / 500 / 1.55
body-sm       14px / 400 / 1.50
body-sm-medium 14px / 500 / 1.50
caption       13px / 400 / 1.40
caption-bold  13px / 600 / 1.40
micro         12px / 500 / 1.40
micro-uppercase 11px / 600 / 1.40 / 1px
button-md     14px / 500 / 1.30
```

Font family:

- Notion Sans

### Radius

```text
xs    4px
sm    6px
md    8px
lg    12px
xl    16px
xxl   20px
xxxl  24px
full  9999px
```

### Spacing

```text
4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 96, 120px
```

### Component patterns

- Primary button: purple, white text, 8px radius
- Secondary button: transparent/outlined
- Workspace cards: white surface, subtle border
- Category badges: pastel background + matching text
- Search pills / tabs / segmented controls
- Comparison/data rows
- FAQ/accordion-like information grouping
- Workspace mockup surfaces

---

# 7. MEDIKIOSK SOURCE MAPPING

Do not blend all five systems indiscriminately.

## Patient kiosk

Primary source:

**Cal.com**

Secondary interaction source:

**Intercom**

Supporting workspace/content source:

**Notion**

Patient visual target:

```text
Cal.com:
  clean controls
  whitespace
  simple progression
  neutral surfaces

Intercom:
  conversational hierarchy
  friendly interaction
  message/input treatment

Notion:
  calm workspace surfaces
  structured content
```

Do not use Linear's dark canvas for the patient kiosk.

Do not use Airtable's colorful signature cards as the patient default.

---

## Doctor — Kayachikitsa

Primary source:

**Linear**

Secondary source:

**Airtable**

Supporting source:

**Notion**

Visual target:

```text
Linear:
  professional density
  precise scanning
  structured dark/controlled surface hierarchy

Airtable:
  structured data
  queues
  table-like organization
  status information

Notion:
  readable case sections
  grouped information
```

---

## Doctor — Panchakarma

Use the **same visual system as Kayachikitsa**.

Do not create a second unrelated dashboard style.

Only the department data/configuration changes.

---

## Emergency Dashboard

Primary source:

**Linear**

Secondary source:

**Airtable**

The Emergency dashboard must visually prioritize:

1. alert state
2. patient code
3. complaint fragment
4. timestamp
5. staff action

Use the source semantic warning/error treatment.

Do not make it visually dramatic with gradients, glowing red effects, or animations.

---

# 8. REQUIRED SCREENS

## Patient

### P01 — Welcome / Language

Content:

- MediKiosk identity
- English / Hindi
- New patient
- Returning patient

Visual:

- Cal.com clean canvas
- simple primary action
- generous whitespace

### P02 — Consent

Content:

- concise consent explanation
- continue action

Visual:

- Cal.com / Notion calm information hierarchy

### P03 — Patient Code

Content:

- generated patient code
- clear explanation
- continue

### P04 — Interview

Content:

- progress
- current question
- conversational history
- text input
- voice control
- continue

Visual:

- Intercom conversation hierarchy
- Cal.com control hierarchy
- no generic chatbot appearance

### P05 — Red Flag

Content:

- urgent instruction
- clear next action
- no normal queue/token

Visual:

- restrained semantic error treatment
- no decorative alarm graphics

### P06 — Document Upload

Content:

- upload prescription/report
- preview
- extraction state
- continue / skip

Visual:

- Cal.com upload simplicity
- Notion/Airtable structured document preview

### P07 — Summary Review

Content:

- chief complaint
- history
- Ayurvedic section
- document extraction
- editable/correctable information

Visual:

- Notion workspace organization
- Airtable structured information

### P08 — Confirmation / Token

Content:

- summary confirmed
- department
- token

Visual:

- Cal.com strong single-action hierarchy

### P09 — Waiting / Completion

Content:

- token
- department
- simple waiting message

Visual:

- calm, sparse, readable

---

# 9. DOCTOR SCREENS

## D01 — Department Queue

Content:

- department
- waiting patients
- token
- patient code
- status
- time

Visual:

- Linear scanning density
- Airtable structured rows

## D02 — Patient Case

Content:

- patient code
- chief complaint
- history
- Ayurvedic assessment
- documents
- extracted data
- confidence/source

Visual:

- Linear precision
- Airtable structured data
- Notion grouped case sections

## D03 — Review / Edit

Content:

- editable fields
- source
- confidence
- correction
- save/confirm

Visual:

- structured professional workspace
- no oversized cards for every tiny field

## D04 — Emergency Dashboard

Content:

- active alerts
- patient code
- complaint fragment
- timestamp
- alert state

Visual:

- Linear density + Airtable information structure
- restrained semantic error/warning treatment

---

# 10. CORE COMPONENT INVENTORY

Build/reuse:

- Top navigation / kiosk header
- Progress indicator
- Primary button
- Secondary button
- Icon button
- Text input
- Textarea
- Voice control
- Conversational message
- Question block
- Choice/segmented control
- Upload area
- Document preview
- Extraction row
- Confidence badge
- Status badge
- Queue row
- Case section
- Editable field
- Summary card
- Alert row
- Empty state
- Loading state
- Error state
- Success state
- Token display

Use the closest component pattern from the mapped source system.

Do not invent a new component style just because it is visually convenient.

---

# 11. VISUAL HIERARCHY

## Patient

```text
Question
  ↓
Supporting explanation
  ↓
Patient input
  ↓
Primary action
```

The question is the dominant visual element.

## Doctor

```text
Patient / token
  ↓
Chief complaint
  ↓
Important history
  ↓
Ayurvedic assessment
  ↓
Documents
  ↓
Confidence / source
  ↓
Edit / confirm
```

The doctor should be able to scan the case quickly.

## Emergency

```text
ALERT
  ↓
Patient
  ↓
Complaint
  ↓
Time
  ↓
Action
```

---

# 12. PRODUCT CONTENT RULES

Use simple patient language.

Avoid technical Artificial Intelligence (AI) terminology in patient-facing copy.

Do not tell the patient:

- that the AI diagnosed them
- that the AI decided treatment
- that the AI replaces a doctor

Use language consistent with:

- recording medical history
- helping prepare the doctor
- reviewing information
- confirming information

The doctor-facing interface may expose:

- AI-derived information
- confidence
- source
- extracted document information

These must remain editable/reviewable.

---

# 13. VISUAL ANTI-PATTERNS

Do NOT generate:

- generic centered AI chatbot landing page
- excessive glassmorphism
- neon gradients
- purple AI glow everywhere
- excessive rounded cards
- every field inside a separate floating card
- giant decorative medical illustrations
- random medical stock imagery
- random dashboard charts
- decorative 3D objects
- excessive shadows
- rainbow status systems
- unrelated dark/light styles within one surface
- copied logos or brand marks
- copied Cal.com / Intercom / Airtable / Linear / Notion branding

The interface must look like **MediKiosk using documented source design patterns**, not a collage of brand copies.

---

# 14. RESPONSIVE REQUIREMENTS

Patient kiosk must work for:

- desktop/kiosk
- tablet
- narrow mobile

Doctor workspace must work for:

- desktop
- tablet

Do not simply shrink desktop.

Preserve:

- hierarchy
- readability
- touch usability
- information grouping
- queue readability
- document readability

---

# 15. STITCH OUTPUT QUALITY GATE

Before accepting a generated screen, check:

### Visual

- Does it clearly resemble the selected source system?
- Are source colors used according to their roles?
- Is typography consistent with the source?
- Are radius and spacing consistent?
- Are components using the source component patterns?
- Is the page hierarchy clear?
- Does it avoid generic AI UI?

### Product

- Does the screen belong to MediKiosk?
- Is the required workflow represented?
- Is patient/doctor/emergency context obvious?
- Is the correct information shown?
- Are interactions understandable?

### Consistency

- Patient screens follow Patient Source Mapping.
- Doctor screens follow Doctor Source Mapping.
- Emergency follows Emergency Source Mapping.
- No unrelated visual language is introduced.

---

# 16. ITERATION RULE

If the first Stitch result looks generic:

1. Compare it with this file.
2. Identify which source design characteristic was lost.
3. Regenerate using the same source mapping.
4. Do not invent a new visual direction.
5. Preserve the MediKiosk product requirements.

The goal is **source-constrained visual refinement**, not free-form redesign.

---

# 17. SOURCE PROVENANCE

Visual system source references:

- Cal.com — getdesign.md DESIGN.md analysis
- Intercom — getdesign.md DESIGN.md analysis
- Airtable — getdesign.md DESIGN.md analysis
- Linear — getdesign.md DESIGN.md analysis
- Notion — getdesign.md DESIGN.md analysis

These source analyses are independent public-pattern analyses. They are references for visual behavior and design-system extraction, not official brand guidelines.

MediKiosk product requirements are derived from:

**MediKiosk — Final Project Plan**
SIH 2026 — Problem Statement 26047.

---

# 18. FINAL STITCH INSTRUCTION

Generate the complete MediKiosk interface as a **high-quality product design system**, not as a generic AI-generated application.

Use:

- Cal.com for patient control/progression/whitespace
- Intercom for patient conversational interaction
- Notion for calm structured workspace content
- Linear for professional doctor scanning/density
- Airtable for structured doctor data and queue organization

Respect the exact source tokens and component patterns documented above.

Do not create a new visual identity.

Do not improvise a new design system.

Do not copy brand identity.

Make MediKiosk feel like a carefully designed healthcare product whose visual language is grounded in these documented, proven interface systems.
