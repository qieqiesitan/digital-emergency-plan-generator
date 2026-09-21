"""在后端容器里测：能不能直连前端容器的 dev server。"""
import urllib.error
import urllib.request

for url in (
    "http://emergency-plan-frontend:5173/",
    "http://emergency-plan-frontend:5173/src/preview-desktop.html",
    "http://host.docker.internal:5173/",
):
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            print(f"OK  {r.status}  {url}  ({len(r.read())} 字节)")
    except Exception as e:  # noqa: BLE001
        print(f"!!  {type(e).__name__}: {e}  {url}")
