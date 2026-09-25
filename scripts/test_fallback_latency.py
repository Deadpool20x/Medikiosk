import time
import json
import urllib.request

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

def test_hindi_turn():
    # 1. Start session
    start_payload = {
        "patient": {"name": "राम कुमार", "age": 52, "gender": "male"},
        "preferred_language": "hi",
        "visit_type": "new"
    }
    start_res, code, dt = post_json("/session/start", start_payload)
    session_id = start_res["session_id"]
    post_json(f"/session/{session_id}/consent")
    post_json(f"/session/{session_id}/patient-code")

    answers = [
        "मुझे पिछले एक महीने से पेट में गैस और भोजन के बाद भारीपन की समस्या है।",
        "यह समस्या करीब 4 हफ्ते पहले शुरू हुई थी जब मेरा खान-पान अनियमित हुआ।",
        "दर्द हल्का है, 10 में से लगभग 4, लेकिन असहजता बनी रहती है।"
    ]

    for i, ans in enumerate(answers, 1):
        res, status, turn_dt = post_json(f"/session/{session_id}/answer", {"answer": ans})
        print(f"[HI Turn {i}] Latency: {turn_dt:.2f}s | HTTP {status} | Next Q: {res.get('next_question')[:50] if res.get('next_question') else 'Done'}")

if __name__ == "__main__":
    test_hindi_turn()
