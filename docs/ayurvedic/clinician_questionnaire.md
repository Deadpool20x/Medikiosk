# MediKiosk Ayurvedic Clinician Review Questionnaire

> **Purpose of this document.** This is the structured agenda for a working session with Ayurvedic
> clinicians (B.A.M.S. / M.D. (Ay.) practitioners). The goal is to confirm, correct, or reject the
> sources-based specification in `clinical_interview_spec_v1.md` and the term standings in
> `terminology_review.md` — **before** any of it is used as authoritative clinical guidance by the
> adaptive interviewer.
>
> **Status: DRAFT AGENDA — awaiting clinician sign-off.** The system is **not** claimed to be
> Ayurvedic-clinically validated until this questionnaire is completed by at least one clinician and
> the answers are committed back into the specification.

---

## 0. Session Info (please complete)

| Field | Value |
|---|---|
| Clinician name | |
| Qualifications | |
| Institute / clinic | |
| Years in practice | |
| Languages of practice (en/hi/gu/other) | |
| Date | |
| Manner of review (in-person / remote / recorded notes) | |

---

## 1. Scope & Format

1. **[Confirm]** Are the three pilot complaint domains correctly scoped for a first release?
   - (a) Digestive/GI, (b) Musculoskeletal, (c) Respiratory — any to drop, add, or re-prioritize?
2. **[Confirm]** Is it acceptable that the kiosk gathers *history features only* (patient-reported),
   while all dosha/agni/ama/nidana conclusions remain physician-side?
3. **[Confirm]** Is it acceptable that interviews are capped at 5 questions? If a domain needs more,
   please tell us which areas are *mandatory* vs *optional* within that budget (see §7).

---

## 2. Digestive / GI domain

### 2.1 Required history areas
Please mark each as **Keep / Expand / Drop** and correct wording:
- [ ] Chief GI symptom identification
- [ ] Onset & duration (acute vs chronic)
- [ ] Food relationship (after meals / empty stomach / specific foods)
- [ ] Bowel habits (regularity, consistency, constipation/looseness)
- [ ] Appetite & digestion capacity (agni proxy: post-meal fullness, heaviness, digestion time)
- [ ] Associated symptoms (nausea, sour/bitter belching, chest/throat burning, bloating, flatulence)
- [ ] Relieving / aggravating context (time of day, posture, stress, smoking, alcohol)

### 2.2 Terminology
- Is the set **amlapitta / agnimandya / ajirna / aruchi / grahani / atisara / vibandha / adhamana /
  chardi / viruddha ahara** the set you would actually use with colleagues?
- Which of these should appear in patient-facing questions (with natural-language explanation), if any?
- Are the patient-friendly interpretations below correct?
  - Agni → "digestive strength / how well your digestion works"
  - Ama → "undigested / unprocessed food matter" (do NOT present as a diagnosis)
  - Mandagni → "slow or weak digestion"
  - Amlapitta → "sour acidity / burning" (questionable as label — please rule on §5)

### 2.3 Follow-up priorities
Rank (1=highest) which of these deserve priority follow-up in a 5-question budget:
- [ ] Food relationship
- [ ] Bowel habits
- [ ] Appetite/digestion
- [ ] Associated symptoms
- [ ] Triggers/relievers

### 2.4 Red flags
Please confirm or correct the escalation list for GI:
- [ ] Vomiting blood / coffee-ground vomitus / black tarry stool
- [ ] Severe sudden abdominal pain (rigid/guarded abdomen)
- [ ] Unintentional weight loss / long-standing difficulty swallowing
- [ ] Jaundice (yellow eyes/skin); high fever with abdominal pain
- [ ] Pain in known ulcer/GB disease requiring urgent attention
What are we **missing**? What is **over-called** (would produce false escalations)?

---

## 3. Musculoskeletal domain

### 3.1 Required history areas
- [ ] Site & laterality (which joints, symmetric/asymmetric)
- [ ] Duration & onset
- [ ] Character (aching/burning/sharp/throbbing) & severity
- [ ] Morning stiffness duration, post-rest stiffness
- [ ] Swelling / warmth / redness over joints
- [ ] Aggravating / relieving (movement, rest, cold, weather, oil application)
- [ ] Functional limitation (stairs, walking distance, grip, dressing)
- [ ] Systemic overlay (fever, fatigue, body ache, appetite loss, heaviness)

### 3.2 Terminology
- Is the set **amavata / sandhigata vata / katishula / katigata vata / manyastambha / grudhrasi /
  vatarakta** correct for the complaints we expect (joint pain, low back pain, neck stiffness,
  radiating leg pain, hot swollen joint)?
- Should the kiosk *ever* ask patients "do you have sandhigata vata / amavata?" or should those terms
  remain physician-side? Please rule on §5.

### 3.3 Follow-up priorities
Rank within a 5-question budget:
- [ ] Site & laterality
- [ ] Stiffness/swelling
- [ ] Aggravators/relievers
- [ ] Functional limitation
- [ ] Systemic overlay

### 3.4 Red flags
- [ ] Inability to bear weight / suspected fracture after trauma
- [ ] Acute hot swollen single joint (with fever)
- [ ] Sudden limb weakness / foot drop / saddle numbness / loss of bowel-bladder control
- [ ] Fever with multiple painful joints
- [ ] Unilateral calf swelling with breathlessness

---

## 4. Respiratory domain

### 4.1 Required history areas
- [ ] Primary symptom (cough / breathlessness / nasal / throat)
- [ ] Onset & duration (acute / subacute / chronic)
- [ ] Cough character & sputum (dry vs productive; amount/color/consistency)
- [ ] Breathlessness profile (effort baseline, nocturnal attacks, orthopnea)
- [ ] Nasal picture (discharge, congestion, sneezing paroxysms)
- [ ] Associated (fever, sore throat, body ache, voice change, chest/side pain)
- [ ] Triggers / relievers (cold air, dust, smoke, season, time of day, specific foods)

### 4.2 Terminology
- Is the triad **kasa / shwasa / pratishyaya** the right frame for cough / breathlessness / rhinitis?
- Patients report "kasa" for cough; should the system ask about *cough character* using
  descriptive analogies (scanty-dry / yellow-thick / white-thick) rather than dosha labels
  (vataja/pittaja/kaphaja)? Please rule on §5.

### 4.3 Follow-up priorities
Rank within a 5-question budget:
- [ ] Cough character / sputum
- [ ] Breathlessness profile
- [ ] Onset & duration
- [ ] Trigger / reliever
- [ ] Associated symptoms

### 4.4 Red flags
- [ ] Blood in sputum (hemoptysis)
- [ ] Breathlessness at rest / slurred speech-conversation difficulty / accessory breathing
- [ ] High fever with cough & chest pain; bluish lips/fingers
- [ ] Choking / inhaled foreign body suspicion
- [ ] Unintentional weight loss + night sweats + prolonged cough (TB-correlate)

---

## 5. Terminology: which terms may be used AT THE KIOSK (patient-facing) vs PHYSICIAN-ONLY

For each term below, check **P** (patient-facing acceptable with plain explanation) or **M**
(physician-only, kiosk must not present it), or **N** (should not be used at all).

| Term | P | M | N | Notes / correction |
|---|---|---|---|---|
| Agni | ☐ | ☐ | ☐ | |
| Ama | ☐ | ☐ | ☐ | |
| Mandagni / Agnimandya | ☐ | ☐ | ☐ | |
| Amlapitta | ☐ | ☐ | ☐ | |
| Ajirna | ☐ | ☐ | ☐ | |
| Grahani | ☐ | ☐ | ☐ | |
| Atisara | ☐ | ☐ | ☐ | |
| Vibandha | ☐ | ☐ | ☐ | |
| Amavata | ☐ | ☐ | ☐ | |
| Sandhigata Vata | ☐ | ☐ | ☐ | |
| Katishula / Katigata Vata | ☐ | ☐ | ☐ | |
| Manyastambha | ☐ | ☐ | ☐ | |
| Grudhrasi | ☐ | ☐ | ☐ | |
| Vatarakta | ☐ | ☐ | ☐ | |
| Kasa | ☐ | ☐ | ☐ | |
| Shwasa | ☐ | ☐ | ☐ | |
| Pratishyaya | ☐ | ☐ | ☐ | |
| Vata / Pitta / Kapha (as labels) | ☐ | ☐ | ☐ | |
| Prakriti / Vikriti | ☐ | ☐ | ☐ | |

---

## 6. Provisionally-correlated modern conditions (please confirm or correct)

The specification records these *correlations* (`[S-corr]`) purely as mapping aids. Please mark
**Agree / Disagree / Nuance** per row.

| Ayurvedic | Proposed modern correlate | Agree | Disagree | Nuance |
|---|---|---|---|---|
| Amlapitta | hyperacidity / acid-peptic / GERD | ☐ | ☐ | |
| Grahani roga | malabsorption / irritable bowel-like chronic GI | ☐ | ☐ | |
| Amavata | rheumatoid-arthritis-like | ☐ | ☐ | |
| Sandhigata vata | osteoarthritis-like | ☐ | ☐ | |
| Grudhrasi | sciatica-like | ☐ | ☐ | |
| Vatarakta | gout-like | ☐ | ☐ | |
| Kasa (subtypes) | cough tiers, not any single modern disease | ☐ | ☐ | |
| Shwasa | dyspnea / breathlessness | ☐ | ☐ | |
| Pratishyaya | rhinitis / common cold | ☐ | ☐ | |

---

## 7. Mandatory vs optional within the 5-question budget
For each domain, give the **mandatory** history areas that must never be skipped, and the **optional**
ones that may flow to the doctor's "not gathered" summary.

- Digestive/GI mandatory: ______________________  optional: ______________________
- Musculoskeletal mandatory: ______________________  optional: ______________________
- Respiratory mandatory: ______________________  optional: ______________________

---

## 8. Inappropriate assumptions the kiosk must NEVER make
Please check all that apply from your experience (and add others):
- [ ] Assuming a patient's diet is vegetarian / non-vegetarian by region or religion
- [ ] Assuming spice tolerance equals a "Pitta imbalance"
- [ ] Assuming age/occupation mapping for a joint complaint (e.g., "elderly, so osteoarthritis")
- [ ] Gender-biased assumptions about strength, pain tolerance, or mental factors
- [ ] Presuming fasting, meals timing, or panchakarma exposure
- [ ] Converting "loss of appetite" into a dosha verdict in the summary
- [ ] Presuming cancer-fear wording or prognosis framing
- [ ] Presenting any classical term as the patient's diagnosis
- [ ] Asking about symptoms that are embarrassing without careful framing (e.g., bowel detail in long lines)

Other: ______________________________________________________________________

---

## 9. Doctor-facing summary formatting
Review the proposed summary fields (per domain in `clinical_interview_spec_v1.md` §4.7/5.7/6.7):
1. Is the "collected concepts + not-gathered flags" layout useful at the clinic?
2. Should the summary mark each field with the **source tag** (`S-classical / S-review / S-corr`)?
3. Should Ayurvedic terms appear in bold with the plain-language equivalent next to them?
4. Is a "red-flag triggered → action taken" line required? (We will show whether P0 escalation fired.)

Paste any preferred summary template in **Appendix A**.

---

## 10. Sign-Off

- [ ] I have reviewed `clinical_interview_spec_v1.md` and `terminology_review.md`.
- [ ] I confirm the corrections above are my professional opinion for the three pilot domains.
- [ ] I understand nothing in this questionnaire grants diagnosis/treatment authority to the kiosk.
- [ ] Scope of confirmation: ☐ Digestive only ☐ Musculoskeletal only ☐ Respiratory only ☐ All three

Clinician signature: ______________________  Date: ______

---

## Appendix A — preferred doctor-facing summary template (paste or sketch here)