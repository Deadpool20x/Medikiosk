import sys
import os
import json
sys.path.insert(0, ".")

from tokenizers import Tokenizer
from backend.rules.adaptive_interview import (
    build_conversation_context,
    DOMAIN_DIGESTIVE,
    ALL_DOMAINS,
    ALL_ALLOWED_CONCEPTS,
)

class MockSession:
    def __init__(self, language: str, chief_complaint: str):
        self.language = language
        self.patient = type("Patient", (), {"name": "Test Patient", "age": 35, "gender": "female"})()
        self.chief_complaint = chief_complaint
        self.presentation_domain = DOMAIN_DIGESTIVE
        self.raw_answers = [
            {"field": "chief_complaint", "question_text": "What brings you in today?", "answer": chief_complaint}
        ]
        self.asked_questions = ["What brings you in today?"]
        self.asked_concepts = ["primary_symptom"]
        self.collected_concepts = {"site": "stomach", "onset": "2 days"}
        self.denied_concepts = ["fever"]
        self.concept_metadata = []
        self.adaptive_question_count = 1

def build_prompts(language: str, answer: str, chief_complaint: str):
    session = MockSession(language, chief_complaint)
    ctx = build_conversation_context(session, answer)
    
    allowed_domains = sorted(ALL_DOMAINS)
    allowed_concepts = sorted(ALL_ALLOWED_CONCEPTS)

    lang_instructions = {
        "hi": (
            "The patient's language is Hindi (hi). Generate next_question.text in simple, "
            "polite, conversational Hindi (Devanagari script), as a COMPLETE question starting "
            "with a question word such as क्या, कितने, कब, कहाँ, कैसे, कैसा. Never use an "
            "elliptical fragment and never drop the subject. Keep all concept keys and JSON in English."
        ),
        "gu": (
            "The patient's language is Gujarati (gu). Generate next_question.text in simple, "
            "polite, conversational Gujarati (Gujarati script), as a COMPLETE question starting "
            "with a question word such as શું, કેટલા, ક્યારે, ક્યાં, કયા, કેવી, કેવું. Never use "
            "an elliptical fragment (never begin with નથી) and never drop the subject. "
            "Keep all concept keys and JSON in English."
        ),
        "en": (
            "The patient's language is English (en). Generate next_question.text in clear, "
            "respectful, non-technical English."
        ),
    }.get(language)

    denial_hint = ctx.get("denial_hint", "")
    normalized_hint = ""
    norm_map = ctx.get("language_normalized_symptoms") or {}
    if norm_map:
        normalized_hint = (
            "The patient answered in a regional language. The following canonical meanings were "
            "recognized (use these, never invent different meanings): "
            + json.dumps(norm_map)
        )

    system_prompt = (
        "You are an empathetic, clinical OPD intake conversational interviewer for MediKiosk. "
        "Your task is to understand the patient's natural language answer, update structured concepts, "
        "and propose the next most clinically useful follow-up question.\n\n"
        "STRICT CONVERSATIONAL AND CLINICAL INVARIANTS:\n"
        "1. NEVER DIAGNOSE. Never suggest a condition, illness, dosha imbalance, or disease name.\n"
        "2. NEVER PRESCRIBE OR TREAT. Never recommend medicines, herbs, dosages, treatments, or Panchakarma.\n"
        "3. NEVER ASK FOR A FACT ALREADY SUFFICIENTLY ESTABLISHED. If a concept has a value in collected_concepts, "
        "do NOT ask for it again unless asking for necessary clarification.\n"
        "4. TREAT EXPLICIT NEGATIVES AS ESTABLISHED ABSENT FINDINGS. If the patient denies a symptom (e.g. 'no fever', 'no vomiting'), "
        "record it in denied_concepts and NEVER ask about it again unless clarifying.\n"
        "5. DO NOT INFER A DIFFERENT BODY SYSTEM WITHOUT EVIDENCE. Ground your interpretation strictly in the patient's words. "
        "Never convert stomach symptoms into jaw pain, or cough into knee pain.\n"
        "6. DO NOT CONVERT UNCERTAINTY INTO CERTAINTY. If regional language or statement is ambiguous, ask clarification.\n"
        "7. ONE CLEAR PATIENT-FRIENDLY QUESTION. Propose exactly ONE question using patient-friendly language.\n"
        "8. DO NOT EXPOSE INTERNAL CONCEPT NAMES. Never say words like 'laterality', 'functional limitation', 'character', or 'site' directly.\n"
        "9. CATEGORY COMPATIBILITY. Do not ask pain descriptors (sharp/dull/numbness) on metabolic weakness or fatigue.\n"
        "10. AYURVEDIC TERMS (e.g., Agni, Ama, Vata) must remain provisional/literature-informed and must never imply disease diagnosis.\n"
        f"11. LANGUAGE: {lang_instructions}\n"
        "12. STRUCTURED JSON OUTPUT ONLY. Respond with valid JSON matching:\n"
        "{\n"
        '  "case_update": {\n'
        f'    "presentation": "one of {json.dumps(allowed_domains)}",\n'
        f'    "concepts": {{ "concept_key": "patient statement" }},\n'
        '    "denied_concepts": ["denied symptom, e.g. fever, vomiting"],\n'
        '    "mentioned_documents": ["document mentioned by patient or empty list"]\n'
        "  },\n"
        '  "next_question": {\n'
        '    "text": "The patient-facing question in the requested language",\n'
        '    "target_concept": "the specific concept being explored",\n'
        '    "reason": "short clinical reason why this question is helpful",\n'
        '    "priority": "high|normal|optional"\n'
        "  },\n"
        '  "status": "continue|sufficient|clarify",\n'
        '  "confidence": 0.85\n'
        "}\n"
        f"Allowed concept keys: {json.dumps(allowed_concepts)}.\n"
        f"13. {denial_hint + ' ' if denial_hint else ''}"
        f"{normalized_hint + ' ' if normalized_hint else ''}"
    )

    user_prompt = (
        f"Current Session Context:\n{json.dumps(ctx, indent=2)}\n\n"
        "Analyze the patient's current answer, update collected concepts, and propose the next question."
    )
    return system_prompt, user_prompt, ctx

def main():
    scenarios = {
        "English (EN)": {
            "lang": "en",
            "cc": "I have had burning stomach pain for two days.",
            "ans": "I have a burning ache in my stomach after eating for the past two days, but no fever."
        },
        "Hindi (HI)": {
            "lang": "hi",
            "cc": "मुझे दो दिन से पेट में जलन और दर्द हो रहा है।",
            "ans": "मुझे दो दिन से खाना खाने के बाद पेट में जलन और दर्द हो रहा है, लेकिन बुखार नहीं है।"
        },
        "Gujarati (GU)": {
            "lang": "gu",
            "cc": "મને બે દિવસથી પેટમાં બળતરા અને દુખાવો થાય છે.",
            "ans": "મને છેલ્લા બે દિવસથી જમ્યા પછી પેટમાં બળતરા અને દુખાવો થાય છે, પણ તાવ નથી."
        }
    }

    # Use pretrained tokenizer from HuggingFace
    try:
        tokenizer = Tokenizer.from_pretrained("meta-llama/Llama-3.2-11B-Vision-Instruct")
    except Exception:
        try:
            tokenizer = Tokenizer.from_pretrained("gpt2")
        except Exception as e:
            print("Tokenizer load failed:", e)
            return

    print("=" * 75)
    print("STEP 1: TOKEN COUNT MEASUREMENT FOR EQUIVALENT TURNS")
    print(f"Tokenizer: {tokenizer.__class__.__name__}")
    print("=" * 75)
    print(f"{'Language':<15} | {'Chars':<8} | {'Tokens':<8} | {'Tokens/Char':<12} | {'Ratio vs EN':<12}")
    print("-" * 75)

    base_tokens = None
    for name, sc in scenarios.items():
        sys_p, usr_p, ctx = build_prompts(sc["lang"], sc["ans"], sc["cc"])
        combined = sys_p + "\n\n" + usr_p
        encoded = tokenizer.encode(combined)
        token_count = len(encoded.ids)
        char_count = len(combined)
        ratio = token_count / char_count
        if base_tokens is None:
            base_tokens = token_count
            vs_en = "1.00x (base)"
        else:
            vs_en = f"{token_count / base_tokens:.2f}x"

        print(f"{name:<15} | {char_count:<8} | {token_count:<8} | {ratio:<12.3f} | {vs_en:<12}")

        # Also count just the patient answer portion
        ans_encoded = tokenizer.encode(sc["ans"])
        print(f"   -> Patient Answer: '{sc['ans'][:40]}...' = {len(sc['ans'])} chars, {len(ans_encoded.ids)} tokens ({len(ans_encoded.ids)/len(sc['ans']):.2f} tok/char)")

if __name__ == "__main__":
    main()
