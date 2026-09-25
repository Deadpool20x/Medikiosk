import sys
import os
import json
import time
import httpx
from dotenv import load_dotenv

sys.path.insert(0, ".")
load_dotenv(".env")

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

def build_trimmed_prompts(language: str, answer: str, chief_complaint: str):
    session = MockSession(language, chief_complaint)
    ctx = build_conversation_context(session, answer)
    
    # If non-English, trim context to reduce BPE expansion
    if language in ("hi", "gu"):
        # Keep top 2 guidance and top 2 history
        ctx["concept_guidance"] = {k: v for i, (k, v) in enumerate(ctx.get("concept_guidance", {}).items()) if i < 2}
        ctx["conversation_history"] = ctx.get("conversation_history", [])[-2:]
        ctx.pop("concept_metadata", None)
        ctx.pop("matched_vernacular_phrases", None)

    lang_instructions = {
        "hi": "Respond in simple, polite Hindi (Devanagari script). Start question with क्या, कितने, कब, कहाँ, कैसे. Keep concept keys and JSON in English.",
        "gu": "Respond in simple, polite Gujarati (Gujarati script). Start question with શું, કેટલા, ક્યારે, ક્યાં, કેવી. Keep concept keys and JSON in English.",
        "en": "Generate next_question.text in clear, respectful English."
    }.get(language)

    if language in ("hi", "gu"):
        system_prompt = (
            "You are a clinical OPD intake interviewer for MediKiosk. "
            "Understand the patient's answer, update concepts, and propose ONE follow-up question.\n\n"
            "INVARIANTS:\n"
            "1. NEVER DIAGNOSE. 2. NEVER PRESCRIBE. 3. NEVER RE-ASK established or denied concepts. "
            f"4. LANGUAGE: {lang_instructions}\n\n"
            "Respond ONLY with valid JSON matching:\n"
            "{\n"
            '  "case_update": {\n'
            f'    "presentation": "{DOMAIN_DIGESTIVE}",\n'
            '    "concepts": {"concept_key": "patient statement"},\n'
            '    "denied_concepts": ["denied symptom"],\n'
            '    "mentioned_documents": []\n'
            "  },\n"
            '  "next_question": {\n'
            '    "text": "Question in requested language",\n'
            '    "target_concept": "concept_name",\n'
            '    "reason": "clinical reason",\n'
            '    "priority": "high"\n'
            "  },\n"
            '  "status": "continue|sufficient|clarify",\n'
            '  "confidence": 0.85\n'
            "}\n"
            f"Allowed concept keys: {json.dumps(sorted(ALL_ALLOWED_CONCEPTS))}."
        )
    else:
        # Original English prompt
        system_prompt = (
            "You are an empathetic, clinical OPD intake conversational interviewer for MediKiosk. "
            "Your task is to understand the patient's natural language answer, update structured concepts, "
            "and propose the next most clinically useful follow-up question.\n\n"
            "STRICT CONVERSATIONAL AND CLINICAL INVARIANTS:\n"
            "1. NEVER DIAGNOSE. Never suggest a condition, illness, dosha imbalance, or disease name.\n"
            "2. NEVER PRESCRIBE OR TREAT. Never recommend medicines, herbs, dosages, treatments, or Panchakarma.\n"
            "3. NEVER ASK FOR A FACT ALREADY SUFFICIENTLY ESTABLISHED.\n"
            "4. TREAT EXPLICIT NEGATIVES AS ESTABLISHED ABSENT FINDINGS.\n"
            "5. DO NOT INFER A DIFFERENT BODY SYSTEM WITHOUT EVIDENCE.\n"
            "6. DO NOT CONVERT UNCERTAINTY INTO CERTAINTY.\n"
            "7. ONE CLEAR PATIENT-FRIENDLY QUESTION.\n"
            "8. DO NOT EXPOSE INTERNAL CONCEPT NAMES.\n"
            "9. CATEGORY COMPATIBILITY.\n"
            "10. AYURVEDIC TERMS must remain provisional.\n"
            f"11. LANGUAGE: {lang_instructions}\n"
            "12. STRUCTURED JSON OUTPUT ONLY.\n"
            f"Allowed concept keys: {json.dumps(sorted(ALL_ALLOWED_CONCEPTS))}."
        )

    # ensure_ascii=False avoids escaping Devanagari/Gujarati into 6-byte \u0xxx sequences
    user_prompt = (
        f"Current Session Context:\n{json.dumps(ctx, indent=2, ensure_ascii=False)}\n\n"
        "Analyze the patient's current answer, update collected concepts, and propose the next question."
    )
    return system_prompt, user_prompt

def main():
    tokenizer = Tokenizer.from_pretrained("gpt2")
    scenarios = {
        "English (EN)": {
            "lang": "en",
            "cc": "I have had burning stomach pain for two days.",
            "ans": "I have a burning ache in my stomach after eating for the past two days, but no fever."
        },
        "Hindi (HI) Trimmed": {
            "lang": "hi",
            "cc": "मुझे दो दिन से पेट में जलन और दर्द हो रहा है।",
            "ans": "मुझे दो दिन से खाना खाने के बाद पेट में जलन और दर्द हो रहा है, लेकिन बुखार नहीं है।"
        },
        "Gujarati (GU) Trimmed": {
            "lang": "gu",
            "cc": "મને બે દિવસથી પેટમાં બળતરા અને દુખાવો થાય છે.",
            "ans": "મને છેલ્લા બે દિવસથી જમ્યા પછી પેટમાં બળતરા અને દુખાવો થાય છે, પણ તાવ નથી."
        }
    }

    print("=" * 75)
    print("TOKEN COMPARISON: TRIMMED SYSTEM PROMPT & ENSURE_ASCII=FALSE")
    print("=" * 75)
    print(f"{'Language':<22} | {'Chars':<8} | {'Tokens':<8} | {'Tokens/Char':<12}")
    print("-" * 75)

    for name, sc in scenarios.items():
        sys_p, usr_p = build_trimmed_prompts(sc["lang"], sc["ans"], sc["cc"])
        combined = sys_p + "\n\n" + usr_p
        encoded = tokenizer.encode(combined)
        print(f"{name:<22} | {len(combined):<8} | {len(encoded.ids):<8} | {len(encoded.ids)/len(combined):<12.3f}")

if __name__ == "__main__":
    main()
