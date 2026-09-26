"""Graph B/H: clinician review ledger + contested-label guard tests.

Evidence anchors:
- docs/ayurvedic/terminology_review.md (SOURCE/UNRESOLVED, zero CONFIRMED)
- docs/ayurvedic/clinician_review_results_v1.md §6.A (empty until sign-off)
"""
import re

from backend.rules.clinical_review import (
    CONTESTED_CORRELATES,
    get_entry,
    is_patient_usable,
    is_reviewed,
    ledger_items,
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
