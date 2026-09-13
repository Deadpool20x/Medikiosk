import asyncio
from dotenv import load_dotenv
load_dotenv('.env')

from backend.services.llm_provider import generate_adaptive_turn, iter_llm_providers

print('Active chain providers:', [p.provider_name for p in iter_llm_providers()])

contexts = {
    'en': {
        'language': 'en',
        'presentation_domain': 'Digestive',
        'interview_step': 'hpi',
        'collected_concepts': {'site': 'stomach', 'onset': '3 days ago'},
        'denied_concepts': ['fever', 'vomiting'],
        'last_patient_answer': 'I have a burning ache in my stomach after eating, but no fever.',
        'turns_count': 1,
        'questions_asked': ['What brings you in today?']
    },
    'hi': {
        'language': 'hi',
        'presentation_domain': 'Digestive',
        'interview_step': 'hpi',
        'collected_concepts': {'site': 'पेट', 'onset': 'दो दिन'},
        'denied_concepts': ['उल्टी'],
        'last_patient_answer': 'मुझे दो दिन से पेट में भारीपन लग रहा है, उल्टी नहीं हुई।',
        'turns_count': 1,
        'questions_asked': ['आपकी क्या समस्या है?']
    },
    'gu': {
        'language': 'gu',
        'presentation_domain': 'Digestive',
        'interview_step': 'hpi',
        'collected_concepts': {'site': 'પેટ', 'onset': 'બે દિવસ'},
        'denied_concepts': ['તાવ'],
        'last_patient_answer': 'મને બે દિવસથી પેટમાં બળતરા થાય છે, તાવ નથી.',
        'turns_count': 1,
        'questions_asked': ['તમને શું તકલીફ છે?']
    }
}

async def run_turns():
    for i, (lang, ctx) in enumerate(contexts.items()):
        if i > 0:
            print("Waiting 17s for Groq 8k TPM rate limit to reset...")
            await asyncio.sleep(17)
        res = await generate_adaptive_turn(ctx)
        provider = res.get('provider')
        text = res.get('next_question', {}).get('text')
        concept = res.get('next_question', {}).get('target_concept')
        conf = res.get('confidence')
        print(f"[{lang.upper()}] Provider: {provider} | Concept: {concept} | Confidence: {conf}")
        print(f"      Question: {text}")
        assert provider in ('groq', 'cerebras'), f"Unexpected provider: {provider}"
        assert 'compound-mini' not in str(provider), "Compound-mini must not be used"

if __name__ == '__main__':
    asyncio.run(run_turns())
