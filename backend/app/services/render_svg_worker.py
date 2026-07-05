import sys, base64
from playwright.sync_api import sync_playwright

svg = base64.b64decode(sys.argv[1]).decode("utf-8")
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
    try:
        p = b.new_page(viewport={"width": 900, "height": 600})
        try:
            html = '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>' + svg + '</body></html>'
            p.set_content(html, wait_until="domcontentloaded", timeout=10000)
            p.wait_for_selector("svg", timeout=5000)
            p.wait_for_timeout(200)
            el = p.query_selector("svg")
            if el:
                sys.stdout.buffer.write(el.screenshot(type="png"))
            else:
                sys.stderr.write("no svg element")
                sys.exit(1)
        finally:
            p.close()
    finally:
        b.close()
