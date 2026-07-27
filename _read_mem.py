import sqlite3, json
db = sqlite3.connect(r'C:\Users\55061\.codex\memories_1.sqlite')
rows = db.execute("SELECT thread_id, rollout_slug, substr(raw_memory,1,500) FROM stage1_outputs ORDER BY generated_at DESC").fetchall()
for r in rows:
    print(f'SLUG: {r[1]}')
    print(f'PREVIEW: {r[2][:300]}')
    print('---')
db.close()
