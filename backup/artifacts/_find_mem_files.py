import json
# Check if memories are stored as files in .codex directory
import os
codex_dir = r'C:\Users\55061\.codex'
for root, dirs, files in os.walk(codex_dir):
    for f in files:
        fp = os.path.join(root, f)
        if 'memor' in f.lower() or 'knowledge' in f.lower() or 'learn' in f.lower():
            print(fp)
