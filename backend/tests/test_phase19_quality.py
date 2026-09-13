"""Phase 1.9: repetition suppression + Gujarati generation-quality regression tests.

Covers:
- Semantic duplicate-information suppression at the case-state/extraction layer
  (exact, paraphrased, multilingual repetition; repeated concept + new info).
- Duration extraction coverage for the live EN Metabolic defect ("for the past month").
- Gujarati question-quality guard (no elliptical fragments) with natural
  duration / trigger-context / progression-severity questions accepted.
"""
from types import SimpleNamespace

from backend.rules.adaptive_interview import (
    DOMAIN_DIGESTIVE,
    extract_concepts_from_text,
    merge_extracted_concept,
    validate_llm_proposal,
)


def _proposal_namespace(concepts, q_text, q_concept, status="continue"):
    return SimpleNamespace(
        case_update=SimpleNamespace(concepts=concepts),
        next_question=SimpleNamespace(text=q_text, target_concept=q_concept, reason="r", priority="normal")
        if q_text
        else None,
        status=status,
    )


def _gu_session(collected=None, asked=None):
    return SimpleNamespace(
        presentation_domain=DOMAIN_DIGESTIVE,
        collected_concepts=collected or {},
        asked_concepts=asked or [],
        asked_questions=[],
        adaptive_question_count=0,
        denied_concepts=[],
        language="gu",
    )


# ---------------------------------------------------------------------------
# Semantic duplicate-information suppression
# ---------------------------------------------------------------------------

def test_p19_exact_repetition_is_suppressed():
    existing = "for the past month"
    assert merge_extracted_concept(existing, "for the past month") == existing


def test_p19_paraphrased_repetition_is_suppressed():
    existing = "for the past month"
    assert merge_extracted_concept(existing, "past month") == existing
    existing = "it started four days ago"
    assert merge_extracted_concept(existing, "it started four days back") == existing


def test_p19_repeated_concept_with_new_information_is_preserved():
    existing = "it started four days ago"
    new = "it started four days ago and today the burning became much worse"
    merged = merge_extracted_concept(existing, new)
    assert merged == new


def test_p19_multilingual_duplicate_is_suppressed():
    gu = "ચાર દિવસથી"
    assert merge_extracted_concept(gu, "ચાર દિવસથી") == gu
    hi = "पांच दिन से"
    assert merge_extracted_concept(hi, "पांच दिन से") == hi


# ---------------------------------------------------------------------------
# Duration extraction coverage (EN Metabolic live defect)
# ---------------------------------------------------------------------------

def test_p19_extracts_duration_from_for_the_past_month():
    concepts = extract_concepts_from_text(
        "I have been feeling extreme weakness and fatigue for the past month."
    )
    assert "duration" in concepts
    assert "past month" in concepts["duration"]


def test_p19_extracts_explicit_duration_with_digits():
    concepts = extract_concepts_from_text("It started four days ago.")
    assert concepts.get("duration") == "four days"


# ---------------------------------------------------------------------------
# Gujarati question-quality guard
# ---------------------------------------------------------------------------

def test_p19_rejects_gujarati_elliptical_fragment():
    result = validate_llm_proposal(
        _proposal_namespace({}, "નથી જમ્યા પછી જાય છે?", "aggravating_factors"),
        _gu_session(),
    )
    assert result.valid is False
    assert any("fragment" in r for r in result.reasons)


def test_p19_accepts_natural_gujarati_duration_question():
    result = validate_llm_proposal(
        _proposal_namespace({}, "આ પાચનની તકલીફ તમને કેટલા સમયથી છે?", "duration"),
        _gu_session(),
    )
    assert result.valid is True


def test_p19_accepts_natural_gujarati_trigger_context_question():
    result = validate_llm_proposal(
        _proposal_namespace({}, "શું જમ્યા પછી કે ખાલી પેટે આ બળતરા વધે છે?", "aggravating_factors"),
        _gu_session(),
    )
    assert result.valid is True


def test_p19_accepts_natural_gujarati_progression_severity_question():
    result = validate_llm_proposal(
        _proposal_namespace({}, "શું આ બળતરા દિવસેને દિવસે વધી રહી છે?", "severity"),
        _gu_session(),
    )
    assert result.valid is True