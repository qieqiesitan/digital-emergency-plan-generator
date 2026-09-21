"""探测反代是否可用。"""
import urllib.request

for u in ("http://127.0.0.1:8099/",
          "http://127.0.0.1:8099/src/preview-desktop.html",
          "http://127.0.0.1:8099/src/preview-mobile.html"):
    try:
        with urllib.request.urlopen(u, timeout=20) as r:
            print(f"OK  {r.status}  {u}  {len(r.read())} 字节")
    except Exception as e:  # noqa: BLE001
        print(f"!!  {type(e).__name__}: {e}  {u}")
