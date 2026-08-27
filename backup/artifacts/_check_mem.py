import sqlite3
db = sqlite3.connect(r'C:\Users\55061\.codex\memories_1.sqlite')
# Show schema
cursor = db.execute("SELECT sql FROM sqlite_master WHERE type='table'")
for row in cursor:
    print(row[0])
print("=== DATA ===")
rows = db.execute("SELECT key, substr(value,1,300), created_at FROM memories ORDER BY key, created_at DESC LIMIT 20").fetchall()
for r in rows:
    print(f'KEY: {r[0]}')
    print(f'PREVIEW: {r[1][:200]}')
    print(f'CREATED: {r[2]}')
    print('---')
db.close()
