import sqlite3
import json

DB_PATH = r"C:\Users\RED\.local\share\mimocode\mimocode.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get all sessions
cur.execute("SELECT * FROM session ORDER BY time_created")
sessions = cur.fetchall()
print(f"=== ALL SESSIONS ({len(sessions)}) ===")
for s in sessions:
    d = dict(s)
    print(f"\n  id={d['id']}")
    print(f"  project_id={d['project_id']}")
    print(f"  title={d.get('title','')}")
    print(f"  directory={d.get('directory','')}")
    print(f"  time_created={d.get('time_created','')}")
    print(f"  summary_files={d.get('summary_files','')}")
    print(f"  summary_additions={d.get('summary_additions','')}")
    print(f"  summary_deletions={d.get('summary_deletions','')}")
    print(f"  summary_diffs preview={str(d.get('summary_diffs',''))[:300]}")

# Count messages per session
cur.execute("""
    SELECT session_id, COUNT(*) as msg_count,
           SUM(CASE WHEN json_extract(data, '$.role') = 'user' THEN 1 ELSE 0 END) as user_count,
           SUM(CASE WHEN json_extract(data, '$.role') = 'assistant' THEN 1 ELSE 0 END) as asst_count
    FROM message GROUP BY session_id
""")
print("\n=== MESSAGES PER SESSION ===")
for r in cur.fetchall():
    print(f"  session={r[0]}  total={r[1]}  user={r[2]}  assistant={r[3]}")

# Count parts per session
cur.execute("SELECT session_id, COUNT(*) FROM part GROUP BY session_id")
print("\n=== PARTS PER SESSION ===")
for r in cur.fetchall():
    print(f"  session={r[0]}  parts={r[1]}")

# Actor registry
cur.execute("SELECT * FROM actor_registry")
actors = cur.fetchall()
print(f"\n=== ACTOR REGISTRY ({len(actors)}) ===")
for a in actors:
    d = dict(a)
    print(f"  actor={d.get('actor_id','')}  session={d.get('session_id','')}  agent={d.get('agent','')}  mode={d.get('mode','')}  desc={d.get('description','')}")

conn.close()
