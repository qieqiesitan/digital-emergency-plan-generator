import sqlite3
db = sqlite3.connect(r'C:\Users\55061\.codex\state_5.sqlite')
cursor = db.execute("SELECT sql FROM sqlite_master WHERE type='table'")
for row in cursor:
    print(row[0])
db.close()
