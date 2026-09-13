import json
import sqlite3
import sys

db, sid = sys.argv[1], sys.argv[2]
conn = sqlite3.connect(db)
cur = conn.cursor()
row = cur.execute("SELECT answer_records_json FROM sessions WHERE session_id = ?", (sid,)).fetchone()
if row is None or row[0] is None:
    print("no answer records found for", sid)
    conn.close()
    sys.exit(1)
recs = json.loads(row[0])
if not recs:
    print("empty answer records for", sid)
    conn.close()
    sys.exit(1)
recs[0]["needs_review"] = True
cur.execute("UPDATE sessions SET answer_records_json = ? WHERE session_id = ?", (json.dumps(recs), sid))
conn.commit()
conn.close()
print("flagged answer 0 for", sid)