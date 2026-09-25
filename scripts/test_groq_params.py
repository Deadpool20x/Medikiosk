import httpx
import os
import json
import time
from dotenv import load_dotenv

load_dotenv(".env")

url = "https://api.groq.com/openai/v1/chat/completions"
api_key = os.getenv("GROQ_API_KEY", "")
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

body1 = {
    "model": "openai/gpt-oss-20b",
    "messages": [
        {"role": "system", "content": "You are a clinical interviewer. Output valid JSON: {\"question\": \"...\"}"},
        {"role": "user", "content": "मुझे दो दिन से पेट में दर्द है।"}
    ],
    "temperature": 0,
    "response_format": {"type": "json_object"}
}

t0 = time.time()
r1 = httpx.post(url, headers=headers, json=body1, timeout=15.0)
dt = time.time() - t0
print(f"Test 2 (WITH response_format): {r1.status_code} in {dt:.2f}s")
if r1.status_code == 200:
    data = r1.json()
    msg = data["choices"][0]["message"]
    print("Content:", msg.get("content"))
    print("Reasoning:", msg.get("reasoning"))
    print("Usage:", data.get("usage"))
else:
    print("Error:", r1.text[:200])
