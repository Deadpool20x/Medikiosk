import sys
import os
import json
import time
import httpx
from dotenv import load_dotenv

sys.path.insert(0, ".")
load_dotenv(".env")

from backend.rules.adaptive_interview import (
    build_conversation_context,
    DOMAIN_DIGESTIVE,
    ALL_DOMAINS,
    ALL_ALLOWED_CONCEPTS,
)
from backend.services.llm_provider import GroqProvider

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
    return system_prompt, user_prompt

def call_groq_and_get_usage(system_prompt: str, user_prompt: str):
    api_key = os.getenv("GROQ_API_KEY", "")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "openai/gpt-oss-20b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"}
    }
    t0 = time.time()
    resp = httpx.post(url, headers=headers, json=body, timeout=30.0)
    dt = time.time() - t0
    if resp.status_code >= 400:
        return {"error": resp.status_code, "text": resp.text, "duration": dt}
    data = resp.json()
    usage = data.get("usage", {})
    usage["duration_seconds"] = dt
    usage["response_content_length"] = len(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
    return usage

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

    print("=" * 70)
    print("STEP 1: MEASURING EXACT TOKEN USAGE AND LATENCY ON GROQ (openai/gpt-oss-20b)")
    print("=" * 70)

    results = {}
    for name, sc in scenarios.items():
        print(f"\nEvaluating {name}...")
        sys_p, usr_p = build_prompts(sc["lang"], sc["ans"], sc["cc"])
        print(f"  System prompt chars: {len(sys_p)} | User prompt chars: {len(usr_p)}")
        
        # Call Groq
        usage = call_groq_and_get_usage(sys_p, usr_p)
        print(f"  Result: {usage}")
        results[name] = usage
        # Brief pause to not burst TPM
        time.sleep(5)

    print("\n" + "=" * 70)
    print("SIDE-BY-SIDE TOKEN COMPARISON TABLE:")
    print("=" * 70)
    print(f"{'Language':<15} | {'Prompt Tokens':<14} | {'Completion Tokens':<17} | {'Total Tokens':<12} | {'Duration (s)':<12}")
    print("-" * 75)
    for name, u in results.items():
        if "error" in u:
            print(f"{name:<15} | ERROR {u['error']} in {u['duration']:.2f}s: {u['text'][:40]}")
        else:
            print(f"{name:<15} | {u.get('prompt_tokens', 'N/A'):<14} | {u.get('completion_tokens', 'N/A'):<17} | {u.get('total_tokens', 'N/A'):<12} | {u.get('duration_seconds', 0.0):<12.2f}")

    with open("scripts/token_measurement_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
