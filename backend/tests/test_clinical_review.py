"""Graph B/H: clinician review ledger + contested-label guard tests.

Evidence anchors:
- docs/ayurvedic/terminology_review.md (SOURCE/UNRESOLVED, zero CONFIRMED)
- docs/ayurvedic/clinician_review_results_v1.md §6.A (empty until sign-off)
"""
import re
from types import SimpleNamespace

from backend.rules.clinical_review import (
    CONTESTED_CORRELATES,
    get_entry,
    is_patient_usable,
    is_reviewed,    ledger_items,
    load_ledger,
    required_history,
    reviewed_count,
)
from backend.rules import adaptive_interview as ai


def test_ledger_loads_with_version_and_entries():
    ledger = load_ledger()
    assert ledger["version"].startswith("1.0")
    assert len(ledger_items()) >= 80


def test_nothing_is_clinician_reviewed_yet():
    # Mirrors packet §6.A: empty until a clinician signs. If this fails, a
    # sign-off was transcribed — update expectations deliberately.
    assert reviewed_count() == 0
    for item in ledger_items():
        assert item["review_status"] == "provisional", item["id"]
        assert not is_reviewed(item["id"])
        assert item["reviewer"] is None
        assert item["review_date"] is None


def test_required_history_constrains_three_domains_without_ordering():
    gi = required_history("digestive")
    ms = required_history("musculoskeletal")
    rs = required_history("respiratory")
    assert {i["id"] for i in gi} == {f"H-GI-{n}" for n in range(1, 8)}
    assert {i["id"] for i in ms} == {f"H-MS-{n}" for n in range(1, 9)}
    assert {i["id"] for i in rs} == {f"H-RS-{n}" for n in range(1, 8)}
    # Ledger constrains WHAT is required; it carries no sequence.
    for item in gi + ms + rs:
        assert "order" not in item and "sequence" not in item


def test_contested_correlates_are_not_patient_usable():
    for term in ["Amlapitta", "amavata", "Sandhigata Vata", "Grudhrasi",
                 "Vatarakta", "Tamaka Shwasa", "Kshayaja", "Rajayakshma",
                 "Agnimandya", "Grahani"]:
        assert not is_patient_usable(term), term
    # Plain feature language is unaffected.
    assert is_patient_usable("sour belching")
    assert is_patient_usable("joint swelling")


def test_doctor_facing_fallback_library_uses_no_contested_label():
    # HUMAN_FALLBACK_LIBRARY is doctor- and patient-visible: it must contain
    # feature descriptions, never contested disease/dosha labels.
    blob = " ".join(
        text.lower()
        for concept in ai.HUMAN_FALLBACK_LIBRARY.values()
        for text in concept.values()
    )
    for correlate in CONTESTED_CORRELATES:
        assert correlate not in blob, correlate
    for domain in ai.DOMAIN_KNOWLEDGE_BASE.values():
        for q in domain.fallback_questions.values():
            joined = " ".join(q.values()).lower()
            for correlate in CONTESTED_CORRELATES:
                assert correlate not in joined, (domain.domain_id, correlate)


def test_ledger_patient_variants_use_pure_scripts():
    for item in ledger_items():
        for v in item.get("patient_variants", {}).get("gu", []):
            assert not re.search(r"[\u0900-\u097F]", v), (item["id"], v)
        for v in item.get("patient_variants", {}).get("hi", []):
            assert not re.search(r"[\u0A80-\u0AFF]", v), (item["id"], v)


def test_term_lookup_by_id():
    entry = get_entry("T-RS-01")
    assert entry["concept"] == "Kasa"
    assert entry["review_status"] == "provisional"
    assert get_entry("NOPE") is None


# ---------------------------------------------------------------------------
# Graph B/D: governance enforcement — provisional can never silently become
# authoritative; unsupported can never become a patient-facing label.
# ---------------------------------------------------------------------------

def _proposal(text, concept):
    return SimpleNamespace(
        case_update=SimpleNamespace(concepts={}),
        next_question=SimpleNamespace(text=text, target_concept=concept,
                                      reason="r", priority="normal"),
        status="continue",
    )


def _sess():
    from backend.rules.adaptive_interview import DOMAIN_DIGESTIVE
    return SimpleNamespace(
        presentation_domain=DOMAIN_DIGESTIVE, collected_concepts={},
        asked_concepts=["primary_symptom"], asked_questions=[],
        adaptive_question_count=1, denied_concepts=[], language="en")


def test_validator_rejects_contested_disease_labels():
    from backend.rules.adaptive_interview import validate_llm_proposal
    for text in ["Do you suffer from amlapitta after meals?",
                 "Is this amavata joint pain worse in the morning?",
                 "Could this be tamaka shwasa at night?",
                 "Have you been told you have sandhigata vata?",
                 "Is the grudhrasi pain radiating down your leg?"]:
        result = validate_llm_proposal(_proposal(text, "associated_symptoms"), _sess(), "digestive")
        assert result.valid is False, text
        assert any("unvalidated clinical label" in r for r in result.reasons), text


def test_validator_accepts_plain_feature_language():
    from backend.rules.adaptive_interview import validate_llm_proposal
    result = validate_llm_proposal(
        _proposal("Do sour burps come after meals or on an empty stomach?",
                  "food_relationship"),
        _sess(), "digestive")
    assert result.valid is True, result.reasons


def test_hypothetical_approval_leaves_real_ledger_untouched():
    from backend.rules.clinical_review import apply_review, load_ledger
    import copy
    draft = copy.deepcopy(load_ledger())
    updated = apply_review(draft, "T-GI-08", decision="CONFIRMED",
                           reviewer="Dr. Example, BAMS", date="2026-09-27",
                           notes="ok for test", final_wording="Amlapitta (test wording)")
    assert is_reviewed("T-GI-08") is False  # real ledger untouched
    assert reviewed_count() == 0
    approved = next(i for i in updated["items"] if i["id"] == "T-GI-08")
    assert approved["reviewer"] == "Dr. Example, BAMS"
    assert approved["accepted_terminology"] == "Amlapitta (test wording)"
    # input mapping not mutated
    assert draft["items"][7]["reviewer"] is None


def test_rejected_and_revised_are_representable():
    from backend.rules.clinical_review import apply_review, load_ledger
    import copy
    draft = copy.deepcopy(load_ledger())
    updated = apply_review(draft, "T-MS-01", decision="REJECTED",
                           reviewer="Dr. Example, BAMS", date="2026-09-27")
    entry = next(i for i in updated["items"] if i["id"] == "T-MS-01")
    assert entry["review_decision"] == "REJECTED"
    assert entry["review_status"] == "provisional"  # never silently confirmed


def test_no_review_record_without_explicit_evidence():
    from backend.rules.clinical_review import apply_review, load_ledger
    import copy
    import pytest
    draft = copy.deepcopy(load_ledger())
    with pytest.raises(ValueError):
        apply_review(draft, "T-GI-01", decision="CONFIRMED", reviewer="", date="2026-09-27")
    with pytest.raises(ValueError):
        apply_review(draft, "T-GI-01", decision="CONFIRMED", reviewer="Dr X", date="")
    with pytest.raises(ValueError):
        apply_review(draft, "T-GI-01", decision="MAYBE", reviewer="Dr X", date="2026-09-27")
    with pytest.raises(ValueError):
        apply_review(draft, "NOPE", decision="CONFIRMED", reviewer="Dr X", date="2026-09-27")


def test_insufficient_status_fails_safely():
    # Code paths asking "may this term label the patient?" get a hard no.
    for term in ["amlapitta", "vatarakta", "kshayaja kasa"]:
        assert not is_patient_usable(term)


def test_safety_gate_needs_no_ledger():
    # Graph F: emergency behavior is independent of review state, even when
    # the ledger itself is unreadable.
    from unittest.mock import patch
    from backend.rules import safety_rules, clinical_review
    from backend.models.schema import Session, Patient, HistoryOfPresentIllness, DoctorReview

    def blank():
        return Session(session_id="x", patient=Patient(name="P", age=30, gender="m"),
                       history_of_present_illness=HistoryOfPresentIllness(),
                       doctor_review=DoctorReview())

    with patch.object(clinical_review, "load_ledger", side_effect=RuntimeError("ledger gone")):
        assert safety_rules.evaluate_safety("severe chest pain", blank()).flagged is True
        assert clinical_review.clinical_mentions(blank()) == []
