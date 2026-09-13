import sys
import asyncio
import time
import json
import urllib.request
sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv(".env")

from backend.services.llm_provider import (
    NvidiaNimProvider,
    GroqProvider,
    iter_llm_providers,
    provider_diagnostics,
)

BASE_URL = "http://127.0.0.1:8000"

def post_json(path, data=None):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode("utf-8") if data is not None else b"{}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=25.0) as resp:
            dt = time.time() - t0
            return json.loads(resp.read().decode("utf-8")), resp.status, dt
    except urllib.error.HTTPError as e:
        dt = time.time() - t0
        return {"error": str(e), "body": e.read().decode("utf-8", errors="ignore")}, e.code, dt
    except Exception as e:
        dt = time.time() - t0
        return {"error": str(e)}, 0, dt

def get_json(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            dt = time.time() - t0
            return json.loads(resp.read().decode("utf-8")), resp.status, dt
    except Exception as e:
        dt = time.time() - t0
        return {"error": str(e)}, 0, dt

CONVERSATIONS = {
    "English": {
        "lang": "en",
        "name": "Sarah Jenkins",
        "age": 45,
        "gender": "female",
        "answers": [
            "I have been having persistent lower back pain and joint stiffness in the mornings.",
            "It started about two months ago after some heavy gardening work.",
            "The pain is about a 6 out of 10, worse when sitting for long periods.",
            "It feels like a dull, aching sensation with occasional sharpness when standing up.",
            "I also notice some fatigue in the afternoons, but no fever or numbness."
        ]
    },
    "Hindi": {
        "lang": "hi",
        "name": "राम कुमार",
        "age": 52,
        "gender": "male",
        "answers": [
            "मुझे पिछले एक महीने से पेट में गैस और भोजन के बाद भारीपन की समस्या है।",
            "यह समस्या करीब 4 हफ्ते पहले शुरू हुई थी जब मेरा खान-पान अनियमित हुआ।",
            "दर्द हल्का है, 10 में से लगभग 4, लेकिन असहजता बनी रहती है।",
            "पेट में जलन और भारीपन जैसा महसूस होता है, भूख भी कम लगती है।",
            "खट्टी डकारें आती हैं, लेकिन उल्टी या बुखार नहीं है।"
        ]
    },
    "Gujarati": {
        "lang": "gu",
        "name": "ભાવેશ પટેલ",
        "age": 38,
        "gender": "male",
        "answers": [
            "મને છેલ્લા પંદર દિવસથી ગળામાં ખારાશ અને હળવી ઉધરસ રહે છે.",
            "આ તકલીફ 15 દિવસ પહેલાં ઋતુ બદલાવા સાથે શરૂ થઈ હતી.",
            "તીવ્રતા 10 માંથી 3 જેટલી છે, સવારે વધારે તકલીફ થાય છે.",
            "ગળામાં સૂકાપણું અને ખંજવાળ જેવો દુખાવો રહે છે.",
            "શરીરમાં થોડી સુસ્તી લાગે છે, પરંતુ કોઈ તાવ કે શ્વાસ લેવામાં તકલીફ નથી."
        ]
    }
}

async def benchmark_nvidia_nim(attempts: int = 10):
    print("\n" + "=" * 60)
    print(f"BENCHMARKING NVIDIA NIM RELIABILITY ({attempts} calls)")
    print("=" * 60)
    p = NvidiaNimProvider()
    if not p.is_configured():
        print("NvidiaNimProvider is NOT configured. Skipping benchmark.")
        return 0, 0, 0, []

    successes = 0
    failures = 0
    timeouts = 0
    latencies = []
    errors = []

    for i in range(attempts):
        t0 = time.time()
        try:
            res = await p.generate(
                prompt="State the primary physiological characteristic of Pitta dosha in under 10 words.",
                system_prompt="You are a clinical Ayurvedic assistant. Answer in concise JSON: {\"answer\": \"...\"}"
            )
            dt = time.time() - t0
            latencies.append(dt)
            successes += 1
            print(f"  [NIM #{i+1:02d}] SUCCESS in {dt:.2f}s | Response: {res[:50] if res else 'None'}...")
        except Exception as e:
            dt = time.time() - t0
            failures += 1
            err_str = f"{type(e).__name__}: {e}"
            errors.append(err_str)
            if "timeout" in err_str.lower() or dt >= 7.0:
                timeouts += 1
            print(f"  [NIM #{i+1:02d}] FAILED in {dt:.2f}s | Error: {err_str[:80]}")

    fail_rate = (failures / attempts) * 100
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0
    print(f"\nNVIDIA NIM Benchmark Results:")
    print(f"  Total Calls: {attempts}")
    print(f"  Successes:   {successes} ({(successes/attempts)*100:.1f}%)")
    print(f"  Failures:    {failures} ({fail_rate:.1f}%)")
    print(f"  Timeouts:    {timeouts}")
    print(f"  Avg Latency: {avg_lat:.2f}s")
    return successes, failures, timeouts, latencies

def run_end_to_end_conversations():
    print("\n" + "=" * 60)
    print("RUNNING MULTI-TURN CONVERSATIONS (5+ turns per language)")
    print("=" * 60)

    results = {}
    hangs_detected = []
    http_401_detected = []
    compound_mini_detected = []

    for language_name, convo in CONVERSATIONS.items():
        print(f"\n--- Starting {language_name} ({convo['lang'].upper()}) Conversation ---")
        # 1. Start session
        start_payload = {
            "patient": {"name": convo["name"], "age": convo["age"], "gender": convo["gender"]},
            "preferred_language": convo["lang"],
            "visit_type": "new"
        }
        start_res, code, dt = post_json("/session/start", start_payload)
        assert code == 200, f"Failed /session/start: {start_res}"
        session_id = start_res["session_id"]
        print(f"  Session created: {session_id} in {dt:.2f}s")

        # 2. Consent
        consent_res, code, dt = post_json(f"/session/{session_id}/consent")
        assert code == 200, f"Failed consent: {consent_res}"

        # 3. Patient code
        pcode_res, code, dt = post_json(f"/session/{session_id}/patient-code")
        assert code == 200, f"Failed patient code: {pcode_res}"
        patient_code = pcode_res["patient_code"]
        print(f"  Patient Code: {patient_code}")

        turn_logs = []

        # 4. Run 5 turns
        for turn_num, ans in enumerate(convo["answers"], 1):
            # Groq free tier limit is 8k TPM; add brief breathing room if needed to avoid throttling
            if turn_num > 1:
                time.sleep(3)

            ans_payload = {"answer": ans}
            ans_res, status_code, turn_dt = post_json(f"/session/{session_id}/answer", ans_payload)

            if status_code == 401:
                http_401_detected.append(f"{language_name} Turn {turn_num}")
            if turn_dt > 10.0:
                hangs_detected.append(f"{language_name} Turn {turn_num} ({turn_dt:.2f}s)")

            # Fetch session to inspect answer record and provider
            sess_data, _, _ = get_json(f"/session/{session_id}")
            records = sess_data.get("answer_records", [])
            last_record = records[-1] if records else {}
            provider_used = last_record.get("provider") or "unknown"

            if "compound-mini" in str(provider_used).lower():
                compound_mini_detected.append(f"{language_name} Turn {turn_num}")

            next_q = ans_res.get("next_question") or "None (Interview Complete)"
            print(f"  [Turn {turn_num}] Latency: {turn_dt:.2f}s | HTTP {status_code} | Provider: {provider_used}")
            print(f"    Answer:   {ans[:50]}...")
            print(f"    Next Q:   {next_q[:60]}...")

            turn_logs.append({
                "turn": turn_num,
                "answer": ans,
                "latency_s": round(turn_dt, 2),
                "http_status": status_code,
                "provider": provider_used,
                "next_question": next_q
            })

        results[language_name] = {
            "session_id": session_id,
            "patient_code": patient_code,
            "turns": turn_logs
        }

    return results, hangs_detected, http_401_detected, compound_mini_detected

async def main():
    print("Active Chain Priority:")
    for p in iter_llm_providers():
        print(f"  - {p.provider_name} (model: {p.model_name})")

    # 1. Benchmark NIM directly
    await benchmark_nvidia_nim(attempts=10)

    # 2. Run real conversations
    results, hangs, http_401s, compound_minis = run_end_to_end_conversations()

    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"Total Languages:       {len(results)}")
    print(f"Turns per Language:    5 (Total: {sum(len(v['turns']) for v in results.values())})")
    print(f"HTTP 401 Occurrences:  {len(http_401s)} ({http_401s})")
    print(f"Hangs (>10s):          {len(hangs)} ({hangs})")
    print(f"compound-mini in chain:{len(compound_minis)} ({compound_minis})")

    # Output JSON summary for evidence
    with open("scripts/provider_verification_report.json", "w", encoding="utf-8") as f:
        json.dump({
            "results": results,
            "hangs": hangs,
            "http_401s": http_401s,
            "compound_minis": compound_minis
        }, f, indent=2, ensure_ascii=False)
    print("\nReport written to scripts/provider_verification_report.json")

if __name__ == "__main__":
    asyncio.run(main())
