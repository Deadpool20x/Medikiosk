import sys
import urllib.request
import json

BASE_URL = "http://127.0.0.1:8000"

def post_json(path, data=None):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode("utf-8") if data is not None else b"{}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_json(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print("=== TEST 1: Emergency trigger BEFORE any interview questions (Screen P01/P02) ===")
    s1 = post_json("/session/start", {
        "patient": {"name": "Aarav Sharma", "age": 42, "gender": "male"},
        "preferred_language": "hi",
        "visit_type": "new"
    })
    s1_id = s1["session_id"]
    print(f"Session 1 created: {s1_id}")

    em1 = post_json(f"/session/{s1_id}/emergency")
    print(f"Emergency triggered for s1: status={em1.get('status')}, patient_code={em1.get('patient_code')}")
    assert em1["status"] == "emergency_alerted", f"Expected emergency_alerted, got {em1}"
    assert em1.get("patient_code"), f"Expected non-empty patient_code, got {em1.get('patient_code')}"

    print("\n=== TEST 2: Emergency trigger during active interview (Screen P04) ===")
    s2 = post_json("/session/start", {
        "patient": {"name": "Meera Patel", "age": 35, "gender": "female"},
        "preferred_language": "gu",
        "visit_type": "new"
    })
    s2_id = s2["session_id"]
    print(f"Session 2 created: {s2_id}")

    post_json(f"/session/{s2_id}/consent")
    code_res = post_json(f"/session/{s2_id}/patient-code")
    s2_code = code_res["patient_code"]
    print(f"Session 2 consented, patient code: {s2_code}")

    ans_res = post_json(f"/session/{s2_id}/answer", {"answer": "હું છેલ્લા 10 દિવસથી પેટમાં દુખાવા સાથે પીડાઉં છું."})
    print(f"Session 2 answered Q1. Next question: {ans_res.get('next_question')[:40]}...")

    em2 = post_json(f"/session/{s2_id}/emergency")
    print(f"Emergency triggered for s2: status={em2.get('status')}, patient_code={em2.get('patient_code')}")
    assert em2["patient_code"] == s2_code

    print("\n=== TEST 3: Verify Doctor Emergency Feed ===")
    doctor_emergencies = get_json("/doctor/emergency")
    print(f"Total emergency items in feed: {len(doctor_emergencies)}")
    
    item1 = next((x for x in doctor_emergencies if x["session_id"] == s1_id), None)
    assert item1 is not None, f"Session 1 {s1_id} not found in emergency feed"
    print(f"Feed Item 1 verified: patient_code={item1['patient_code']}, reported_at={item1['reported_at']}, symptom={item1['symptom']}")
    assert item1["patient_code"].startswith("AIIA-"), f"Unexpected code: {item1['patient_code']}"
    assert "emergency assistance at kiosk" in str(item1["symptom"]).lower()

    item2 = next((x for x in doctor_emergencies if x["session_id"] == s2_id), None)
    assert item2 is not None, f"Session 2 {s2_id} not found in emergency feed"
    print(f"Feed Item 2 verified: patient_code={item2['patient_code']}, reported_at={item2['reported_at']}, symptom={item2['symptom']}")
    assert item2["patient_code"] == s2_code
    assert "emergency assistance at kiosk" in str(item2["symptom"]).lower()

    print("\n[SUCCESS] Emergency trigger verified across multiple screens and confirmed in doctor feed.")

if __name__ == "__main__":
    main()
