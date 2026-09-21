"""直接取 /src/preview-mobile.tsx 的编译结果，看 Vite 报什么错。"""
import urllib.request

url = "http://127.0.0.1:8099/src/preview-mobile.tsx"
try:
    with urllib.request.urlopen(url, timeout=60) as r:
        body = r.read().decode("utf-8", errors="replace")
    print("status 200，前 800 字：")
    print(body[:800])
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
    print(e.read().decode("utf-8", errors="replace")[:1500])
