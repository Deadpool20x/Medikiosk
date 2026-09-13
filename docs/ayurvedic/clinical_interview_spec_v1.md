# MediKiosk Ayurvedic Clinical Interview Specification — v1

> **Status: PROVISIONAL PILOT SPECIFICATION — SOURCE-DERIVED, NOT YET CLINICIAN-VALIDATED**
>
> This document is **not** an Ayurvedic-clinical validation. It is a literature-grounded draft for
> clinician review. Every clinical requirement below is tagged with its provenance:
>
> - **[S]** Source-supported — traceable to classical or peer-reviewed Ayurvedic/clinical literature.
> - **[C]** Clinician-provided — not yet available; reserved for items confirmed by the clinician review
>   (see `clinician_questionnaire.md`).
> - **[E]** Engineering assumption — how the kiosk can collect what clinicians need, without claiming
>   clinical equivalence to any modern diagnosis.
>
> Until an Ayurvedic clinician reviews and confirms this specification, the system remains a
> *provisional pilot intake framework* and **must not be presented as clinically validated**.
>
> Related: `clinician_questionnaire.md` (meeting agenda for Ayurvedic doctors),
> `terminology_review.md` (term-by-term provenance and status ledger).

---

## 1. Purpose & Non-Goals

**Purpose.** Provide a structured, clinician-reviewable specification of what information the MediKiosk
adaptive interviewer should gather for three pilot complaint domains — Digestive/GI, Musculoskeletal,
Respiratory — and how that information should appear in the doctor-facing summary.

**Non-goals (hard constraints).**
- **[C/E]** No Ayurvedic *diagnosis*, prognosis (sadhyasadhyata), dosha determination, or disease naming by the system.
- **[C/E]** No treatment, prescription, formulation, panchakarma, or autonomous clinical decision logic.
- **[E]** No fixed question sequence. This document is guidance/context for the LLM interviewer; the
  adaptive engine decides order based on gathered concepts (Phase 1 architecture, unchanged).
- **[E]** No question bank. Deterministic fallback questions are curated separately inside
  `backend/rules/adaptive_interview.py` and are not expanded here.

---

## 2. How to Read This Specification

Each requirement row is tagged `[S]`, `[C]`, or `[E]`. Three sub-classifications refine `[S]`:

1. **`[S-classical]`** — directly stated or near-directly implied in a classical samhita (e.g. Charaka,
   Sushruta, Ashtanga Hridaya, Madhava Nidana).
2. **`[S-review]`** — supported by peer-reviewed Ayurvedic/clinical literature or official curricula
   (e.g. CCIM/CCRAS syllabi), interpreting the classical text.
3. **`[S-corr]`** — an acknowledged *correlation* between an Ayurvedic and a biomedicine concept.
   Correlations are inherently provisional; they must be confirmed by clinicians before use in summary.

The task of the clinician review is to promote `[S-classical]`/`[S-review]`/`[S-corr]` items to
`[C]` (confirmed) or reject/correct them. See `clinician_questionnaire.md`.

---

## 3. Cross-Cutting Ayurvedic Concepts (all domains)

These concepts recur across all three pilot domains and inform how a clinician interprets patient
answers. The kiosk should gather the subset below as it becomes relevant — never as a fixed sci-fi
battery of questions.

### 3.1 Agni (digestive fire) — core lens
- **[S-classical]** `Agni` refers to the biological/metabolic fire; `Jatharagni` (gastric/duodenal
  digestive capacity) governs all other agnis. Agni states are classically grouped as
  *samagni* (balanced), *vishamagni* (irregular), *tikshnagni* (sharp/excess), *mandagni* (diminished).
  [Charaka Chikitsasthana 15/51; Ashtanga Hridaya]
- **[S-classical]** Weak (manda) agni → improper digestion → `ama` (undigested/metabolic waste).
  Ama is pathogenic and links GI disturbance to joint/body disorders (e.g. amavata, tamaka shwasa).
  [Madhava Nidana; reviewed in peer-reviewed literature]
- **[E]** Kiosk collects surrogate signals: appetite pattern, eating habits, post-meal fullness,
  digestion time ("do you feel heavy after meals?"), regular vs suppressed urges. No dosha scoring.

### 3.2 Ama (undigested matter / metabolic toxicity)
- **[S-classical]** Ama is the intermediate product of impaired digestion; signs include heaviness
  (gaurava), lassitude (alasya), anorexia (aruchi), body ache (angamarda), foul breath/stools,
  coating on tongue, joint stiffness. [Charaka; Madhava Nidana]
- **[E]** Kiosk collects observation-able patient reports (heaviness, fatigue, appetite, tongue coating
  if the patient mentions it). Ama detection as a *conclusion* is physician-only.

### 3.3 Srotas (channels) framing for the three domains
- **[S-classical]** Respiratory complaints are framed under *pranavaha* srotas; digestive under
  *annavaha* and *purishvaha* srotas; musculoskeletal/articular under *rasavaha*, *asthivaha*,
  *majjavaha* srotas. [Charaka; CCIM PG syllabus domain listing]
- **[E]** Used as internal organization of *history areas*, not as patient-facing terminology.

### 3.4 Dashavidha Pariksha (tenfold examination) — history scaffolding
- **[S-classical]** Charaka's tenfold patient assessment: prakriti, vikriti, sara, samhanana, pramana,
  satmya, satva, aharashakti, vyayama shakti, vaya. [Charaka Vimana sthana 8]
- **[E]** Feasible pillars for a kiosk interview: aharashakti (diet/capacity), satmya (habitual food
  tolerance), vaya (age), vyayama shakti (activity/exercise tolerance), and—where patients consent and
  it is culturally safe—prakriti (constitution). The rest require physician examination and stay
  physician-side.

### 3.5 Diet, lifestyle, context common battery (asked only as relevant)
- **[S-review]** Viruddha ahara (incompatible food combos), adhyashana (overeating / re-eating before
  prior meal digested), vishamashana (irregular meals), suppression of natural urges (vegadharana),
  sedentary habit (nishchalatva), exercise immediately after heavy food, and mental factors (chinta,
  shoka, krodha) are nidana (causal factors) classically emphasized across GI, joint, and respiratory
  disorders. [Charaka; Madhava Nidana]
- **[S-corr]** Correspond to modern lifestyle-history items: meal regularity, portion, food pairing,
  physical activity, sleep, stress, tobacco/alcohol, occupation. [Correlation awaiting clinician confirmation]
- **[E]** Harmonized kiosk questions, in patient vocabulary (en/hi/gu), tri-language.

---

## 4. Domain 1 — Digestive / GI (`annavaha`/`purishvaha`)

### 4.1 Common patient complaint expressions
- **[S-corr]** Patient lay terms (en/hi/gu) that overlap with classical entities:
  - acidity / burning in chest or throat / sour belching → correlated with *amlapitta* (urdhwaga).
  - indigestion, heavy feeling after meals, no appetite → correlated with *agnimandya*, *ajirna*,
    *aruchi*.
  - gas, bloating, distension → *adhamana*, *anaha*.
  - constipation / irregular bowel → *vibandha*, *malasanga*.
  - loose motions / diarrhea → *atisara*.
  - sour/bitter belching (amlodgara), heart/chest burning (hridkantadaha), nausea (hrillasatva),
    vomiting (chardi), loss of taste (aruchi). [Amlapitta symptom set, reviewed in literature]
- **[E]** Triggers already mapped in Phase 1 (stomach pain, acidity, gas, bloating, constipation,
  diarrhea, heartburn, indigestion, nausea, loss of appetite, vomiting, burping/belching, burning in
  stomach, irregular bowel) plus vernacular (gu/hi) equivalents.

### 4.2 Required history areas
| # | History area | Kiosk-collectable surrogate | Tag |
|---|---|---|---|
| 1 | Improvising primary symptom: which GI symptom is chief | chief complaint | [E] |
| 2 | Duration & onset (acute vs chronic) | duration; recent/gradual | [E] |
| 3 | Food relationship: after meals / empty stomach / specific foods (spicy, sour, fried, heavy) | food_relationship | [E] |
| 4 | Bowel habits: regularity, consistency, constipation/looseness, straining | bowel_habits | [E] |
| 5 | Appetite & digestion capacity (aharashakti; agni proxy) | appetite, post-meal fullness, digestion time | [S-classical] + [E] |
| 6 | Associated symptoms: nausea, sour/bitter belching, chest/throat burning, bloating, flatulence | associated_symptoms | [S-classical] |
| 7 | Relieving/aggravating context: time of day, posture, stress, smoking, alcohol | relieving_factors, triggers | [S-review] + [E] |

### 4.3 Important associated symptoms (watch for)
- **[S-classical]** Amlodgara (sour eructation), hridkanta daha (burning chest/throat), hrillasatva
  (nausea), chardi (vomiting), avipaka (indigestion), aruchi (loss of taste/appetite), udara adhamana
  (abdominal distension). [Amlapitta/Grahani/Ajirna symptom sets]
- **[S-corr]** For differential context only (never phrased diagnostically): unintentional weight loss,
  black/tarry stool (melena-like), blood in stool/vomitus (rakta), jaundice/yellow eyes (kamala),
  dysphagia (difficulty swallowing) — these are **red-flag escalations** (§4.5), not routine questions.

### 4.4 Relevant diet / lifestyle / context
- **[S-review]** Meals: regularity (vishamashana), quantity vs capacity (atishana/adhyashana),
  incompatible combinations (viruddha ahara), spicy/sour/fried/cold-heavy food tolerance (satmya),
  water patterns, tobacco, alcohol, chewing tobacco/paan, sleep & stress, occupation (overnight shift,
  sedentary), suppression of urges. [Charaka/Madhava + modern lifestyle correlations]
- **[E]** Collected only if not already present; adaptive engine caps at 5 questions/turn budget
  (Phase 1 MAX_TURNS), so incompleteness auto-flows into the doctor-facing summary as "not gathered".

### 4.5 Safety / red-flag considerations
- **[S-corr]** Immediate escalation (P0 freeze, per Phase 1 safety architecture):
  - vomiting blood / coffee-ground vomitus / black tarry stool
  - severe sudden abdominal pain (rigid/guarded abdomen), persistent non-billious vomiting
  - weight loss without effort, long-standing dysphagia
  - jaundice (yellow eyes/skin), high fever with abdominal pain
  - known ulcer/GB disease + severe pain (obstruction/perforation suspicion)
- **[E]** These are screening escalations only; the kiosk never determines their meaning.

### 4.6 Information that must remain physician-only (never asked by kiosk)
- **[C/E]** Nidana/diagnosis equivalence (e.g. "you have GERD/amalpitta"), dosha imbalance verdict,
  prognosis, whether ama is present, ulcer vs functional dyspepsia determination, treatment/pathya.

### 4.7 Doctor-facing summary requirements
- **[E]** Structured summary must include: chief GI symptom, duration/onset, food relationship,
  bowel habits, appetite/digestion pattern, associated symptoms, aggravators/relievers, red-flag status
  (escalated or clean), diet/lifestyle inputs gathered, explicitly flagged "not gathered" items.

---

## 5. Domain 2 — Musculoskeletal (`rasavaha`/`asthivaha`/`majjavaha`)

### 5.1 Common patient complaint expressions
- **[S-corr]** Patient lay terms overlapping classical entities:
  - joint pain with swelling/stiffness, multiple joints, morning stiffness → *amavata* (RA-correlated)
    vs *sandhigata vata* (OA-correlated) — kiosk collects features, never picks a name.
  - knee pain on stairs/walking, elderly, gradual — *sandhigata vata* features.
  - low back pain, prolonged sitting/standing — *katishula* / *katigata vata* contexts.
  - neck stiffness/cramp after cold/sudden movement — *manyastambha* contexts.
  - radiating leg pain — *grudhrasi* (sciatica-correlated) contexts.
  - gout-like hot swollen joint — *vatarakta* contexts.
- **[E]** Phase 1 triggers already mapped: back/lower back, knee, joint, shoulder, neck, stiffness,
  sprain, swelling in joint, arthritis, sciatica, muscle ache, leg/hip pain, spine/cervical/lumbar,
  plus gu/hi equivalents and classical tokens (sandhigata, amavata, kati, janu, greeva).

### 5.2 Required history areas
| # | History area | Kiosk-collectable surrogate | Tag |
|---|---|---|---|
| 1 | Site & laterality (which joints, L/R/both; symmetric vs asymmetric) | site, laterality | [E] |
| 2 | Duration & onset (acute/chronic; gradual vs sudden) | duration | [E] |
| 3 | Character (aching, burning, sharp, throbbing) & severity (0–10 / interference) | character, severity | [E] |
| 4 | Stiffness: morning stiffness duration, post-rest stiffness (gel phenomenon) | stiffness_or_swelling | [S-corr] (amavata/sandhigata relevance) |
| 5 | Swelling, warmth, redness of joints | stiffness_or_swelling | [S-classical] |
| 6 | Aggravating/relieving: movement, rest, cold, weather, massage/oil application | aggravating/relieving_factors | [S-review] |
| 7 | Functional limitation: stairs, walking distance, grip, dressing | functional_limitation | [E] |
| 8 | Systemic overlay: fever, fatigue, body ache (angamarda), loss of appetite (aruchi), heaviness (gaurava) | associated_symptoms | [S-classical] |

### 5.3 Important associated symptoms (watch for)
- **[S-classical]** For joint/body pains: sarva-anga shula/gaurava (general body pain/heaviness),
  stiffness (stabdhata), swelling (shotha/sandhi shotha), migratory pain (sanchari vedana), pyrexia
  (jwara), anorexia (aruchi), lassitude (alasya), thirst (trishna), oedema (anga shunata).
  [Amavata feature set — Madhava Nidana; reviewed]
- **[S-corr]** Red-flag associates for escalation (never diagnostic): unexplained weight loss + night
  pains, acute hot swollen joint (gout/crystal correlates), fever with joint swelling, trauma with
  inability to bear weight, limb weakness/numbness.

### 5.4 Relevant diet / lifestyle / context
- **[S-review]** Dietary nidana for joint/ama processes: viruddhahara, mandagni, sedentary habit,
  exercise right after heavy food, cold/damp exposure, night waking, mental stress.
- **[E]** Occupation (sitting/standing/lifting), daily activity level, sleep, food tolerance
  (especially heavy/oily), tobacco & alcohol, any prior trauma.

### 5.5 Safety / red-flag considerations
- **[S-corr]** Immediate escalation:
  - inability to bear weight / suspected fracture (trauma context)
  - acute hot swollen single joint (fever) — septic/gout-correlated
  - limb weakness (sudden), foot drop, saddle numbness, loss of bowel/bladder control
    (cauda-equina-style urgency — purely clinical screening)
  - fever + painful multiple joints associated with evening rise
  - unilateral swelling of calf (DVT-correlated suspicion) with breathlessness
- **[E]** Task of red-flag screen is detection-and-escalate, never interpretation.

### 5.6 Information that must remain physician-only
- **[C/E]** Disease naming (amavata vs sandhigata vata vs OA vs RA), dosha dominance determination,
  prognosis, determination of ama, need for panchakarma/basti, medication review.
- **[C]** Use of classical terms (amavata, sandhigata, vatarakta) to *describe* patient-reported features
  in summary is provisional and must be clinician-confirmed via terminology_review.md before any
  doctor-facing output uses them as interpretive labels.

### 5.7 Doctor-facing summary requirements
- **[E]** Site/laterality, duration & onset, character & severity, stiffness/swelling pattern,
  aggravators/relievers, functional impact, systemic overlay, red-flag status, diet/lifestyle inputs,
  flagged "not gathered" items.

---

## 6. Domain 3 — Respiratory (`pranavaha`)

### 6.1 Common patient complaint expressions
- **[S-classical]** Kasa (cough) is both a symptom and a disease; shwasa (dyspnea/shortness of breath)
  and pratishyaya (rhinitis/coryza) are the classical triad of common respiratory complaints.
  [Charaka Chikitsa 17–18; Sushruta Uttara; Ashtanga Hridaya]
- **[S-review]** Kasa subtypes are classically grouped by expectoration quality as guidance (dry vs
  productive-with-moderate vs thick-white-productive vs hemorrhagic/barky). Five classical types:
  vataja, pittaja, kaphaja, kshataja (hemorrhagic/trauma), kshayaja (wasting).
  [Charaka Chikitsa 18; widely reviewed in literature]
- **[E]** Phase 1 triggers already mapped: cough, cold, congestion, runny nose, sore throat, sneezing,
  phlegm/mucus, blocked nose, sinus, plus gu/hi equivalents and classical tokens (kasa, shwasa,
  pratishyaya).

### 6.2 Required history areas
| # | History area | Kiosk-collectable surrogate | Tag |
|---|---|---|---|
| 1 | Primary respiratory symptom (which is chief: cough / breathlessness / nose / throat) | primary_symptom | [E] |
| 2 | Onset & duration: acute (<2 wk), subacute, chronic (>2–3 mo) | onset, duration | [E] |
| 3 | Cough character: dry vs productive; sputum amount/color/consistency | cough_character | [S-review] |
| 4 | Breathlessness: baseline effort level, nocturnal attacks, orthopnea | severity, triggers | [S-classical] (shwasa) |
| 5 | Nasal: discharge quality, congestion, sneeze paroxysms | associated_symptoms | [S-classical] (pratishyaya) |
| 6 | Associated: fever, sore throat, body ache, headache, voice change (svarabheda), chest pain (parshvashula) | associated_symptoms | [S-classical] |
| 7 | Triggers/relievers: cold air, dust, smoke, seasonal shift, night pattern, food (cold/heavy/sweet/oily) | triggers, relieving_factors | [S-review] |

### 6.3 Important associated symptoms (watch for)
- **[S-classical]** Cough variants & tracers: dry hack (vataja features), yellow/thick expectoration
  (pittaja features), white-thick-productive (kaphaja), hoarseness (svarabheda), chest/side pain
  (parshva shula), fever, wasting/weakness (kshaya context). [Charaka Chikitsa 18]
- **[S-corr]** Red-flag escalations (never routine): hemoptysis (rakta in sputum), fever >3 days /
  high fever, rapid breathing at rest, chest pain, unintentional weight loss + night sweats
  (kshayaja/TB-correlated), bluish lips/fingers.

### 6.4 Relevant diet / lifestyle / context
- **[S-review]** Respiratory nidana emphasis: cold exposure, dust/smoke (raja-dhuma), cold water/food,
  heavy/sweet/oily foods and milk (which classically aggravate kaphaja), suppressed urges, sedentary
  habit, exercise; seasonal (ritucharya) transitions. [Charaka; Bhavaprakasha; reviewed]
- **[E]** Occupation (dust/fume exposure), smoking/chewing tobacco, cooking-fuel smoke (biomass/chullah),
  sleep posture, animal/pet exposure, past asthma/cough history, season of occurrence.

### 6.5 Safety / red-flag considerations
- **[S-corr]** Immediate escalation:
  - hemoptysis (blood in sputum)
  - breathlessness at rest / unable to speak full sentences / accessory-muscle breathing
  - high-grade fever with cough & chest pain, bluish lips/fingers (oxygenation concern)
  - choking episode, inhaled foreign body suspicion (children)
  - unintentional weight loss + night sweats + prolonged cough
- **[E]** Detection-and-escalate only.

### 6.6 Information that must remain physician-only
- **[C/E]** Diagnosis (kasa subtype naming, asthma/COPD/TB correspondence), severity of shwasa as a
  disease entity, whether rakta indicates kshataja/kshayaja status, treatment, inhaler/nebulizer advice.

### 6.7 Doctor-facing summary requirements
- **[E]** Primary symptom, onset & duration, cough character & sputum quality, breathlessness profile,
  nasal picture, associated symptoms, triggers/relievers, red-flag status, diet/lifestyle inputs,
  flagged "not gathered" items.

---

## 7. Governance Rules (applied by the adaptive interview system)

1. **[E]** Tagging is stateless per session; no dosha/agni/ama *conclusions* are stored or surfaced.
   Only patient-reported *concepts* and *feature prompts* are collected.
2. **[E]** Ayurvedic terminology in questions must always pair a patient-friendly phrase
   (en/hi/gu) with the classical term when needed for clarity — never classical term alone.
3. **[E]** Red-flag detection follows Phase 1 `evaluate_safety` (deterministic, P0 freeze). No LLM
   decisioning on red flags.
4. **[E]** The adaptive interviewer has a hard turn cap (Phase 1 MAX_TURNS=5). Incomplete areas flow
   to the doctor-facing summary as explicit gaps rather than extending the interview.
5. **[C]** Nothing in this spec changes Phase 1 architecture; all items here are *context/guidance*
   material to be consumed as reference by the conversational layer, pending clinician approval of each.

---

## 8. Open Questions Requiring Clinician Input (top priorities)
1. Do the three pilot domains and their required-history lists match your clinic's intake practice?
2. Which classical terms may the system *ask* patients to choose between (e.g. "is the sputum scanty and
   dry, yellow, or thick-white"?), and which must remain physician-interpreted only?
3. Acceptability of the amlapitta, amavata/sandhigata vata, kasa-subtype *correlations*
   recorded as `[S-corr]` in `terminology_review.md`.
4. Which associated symptoms are mandatory to capture in a 5-question budget per domain.
5. Appetite/digestion (agni proxy) capture acceptable to you across all three domains?
6. Inappropriate assumptions the system must never make (regional food, religion, gender, age,
   occupation, caste-linked diet) — to be listed in `clinician_questionnaire.md` §8.

---

## 9. Source Basis (primary references)
- Charaka Samhita: Sutra/Vimana/Chikitsa Sthana (Vimana 8 — Dashavidha; Chikitsa 15 — Agni;
  Chikitsa 17–18 — Shwasa/Hikka & Kasa; Grahani/Amlapitta & Vatavyadhi adhyayas).
- Sushruta Samhita: Uttara Tantra (Kasa/Shwasa/Pratishyaya) and Nidana Sthana.
- Ashtanga Hridaya (Vagbhata): Nidana & Chikitsa.
- Madhava Nidana (Madhavakara): Amavata (Nidana 25), Ama concept.
- CCIM (Central Council of Indian Medicine) PG Kayachikitsa syllabus — srotas grouping of classical
  rogas and modern correlates (Sdhigatavata≈OA; Amavata≈RA; Amlapitta≈GERD; etc.).
- Peer-reviewed reviews: Amlapitta (JAIMS 2025), Amavata (JAIMS, IJAR), Agni (PMC 3221079),
  Pratishyaya RCT protocol (PMC 11890129), Kasa subtypes (Ask-Ayurveda; EasyAyurveda; CCA).
- Note: these citations are mapping aids for clinician review, not validation.